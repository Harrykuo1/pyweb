from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Job, JobKind, Member, User, UserRole


@pytest.fixture
def client_factory(db_session):
    db_session.add_all(
        [
            User(
                username="admin",
                password_hash=hash_password("admin-pw"),
                role=UserRole.ADMIN,
            ),
            User(
                username="viewer",
                password_hash=hash_password("viewer-pw"),
                role=UserRole.VIEWER,
            ),
        ]
    )
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)

    def login_as(role):
        creds = {
            "admin": ("admin", "admin-pw"),
            "viewer": ("viewer", "viewer-pw"),
        }[role]
        r = client.post(
            "/api/auth/login",
            json={"username": creds[0], "password": creds[1]},
        )
        assert r.status_code == 200, r.text

    try:
        yield client, login_as
    finally:
        client.close()
        app.dependency_overrides.clear()


def _add_member(db_session, *, real_name, joined_at, institution="NTU", position=None):
    db_session.add(
        Member(
            graduation_year=2025,
            real_name=real_name,
            institution=institution,
            position=position,
            joined_at=joined_at,
        )
    )


def _add_job(
    db_session,
    *,
    company,
    created_at,
    kind=JobKind.INTERNSHIP,
    real_name=None,
    category=None,
    job_year=2025,
    job_month=6,
):
    db_session.add(
        Job(
            job_year=job_year,
            job_month=job_month,
            company=company,
            category=category,
            kind=kind,
            experience_md="x",
            real_name=real_name,
            created_at=created_at,
        )
    )


def test_list_timeline_requires_auth(client_factory):
    client, _ = client_factory
    r = client.get("/api/timeline")
    assert r.status_code == 401


