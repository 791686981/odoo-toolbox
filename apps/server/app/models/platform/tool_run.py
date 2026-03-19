from __future__ import annotations

from sqlalchemy import Column, DateTime, JSON, String, Text

from app.db.base import Base
from app.models.entities import new_id, utcnow


class ToolRun(Base):
    __tablename__ = "tool_runs"

    id = Column(String(36), primary_key=True, default=new_id)
    tool_id = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default="queued")
    summary = Column(Text, nullable=False, default="")
    created_by = Column(String(100), nullable=False)
    input_payload = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
