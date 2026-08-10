"""Project business flow."""

from __future__ import annotations

import logging
from typing import Any

from app.db import projects as projects_repo

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
