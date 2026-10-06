"""Exercise the migrated database over real HTTP with independent connections."""

import json
import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
URL = "/api/activity/batches"


@pytest.fixture
def live_api(tmp_path, postgres_url):
    database = create_engine(postgres_url)
    env = {
        **os.environ,
        "DATABASE_URL": postgres_url,
        "SESSION_SECRET": "isolated-http-test",
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        check=True,
        capture_output=True,
    )
    credential = json.loads(
        subprocess.check_output(
            [
                sys.executable,
                "-m",
                "app.activity_tokens",
                "create",
                "--guild-id",
                "100",
                "--name",
                "http-test",
            ],
            cwd=BACKEND_ROOT,
            env=env,
            text=True,
        )
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    processes = []
    log = (tmp_path / "uvicorn.log").open("w+")

    def start():
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=BACKEND_ROOT,
            env=env,
            stdout=log,
            stderr=log,
        )
        processes.append(process)
        deadline = time.monotonic() + 20
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", trust_env=False
        ) as probe:
            while time.monotonic() < deadline and process.poll() is None:
                try:
                    if probe.get("/health").status_code == 200:
                        return
                except httpx.ConnectError:
                    pass
                time.sleep(0.05)
        log.flush()
        log.seek(0)
        pytest.fail(f"API startup failed: {log.read()}")

    def restart():
        processes[-1].terminate()
        processes[-1].wait(timeout=10)
        start()

    try:
        start()
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            trust_env=False,
            timeout=20,
            headers={"Authorization": f"Bearer {credential['token']}"},
        ) as client:
            yield client, database, restart
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        log.close()
        database.dispose()


def batch(start=0, count=500):
    stamp = datetime(2026, 1, 1, 10, tzinfo=UTC)
    return {
        "guild_id": "100",
        "messages": [
            {
                "message_id": str(100000 + i),
                "user_id": "300",
                "channel_id": "400",
                "sent_at": (stamp + timedelta(seconds=i)).isoformat(),
                "reply_to_user_id": "500",
                "text_length": i,
                "attachment_count": i % 3,
            }
            for i in range(start, start + count)
        ],
        "voice_samples": [
            {
                "user_id": "300",
                "channel_id": "600",
                "sampled_at": (
                    stamp + timedelta(minutes=i, microseconds=123456)
                ).isoformat(),
            }
            for i in range(start, start + count)
        ],
    }


def test_real_http_writes_ten_thousand_rows_and_survives_restart(live_api):
    client, database, restart = live_api
    for start in range(0, 5000, 500):
        response = client.post(URL, json=batch(start))
        assert response.status_code == 200, response.text
        assert response.json() == {
            "messages": {"inserted": 500, "duplicates": 0},
            "voice_samples": {"inserted": 500, "duplicates": 0},
        }
    with database.begin() as connection:
        for table in ("message_events", "voice_samples"):
            assert (
                connection.exec_driver_sql(f"SELECT count(*) FROM {table}").fetchone()[
                    0
                ]
                == 5000
            )
        assert connection.exec_driver_sql(
            "SELECT user_id, channel_id, reply_to_user_id, text_length, attachment_count, sent_at "
            "FROM message_events WHERE message_id = '100002'"
        ).fetchone() == (
            "300",
            "400",
            "500",
            2,
            2,
            datetime(2026, 1, 1, 10, 0, 2, tzinfo=UTC),
        )
        assert connection.exec_driver_sql(
            "SELECT min(sampled_at) FROM voice_samples"
        ).fetchone()[0] == datetime(2026, 1, 1, 10, 0, 0, 123456, tzinfo=UTC)
    restart()
    retried = client.post(URL, json=batch())
    assert retried.status_code == 200, retried.text
    assert retried.json()["messages"] == {"inserted": 0, "duplicates": 500}
    assert retried.json()["voice_samples"] == {"inserted": 0, "duplicates": 500}


def test_eight_concurrent_retries_insert_each_event_once(live_api):
    client, database, _ = live_api
    # Force transactions to overlap after acquiring their first row lock.
    with database.begin() as connection:
        connection.exec_driver_sql("""
            CREATE FUNCTION overlap_ingest() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF current_setting('pyweb.delayed', true) IS DISTINCT FROM '1'
                   AND current_setting('pyweb.delayed', true) IS DISTINCT FROM '2' THEN
                    PERFORM set_config('pyweb.delayed', '1', true);
                ELSIF current_setting('pyweb.delayed', true) = '1' THEN
                    PERFORM set_config('pyweb.delayed', '2', true);
                    PERFORM pg_sleep(0.5);
                END IF;
                RETURN NEW;
            END $$
        """)
        connection.exec_driver_sql("""
            CREATE TRIGGER overlap_ingest BEFORE INSERT ON message_events
            FOR EACH ROW EXECUTE FUNCTION overlap_ingest()
        """)
    body = batch()
    bodies = []
    for offset in range(8):
        variant = {"guild_id": body["guild_id"]}
        for key in ("messages", "voice_samples"):
            rows = body[key]
            rotated = rows[offset * 61 :] + rows[: offset * 61]
            variant[key] = rotated if offset % 2 else list(reversed(rotated))
        bodies.append(variant)
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(
            pool.map(lambda payload: client.post(URL, json=payload), bodies)
        )
    for response in responses:
        assert response.status_code == 200, response.text
    for kind in ("messages", "voice_samples"):
        assert sum(r.json()[kind]["inserted"] for r in responses) == 500
        assert sum(r.json()[kind]["duplicates"] for r in responses) == 3500
    with database.begin() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM message_events"
            ).fetchone()[0]
            == 500
        )
        assert (
            connection.exec_driver_sql("SELECT count(*) FROM voice_samples").fetchone()[
                0
            ]
            == 500
        )


def test_real_database_failure_rolls_back_and_retry_recovers(live_api):
    client, database, _ = live_api
    body = batch(count=3)
    with database.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE voice_samples ADD CONSTRAINT fail_voice CHECK (false)"
        )
    assert client.post(URL, json=body).status_code == 500
    with database.begin() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM message_events"
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.exec_driver_sql("SELECT count(*) FROM voice_samples").fetchone()[
                0
            ]
            == 0
        )
        connection.exec_driver_sql(
            "ALTER TABLE voice_samples DROP CONSTRAINT fail_voice"
        )
    # Uvicorn closes the connection after the unhandled storage error. A
    # fresh pool avoids racing that close by reusing the failed connection.
    with httpx.Client(
        base_url=client.base_url,
        headers=client.headers,
        trust_env=False,
        timeout=20,
    ) as retry_client:
        retried = retry_client.post(URL, json=body)
    assert retried.status_code == 200, retried.text
    assert retried.json()["messages"]["inserted"] == 3
    assert retried.json()["voice_samples"]["inserted"] == 3
    with database.begin() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM message_events"
            ).fetchone()[0]
            == 3
        )
        assert (
            connection.exec_driver_sql("SELECT count(*) FROM voice_samples").fetchone()[
                0
            ]
            == 3
        )
