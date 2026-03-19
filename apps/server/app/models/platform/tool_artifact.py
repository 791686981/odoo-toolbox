from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String

from app.db.base import Base
from app.models.entities import new_id, utcnow


class ToolArtifact(Base):
    __tablename__ = "tool_artifacts"

    id = Column(String(36), primary_key=True, default=new_id)
    run_id = Column(String(36), ForeignKey("tool_runs.id"), nullable=False)
    kind = Column(String(50), nullable=False)
    file_id = Column(String(36), ForeignKey("uploaded_files.id"), nullable=False)
    label = Column(String(255), nullable=False, default="")
    artifact_metadata = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=utcnow, nullable=False)
