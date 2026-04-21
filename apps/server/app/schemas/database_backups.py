from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DatabaseBackupTreeNodeResponse(BaseModel):
    id: str
    name: str
    database_name: str
    odoo_version: str
    parent_id: str | None
    source_type: str
    is_main_root: bool
    created_at: datetime
    children: list["DatabaseBackupTreeNodeResponse"] = Field(default_factory=list)


class DatabaseBackupTreeResponse(BaseModel):
    main_root_id: str | None
    items: list[DatabaseBackupTreeNodeResponse] = Field(default_factory=list)


DatabaseBackupTreeNodeResponse.model_rebuild()
