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

# Canonical storage values
STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_RECORDING = "recording"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

STATUS_LABELS = {
    STATUS_QUEUED: "Queued",
    STATUS_PROCESSING: "Processing",
    STATUS_RECORDING: "Recording",
    STATUS_COMPLETED: "Completed",
    STATUS_FAILED: "Failed",
}

# Accept common UI / query aliases
STATUS_ALIASES = {
    "queued": STATUS_QUEUED,
    "processing": STATUS_PROCESSING,
    "recording": STATUS_RECORDING,
    "completed": STATUS_COMPLETED,
    "failed": STATUS_FAILED,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_object_id(value: str | ObjectId | None) -> ObjectId | None:
    if value is None or value == "":
        return None
    try:
        return value if isinstance(value, ObjectId) else ObjectId(str(value))
    except (InvalidId, TypeError, ValueError):
        return None


def normalize_status(value: str | None) -> str | None:
    if not value:
        return None
    return STATUS_ALIASES.get(value.strip().lower())


def status_label(raw: str | None) -> str:
    key = normalize_status(raw) or (raw or STATUS_QUEUED)
    return STATUS_LABELS.get(key, (raw or "Unknown").title())


def serialize_meeting(
    doc: dict[str, Any] | None,
    *,
    project_name: str | None = None,
) -> dict[str, Any] | None:
    if not doc:
        return None

    created = doc.get("created_at") or _utcnow()
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    title = doc.get("title") or "Untitled meeting"
    raw_status = doc.get("status") or STATUS_QUEUED
    project_oid = doc.get("project_id")
    project_id = str(project_oid) if project_oid else None
    duration = doc.get("duration_minutes")

    return {
        "id": str(doc["_id"]),
        "user_id": str(doc["user_id"]),
        "platform": doc.get("platform"),
        "platform_label": PLATFORM_LABELS.get(doc.get("platform", ""), doc.get("platform")),
        "meeting_url": doc.get("meeting_url"),
        "title": title,
        "name": title,
        "status_raw": normalize_status(raw_status) or raw_status,
        "status": status_label(raw_status),
        "project_id": project_id,
        "project_name": project_name if project_name is not None else ("Unassigned" if not project_id else "Project"),
        "created_at": created,
        "updated_at": doc.get("updated_at") or created,
        "date_dt": created,
        "duration_minutes": duration,
        "duration_label": f"{duration} min" if duration else "—",
        "summary": doc.get("summary")
        or "Summary will appear here once the meeting has been processed.",
        "transcript_preview": doc.get("transcript_preview")
        or "Transcript preview will appear after processing completes.",
    }


async def create_meeting(
    *,
    user_id: str | ObjectId,
    platform: str,
    meeting_url: str,
    title: str = "",
    project_id: str | ObjectId | None = None,
) -> dict[str, Any]:
    """
    Insert a meeting for processing.

    Optional project_id links the meeting under a project (same user).
    """
    if platform not in ALLOWED_PLATFORMS:
        raise ValueError("invalid_platform")

    url = (meeting_url or "").strip()
    if not url:
        raise ValueError("missing_url")

    uid = _to_object_id(user_id)
    if not uid:
        raise ValueError("invalid_user")

    project_oid = None
    project_name: str | None = None
    if project_id not in (None, ""):
        project_oid = _to_object_id(project_id)
        if not project_oid:
            raise ValueError("invalid_project")
        project = await get_db().projects.find_one({"_id": project_oid, "user_id": uid})
        if not project:
            raise ValueError("invalid_project")
        project_name = project.get("name") or "Project"

    now = _utcnow()
    doc: dict[str, Any] = {
        "user_id": uid,
        "platform": platform,
        "meeting_url": url,
        "title": (title or "").strip() or "Untitled meeting",
        "status": STATUS_QUEUED,
        "project_id": project_oid,
        "created_at": now,
        "updated_at": now,
    }
    result = await get_db().meetings.insert_one(doc)
    if project_oid:
        await get_db().projects.update_one(
            {"_id": project_oid},
            {"$set": {"updated_at": now}},
        )
    created = await get_db().meetings.find_one({"_id": result.inserted_id})
    return serialize_meeting(created, project_name=project_name)  # type: ignore[return-value]


async def update_meeting_status(meeting_id: str, status: str) -> None:
    try:
        oid = ObjectId(str(meeting_id))
    except (InvalidId, TypeError, ValueError):
        return
    normalized = normalize_status(status) or status
    await get_db().meetings.update_one(
        {"_id": oid},
        {"$set": {"status": normalized, "updated_at": _utcnow()}},
    )


async def update_meeting_project(
    *,
    meeting_id: str | ObjectId,
    user_id: str | ObjectId,
    project_id: str | ObjectId | None,
) -> dict[str, Any]:
    """
    Assign or unassign a meeting to a project owned by the same user.

    project_id empty/None → unassigned.
    """
    mid = _to_object_id(meeting_id)
    uid = _to_object_id(user_id)
    if not mid or not uid:
        raise ValueError("invalid_meeting")

    existing = await get_db().meetings.find_one({"_id": mid, "user_id": uid})
    if not existing:
        raise ValueError("not_found")

    project_oid = None
    project_name: str | None = None
    if project_id not in (None, ""):
        project_oid = _to_object_id(project_id)
        if not project_oid:
            raise ValueError("invalid_project")
        project = await get_db().projects.find_one({"_id": project_oid, "user_id": uid})
        if not project:
            raise ValueError("invalid_project")
        project_name = project.get("name") or "Project"

    now = _utcnow()
    await get_db().meetings.update_one(
        {"_id": mid, "user_id": uid},
        {"$set": {"project_id": project_oid, "updated_at": now}},
    )
    if project_oid:
        await get_db().projects.update_one(
            {"_id": project_oid},
            {"$set": {"updated_at": now}},
        )

    updated = await get_db().meetings.find_one({"_id": mid})
    return serialize_meeting(updated, project_name=project_name)  # type: ignore[return-value]


async def find_meeting_by_id(
    meeting_id: str,
    *,
    user_id: str | ObjectId | None = None,
) -> dict[str, Any] | None:
    oid = _to_object_id(meeting_id)
    if not oid:
        return None
    query: dict[str, Any] = {"_id": oid}
    if user_id is not None:
        uid = _to_object_id(user_id)
        if not uid:
            return None
        query["user_id"] = uid
    doc = await get_db().meetings.find_one(query)
    if not doc:
        return None
    project_name = None
    if doc.get("project_id"):
        project = await get_db().projects.find_one({"_id": doc["project_id"]})
        if project:
            project_name = project.get("name")
    return serialize_meeting(doc, project_name=project_name)


async def list_meetings_for_user(
    user_id: str | ObjectId,
    *,
    status: str | None = None,
    project_id: str | ObjectId | None = None,
    limit: int | None = None,
    skip: int = 0,
) -> list[dict[str, Any]]:
    uid = _to_object_id(user_id)
    if not uid:
        return []

    query: dict[str, Any] = {"user_id": uid}
    normalized = normalize_status(status)
    if normalized:
        query["status"] = normalized
    if project_id is not None:
        poid = _to_object_id(project_id)
        if not poid:
            return []
        query["project_id"] = poid

    cursor = get_db().meetings.find(query).sort("created_at", -1).skip(skip)
    if limit is not None:
        cursor = cursor.limit(limit)
    docs = await cursor.to_list(length=limit if limit is not None else 1000)

    project_ids = {d["project_id"] for d in docs if d.get("project_id")}
    names: dict[ObjectId, str] = {}
    if project_ids:
        async for p in get_db().projects.find({"_id": {"$in": list(project_ids)}}):
            names[p["_id"]] = p.get("name") or "Project"

    result: list[dict[str, Any]] = []
    for d in docs:
        pid = d.get("project_id")
        serialized = serialize_meeting(
            d,
            project_name=names.get(pid) if pid else None,
        )
        if serialized:
            result.append(serialized)
    return result


async def count_meetings_for_user(
    user_id: str | ObjectId,
    *,
    status: str | None = None,
    project_id: str | ObjectId | None = None,
) -> int:
    uid = _to_object_id(user_id)
    if not uid:
        return 0
    query: dict[str, Any] = {"user_id": uid}
    normalized = normalize_status(status)
    if normalized:
        query["status"] = normalized
    if project_id is not None:
        poid = _to_object_id(project_id)
        if not poid:
            return 0
        query["project_id"] = poid
    return int(await get_db().meetings.count_documents(query))


async def meeting_stats_for_user(user_id: str | ObjectId) -> dict[str, int]:
    uid = _to_object_id(user_id)
    if not uid:
        return {
            "total_meetings": 0,
            "processing": 0,
            "completed": 0,
            "recording": 0,
            "queued": 0,
            "failed": 0,
        }

    total = int(await get_db().meetings.count_documents({"user_id": uid}))
    pipeline = [
        {"$match": {"user_id": uid}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    by_status: dict[str, int] = {}
    async for row in get_db().meetings.aggregate(pipeline):
        key = normalize_status(row["_id"]) or str(row["_id"] or "")
        by_status[key] = int(row["count"])

    return {
        "total_meetings": total,
        "processing": by_status.get(STATUS_PROCESSING, 0) + by_status.get(STATUS_QUEUED, 0),
        "completed": by_status.get(STATUS_COMPLETED, 0),
        "recording": by_status.get(STATUS_RECORDING, 0),
        "queued": by_status.get(STATUS_QUEUED, 0),
        "failed": by_status.get(STATUS_FAILED, 0),
    }
