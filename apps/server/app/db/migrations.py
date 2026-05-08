from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.models import DatabaseBackupNode


DATABASE_BACKUP_NODE_COLUMNS = [
    "id",
    "name",
    "database_name",
    "odoo_version",
    "parent_id",
    "source_type",
    "zip_file_id",
    "node_kind",
    "snapshot_type",
    "domain",
    "requirement_title",
    "notion_url",
    "base_node_id",
    "git_branch",
    "git_commit",
    "metadata",
    "is_main_root",
    "created_by",
    "note",
    "created_at",
    "updated_at",
]


def migrate_database_backup_nodes_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if "database_backup_nodes" not in inspector.get_table_names():
        return

    with engine.begin() as connection:
        columns = {column["name"]: column for column in inspect(connection).get_columns("database_backup_nodes")}
        _add_missing_database_backup_columns(connection, columns)
        connection.execute(
            text(
                """
                UPDATE database_backup_nodes
                SET node_kind = 'snapshot'
                WHERE node_kind IS NULL OR node_kind = ''
                """
            )
        )

        columns = {column["name"]: column for column in inspect(connection).get_columns("database_backup_nodes")}
        zip_file = columns.get("zip_file_id")
        if zip_file is not None and zip_file.get("nullable") is False:
            if connection.dialect.name == "sqlite":
                _rebuild_sqlite_database_backup_nodes(connection)
            else:
                connection.execute(text("ALTER TABLE database_backup_nodes ALTER COLUMN zip_file_id DROP NOT NULL"))


def _add_missing_database_backup_columns(connection, columns: dict[str, dict]) -> None:
    column_sql = {
        "node_kind": "VARCHAR(50)",
        "snapshot_type": "VARCHAR(50)",
        "domain": "VARCHAR(255)",
        "requirement_title": "VARCHAR(500)",
        "notion_url": "VARCHAR(1000)",
        "base_node_id": "VARCHAR(36)",
        "git_branch": "VARCHAR(255)",
        "git_commit": "VARCHAR(255)",
        "metadata": "JSON",
    }
    for column_name, column_type in column_sql.items():
        if column_name not in columns:
            connection.execute(text(f'ALTER TABLE database_backup_nodes ADD COLUMN "{column_name}" {column_type}'))


def _rebuild_sqlite_database_backup_nodes(connection) -> None:
    connection.execute(text("PRAGMA foreign_keys=OFF"))
    try:
        connection.execute(text("ALTER TABLE database_backup_nodes RENAME TO database_backup_nodes_old"))
        DatabaseBackupNode.__table__.create(bind=connection, checkfirst=False)
        columns_csv = ", ".join(f'"{column}"' for column in DATABASE_BACKUP_NODE_COLUMNS)
        select_csv = ", ".join(
            "COALESCE(node_kind, 'snapshot')" if column == "node_kind" else f'"{column}"'
            for column in DATABASE_BACKUP_NODE_COLUMNS
        )
        connection.execute(
            text(
                f"""
                INSERT INTO database_backup_nodes ({columns_csv})
                SELECT {select_csv}
                FROM database_backup_nodes_old
                """
            )
        )
        connection.execute(text("DROP TABLE database_backup_nodes_old"))
    finally:
        connection.execute(text("PRAGMA foreign_keys=ON"))
