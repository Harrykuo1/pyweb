import pytest
from pydantic import ValidationError

from app.models import User, UserRole
from app.schemas import (
    LoginRequest,
    UpdatePasswordRequest,
    UpdateUsernameRequest,
    UserResponse,
)


def test_login_request_accepts_password_only():
    req = LoginRequest(password="hunter2")
    assert req.password == "hunter2"


def test_login_request_rejects_empty_password():
    with pytest.raises(ValidationError):
        LoginRequest(password="")


def test_login_request_rejects_missing_password():
    with pytest.raises(ValidationError):
        LoginRequest()


def test_login_request_ignores_unrelated_fields():
    # Extra fields are silently dropped by Pydantic v2 default config; this
    # documents the contract so a future stricter config flips the test.
    req = LoginRequest(password="ok", username="ignored")
    assert req.password == "ok"
    assert not hasattr(req, "username")


def test_user_response_from_orm_object():
    # A transient (un-flushed) ORM object leaves server_default columns as
    # None, so set is_active explicitly; queried users always carry a real bool.
    u = User(
        id=42,
        username="admin",
        password_hash="hash",
        role=UserRole.ADMIN,
        is_active=True,
    )
    resp = UserResponse.model_validate(u)
    assert resp.id == 42
    assert resp.username == "admin"
    assert resp.role is UserRole.ADMIN


def test_user_response_excludes_password_hash():
    u = User(
        id=1,
        username="x",
        password_hash="secret-hash",
        role=UserRole.VIEWER,
        is_active=True,
    )
    dumped = UserResponse.model_validate(u).model_dump()
    assert "password_hash" not in dumped
    assert dumped == {
        "id": 1,
        "username": "x",
        "role": UserRole.VIEWER,
        "discord_username": None,
        "discord_global_name": None,
        "has_profile": False,
        "member_id": None,
        "member_name": None,
        "is_active": True,
    }


def test_update_username_request_accepts_valid_name():
    req = UpdateUsernameRequest(username="alice")
    assert req.username == "alice"


def test_update_username_request_rejects_empty_name():
    with pytest.raises(ValidationError):
        UpdateUsernameRequest(username="")


def test_update_username_request_rejects_too_long_name():
    with pytest.raises(ValidationError):
        UpdateUsernameRequest(username="x" * 65)


def test_update_password_request_accepts_both_fields():
    req = UpdatePasswordRequest(current_password="old", new_password="new")
    assert req.current_password == "old"
    assert req.new_password == "new"


def test_update_password_request_rejects_empty_current_password():
    with pytest.raises(ValidationError):
        UpdatePasswordRequest(current_password="", new_password="new")


def test_update_password_request_rejects_empty_new_password():
    with pytest.raises(ValidationError):
        UpdatePasswordRequest(current_password="old", new_password="")


def test_update_password_request_rejects_missing_fields():
    with pytest.raises(ValidationError):
        UpdatePasswordRequest(new_password="new")
    with pytest.raises(ValidationError):
        UpdatePasswordRequest(current_password="old")
