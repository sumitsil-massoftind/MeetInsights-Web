"""Safe post-login return paths (share links and in-app pages)."""

from __future__ import annotations

from urllib.parse import unquote


def safe_internal_next(value: str | None) -> str | None:
    """Allow only same-origin relative paths, never protocol-relative or auth URLs."""

    raw = unquote((value or "").strip())
    if not raw.startswith("/") or raw.startswith("//") or "\\" in raw:
        return None
    path = raw.split("?", 1)[0]
    blocked = ("/login", "/auth/", "/logout", "/static/")
    if any(path == item.rstrip("/") or path.startswith(item) for item in blocked):
        return None
    return raw
