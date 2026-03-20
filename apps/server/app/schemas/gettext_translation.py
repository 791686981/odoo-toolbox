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


class GettextContextDraftRequest(BaseModel):
    uploaded_file_id: str
    source_language: str
    target_language: str


class GettextContextDraftResponse(BaseModel):
    background: str


class GettextTranslationEntryResponse(BaseModel):
    id: str
    entry_index: int
    msgctxt: str
    msgid: str
    msgid_plural: str
    msgstr: str
    msgstr_plural: dict[int, str]
    translated_value: str
    translated_plural_values: dict[int, str]
    edited_value: str
    edited_plural_values: dict[int, str]
    comment: str
    tcomment: str
    occurrences: list[list[str]]
    flags: list[str]
    status: str
    is_plural: bool
    is_fuzzy: bool


class GettextTranslationEntriesPage(BaseModel):
    items: list[GettextTranslationEntryResponse]
    total: int
    page: int
    page_size: int


class GettextProofreadSuggestionResponse(BaseModel):
    entry_id: str
    entry_index: int
    msgid: str
    msgid_plural: str
    current_value: str
    current_plural_values: dict[int, str] = Field(default_factory=dict)
    suggested_value: str
    suggested_plural_values: dict[int, str] = Field(default_factory=dict)
    reason: str
    is_plural: bool


class GettextProofreadPreviewResponse(BaseModel):
    model: str
    items: list[GettextProofreadSuggestionResponse]


class UpdateGettextTranslationEntryRequest(BaseModel):
    edited_value: str = ""
    edited_plural_values: dict[int, str] = Field(default_factory=dict)


class ExportGettextTranslationResponse(BaseModel):
    file_id: str
    filename: str


class CreateGettextTranslationJobRequest(BaseModel):
    uploaded_file_id: str
    source_language: str
    target_language: str
    context_text: str = ""
    translation_mode: str = Field(default="blank", pattern="^(blank|blank_and_fuzzy|overwrite_all)$")
    chunk_size: int = Field(default=20, ge=1, le=200)
    concurrency: int = Field(default=1, ge=1, le=10)
