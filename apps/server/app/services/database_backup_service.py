from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from email.utils import format_datetime
import hashlib
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4
import zipfile

from fastapi import HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import DatabaseBackupNode, UploadedFile
from app.schemas.database_backups import (
    DatabaseBackupDetailResponse,
    DatabaseBackupRestoreEnvResponse,
    DatabaseBackupTreeNodeResponse,
    DatabaseBackupTreeResponse,
    DatabaseBackupZipResponse,
    UatEnsureTreeResponse,
    UatSnapshotCreateResponse,
)


NODE_KIND_FOLDER = "folder"
NODE_KIND_SNAPSHOT = "snapshot"
SNAPSHOT_TYPES = {"baseline", "issue_reproduction", "regression", "ad_hoc"}
UAT_ROOT_NAME = "UAT"
UAT_DOMAINS = [
    "市场管理",
    "经营管理",
    "项目管理",
    "档案管理",
    "工时管理",
    "知识管理",
    "技术质量",
    "合同管理",
    "资质管理",
    "用章管理",
    "人力资源",
    "采购管理",
    "外部集成",
]


def _node_sort_key(node: DatabaseBackupNode) -> tuple[int, datetime, str]:
    created_at = node.created_at
    if created_at is None:
        created_at = datetime.min.replace(tzinfo=timezone.utc)
    kind_order = 0 if node.node_kind == NODE_KIND_FOLDER else 1
    return (kind_order, created_at, node.id)


def _metadata(node: DatabaseBackupNode) -> dict[str, Any]:
    return dict(node.node_metadata or {})


