"""Authentication routes — Google Sign-In + session cookies."""

from __future__ import annotations

import logging
import secrets
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api_response import api_error, api_success
from app.auth.config import get_settings
from app.auth.errors import public_auth_error
from app.auth.next_url import safe_internal_next
from app.auth.service import (
    AuthError,
    exchange_google_code,
    google_authorize_url,
    login_with_google_profile,
    logout_request,
    refresh_bearer_token,
    set_bearer_handoff_cookie,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")

OAUTH_STATE_COOKIE = "mi_oauth_state"
AUTH_NEXT_COOKIE = "mi_auth_next"


def _set_next_cookie(response: RedirectResponse, next_url: str | None) -> None:
    settings = get_settings()
    if next_url:
        response.set_cookie(
            AUTH_NEXT_COOKIE,
            next_url,
            max_age=600,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            path="/",
        )
        return
    response.delete_cookie(AUTH_NEXT_COOKIE, path="/")


def _login_error_redirect(code: str) -> RedirectResponse:
    return RedirectResponse(url="/login?error=" + quote_plus(code), status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login(request: Request, error: str = "", next: str = ""):
    settings = get_settings()
    next_url = safe_internal_next(next) or ""
    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "page_title": "Sign in",
            # Never render raw query strings — only mapped safe copy
            "error": public_auth_error(error),
            "google_configured": settings.google_configured,
            "next": next_url,
        },
    )


@router.get("/auth/google")
async def auth_google_start(request: Request, next: str = ""):
    settings = get_settings()
    if not settings.google_configured:
        logger.error("Google OAuth credentials are missing; refusing sign-in start")
        return _login_error_redirect("sign_in_unavailable")

    state = secrets.token_urlsafe(24)
    response = RedirectResponse(url=google_authorize_url(state), status_code=302)
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    _set_next_cookie(response, safe_internal_next(next) or safe_internal_next(request.cookies.get(AUTH_NEXT_COOKIE)))
    return response


@router.get("/auth/google/callback")
async def auth_google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    # Google may return error=access_denied, etc. — never echo that to the UI
    if error:
        logger.info("Google OAuth cancelled or denied: %s", error)
        if error in {"access_denied", "user_cancelled"}:
            return _login_error_redirect("sign_in_cancelled")
        return _login_error_redirect("sign_in_failed")

    if not code:
        logger.warning("OAuth callback missing authorization code")
        return _login_error_redirect("sign_in_failed")

    cookie_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if not state or not cookie_state or state != cookie_state:
        logger.warning("OAuth state mismatch")
        return _login_error_redirect("sign_in_failed")

    try:
        profile = await exchange_google_code(code)
        next_url = safe_internal_next(request.cookies.get(AUTH_NEXT_COOKIE)) or "/dashboard"
        response = RedirectResponse(url=next_url, status_code=303)
        await login_with_google_profile(profile, response)
        response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
        response.delete_cookie(AUTH_NEXT_COOKIE, path="/")
        return response
    except AuthError as exc:
        logger.warning("AuthError during Google login: %s", exc.message)
        return _login_error_redirect(exc.public_code)
    except Exception:
        logger.exception("Unexpected error during Google login")
        return _login_error_redirect("sign_in_failed")


@router.get("/logout")
@router.post("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=303)
    await logout_request(request, response)
    return response


@router.post("/api/auth/refresh")
async def api_refresh_token(request: Request):
    """
    Refresh is authenticated by the HttpOnly session cookie.
    All other /api/* routes require a verified Bearer access token.
    """
    refreshed = await refresh_bearer_token(request)
    if not refreshed:
        return api_error("Session expired. Please sign in again.", status_code=401)

    _user, tokens = refreshed
    response = api_success(
        {
            "access_token": tokens.access_token,
            "token_type": "Bearer",
            "access_token_expired": tokens.access_token_expired,
        },
        msg="Token refreshed successfully.",
    )
    set_bearer_handoff_cookie(response, tokens.access_token)
    return response
