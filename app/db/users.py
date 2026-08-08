"""users collection helpers — documents use MongoDB _id only (no custom id field)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from app.db.mongodb import get_db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def serialize_user(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a plain dict; expose _id as string for JWT/cookies/templates."""
    if not doc:
        return None
    return {
        "_id": str(doc["_id"]),
        "email": doc.get("email", ""),
        "name": doc.get("name", ""),
        "google_sub": doc.get("google_sub"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


async def find_user_by_email(email: str) -> dict[str, Any] | None:
    doc = await get_db().users.find_one({"email": email.lower().strip()})
    return serialize_user(doc)


async def find_user_by_id(user_id: str | ObjectId) -> dict[str, Any] | None:
    try:
        oid = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
    except (InvalidId, TypeError, ValueError):
        return None
    doc = await get_db().users.find_one({"_id": oid})
    return serialize_user(doc)


async def upsert_google_user(*, email: str, name: str, google_sub: str | None = None) -> dict[str, Any]:
    """
    Create or update a user from Google profile.

    Schema:
    {
      "_id": ObjectId(...),
      "email": "...",
      "name": "...",
      "created_at": ...,
      "updated_at": ...
    }
    """
    db = get_db()
    now = _utcnow()
    email_norm = email.lower().strip()
    existing = await db.users.find_one({"email": email_norm})

    if existing:
        update: dict[str, Any] = {
            "name": name or existing.get("name") or email_norm,
            "updated_at": now,
        }
        if google_sub:
            update["google_sub"] = google_sub
        await db.users.update_one({"_id": existing["_id"]}, {"$set": update})
        return await find_user_by_id(existing["_id"])  # type: ignore[return-value]

    user = {
        "email": email_norm,
        "name": name or email_norm,
        "created_at": now,
        "updated_at": now,
    }
    if google_sub:
        user["google_sub"] = google_sub
    result = await db.users.insert_one(user)
    return await find_user_by_id(result.inserted_id)  # type: ignore[return-value]
