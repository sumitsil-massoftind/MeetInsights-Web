"""Projects list and project detail pages."""

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.mock_data_service import (
    get_meeting,
    get_meetings_for_project,
    get_project,
    get_projects,
    mock_chat_reply,
)

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


@router.post("/projects/create", response_class=HTMLResponse)
async def create_project_mock(request: Request, name: str = Form(""), description: str = Form("")):
    """UI-only create project dialog handler — returns toast partial, no persistence."""
    return templates.TemplateResponse(
        "components/toast.html",
        {
            "request": request,
            "message": f'Project "{name or "Untitled"}" would be created (UI mock only).',
            "toast_type": "info",
        },
    )


@router.post("/projects/{project_id}/chat", response_class=HTMLResponse)
async def project_chat(
    request: Request,
    project_id: str,
    message: str = Form(...),
    meeting_ids: str = Form(""),
):
    """Mock multi-meeting chat from project detail."""
    project = get_project(project_id)
    selected = [mid for mid in meeting_ids.split(",") if mid]
    names = []
    for mid in selected:
        m = get_meeting(mid)
        if m:
            names.append(m["name"])

    base = mock_chat_reply(message)
    if names:
        context = f"Based on {len(names)} selected meeting(s) ({', '.join(names[:3])}{'…' if len(names) > 3 else ''}): "
    else:
        context = f"Based on project “{project['name'] if project else 'this project'}”: "

    return templates.TemplateResponse(
        "components/chat_exchange.html",
        {
            "request": request,
            "user_message": message,
            "assistant_message": context + base,
            "meeting_name": project["name"] if project else "project",
        },
    )
