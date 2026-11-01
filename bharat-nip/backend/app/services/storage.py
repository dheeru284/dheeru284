from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.ingest.extract import sniff_content_type
from app.models import StoredFile, User
from app.services.errors import Unprocessable

ALLOWED_UPLOAD_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp"}


def save_upload(
    session: Session, settings: Settings, user: User, filename: str, data: bytes
) -> StoredFile:
    if not data:
        raise Unprocessable("Uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise Unprocessable(f"File exceeds {settings.max_upload_bytes} bytes.")
    # Trust the bytes, not the client's declared content type.
    content_type = sniff_content_type(data)
    if content_type not in ALLOWED_UPLOAD_TYPES:
        raise Unprocessable("Only PDF, PNG, JPEG, GIF and WEBP files are accepted.")
    digest = hashlib.sha256(data).hexdigest()
    rel = Path(digest[:2]) / digest
    path = settings.storage_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(data)
    stored = StoredFile(
        sha256=digest,
        filename=Path(filename or "upload").name[:255],
        content_type=content_type,
        size_bytes=len(data),
        storage_path=str(rel),
        uploaded_by_id=user.id,
    )
    session.add(stored)
    session.flush()
    return stored


def read_stored(settings: Settings, stored: StoredFile) -> bytes:
    return (settings.storage_dir / stored.storage_path).read_bytes()