def _merge_metadata(existing: dict[str, Any] | None, patch: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(existing or {})
    if patch:
        merged.update(patch)
    return merged


def _zip_response(node: DatabaseBackupNode, file_record: UploadedFile | None) -> DatabaseBackupZipResponse | None:
    if file_record is None:
        return None
    return DatabaseBackupZipResponse(
        file_id=file_record.id,
        filename=file_record.original_name,
        size=file_record.size,
        mime_type=file_record.mime_type,
        sha256=file_record.sha256,
        download_url=f"/api/database-backups/nodes/{node.id}/zip",
    )


def _build_tree_node(
    node: DatabaseBackupNode,
    children_by_parent_id: dict[str | None, list[DatabaseBackupNode]],
    files_by_id: dict[str, UploadedFile],
) -> DatabaseBackupTreeNodeResponse:
    children = sorted(children_by_parent_id.get(node.id, []), key=_node_sort_key, reverse=True)
    file_record = files_by_id.get(node.zip_file_id or "")
    return DatabaseBackupTreeNodeResponse(
        id=node.id,
        name=node.name,
        database_name=node.database_name,
        odoo_version=node.odoo_version,
        parent_id=node.parent_id,
        source_type=node.source_type,
        node_kind=node.node_kind or NODE_KIND_SNAPSHOT,
        snapshot_type=node.snapshot_type,
        domain=node.domain,
        requirement_title=node.requirement_title,
        notion_url=node.notion_url,
        is_main_root=node.is_main_root,
        created_at=node.created_at,
        zip=_zip_response(node, file_record),
        children=[_build_tree_node(child, children_by_parent_id, files_by_id) for child in children],
    )


def build_database_backup_tree_response(
    nodes: Iterable[DatabaseBackupNode],
    files_by_id: dict[str, UploadedFile] | None = None,
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
    file_map = files_by_id or {}
    return DatabaseBackupTreeResponse(
        main_root_id=main_root.id if main_root is not None else None,
        items=[_build_tree_node(node, children_by_parent_id, file_map) for node in ordered_roots],
    )


def build_files_by_id(db: Session, nodes: Iterable[DatabaseBackupNode]) -> dict[str, UploadedFile]:
    file_ids = [node.zip_file_id for node in nodes if node.zip_file_id]
    if not file_ids:
        return {}
    files = db.execute(select(UploadedFile).where(UploadedFile.id.in_(file_ids))).scalars().all()
    return {file_record.id: file_record for file_record in files}


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


def _validate_folder_node(node: DatabaseBackupNode) -> None:
    if node.zip_file_id is not None:
        raise HTTPException(status_code=500, detail="目录节点不能绑定 zip 文件。")


def _validate_snapshot_node(node: DatabaseBackupNode) -> None:
    if node.zip_file_id is None:
        raise HTTPException(status_code=500, detail="快照节点必须绑定 zip 文件。")


def _validate_domain(domain: str) -> None:
    if domain not in UAT_DOMAINS:
        raise HTTPException(status_code=400, detail="domain 必须是标准 UAT 业务域，且不能是“模版”。")


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
        uploaded_file = _create_uploaded_file(db, upload=upload, destination=destination, size=size, sha256=sha256, username=username)

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
            node_kind=NODE_KIND_SNAPSHOT,
            snapshot_type="ad_hoc",
            is_main_root=is_main_root,
            created_by=username,
            note=note,
            node_metadata={},
        )
        _validate_snapshot_node(node)
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


def _create_uploaded_file(
    db: Session,
    *,
    upload: UploadFile,
    destination: Path,
    size: int,
    sha256: str,
    username: str,
) -> UploadedFile:
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
    return uploaded_file


def create_database_backup_folder(
    db: Session,
    *,
    name: str,
    parent_id: str | None,
    domain: str | None,
    requirement_title: str | None,
    notion_url: str | None,
    note: str,
    metadata: dict[str, Any] | None,
    username: str,
) -> DatabaseBackupNode:
    if parent_id is not None and db.get(DatabaseBackupNode, parent_id) is None:
        raise HTTPException(status_code=404, detail="父节点不存在。")
    if parent_id is None and name == UAT_ROOT_NAME:
        existing_uat_roots = _find_top_level_uat_folders(db)
        if existing_uat_roots:
            raise HTTPException(status_code=400, detail="顶层 UAT 目录已存在，请使用 /uat/ensure-tree 保持幂等。")

    node = DatabaseBackupNode(
        name=name,
        database_name="",
        odoo_version="",
        parent_id=parent_id,
        source_type="root" if parent_id is None else "branch",
        zip_file_id=None,
        node_kind=NODE_KIND_FOLDER,
        domain=domain,
        requirement_title=requirement_title,
        notion_url=notion_url,
        is_main_root=False,
        created_by=username,
        note=note,
        node_metadata=dict(metadata or {}),
    )
    _validate_folder_node(node)
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def serialize_database_backup_detail(
    node: DatabaseBackupNode,
    file_record: UploadedFile | None = None,
) -> DatabaseBackupDetailResponse:
    return DatabaseBackupDetailResponse(
        id=node.id,
        name=node.name,
        database_name=node.database_name,
        odoo_version=node.odoo_version,
        parent_id=node.parent_id,
        source_type=node.source_type,
        node_kind=node.node_kind or NODE_KIND_SNAPSHOT,
        snapshot_type=node.snapshot_type,
        domain=node.domain,
        requirement_title=node.requirement_title,
        notion_url=node.notion_url,
        base_node_id=node.base_node_id,
        git_branch=node.git_branch,
        git_commit=node.git_commit,
        metadata=_metadata(node),
        is_main_root=node.is_main_root,
        note=node.note,
        created_at=node.created_at,
        updated_at=node.updated_at,
        zip=_zip_response(node, file_record),
    )


def load_database_backup_node(
    db: Session,
    node_id: str,
) -> DatabaseBackupNode:
    node = db.get(DatabaseBackupNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="备份节点不存在。")
    return node


def load_database_backup_detail(
    db: Session,
    node_id: str,
) -> tuple[DatabaseBackupNode, UploadedFile | None]:
    node = load_database_backup_node(db, node_id)
    if node.node_kind == NODE_KIND_FOLDER:
        return node, None

    if node.zip_file_id is None:
        raise HTTPException(status_code=404, detail="备份 zip 文件不存在。")
    file_record = db.get(UploadedFile, node.zip_file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="备份 zip 文件不存在。")

    return node, file_record


def load_database_backup_zip_detail(
    db: Session,
    node_id: str,
) -> tuple[DatabaseBackupNode, UploadedFile]:
    node = load_database_backup_node(db, node_id)
    if node.node_kind != NODE_KIND_SNAPSHOT:
        raise HTTPException(status_code=400, detail="目录节点不能下载 zip。")
    if node.zip_file_id is None:
        raise HTTPException(status_code=404, detail="备份 zip 文件不存在。")
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
    notion_url: str | None,
    base_node_id: str | None,
    git_branch: str | None,
    git_commit: str | None,
    database_name: str | None,
    odoo_version: str | None,
    metadata: dict[str, Any] | None,
) -> DatabaseBackupNode:
    if name is not None:
        node.name = name
    if note is not None:
        node.note = note
    if notion_url is not None:
        node.notion_url = notion_url or None
    if base_node_id is not None:
        node.base_node_id = base_node_id or None
    if git_branch is not None:
        node.git_branch = git_branch or None
    if git_commit is not None:
        node.git_commit = git_commit or None
    if database_name is not None:
        node.database_name = database_name
    if odoo_version is not None:
        node.odoo_version = odoo_version
    if metadata is not None:
        node.node_metadata = _merge_metadata(node.node_metadata, metadata)
    db.commit()
    db.refresh(node)
    return node


