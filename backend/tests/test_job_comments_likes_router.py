from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Job, JobKind, Member, PostStatus, User, UserRole


@pytest.fixture
def ctx(db_session):
    admin = User(
        username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN
    )
    viewer = User(
        username="viewer",
        password_hash=hash_password("viewer-pw"),
        role=UserRole.VIEWER,
    )
    mem = User(
        username="mem", password_hash=hash_password("mem-pw"), role=UserRole.MEMBER
    )
    other = User(
        username="other", password_hash=hash_password("other-pw"), role=UserRole.MEMBER
    )
    np = User(username="np", password_hash=hash_password("np-pw"), role=UserRole.MEMBER)
    db_session.add_all([admin, viewer, mem, other, np])
    db_session.flush()
    mem_member = Member(
        graduation_year=2024,
        real_name="我本人",
        institution="X",
        user_id=mem.id,
        photo_content_type="image/png",
        photo_updated_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    db_session.add_all(
        [
            mem_member,
            Member(
                graduation_year=2024, real_name="別人", institution="Y", user_id=other.id
            ),
        ]
    )
    db_session.flush()
    job = Job(
        job_year=2024,
        job_month=6,
        company="Acme",
        kind=JobKind.INTERNSHIP,
        experience_md="心得",
        status=PostStatus.ACCEPTED,
        subject_member_id=mem_member.id,
    )
    db_session.add(job)
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)

    def login(pw):
        assert client.post("/api/auth/login", json={"password": pw}).status_code == 200

    try:
        yield client, login, job.id
    finally:
        client.close()
        app.dependency_overrides.clear()


# ---- comments ----
def test_member_can_comment_on_job(ctx):
    client, login, jid = ctx
    login("mem-pw")
    r = client.post(f"/api/jobs/{jid}/comments", json={"body": "推"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["body"] == "推"
    assert body["author_display_name"] == "我本人"
    assert body["author_member_id"] is not None
    assert body["author_has_photo"] is True
    assert body["can_edit"] is True


def test_viewer_cannot_comment_on_job(ctx):
    client, login, jid = ctx
    login("viewer-pw")
    assert client.post(f"/api/jobs/{jid}/comments", json={"body": "x"}).status_code == 403


def test_job_comment_edit_and_delete_flow(ctx):
    client, login, jid = ctx
    login("mem-pw")
    cid = client.post(f"/api/jobs/{jid}/comments", json={"body": "打錯"}).json()["id"]
    r = client.put(f"/api/jobs/{jid}/comments/{cid}", json={"body": "更正"})
    assert r.json()["body"] == "更正"
    assert r.json()["edited_at"] is not None
    assert (
        client.request("DELETE", f"/api/jobs/{jid}/comments/{cid}").status_code == 204
    )


def test_admin_deletes_others_job_comment_needs_password(ctx):
    client, login, jid = ctx
    login("mem-pw")
    cid = client.post(f"/api/jobs/{jid}/comments", json={"body": "hi"}).json()["id"]
    client.post("/api/auth/logout")
    login("admin-pw")
    assert (
        client.request("DELETE", f"/api/jobs/{jid}/comments/{cid}").status_code == 422
    )
    ok = client.request(
        "DELETE", f"/api/jobs/{jid}/comments/{cid}", json={"password": "admin-pw"}
    )
    assert ok.status_code == 204


# ---- likes ----
def test_job_like_then_unlike(ctx):
    client, login, jid = ctx
    login("mem-pw")
    assert client.post(f"/api/jobs/{jid}/like").json() == {
        "like_count": 1,
        "liked": True,
    }
    assert client.request("DELETE", f"/api/jobs/{jid}/like").json() == {
        "like_count": 0,
        "liked": False,
    }


def test_job_like_idempotent(ctx):
    client, login, jid = ctx
    login("mem-pw")
    client.post(f"/api/jobs/{jid}/like")
    assert client.post(f"/api/jobs/{jid}/like").json()["like_count"] == 1


def test_viewer_cannot_like_job(ctx):
    client, login, jid = ctx
    login("viewer-pw")
    assert client.post(f"/api/jobs/{jid}/like").status_code == 403


def test_job_response_carries_likes(ctx):
    client, login, jid = ctx
    login("mem-pw")
    client.post(f"/api/jobs/{jid}/like")
    mine = client.get(f"/api/jobs/{jid}").json()
    assert mine["like_count"] == 1
    assert mine["liked_by_me"] is True

    client.post("/api/auth/logout")
    login("other-pw")
    theirs = client.get(f"/api/jobs/{jid}").json()
    assert theirs["like_count"] == 1
    assert theirs["liked_by_me"] is False


def test_job_list_likers(ctx):
    client, login, jid = ctx
    login("mem-pw")
    client.post(f"/api/jobs/{jid}/like")
    likers = client.get(f"/api/jobs/{jid}/likes").json()
    assert len(likers) == 1
    assert likers[0]["display_name"] == "我本人"
    assert likers[0]["has_photo"] is True


def test_jobs_sort_by_likes(ctx):
    client, login, jid = ctx
    # A second accepted job (admin post publishes immediately) with no likes.
    login("admin-pw")
    jid2 = client.post(
        "/api/jobs",
        json={
            "job_year": 2024,
            "job_month": 7,
            "company": "Beta",
            "kind": "fulltime",
            "experience_md": "另一篇",
        },
    ).json()["id"]

    client.post("/api/auth/logout")
    login("mem-pw")
    client.post(f"/api/jobs/{jid}/like")

    ids = [j["id"] for j in client.get("/api/jobs?sort=likes&order=desc").json()["items"]]
    assert ids[0] == jid
    assert ids.index(jid) < ids.index(jid2)
