"""Dashboard page."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.mock_data_service import (
    get_recent_meetings,
    get_recent_projects,
    get_stats,
)

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "active_nav": "dashboard",
            "page_title": "Dashboard",
            "stats": get_stats(),
            "recent_meetings": get_recent_meetings(5),
            "recent_projects": get_recent_projects(4),
        },
    )
