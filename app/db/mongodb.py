"""MongoDB connection helpers."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.auth.config import get_settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    settings = get_settings()
    return get_client()[settings.mongodb_db]


async def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


_SHARE_UNIQUE_INDEX = "user_id_1_shared_from_meeting_id_1"
_SHARE_UNIQUE_PARTIAL = {
    "shared_from_meeting_id": {"$exists": True, "$type": "objectId"},
}


def _share_unique_index_is_current(info: dict) -> bool:
    """True when uniqueness only applies to real share copies, not null originals."""
    if not info.get("unique"):
        return False
    if info.get("sparse"):
        return False
    field = (info.get("partialFilterExpression") or {}).get("shared_from_meeting_id")
    if not isinstance(field, dict) or field.get("$exists") is not True:
        return False
    # Mongo may store BSON type as "objectId" or numeric 7.
    return field.get("$type") in ("objectId", "objectid", 7)


async def _ensure_share_unique_index(meetings) -> None:
    """Prevent duplicate shares of the same meeting to one user.

    Original uploads/bot meetings omit shared_from_meeting_id (or store null).
    A unique index without a partial filter treats those nulls as equal, so a
    user can only own one original meeting. Restrict uniqueness to ObjectId
    values.
    """
    existing = await meetings.index_information()
    info = existing.get(_SHARE_UNIQUE_INDEX)
    if info is not None and not _share_unique_index_is_current(info):
        await meetings.drop_index(_SHARE_UNIQUE_INDEX)
    await meetings.create_index(
        [("user_id", 1), ("shared_from_meeting_id", 1)],
        unique=True,
        name=_SHARE_UNIQUE_INDEX,
        partialFilterExpression=_SHARE_UNIQUE_PARTIAL,
    )


async def ensure_indexes() -> None:
    """Create indexes used by auth, projects, and meetings lookups."""
    db = get_db()
    await db.users.create_index("email", unique=True)
    await db.user_sessions.create_index("refresh_token", unique=True)
    await db.user_sessions.create_index([("user_id", 1), ("revoked", 1)])
    await db.user_sessions.create_index("expires_at")
    await db.projects.create_index([("user_id", 1), ("updated_at", -1)])
    await db.meetings.create_index([("user_id", 1), ("created_at", -1)])
    await db.meetings.create_index([("user_id", 1), ("status", 1)])
    await db.meetings.create_index([("user_id", 1), ("project_id", 1)])
    await db.meetings.create_index("status")
    await db.meetings.create_index("share_token", unique=True, sparse=True)
    await _ensure_share_unique_index(db.meetings)
