from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from datetime import timezone
from typing import Iterable

from app.models import DatabaseBackupNode
from app.schemas.database_backups import (
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
