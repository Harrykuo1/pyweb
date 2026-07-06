from app.core.discord_link import link_or_queue, normalize_discord_handle
from app.core.discord_oauth import DiscordIdentity
from app.models import Member, PendingDiscordLink, User, UserRole


def _pre_created(db, handle):
    """Mimic a Phase-1 backfilled account: member + linked user with a
    pending handle and no discord_id yet."""
    u = User(role=UserRole.MEMBER, pending_discord_username=handle)
    db.add(u)
    db.flush()
    m = Member(graduation_year=2024, real_name="X", institution="Y", user_id=u.id)
    db.add(m)
    db.commit()
    return u


def test_links_matching_account_and_backfills_discord_id(db_session):
    u = _pre_created(db_session, "harrykuo1")

    result = link_or_queue(
        db_session,
        DiscordIdentity(id="D1", username="harrykuo1", global_name="Harry"),
    )

    assert result is not None
    assert result.id == u.id
    assert result.discord_id == "D1"
    assert result.discord_username == "harrykuo1"
    assert result.discord_global_name == "Harry"
    assert result.pending_discord_username is None
    assert db_session.query(PendingDiscordLink).count() == 0


def test_match_is_case_insensitive(db_session):
    _pre_created(db_session, "MixedCase")
    result = link_or_queue(
        db_session, DiscordIdentity(id="D2", username="mixedcase", global_name=None)
    )
    assert result is not None
    assert result.discord_id == "D2"


def test_no_match_queues_pending_link(db_session):
    _pre_created(db_session, "someone_else")

    result = link_or_queue(
        db_session, DiscordIdentity(id="D3", username="ghost", global_name="Ghost")
    )

    assert result is None
    pending = db_session.query(PendingDiscordLink).one()
    assert pending.discord_id == "D3"
    assert pending.discord_username == "ghost"


def test_queue_is_idempotent_on_repeat(db_session):
    ident = DiscordIdentity(id="D4", username="ghost", global_name="Ghost")
    assert link_or_queue(db_session, ident) is None
    assert link_or_queue(db_session, ident) is None
    assert db_session.query(PendingDiscordLink).filter_by(discord_id="D4").count() == 1


def test_ambiguous_multiple_candidates_queues_instead_of_guessing(db_session):
    # Two unlinked accounts claiming the same handle (should not happen with
    # unique handles, but never auto-link the wrong person).
    _pre_created(db_session, "dup")
    _pre_created(db_session, "dup")

    result = link_or_queue(
        db_session, DiscordIdentity(id="D5", username="dup", global_name=None)
    )
    assert result is None
    assert db_session.query(PendingDiscordLink).filter_by(discord_id="D5").count() == 1


def test_normalize_strips_whitespace_and_at():
    assert normalize_discord_handle("  @Cool.Name  ") == "Cool.Name"


def test_normalize_plain_handle_unchanged():
    assert normalize_discord_handle("somehandle") == "somehandle"


def test_normalize_empty_becomes_none():
    assert normalize_discord_handle("") is None
    assert normalize_discord_handle("   ") is None
    assert normalize_discord_handle("@") is None
    assert normalize_discord_handle(None) is None
