from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import UploadedFile


def store_upload(db: Session, upload: UploadFile, username: str) -> UploadedFile:
    suffix = Path(upload.filename or "upload.csv").suffix or ".csv"
    stored_name = f"{uuid4()}{suffix}"
    destination = settings.upload_dir / stored_name
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    file_bytes = upload.file.read()
    destination.write_bytes(file_bytes)
    record = UploadedFile(
        original_name=upload.filename or "upload.csv",
        stored_path=str(destination),
        mime_type=upload.content_type or "application/octet-stream",
        size=len(file_bytes),
        sha256=hashlib.sha256(file_bytes).hexdigest(),
        created_by=username,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def store_generated_file(
    db: Session,
    filename: str,
    content: bytes,
    mime_type: str,
    username: str,
) -> UploadedFile:
    stored_name = f"{uuid4()}-{filename}"
    destination = settings.output_dir / stored_name
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)

    record = UploadedFile(
        original_name=filename,
        stored_path=str(destination),
        mime_type=mime_type,
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        created_by=username,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
