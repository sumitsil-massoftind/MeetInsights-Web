"""Start-meeting and upload-recording business flows: persist then enqueue."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import UploadFile

from app.db import meetings as meetings_repo
from app.queue.rabbitmq import publish_meeting_id, publish_recording_ready
from app.services.recording_storage import (
    RecordingStorageError,
    delete_meeting_recordings,
    delete_recording,
    save_uploaded_recording,
)

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


async def upload_recording(
    *,
    user_id: str,
    upload: UploadFile,
    title: str = "",
    platform: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    """
    Store a video in the shared recordings folder, create a meeting, and
    publish to the MeetInsight processing queue.
    """
    stored: dict[str, str | int] | None = None
    try:
        stored = await save_uploaded_recording(upload)
    except RecordingStorageError as exc:
        raise MeetingStartError(exc.public_message, log_message=exc.code) from exc
    except Exception as exc:
        logger.exception("Unexpected upload storage error for user=%s", user_id)
        raise MeetingStartError("Unable to store the recording. Please try again.") from exc

    try:
        meeting = await meetings_repo.create_uploaded_meeting(
            user_id=user_id,
            title=title,
            platform=platform or None,
            project_id=project_id or None,
            recording_filename=str(stored["recording_filename"]),
            recording_path=str(stored["recording_path"]),
            original_filename=str(stored["original_filename"]),
            file_size_bytes=int(stored["file_size_bytes"]),
        )
    except ValueError as exc:
        delete_recording(stored.get("recording_path") if stored else None)
        code = str(exc)
        if code == "invalid_platform":
            raise MeetingStartError("Please choose a valid meeting platform.") from exc
        if code == "invalid_project":
            raise MeetingStartError("Please choose a valid project.") from exc
        raise MeetingStartError("Unable to save the uploaded meeting. Please try again.") from exc
    except Exception as exc:
        delete_recording(stored.get("recording_path") if stored else None)
        logger.exception("Failed to insert uploaded meeting for user=%s", user_id)
        raise MeetingStartError("Unable to save the uploaded meeting. Please try again.") from exc

    meeting_id = meeting["id"]
    try:
        await publish_recording_ready(meeting_id)
    except Exception as exc:
        logger.exception("Failed to publish uploaded meeting id=%s", meeting_id)
        await meetings_repo.update_meeting_status(meeting_id, "failed")
        raise MeetingStartError(
            "Recording was saved but could not be queued for processing. Please try again.",
            log_message=str(exc),
        ) from exc

    return meeting


async def delete_user_meeting(*, user_id: str, meeting_id: str) -> dict[str, Any]:
    deleted = await meetings_repo.pop_meeting_for_user(meeting_id=meeting_id, user_id=user_id)
    if not deleted:
        raise MeetingStartError("Meeting not found.")

    filename = deleted.get("recording_filename")
    remaining = await meetings_repo.count_recording_refs(filename)
    if remaining == 0:
        delete_meeting_recordings(filename, deleted.get("recording_path"))

    title = deleted.get("title") or "Untitled meeting"
    return {"id": str(deleted["_id"]), "title": title}
