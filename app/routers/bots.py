"""Bots page — live free/in-use status from MeetRecorder."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api_response import api_success
from app.services.bot_status_service import fetch_bot_status

router = APIRouter(tags=["bots"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/bots", response_class=HTMLResponse)
async def bots_page(request: Request):
    status = await fetch_bot_status()
    return templates.TemplateResponse(
        "bots/index.html",
        {
            "request": request,
            "active_nav": "bots",
            "page_title": "Bots",
            "bot_status": status,
        },
    )


@router.get("/api/bots")
async def bots_api():
    status = await fetch_bot_status()
    return api_success(status)
