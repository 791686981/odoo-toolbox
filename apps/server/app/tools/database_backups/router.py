from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import DatabaseBackupNode
from app.schemas.database_backups import (
    DatabaseBackupDetailResponse,
    DatabaseBackupRestoreEnvResponse,
    UatEnsureTreeRequest,
    UatEnsureTreeResponse,
    UatSnapshotUploadGuideResponse,
)
from app.services.database_backup_service import (
    build_database_backup_restore_env,
    build_database_backup_tree_response,
    build_files_by_id,
    ensure_uat_tree as ensure_uat_tree_service,
    filter_uat_tree,
    load_database_backup_detail,
    serialize_database_backup_detail,
    serialize_uat_ensure_tree_response,
)


router = APIRouter(prefix="/tools/database-backups")


class ListDatabaseBackupTreeRequest(BaseModel):
    root: str | None = Field(default=None, description='可选；传 "UAT" 时只返回 UAT 备份树。')


class DatabaseBackupNodeLookupRequest(BaseModel):
    node_id: str


class PrepareUatSnapshotUploadRequest(BaseModel):
    domain: str
    requirement_title: str
    snapshot_name: str
    snapshot_type: str
    parent_id: str | None = None
    notion_url: str | None = None
    base_node_id: str | None = None
    git_branch: str | None = None
    git_commit: str | None = None
    odoo_version: str | None = None
    database_name: str | None = None
    note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post(
    "/list-tree",
    response_model=None,
    tags=["mcp"],
    summary="列出数据库备份树",
    description="返回数据库备份树。root 为 UAT 时只返回 UAT 目录及其子节点。",
)
def list_database_backup_tree(
    payload: ListDatabaseBackupTreeRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    nodes = db.execute(select(DatabaseBackupNode)).scalars().all()
    if payload.root == "UAT":
        nodes = filter_uat_tree(nodes)
    return build_database_backup_tree_response(nodes, build_files_by_id(db, nodes)).model_dump(mode="json")


@router.post(
    "/ensure-uat-tree",
    response_model=UatEnsureTreeResponse,
    tags=["mcp"],
    summary="确保 UAT 备份树目录",
    description="幂等创建 UAT 根、标准业务域目录和指定需求目录。",
)
def ensure_uat_tree(
    payload: UatEnsureTreeRequest,
    db: Session = Depends(get_db),
) -> UatEnsureTreeResponse:
    root, domain_node, requirement_node = ensure_uat_tree_service(
        db,
        domain=payload.domain,
        requirement_title=payload.requirement_title,
        notion_url=payload.notion_url,
        metadata=payload.metadata,
        username="mcp",
    )
    return serialize_uat_ensure_tree_response(root, domain_node, requirement_node)


@router.post(
    "/get-node",
    response_model=DatabaseBackupDetailResponse,
    tags=["mcp"],
    summary="查询数据库备份节点",
    description="查询数据库备份节点详情；目录节点不会返回 zip 下载信息。",
)
def get_database_backup_node(
    payload: DatabaseBackupNodeLookupRequest,
    db: Session = Depends(get_db),
) -> DatabaseBackupDetailResponse:
    node, file_record = load_database_backup_detail(db, payload.node_id)
    return serialize_database_backup_detail(node, file_record)


@router.post(
    "/prepare-uat-snapshot-upload",
    response_model=UatSnapshotUploadGuideResponse,
    tags=["mcp"],
    summary="准备 UAT 快照上传",
    description="不创建节点，只返回 REST multipart 上传地址、鉴权方式和推荐表单字段。",
)
def prepare_uat_snapshot_upload(payload: PrepareUatSnapshotUploadRequest) -> UatSnapshotUploadGuideResponse:
    fields = payload.model_dump(exclude_none=True)
    fields.pop("metadata", None)
    if payload.metadata:
        fields["metadata"] = json.dumps(payload.metadata, ensure_ascii=False)
    fields["file"] = "<Odoo 原生数据库备份 zip>"
    return UatSnapshotUploadGuideResponse(
        upload_url="/api/database-backups/uat/snapshots",
        auth="Authorization: Bearer <TOOLBOX_DATABASE_BACKUP_WRITE_API_KEY>",
        recommended_form_fields=fields,
    )


@router.post(
    "/build-odoo-restore-env",
    response_model=DatabaseBackupRestoreEnvResponse,
    tags=["mcp"],
    summary="生成 Odoo 恢复环境变量",
    description="输入快照节点 ID，返回可写入 Odoo worktree .env 的恢复配置片段。",
)
def build_odoo_restore_env(
    payload: DatabaseBackupNodeLookupRequest,
    db: Session = Depends(get_db),
) -> DatabaseBackupRestoreEnvResponse:
    return build_database_backup_restore_env(db, payload.node_id)
