"""Writing an UploadFile to disk without holding it in memory."""

import os
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

# 1 MiB: small enough that resident cost is noise, large enough that the
# copy stays disk-bound rather than syscall-bound.
CHUNK_BYTES = 1024 * 1024


async def stream_to_disk(
    file: UploadFile,
    target: Path,
    *,
    max_bytes: int,
    too_large_detail: str,
) -> int:
    """Copy `file` to `target` a chunk at a time; return the bytes written.

    Starlette already spools the request body to a temp file, so receiving
    the upload was never the problem — `await file.read()` is. It
    materializes the entire spool as one bytes object, which for a 240 MB
    video is 240 MB of RSS per concurrent upload, spent *before* any size
    check gets to reject it. Copying chunk by chunk keeps that flat and lets
    the cap abort partway through instead of after the fact.

    The bytes land in a sibling .part file and are moved into place only once
    the whole upload has arrived. That matters for the attachment overwrite
    path, where `target` is an existing file: streaming straight into it would
    truncate the user's current attachment the moment a replacement upload
    failed or ran over the cap. os.replace is atomic within a filesystem, and
    the .part file shares the destination directory to stay on one.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    written = 0
    try:
        with partial.open("wb") as out:
            while chunk := await file.read(CHUNK_BYTES):
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=too_large_detail,
                    )
                out.write(chunk)
        os.replace(partial, target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return written
