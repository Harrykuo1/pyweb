"""Exercises app.core.media against the real ffmpeg binary.

The router tests stub the converter out so they run anywhere; these are the
ones that would notice if the shipped ffmpeg stopped handling HEIC. ffmpeg
lives in the backend image, not necessarily on a developer's host, so they
skip rather than fail when it is absent.
"""

import shutil
import subprocess

import pytest

from app.core.media import MediaConversionError, heic_to_jpeg

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg is not installed on this host (it ships in the backend image)",
)

# JPEG start-of-image marker.
JPEG_SOI = b"\xff\xd8\xff"


@pytest.fixture
def heic_file(tmp_path):
    """A real HEIC still: HEVC frame in an ISOBMFF container, same shape as
    what a phone produces."""
    path = tmp_path / "sample.heic"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:duration=1:rate=1",
            "-frames:v",
            "1",
            "-c:v",
            "libx265",
            "-tag:v",
            "hvc1",
            "-f",
            "mp4",
            "-y",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def test_heic_to_jpeg_produces_a_real_jpeg(heic_file, tmp_path):
    out = tmp_path / "out.jpg"
    heic_to_jpeg(heic_file, out)

    assert out.exists()
    assert out.read_bytes()[:3] == JPEG_SOI


def test_heic_to_jpeg_rejects_a_file_that_is_not_an_image(tmp_path):
    src = tmp_path / "bad.heic"
    src.write_bytes(b"this is not an image, whatever the extension claims")

    with pytest.raises(MediaConversionError):
        heic_to_jpeg(src, tmp_path / "out.jpg")
