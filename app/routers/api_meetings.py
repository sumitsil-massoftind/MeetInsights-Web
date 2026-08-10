"""JSON API for meetings."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api_response import api_error, api_success
from app.db.meetings import PLATFORM_LABELS
from app.mock_data_service import get_meeting, mock_chat_reply
from app.services.meeting_service import MeetingStartError, start_meeting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/meetings", tags=["api-meetings"])


class CreateMeetingBody(BaseModel):
    platform: str = Field(..., description="google_meet | zoom | teams")
    meeting_url: str = Field(..., min_length=1)
    title: str = ""


class ChatBody(BaseModel):
    message: str = Field(..., min_length=1)


@router.post("")
async def api_create_meeting(request: Request, body: CreateMeetingBody):
    """
    Store meeting details in MongoDB and enqueue the meeting id on RabbitMQ.

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
        )
        return api_success(
            {
                "id": meeting["id"],
                "platform": meeting["platform"],
                "platform_label": meeting.get("platform_label")
                or PLATFORM_LABELS.get(meeting["platform"], meeting["platform"]),
                "meeting_url": meeting["meeting_url"],
                "title": meeting["title"],
                "status": meeting["status"],
            },
            msg="Meeting started and queued for processing.",
            status_code=201,
        )
    except MeetingStartError as exc:
        logger.warning("API start meeting failed: %s", exc.log_message)
        return api_error(exc.public_message, status_code=400)


@router.post("/{meeting_id}/chat")
async def api_meeting_chat(meeting_id: str, body: ChatBody):
    """Mock meeting chat — JSON in/out only."""
    meeting = get_meeting(meeting_id)
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
