from datetime import UTC, datetime, timedelta

from app.core.discord_oauth import DiscordIdentity
from app.core.discord_register import invite_is_valid, register_via_invite
from app.models import RegistrationInvite, User, UserRole


def _invite(**kw):
    now = datetime.now(UTC)
    defaults = {"token": "t", "created_at": now, "expires_at": now + timedelta(hours=1)}
    defaults.update(kw)
    return RegistrationInvite(**defaults)


def test_invite_valid_when_fresh_and_unused():
    now = datetime.now(UTC)
    assert invite_is_valid(_invite(), now) is True


def test_invite_invalid_when_none():
    assert invite_is_valid(None, datetime.now(UTC)) is False


def test_invite_invalid_when_used():
    now = datetime.now(UTC)
    assert invite_is_valid(_invite(used_at=now), now) is False


def test_invite_invalid_when_expired():
    now = datetime.now(UTC)
    expired = _invite(expires_at=now - timedelta(minutes=1))
    assert invite_is_valid(expired, now) is False


def test_invite_valid_handles_naive_expires_at():
    # SQLite can hand back a tz-naive datetime; validity must not blow up.
    now = datetime.now(UTC)
    naive = _invite(expires_at=(now + timedelta(hours=1)).replace(tzinfo=None))
    assert invite_is_valid(naive, now) is True


def _seed_invite(db):
    now = datetime.now(UTC)
    inv = RegistrationInvite(
        token="valid", created_at=now, expires_at=now + timedelta(hours=1)
    )
    db.add(inv)
    db.commit()
    return inv


def test_register_creates_member_account_and_consumes_invite(db_session):
    _seed_invite(db_session)
    ident = DiscordIdentity(id="NEW", username="newbie", global_name="Newbie")

    user, err = register_via_invite(db_session, ident, "valid")

    assert err is None
    assert user is not None
    assert user.role is UserRole.MEMBER
    assert user.discord_id == "NEW"
    assert user.discord_username == "newbie"
    invite = db_session.query(RegistrationInvite).filter_by(token="valid").one()
    assert invite.used_at is not None
    assert invite.used_by_user_id == user.id


def test_consume_invite_is_a_guarded_compare_and_set(db_session):
    # The single-use guarantee is a DB-level compare-and-set, not just the
    # earlier read-check, so two callers racing the same token can't both
    # consume it. Once one claims used_at, a second claim matches 0 rows.
    from app.core.discord_register import _consume_invite

    _seed_invite(db_session)
    u1 = User(role=UserRole.MEMBER, discord_id="A", discord_username="a")
    u2 = User(role=UserRole.MEMBER, discord_id="B", discord_username="b")
    db_session.add_all([u1, u2])
    db_session.commit()
    now = datetime.now(UTC)

    assert _consume_invite(db_session, "valid", now, u1.id) is True
    db_session.commit()
    assert _consume_invite(db_session, "valid", now, u2.id) is False

    invite = db_session.query(RegistrationInvite).filter_by(token="valid").one()
    assert invite.used_by_user_id == u1.id


def test_register_rejects_invalid_token(db_session):
    ident = DiscordIdentity(id="NEW", username="x", global_name=None)
    user, err = register_via_invite(db_session, ident, "nope")
    assert user is None
    assert err == "invalid_invite"


def test_register_rejects_already_registered_identity(db_session):
    _seed_invite(db_session)
    db_session.add(User(role=UserRole.MEMBER, discord_id="DUP"))
    db_session.commit()
    ident = DiscordIdentity(id="DUP", username="x", global_name=None)

    user, err = register_via_invite(db_session, ident, "valid")
    assert user is None
    assert err == "already_registered"


def test_register_claims_matching_pre_provisioned_account(db_session):
    """Invite + a pre-created account for the same handle -> claim it,
    don't mint a duplicate."""
    _seed_invite(db_session)
    pre = User(role=UserRole.MEMBER, pending_discord_username="alice")
    db_session.add(pre)
    db_session.commit()
    pre_id = pre.id
    ident = DiscordIdentity(id="NEW", username="Alice", global_name="Alice")

    user, err = register_via_invite(db_session, ident, "valid")

    assert err is None
    assert user is not None
    assert user.id == pre_id  # same account, no duplicate minted
    assert user.discord_id == "NEW"
    assert user.pending_discord_username is None
    assert db_session.query(User).count() == 1
    invite = db_session.query(RegistrationInvite).filter_by(token="valid").one()
    assert invite.used_at is not None
    assert invite.used_by_user_id == pre_id


def test_register_does_not_claim_or_burn_for_suspended_pending_match(db_session):
    # A suspended pre-created account must not be claimed and the single-use
    # invite must not be consumed: reject without mutating anything.
    _seed_invite(db_session)
    pre = User(role=UserRole.MEMBER, pending_discord_username="alice", is_active=False)
    db_session.add(pre)
    db_session.commit()

    ident = DiscordIdentity(id="NEW", username="Alice", global_name="Alice")
    user, err = register_via_invite(db_session, ident, "valid")

    assert user is None
    assert err == "account_suspended"
    db_session.refresh(pre)
    assert pre.discord_id is None
    assert pre.pending_discord_username == "alice"
    invite = db_session.query(RegistrationInvite).filter_by(token="valid").one()
    assert invite.used_at is None


def test_register_via_invite_queues_on_ambiguous_handle(db_session):
    from app.models import PendingDiscordLink

    _seed_invite(db_session)
    db_session.add_all(
        [
            User(role=UserRole.MEMBER, pending_discord_username="alice"),
            User(role=UserRole.MEMBER, pending_discord_username="alice"),
        ]
    )
    db_session.commit()
    before = db_session.query(User).count()
    ident = DiscordIdentity(id="NEW", username="alice", global_name=None)

    user, err = register_via_invite(db_session, ident, "valid")

    assert user is None
    assert err == "link_ambiguous"
    assert db_session.query(User).count() == before  # NO new account minted
    assert db_session.query(PendingDiscordLink).filter_by(discord_id="NEW").count() == 1
    # invite NOT consumed on ambiguous
    invite = db_session.query(RegistrationInvite).filter_by(token="valid").one()
    assert invite.used_at is None
