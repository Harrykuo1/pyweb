from datetime import UTC, datetime

from app.core.job_serialize import job_display_name, serialize_job
from app.models import Job, JobKind, PostStatus


def _job(**kw):
    defaults = {
        "job_year": 2024,
        "job_month": 3,
        "company": "Acme",
        "category": None,
        "kind": JobKind.INTERNSHIP,
        "experience_md": "hi",
        "real_name": None,
        "timeline_md": None,
        "timeline_events": None,
        "subject_member_id": None,
        "author_user_id": None,
        "is_anonymous": False,
        "status": PostStatus.ACCEPTED,
        "review_reason": None,
    }
    defaults.update(kw)
    j = Job(**defaults)
    j.id = 1
    j.created_at = datetime.now(UTC)
    return j


def test_non_admin_sees_display_name_when_not_anonymous():
    j = _job(subject_member_id=7, is_anonymous=False)
    r = serialize_job(
        j,
        is_admin=False,
        viewer_member_id=None,
        attachment_count=0,
        subject_name="王小明",
    )
    assert r.display_name == "王小明"
    assert r.subject_member_id == 7
    assert r.author_user_id is None


def test_non_admin_anonymous_hides_all_identity():
    j = _job(
        subject_member_id=7, author_user_id=9, is_anonymous=True, review_reason="x"
    )
    r = serialize_job(
        j,
        is_admin=False,
        viewer_member_id=None,
        attachment_count=0,
        subject_name="王小明",
    )
    assert r.is_anonymous is True
    assert r.display_name is None
    assert r.subject_member_id is None
    assert r.author_user_id is None
    assert r.review_reason is None


def test_admin_sees_identity_even_when_anonymous():
    j = _job(
        subject_member_id=7,
        author_user_id=9,
        is_anonymous=True,
        review_reason="因為",
    )
    r = serialize_job(
        j, is_admin=True, viewer_member_id=None, attachment_count=0, subject_name="王小明"
    )
    assert r.display_name == "王小明"
    assert r.subject_member_id == 7
    assert r.author_user_id == 9
    assert r.review_reason == "因為"
    assert r.can_edit is True


def test_owner_sees_own_review_reason_and_can_edit():
    j = _job(
        subject_member_id=7,
        is_anonymous=True,
        status=PostStatus.REJECTED,
        review_reason="請補充",
    )
    r = serialize_job(
        j, is_admin=False, viewer_member_id=7, attachment_count=0, subject_name="我"
    )
    assert r.can_edit is True
    assert r.review_reason == "請補充"
    # Still anonymous in the public projection.
    assert r.display_name is None


def test_legacy_real_name_used_when_no_subject():
    j = _job(subject_member_id=None, real_name="舊資料", is_anonymous=False)
    r = serialize_job(
        j, is_admin=False, viewer_member_id=None, attachment_count=0, subject_name=None
    )
    assert r.display_name == "舊資料"


def test_job_display_name_hides_anonymous_from_non_admin():
    j = _job(is_anonymous=True, real_name="洩漏")
    assert job_display_name(j, is_admin=False, subject_name="洩漏") is None
    assert job_display_name(j, is_admin=True, subject_name="洩漏") == "洩漏"
