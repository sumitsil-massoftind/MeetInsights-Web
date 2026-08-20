"""JSON API for meetings."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, Request, UploadFile
from pydantic import BaseModel, Field

from app.api_response import api_error, api_success
from app.db.meetings import PLATFORM_LABELS
from app.queue.rabbitmq import publish_recording_ready
from app.services.meeting_service import MeetingStartError, start_meeting, upload_recording
from app.services.recording_storage import resolve_recording_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/meetings", tags=["api-meetings"])


class CreateMeetingBody(BaseModel):
    platform: str = Field(..., description="google_meet | zoom | teams")
    meeting_url: str = Field(..., min_length=1)
    title: str = ""
    project_id: str | None = None


def _meeting_payload(meeting: dict) -> dict:
    return {
        "id": meeting["id"],
        "platform": meeting.get("platform"),
        "platform_label": meeting.get("platform_label")
        or PLATFORM_LABELS.get(meeting.get("platform") or "", meeting.get("platform")),
        "meeting_url": meeting.get("meeting_url"),
        "title": meeting["title"],
        "status": meeting.get("status_raw") or meeting.get("status"),
        "source": meeting.get("source"),
        "recording_filename": meeting.get("recording_filename"),
        "original_filename": meeting.get("original_filename"),
        "project_id": meeting.get("project_id"),
        "project_name": meeting.get("project_name"),
    }


@router.post("")
async def api_create_meeting(request: Request, body: CreateMeetingBody):
    """
    Store meeting details in MongoDB (optional project_id) and enqueue on RabbitMQ.

    Content-Type: application/json
    """
    user = getattr(request.state, "user", None)
    if not user:
        return api_error("Please sign in to continue.", status_code=401)

    try:
        meeting = await start_meeting(
            user_id=user["_id"],
            platform=body.platform.strip(),
            meeting_url=str(body.meeting_url).strip(),
            title=(body.title or "").strip(),
            project_id=(body.project_id or None),
        )
        return api_success(
            _meeting_payload(meeting),
            msg="Bot invited to join the meeting.",
            status_code=201,
        )
    except MeetingStartError as exc:
        logger.warning("API start meeting failed: %s", exc.log_message)
        return api_error(exc.public_message, status_code=400)


@router.post("/upload")
async def api_upload_meeting(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(""),
    platform: str = Form(""),
    project_id: str = Form(""),
):
    """
    Upload a previously recorded meeting video.

    Stores the file in RECORDINGS_DIR, inserts a MongoDB meeting, and publishes
    {"id": "<meeting_id>"} to the MeetInsight recordings queue.

    Content-Type: multipart/form-data
    """
    user = getattr(request.state, "user", None)
    if not user:
        return api_error("Please sign in to continue.", status_code=401)

    try:
        meeting = await upload_recording(
            user_id=user["_id"],
            upload=file,
            title=(title or "").strip(),
            platform=(platform or "").strip() or None,
            project_id=(project_id or "").strip() or None,
        )
        return api_success(
            _meeting_payload(meeting),
            msg="Recording uploaded and queued for processing.",
            status_code=201,
        )
    except MeetingStartError as exc:
        logger.warning("API upload meeting failed: %s", exc.log_message)
        return api_error(exc.public_message, status_code=400)


class AssignProjectBody(BaseModel):
    project_id: str | None = None


@router.post("/{meeting_id}/regenerate-transcript")
async def api_regenerate_transcript(request: Request, meeting_id: str):
    """Queue an existing recording for transcription again."""
    from app.db import meetings as meetings_repo

    user = getattr(request.state, "user", None)
    if not user:
        return api_error("Please sign in to continue.", status_code=401)

    meeting = await meetings_repo.find_meeting_by_id(meeting_id, user_id=user["_id"])
    if not meeting:
        return api_error("Meeting not found.", status_code=404)
    if not resolve_recording_path(meeting.get("recording_filename")):
        return api_error("The meeting recording is not available.", status_code=404)
    if meeting.get("status_raw") in {"queued", "processing"}:
        return api_error("Transcription is already queued or processing.", status_code=409)

    await meetings_repo.update_meeting_status(meeting_id, "queued")
    try:
        await publish_recording_ready(meeting_id)
    except Exception:
        logger.exception("Failed to regenerate transcript for meeting=%s", meeting_id)
        await meetings_repo.update_meeting_status(meeting_id, "failed")
        return api_error(
            "Unable to queue the recording for transcription. Please try again.",
            status_code=503,
        )

    return api_success(
        {
            "id": meeting_id,
            "status": "queued",
        },
        msg="Recording queued to regenerate the transcript.",
    )


@router.post("/{meeting_id}/project")
async def api_assign_meeting_project(
    request: Request,
    meeting_id: str,
    body: AssignProjectBody,
):
    """Assign or unassign a meeting to a project (JSON only)."""
    from app.db import meetings as meetings_repo

    user = getattr(request.state, "user", None)
    if not user:
        return api_error("Please sign in to continue.", status_code=401)

    try:
        meeting = await meetings_repo.update_meeting_project(
            meeting_id=meeting_id,
            user_id=user["_id"],
            project_id=body.project_id or None,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "not_found":
            return api_error("Meeting not found.", status_code=404)
        if code == "invalid_project":
            return api_error("Please choose a valid project.", status_code=400)
        return api_error("Unable to update project assignment.", status_code=400)
    except Exception:
        logger.exception("Failed to assign project for meeting=%s", meeting_id)
        return api_error("Unable to update project assignment.", status_code=500)

    project_name = meeting.get("project_name")
    if meeting.get("project_id"):
        msg = f'Meeting added to project "{project_name}".'
    else:
        msg = "Meeting removed from project."

    return api_success(
        {
            "id": meeting["id"],
            "title": meeting.get("title") or meeting.get("name"),
            "project_id": meeting.get("project_id"),
            "project_name": project_name if meeting.get("project_id") else None,
        },
        msg=msg,
    )
