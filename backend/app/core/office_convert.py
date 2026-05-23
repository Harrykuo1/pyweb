"""OnlyOffice-backed PDF conversion for Office documents.

Architecture:

  1. Upload handler writes the source under
     ``<uploads_root>/<job_id>/<filename>`` and calls ``convert_to_pdf``
     with the same coordinates.
  2. We submit an *async* conversion job to OnlyOffice. The ``url``
     field tells OnlyOffice to GET the source from
     ``/internal/source/<job_id>/<filename>`` on the compose-internal
     network — backend serves it directly off disk, no token registry.
     Async mode is the only reliable shape: sync mode races against
     OnlyOffice's internal nginx upstream timeout (60s), and earlier
     in-memory token registries kept timing out before OnlyOffice's
     worker queue drained enough to pick the job up.
  3. We poll OnlyOffice (same key, every second) until it answers with
     ``endConvert: true`` and a ``fileUrl``.
  4. We GET the resulting PDF from ``fileUrl`` and save it.

The /internal source endpoint is unauthenticated by design — backend's
port 8000 is expose-only on the compose network, so only the
onlyoffice service can reach it. Path traversal is blocked at the
endpoint with a basename check.

Any failure mode (transport error, JWT misconfig, OnlyOffice -8
unsupported-format error, missing fileUrl, ...) returns False so the
upload handler degrades to ``preview_available=False`` instead of
turning a flaky conversion into a 500.
"""
from __future__ import annotations

import secrets
import time
from pathlib import Path
from urllib.parse import quote

import httpx
import jwt as pyjwt

from app.core.config import settings

OFFICE_EXTENSIONS: frozenset[str] = frozenset(
    {".doc", ".docx", ".ppt", ".pptx"}
)

# How often we poll OnlyOffice for conversion progress.
POLL_INTERVAL_SECONDS: float = 1.0

# Per-poll HTTP timeout. OnlyOffice answers an async-mode poll in
# milliseconds when there's nothing to report, so anything more than a
# few seconds means a network or container-internal stall.
POLL_HTTP_TIMEOUT_SECONDS: float = 15.0


def is_convertible(filename: str) -> bool:
    return Path(filename).suffix.lower() in OFFICE_EXTENSIONS


def _auth_header(body: dict[str, object]) -> dict[str, str]:
    secret = settings.onlyoffice_jwt_secret
    if not secret:
        return {}
    token = pyjwt.encode(body, secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _signed_request_body(body: dict[str, object]) -> dict[str, object]:
    secret = settings.onlyoffice_jwt_secret
    if not secret:
        return body
    # OnlyOffice accepts the JWT either in the Authorization header or
    # as a `token` field in the body. We send both so the docserver's
    # configured validation mode doesn't matter.
    token = pyjwt.encode(body, secret, algorithm="HS256")
    return {**body, "token": token}


def convert_to_pdf(
    job_id: int, source: Path, source_relpath: str, output: Path
) -> bool:
    if not settings.onlyoffice_internal_url or not settings.backend_internal_url:
        return False
    if not source.exists():
        return False
    if not is_convertible(source.name):
        return False

    source_ext = source.suffix.lower().lstrip(".")
    # Unique key per conversion call so OnlyOffice doesn't dedupe with
    # a stale failed attempt that's still in its internal cache.
    key = secrets.token_urlsafe(16)
    deadline = time.monotonic() + settings.onlyoffice_convert_timeout_seconds

    # Preserve "/" so multi-segment relpaths (folder uploads) reach
    # the internal source endpoint as one path; everything else gets
    # percent-encoded.
    source_url = (
        f"{settings.backend_internal_url}"
        f"/internal/source/{job_id}/{quote(source_relpath, safe='/')}"
    )

    with httpx.Client(timeout=POLL_HTTP_TIMEOUT_SECONDS) as client:
        convert_url = f"{settings.onlyoffice_internal_url}/ConvertService.ashx"

        while True:
            if time.monotonic() > deadline:
                return False

            body: dict[str, object] = {
                "key": key,
                "url": source_url,
                "filetype": source_ext,
                "outputtype": "pdf",
                "async": True,
            }
            signed = _signed_request_body(body)
            headers = {
                "Content-Type": "application/json",
                # OnlyOffice's ConvertService.ashx defaults to XML;
                # Accept flips it to JSON so resp.json() doesn't die.
                "Accept": "application/json",
                **_auth_header(body),
            }

            try:
                resp = client.post(convert_url, json=signed, headers=headers)
            except httpx.HTTPError:
                return False
            if resp.status_code != 200:
                return False
            try:
                data = resp.json()
            except ValueError:
                return False
            if not isinstance(data, dict):
                return False
            if "error" in data:
                return False

            if data.get("endConvert"):
                file_url = data.get("fileUrl")
                if not isinstance(file_url, str) or not file_url:
                    return False
                try:
                    pdf_resp = client.get(file_url)
                except httpx.HTTPError:
                    return False
                if pdf_resp.status_code != 200:
                    return False
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(pdf_resp.content)
                return True

            time.sleep(POLL_INTERVAL_SECONDS)
