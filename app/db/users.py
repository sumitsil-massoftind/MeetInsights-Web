"""users collection helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument

from app.auth.config import get_settings
from app.db.mongodb import get_db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def next_user_id() -> int:
    """Atomic integer id sequence (schema uses numeric id, e.g. 2003)."""
    settings = get_settings()
    db = get_db()
    doc = await db.counters.find_one_and_update(
        {"_id": "users"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    seq = int(doc.get("seq", 1))
    # First insert after upsert starts at 1 — bump to USER_ID_START
    if seq < settings.user_id_start:
        doc = await db.counters.find_one_and_update(
            {"_id": "users"},
            {"$set": {"seq": settings.user_id_start}},
            return_document=ReturnDocument.AFTER,
        )
        seq = int(doc["seq"])
    return seq


async def find_user_by_email(email: str) -> dict[str, Any] | None:
    return await get_db().users.find_one({"email": email.lower().strip()})


async def find_user_by_id(user_id: int) -> dict[str, Any] | None:
    return await get_db().users.find_one({"id": int(user_id)})


async def upsert_google_user(*, email: str, name: str, google_sub: str | None = None) -> dict[str, Any]:
    """
    Create or update a user from Google profile.

    Schema:
    {
      "id": 2003,
      "email": "...",
      "name": "...",
      "created_at": ...,
      "updated_at": ...
    }
    """
    db = get_db()
    now = _utcnow()
    email_norm = email.lower().strip()
    existing = await find_user_by_email(email_norm)

    if existing:
        update: dict[str, Any] = {
            "name": name or existing.get("name") or email_norm,
            "updated_at": now,
        }
        if google_sub:
            update["google_sub"] = google_sub
        await db.users.update_one({"id": existing["id"]}, {"$set": update})
        return await find_user_by_id(existing["id"])  # type: ignore[return-value]

    user_id = await next_user_id()
    user = {
        "id": user_id,
        "email": email_norm,
        "name": name or email_norm,
        "created_at": now,
        "updated_at": now,
    }
    if google_sub:
        user["google_sub"] = google_sub
    await db.users.insert_one(user)
    # Drop Mongo _id from returned view for templates
    stored = await find_user_by_id(user_id)
    return stored  # type: ignore[return-value]
