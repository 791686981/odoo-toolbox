from __future__ import annotations

from typing import List

from openai import OpenAI
from pydantic import BaseModel, Field

from app.core.config import settings


class ContextDraftResponse(BaseModel):
    background: str


class TranslationItemResponse(BaseModel):
    row_number: int
    translated_value: str


class TranslationBatchResponse(BaseModel):
    items: List[TranslationItemResponse]


class ProofreadItemResponse(BaseModel):
    row_number: int
    suggested_value: str
    reason: str


class ProofreadBatchResponse(BaseModel):
    items: List[ProofreadItemResponse]


class GettextPluralValueResponse(BaseModel):
    index: int
    value: str


class GettextTranslationItemResponse(BaseModel):
    entry_index: int
    translated_value: str = ""
    translated_plural_values: List[GettextPluralValueResponse] = Field(default_factory=list)


class GettextTranslationBatchResponse(BaseModel):
    items: List[GettextTranslationItemResponse]


class GettextProofreadItemResponse(BaseModel):
    entry_index: int
    suggested_value: str = ""
    suggested_plural_values: List[GettextPluralValueResponse] = Field(default_factory=list)
    reason: str


class GettextProofreadBatchResponse(BaseModel):
    items: List[GettextProofreadItemResponse]


class OpenAIService:
    def __init__(self) -> None:
        self._client = None

    def _require_client(self) -> OpenAI:
        if self._client is None:
            if not settings.openai_api_key:
                raise RuntimeError("OpenAI 未配置，请设置 TOOLBOX_OPENAI_API_KEY。")
            self._client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
        return self._client

    def create_context_draft(self, system_prompt: str, user_prompt: str) -> str:
        client = self._require_client()
        response = client.responses.parse(
            model=settings.openai_translation_model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
            text_format=ContextDraftResponse,
        )
        parsed = response.output_parsed
        return parsed.background.strip()

    def translate_rows(self, system_prompt: str, user_prompt: str) -> List[TranslationItemResponse]:
        client = self._require_client()
        response = client.responses.parse(
            model=settings.openai_translation_model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
            text_format=TranslationBatchResponse,
        )
        parsed = response.output_parsed
        return parsed.items

    def proofread_rows(self, system_prompt: str, user_prompt: str) -> List[ProofreadItemResponse]:
        client = self._require_client()
        response = client.responses.parse(
            model=settings.openai_review_model or settings.openai_translation_model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
            text_format=ProofreadBatchResponse,
        )
        parsed = response.output_parsed
        return parsed.items

    def translate_gettext_entries(self, system_prompt: str, user_prompt: str) -> List[GettextTranslationItemResponse]:
        client = self._require_client()
        response = client.responses.parse(
            model=settings.openai_translation_model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
            text_format=GettextTranslationBatchResponse,
        )
        parsed = response.output_parsed
        return parsed.items

    def proofread_gettext_entries(self, system_prompt: str, user_prompt: str) -> List[GettextProofreadItemResponse]:
        client = self._require_client()
        response = client.responses.parse(
            model=settings.openai_review_model or settings.openai_translation_model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
            text_format=GettextProofreadBatchResponse,
        )
        parsed = response.output_parsed
        return parsed.items


openai_service = OpenAIService()
