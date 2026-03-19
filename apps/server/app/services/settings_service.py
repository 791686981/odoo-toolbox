from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import SystemSetting
from app.schemas.settings import SettingsResponse, UpdateSettingsRequest


def _get(db: Session, key: str, fallback: str) -> str:
    record = db.get(SystemSetting, key)
    return record.value if record is not None else fallback


def get_runtime_settings(db: Session) -> SettingsResponse:
    return SettingsResponse(
        openai_base_url=settings.openai_base_url,
        openai_translation_model=settings.openai_translation_model,
        openai_review_model=settings.openai_review_model or settings.openai_translation_model,
        default_source_language=_get(db, "default_source_language", settings.default_source_language),
        default_target_language=_get(db, "default_target_language", settings.default_target_language),
        default_chunk_size=int(_get(db, "default_chunk_size", str(settings.default_chunk_size))),
        default_concurrency=int(_get(db, "default_concurrency", str(settings.default_concurrency))),
        default_overwrite_existing=_get(
            db,
            "default_overwrite_existing",
            "true" if settings.default_overwrite_existing else "false",
        ).lower()
        == "true",
    )


def update_runtime_settings(db: Session, payload: UpdateSettingsRequest) -> SettingsResponse:
    updates = {
        "default_source_language": payload.default_source_language,
        "default_target_language": payload.default_target_language,
        "default_chunk_size": str(payload.default_chunk_size),
        "default_concurrency": str(payload.default_concurrency),
        "default_overwrite_existing": "true" if payload.default_overwrite_existing else "false",
    }

    for key, value in updates.items():
        record = db.get(SystemSetting, key)
        if record is None:
            db.add(SystemSetting(key=key, value=value))
        else:
            record.value = value

    db.commit()
    return get_runtime_settings(db)
