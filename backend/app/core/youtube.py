"""Reducing a pasted YouTube URL to its video id.

Only the id is stored, never the URL, and the embed address is rebuilt from
it at render time. That is the whole security argument: what reaches an
iframe src goes from arbitrary user text to eleven characters drawn from a
fixed alphabet, so there is nothing left to smuggle a javascript: scheme or
a different origin through.
"""

import re
from urllib.parse import parse_qs, urlparse

# YouTube ids are exactly 11 characters of base64url.
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_WATCH_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
_SHORT_HOSTS = {"youtu.be", "www.youtu.be"}

# /embed/<id>, /shorts/<id>, /live/<id> and /v/<id> all put the id in the
# path rather than the query.
_PATH_PREFIXES = ("/embed/", "/shorts/", "/live/", "/v/")


def parse_video_id(raw: str) -> str | None:
    """The 11-character id from a YouTube URL, or None if this is not one.

    Accepts a bare id too, since someone copying from the address bar of a
    share dialog often ends up with just that.
    """
    text = (raw or "").strip()
    if not text:
        return None
    if _ID_RE.match(text):
        return text

    # A scheme-less paste ("youtu.be/xxxx") parses with an empty netloc,
    # which would otherwise fall through as unrecognized.
    if "//" not in text:
        text = f"https://{text}"

    try:
        parsed = urlparse(text)
    except ValueError:
        return None
    # http and https only: a javascript: or data: URL must never be treated
    # as a video reference even if the rest of it looks plausible.
    if parsed.scheme not in ("http", "https"):
        return None

    host = (parsed.hostname or "").lower()
    if host in _SHORT_HOSTS:
        candidate = parsed.path.lstrip("/").split("/")[0]
        return candidate if _ID_RE.match(candidate) else None

    if host in _WATCH_HOSTS:
        if parsed.path == "/watch":
            values = parse_qs(parsed.query).get("v", [])
            candidate = values[0] if values else ""
            return candidate if _ID_RE.match(candidate) else None
        for prefix in _PATH_PREFIXES:
            if parsed.path.startswith(prefix):
                candidate = parsed.path[len(prefix) :].split("/")[0]
                return candidate if _ID_RE.match(candidate) else None

    return None
