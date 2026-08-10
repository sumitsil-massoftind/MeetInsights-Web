"""JSON API for projects (mock create + mock chat)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api_response import api_error, api_success
from app.mock_data_service import get_meeting, get_project, mock_chat_reply

router = APIRouter(prefix="/api/projects", tags=["api-projects"])


class CreateProjectBody(BaseModel):
    name: str = ""
    description: str = ""


class ProjectChatBody(BaseModel):
    message: str = Field(..., min_length=1)
    meeting_ids: list[str] = Field(default_factory=list)


@router.post("")
async def api_create_project(request: Request, body: CreateProjectBody):
    """UI mock create project — accepts JSON only; no persistence yet."""
    user = getattr(request.state, "user", None)
    if not user:
        return api_error("Please sign in to continue.", status_code=401)

    name = (body.name or "").strip() or "Untitled"
    return api_success(
        {
            "name": name,
            "description": (body.description or "").strip(),
        },
        msg=f'Project "{name}" would be created (UI mock only).',
        status_code=201,
    )


@router.post("/{project_id}/chat")
async def api_project_chat(project_id: str, body: ProjectChatBody):
    """Mock multi-meeting project chat — JSON in/out only."""
    project = get_project(project_id)
    selected = [mid for mid in body.meeting_ids if mid]
    names = []
    for mid in selected:
        m = get_meeting(mid)
        if m:
            names.append(m["name"])

    base = mock_chat_reply(body.message.strip())
    if names:
        context = (
            f"Based on {len(names)} selected meeting(s) "
            f"({', '.join(names[:3])}{'…' if len(names) > 3 else ''}): "
        )
    else:
        context = f"Based on project “{project['name'] if project else 'this project'}”: "

    return api_success(
        {
            "user_message": body.message.strip(),
            "assistant_message": context + base,
            "project_id": project_id,
            "meeting_ids": selected,
        },
        msg="Success",
    )
