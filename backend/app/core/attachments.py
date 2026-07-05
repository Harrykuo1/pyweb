"""Helpers shared by the job-attachment upload/list/delete endpoints.

The allowlists below are the single source of truth for what the
backend will accept. The browser sets Content-Type for itself so MIME
matching alone isn't authoritative — we also enforce an extension
allowlist as a cheap defense-in-depth measure against drive-by
uploads of executables that lie about being PDFs.
"""

from pathlib import Path

# Extensions whose bytes the browser can safely render in place: the
# download endpoint serves these with Content-Disposition: inline so
# <embed src> / <img src> in the viewer pick them up. Office formats
# don't appear here — they're previewed via the OnlyOffice-converted
# .preview.pdf served from a separate route. Everything outside this
# set gets forced down as an attachment plus X-Content-Type-Options:
# nosniff, so HTML / SVG / scripts can't ride the same response to
# get an inline-render XSS foothold.
PREVIEW_INLINE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
    }
)


# OS-spat metadata files that show up in folder uploads but the
# operator never actually wants archived. Frontend should also skip
# these client-side; the backend list is the safety net.
JUNK_BASENAMES: frozenset[str] = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})


def sanitize_relpath(name: str) -> str:
    """Reduce a user-supplied relative path to a safe forward-slash
    form. Each segment runs through the basename-safety checks so the
    full path can't escape the per-job directory.

    Accepts:
      * single basenames (legacy single-file upload), and
      * forward-slash separated relative paths (folder uploads).

    Rejects null bytes, backslashes (Windows clients must normalise
    before sending), absolute paths, parent references, dot-segments,
    and empty segments. Raises ValueError with a Traditional-Chinese
    message that surfaces directly in the upload error toast.
    """
    if not name:
        raise ValueError("檔名不可為空")
    if "\x00" in name or "\\" in name:
        raise ValueError("檔名包含不允許的字元")
    if name.startswith("/"):
        raise ValueError("檔名無效")
    parts = name.split("/")
    safe_parts: list[str] = []
    for part in parts:
        if not part or part in {".", ".."}:
            raise ValueError("檔名無效")
        if len(part) > 255:
            raise ValueError("檔名過長")
        safe_parts.append(part)
    if not safe_parts:
        raise ValueError("檔名無效")
    return "/".join(safe_parts)


# Back-compat alias for callers that only ever dealt with bare
# filenames; sanitize_relpath does the right thing for both shapes.
sanitize_filename = sanitize_relpath


def is_junk(relpath: str) -> bool:
    """True when the last segment is an OS-metadata file we always
    want to skip — frontend filters these too but a sneaky uploader
    might bypass that."""
    last = relpath.rsplit("/", 1)[-1]
    return last in JUNK_BASENAMES


def ext_of(name: str) -> str:
    return Path(name).suffix.lower()


def next_available_relpath(directory: Path, relpath: str) -> str:
    """Return `relpath` unchanged if no file by that path exists under
    `directory`; otherwise append " (N)" to the last segment and bump
    until a free slot is found. Mirrors the macOS/Windows Finder
    rename UX, but path-aware: "src/foo.py" colliding becomes
    "src/foo (1).py", not "src/foo.py (1)"."""
    candidate = directory / relpath
    if not candidate.exists():
        return relpath
    pure = Path(relpath)
    parent = pure.parent  # PurePath; "." for bare basenames
    stem = pure.stem
    suffix = pure.suffix
    n = 1
    while True:
        renamed_last = f"{stem} ({n}){suffix}"
        renamed = (
            renamed_last
            if str(parent) == "."
            else f"{parent.as_posix()}/{renamed_last}"
        )
        if not (directory / renamed).exists():
            return renamed
        n += 1


# Back-compat alias.
next_available_filename = next_available_relpath
