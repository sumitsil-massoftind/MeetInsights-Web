"""Google OAuth + session establishment service."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import Request, Response

from app.auth.config import Settings, get_settings
from app.auth.jwt_helper import JWTHelper, generate_session_refresh_token
from app.db import sessions as session_repo
from app.db import users as user_repo


class AuthError(Exception):
    """Internal auth failure with a public UI error code (never raw tech details)."""

    def __init__(self, message: str, public_code: str = "sign_in_failed") -> None:
        self.message = message  # for logs only
        self.public_code = public_code
        super().__init__(message)


def google_authorize_url(state: str) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": settings.google_scopes,
        "access_type": "online",
        "include_granted_scopes": "true",
        "prompt": "select_account",
        "state": state,
    }
    return f"{settings.google_auth_url}?{urlencode(params)}"


async def exchange_google_code(code: str) -> dict[str, Any]:
    """Exchange authorization code for tokens and fetch Google userinfo."""
    settings = get_settings()
    if not settings.google_configured:
        raise AuthError(
            "Google OAuth credentials missing",
            public_code="sign_in_unavailable",
        )

    async with httpx.AsyncClient(timeout=20.0) as client:
        token_resp = await client.post(
            settings.google_token_url,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code >= 400:
            raise AuthError(
                f"Google token exchange failed: {token_resp.status_code}",
                public_code="sign_in_failed",
            )

        token_data = token_resp.json()
        access = token_data.get("access_token")
        if not access:
            raise AuthError("Google response missing access_token", public_code="sign_in_failed")

        info_resp = await client.get(
            settings.google_userinfo_url,
            headers={"Authorization": f"Bearer {access}"},
        )
        if info_resp.status_code >= 400:
            raise AuthError(
                f"Google userinfo failed: {info_resp.status_code}",
                public_code="sign_in_failed",
            )

        profile = info_resp.json()
        email = (profile.get("email") or "").strip()
        if not email:
            raise AuthError("Google profile missing email", public_code="account_issue")
        if profile.get("email_verified") is False:
            raise AuthError("Google email not verified", public_code="account_issue")

        return {
            "email": email,
            "name": (profile.get("name") or profile.get("given_name") or email).strip(),
            "google_sub": profile.get("sub"),
            "picture": profile.get("picture"),
        }


async def login_with_google_profile(profile: dict[str, Any], response: Response) -> dict[str, Any]:
    """Upsert user, create session + tokens, set cookies."""
    user = await user_repo.upsert_google_user(
        email=profile["email"],
        name=profile["name"],
        google_sub=profile.get("google_sub"),
    )
    if not user:
        raise AuthError("User upsert returned empty", public_code="sign_in_failed")

    # Opaque session refresh token stored in MongoDB (user_sessions schema)
    session_refresh = generate_session_refresh_token()
    await session_repo.create_session(user_id=user["_id"], refresh_token=session_refresh)

    # Encrypted JWT pair (src jwt_helper pattern) used as browser access credential
    jwt_helper = JWTHelper()
    tokens = jwt_helper.create_token(
        {
            "param": {
                "user_id": user["_id"],
                "email": user["email"],
                "name": user["name"],
            }
        }
    )

    set_auth_cookies(
        response,
        access_token=tokens.access_token,
        session_refresh_token=session_refresh,
        access_max_age=tokens.access_token_expired - int(time.time()),
        refresh_max_age=tokens.refresh_token_expired - int(time.time()),
    )
    return user


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    session_refresh_token: str,
    access_max_age: int,
    refresh_max_age: int,
) -> None:
    settings = get_settings()
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "path": "/",
    }
    response.set_cookie(
        settings.access_cookie_name,
        access_token,
        max_age=max(60, access_max_age),
        **common,
    )
    response.set_cookie(
        settings.refresh_cookie_name,
        session_refresh_token,
        max_age=max(60, refresh_max_age),
        **common,
    )


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.access_cookie_name, path="/")
    response.delete_cookie(settings.refresh_cookie_name, path="/")


async def resolve_user_from_request(request: Request) -> dict[str, Any] | None:
    """
    Resolve the current user from cookies.

    1. Verify encrypted access JWT
    2. Else validate opaque refresh session in MongoDB and issue a new access JWT
    """
    settings = get_settings()
    jwt_helper = JWTHelper(settings)
    access = request.cookies.get(settings.access_cookie_name)
    refresh = request.cookies.get(settings.refresh_cookie_name)

    if access:
        try:
            payload = jwt_helper.verify_access_token(access)
            param = payload.get("param") or payload
            user_id = param.get("user_id")
            if user_id is not None:
                user = await user_repo.find_user_by_id(str(user_id))
                if user:
                    return user
        except Exception:
            pass

    if not refresh:
        return None

    session = await session_repo.find_valid_session(refresh)
    if not session:
        return None

    user = await user_repo.find_user_by_id(session["user_id"])
    if not user:
        return None

    # Attach flag so middleware can re-issue access cookie
    user = dict(user)
    user["_reissue_access"] = True
    return user


async def reissue_access_cookie(user: dict[str, Any], response: Response) -> None:
    jwt_helper = JWTHelper()
    tokens = jwt_helper.create_token(
        {
            "param": {
                "user_id": user["_id"],
                "email": user["email"],
                "name": user["name"],
            }
        }
    )
    settings = get_settings()
    response.set_cookie(
        settings.access_cookie_name,
        tokens.access_token,
        max_age=Settings.parse_ttl_seconds(settings.jwt_expires),
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


async def logout_request(request: Request, response: Response) -> None:
    settings = get_settings()
    refresh = request.cookies.get(settings.refresh_cookie_name)
    if refresh:
        await session_repo.revoke_session(refresh)
    clear_auth_cookies(response)


def user_initials(name: str | None, email: str | None = None) -> str:
    source = (name or email or "U").strip()
    parts = source.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return source[:2].upper()
