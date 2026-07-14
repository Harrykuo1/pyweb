from sqlalchemy.orm import Session

from app.models import Member, User


def member_display_map(db: Session, user_ids: list[int | None]) -> dict[int, dict]:
    """Map user_id -> {name, member_id, has_photo, photo_updated_at} in one
    query. The name prefers the member's real name, then the Discord global
    name / handle, then the legacy username, so every user (including a
    profileless admin) shows a name; the member fields let the UI render their
    photo as an avatar.

    Shared by anything that shows "who did this" — comment authors, like
    actors, and (once ported) their job equivalents.
    """
    ids = [u for u in user_ids if u is not None]
    if not ids:
        return {}
    rows = (
        db.query(
            User.id,
            Member.id,
            Member.real_name,
            Member.photo_content_type,
            Member.photo_updated_at,
            User.discord_global_name,
            User.discord_username,
            User.username,
        )
        .outerjoin(Member, Member.user_id == User.id)
        .filter(User.id.in_(ids))
        .all()
    )
    out: dict[int, dict] = {}
    for (
        uid,
        mid,
        real_name,
        photo_ct,
        photo_updated,
        global_name,
        handle,
        username,
    ) in rows:
        out[uid] = {
            "name": real_name or global_name or handle or username or "未知成員",
            "member_id": mid,
            "has_photo": photo_ct is not None,
            "photo_updated_at": photo_updated,
        }
    return out
