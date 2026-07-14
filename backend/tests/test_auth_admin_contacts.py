import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Member, User, UserRole


@pytest.fixture
def ctx(db_session):
    # The break-glass password admin: no Discord handle, so unreachable.
    seeded_admin = User(
        username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN
    )
    # A real, contactable admin.
    dc_admin = User(
        role=UserRole.ADMIN,
        discord_id="D1",
        discord_username="as6325400",
        discord_global_name="Harry",
    )
    # An admin who never set a Discord display name — handle only.
    handle_only_admin = User(
        role=UserRole.ADMIN,
        discord_id="D2",
        discord_username="handleonly",
        discord_global_name=None,
    )
    # Suspended admin — must not be listed.
    suspended_admin = User(
        role=UserRole.ADMIN,
        discord_id="D3",
        discord_username="gone",
        discord_global_name="Gone",
        is_active=False,
    )
    # A plain member — must not be listed.
    member_user = User(
        role=UserRole.MEMBER,
        discord_id="D4",
        discord_username="justamember",
        discord_global_name="Member",
    )
    db_session.add_all(
        [seeded_admin, dc_admin, handle_only_admin, suspended_admin, member_user]
    )
    db_session.flush()
    # Give the contactable admin a member profile, so we can prove the
    # endpoint never leaks a real name.
    db_session.add(
        Member(
            graduation_year=2024,
            real_name="王子銜",
            institution="X",
            user_id=dc_admin.id,
        )
    )
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_admin_contacts_is_public(ctx):
    # The login page is pre-auth, so this must work with no session.
    assert ctx.get("/api/auth/admin-contacts").status_code == 200


def test_lists_only_reachable_active_admins(ctx):
    handles = [
        c["discord_username"] for c in ctx.get("/api/auth/admin-contacts").json()
    ]
    # Contactable admins only: the seeded password admin (no handle), the
    # suspended admin, and the plain member are all excluded.
    assert handles == ["as6325400", "handleonly"]


def test_returns_discord_display_name_and_handle(ctx):
    contacts = ctx.get("/api/auth/admin-contacts").json()
    assert contacts[0] == {"display_name": "Harry", "discord_username": "as6325400"}
    # No global name set → null, so the UI falls back to the bare handle.
    assert contacts[1] == {"display_name": None, "discord_username": "handleonly"}


def test_never_leaks_a_real_name(ctx):
    body = ctx.get("/api/auth/admin-contacts").text
    # This endpoint is public — a member's real name must never appear.
    assert "王子銜" not in body
