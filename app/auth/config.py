"""Application settings loaded from environment."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (MeetInsights-Web/)
_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")


class Settings:
    """Runtime configuration."""

    app_name: str = "Meet Insights"
    app_base_url: str = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
    debug: bool = os.getenv("DEBUG", "false").lower() in {"1", "true", "yes"}

    # MongoDB
    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_db: str = os.getenv("MONGODB_DB", "meetinsights")

    # RabbitMQ
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    rabbitmq_meeting_queue: str = os.getenv("RABBITMQ_MEETING_QUEUE", "meetinsights.meetings")
    # Recording-ready jobs for MeetInsight (not the bot join queue)
    rabbitmq_recording_queue: str = os.getenv(
        "RABBITMQ_RECORDING_QUEUE",
        "meetinsights.recordings",
    )

    # Local recordings folder (same path MeetRecorder writes to; not S3 yet)
    _recordings_dir_raw: str = os.getenv("RECORDINGS_DIR", "").strip()
    try:
        _max_upload = int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024 * 1024 * 1024)) or 0)
    except ValueError:
        _max_upload = 0
    max_upload_bytes: int = _max_upload if _max_upload > 0 else (2 * 1024 * 1024 * 1024)

    # Google OAuth
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://127.0.0.1:8000/auth/google/callback",
    )
    google_auth_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    google_token_url: str = "https://oauth2.googleapis.com/token"
    google_userinfo_url: str = "https://www.googleapis.com/oauth2/v3/userinfo"
    google_scopes: str = "openid email profile"

    # JWT / encryption (mirrors src/helper/jwt_helper.ts env names)
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-jwt-secret-change-me-32b!")
    refresh_token_key: str = os.getenv("REFRESH_TOKEN_KEY", "dev-refresh-secret-change-me!!")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expires: str = os.getenv("JWT_EXPIRES", "3600s")  # access TTL
    refresh_token_expire: str = os.getenv("REFRESH_TOKEN_EXPIRE", "2592000s")  # 30 days
    crypt_algo: str = os.getenv("CRYPT_ALGO", "aes-256-cbc")
    encryption_iv_key: str = os.getenv("ENCRYPTION_IV_KEY", "0123456789abcdef")  # 16 chars

    # Cookies
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
    cookie_samesite: str = os.getenv("COOKIE_SAMESITE", "lax")
    access_cookie_name: str = "mi_access_token"
    refresh_cookie_name: str = "mi_refresh_token"
    bearer_handoff_cookie_name: str = "mi_bearer_handoff"

    @property
    def recordings_dir(self) -> Path:
        """
        Directory where meeting videos are stored.

        Defaults to ../MeetRecorder/recordings so uploads land next to
        bot recordings. Override with RECORDINGS_DIR (absolute or relative
        to the MeetInsights-Web project root).
        """
        raw = (self._recordings_dir_raw or "").strip()
        if raw:
            path = Path(raw)
            return path.resolve() if path.is_absolute() else (_ROOT / path).resolve()
        return (_ROOT.parent / "MeetRecorder" / "recordings").resolve()

    @property
    def google_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @staticmethod
    def parse_ttl_seconds(value: str) -> int:
        """Parse '3600s' / '3600' style TTL used by the Node helpers."""
        raw = (value or "").strip().lower()
        if raw.endswith("s"):
            raw = raw[:-1]
        try:
            return max(1, int(raw))
        except ValueError:
            return 3600


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
