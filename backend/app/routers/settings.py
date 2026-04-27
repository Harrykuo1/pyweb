from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.database import get_db
from app.models import SiteSetting, User

router = APIRouter(prefix="/api/settings", tags=["settings"])


# Keys live in this allowlist so the table cannot be turned into an
# arbitrary key/value dump from the admin UI.
ALLOWED_KEYS = {"login_logo"}

# login_logo is rendered before the user authenticates, so its GET must be
# anonymous. Other future keys can opt in by adding them here.
PUBLIC_GET_KEYS = {"login_logo"}

IMAGE_MAX_BYTES = 2 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}


def _check_key(key: str) -> None:
    if key not in ALLOWED_KEYS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown setting key '{key}'",
        )


@router.get("/{key}/image")
def get_setting_image(
    key: str,
    db: Session = Depends(get_db),
) -> Response:
    _check_key(key)
    if key not in PUBLIC_GET_KEYS:
        # For now every allowed key is public; this guard keeps the door
        # closed if a future key is added without an explicit opt-in.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    setting = db.query(SiteSetting).filter_by(key=key).one_or_none()
    if setting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not set")

    return Response(
        content=setting.value,
        media_type=setting.content_type,
        headers={
            # Tag with mtime so the frontend can bust caches by query string.
            "ETag": f'"{setting.updated_at.isoformat()}"',
            "Cache-Control": "public, max-age=60",
        },
    )


@router.post("/{key}/image")
async def upload_setting_image(
    key: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    _check_key(key)

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Image must be one of: {sorted(ALLOWED_IMAGE_TYPES)}",
        )

    data = await file.read()
    if len(data) > IMAGE_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Image must be at most {IMAGE_MAX_BYTES} bytes",
        )

    setting = db.query(SiteSetting).filter_by(key=key).one_or_none()
    if setting is None:
        setting = SiteSetting(key=key, value=data, content_type=file.content_type)
        db.add(setting)
    else:
        setting.value = data
        setting.content_type = file.content_type

    db.commit()
    db.refresh(setting)
    return {
        "key": setting.key,
        "content_type": setting.content_type,
        "size": len(setting.value),
        "updated_at": setting.updated_at.isoformat(),
    }


@router.delete("/{key}/image", status_code=status.HTTP_204_NO_CONTENT)
def delete_setting_image(
    key: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    _check_key(key)

    setting = db.query(SiteSetting).filter_by(key=key).one_or_none()
    if setting is not None:
        db.delete(setting)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
