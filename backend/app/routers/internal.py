"""Compose-internal endpoints.

These routes live OUTSIDE the /api/ prefix on purpose — the frontend
nginx only forwards /api/* to the backend, so /internal/* is
unreachable from the public host. OnlyOffice (the only legitimate
caller) reaches them via the compose-internal DNS name
``backend:8000``.

We dropped an earlier in-memory token registry because OnlyOffice's
async worker queue can lag arbitrarily — by the time it actually
fetched the source, the polling loop had already given up and dropped
the token. Serving the file straight off disk by (job_id, filename)
is idempotent and survives any restart / retry timing.
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.routers.job_attachments import get_uploads_root, job_uploads_dir

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/source/{job_id}/{filename}")
def serve_source(
    job_id: int,
    filename: str,
    uploads_root: Path = Depends(get_uploads_root),
) -> FileResponse:
    # Path traversal defence: any separator or parent reference is a
    # 404. The filename was sanitised at upload time, so anything
    # weird arriving here is suspect.
    safe = Path(filename).name
    if safe != filename or safe in {"", ".", ".."}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    file_path = job_uploads_dir(uploads_root, job_id) / safe
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return FileResponse(file_path, media_type="application/octet-stream")
