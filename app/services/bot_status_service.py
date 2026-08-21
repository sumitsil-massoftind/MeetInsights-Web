"""Fetch live bot pool status from MeetRecorder worker."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.auth.config import get_settings

logger = logging.getLogger(__name__)


async def fetch_bot_status() -> dict[str, Any]:
    """
    Return live bot free/in-use status from MeetRecorder.

    Shape:
      ok, reachable, docker_bots, max_concurrent, used, free, waiting, bots[], error?
    """
    settings = get_settings()
    base = (settings.meetrecorder_status_url or "").rstrip("/")
    empty_bots: list[dict[str, Any]] = []

    if not base:
        return {
            "ok": False,
            "reachable": False,
            "docker_bots": False,
            "max_concurrent": 0,
            "used": 0,
            "free": 0,
            "waiting": 0,
            "bots": empty_bots,
            "error": "MeetRecorder status URL is not configured.",
        }

    url = f"{base}/bots"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.warning("MeetRecorder bot status unavailable: %s", exc)
        return {
            "ok": False,
            "reachable": False,
            "docker_bots": False,
            "max_concurrent": 0,
            "used": 0,
            "free": 0,
            "waiting": 0,
            "bots": empty_bots,
            "error": "MeetRecorder worker is unreachable. Is the worker running?",
        }

    bots = []
    for item in data.get("bots") or []:
        if not isinstance(item, dict):
            continue
        bots.append(
            {
                "id": str(item.get("id") or ""),
                "index": item.get("index"),
                "bot_name": str(item.get("bot_name") or item.get("id") or ""),
                "status": str(item.get("status") or "free"),
                "meeting_id": item.get("meeting_id") or None,
                "meeting_title": item.get("meeting_title") or None,
                "container_name": item.get("container_name") or None,
                "acquired_at": item.get("acquired_at") or None,
            }
        )

    return {
        "ok": bool(data.get("ok", True)),
        "reachable": True,
        "docker_bots": bool(data.get("docker_bots")),
        "max_concurrent": int(data.get("max_concurrent") or len(bots) or 0),
        "used": int(data.get("used") or 0),
        "free": int(data.get("free") or 0),
        "waiting": int(data.get("waiting") or 0),
        "bots": bots,
        "error": None,
    }
