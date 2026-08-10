"""Start-meeting business flow: persist then enqueue."""

from __future__ import annotations

import logging
from typing import Any

from app.db import meetings as meetings_repo
from app.queue.rabbitmq import publish_meeting_id

logger = logging.getLogger(__name__)


class MeetingStartError(Exception):
    def __init__(self, public_message: str, *, log_message: str = "") -> None:
        self.public_message = public_message
        self.log_message = log_message or public_message
        super().__init__(self.log_message)


async def start_meeting(
    *,
    user_id: str,
    platform: str,
    meeting_url: str,
    title: str = "",
    project_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a meeting in MongoDB and push its id to RabbitMQ.

    On queue failure the meeting status is set to `failed`.
    """
    try:
        meeting = await meetings_repo.create_meeting(
            user_id=user_id,
            platform=platform,
            meeting_url=meeting_url,
            title=title,
            project_id=project_id or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "invalid_platform":
            raise MeetingStartError("Please choose a valid meeting platform.") from exc
        if code == "missing_url":
            raise MeetingStartError("Please enter a meeting link.") from exc
        if code == "invalid_project":
            raise MeetingStartError("Please choose a valid project.") from exc
        raise MeetingStartError("Unable to invite the bot. Please try again.") from exc
    except Exception as exc:
        logger.exception("Failed to insert meeting for user=%s", user_id)
        raise MeetingStartError("Unable to invite the bot. Please try again.") from exc

    meeting_id = meeting["id"]
    try:
        await publish_meeting_id(meeting_id)
    except Exception as exc:
        logger.exception("Failed to publish meeting id=%s", meeting_id)
        await meetings_repo.update_meeting_status(meeting_id, "failed")
        raise MeetingStartError(
            "Meeting was saved but could not be queued for processing. Please try again.",
            log_message=str(exc),
        ) from exc

    return meeting
