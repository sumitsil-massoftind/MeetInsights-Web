"""JSON API for projects."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api_response import api_error, api_success
from app.db import meetings as meetings_repo
from app.db import projects as projects_repo
from app.mock_data_service import mock_chat_reply
from app.services.project_service import ProjectError, create_project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["api-projects"])


class CreateProjectBody(BaseModel):
    name: str = ""
    description: str = ""


class ProjectChatBody(BaseModel):
    message: str = Field(..., min_length=1)
    meeting_ids: list[str] = Field(default_factory=list)


@router.post("")
async def api_create_project(request: Request, body: CreateProjectBody):
    """Create a project in MongoDB for the signed-in user."""
    user = getattr(request.state, "user", None)
    if not user:
        return api_error("Please sign in to continue.", status_code=401)

    try:
        project = await create_project(
            user_id=user["_id"],
            name=(body.name or "").strip(),
            description=(body.description or "").strip(),
        )
        return api_success(
            {
                "id": project["id"],
                "name": project["name"],
                "description": project["description"],
                "color": project["color"],
            },
            msg=f'Project "{project["name"]}" created.',
            status_code=201,
        )
    except ProjectError as exc:
        logger.warning("Create project failed: %s", exc.log_message)
        return api_error(exc.public_message, status_code=400)


@router.post("/{project_id}/chat")
async def api_project_chat(request: Request, project_id: str, body: ProjectChatBody):
    """Project multi-meeting chat — JSON in/out (mock reply)."""
    user = getattr(request.state, "user", None)
    if not user:
        return api_error("Please sign in to continue.", status_code=401)

    project = await projects_repo.find_project_by_id(project_id, user_id=user["_id"])
    selected = [mid for mid in body.meeting_ids if mid]
    names = []
    for mid in selected:
        m = await meetings_repo.find_meeting_by_id(mid, user_id=user["_id"])
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
