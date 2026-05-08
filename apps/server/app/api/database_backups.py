from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    verify_database_backup_download_access,
    verify_database_backup_write_access,
)
from app.db.session import get_db
from app.models import DatabaseBackupNode, User
from app.schemas.database_backups import (
    DatabaseBackupDetailResponse,
    DatabaseBackupFolderCreateRequest,
    DatabaseBackupPatchRequest,
    DatabaseBackupRestoreEnvResponse,
    DatabaseBackupTreeResponse,
    UatEnsureTreeRequest,
    UatEnsureTreeResponse,
    UatSnapshotCreateResponse,
)
from app.services.database_backup_service import (
    build_database_backup_restore_env,
    build_database_backup_tree_response,
    build_database_backup_zip_headers,
    build_files_by_id,
    create_database_backup_folder,
    create_database_backup_node,
    create_uat_snapshot,
    delete_database_backup_leaf_node,
    ensure_uat_tree,
    load_database_backup_detail,
    load_database_backup_node,
    load_database_backup_zip_detail,
    mark_database_backup_main_root,
    serialize_database_backup_detail,
    serialize_uat_ensure_tree_response,
    serialize_uat_snapshot_create_response,
    update_database_backup_detail,
)


router = APIRouter(tags=["database-backups"])


def _auth_username(user: User | None) -> str:
    return user.username if user is not None else "api-key"


def _build_database_backup_zip_response(file_record, path: Path) -> FileResponse:
    return FileResponse(
        path,
        media_type="application/zip",
        filename=file_record.original_name,
        headers=build_database_backup_zip_headers(file_record, path),
    )


@router.get("/database-backups/tree", response_model=DatabaseBackupTreeResponse)
def get_database_backup_tree(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatabaseBackupTreeResponse:
    nodes = db.execute(select(DatabaseBackupNode)).scalars().all()
    return build_database_backup_tree_response(nodes, build_files_by_id(db, nodes))


@router.post("/database-backups/folders", response_model=DatabaseBackupDetailResponse)
def create_database_backup_folder_api(
    payload: DatabaseBackupFolderCreateRequest,
    auth_context: User | None = Depends(verify_database_backup_write_access),
    db: Session = Depends(get_db),
) -> DatabaseBackupDetailResponse:
    node = create_database_backup_folder(
        db,
        name=payload.name,
        parent_id=payload.parent_id,
        domain=payload.domain,
        requirement_title=payload.requirement_title,
        notion_url=payload.notion_url,
        note=payload.note,
        metadata=payload.metadata,
        username=_auth_username(auth_context),
    )
    return serialize_database_backup_detail(node)


@router.post("/database-backups/uat/ensure-tree", response_model=UatEnsureTreeResponse)
def ensure_uat_tree_api(
    payload: UatEnsureTreeRequest,
    auth_context: User | None = Depends(verify_database_backup_write_access),
    db: Session = Depends(get_db),
) -> UatEnsureTreeResponse:
    root, domain_node, requirement_node = ensure_uat_tree(
        db,
        domain=payload.domain,
        requirement_title=payload.requirement_title,
        notion_url=payload.notion_url,
        metadata=payload.metadata,
        username=_auth_username(auth_context),
    )
    return serialize_uat_ensure_tree_response(root, domain_node, requirement_node)


@router.post("/database-backups/uat/snapshots", response_model=UatSnapshotCreateResponse)
def create_uat_snapshot_api(
    domain: str = Form(...),
    requirement_title: str = Form(...),
    snapshot_name: str = Form(...),
    snapshot_type: str = Form(...),
    parent_id: str | None = Form(None),
    notion_url: str | None = Form(None),
    base_node_id: str | None = Form(None),
    git_branch: str | None = Form(None),
    git_commit: str | None = Form(None),
    odoo_version: str = Form(""),
    database_name: str = Form(""),
    note: str = Form(""),
    metadata: str | None = Form(None),
    file: UploadFile = File(...),
    auth_context: User | None = Depends(verify_database_backup_write_access),
    db: Session = Depends(get_db),
) -> UatSnapshotCreateResponse:
    node, file_record, restore_env = create_uat_snapshot(
        db,
        domain=domain,
        requirement_title=requirement_title,
        snapshot_name=snapshot_name,
        snapshot_type=snapshot_type,
        parent_id=parent_id,
        notion_url=notion_url,
        base_node_id=base_node_id,
        git_branch=git_branch,
        git_commit=git_commit,
        odoo_version=odoo_version,
        database_name=database_name,
        note=note,
        metadata=_parse_metadata_form(metadata),
        upload=file,
        username=_auth_username(auth_context),
    )
    return serialize_uat_snapshot_create_response(node, file_record, restore_env)


def _parse_metadata_form(value: str | None) -> dict[str, Any] | None:
    if value is None or value == "":
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="metadata 必须是 JSON 对象。") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="metadata 必须是 JSON 对象。")
    return parsed


