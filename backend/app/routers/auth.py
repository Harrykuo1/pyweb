from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import verify_password
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    # bcrypt hashes are salted, so we cannot index by them. Two seeded
    # accounts means the linear scan is fine; revisit if the user count grows.
    for user in db.query(User).all():
        if verify_password(payload.password, user.password_hash):
            request.session["user_id"] = user.id
            request.session["role"] = user.role.value
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid password",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
