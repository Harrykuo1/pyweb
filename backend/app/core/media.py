"""ffmpeg-backed media conversion.

Uploads arrive in whatever the recording device produced, which is routinely
something browsers cannot display: iPhones shoot HEIC stills and HEVC video
by default, and neither plays in Chrome or Firefox. Everything user-facing is
normalized here on the way in, so nothing downstream has to care what the
camera was set to.
"""

import subprocess
from pathlib import Path

FFMPEG = "ffmpeg"

# A still image is sub-second work; anything near this is a malformed file
# that ffmpeg is chewing on, and the request is already holding a worker.
STILL_TIMEOUT_SECONDS = 30

# Content types the browser reports for HEIC/HEIF stills. The upload path
# keys off this set to decide whether a file needs converting at all.
HEIC_MIME_TYPES = frozenset({"image/heic", "image/heif"})


class MediaConversionError(Exception):
    """ffmpeg could not read or convert the file."""


def _run(args: list[str], *, timeout: int) -> None:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise MediaConversionError("ffmpeg timed out") from e
    if proc.returncode != 0:
        # stderr carries ffmpeg's reason; keep the tail, it is the useful part.
        tail = proc.stderr.decode("utf-8", "replace").strip()[-500:]
        raise MediaConversionError(tail or f"ffmpeg exited {proc.returncode}")


def heic_to_jpeg(source: Path, target: Path) -> None:
    """Decode a HEIC/HEIF still to JPEG.

    Blocking — call it off the event loop. `-q:v 2` is near the top of JPEG's
    quality scale: the point is to make the photo displayable, not to shrink
    it, so the re-encode should not be what the viewer notices.
    """
    _run(
        [
            FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            "-y",
            str(target),
        ],
        timeout=STILL_TIMEOUT_SECONDS,
    )
