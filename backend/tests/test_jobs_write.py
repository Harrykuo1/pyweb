import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Member, User, UserRole


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
    np = User(username="np", password_hash=hash_password("np-pw"), role=UserRole.MEMBER)
    otheru = User(
        username="otheru", password_hash=hash_password("other-pw"), role=UserRole.MEMBER
    )
    db_session.add_all([admin, viewer, mem, np, otheru])
    db_session.flush()
    mem_member = Member(
        graduation_year=2024, real_name="我本人", institution="X", user_id=mem.id
    )
    other = Member(
        graduation_year=2024, real_name="別人", institution="Y", user_id=otheru.id
    )
    db_session.add_all([mem_member, other])
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)

    def login(pw):
        assert client.post("/api/auth/login", json={"password": pw}).status_code == 200

    try:
        yield client, login, {"mem_member": mem_member.id, "other": other.id}
    finally:
        client.close()
        app.dependency_overrides.clear()


_BASE = {"job_year": 2025, "job_month": 6, "company": "Acme", "kind": "internship"}


def _payload(**kw):
    p = {**_BASE, "experience_md": "hi"}
    p.update(kw)
    return p


# ---------- create: admin ----------


def test_admin_create_with_subject_is_accepted(ctx, db_session):
    client, login, ids = ctx
    login("admin-pw")
    r = client.post(
        "/api/jobs", json=_payload(subject_member_id=ids["other"], is_anonymous=False)
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "accepted"
    assert body["display_name"] == "別人"
    assert body["subject_member_id"] == ids["other"]


def test_admin_create_with_real_name_fallback(ctx):
    client, login, _ = ctx
    login("admin-pw")
    r = client.post("/api/jobs", json=_payload(real_name="Carol"))
    assert r.status_code == 201
    assert r.json()["display_name"] == "Carol"
    assert r.json()["status"] == "accepted"


def test_admin_create_with_unknown_subject_404(ctx):
    client, login, _ = ctx
    login("admin-pw")
    r = client.post("/api/jobs", json=_payload(subject_member_id=99999))
    assert r.status_code == 404


def test_create_rejects_oversized_experience_md(ctx):
    # Free-text markdown is length-bounded so one authenticated write can't
    # stuff the ~256 MB body limit into a text column.
    from app.schemas.job import MARKDOWN_MAX_LENGTH

    client, login, _ = ctx
    login("admin-pw")
    over = client.post(
        "/api/jobs", json=_payload(experience_md="x" * (MARKDOWN_MAX_LENGTH + 1))
    )
    assert over.status_code == 422, over.text
    at_limit = client.post(
        "/api/jobs", json=_payload(experience_md="x" * MARKDOWN_MAX_LENGTH)
    )
    assert at_limit.status_code == 201, at_limit.text


# ---------- create: member ----------


def test_member_create_is_pending_and_subject_is_self(ctx, db_session):
    client, login, ids = ctx
    login("mem-pw")
    # Even if a member tries to attribute the post to someone else, it's
    # forced back to themselves.
    r = client.post(
        "/api/jobs", json=_payload(subject_member_id=ids["other"], real_name="冒充")
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["subject_member_id"] == ids["mem_member"]
    assert body["display_name"] == "我本人"  # owner sees their own name
    assert body["can_edit"] is True


def test_member_create_anonymous(ctx):
    client, login, _ = ctx
    login("mem-pw")
    r = client.post("/api/jobs", json=_payload(is_anonymous=True))
    assert r.status_code == 201
    assert r.json()["is_anonymous"] is True


def test_member_without_profile_cannot_create(ctx):
    client, login, _ = ctx
    login("np-pw")
    r = client.post("/api/jobs", json=_payload())
    assert r.status_code == 403


def test_viewer_cannot_create(ctx):
    client, login, _ = ctx
    login("viewer-pw")
    r = client.post("/api/jobs", json=_payload())
    assert r.status_code == 403


# ---------- update: ownership + resubmit ----------


def _member_creates(client, login, **kw):
    login("mem-pw")
    r = client.post("/api/jobs", json=_payload(**kw))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_owner_can_update_own_post(ctx):
    client, login, _ = ctx
    jid = _member_creates(client, login)
    r = client.put(f"/api/jobs/{jid}", json={"company": "Updated"})
    assert r.status_code == 200
    assert r.json()["company"] == "Updated"


def test_non_owner_member_cannot_update(ctx):
    client, login, _ = ctx
    jid = _member_creates(client, login)  # owned by mem
    client.post("/api/auth/logout")
    login("other-pw")  # a different member
    r = client.put(f"/api/jobs/{jid}", json={"company": "Hijack"})
    assert r.status_code == 403


def test_admin_can_update_any_post(ctx):
    client, login, _ = ctx
    jid = _member_creates(client, login)
    client.post("/api/auth/logout")
    login("admin-pw")
    r = client.put(f"/api/jobs/{jid}", json={"company": "AdminEdit"})
    assert r.status_code == 200
    assert r.json()["company"] == "AdminEdit"


def test_member_editing_rejected_post_resubmits_to_pending(ctx, db_session):
    from app.models import Job, PostStatus

    client, login, _ = ctx
    jid = _member_creates(client, login)
    # Admin rejects it out of band.
    db_session.query(Job).filter_by(id=jid).update({"status": PostStatus.REJECTED})
    db_session.commit()

    r = client.put(f"/api/jobs/{jid}", json={"experience_md": "revised"})
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


def test_resubmit_clears_stale_review_state(ctx, db_session):
    from app.models import Job, PostStatus

    client, login, _ = ctx
    jid = _member_creates(client, login)
    db_session.query(Job).filter_by(id=jid).update(
        {
            "status": PostStatus.REJECTED,
            "review_reason": "缺少細節",
            "reviewed_at": None,
        }
    )
    db_session.commit()

    r = client.put(f"/api/jobs/{jid}", json={"experience_md": "revised"})
    assert r.json()["status"] == "pending"
    db_session.expire_all()
    row = db_session.query(Job).filter_by(id=jid).first()
    # The stale rejection reason must not ride along on the re-queued post.
    assert row.review_reason is None


def test_member_editing_accepted_post_returns_to_pending(ctx, db_session):
    from app.models import Job, PostStatus

    client, login, _ = ctx
    jid = _member_creates(client, login)
    # Admin approved it; the member then edits the (public) post.
    db_session.query(Job).filter_by(id=jid).update({"status": PostStatus.ACCEPTED})
    db_session.commit()

    r = client.put(f"/api/jobs/{jid}", json={"experience_md": "sneaky edit"})
    assert r.status_code == 200
    # Editing public content re-enters the review queue; it must not stay live.
    assert r.json()["status"] == "pending"


def test_admin_editing_accepted_post_stays_accepted(ctx, db_session):
    from app.models import Job, PostStatus

    client, login, _ = ctx
    jid = _member_creates(client, login)
    db_session.query(Job).filter_by(id=jid).update({"status": PostStatus.ACCEPTED})
    db_session.commit()
    client.post("/api/auth/logout")
    login("admin-pw")

    r = client.put(f"/api/jobs/{jid}", json={"experience_md": "admin edit"})
    assert r.status_code == 200
    # Admin edits are trusted and do not bounce the post back to review.
    assert r.json()["status"] == "accepted"


def test_member_cannot_reassign_subject(ctx):
    client, login, ids = ctx
    jid = _member_creates(client, login)
    r = client.put(f"/api/jobs/{jid}", json={"subject_member_id": ids["other"]})
    assert r.status_code == 200
    # Subject stays the member themselves.
    assert r.json()["subject_member_id"] == ids["mem_member"]


# ---------- delete: ownership ----------


def test_member_owner_can_delete_without_password(ctx):
    client, login, _ = ctx
    jid = _member_creates(client, login)
    r = client.request("DELETE", f"/api/jobs/{jid}")
    assert r.status_code == 204


def test_non_owner_member_cannot_delete(ctx):
    client, login, _ = ctx
    jid = _member_creates(client, login)
    client.post("/api/auth/logout")
    login("other-pw")
    r = client.request("DELETE", f"/api/jobs/{jid}")
    assert r.status_code == 403


# ---------- approval: accept / reject ----------


def test_admin_accept_publishes_pending_post(ctx):
    client, login, _ = ctx
    jid = _member_creates(client, login)  # pending
    client.post("/api/auth/logout")
    login("admin-pw")
    r = client.post(f"/api/jobs/{jid}/accept")
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"


def test_admin_reject_sets_reason(ctx):
    client, login, _ = ctx
    jid = _member_creates(client, login)
    client.post("/api/auth/logout")
    login("admin-pw")
    r = client.post(f"/api/jobs/{jid}/reject", json={"reason": "請補充公司名"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "rejected"
    assert body["review_reason"] == "請補充公司名"


def test_reject_requires_reason(ctx):
    client, login, _ = ctx
    jid = _member_creates(client, login)
    client.post("/api/auth/logout")
    login("admin-pw")
    r = client.post(f"/api/jobs/{jid}/reject", json={})
    assert r.status_code == 422


def test_member_cannot_accept(ctx):
    client, login, _ = ctx
    jid = _member_creates(client, login)
    r = client.post(f"/api/jobs/{jid}/accept")
    assert r.status_code == 403
