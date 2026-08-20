"""JSON API for projects."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api_response import api_error, api_success
from app.services.project_service import ProjectError, create_project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["api-projects"])


class CreateProjectBody(BaseModel):
    name: str = ""
    description: str = ""


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
