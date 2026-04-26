import pytest
from pydantic import ValidationError

from app.models import User, UserRole
from app.schemas import LoginRequest, UserResponse


def test_login_request_accepts_valid_payload():
    req = LoginRequest(username="alice", password="hunter2")
    assert req.username == "alice"
    assert req.password == "hunter2"


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "", "password": "x"},
        {"username": "alice", "password": ""},
        {"username": "alice"},
        {"password": "x"},
    ],
)
def test_login_request_rejects_invalid_payload(payload):
    with pytest.raises(ValidationError):
        LoginRequest(**payload)


def test_user_response_from_orm_object():
    u = User(id=42, username="admin", password_hash="hash", role=UserRole.ADMIN)
    resp = UserResponse.model_validate(u)
    assert resp.id == 42
    assert resp.username == "admin"
    assert resp.role is UserRole.ADMIN


def test_user_response_excludes_password_hash():
    u = User(id=1, username="x", password_hash="secret-hash", role=UserRole.VIEWER)
    dumped = UserResponse.model_validate(u).model_dump()
    assert "password_hash" not in dumped
    assert dumped == {"id": 1, "username": "x", "role": UserRole.VIEWER}
