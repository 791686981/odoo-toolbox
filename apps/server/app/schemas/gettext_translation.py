from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GettextTranslationRunResponse(BaseModel):
    id: str
    tool_id: str
    status: str
    progress: int
    input_file_type: str
    translation_mode: str
    source_language: str
    target_language: str
    context_text: str
    chunk_size: int
    concurrency: int
    total_entries: int
    processed_entries: int
    error_message: str
    uploaded_file_id: str
    exported_file_id: str | None = None
    created_at: datetime
    updated_at: datetime


class CreateGettextTranslationJobRequest(BaseModel):
    uploaded_file_id: str
    source_language: str
    target_language: str
    context_text: str = ""
    translation_mode: str = Field(default="blank", pattern="^(blank|blank_and_fuzzy|overwrite_all)$")
    chunk_size: int = Field(default=20, ge=1, le=200)
    concurrency: int = Field(default=1, ge=1, le=10)
