"""Meetings list and meeting detail pages."""

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.mock_data_service import get_meeting, get_meetings, mock_chat_reply

router = APIRouter(tags=["meetings"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/meetings", response_class=HTMLResponse)
async def meetings_list(request: Request, page: int = 1, status: str = ""):
    all_meetings = sorted(get_meetings(), key=lambda m: m["date_dt"], reverse=True)
    if status:
        all_meetings = [m for m in all_meetings if m["status"].lower() == status.lower()]

    per_page = 10
    total = len(all_meetings)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    page_items = all_meetings[start : start + per_page]

    return templates.TemplateResponse(
        "meetings/index.html",
        {
            "request": request,
            "active_nav": "meetings",
            "page_title": "Meetings",
            "meetings": page_items,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "status_filter": status,
        },
    )


@router.get("/meetings/{meeting_id}", response_class=HTMLResponse)
async def meeting_detail(request: Request, meeting_id: str):
    meeting = get_meeting(meeting_id)
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

    return templates.TemplateResponse(
        "meeting/detail.html",
        {
            "request": request,
            "active_nav": "meetings",
            "page_title": meeting["name"],
            "meeting": meeting,
        },
    )


@router.post("/meetings/{meeting_id}/chat", response_class=HTMLResponse)
async def meeting_chat(
    request: Request,
    meeting_id: str,
    message: str = Form(...),
):
    """Return HTMX partial with user + assistant chat bubbles (mock only)."""
    meeting = get_meeting(meeting_id)
    reply = mock_chat_reply(message)
    return templates.TemplateResponse(
        "components/chat_exchange.html",
        {
            "request": request,
            "user_message": message,
            "assistant_message": reply,
            "meeting_name": meeting["name"] if meeting else "this meeting",
        },
    )
