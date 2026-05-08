from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


NodeKind = Literal["folder", "snapshot"]
SnapshotType = Literal["baseline", "issue_reproduction", "regression", "ad_hoc"]


class DatabaseBackupZipResponse(BaseModel):
    file_id: str
    filename: str
    size: int
    mime_type: str
    sha256: str
    download_url: str


class DatabaseBackupRestoreEnvResponse(BaseModel):
    node_id: str
    restore_env: str
    values: dict[str, str]


class DatabaseBackupTreeNodeResponse(BaseModel):
    id: str
    name: str
    database_name: str
    odoo_version: str
    parent_id: str | None
    source_type: str
    node_kind: NodeKind
    snapshot_type: SnapshotType | None = None
    domain: str | None = None
    requirement_title: str | None = None
    notion_url: str | None = None
    is_main_root: bool
    created_at: datetime
    zip: DatabaseBackupZipResponse | None = None
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
    node_kind: NodeKind
    snapshot_type: SnapshotType | None = None
    domain: str | None = None
    requirement_title: str | None = None
    notion_url: str | None = None
    base_node_id: str | None = None
    git_branch: str | None = None
    git_commit: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_main_root: bool
    note: str
    created_at: datetime
    updated_at: datetime
    zip: DatabaseBackupZipResponse | None = None


class DatabaseBackupPatchRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    note: str | None = None
    notion_url: str | None = None
    base_node_id: str | None = None
    git_branch: str | None = None
    git_commit: str | None = None
    database_name: str | None = None
    odoo_version: str | None = None
    metadata: dict[str, Any] | None = None


class DatabaseBackupFolderCreateRequest(BaseModel):
    name: str
    parent_id: str | None = None
    domain: str | None = None
    requirement_title: str | None = None
    notion_url: str | None = None
    note: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class UatEnsureTreeRequest(BaseModel):
    domain: str
    requirement_title: str
    notion_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UatEnsureTreeResponse(BaseModel):
    root: DatabaseBackupDetailResponse
    domain_node: DatabaseBackupDetailResponse
    requirement_node: DatabaseBackupDetailResponse


class UatSnapshotCreateResponse(BaseModel):
    node_id: str
    name: str
    parent_id: str
    node_kind: NodeKind
    snapshot_type: SnapshotType
    sha256: str
    download_url: str
    restore_env: str


class UatSnapshotUploadGuideResponse(BaseModel):
    upload_url: str
    method: str = "POST"
    auth: str
    recommended_form_fields: dict[str, Any]


DatabaseBackupTreeNodeResponse.model_rebuild()