def delete_database_backup_leaf_node(
    db: Session,
    node_id: str,
) -> None:
    node = load_database_backup_node(db, node_id)
    child_exists = db.execute(
        select(DatabaseBackupNode.id).where(DatabaseBackupNode.parent_id == node.id).limit(1),
    ).first()
    if child_exists:
        raise HTTPException(status_code=400, detail="只能删除没有子节点的备份节点。")

    file_record = None
    stored_path = None
    if node.node_kind == NODE_KIND_SNAPSHOT:
        if node.zip_file_id is None:
            raise HTTPException(status_code=404, detail="备份 zip 文件不存在。")
        file_record = db.get(UploadedFile, node.zip_file_id)
        if file_record is None:
            raise HTTPException(status_code=404, detail="备份 zip 文件不存在。")
        stored_path = Path(file_record.stored_path)

    try:
        db.delete(node)
        db.flush()
        if file_record is not None:
            db.delete(file_record)
        db.commit()
    except Exception:
        db.rollback()
        raise

    if stored_path is not None:
        stored_path.unlink(missing_ok=True)


def mark_database_backup_main_root(
    db: Session,
    node: DatabaseBackupNode,
) -> DatabaseBackupNode:
    if node.parent_id is not None:
        raise HTTPException(status_code=400, detail="只有根节点可以设置为主线节点。")
    if node.node_kind != NODE_KIND_SNAPSHOT:
        raise HTTPException(status_code=400, detail="只有快照节点可以设置为主线节点。")

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


def ensure_uat_tree(
    db: Session,
    *,
    domain: str,
    requirement_title: str,
    notion_url: str | None,
    metadata: dict[str, Any] | None,
    username: str,
) -> tuple[DatabaseBackupNode, DatabaseBackupNode, DatabaseBackupNode]:
    _validate_domain(domain)
    if not requirement_title.strip():
        raise HTTPException(status_code=400, detail="requirement_title 不能为空。")

    root = _ensure_uat_root(db, username=username)
    domain_nodes = {_domain_key(node): node for node in _list_uat_domain_nodes(db, root)}
    for standard_domain in UAT_DOMAINS:
        if standard_domain not in domain_nodes:
            domain_nodes[standard_domain] = _new_uat_domain_node(db, root, standard_domain, username)
        else:
            domain_nodes[standard_domain].name = standard_domain
            domain_nodes[standard_domain].domain = standard_domain
            domain_nodes[standard_domain].node_metadata = _merge_metadata(
                domain_nodes[standard_domain].node_metadata,
                {"purpose": "uat-domain"},
            )

    domain_node = domain_nodes[domain]
    requirement = _ensure_requirement_node(
        db,
        domain_node=domain_node,
        domain=domain,
        requirement_title=requirement_title.strip(),
        notion_url=notion_url,
        metadata=metadata,
        username=username,
    )
    db.commit()
    for node in [root, domain_node, requirement]:
        db.refresh(node)
    return root, domain_node, requirement


