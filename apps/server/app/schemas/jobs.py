from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class TranslationJobResponse(BaseModel):
    id: str
    status: str
    progress: int
    source_language: str
    target_language: str
    context_text: str
    overwrite_existing: bool
    chunk_size: int
    concurrency: int
    total_rows: int
    processed_rows: int
    error_message: str
    uploaded_file_id: str
    exported_file_id: str | None = None
    created_at: datetime
    updated_at: datetime


class TranslationRowResponse(BaseModel):
    id: str
    row_number: int
    module: str
    record_type: str
    name: str
    res_id: str
    source_text: str
    original_value: str
    translated_value: str
    edited_value: str
    comments: str
    status: str


class TranslationRowsPage(BaseModel):
    items: List[TranslationRowResponse]
    total: int
    page: int
    page_size: int


class UpdateTranslationRowRequest(BaseModel):
    edited_value: str = Field(default="")


class ExportJobResponse(BaseModel):
    file_id: str
    filename: str


class ProofreadSuggestionResponse(BaseModel):
    row_id: str
    row_number: int
    source_text: str
    current_value: str
    suggested_value: str
    reason: str


class ProofreadPreviewResponse(BaseModel):
    model: str
    items: List[ProofreadSuggestionResponse]
