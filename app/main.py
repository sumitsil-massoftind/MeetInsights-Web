"""Meet Insights — FastAPI web UI with Google Sign-In."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth.config import get_settings
from app.auth.service import reissue_access_cookie, resolve_user_from_request, user_initials
from app.db.mongodb import close_client, ensure_indexes
from app.routers import auth, dashboard, meetings, projects, settings as settings_router

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
_settings = get_settings()

PUBLIC_PATH_PREFIXES = (
    "/login",
    "/auth/",
    "/logout",
    "/static/",
    "/health",
    "/favicon.ico",
)

if _settings.debug:
    PUBLIC_PATH_PREFIXES = PUBLIC_PATH_PREFIXES + ("/docs", "/openapi.json", "/redoc")


def _is_public_path(path: str) -> bool:
    if path == "/":
        return True
    return any(path == p.rstrip("/") or path.startswith(p) for p in PUBLIC_PATH_PREFIXES)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        await ensure_indexes()
    except Exception:
        logger.exception("Failed to ensure MongoDB indexes on startup")
    yield
    await close_client()


app = FastAPI(
    title="Meet Insights",
    description="AI Meeting Intelligence Platform",
    version="1.1.0",
    lifespan=lifespan,
    # Hide OpenAPI UI unless DEBUG — avoids leaking API surface
    docs_url="/docs" if _settings.debug else None,
    redoc_url="/redoc" if _settings.debug else None,
    openapi_url="/openapi.json" if _settings.debug else None,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(meetings.router)
app.include_router(projects.router)
app.include_router(settings_router.router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Return friendly messages; never echo internal detail into UI HTML."""
    accepts = request.headers.get("accept", "")
    if "text/html" in accepts:
        if exc.status_code in {401, 403}:
            return RedirectResponse(url="/login?error=session_expired", status_code=302)
        if exc.status_code == 404:
            return RedirectResponse(url="/dashboard" if getattr(request.state, "user", None) else "/login", status_code=302)
        return RedirectResponse(url="/login?error=sign_in_failed", status_code=302)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": "Request could not be completed."},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
    accepts = request.headers.get("accept", "")
    if "text/html" in accepts:
        return RedirectResponse(url="/login?error=sign_in_failed", status_code=302)
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    accepts = request.headers.get("accept", "")
    if "text/html" in accepts:
        # Prefer login for safety; dashboard if somehow authenticated
        if getattr(request.state, "user", None):
            return RedirectResponse(url="/dashboard", status_code=302)
        return RedirectResponse(url="/login?error=sign_in_failed", status_code=302)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Please try again later."},
    )


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    request.state.user = None
    request.state.user_initials = "U"

    if _is_public_path(path):
        if path.startswith("/login"):
            user = await resolve_user_from_request(request)
            if user:
                return RedirectResponse(url="/dashboard", status_code=302)
        return await call_next(request)

    user = await resolve_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    reissue = user.pop("_reissue_access", False)
    request.state.user = user
    request.state.user_initials = user_initials(user.get("name"), user.get("email"))

    response = await call_next(request)
    if reissue:
        await reissue_access_cookie(user, response)
    return response


@app.get("/")
async def root(request: Request):
    user = await resolve_user_from_request(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/health")
async def health():
    return {"status": "ok"}