def test_list_timeline_empty(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.get("/api/timeline")
    assert r.status_code == 200
    assert r.json() == {"items": [], "has_more": False}


def test_list_timeline_only_members(client_factory, db_session):
    client, login_as = client_factory
    _add_member(
        db_session,
        real_name="Alice",
        joined_at=datetime(2025, 5, 1, tzinfo=timezone.utc),
        position="SWE",
    )
    _add_member(
        db_session,
        real_name="Bob",
        joined_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/timeline")
    items = r.json()["items"]
    assert [(x["type"], x["real_name"]) for x in items] == [
        ("member_joined", "Bob"),
        ("member_joined", "Alice"),
    ]
    assert items[1]["position"] == "SWE"
    assert items[0]["has_photo"] is False


def test_list_timeline_only_jobs(client_factory, db_session):
    client, login_as = client_factory
    _add_job(
        db_session,
        company="Acme",
        created_at=datetime(2025, 5, 1, tzinfo=timezone.utc),
        real_name="Alice",
    )
    _add_job(
        db_session,
        company="Globex",
        created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        real_name=None,
        category="Backend",
    )
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/timeline")
    items = r.json()["items"]
    assert [(x["type"], x["company"]) for x in items] == [
        ("job_created", "Globex"),
        ("job_created", "Acme"),
    ]
    # Anonymous job preserves null real_name so the frontend can render
    # "匿名成員" without ambiguity.
    assert items[0]["real_name"] is None
    assert items[0]["category"] == "Backend"
    assert items[1]["real_name"] == "Alice"


def test_list_timeline_merges_members_and_jobs_by_timestamp_desc(
    client_factory, db_session
):
    client, login_as = client_factory
    # Interleave timestamps so the only correct ordering is a true merge,
    # not just members-then-jobs or vice versa.
    _add_member(
        db_session,
        real_name="Alice",
        joined_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    _add_job(
        db_session,
        company="Acme",
        created_at=datetime(2025, 2, 1, tzinfo=timezone.utc),
    )
    _add_member(
        db_session,
        real_name="Bob",
        joined_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
    )
    _add_job(
        db_session,
        company="Globex",
        created_at=datetime(2025, 4, 1, tzinfo=timezone.utc),
    )
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/timeline")
    items = r.json()["items"]
    labels = [
        (x["type"], x.get("company") or x.get("real_name")) for x in items
    ]
    assert labels == [
        ("job_created", "Globex"),
        ("member_joined", "Bob"),
        ("job_created", "Acme"),
        ("member_joined", "Alice"),
    ]


def test_list_timeline_respects_limit(client_factory, db_session):
    client, login_as = client_factory
    for idx in range(8):
        _add_member(
            db_session,
            real_name=f"M{idx}",
            joined_at=datetime(2025, 1, 1 + idx, tzinfo=timezone.utc),
        )
    for idx in range(8):
        _add_job(
            db_session,
            company=f"J{idx}",
            created_at=datetime(2025, 2, 1 + idx, tzinfo=timezone.utc),
        )
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/timeline?limit=5")
    items = r.json()["items"]
    assert len(items) == 5
    # The 5 newest are all jobs (Feb beats Jan), in descending order.
    assert [x["company"] for x in items] == ["J7", "J6", "J5", "J4", "J3"]


def test_list_timeline_default_limit_is_ten(client_factory, db_session):
    client, login_as = client_factory
    for idx in range(15):
        _add_member(
            db_session,
            real_name=f"M{idx}",
            joined_at=datetime(2025, 1, 1 + idx, tzinfo=timezone.utc),
        )
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/timeline")
    assert len(r.json()["items"]) == 10


def test_list_timeline_rejects_limit_below_min(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.get("/api/timeline?limit=0")
    assert r.status_code == 422


def test_list_timeline_rejects_limit_above_max(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.get("/api/timeline?limit=51")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Cursor pagination via `before`
# ---------------------------------------------------------------------------


def test_list_timeline_has_more_true_when_more_rows_exist(client_factory, db_session):
    client, login_as = client_factory
    # 8 total members, asking for 5 → 3 still older than the last one.
    for idx in range(8):
        _add_member(
            db_session,
            real_name=f"M{idx}",
            joined_at=datetime(2025, 1, 1 + idx, tzinfo=timezone.utc),
        )
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/timeline?limit=5")
    body = r.json()
    assert len(body["items"]) == 5
    assert body["has_more"] is True


def test_list_timeline_has_more_false_when_exactly_limit_rows(client_factory, db_session):
    client, login_as = client_factory
    for idx in range(5):
        _add_member(
            db_session,
            real_name=f"M{idx}",
            joined_at=datetime(2025, 1, 1 + idx, tzinfo=timezone.utc),
        )
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/timeline?limit=5")
    body = r.json()
    assert len(body["items"]) == 5
    assert body["has_more"] is False


def test_list_timeline_paginates_via_before_cursor(client_factory, db_session):
    client, login_as = client_factory
    # Mix of members and jobs interleaved across days so the merged feed
    # is genuinely sorted across both tables, not just members-then-jobs.
    for idx in range(6):
        _add_member(
            db_session,
            real_name=f"M{idx}",
            joined_at=datetime(2025, 1, 1 + idx, tzinfo=timezone.utc),
        )
    for idx in range(6):
        _add_job(
            db_session,
            company=f"J{idx}",
            created_at=datetime(2025, 1, 1 + idx, 12, tzinfo=timezone.utc),
        )
    db_session.commit()
    login_as("viewer")

    # First page: newest 4 across both tables.
    page1 = client.get("/api/timeline?limit=4").json()
    assert len(page1["items"]) == 4
    assert page1["has_more"] is True

    # Cursor-walk: hand the last item's timestamp back as `before`.
    cursor = page1["items"][-1]["timestamp"]
    page2 = client.get(f"/api/timeline?limit=4&before={cursor}").json()
    assert len(page2["items"]) == 4
    assert page2["has_more"] is True
    # No overlap between the two pages — `before` is a strict <.
    seen_keys_p1 = {(x["type"], x.get("member_id") or x.get("job_id")) for x in page1["items"]}
    seen_keys_p2 = {(x["type"], x.get("member_id") or x.get("job_id")) for x in page2["items"]}
    assert seen_keys_p1.isdisjoint(seen_keys_p2)

    # Page 2's last item is older than page 1's last item.
    assert page2["items"][-1]["timestamp"] < page1["items"][-1]["timestamp"]


def test_list_timeline_pagination_walks_to_end(client_factory, db_session):
    client, login_as = client_factory
    for idx in range(7):
        _add_member(
            db_session,
            real_name=f"M{idx}",
            joined_at=datetime(2025, 1, 1 + idx, tzinfo=timezone.utc),
        )
    db_session.commit()
    login_as("viewer")

    # Walk until has_more flips false. With 7 rows, limit=3 → pages of
    # 3, 3, 1, with the last page reporting has_more=False.
    collected: list[str] = []
    cursor = None
    while True:
        url = "/api/timeline?limit=3"
        if cursor is not None:
            url += f"&before={cursor}"
        body = client.get(url).json()
        collected.extend(x["real_name"] for x in body["items"])
        if not body["has_more"]:
            break
        cursor = body["items"][-1]["timestamp"]

    # All 7 members reached, newest first, with no duplicates.
    assert collected == [f"M{idx}" for idx in reversed(range(7))]


def test_list_timeline_before_with_no_older_rows_returns_empty(client_factory, db_session):
    client, login_as = client_factory
    _add_member(
        db_session,
        real_name="Alice",
        joined_at=datetime(2025, 5, 1, tzinfo=timezone.utc),
    )
    db_session.commit()
    login_as("viewer")

    # Cursor older than the only row → empty + has_more=False.
    body = client.get(
        "/api/timeline?before=2025-01-01T00:00:00%2B00:00"
    ).json()
    assert body == {"items": [], "has_more": False}
