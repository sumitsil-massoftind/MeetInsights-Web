"""user_sessions collection helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.auth.config import Settings, get_settings
from app.db.mongodb import get_db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_session(*, user_id: int, refresh_token: str) -> dict[str, Any]:
    """
    Store a session row matching:

    {
      "user_id": 2003,
      "refresh_token": "...",
      "expires_at": ...,
      "created_at": ...,
      "revoked": false
    }
    """
    settings = get_settings()
    ttl = Settings.parse_ttl_seconds(settings.refresh_token_expire)
    now = _utcnow()
    session = {
        "user_id": int(user_id),
        "refresh_token": refresh_token,
        "expires_at": now + timedelta(seconds=ttl),
        "created_at": now,
        "revoked": False,
    }
    await get_db().user_sessions.insert_one(session)
    return session


async def find_valid_session(refresh_token: str) -> dict[str, Any] | None:
    now = _utcnow()
    return await get_db().user_sessions.find_one(
        {
            "refresh_token": refresh_token,
            "revoked": False,
            "expires_at": {"$gt": now},
        }
    )


async def revoke_session(refresh_token: str) -> None:
    await get_db().user_sessions.update_one(
        {"refresh_token": refresh_token},
        {"$set": {"revoked": True}},
    )


async def revoke_all_user_sessions(user_id: int) -> None:
    await get_db().user_sessions.update_many(
        {"user_id": int(user_id), "revoked": False},
        {"$set": {"revoked": True}},
    )
