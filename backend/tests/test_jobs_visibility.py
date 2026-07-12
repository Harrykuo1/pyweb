import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Job, JobKind, Member, PostStatus, User, UserRole


@pytest.fixture
def client(db_session):
    admin = User(
        username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN
    )
    member = User(
        username="mem", password_hash=hash_password("mem-pw"), role=UserRole.MEMBER
    )
    db_session.add_all([admin, member])
    db_session.flush()
    db_session.add(
        Member(
            graduation_year=2024, real_name="會員", institution="X", user_id=member.id
        )
    )
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def _login(client, password):
    assert (
        client.post("/api/auth/login", json={"password": password}).status_code == 200
    )


def _add_job(db, **kw):
    defaults = {
        "job_year": 2024,
        "job_month": 3,
        "company": "Acme",
        "kind": JobKind.INTERNSHIP,
        "experience_md": "generic body",
        "status": PostStatus.ACCEPTED,
        "is_anonymous": False,
    }
    defaults.update(kw)
    j = Job(**defaults)
    db.add(j)
    db.commit()
    return j


def test_admin_list_shows_display_name_and_status_not_real_name(client, db_session):
    m = Member(graduation_year=2024, real_name="王小明", institution="X")
    db_session.add(m)
    db_session.flush()
    _add_job(db_session, subject_member_id=m.id)
    _login(client, "admin-pw")

    item = client.get("/api/jobs").json()["items"][0]
    assert item["display_name"] == "王小明"
    assert item["status"] == "accepted"
    assert "real_name" not in item


def test_admin_status_filter_returns_pending_queue(client, db_session):
    _add_job(db_session, company="A", status=PostStatus.ACCEPTED)
    _add_job(db_session, company="B", status=PostStatus.PENDING)
    _login(client, "admin-pw")

    companies = [
        i["company"] for i in client.get("/api/jobs?status=pending").json()["items"]
    ]
    assert companies == ["B"]


def test_non_admin_search_cannot_match_real_name(client, db_session):
    # A job whose author name lives in real_name; its body has no match.
    _add_job(
        db_session, company="Acme", real_name="SecretName", experience_md="generic body"
    )

    # Admin search covers real_name → finds it.
    _login(client, "admin-pw")
    admin_hits = [
        i["company"] for i in client.get("/api/jobs?q=SecretName").json()["items"]
    ]
    assert admin_hits == ["Acme"]

    # A non-admin member must not be able to reverse-lookup by name (§8).
    client.post("/api/auth/logout")
    _login(client, "mem-pw")
    assert client.get("/api/jobs?q=SecretName").json()["items"] == []


def test_non_admin_cannot_see_anonymous_author(client, db_session):
    m = Member(graduation_year=2024, real_name="匿名者", institution="X")
    db_session.add(m)
    db_session.flush()
    _add_job(
        db_session,
        subject_member_id=m.id,
        is_anonymous=True,
        status=PostStatus.ACCEPTED,
    )
    _login(client, "mem-pw")

    item = client.get("/api/jobs").json()["items"][0]
    assert item["is_anonymous"] is True
    assert item["display_name"] is None
    assert item["subject_member_id"] is None
    assert item["author_user_id"] is None
