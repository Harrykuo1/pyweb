from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str | None) -> bool:
    # Login scans every user and calls this against each stored hash, so one
    # NULL (Discord-only accounts) or malformed/non-bcrypt hash must not raise
    # — otherwise a single bad row 500s the whole login endpoint for everyone.
    if not hashed:
        return False
    try:
        return _pwd_context.verify(plain, hashed)
    except (ValueError, TypeError):
        return False
