"""Project documents in MongoDB."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from app.db.mongodb import get_db

DEFAULT_PROJECT_COLORS = (
    "#2563EB",
    "#059669",
    "#D97706",
    "#7C3AED",
    "#DC2626",
    "#0891B2",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_object_id(value: str | ObjectId) -> ObjectId | None:
    try:
        return value if isinstance(value, ObjectId) else ObjectId(str(value))
    except (InvalidId, TypeError, ValueError):
        return None


def serialize_project(
    doc: dict[str, Any] | None,
    *,
    meeting_count: int | None = None,
    owner_name: str = "",
) -> dict[str, Any] | None:
    if not doc:
        return None
    updated = doc.get("updated_at") or doc.get("created_at") or _utcnow()
    return {
        "id": str(doc["_id"]),
        "user_id": str(doc["user_id"]),
        "name": doc.get("name") or "Untitled project",
        "description": doc.get("description") or "",
        "color": doc.get("color") or DEFAULT_PROJECT_COLORS[0],
        "owner": owner_name or doc.get("owner") or "",
        "meeting_count": meeting_count if meeting_count is not None else int(doc.get("meeting_count") or 0),
        "created_at": doc.get("created_at"),
        "updated_at": updated,
        "last_updated_dt": updated,
    }


async def create_project(
    *,
    user_id: str | ObjectId,
    name: str,
    description: str = "",
    color: str | None = None,
) -> dict[str, Any]:
    oid = _to_object_id(user_id)
    if not oid:
        raise ValueError("invalid_user")

    cleaned = (name or "").strip()
    if not cleaned:
        raise ValueError("missing_name")

    now = _utcnow()
    palette = color or DEFAULT_PROJECT_COLORS[hash(cleaned) % len(DEFAULT_PROJECT_COLORS)]
    doc = {
        "user_id": oid,
        "name": cleaned,
        "description": (description or "").strip(),
        "color": palette,
        "created_at": now,
        "updated_at": now,
    }
    result = await get_db().projects.insert_one(doc)
    created = await get_db().projects.find_one({"_id": result.inserted_id})
    return serialize_project(created, meeting_count=0)  # type: ignore[return-value]


async def find_project_by_id(
    project_id: str | ObjectId,
    *,
    user_id: str | ObjectId | None = None,
) -> dict[str, Any] | None:
    oid = _to_object_id(project_id)
    if not oid:
        return None
    query: dict[str, Any] = {"_id": oid}
    if user_id is not None:
        uid = _to_object_id(user_id)
        if not uid:
            return None
        query["user_id"] = uid
    doc = await get_db().projects.find_one(query)
    return serialize_project(doc)


async def list_projects_for_user(
    user_id: str | ObjectId,
    *,
    limit: int | None = None,
    owner_name: str = "",
) -> list[dict[str, Any]]:
    uid = _to_object_id(user_id)
    if not uid:
        return []

    cursor = get_db().projects.find({"user_id": uid}).sort("updated_at", -1)
    if limit:
        cursor = cursor.limit(limit)
    docs = await cursor.to_list(length=limit or 500)

    if not docs:
        return []

    project_oids = [d["_id"] for d in docs]
    pipeline = [
        {"$match": {"user_id": uid, "project_id": {"$in": project_oids}}},
        {"$group": {"_id": "$project_id", "count": {"$sum": 1}}},
    ]
    counts: dict[ObjectId, int] = {}
    async for row in get_db().meetings.aggregate(pipeline):
        counts[row["_id"]] = int(row["count"])

    return [
        serialize_project(
            d,
            meeting_count=counts.get(d["_id"], 0),
            owner_name=owner_name,
        )
        for d in docs
        if d
    ]  # type: ignore[misc]


async def count_projects_for_user(user_id: str | ObjectId) -> int:
    uid = _to_object_id(user_id)
    if not uid:
        return 0
    return int(await get_db().projects.count_documents({"user_id": uid}))


async def touch_project(project_id: str | ObjectId) -> None:
    oid = _to_object_id(project_id)
    if not oid:
        return
    await get_db().projects.update_one(
        {"_id": oid},
        {"$set": {"updated_at": _utcnow()}},
    )
