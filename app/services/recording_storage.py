"""Save uploaded meeting videos into the shared local recordings folder."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.auth.config import get_settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = frozenset({".mp4", ".webm", ".mov", ".mkv"})
CHUNK_SIZE = 1024 * 1024


class RecordingStorageError(Exception):
    def __init__(self, public_message: str, *, code: str = "") -> None:
        self.public_message = public_message
        self.code = code
        super().__init__(public_message)


def original_extension(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix in ALLOWED_EXTENSIONS else ""


def unique_recording_name(original_filename: str | None) -> str:
    ext = original_extension(original_filename) or ".mp4"
    return f"upload-{uuid.uuid4().hex}{ext}"


def human_file_size(size_bytes: int | None) -> str:
    size = int(size_bytes or 0)
    if size <= 0:
        return ""
    for unit, threshold in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if size >= threshold:
            return f"{size / threshold:.1f} {unit}"
    return f"{size} B"


def resolve_recording_path(recording_filename: str | None) -> Path | None:
    """Resolve a stored recording filename without allowing path traversal."""
    filename = Path(recording_filename or "").name
    if not filename or not original_extension(filename):
        return None

    recordings_dir = get_settings().recordings_dir.resolve()
    candidate = (recordings_dir / filename).resolve()
    if candidate.parent != recordings_dir or not candidate.is_file():
        return None
    return candidate


async def save_uploaded_recording(upload: UploadFile) -> dict[str, str | int]:
    """
    Stream the upload to RECORDINGS_DIR with a unique filename.

    Returns recording_filename, recording_path (absolute), original_filename, file_size_bytes.
    """
    original = Path(upload.filename or "").name
    if not original_extension(original):
        raise RecordingStorageError(
            "Please upload an MP4, WebM, MOV, or MKV video file.",
            code="invalid_type",
        )

    settings = get_settings()
    recordings_dir = settings.recordings_dir
    recordings_dir.mkdir(parents=True, exist_ok=True)

    filename = unique_recording_name(original)
    dest = recordings_dir / filename
    max_bytes = settings.max_upload_bytes
    size = 0

    try:
        with dest.open("wb") as out:
            while True:
                chunk = await upload.read(CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise RecordingStorageError(
                        "This video is too large to upload. Please choose a smaller file.",
                        code="file_too_large",
                    )
                out.write(chunk)
    except RecordingStorageError:
        dest.unlink(missing_ok=True)
        raise
    except Exception as exc:
        dest.unlink(missing_ok=True)
        logger.exception("Failed to write uploaded recording to %s", dest)
        raise RecordingStorageError(
            "Unable to store the recording. Please try again.",
            code="write_failed",
        ) from exc
    finally:
        await upload.close()

    if size <= 0:
        dest.unlink(missing_ok=True)
        raise RecordingStorageError(
            "The uploaded file is empty. Please choose a valid recording.",
            code="empty_file",
        )

    return {
        "recording_filename": filename,
        "recording_path": str(dest),
        "original_filename": original,
        "file_size_bytes": size,
    }


def delete_recording(path: str | Path | None) -> None:
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete recording file %s", path)


def delete_meeting_recordings(
    recording_filename: str | None,
    recording_path: str | None = None,
) -> None:
    """Delete files for a meeting, staying inside RECORDINGS_DIR."""
    resolved = resolve_recording_path(recording_filename)
    if resolved:
        delete_recording(resolved)

    if not recording_path:
        return
    try:
        recordings_dir = get_settings().recordings_dir.resolve()
        candidate = Path(recording_path).resolve()
        candidate.relative_to(recordings_dir)
    except (OSError, ValueError):
        return
    if candidate.is_file() and candidate != resolved:
        delete_recording(candidate)
