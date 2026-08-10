"""Meeting documents in MongoDB."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from app.db.mongodb import get_db

ALLOWED_PLATFORMS = frozenset({"google_meet", "zoom", "teams"})

PLATFORM_LABELS = {
    "google_meet": "Google Meet",
    "zoom": "Zoom",
    "teams": "Microsoft Teams",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def serialize_meeting(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return None
    return {
        "id": str(doc["_id"]),
        "user_id": str(doc["user_id"]),
        "platform": doc.get("platform"),
        "platform_label": PLATFORM_LABELS.get(doc.get("platform", ""), doc.get("platform")),
        "meeting_url": doc.get("meeting_url"),
        "title": doc.get("title"),
        "status": doc.get("status"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


async def create_meeting(
    *,
    user_id: str | ObjectId,
    platform: str,
    meeting_url: str,
    title: str = "",
) -> dict[str, Any]:
    """
    Insert a meeting for processing.

    {
      "_id": ObjectId,
      "user_id": ObjectId,
      "platform": "google_meet|zoom|teams",
      "meeting_url": "...",
      "title": "...",
      "status": "queued",
      "created_at": ...,
      "updated_at": ...
    }
    """
    if platform not in ALLOWED_PLATFORMS:
        raise ValueError("invalid_platform")

    url = (meeting_url or "").strip()
    if not url:
        raise ValueError("missing_url")

    try:
        oid = user_id if isinstance(user_id, ObjectId) else ObjectId(str(user_id))
    except (InvalidId, TypeError, ValueError) as exc:
        raise ValueError("invalid_user") from exc

    now = _utcnow()
    doc = {
        "user_id": oid,
        "platform": platform,
        "meeting_url": url,
        "title": (title or "").strip() or "Untitled meeting",
        "status": "queued",
        "created_at": now,
        "updated_at": now,
    }
    result = await get_db().meetings.insert_one(doc)
    created = await get_db().meetings.find_one({"_id": result.inserted_id})
    return serialize_meeting(created)  # type: ignore[return-value]


async def update_meeting_status(meeting_id: str, status: str) -> None:
    try:
        oid = ObjectId(str(meeting_id))
    except (InvalidId, TypeError, ValueError):
        return
    await get_db().meetings.update_one(
        {"_id": oid},
        {"$set": {"status": status, "updated_at": _utcnow()}},
    )


async def find_meeting_by_id(meeting_id: str) -> dict[str, Any] | None:
    try:
        oid = ObjectId(str(meeting_id))
    except (InvalidId, TypeError, ValueError):
        return None
    doc = await get_db().meetings.find_one({"_id": oid})
    return serialize_meeting(doc)