def _ensure_uat_root(db: Session, *, username: str) -> DatabaseBackupNode:
    roots = _find_top_level_uat_folders(db)
    purpose_roots = [node for node in roots if _metadata(node).get("purpose") == "uat-root"]
    if len(purpose_roots) > 1:
        raise HTTPException(status_code=400, detail="存在多个 UAT 根目录，请先清理重复目录。")
    root = purpose_roots[0] if purpose_roots else None
    if root is None and len(roots) == 1:
        root = roots[0]
    if root is None and len(roots) > 1:
        raise HTTPException(status_code=400, detail="存在多个顶层 UAT 目录，请先保留一个或标记 metadata.purpose=uat-root。")
    if root is not None:
        root.node_metadata = _merge_metadata(root.node_metadata, {"purpose": "uat-root"})
        return root

    root = DatabaseBackupNode(
        name=UAT_ROOT_NAME,
        database_name="",
        odoo_version="",
        parent_id=None,
        source_type="root",
        zip_file_id=None,
        node_kind=NODE_KIND_FOLDER,
        is_main_root=False,
        created_by=username,
        note="",
        node_metadata={"purpose": "uat-root"},
    )
    db.add(root)
    db.flush()
    return root


def _find_top_level_uat_folders(db: Session) -> list[DatabaseBackupNode]:
    return (
        db.execute(
            select(DatabaseBackupNode)
            .where(DatabaseBackupNode.parent_id.is_(None))
            .where(DatabaseBackupNode.node_kind == NODE_KIND_FOLDER)
            .where(DatabaseBackupNode.name == UAT_ROOT_NAME)
            .order_by(DatabaseBackupNode.created_at.asc(), DatabaseBackupNode.id.asc())
        )
        .scalars()
        .all()
    )


def _list_uat_domain_nodes(db: Session, root: DatabaseBackupNode) -> list[DatabaseBackupNode]:
    return (
        db.execute(
            select(DatabaseBackupNode)
            .where(DatabaseBackupNode.parent_id == root.id)
            .where(DatabaseBackupNode.node_kind == NODE_KIND_FOLDER)
        )
        .scalars()
        .all()
    )


def _domain_key(node: DatabaseBackupNode) -> str:
    return node.domain or node.name


def _new_uat_domain_node(
    db: Session,
    root: DatabaseBackupNode,
    domain: str,
    username: str,
) -> DatabaseBackupNode:
    node = DatabaseBackupNode(
        name=domain,
        database_name="",
        odoo_version="",
        parent_id=root.id,
        source_type="branch",
        zip_file_id=None,
        node_kind=NODE_KIND_FOLDER,
        domain=domain,
        is_main_root=False,
        created_by=username,
        note="",
        node_metadata={"purpose": "uat-domain"},
    )
    db.add(node)
    db.flush()
    return node


