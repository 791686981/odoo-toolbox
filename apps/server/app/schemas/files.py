from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UploadedFileResponse(BaseModel):
    id: str
    original_name: str
    mime_type: str
    size: int
    created_at: datetime


class StoredFileResponse(UploadedFileResponse):
    kind: str
    run_id: str | None = None
    tool_id: str | None = None
    artifact_label: str | None = None
