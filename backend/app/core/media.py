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


# Transcoding is roughly half to one times the clip's own length on CPU, so a
# long upload legitimately runs for minutes. This bound only exists to stop a
# pathological file from occupying a worker thread forever.
VIDEO_TIMEOUT_SECONDS = 30 * 60

# "1080p" here means the SHORT edge, not the height: capping height alone
# would leave a 1080x1920 phone clip untouched while squashing a 2160x3840
# one to 607x1080. Limiting the short edge treats both orientations the same.
MAX_SHORT_EDGE = 1080

_SCALE_FILTER = (
    f"scale='if(gt(iw,ih),-2,min({MAX_SHORT_EDGE},iw))'"
    f":'if(gt(iw,ih),min({MAX_SHORT_EDGE},ih),-2)'"
)


def probe_duration_seconds(source: Path) -> int:
    """Length in whole seconds, or 0 if the container does not report one."""
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(source),
            ],
            capture_output=True,
            timeout=STILL_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise MediaConversionError("ffprobe timed out") from e
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace").strip()[-500:]
        raise MediaConversionError(tail or "ffprobe could not read the file")
    try:
        return int(float(proc.stdout.decode().strip()))
    except ValueError:
        return 0


def transcode_video(source: Path, target: Path) -> None:
    """Normalize an uploaded video to H.264/AAC MP4, capped at 1080p.

    Blocking — call it off the event loop. Phones default to HEVC, which
    Chrome and Firefox will not play, so this is what makes an upload
    watchable at all rather than an optimization.

    +faststart moves the moov atom to the front of the file. Without it a
    browser has to fetch the whole video before it can start playing, which
    for a 100 MB clip reads as the player being broken.
    """
    _run(
        [
            FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
            "-vf",
            _SCALE_FILTER,
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            "-y",
            str(target),
        ],
        timeout=VIDEO_TIMEOUT_SECONDS,
    )


def extract_poster(source: Path, target: Path, *, at_second: int) -> None:
    """Pull a still for the media grid to show.

    Seeks in rather than taking frame zero, which on a phone clip is often
    the black frame while the sensor settles.
    """
    _run(
        [
            FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(at_second),
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            "-vf",
            _SCALE_FILTER,
            "-y",
            str(target),
        ],
        timeout=STILL_TIMEOUT_SECONDS,
    )
