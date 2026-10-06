import hashlib
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActivityIngestToken

bearer = HTTPBearer(auto_error=False, scheme_name="ActivityBotToken")


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    return "pyweb_activity_" + secrets.token_urlsafe(32)


def require_activity_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> ActivityIngestToken:
    token = None
    if credentials is not None and len(credentials.credentials) <= 256:
        token = (
            db.query(ActivityIngestToken)
            .filter_by(
                token_hash=token_digest(credentials.credentials), revoked_at=None
            )
            .one_or_none()
        )
    if token is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or revoked activity token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token
