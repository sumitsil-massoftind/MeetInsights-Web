"""Load and expose mock JSON data for the UI."""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

MOCK_DIR = Path(__file__).resolve().parent / "mock_data"


def _load_json(filename: str) -> Any:
    with open(MOCK_DIR / filename, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def get_projects() -> list[dict]:
    projects = _load_json("projects.json")
    for project in projects:
        project["last_updated_dt"] = datetime.fromisoformat(project["last_updated"])
    return projects


@lru_cache(maxsize=1)
def get_meetings() -> list[dict]:
    meetings = _load_json("meetings.json")
    for meeting in meetings:
        meeting["date_dt"] = datetime.fromisoformat(meeting["date"])
        hours, minutes = divmod(meeting["duration_minutes"], 60)
        if hours:
            meeting["duration_label"] = f"{hours}h {minutes}m" if minutes else f"{hours}h"
        else:
            meeting["duration_label"] = f"{minutes}m"
        if meeting.get("project_id") is None:
            meeting["project_name"] = "Unassigned"
    return meetings


@lru_cache(maxsize=1)
def get_activity() -> list[dict]:
    activity = _load_json("activity.json")
    for item in activity:
        item["timestamp_dt"] = datetime.fromisoformat(item["timestamp"])
    return sorted(activity, key=lambda a: a["timestamp_dt"], reverse=True)


@lru_cache(maxsize=1)
def get_chat_responses() -> dict:
    return _load_json("chat_responses.json")


def get_project(project_id: str) -> dict | None:
    return next((p for p in get_projects() if p["id"] == project_id), None)


def get_meeting(meeting_id: str) -> dict | None:
    return next((m for m in get_meetings() if m["id"] == meeting_id), None)


def get_meetings_for_project(project_id: str) -> list[dict]:
    return [m for m in get_meetings() if m.get("project_id") == project_id]


def get_stats() -> dict[str, int]:
    meetings = get_meetings()
    return {
        "total_meetings": len(meetings),
        "total_projects": len(get_projects()),
        "processing": sum(1 for m in meetings if m["status"] == "Processing"),
        "completed": sum(1 for m in meetings if m["status"] == "Completed"),
        "recording": sum(1 for m in meetings if m["status"] == "Recording"),
    }


def get_recent_meetings(limit: int = 5) -> list[dict]:
    return sorted(get_meetings(), key=lambda m: m["date_dt"], reverse=True)[:limit]


def get_recent_projects(limit: int = 4) -> list[dict]:
    return sorted(get_projects(), key=lambda p: p["last_updated_dt"], reverse=True)[:limit]


def mock_chat_reply(message: str) -> str:
    """Return a canned reply based on simple keyword matching."""
    data = get_chat_responses()
    lower = message.lower()
    for entry in data.get("responses", []):
        if any(keyword in lower for keyword in entry.get("keywords", [])):
            return entry["reply"]
    return data.get("default", "I can help you explore this meeting's summary and transcript.")
