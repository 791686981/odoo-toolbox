from __future__ import annotations

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base
from app.models.entities import new_id, utcnow


class GettextTranslationRun(Base):
    __tablename__ = "gettext_translation_runs"

    id = Column(String(36), primary_key=True, default=new_id)
    tool_id = Column(String(100), nullable=False, default="gettext-translation")
    status = Column(String(50), nullable=False, default="queued")
    progress = Column(Integer, nullable=False, default=0)
    input_file_type = Column(String(10), nullable=False)
    translation_mode = Column(String(32), nullable=False)
    source_language = Column(String(32), nullable=False)
    target_language = Column(String(32), nullable=False)
    context_text = Column(Text, nullable=False, default="")
    chunk_size = Column(Integer, nullable=False)
    concurrency = Column(Integer, nullable=False)
    total_entries = Column(Integer, nullable=False, default=0)
    processed_entries = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=False, default="")
    uploaded_file_id = Column(String(36), ForeignKey("uploaded_files.id"), nullable=False)
    exported_file_id = Column(String(36), ForeignKey("uploaded_files.id"), nullable=True)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class GettextTranslationEntry(Base):
    __tablename__ = "gettext_translation_entries"

    id = Column(String(36), primary_key=True, default=new_id)
    run_id = Column(String(36), ForeignKey("gettext_translation_runs.id"), nullable=False)
    entry_index = Column(Integer, nullable=False)
    msgctxt = Column(Text, nullable=False, default="")
    msgid = Column(Text, nullable=False, default="")
    msgid_plural = Column(Text, nullable=False, default="")
    msgstr = Column(Text, nullable=False, default="")
    msgstr_plural = Column(JSON, nullable=False, default=dict)
    translated_value = Column(Text, nullable=False, default="")
    translated_plural_values = Column(JSON, nullable=False, default=dict)
    edited_value = Column(Text, nullable=False, default="")
    edited_plural_values = Column(JSON, nullable=False, default=dict)
    occurrences = Column(JSON, nullable=False, default=list)
    flags = Column(JSON, nullable=False, default=list)
    comment = Column(Text, nullable=False, default="")
    tcomment = Column(Text, nullable=False, default="")
    previous_msgid = Column(Text, nullable=False, default="")
    status = Column(String(50), nullable=False, default="pending")
    is_plural = Column(Boolean, nullable=False, default=False)
    is_fuzzy = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class GettextTranslationChunk(Base):
    __tablename__ = "gettext_translation_chunks"

    id = Column(String(36), primary_key=True, default=new_id)
    run_id = Column(String(36), ForeignKey("gettext_translation_runs.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    entry_ids = Column(JSON, nullable=False, default=list)
    entry_count = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False, default="pending")
    error_message = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
