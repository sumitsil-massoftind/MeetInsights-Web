"""JSON API for meetings."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api_response import api_error, api_success
from app.db.meetings import PLATFORM_LABELS
from app.mock_data_service import mock_chat_reply
from app.services.meeting_service import MeetingStartError, start_meeting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/meetings", tags=["api-meetings"])


class CreateMeetingBody(BaseModel):
    platform: str = Field(..., description="google_meet | zoom | teams")
    meeting_url: str = Field(..., min_length=1)
    title: str = ""
    project_id: str | None = None


class ChatBody(BaseModel):
    message: str = Field(..., min_length=1)


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
            {
                "id": meeting["id"],
                "platform": meeting["platform"],
                "platform_label": meeting.get("platform_label")
                or PLATFORM_LABELS.get(meeting["platform"], meeting["platform"]),
                "meeting_url": meeting["meeting_url"],
                "title": meeting["title"],
                "status": meeting.get("status_raw") or meeting.get("status"),
                "project_id": meeting.get("project_id"),
                "project_name": meeting.get("project_name"),
            },
            msg="Bot invited to join the meeting.",
            status_code=201,
        )
    except MeetingStartError as exc:
        logger.warning("API start meeting failed: %s", exc.log_message)
        return api_error(exc.public_message, status_code=400)


class AssignProjectBody(BaseModel):
    project_id: str | None = None


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


@router.post("/{meeting_id}/chat")
async def api_meeting_chat(request: Request, meeting_id: str, body: ChatBody):
    """Meeting chat — JSON in/out (mock reply for now)."""
    from app.db import meetings as meetings_repo

    user = getattr(request.state, "user", None)
    if not user:
        return api_error("Please sign in to continue.", status_code=401)

    meeting = await meetings_repo.find_meeting_by_id(meeting_id, user_id=user["_id"])
    reply = mock_chat_reply(body.message.strip())
    return api_success(
        {
            "user_message": body.message.strip(),
            "assistant_message": reply,
            "meeting_id": meeting_id,
            "meeting_name": meeting["name"] if meeting else "this meeting",
        },
        msg="Success",
    )
