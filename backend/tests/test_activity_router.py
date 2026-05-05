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


def test_list_activity_requires_auth(client_factory):
    client, _ = client_factory
    r = client.get("/api/activity")
    assert r.status_code == 401


def test_list_activity_empty(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.get("/api/activity")
    assert r.status_code == 200
    assert r.json() == {"items": []}


def test_list_activity_only_members(client_factory, db_session):
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

    r = client.get("/api/activity")
    items = r.json()["items"]
    assert [(x["type"], x["real_name"]) for x in items] == [
        ("member_joined", "Bob"),
        ("member_joined", "Alice"),
    ]
    assert items[1]["position"] == "SWE"
    assert items[0]["has_photo"] is False


def test_list_activity_only_jobs(client_factory, db_session):
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

    r = client.get("/api/activity")
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


def test_list_activity_merges_members_and_jobs_by_timestamp_desc(
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

    r = client.get("/api/activity")
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


def test_list_activity_respects_limit(client_factory, db_session):
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

    r = client.get("/api/activity?limit=5")
    items = r.json()["items"]
    assert len(items) == 5
    # The 5 newest are all jobs (Feb beats Jan), in descending order.
    assert [x["company"] for x in items] == ["J7", "J6", "J5", "J4", "J3"]


def test_list_activity_default_limit_is_ten(client_factory, db_session):
    client, login_as = client_factory
    for idx in range(15):
        _add_member(
            db_session,
            real_name=f"M{idx}",
            joined_at=datetime(2025, 1, 1 + idx, tzinfo=timezone.utc),
        )
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/activity")
    assert len(r.json()["items"]) == 10


def test_list_activity_rejects_limit_below_min(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.get("/api/activity?limit=0")
    assert r.status_code == 422


def test_list_activity_rejects_limit_above_max(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.get("/api/activity?limit=51")
    assert r.status_code == 422
