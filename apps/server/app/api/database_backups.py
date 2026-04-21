from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import DatabaseBackupNode, User
from app.schemas.database_backups import (
    DatabaseBackupDetailResponse,
    DatabaseBackupPatchRequest,
    DatabaseBackupTreeResponse,
)
from app.services.database_backup_service import (
    build_database_backup_tree_response,
    build_database_backup_zip_headers,
    create_database_backup_node,
    load_database_backup_detail,
    mark_database_backup_main_root,
    serialize_database_backup_detail,
    update_database_backup_detail,
)


router = APIRouter(tags=["database-backups"])


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
    return build_database_backup_tree_response(nodes)


@router.post("/database-backups/nodes", response_model=DatabaseBackupDetailResponse)
def create_database_backup_node_api(
    name: str = Form(...),
    database_name: str = Form(...),
    odoo_version: str = Form(...),
    source_type: str = Form(...),
    parent_id: str | None = Form(None),
    is_main_root: bool = Form(False),
    note: str = Form(""),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatabaseBackupDetailResponse:
    node, file_record = create_database_backup_node(
        db,
        name=name,
        database_name=database_name,
        odoo_version=odoo_version,
        source_type=source_type,
        parent_id=parent_id,
        is_main_root=is_main_root,
        note=note,
        upload=file,
        username=user.username,
    )
    return serialize_database_backup_detail(node, file_record)


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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatabaseBackupDetailResponse:
    if payload.model_extra:
        raise HTTPException(status_code=400, detail="只允许修改 name 和 note。")
    if payload.name is None and payload.note is None:
        raise HTTPException(status_code=400, detail="只允许修改 name 和 note。")

    node, file_record = load_database_backup_detail(db, node_id)
    node = update_database_backup_detail(db, node, name=payload.name, note=payload.note)
    return serialize_database_backup_detail(node, file_record)


@router.post("/database-backups/nodes/{node_id}/mark-main-root", response_model=DatabaseBackupDetailResponse)
def mark_database_backup_node_main_root(
    node_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatabaseBackupDetailResponse:
    node, file_record = load_database_backup_detail(db, node_id)
    node = mark_database_backup_main_root(db, node)
    return serialize_database_backup_detail(node, file_record)


@router.get("/database-backups/nodes/{node_id}/zip")
def download_database_backup_node_zip(
    node_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    node, file_record = load_database_backup_detail(db, node_id)
    path = Path(file_record.stored_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="备份 zip 文件不存在。")
    return _build_database_backup_zip_response(file_record, path)


@router.head("/database-backups/nodes/{node_id}/zip")
def head_database_backup_node_zip(
    node_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    _, file_record = load_database_backup_detail(db, node_id)
    path = Path(file_record.stored_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="备份 zip 文件不存在。")
    return _build_database_backup_zip_response(file_record, path)
