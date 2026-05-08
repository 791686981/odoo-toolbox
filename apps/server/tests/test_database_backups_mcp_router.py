import io
import json
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select


def _zip_bytes(filename: str, content: bytes) -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, content)
    buffer.seek(0)
    return buffer


def test_prepare_uat_snapshot_upload_returns_rest_ready_metadata_without_creating_node(tmp_path) -> None:
    from app.core.config import settings
    from app.db import session as db_session
    from app.db.base import Base
    from app.db.session import configure_database, session_scope
    from app.models import DatabaseBackupNode
    from app.tools.database_backups.router import router

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    settings.database_backup_write_api_key = "write-test-key"
    configure_database()
    Base.metadata.create_all(bind=db_session.engine)

    app = FastAPI()
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/database-backups/prepare-uat-snapshot-upload",
            json={
                "domain": "项目管理",
                "requirement_title": "EPIC-04 WBS 拆解与执行任务基础",
                "snapshot_name": "基线快照 - 2026-05-08",
                "snapshot_type": "baseline",
                "notion_url": "https://notion.example/epic-04",
                "database_name": "uat_epic04",
                "metadata": {"阶段": "基线", "round": 1},
            },
        )

    assert response.status_code == 200
    guide = response.json()
    fields = guide["recommended_form_fields"]
    assert guide["upload_url"] == "/api/database-backups/uat/snapshots"
    assert fields["metadata"] == '{"阶段": "基线", "round": 1}'
    assert json.loads(fields["metadata"]) == {"阶段": "基线", "round": 1}
    assert fields["file"] == "<Odoo 原生数据库备份 zip>"

    with session_scope() as db:
        assert db.execute(select(DatabaseBackupNode)).scalars().all() == []

    rest_app = __import__("app.main", fromlist=["create_app"]).create_app()
    with TestClient(rest_app) as client:
        rest_fields = dict(fields)
        rest_fields.pop("file")
        upload_response = client.post(
            "/api/database-backups/uat/snapshots",
            data=rest_fields,
            files={"file": ("uat.zip", _zip_bytes("dump.sql", b"dump"), "application/zip")},
            headers={"Authorization": "Bearer write-test-key"},
        )

    assert upload_response.status_code == 200
    assert upload_response.json()["snapshot_type"] == "baseline"
