"""Projects list and project detail pages (HTML only — mutations via /api/* JSON)."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.mock_data_service import get_meetings_for_project, get_project, get_projects

router = APIRouter(tags=["projects"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/projects", response_class=HTMLResponse)
async def projects_list(request: Request):
    return templates.TemplateResponse(
        "projects/index.html",
        {
            "request": request,
            "active_nav": "projects",
            "page_title": "Projects",
            "projects": sorted(get_projects(), key=lambda p: p["last_updated_dt"], reverse=True),
        },
    )


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail(request: Request, project_id: str):
    project = get_project(project_id)
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

    meetings = sorted(
        get_meetings_for_project(project_id),
        key=lambda m: m["date_dt"],
        reverse=True,
    )

    return templates.TemplateResponse(
        "project/detail.html",
        {
            "request": request,
            "active_nav": "projects",
            "page_title": project["name"],
            "project": project,
            "meetings": meetings,
        },
    )
