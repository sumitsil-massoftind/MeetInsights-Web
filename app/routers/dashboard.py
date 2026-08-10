"""Dashboard page (MongoDB-backed stats and recent items)."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.db import meetings as meetings_repo
from app.db import projects as projects_repo

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = request.state.user
    user_id = user["_id"]
    owner = user.get("name") or user.get("email") or ""

    mstats = await meetings_repo.meeting_stats_for_user(user_id)
    total_projects = await projects_repo.count_projects_for_user(user_id)

    stats = {
        "total_meetings": mstats["total_meetings"],
        "total_projects": total_projects,
        "processing": mstats["processing"],
        "completed": mstats["completed"],
        "recording": mstats["recording"],
    }

    recent_meetings = await meetings_repo.list_meetings_for_user(user_id, limit=5)
    recent_projects = await projects_repo.list_projects_for_user(
        user_id,
        limit=4,
        owner_name=owner,
    )
    join_projects = await projects_repo.list_projects_for_user(user_id, owner_name=owner)

    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "active_nav": "dashboard",
            "page_title": "Dashboard",
            "stats": stats,
            "recent_meetings": recent_meetings,
            "recent_projects": recent_projects,
            "join_projects": join_projects,
        },
    )
