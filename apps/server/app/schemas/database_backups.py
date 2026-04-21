from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DatabaseBackupZipResponse(BaseModel):
    file_id: str
    filename: str
    size: int
    mime_type: str
    sha256: str
    download_url: str


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


class DatabaseBackupDetailResponse(BaseModel):
    id: str
    name: str
    database_name: str
    odoo_version: str
    parent_id: str | None = None
    source_type: str
    is_main_root: bool
    note: str
    created_at: datetime
    updated_at: datetime
    zip: DatabaseBackupZipResponse


DatabaseBackupTreeNodeResponse.model_rebuild()
