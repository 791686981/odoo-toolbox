from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=new_id)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(String(36), primary_key=True, default=new_id)
    original_name = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False)
    mime_type = Column(String(255), nullable=False)
    size = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class TranslationJob(Base):
    __tablename__ = "translation_jobs"

    id = Column(String(36), primary_key=True, default=new_id)
    tool_id = Column(String(100), nullable=False, default="csv-translation")
    status = Column(String(50), nullable=False, default="draft")
    progress = Column(Integer, nullable=False, default=0)
    source_language = Column(String(32), nullable=False)
    target_language = Column(String(32), nullable=False)
    context_text = Column(Text, nullable=False)
    overwrite_existing = Column(Boolean, nullable=False, default=False)
    chunk_size = Column(Integer, nullable=False)
    concurrency = Column(Integer, nullable=False)
    total_rows = Column(Integer, nullable=False, default=0)
    processed_rows = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=False, default="")
    uploaded_file_id = Column(String(36), ForeignKey("uploaded_files.id"), nullable=False)
    exported_file_id = Column(String(36), ForeignKey("uploaded_files.id"), nullable=True)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class TranslationJobChunk(Base):
    __tablename__ = "translation_job_chunks"

    id = Column(String(36), primary_key=True, default=new_id)
    job_id = Column(String(36), ForeignKey("translation_jobs.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    row_numbers = Column(JSON, nullable=False, default=list)
    row_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class TranslationRowResult(Base):
    __tablename__ = "translation_row_results"

    id = Column(String(36), primary_key=True, default=new_id)
    job_id = Column(String(36), ForeignKey("translation_jobs.id"), nullable=False)
    row_number = Column(Integer, nullable=False)
    module = Column(String(255), nullable=False, default="")
    record_type = Column(String(255), nullable=False, default="")
    name = Column(String(255), nullable=False, default="")
    res_id = Column(String(255), nullable=False, default="")
    source_text = Column(Text, nullable=False, default="")
    original_value = Column(Text, nullable=False, default="")
    translated_value = Column(Text, nullable=False, default="")
    edited_value = Column(Text, nullable=False, default="")
    comments = Column(Text, nullable=False, default="")
    raw_data = Column(JSON, nullable=False, default=dict)
    status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
