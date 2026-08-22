"""Meeting documents in MongoDB."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import secrets
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

from app.db.mongodb import get_db

ALLOWED_PLATFORMS = frozenset({"google_meet", "zoom", "teams"})

SOURCE_BOT = "bot"
SOURCE_UPLOAD = "upload"
SOURCE_SHARED = "shared"

PLATFORM_LABELS = {
    "google_meet": "Google Meet",
    "zoom": "Zoom",
    "teams": "Microsoft Teams",
}

# Canonical storage values
STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_RECORDING = "recording"
STATUS_RECORDING_INITIATED = "recording_initiated"
STATUS_RECORDING_COMPLETE = "recording_complete"
STATUS_RECORDING_FAILED = "recording_failed"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

STATUS_LABELS = {
    STATUS_QUEUED: "Queued",
    STATUS_PROCESSING: "Processing",
    STATUS_RECORDING: "Recording",
    STATUS_RECORDING_INITIATED: "Starting",
    STATUS_RECORDING_COMPLETE: "Completed",
    STATUS_RECORDING_FAILED: "Failed",
    STATUS_COMPLETED: "Completed",
    STATUS_FAILED: "Failed",
}

# Accept common UI / query aliases
STATUS_ALIASES = {
    "queued": STATUS_QUEUED,
    "processing": STATUS_PROCESSING,
    "recording": STATUS_RECORDING,
    "recording_initiated": STATUS_RECORDING_INITIATED,
    "recording_complete": STATUS_RECORDING_COMPLETE,
    "recording_failed": STATUS_RECORDING_FAILED,
    "completed": STATUS_COMPLETED,
    "failed": STATUS_FAILED,
}

# UI filters group worker statuses with legacy dashboard statuses
STATUS_FILTER_GROUPS = {
    STATUS_QUEUED: [STATUS_QUEUED],
    STATUS_PROCESSING: [STATUS_PROCESSING, STATUS_RECORDING_INITIATED],
    STATUS_RECORDING: [STATUS_RECORDING, STATUS_RECORDING_INITIATED],
    STATUS_COMPLETED: [STATUS_COMPLETED, STATUS_RECORDING_COMPLETE],
    STATUS_FAILED: [STATUS_FAILED, STATUS_RECORDING_FAILED],
    STATUS_RECORDING_INITIATED: [STATUS_RECORDING_INITIATED],
    STATUS_RECORDING_COMPLETE: [STATUS_RECORDING_COMPLETE],
    STATUS_RECORDING_FAILED: [STATUS_RECORDING_FAILED],
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


def status_filter_query(value: str | None) -> dict[str, Any] | None:
    """Mongo filter for a UI status, including worker lifecycle aliases."""
    normalized = normalize_status(value)
    if not normalized:
        return None
    group = STATUS_FILTER_GROUPS.get(normalized, [normalized])
    if len(group) == 1:
        return {"status": group[0]}
    return {"status": {"$in": list(group)}}


def status_label(raw: str | None) -> str:
    key = normalize_status(raw) or (raw or STATUS_QUEUED)
    return STATUS_LABELS.get(key, (raw or "Unknown").title())


def _serialize_action_items(raw: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for value in raw or []:
        if isinstance(value, dict):
            task = str(value.get("task") or "").strip()
            owner = str(value.get("owner") or "").strip()
            deadline = str(value.get("deadline") or "").strip()
        else:
            task = str(value or "").strip()
            owner = ""
            deadline = ""
        if not task:
            continue
        items.append({"task": task, "owner": owner, "deadline": deadline})
    return items


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
    source = doc.get("source") or SOURCE_BOT
    platform = doc.get("platform")
    platform_label = PLATFORM_LABELS.get(platform, platform)
    if source == SOURCE_UPLOAD and not platform_label:
        platform_label = "Uploaded recording"

    full_transcript = (doc.get("transcript") or "").strip()
    segments = doc.get("transcript_segments") or []
    speakers = doc.get("speakers") or []
    preview = (doc.get("transcript_preview") or "").strip()
    if not preview and full_transcript:
        preview = full_transcript[:500]
        if len(full_transcript) > 500:
            preview = preview.rstrip() + "…"

    return {
        "id": str(doc["_id"]),
        "user_id": str(doc["user_id"]),
        "platform": platform,
        "platform_label": platform_label,
        "meeting_url": doc.get("meeting_url"),
        "title": title,
        "name": title,
        "source": source,
        "is_shared": source == SOURCE_SHARED,
        "shared_from_meeting_id": str(doc["shared_from_meeting_id"])
        if doc.get("shared_from_meeting_id")
        else None,
        "recording_filename": doc.get("recording_filename"),
        "original_filename": doc.get("original_filename"),
        "file_size_bytes": doc.get("file_size_bytes"),
        "bot_slot": doc.get("bot_slot"),
        "bot_name": doc.get("bot_name"),
        "container_name": doc.get("container_name"),
        "status_raw": normalize_status(raw_status) or raw_status,
        "status": status_label(raw_status),
        "project_id": project_id,
        "project_name": project_name if project_name is not None else ("Unassigned" if not project_id else "Project"),
        "created_at": created,
        "updated_at": doc.get("updated_at") or created,
        "date_dt": created,
        "duration_minutes": duration,
        "duration_label": f"{duration} min" if duration else "—",
        "language": doc.get("language"),
        "speakers": speakers,
        "transcript": full_transcript,
        "transcript_segments": segments,
        "has_transcript": bool(segments or full_transcript),
        "has_summary": bool((doc.get("summary") or "").strip()),
        "summary": doc.get("summary")
        or "Summary will appear here once the meeting has been processed.",
        "summary_meeting_objective": doc.get("summary_meeting_objective") or "",
        "summary_key_points": doc.get("summary_key_points") or [],
        "summary_discussion": doc.get("summary_discussion") or [],
        "summary_requirements": doc.get("summary_requirements") or [],
        "summary_decisions": doc.get("summary_decisions") or [],
        "summary_action_items": _serialize_action_items(doc.get("summary_action_items")),
        "summary_open_questions": doc.get("summary_open_questions") or [],
        "summary_outcome": doc.get("summary_outcome") or "",
        "transcript_preview": preview
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
        "source": SOURCE_BOT,
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


async def create_uploaded_meeting(
    *,
    user_id: str | ObjectId,
    title: str = "",
    platform: str | None = None,
    project_id: str | ObjectId | None = None,
    recording_filename: str,
    recording_path: str,
    original_filename: str = "",
    file_size_bytes: int = 0,
) -> dict[str, Any]:
    """Insert a meeting whose recording is already stored locally."""
    uid = _to_object_id(user_id)
    if not uid:
        raise ValueError("invalid_user")

    platform_value = (platform or "").strip()
    if platform_value and platform_value not in ALLOWED_PLATFORMS:
        raise ValueError("invalid_platform")

    filename = (recording_filename or "").strip()
    stored_path = (recording_path or "").strip()
    if not filename or not stored_path:
        raise ValueError("missing_recording")

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

    display_title = (title or "").strip()
    if not display_title:
        stem = Path(original_filename or filename).stem.replace("-", " ").replace("_", " ").strip()
        display_title = stem or "Uploaded recording"

    now = _utcnow()
    doc: dict[str, Any] = {
        "user_id": uid,
        "platform": platform_value or None,
        "meeting_url": None,
        "title": display_title,
        "status": STATUS_QUEUED,
        "source": SOURCE_UPLOAD,
        "storage": "local",
        "recording_filename": filename,
        "recording_path": stored_path,
        "original_filename": (original_filename or "").strip() or filename,
        "file_size_bytes": int(file_size_bytes or 0),
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


def _search_regex(term: str) -> dict[str, str]:
    return {"$regex": re.escape(term), "$options": "i"}


async def _meetings_query(
    uid: ObjectId,
    *,
    status: str | None = None,
    project_id: str | ObjectId | None = None,
    q: str | None = None,
) -> dict[str, Any] | None:
    query: dict[str, Any] = {"user_id": uid}
    status_q = status_filter_query(status)
    if status_q:
        query.update(status_q)
    if project_id is not None:
        poid = _to_object_id(project_id)
        if not poid:
            return None
        query["project_id"] = poid

    term = (q or "").strip()[:80]
    if term:
        regex = _search_regex(term)
        clauses: list[dict[str, Any]] = [{"title": regex}]
        project_ids = await get_db().projects.distinct(
            "_id",
            {"user_id": uid, "name": regex},
        )
        if project_ids:
            clauses.append({"project_id": {"$in": list(project_ids)}})
        if "unassigned".startswith(term.lower()) and len(term) >= 3:
            clauses.append(
                {
                    "$or": [
                        {"project_id": None},
                        {"project_id": {"$exists": False}},
                    ]
                }
            )
        query["$or"] = clauses
    return query


async def list_meetings_for_user(
    user_id: str | ObjectId,
    *,
    status: str | None = None,
    project_id: str | ObjectId | None = None,
    q: str | None = None,
    limit: int | None = None,
    skip: int = 0,
) -> list[dict[str, Any]]:
    uid = _to_object_id(user_id)
    if not uid:
        return []

    query = await _meetings_query(uid, status=status, project_id=project_id, q=q)
    if query is None:
        return []

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
    q: str | None = None,
) -> int:
    uid = _to_object_id(user_id)
    if not uid:
        return 0
    query = await _meetings_query(uid, status=status, project_id=project_id, q=q)
    if query is None:
        return 0
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
        "processing": by_status.get(STATUS_PROCESSING, 0)
        + by_status.get(STATUS_QUEUED, 0)
        + by_status.get(STATUS_RECORDING_INITIATED, 0),
        "completed": by_status.get(STATUS_COMPLETED, 0)
        + by_status.get(STATUS_RECORDING_COMPLETE, 0),
        "recording": by_status.get(STATUS_RECORDING, 0),
        "queued": by_status.get(STATUS_QUEUED, 0),
        "failed": by_status.get(STATUS_FAILED, 0)
        + by_status.get(STATUS_RECORDING_FAILED, 0),
    }


SHARE_COPY_FIELDS = (
    "platform",
    "meeting_url",
    "title",
    "status",
    "storage",
    "recording_filename",
    "recording_path",
    "original_filename",
    "file_size_bytes",
    "language",
    "duration_minutes",
    "transcript",
    "transcript_preview",
    "transcript_segments",
    "speakers",
    "transcription_provider",
    "summary",
    "summary_meeting_objective",
    "summary_key_points",
    "summary_discussion",
    "summary_requirements",
    "summary_decisions",
    "summary_action_items",
    "summary_open_questions",
    "summary_outcome",
    "summary_provider",
    "summarized_at",
    "processed_at",
)


def _is_share_token(token: str) -> bool:
    value = (token or "").strip()
    if len(value) < 8 or len(value) > 64:
        return False
    return all(ch.isalnum() or ch in "-_" for ch in value)


async def ensure_share_token(
    *,
    meeting_id: str | ObjectId,
    user_id: str | ObjectId,
) -> str:
    """Return a stable share token for a meeting the user owns."""

    mid = _to_object_id(meeting_id)
    uid = _to_object_id(user_id)
    if not mid or not uid:
        raise ValueError("not_found")

    existing = await get_db().meetings.find_one({"_id": mid, "user_id": uid})
    if not existing:
        raise ValueError("not_found")

    current = str(existing.get("share_token") or "").strip()
    if current:
        return current

    for _ in range(6):
        token = secrets.token_urlsafe(16)
        result = await get_db().meetings.update_one(
            {
                "_id": mid,
                "user_id": uid,
                "$or": [
                    {"share_token": {"$exists": False}},
                    {"share_token": ""},
                    {"share_token": None},
                ],
            },
            {"$set": {"share_token": token, "updated_at": _utcnow()}},
        )
        if result.modified_count:
            return token
        refreshed = await get_db().meetings.find_one({"_id": mid, "user_id": uid})
        current = str((refreshed or {}).get("share_token") or "").strip()
        if current:
            return current

    raise ValueError("share_failed")


async def claim_shared_meeting(
    *,
    token: str,
    user_id: str | ObjectId,
) -> tuple[dict[str, Any], str]:
    """
    Open a share link.

    Returns (serialized meeting, reason) where reason is:
      owner | existing | created
    """

    if not _is_share_token(token):
        raise ValueError("invalid_share")

    uid = _to_object_id(user_id)
    if not uid:
        raise ValueError("invalid_user")

    source = await get_db().meetings.find_one({"share_token": token.strip()})
    if not source:
        raise ValueError("invalid_share")

    if source.get("user_id") == uid:
        serialized = serialize_meeting(source)
        if not serialized:
            raise ValueError("invalid_share")
        return serialized, "owner"

    existing = await get_db().meetings.find_one(
        {"user_id": uid, "shared_from_meeting_id": source["_id"]}
    )
    if existing:
        serialized = serialize_meeting(existing)
        if not serialized:
            raise ValueError("invalid_share")
        return serialized, "existing"

    now = _utcnow()
    copy: dict[str, Any] = {
        field: source[field]
        for field in SHARE_COPY_FIELDS
        if field in source
    }
    copy.update(
        {
            "user_id": uid,
            "source": SOURCE_SHARED,
            "project_id": None,
            "shared_from_meeting_id": source["_id"],
            "shared_by_user_id": source.get("user_id"),
            "created_at": now,
            "updated_at": now,
        }
    )
    try:
        result = await get_db().meetings.insert_one(copy)
    except DuplicateKeyError:
        existing = await get_db().meetings.find_one(
            {"user_id": uid, "shared_from_meeting_id": source["_id"]}
        )
        serialized = serialize_meeting(existing)
        if not serialized:
            raise ValueError("share_failed")
        return serialized, "existing"
    created = await get_db().meetings.find_one({"_id": result.inserted_id})
    serialized = serialize_meeting(created)
    if not serialized:
        raise ValueError("share_failed")
    return serialized, "created"


async def pop_meeting_for_user(
    *,
    meeting_id: str | ObjectId,
    user_id: str | ObjectId,
) -> dict[str, Any] | None:
    """Delete a meeting owned by the user and return the raw document."""
    mid = _to_object_id(meeting_id)
    uid = _to_object_id(user_id)
    if not mid or not uid:
        return None
    return await get_db().meetings.find_one_and_delete({"_id": mid, "user_id": uid})


async def count_recording_refs(recording_filename: str | None, *, exclude_id: ObjectId | None = None) -> int:
    filename = (recording_filename or "").strip()
    if not filename:
        return 0
    query: dict[str, Any] = {"recording_filename": filename}
    if exclude_id is not None:
        query["_id"] = {"$ne": exclude_id}
    return int(await get_db().meetings.count_documents(query))


async def list_project_meeting_docs(
    *,
    user_id: str | ObjectId,
    project_id: str | ObjectId,
) -> list[dict[str, Any]]:
    uid = _to_object_id(user_id)
    poid = _to_object_id(project_id)
    if not uid or not poid:
        return []
    return await get_db().meetings.find({"user_id": uid, "project_id": poid}).to_list(length=5000)


async def unassign_project_meetings(
    *,
    user_id: str | ObjectId,
    project_id: str | ObjectId,
) -> int:
    uid = _to_object_id(user_id)
    poid = _to_object_id(project_id)
    if not uid or not poid:
        return 0
    result = await get_db().meetings.update_many(
        {"user_id": uid, "project_id": poid},
        {"$set": {"project_id": None, "updated_at": _utcnow()}},
    )
    return int(result.modified_count)