@router.post("/database-backups/nodes", response_model=DatabaseBackupDetailResponse)
def create_database_backup_node_api(
    name: str = Form(...),
    database_name: str | None = Form(None),
    odoo_version: str = Form(""),
    source_type: str = Form(...),
    parent_id: str | None = Form(None),
    is_main_root: bool = Form(False),
    note: str = Form(""),
    file: UploadFile = File(...),
    auth_context: User | None = Depends(verify_database_backup_write_access),
    db: Session = Depends(get_db),
) -> DatabaseBackupDetailResponse:
    node, file_record = create_database_backup_node(
        db,
        name=name,
        database_name=database_name or name,
        odoo_version=odoo_version or "",
        source_type=source_type,
        parent_id=parent_id,
        is_main_root=is_main_root,
        note=note,
        upload=file,
        username=_auth_username(auth_context),
    )
    return serialize_database_backup_detail(node, file_record)


@router.delete("/database-backups/nodes/{node_id}", status_code=204)
def delete_database_backup_node(
    node_id: str,
    auth_context: User | None = Depends(verify_database_backup_write_access),
    db: Session = Depends(get_db),
) -> Response:
    delete_database_backup_leaf_node(db, node_id)
    return Response(status_code=204)


@router.get("/database-backups/nodes/{node_id}", response_model=DatabaseBackupDetailResponse)
def get_database_backup_node_detail(
    node_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatabaseBackupDetailResponse:
    node, file_record = load_database_backup_detail(db, node_id)
    return serialize_database_backup_detail(node, file_record)


@router.patch("/database-backups/nodes/{node_id}", response_model=DatabaseBackupDetailResponse)
def patch_database_backup_node(
    node_id: str,
    payload: DatabaseBackupPatchRequest = Body(...),
    auth_context: User | None = Depends(verify_database_backup_write_access),
    db: Session = Depends(get_db),
) -> DatabaseBackupDetailResponse:
    forbidden_fields = {"node_kind", "zip_file_id", "parent_id", "source_type", "is_main_root"}
    if payload.model_extra:
        blocked = forbidden_fields.intersection(payload.model_extra)
        if blocked:
            raise HTTPException(status_code=400, detail=f"不允许修改字段: {', '.join(sorted(blocked))}。")
        raise HTTPException(status_code=400, detail="包含不支持修改的字段。")
    if not any(value is not None for value in payload.model_dump().values()):
        raise HTTPException(status_code=400, detail="没有可修改的字段。")

    node = load_database_backup_node(db, node_id)
    node = update_database_backup_detail(
        db,
        node,
        name=payload.name,
        note=payload.note,
        notion_url=payload.notion_url,
        base_node_id=payload.base_node_id,
        git_branch=payload.git_branch,
        git_commit=payload.git_commit,
        database_name=payload.database_name,
        odoo_version=payload.odoo_version,
        metadata=payload.metadata,
    )
    _, file_record = load_database_backup_detail(db, node.id)
    return serialize_database_backup_detail(node, file_record)


@router.post("/database-backups/nodes/{node_id}/restore-env", response_model=DatabaseBackupRestoreEnvResponse)
def build_database_backup_restore_env_api(
    node_id: str,
    auth_context: User | None = Depends(verify_database_backup_write_access),
    db: Session = Depends(get_db),
) -> DatabaseBackupRestoreEnvResponse:
    return build_database_backup_restore_env(db, node_id)


@router.post("/database-backups/nodes/{node_id}/mark-main-root", response_model=DatabaseBackupDetailResponse)
def mark_database_backup_node_main_root(
    node_id: str,
    auth_context: User | None = Depends(verify_database_backup_write_access),
    db: Session = Depends(get_db),
) -> DatabaseBackupDetailResponse:
    node, file_record = load_database_backup_zip_detail(db, node_id)
    node = mark_database_backup_main_root(db, node)
    return serialize_database_backup_detail(node, file_record)


@router.get("/database-backups/nodes/{node_id}/zip")
def download_database_backup_node_zip(
    node_id: str,
    _auth_context: User | None = Depends(verify_database_backup_download_access),
    db: Session = Depends(get_db),
) -> FileResponse:
    node, file_record = load_database_backup_zip_detail(db, node_id)
    path = Path(file_record.stored_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="备份 zip 文件不存在。")
    return _build_database_backup_zip_response(file_record, path)


@router.head("/database-backups/nodes/{node_id}/zip")
def head_database_backup_node_zip(
    node_id: str,
    _auth_context: User | None = Depends(verify_database_backup_download_access),
    db: Session = Depends(get_db),
) -> Response:
    _, file_record = load_database_backup_zip_detail(db, node_id)
    path = Path(file_record.stored_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="备份 zip 文件不存在。")
    return _build_database_backup_zip_response(file_record, path)
