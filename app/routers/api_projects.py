"""JSON API for projects."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api_response import api_error, api_success
from app.services.project_service import ProjectError, create_project, delete_user_project

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


@router.delete("/{project_id}")
async def api_delete_project(
    request: Request,
    project_id: str,
    delete_meetings: bool = False,
):
    """
    Delete a project the signed-in user owns.

    delete_meetings=false (default) unassigns meetings.
    delete_meetings=true also deletes those meetings and their recordings.
    """
    user = getattr(request.state, "user", None)
    if not user:
        return api_error("Please sign in to continue.", status_code=401)

    try:
        result = await delete_user_project(
            user_id=str(user["_id"]),
            project_id=project_id,
            delete_meetings=delete_meetings,
        )
    except ProjectError as exc:
        status = 404 if "not found" in exc.public_message.lower() else 400
        return api_error(exc.public_message, status_code=status)
    except Exception:
        logger.exception("Failed to delete project=%s", project_id)
        return api_error("Unable to delete the project. Please try again.", status_code=500)

    if delete_meetings:
        count = result["deleted_meetings"]
        msg = (
            f'Project “{result["name"]}” and {count} meeting{"s" if count != 1 else ""} were deleted.'
            if count
            else f'Project “{result["name"]}” was deleted.'
        )
    else:
        kept = result["kept_meetings"]
        msg = (
            f'Project “{result["name"]}” was deleted. {kept} meeting{"s" if kept != 1 else ""} stayed in your library.'
            if kept
            else f'Project “{result["name"]}” was deleted.'
        )
    return api_success(result, msg=msg)
