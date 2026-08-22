"""Project business flow."""

from __future__ import annotations

import logging
from typing import Any

from app.db import meetings as meetings_repo
from app.db import projects as projects_repo
from app.services.meeting_service import delete_user_meeting

logger = logging.getLogger(__name__)


class ProjectError(Exception):
    def __init__(self, public_message: str, *, log_message: str = "") -> None:
        self.public_message = public_message
        self.log_message = log_message or public_message
        super().__init__(self.log_message)


async def create_project(
    *,
    user_id: str,
    name: str,
    description: str = "",
) -> dict[str, Any]:
    try:
        return await projects_repo.create_project(
            user_id=user_id,
            name=name,
            description=description,
        )
    except ValueError as exc:
        if str(exc) == "missing_name":
            raise ProjectError("Please enter a project name.") from exc
        raise ProjectError("Unable to create project. Please try again.") from exc
    except Exception as exc:
        logger.exception("Failed to create project for user=%s", user_id)
        raise ProjectError("Unable to create project. Please try again.") from exc


async def delete_user_project(
    *,
    user_id: str,
    project_id: str,
    delete_meetings: bool = False,
) -> dict[str, Any]:
    project = await projects_repo.find_project_by_id(project_id, user_id=user_id)
    if not project:
        raise ProjectError("Project not found.")

    meeting_docs = await meetings_repo.list_project_meeting_docs(
        user_id=user_id,
        project_id=project_id,
    )
    removed_meetings = 0
    kept_meetings = 0

    if delete_meetings:
        for doc in meeting_docs:
            try:
                await delete_user_meeting(user_id=user_id, meeting_id=str(doc["_id"]))
                removed_meetings += 1
            except Exception:
                logger.exception(
                    "Failed to delete meeting=%s while removing project=%s",
                    doc.get("_id"),
                    project_id,
                )
                raise ProjectError("Unable to delete the project meetings. Please try again.")
    else:
        kept_meetings = await meetings_repo.unassign_project_meetings(
            user_id=user_id,
            project_id=project_id,
        )

    removed = await projects_repo.delete_project_for_user(
        project_id=project_id,
        user_id=user_id,
    )
    if not removed:
        raise ProjectError("Project not found.")

    return {
        "id": project["id"],
        "name": project["name"],
        "deleted_meetings": removed_meetings,
        "kept_meetings": kept_meetings,
    }
