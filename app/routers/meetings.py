"""Meetings list and meeting detail pages (HTML — data from MongoDB)."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.auth.config import get_settings
from app.db import meetings as meetings_repo
from app.db import projects as projects_repo
from app.services.recording_storage import human_file_size, resolve_recording_path

router = APIRouter(tags=["meetings"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")

RECORDING_MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
}


@router.get("/meetings", response_class=HTMLResponse)
async def meetings_list(request: Request, page: int = 1, status: str = "", q: str = ""):
    user = request.state.user
    user_id = user["_id"]
    search_query = (q or "").strip()[:80]
    per_page = 10
    total = await meetings_repo.count_meetings_for_user(
        user_id,
        status=status or None,
        q=search_query or None,
    )
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    skip = (page - 1) * per_page

    page_items = await meetings_repo.list_meetings_for_user(
        user_id,
        status=status or None,
        q=search_query or None,
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
            "search_query": search_query,
            "max_upload_bytes": get_settings().max_upload_bytes,
        },
    )


@router.get("/meetings/shared/{token}")
async def claim_shared_meeting(request: Request, token: str):
    """Copy the shared meeting into this user's workspace, then open it."""
    user = request.state.user
    try:
        meeting, reason = await meetings_repo.claim_shared_meeting(
            token=token,
            user_id=user["_id"],
        )
    except ValueError:
        return templates.TemplateResponse(
            "meeting/not_found.html",
            {
                "request": request,
                "active_nav": "meetings",
                "page_title": "Share link not found",
            },
            status_code=404,
        )

    suffix = "?shared=1" if reason == "created" else ""
    return RedirectResponse(url=f"/meetings/{meeting['id']}{suffix}", status_code=303)


@router.get("/meetings/{meeting_id}/recording")
async def meeting_recording(request: Request, meeting_id: str, download: bool = False):
    """Stream a recording owned by the signed-in user for playback or download."""
    user = request.state.user
    meeting = await meetings_repo.find_meeting_by_id(meeting_id, user_id=user["_id"])
    if not meeting:
        return Response(status_code=404)

    recording_path = resolve_recording_path(meeting.get("recording_filename"))
    if not recording_path:
        return Response(status_code=404)

    # Only the server-generated filename is echoed back, so the header stays safe.
    disposition = f'attachment; filename="{recording_path.name}"' if download else "inline"

    return FileResponse(
        recording_path,
        media_type=RECORDING_MEDIA_TYPES.get(recording_path.suffix.lower(), "application/octet-stream"),
        headers={
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
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

    meeting["recording_available"] = bool(
        resolve_recording_path(meeting.get("recording_filename"))
    )
    meeting["recording_size_label"] = human_file_size(meeting.get("file_size_bytes"))
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
            "meetinsight_socket_url": get_settings().meetinsight_socket_url,
        },
    )