def _ensure_requirement_node(
    db: Session,
    *,
    domain_node: DatabaseBackupNode,
    domain: str,
    requirement_title: str,
    notion_url: str | None,
    metadata: dict[str, Any] | None,
    username: str,
) -> DatabaseBackupNode:
    query = (
        select(DatabaseBackupNode)
        .where(DatabaseBackupNode.parent_id == domain_node.id)
        .where(DatabaseBackupNode.node_kind == NODE_KIND_FOLDER)
        .where(DatabaseBackupNode.domain == domain)
    )
    normalized_notion_url = notion_url.strip() if notion_url else None
    if normalized_notion_url:
        query = query.where(DatabaseBackupNode.notion_url == normalized_notion_url)
    else:
        query = query.where(DatabaseBackupNode.requirement_title == requirement_title)

    node = db.execute(query).scalar_one_or_none()
    if node is None:
        node = DatabaseBackupNode(
            name=requirement_title,
            database_name="",
            odoo_version="",
            parent_id=domain_node.id,
            source_type="branch",
            zip_file_id=None,
            node_kind=NODE_KIND_FOLDER,
            domain=domain,
            requirement_title=requirement_title,
            notion_url=normalized_notion_url,
            is_main_root=False,
            created_by=username,
            note="",
            node_metadata=_merge_metadata({"purpose": "uat-requirement"}, metadata),
        )
        db.add(node)
        db.flush()
        return node

    node.name = requirement_title
    node.requirement_title = requirement_title
    if normalized_notion_url:
        node.notion_url = normalized_notion_url
    node.node_metadata = _merge_metadata(node.node_metadata, metadata)
    return node


def serialize_uat_ensure_tree_response(
    root: DatabaseBackupNode,
    domain_node: DatabaseBackupNode,
    requirement_node: DatabaseBackupNode,
) -> UatEnsureTreeResponse:
    return UatEnsureTreeResponse(
        root=serialize_database_backup_detail(root),
        domain_node=serialize_database_backup_detail(domain_node),
        requirement_node=serialize_database_backup_detail(requirement_node),
    )


def create_uat_snapshot(
    db: Session,
    *,
    domain: str,
    requirement_title: str,
    snapshot_name: str,
    snapshot_type: str,
    parent_id: str | None,
    notion_url: str | None,
    base_node_id: str | None,
    git_branch: str | None,
    git_commit: str | None,
    odoo_version: str,
    database_name: str,
    note: str,
    metadata: dict[str, Any] | None,
    upload: UploadFile,
    username: str,
) -> tuple[DatabaseBackupNode, UploadedFile, str]:
    _validate_domain(domain)
    if snapshot_type not in SNAPSHOT_TYPES:
        raise HTTPException(status_code=400, detail="snapshot_type 不合法。")
    if not snapshot_name.strip():
        raise HTTPException(status_code=400, detail="snapshot_name 不能为空。")

    if parent_id:
        parent = _load_uat_requirement_parent(
            db,
            parent_id,
            domain=domain,
            requirement_title=requirement_title,
            notion_url=notion_url,
        )
    else:
        _, _, parent = ensure_uat_tree(
            db,
            domain=domain,
            requirement_title=requirement_title,
            notion_url=notion_url,
            metadata=metadata,
            username=username,
        )

    ensure_database_backup_zip(upload)
    try:
        destination, size, sha256 = _store_database_backup_zip(upload)
        uploaded_file = _create_uploaded_file(db, upload=upload, destination=destination, size=size, sha256=sha256, username=username)
        node = DatabaseBackupNode(
            name=snapshot_name.strip(),
            database_name=database_name,
            odoo_version=odoo_version,
            parent_id=parent.id,
            source_type="branch",
            zip_file_id=uploaded_file.id,
            node_kind=NODE_KIND_SNAPSHOT,
            snapshot_type=snapshot_type,
            domain=domain,
            requirement_title=requirement_title.strip(),
            notion_url=notion_url.strip() if notion_url else None,
            base_node_id=base_node_id or None,
            git_branch=git_branch or None,
            git_commit=git_commit or None,
            is_main_root=False,
            created_by=username,
            note=note,
            node_metadata=_merge_metadata({"purpose": "uat-snapshot"}, metadata),
        )
        _validate_snapshot_node(node)
        db.add(node)
        db.flush()
        restore_env = build_restore_env_text(node)
        db.commit()
        db.refresh(node)
        return node, uploaded_file, restore_env
    except Exception:
        db.rollback()
        if "destination" in locals() and destination.exists():
            destination.unlink()
        raise


