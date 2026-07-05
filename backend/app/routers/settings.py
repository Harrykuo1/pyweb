from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.runtime_config import CONFIG_BY_KEY, CONFIG_FIELDS
from app.database import get_db
from app.models import AppConfig, SiteSetting, User
from app.schemas import ConfigResponse, ConfigUpdateRequest

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


# ---------- Scalar runtime config (app_configs table) ----------


def _read_config(db: Session) -> ConfigResponse:
    rows = {r.key: r.value for r in db.query(AppConfig).all()}
    fields = []
    for field in CONFIG_FIELDS:
        raw = rows.get(field.key, field.default)
        # Fields only contain int types today; cast accordingly.
        fields.append(
            {
                "key": field.key,
                "value": int(raw),
                "type": field.type,
                "min": field.min_value,
                "max": field.max_value,
            }
        )
    return ConfigResponse.model_validate({"fields": fields})


@router.get("/config", response_model=ConfigResponse)
def get_runtime_config(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ConfigResponse:
    return _read_config(db)


@router.put("/config", response_model=ConfigResponse)
def update_runtime_config(
    payload: ConfigUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ConfigResponse:
    # Reject unknown keys outright — the table is a closed allowlist so
    # the admin UI cannot turn it into a free-form key/value store.
    unknown = set(payload.values) - set(CONFIG_BY_KEY)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown config keys: {sorted(unknown)}",
        )

    for key, value in payload.values.items():
        field = CONFIG_BY_KEY[key]
        if field.min_value is not None and value < field.min_value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{key} must be >= {field.min_value}",
            )
        if field.max_value is not None and value > field.max_value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{key} must be <= {field.max_value}",
            )

        row = db.query(AppConfig).filter_by(key=key).one_or_none()
        if row is None:
            db.add(AppConfig(key=key, value=str(value)))
        else:
            row.value = str(value)

    db.commit()
    return _read_config(db)


# ---------- Binary image assets (site_settings table) ----------


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
