from __future__ import annotations

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    openai_base_url: str
    openai_translation_model: str
    openai_review_model: str
    default_source_language: str
    default_target_language: str
    default_chunk_size: int
    default_concurrency: int
    default_overwrite_existing: bool


class UpdateSettingsRequest(BaseModel):
    default_source_language: str
    default_target_language: str
    default_chunk_size: int
    default_concurrency: int
    default_overwrite_existing: bool
