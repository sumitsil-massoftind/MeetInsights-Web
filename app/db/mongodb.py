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
    await db.meetings.create_index(
        [("user_id", 1), ("shared_from_meeting_id", 1)],
        unique=True,
        sparse=True,
    )
