from app.backfill_accounts import backfill_member_accounts
from app.models import Member, User, UserRole


def _add_member(db, name, resume):
    m = Member(graduation_year=2024, real_name=name, institution="X", resume_md=resume)
    db.add(m)
    db.flush()
    return m


def test_backfill_creates_and_links_accounts(db_session):
    m1 = _add_member(db_session, "郭禮德", "略歷\n- Discord: `harrykuo1`\n其他")
    m2 = _add_member(db_session, "劉政勳", "- Discord: `dayeh_no1`")
    db_session.commit()

    created = backfill_member_accounts(db_session.connection())
    db_session.expire_all()

    assert created == 2
    u1 = db_session.query(User).filter_by(pending_discord_username="harrykuo1").one()
    assert u1.role is UserRole.MEMBER
    assert u1.discord_id is None
    assert u1.username is None
    assert u1.password_hash is None
    assert db_session.get(Member, m1.id).user_id == u1.id
    assert db_session.get(Member, m2.id).user_id is not None


def test_backfill_handles_missing_handle_and_is_idempotent(db_session):
    m = _add_member(db_session, "無 Discord", "純文字履歷，沒有 handle")
    db_session.commit()

    created = backfill_member_accounts(db_session.connection())
    db_session.expire_all()

    # Account is still created (so the member can be linked later); the
    # pending handle is just null.
    assert created == 1
    linked_user_id = db_session.get(Member, m.id).user_id
    assert linked_user_id is not None
    assert db_session.get(User, linked_user_id).pending_discord_username is None

    # Idempotent: members already linked are skipped.
    again = backfill_member_accounts(db_session.connection())
    assert again == 0
