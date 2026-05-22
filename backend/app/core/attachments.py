"""Helpers shared by the job-attachment upload/list/delete endpoints.

The allowlists below are the single source of truth for what the
backend will accept. The browser sets Content-Type for itself so MIME
matching alone isn't authoritative — we also enforce an extension
allowlist as a cheap defense-in-depth measure against drive-by
uploads of executables that lie about being PDFs.
"""
from pathlib import Path

ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf",
        ".ppt",
        ".pptx",
        ".doc",
        ".docx",
        ".png",
        ".jpg",
        ".jpeg",
    }
)

ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "image/png",
        "image/jpeg",
    }
)


def sanitize_filename(name: str) -> str:
    """Reduce a user-supplied filename to a base name with no directory
    components and no special control characters. Raises ValueError if
    the input can't safely be used as a per-job filename.

    Error messages are in Traditional Chinese because they surface
    directly in the upload error toast on the frontend."""
    if not name:
        raise ValueError("檔名不可為空")
    base = Path(name).name
    if not base or base in {".", ".."}:
        raise ValueError("檔名無效")
    if "\x00" in base or "/" in base or "\\" in base:
        raise ValueError("檔名包含不允許的字元")
    if len(base) > 255:
        raise ValueError("檔名過長")
    return base


def ext_of(name: str) -> str:
    return Path(name).suffix.lower()


def next_available_filename(directory: Path, name: str) -> str:
    """Return `name` unchanged if no file by that name exists in
    `directory`; otherwise append " (N)" before the extension and bump
    until a free slot is found. Mirrors the macOS/Windows Finder
    rename UX so the on-disk name and the user-visible name stay in
    lockstep."""
    candidate = directory / name
    if not candidate.exists():
        return name
    stem = Path(name).stem
    suffix = Path(name).suffix
    n = 1
    while True:
        renamed = f"{stem} ({n}){suffix}"
        if not (directory / renamed).exists():
            return renamed
        n += 1