def _load_uat_requirement_parent(
    db: Session,
    parent_id: str,
    *,
    domain: str,
    requirement_title: str,
    notion_url: str | None,
) -> DatabaseBackupNode:
    parent = load_database_backup_node(db, parent_id)
    if parent.node_kind != NODE_KIND_FOLDER or not parent.requirement_title:
        raise HTTPException(status_code=400, detail="parent_id 必须是 UAT 需求目录节点。")
    if parent.domain != domain:
        raise HTTPException(status_code=400, detail="parent_id 与 domain 不匹配。")
    normalized_notion_url = notion_url.strip() if notion_url else None
    if normalized_notion_url and parent.notion_url and parent.notion_url != normalized_notion_url:
        raise HTTPException(status_code=400, detail="parent_id 与 notion_url 不匹配。")
    if not normalized_notion_url and parent.requirement_title != requirement_title:
        raise HTTPException(status_code=400, detail="parent_id 与 requirement_title 不匹配。")

    domain_node = load_database_backup_node(db, parent.parent_id or "")
    root = load_database_backup_node(db, domain_node.parent_id or "")
    if root.name != UAT_ROOT_NAME or root.node_kind != NODE_KIND_FOLDER:
        raise HTTPException(status_code=400, detail="parent_id 必须位于 UAT 树下。")
    if normalized_notion_url and not parent.notion_url:
        parent.notion_url = normalized_notion_url
    if normalized_notion_url and parent.requirement_title != requirement_title:
        parent.name = requirement_title
        parent.requirement_title = requirement_title
    return parent


def serialize_uat_snapshot_create_response(
    node: DatabaseBackupNode,
    file_record: UploadedFile,
    restore_env: str,
) -> UatSnapshotCreateResponse:
    return UatSnapshotCreateResponse(
        node_id=node.id,
        name=node.name,
        parent_id=node.parent_id or "",
        node_kind=NODE_KIND_SNAPSHOT,
        snapshot_type=node.snapshot_type or "ad_hoc",
        sha256=file_record.sha256,
        download_url=f"/api/database-backups/nodes/{node.id}/zip",
        restore_env=restore_env,
    )


def build_restore_env_text(node: DatabaseBackupNode) -> str:
    values = {
        "ODOO_RESTORE_NODE_ID": node.id,
        "ODOO_RESTORE_IF_EXISTS": "overwrite",
        "ODOO_RESTORE_NEUTRALIZE": "false",
    }
    if node.database_name:
        values["ODOO_RESTORE_TARGET_DB"] = node.database_name
    return "\n".join(f"{key}={value}" for key, value in values.items())


def build_database_backup_restore_env(
    db: Session,
    node_id: str,
) -> DatabaseBackupRestoreEnvResponse:
    node = load_database_backup_node(db, node_id)
    if node.node_kind != NODE_KIND_SNAPSHOT:
        raise HTTPException(status_code=400, detail="只有快照节点可以生成 Odoo 恢复环境变量。")
    if node.zip_file_id is None:
        raise HTTPException(status_code=404, detail="备份 zip 文件不存在。")
    restore_env = build_restore_env_text(node)
    values = dict(line.split("=", 1) for line in restore_env.splitlines())
    return DatabaseBackupRestoreEnvResponse(node_id=node.id, restore_env=restore_env, values=values)


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


def filter_uat_tree(nodes: Iterable[DatabaseBackupNode]) -> list[DatabaseBackupNode]:
    node_list = list(nodes)
    node_by_id = {node.id: node for node in node_list}
    root = next(
        (
            node
            for node in node_list
            if node.parent_id is None and node.node_kind == NODE_KIND_FOLDER and node.name == UAT_ROOT_NAME
        ),
        None,
    )
    if root is None:
        return []

    selected = []
    for node in node_list:
        cursor = node
        while cursor is not None:
            if cursor.id == root.id:
                selected.append(node)
                break
            cursor = node_by_id.get(cursor.parent_id or "")
    return selected
