from __future__ import annotations

from collections import defaultdict
import hashlib
from email.utils import format_datetime
from datetime import datetime
from datetime import timezone
from pathlib import Path
from uuid import uuid4
import zipfile
from typing import Iterable

from fastapi import HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import DatabaseBackupNode
from app.models import UploadedFile
from app.schemas.database_backups import (
    DatabaseBackupDetailResponse,
    DatabaseBackupZipResponse,
    DatabaseBackupTreeNodeResponse,
    DatabaseBackupTreeResponse,
)


def _node_sort_key(node: DatabaseBackupNode) -> tuple[datetime, str]:
    created_at = node.created_at
    if created_at is None:
        created_at = datetime.min.replace(tzinfo=timezone.utc)
    return (created_at, node.id)


def _build_tree_node(
    node: DatabaseBackupNode,
    children_by_parent_id: dict[str | None, list[DatabaseBackupNode]],
) -> DatabaseBackupTreeNodeResponse:
    children = sorted(children_by_parent_id.get(node.id, []), key=_node_sort_key, reverse=True)
    return DatabaseBackupTreeNodeResponse(
        id=node.id,
        name=node.name,
        database_name=node.database_name,
        odoo_version=node.odoo_version,
        parent_id=node.parent_id,
        source_type=node.source_type,
        is_main_root=node.is_main_root,
        created_at=node.created_at,
        children=[_build_tree_node(child, children_by_parent_id) for child in children],
    )


def build_database_backup_tree_response(
    nodes: Iterable[DatabaseBackupNode],
) -> DatabaseBackupTreeResponse:
    node_list = list(nodes)
    if not node_list:
        return DatabaseBackupTreeResponse(main_root_id=None, items=[])

    children_by_parent_id: dict[str | None, list[DatabaseBackupNode]] = defaultdict(list)
    for node in node_list:
        children_by_parent_id[node.parent_id].append(node)

    roots = children_by_parent_id[None]
    main_roots = [node for node in roots if node.is_main_root]
    main_root = sorted(main_roots, key=_node_sort_key, reverse=True)[0] if main_roots else None
    other_roots = [node for node in roots if not node.is_main_root]
    other_roots = sorted(other_roots, key=_node_sort_key, reverse=True)

    ordered_roots = ([] if main_root is None else [main_root]) + other_roots
    return DatabaseBackupTreeResponse(
        main_root_id=main_root.id if main_root is not None else None,
        items=[_build_tree_node(node, children_by_parent_id) for node in ordered_roots],
    )


def ensure_database_backup_zip(upload: UploadFile) -> None:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix != ".zip":
        raise HTTPException(status_code=400, detail="数据库备份节点只接受 .zip 文件。")


def _store_database_backup_zip(upload: UploadFile) -> tuple[Path, int, str]:
    suffix = Path(upload.filename or "backup.zip").suffix or ".zip"
    stored_name = f"{uuid4()}{suffix}"
    destination = settings.upload_dir / stored_name
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    sha256 = hashlib.sha256()
    size = 0

    with destination.open("wb") as destination_file:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            destination_file.write(chunk)
            sha256.update(chunk)
            size += len(chunk)

    if not zipfile.is_zipfile(destination):
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="数据库备份节点只接受有效的 .zip 文件。")

    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            destination.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="数据库备份节点只接受有效的 .zip 文件。")

    return destination, size, sha256.hexdigest()


