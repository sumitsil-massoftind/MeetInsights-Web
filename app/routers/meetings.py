"""Meetings list and meeting detail pages (HTML — data from MongoDB)."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.db import meetings as meetings_repo
from app.db import projects as projects_repo

router = APIRouter(tags=["meetings"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/meetings", response_class=HTMLResponse)
async def meetings_list(request: Request, page: int = 1, status: str = ""):
    user = request.state.user
    user_id = user["_id"]
    per_page = 10
    total = await meetings_repo.count_meetings_for_user(user_id, status=status or None)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    skip = (page - 1) * per_page

    page_items = await meetings_repo.list_meetings_for_user(
        user_id,
        status=status or None,
        limit=per_page,
        skip=skip,
    )
    join_projects = await projects_repo.list_projects_for_user(
        user_id,
        owner_name=user.get("name") or "",
    )

    return templates.TemplateResponse(
        "meetings/index.html",
        {
            "request": request,
            "active_nav": "meetings",
            "page_title": "Meetings",
            "meetings": page_items,
            "join_projects": join_projects,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "status_filter": status,
        },
    )


@router.get("/meetings/{meeting_id}", response_class=HTMLResponse)
async def meeting_detail(request: Request, meeting_id: str):
    user = request.state.user
    meeting = await meetings_repo.find_meeting_by_id(meeting_id, user_id=user["_id"])
    if not meeting:
        return templates.TemplateResponse(
            "meeting/not_found.html",
            {
                "request": request,
                "active_nav": "meetings",
                "page_title": "Meeting Not Found",
            },
            status_code=404,
        )

    join_projects = await projects_repo.list_projects_for_user(
        user["_id"],
        owner_name=user.get("name") or "",
    )

    return templates.TemplateResponse(
        "meeting/detail.html",
        {
            "request": request,
            "active_nav": "meetings",
            "page_title": meeting["name"],
            "meeting": meeting,
            "join_projects": join_projects,
        },
    )
