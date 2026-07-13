"""Role-aware serialization for job posts (spec §8).

The single choke point that decides, per requester, whether each identity
field on a job is returned truthfully or nulled out. Anonymous posts leak
nothing to non-admins: display_name, subject_member_id, author_user_id and
review_reason all come back null so there is no hook to reverse-lookup the
author. Admins always get the full identity (they review and post on behalf
of members); the post's owner sees their own review_reason.

`job_display_name` is factored out so other job-returning surfaces (e.g. the
home timeline feed) reuse the exact same anonymity rule. Pure functions: the
caller resolves subject_name (batched for lists) and passes it in, so these
stay unit-testable without a DB.
"""

from __future__ import annotations

from app.models import Job
from app.schemas import JobResponse


def job_display_name(
    job: Job, *, is_admin: bool, subject_name: str | None
) -> str | None:
    """Public-safe name for a job's subject: the subject member's real name
    (falling back to the legacy real_name string), or None when the post is
    anonymous to this viewer."""
    if is_admin or not job.is_anonymous:
        return subject_name or job.real_name
    return None


def serialize_job(
    job: Job,
    *,
    is_admin: bool,
    viewer_member_id: int | None,
    attachment_count: int,
    subject_name: str | None,
    like_count: int = 0,
    liked_by_me: bool = False,
) -> JobResponse:
    is_owner = (
        viewer_member_id is not None
        and job.subject_member_id is not None
        and job.subject_member_id == viewer_member_id
    )
    can_see_identity = is_admin or not job.is_anonymous
    return JobResponse(
        id=job.id,
        job_year=job.job_year,
        job_month=job.job_month,
        company=job.company,
        category=job.category,
        kind=job.kind.value,
        experience_md=job.experience_md,
        timeline_md=job.timeline_md,
        timeline_events=job.timeline_events,
        created_at=job.created_at,
        attachment_count=attachment_count,
        display_name=job_display_name(
            job, is_admin=is_admin, subject_name=subject_name
        ),
        is_anonymous=job.is_anonymous,
        status=job.status.value,
        subject_member_id=job.subject_member_id if can_see_identity else None,
        author_user_id=job.author_user_id if is_admin else None,
        review_reason=job.review_reason if (is_admin or is_owner) else None,
        can_edit=is_admin or is_owner,
        like_count=like_count,
        liked_by_me=liked_by_me,
    )
