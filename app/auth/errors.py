"""User-safe auth error codes for the UI.

Never expose env vars, internal OAuth details, DB messages, or stack traces.
"""

from __future__ import annotations

# query param ?error=<code>
AUTH_ERROR_MESSAGES: dict[str, str] = {
    "sign_in_unavailable": "Sign-in is temporarily unavailable. Please try again later.",
    "sign_in_failed": "We couldn’t sign you in. Please try again.",
    "sign_in_cancelled": "Sign-in was cancelled. You can try again when you’re ready.",
    "session_expired": "Your session expired. Please sign in again.",
    "account_issue": "There was a problem with your account. Please try again or contact support.",
}

DEFAULT_AUTH_ERROR = AUTH_ERROR_MESSAGES["sign_in_failed"]

# Codes we accept from the ?error= query string
ALLOWED_AUTH_ERROR_CODES = frozenset(AUTH_ERROR_MESSAGES.keys())


def public_auth_error(code: str | None) -> str:
    """Map an error code (or unknown value) to a safe UI message."""
    if not code:
        return ""
    key = code.strip().lower()
    # Reject free-form / technical strings passed via the URL
    if key not in ALLOWED_AUTH_ERROR_CODES:
        return DEFAULT_AUTH_ERROR
    return AUTH_ERROR_MESSAGES[key]