def create_database_backup_node(
    db: Session,
    *,
    name: str,
    database_name: str,
    odoo_version: str,
    source_type: str,
    parent_id: str | None,
    is_main_root: bool,
    note: str,
    upload: UploadFile,
    username: str,
) -> tuple[DatabaseBackupNode, UploadedFile]:
    ensure_database_backup_zip(upload)

    if parent_id is None:
        if source_type != "root":
            raise HTTPException(status_code=400, detail="根节点的 source_type 必须为 root。")
    else:
        parent = db.get(DatabaseBackupNode, parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="父节点不存在。")
        if source_type != "branch":
            raise HTTPException(status_code=400, detail="子节点的 source_type 必须为 branch。")
        if is_main_root:
            raise HTTPException(status_code=400, detail="子节点不能设置为主线节点。")

    try:
        destination, size, sha256 = _store_database_backup_zip(upload)

        uploaded_file = UploadedFile(
            original_name=upload.filename or "backup.zip",
            stored_path=str(destination),
            mime_type=upload.content_type or "application/zip",
            size=size,
            sha256=sha256,
            created_by=username,
        )
        db.add(uploaded_file)
        db.flush()

        if is_main_root:
            db.execute(
                update(DatabaseBackupNode)
                .where(DatabaseBackupNode.is_main_root.is_(True))
                .values(is_main_root=False)
            )

        node = DatabaseBackupNode(
            name=name,
            database_name=database_name,
            odoo_version=odoo_version,
            parent_id=parent_id,
            source_type=source_type,
            zip_file_id=uploaded_file.id,
            is_main_root=is_main_root,
            created_by=username,
            note=note,
        )
        db.add(node)
        db.flush()
        db.refresh(node)
        db.commit()
        return node, uploaded_file
    except Exception:
        db.rollback()
        if "destination" in locals() and destination.exists():
            destination.unlink()
        raise


def serialize_database_backup_detail(
    node: DatabaseBackupNode,
    file_record: UploadedFile,
) -> DatabaseBackupDetailResponse:
    return DatabaseBackupDetailResponse(
        id=node.id,
        name=node.name,
        database_name=node.database_name,
        odoo_version=node.odoo_version,
        parent_id=node.parent_id,
        source_type=node.source_type,
        is_main_root=node.is_main_root,
        note=node.note,
        created_at=node.created_at,
        updated_at=node.updated_at,
        zip=DatabaseBackupZipResponse(
            file_id=file_record.id,
            filename=file_record.original_name,
            size=file_record.size,
            mime_type=file_record.mime_type,
            sha256=file_record.sha256,
            download_url=f"/api/database-backups/nodes/{node.id}/zip",
        ),
    )


def load_database_backup_detail(
    db: Session,
    node_id: str,
) -> tuple[DatabaseBackupNode, UploadedFile]:
    node = db.get(DatabaseBackupNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="备份节点不存在。")

    file_record = db.get(UploadedFile, node.zip_file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="备份 zip 文件不存在。")

    return node, file_record


def update_database_backup_detail(
    db: Session,
    node: DatabaseBackupNode,
    *,
    name: str | None,
    note: str | None,
) -> DatabaseBackupNode:
    if name is not None:
        node.name = name
    if note is not None:
        node.note = note
    db.commit()
    db.refresh(node)
    return node


def delete_database_backup_leaf_node(
    db: Session,
    node_id: str,
) -> None:
    node, file_record = load_database_backup_detail(db, node_id)
    child_exists = db.execute(
        select(DatabaseBackupNode.id).where(DatabaseBackupNode.parent_id == node.id).limit(1),
    ).first()
    if child_exists:
        raise HTTPException(status_code=400, detail="只能删除没有子节点的备份节点。")

    stored_path = Path(file_record.stored_path)
    try:
        db.delete(node)
        db.flush()
        db.delete(file_record)
        db.commit()
    except Exception:
        db.rollback()
        raise

    stored_path.unlink(missing_ok=True)


def mark_database_backup_main_root(
    db: Session,
    node: DatabaseBackupNode,
) -> DatabaseBackupNode:
    if node.parent_id is not None:
        raise HTTPException(status_code=400, detail="只有根节点可以设置为主线节点。")

    db.execute(
        update(DatabaseBackupNode)
        .where(DatabaseBackupNode.is_main_root.is_(True))
        .where(DatabaseBackupNode.id != node.id)
        .values(is_main_root=False)
    )
    node.is_main_root = True
    db.commit()
    db.refresh(node)
    return node


def build_database_backup_zip_headers(
    file_record: UploadedFile,
    file_path: Path,
) -> dict[str, str]:
    stat_result = file_path.stat()
    last_modified = format_datetime(datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc), usegmt=True)
    return {
        "content-type": file_record.mime_type,
        "x-file-sha256": file_record.sha256,
        "content-length": str(file_record.size),
        "etag": f'"{file_record.sha256}"',
        "last-modified": last_modified,
    }
