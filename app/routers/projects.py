"""Projects list and project detail pages (HTML — data from MongoDB)."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth.config import get_settings
from app.db import meetings as meetings_repo
from app.db import projects as projects_repo

router = APIRouter(tags=["projects"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/projects", response_class=HTMLResponse)
async def projects_list(request: Request):
    user = request.state.user
    owner = user.get("name") or user.get("email") or ""
    projects = await projects_repo.list_projects_for_user(user["_id"], owner_name=owner)

    return templates.TemplateResponse(
        "projects/index.html",
        {
            "request": request,
            "active_nav": "projects",
            "page_title": "Projects",
            "projects": projects,
        },
    )


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail(request: Request, project_id: str):
    user = request.state.user
    owner = user.get("name") or user.get("email") or ""
    project = await projects_repo.find_project_by_id(project_id, user_id=user["_id"])
    if not project:
        return templates.TemplateResponse(
            "project/not_found.html",
            {
                "request": request,
                "active_nav": "projects",
                "page_title": "Project Not Found",
            },
            status_code=404,
        )

    project["owner"] = owner
    meetings = await meetings_repo.list_meetings_for_user(
        user["_id"],
        project_id=project_id,
    )
    project["meeting_count"] = len(meetings)

    return templates.TemplateResponse(
        "project/detail.html",
        {
            "request": request,
            "active_nav": "projects",
            "page_title": project["name"],
            "project": project,
            "meetings": meetings,
            "meetinsight_socket_url": get_settings().meetinsight_socket_url,
        },
    )
