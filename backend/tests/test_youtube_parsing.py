"""The parser is the security boundary for YouTube references.

Only the extracted id is stored and the embed URL is rebuilt from it, so
whatever reaches an iframe src is eleven characters of a fixed alphabet.
These tests exist to keep it that way: anything that is not a YouTube video
URL has to come back None rather than be passed along.
"""

import pytest

from app.core.youtube import parse_video_id

VIDEO_ID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={VIDEO_ID}",
        f"https://youtube.com/watch?v={VIDEO_ID}",
        f"https://m.youtube.com/watch?v={VIDEO_ID}",
        # Share links carry a timestamp and a tracking parameter.
        f"https://www.youtube.com/watch?v={VIDEO_ID}&t=42s&feature=share",
        f"https://youtu.be/{VIDEO_ID}",
        f"https://youtu.be/{VIDEO_ID}?t=42",
        f"https://www.youtube.com/embed/{VIDEO_ID}",
        f"https://www.youtube.com/shorts/{VIDEO_ID}",
        f"https://www.youtube.com/live/{VIDEO_ID}",
        f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}",
        "http://www.youtube.com/watch?v=" + VIDEO_ID,
        # No scheme, which is what a copy out of the address bar often gives.
        f"youtu.be/{VIDEO_ID}",
        f"www.youtube.com/watch?v={VIDEO_ID}",
        # Someone pasting just the id.
        VIDEO_ID,
        f"  https://youtu.be/{VIDEO_ID}  ",
    ],
)
def test_recognized_forms_yield_the_id(url):
    assert parse_video_id(url) == VIDEO_ID


@pytest.mark.parametrize(
    "label,url",
    [
        ("empty", ""),
        ("whitespace", "   "),
        ("not a url at all", "看這個影片"),
        # A javascript: URL must never survive, however video-ish it looks.
        ("javascript scheme", f"javascript:alert('{VIDEO_ID}')"),
        ("data scheme", "data:text/html,<script>alert(1)</script>"),
        # A lookalike host is the obvious way to aim an iframe elsewhere.
        ("lookalike host", f"https://youtube.com.evil.test/watch?v={VIDEO_ID}"),
        ("unrelated host", f"https://vimeo.com/watch?v={VIDEO_ID}"),
        # A suffix match on the host would let these through, which is the
        # whole reason the allowlist compares whole hostnames.
        ("host ending in youtu.be", f"https://evil-youtu.be/{VIDEO_ID}"),
        ("host ending in youtube.com", f"https://evilyoutube.com/watch?v={VIDEO_ID}"),
        ("subdomain of an attacker", f"https://youtu.be.evil.test/{VIDEO_ID}"),
        ("youtube but not a video", "https://www.youtube.com/results?q=x"),
        ("channel page", "https://www.youtube.com/@someone"),
        ("id too short", "https://youtu.be/abc"),
        ("id too long", f"https://youtu.be/{VIDEO_ID}XXXX"),
        ("id with a bad character", "https://youtu.be/dQw4w9WgXc!"),
        ("watch with no v", "https://www.youtube.com/watch?t=1"),
    ],
)
def test_everything_else_is_refused(label, url):
    assert parse_video_id(url) is None, label


def test_the_parsed_id_is_always_embed_safe():
    # What the endpoint stores is what ends up in an iframe src, so the
    # charset is the guarantee — not escaping at render time.
    parsed = parse_video_id(f"https://youtu.be/{VIDEO_ID}?t=1&si=abc")
    assert parsed is not None
    assert len(parsed) == 11
    assert all(c.isalnum() or c in "-_" for c in parsed)
