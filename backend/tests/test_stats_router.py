from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Event, Job, JobKind, Member, User, UserRole


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


def _add_member(db_session, *, real_name, graduation_year=2025, institution="NTU"):
    db_session.add(
        Member(
            graduation_year=graduation_year,
            real_name=real_name,
            institution=institution,
        )
    )


def _add_job(
    db_session,
    *,
    company,
    job_year=2025,
    job_month=6,
    kind=JobKind.INTERNSHIP,
    status="accepted",
):
    db_session.add(
        Job(
            job_year=job_year,
            job_month=job_month,
            company=company,
            kind=kind,
            experience_md="x",
            status=status,
        )
    )


def test_stats_requires_auth(client_factory):
    client, _ = client_factory
    r = client.get("/api/stats")
    assert r.status_code == 401


def test_stats_empty_db(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.get("/api/stats")
    assert r.status_code == 200
    assert r.json() == {
        "total_members": 0,
        "total_jobs": 0,
        "total_events": 0,
        "total_companies": 0,
        "year_min": None,
        "year_max": None,
    }


def test_stats_counts_members_and_jobs(client_factory, db_session):
    client, login_as = client_factory
    _add_member(db_session, real_name="Alice")
    _add_member(db_session, real_name="Bob")
    _add_member(db_session, real_name="Carol")
    _add_job(db_session, company="Acme")
    _add_job(db_session, company="Globex")
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/stats")
    body = r.json()
    assert body["total_members"] == 3
    assert body["total_jobs"] == 2


def test_stats_counts_events(client_factory, db_session):
    client, login_as = client_factory
    db_session.add_all(
        [
            Event(title="春酒", event_date=date(2026, 3, 1), status="accepted"),
            Event(title="溪頭兩日遊", event_date=date(2026, 1, 15), status="accepted"),
        ]
    )
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/stats")
    assert r.json()["total_events"] == 2


def test_stats_hides_pending_and_suspended_from_non_admin(client_factory, db_session):
    # Non-admin totals must count only visible content, so the numbers can't
    # betray the existence of hidden posts or suspended members.
    client, login_as = client_factory
    _add_job(db_session, company="Public", status="accepted")
    _add_job(db_session, company="Hidden", status="pending")
    db_session.add_all(
        [
            Event(title="Public", event_date=date(2026, 3, 1), status="accepted"),
            Event(title="Hidden", event_date=date(2026, 3, 2), status="pending"),
        ]
    )
    _add_member(db_session, real_name="Active")
    suspended = User(
        role=UserRole.MEMBER, is_active=False, discord_id="susp", discord_username="s"
    )
    db_session.add(suspended)
    db_session.commit()
    db_session.add(
        Member(
            graduation_year=2025,
            real_name="Suspended",
            institution="X",
            user_id=suspended.id,
        )
    )
    db_session.commit()

    login_as("admin")
    a = client.get("/api/stats").json()
    assert (a["total_jobs"], a["total_events"], a["total_members"]) == (2, 2, 2)

    client.post("/api/auth/logout")
    login_as("viewer")
    v = client.get("/api/stats").json()
    assert v["total_jobs"] == 1
    assert v["total_events"] == 1
    assert v["total_members"] == 1
    assert v["total_companies"] == 1


def test_stats_counts_companies_distinct(client_factory, db_session):
    # Two jobs at the same company should count as one for total_companies.
    client, login_as = client_factory
    _add_job(db_session, company="Acme")
    _add_job(db_session, company="Acme")
    _add_job(db_session, company="Globex")
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/stats")
    assert r.json()["total_companies"] == 2


def test_stats_reports_year_min_and_max(client_factory, db_session):
    client, login_as = client_factory
    _add_job(db_session, company="A", job_year=2020)
    _add_job(db_session, company="B", job_year=2026)
    _add_job(db_session, company="C", job_year=2023)
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/stats")
    body = r.json()
    assert body["year_min"] == 2020
    assert body["year_max"] == 2026
