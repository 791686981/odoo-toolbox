from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import DatabaseBackupNode, User
from app.schemas.database_backups import DatabaseBackupDetailResponse, DatabaseBackupTreeResponse
from app.services.database_backup_service import (
    build_database_backup_tree_response,
    create_database_backup_node,
    serialize_database_backup_detail,
)


router = APIRouter(tags=["database-backups"])


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
