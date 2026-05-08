import io
import sqlite3
import zipfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_optional_api_keys():
    from app.core.config import settings

    settings.mcp_api_key = ""
    settings.download_api_key = ""
    settings.database_backup_write_api_key = ""
    yield
    settings.mcp_api_key = ""
    settings.download_api_key = ""
    settings.database_backup_write_api_key = ""


def _zip_bytes(filename: str, content: bytes) -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, content)
    buffer.seek(0)
    return buffer


def test_database_backups_tree_returns_empty_state(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123456"},
        )
        assert login_response.status_code == 200

        response = client.get("/api/database-backups/tree")

        assert response.status_code == 200
        assert response.json() == {"main_root_id": None, "items": []}


def test_database_backup_node_create_defaults_database_name_and_version(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123456"},
        )
        assert login_response.status_code == 200

        response = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "prod-main-20260422",
                "source_type": "root",
                "is_main_root": "true",
                "note": "main root",
            },
            files={"file": ("prod-main.zip", _zip_bytes("root.txt", b"root-bytes"), "application/zip")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["database_name"] == "prod-main-20260422"
        assert payload["odoo_version"] == ""


def test_database_backup_node_create_root_and_child_populates_tree(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123456"},
        )
        assert login_response.status_code == 200

        root_response = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "prod-main",
                "database_name": "prod_main",
                "odoo_version": "18.0",
                "source_type": "root",
                "is_main_root": "true",
                "note": "main root",
            },
            files={"file": ("prod-main.zip", _zip_bytes("root.txt", b"root-bytes"), "application/zip")},
        )
        assert root_response.status_code == 200
        root_payload = root_response.json()
        assert root_payload["zip"]["download_url"] == f"/api/database-backups/nodes/{root_payload['id']}/zip"

        child_response = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "prod-main-branch",
                "database_name": "prod_main_branch",
                "odoo_version": "18.0",
                "source_type": "branch",
                "parent_id": root_payload["id"],
                "is_main_root": "false",
                "note": "child branch",
            },
            files={
                "file": (
                    "prod-main-branch.zip",
                    _zip_bytes("child.txt", b"child-bytes"),
                    "application/zip",
                )
            },
        )
        assert child_response.status_code == 200
        child_payload = child_response.json()
        assert child_payload["parent_id"] == root_payload["id"]

        tree_response = client.get("/api/database-backups/tree")
        assert tree_response.status_code == 200
        payload = tree_response.json()
        assert payload["main_root_id"] == root_payload["id"]
        assert len(payload["items"]) == 1
        assert payload["items"][0]["id"] == root_payload["id"]
        child_tree = payload["items"][0]["children"][0]
        assert child_tree["id"] == child_payload["id"]
        assert child_tree["name"] == "prod-main-branch"
        assert child_tree["node_kind"] == "snapshot"
        assert child_tree["zip"]["download_url"] == f"/api/database-backups/nodes/{child_payload['id']}/zip"
        assert child_tree["children"] == []


def test_database_backup_node_rejects_non_zip_upload(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123456"},
        )
        assert login_response.status_code == 200

        response = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "bad-upload",
                "database_name": "bad_upload",
                "odoo_version": "18.0",
                "source_type": "root",
                "is_main_root": "true",
                "note": "",
            },
            files={"file": ("bad-upload.zip", io.BytesIO(b"not zip"), "application/zip")},
        )

        assert response.status_code == 400
        assert "zip" in response.json()["detail"].lower()


def test_database_backup_node_rejects_missing_parent(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123456"},
        )
        assert login_response.status_code == 200

        response = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "orphan",
                "database_name": "orphan_db",
                "odoo_version": "18.0",
                "source_type": "branch",
                "parent_id": "missing-parent",
                "is_main_root": "false",
                "note": "orphan branch",
            },
            files={"file": ("orphan.zip", _zip_bytes("orphan.txt", b"branch-bytes"), "application/zip")},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "父节点不存在。"


def test_database_backup_node_delete_allows_leaf_only(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123456"},
        )
        assert login_response.status_code == 200

        root_response = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "prod-main",
                "source_type": "root",
                "is_main_root": "true",
                "note": "main root",
            },
            files={"file": ("prod-main.zip", _zip_bytes("root.txt", b"root-bytes"), "application/zip")},
        )
        assert root_response.status_code == 200
        root_payload = root_response.json()

        child_response = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "prod-main-leaf",
                "source_type": "branch",
                "parent_id": root_payload["id"],
                "is_main_root": "false",
                "note": "leaf branch",
            },
            files={"file": ("prod-main-leaf.zip", _zip_bytes("leaf.txt", b"leaf-bytes"), "application/zip")},
        )
        assert child_response.status_code == 200
        child_payload = child_response.json()

        blocked_response = client.delete(f"/api/database-backups/nodes/{root_payload['id']}")
        assert blocked_response.status_code == 400
        assert blocked_response.json()["detail"] == "只能删除没有子节点的备份节点。"

        delete_response = client.delete(f"/api/database-backups/nodes/{child_payload['id']}")
        assert delete_response.status_code == 204

        tree_response = client.get("/api/database-backups/tree")
        assert tree_response.status_code == 200
        assert tree_response.json()["items"][0]["children"] == []

        zip_response = client.get(f"/api/database-backups/nodes/{child_payload['id']}/zip")
        assert zip_response.status_code == 404


def test_database_backups_detail_patch_mark_main_root_and_zip_download(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123456"},
        )
        assert login_response.status_code == 200

        first_root_response = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "prod-main-a",
                "database_name": "prod_main_a",
                "odoo_version": "18.0",
                "source_type": "root",
                "is_main_root": "true",
                "note": "A",
            },
            files={"file": ("prod-main-a.zip", _zip_bytes("a.txt", b"a-bytes"), "application/zip")},
        )
        assert first_root_response.status_code == 200
        first_root = first_root_response.json()

        second_root_response = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "prod-main-b",
                "database_name": "prod_main_b",
                "odoo_version": "18.0",
                "source_type": "root",
                "is_main_root": "false",
                "note": "B",
            },
            files={"file": ("prod-main-b.zip", _zip_bytes("b.txt", b"b-bytes"), "application/zip")},
        )
        assert second_root_response.status_code == 200
        second_root = second_root_response.json()

        detail_response = client.get(f"/api/database-backups/nodes/{first_root['id']}")
        assert detail_response.status_code == 200
        assert detail_response.json()["zip"]["download_url"] == f"/api/database-backups/nodes/{first_root['id']}/zip"

        patch_response = client.patch(
            f"/api/database-backups/nodes/{first_root['id']}",
            json={"name": "prod-main-a-renamed", "note": "updated"},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["name"] == "prod-main-a-renamed"
        assert patch_response.json()["note"] == "updated"

        metadata_patch = client.patch(
            f"/api/database-backups/nodes/{first_root['id']}",
            json={"database_name": "prod_main_a_renamed", "metadata": {"phase": "uat"}},
        )
        assert metadata_patch.status_code == 200
        assert metadata_patch.json()["database_name"] == "prod_main_a_renamed"
        assert metadata_patch.json()["metadata"] == {"phase": "uat"}

        forbidden_patch = client.patch(
            f"/api/database-backups/nodes/{first_root['id']}",
            json={"parent_id": "should_fail"},
        )
        assert forbidden_patch.status_code == 400

        mark_response = client.post(f"/api/database-backups/nodes/{second_root['id']}/mark-main-root")
        assert mark_response.status_code == 200
        assert mark_response.json()["is_main_root"] is True

        tree_response = client.get("/api/database-backups/tree")
        assert tree_response.status_code == 200
        assert tree_response.json()["main_root_id"] == second_root["id"]

        zip_response = client.get(f"/api/database-backups/nodes/{first_root['id']}/zip")
        assert zip_response.status_code == 200
        assert zip_response.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(zip_response.content)) as archive:
            assert archive.read("a.txt") == b"a-bytes"

        head_response = client.head(f"/api/database-backups/nodes/{first_root['id']}/zip")
        assert head_response.status_code == 200
        assert head_response.headers["content-type"] == "application/zip"
        assert head_response.headers["x-file-sha256"] == detail_response.json()["zip"]["sha256"]
        assert head_response.headers["etag"] == f'"{detail_response.json()["zip"]["sha256"]}"'
        assert head_response.headers["last-modified"]
        assert head_response.headers["content-length"] == str(len(zip_response.content))


def test_database_backup_zip_download_supports_bearer_token(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    settings.download_api_key = "download-test-key"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        login_response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123456"},
        )
        assert login_response.status_code == 200

        root_response = client.post(
            "/api/database-backups/nodes",
            data={
                "name": "prod-main-token",
                "source_type": "root",
                "is_main_root": "true",
                "note": "token download",
            },
            files={"file": ("prod-main-token.zip", _zip_bytes("token.txt", b"token-bytes"), "application/zip")},
        )
        assert root_response.status_code == 200
        root_payload = root_response.json()

        client.cookies.clear()

        zip_response = client.get(
            f"/api/database-backups/nodes/{root_payload['id']}/zip",
            headers={"Authorization": "Bearer download-test-key"},
        )
        assert zip_response.status_code == 200
        assert zip_response.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(zip_response.content)) as archive:
            assert archive.read("token.txt") == b"token-bytes"

        head_response = client.head(
            f"/api/database-backups/nodes/{root_payload['id']}/zip",
            headers={"Authorization": "Bearer download-test-key"},
        )
        assert head_response.status_code == 200
        assert head_response.headers["content-type"] == "application/zip"


def test_database_backup_folder_detail_download_restore_and_delete_rules(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "admin123456"}).status_code == 200

        root_response = client.post("/api/database-backups/folders", json={"name": "UAT"})
        assert root_response.status_code == 200
        root = root_response.json()
        assert root["node_kind"] == "folder"
        assert root["zip"] is None

        child_response = client.post(
            "/api/database-backups/folders",
            json={"name": "项目管理", "parent_id": root["id"], "domain": "项目管理"},
        )
        assert child_response.status_code == 200
        child = child_response.json()

        assert client.delete(f"/api/database-backups/nodes/{root['id']}").status_code == 400
        assert client.get(f"/api/database-backups/nodes/{root['id']}/zip").status_code == 400
        assert client.post(f"/api/database-backups/nodes/{root['id']}/restore-env").status_code == 400

        assert client.delete(f"/api/database-backups/nodes/{child['id']}").status_code == 204
        assert client.delete(f"/api/database-backups/nodes/{root['id']}").status_code == 204


def test_database_backup_write_endpoints_support_cookie_and_bearer_token(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    settings.database_backup_write_api_key = "write-test-key"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        unauthenticated = client.post("/api/database-backups/folders", json={"name": "nope"})
        assert unauthenticated.status_code == 401

        token_response = client.post(
            "/api/database-backups/folders",
            json={"name": "token-folder"},
            headers={"Authorization": "Bearer write-test-key"},
        )
        assert token_response.status_code == 200
        assert token_response.json()["created_at"]

        assert client.post("/api/auth/login", json={"username": "admin", "password": "admin123456"}).status_code == 200
        cookie_response = client.post("/api/database-backups/folders", json={"name": "cookie-folder"})
        assert cookie_response.status_code == 200
        assert cookie_response.json()["name"] == "cookie-folder"


def test_uat_ensure_tree_is_idempotent_by_notion_url_and_merges_metadata(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "admin123456"}).status_code == 200

        first = client.post(
            "/api/database-backups/uat/ensure-tree",
            json={
                "domain": "项目管理",
                "requirement_title": "EPIC-04 WBS 拆解与执行任务基础",
                "notion_url": "https://notion.example/epic-04",
                "metadata": {"epic": "04"},
            },
        )
        assert first.status_code == 200
        first_payload = first.json()
        requirement_id = first_payload["requirement_node"]["id"]

        second = client.post(
            "/api/database-backups/uat/ensure-tree",
            json={
                "domain": "项目管理",
                "requirement_title": "EPIC-04 WBS 拆解与任务基础",
                "notion_url": "https://notion.example/epic-04",
                "metadata": {"priority": "high"},
            },
        )
        assert second.status_code == 200
        second_requirement = second.json()["requirement_node"]
        assert second_requirement["id"] == requirement_id
        assert second_requirement["requirement_title"] == "EPIC-04 WBS 拆解与任务基础"
        assert second_requirement["metadata"]["epic"] == "04"
        assert second_requirement["metadata"]["priority"] == "high"

        tree = client.get("/api/database-backups/tree").json()
        uat_root = next(node for node in tree["items"] if node["name"] == "UAT")
        assert {node["name"] for node in uat_root["children"]} >= {
            "市场管理",
            "经营管理",
            "项目管理",
            "采购管理",
            "外部集成",
        }
        assert len(uat_root["children"]) == 13

        invalid = client.post(
            "/api/database-backups/uat/ensure-tree",
            json={"domain": "模版", "requirement_title": "模板需求"},
        )
        assert invalid.status_code == 400


def test_uat_root_duplicate_creation_is_blocked_and_ensure_tree_reports_clear_error(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database, session_scope
    from app.main import create_app
    from app.models import DatabaseBackupNode

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "admin123456"}).status_code == 200

        root_response = client.post("/api/database-backups/folders", json={"name": "UAT"})
        assert root_response.status_code == 200
        duplicate_response = client.post("/api/database-backups/folders", json={"name": "UAT"})
        assert duplicate_response.status_code == 400

    with session_scope() as db:
        db.add(
            DatabaseBackupNode(
                name="UAT",
                database_name="",
                odoo_version="",
                parent_id=None,
                source_type="root",
                zip_file_id=None,
                node_kind="folder",
                is_main_root=False,
                created_by="legacy",
                note="duplicate",
                node_metadata={},
            )
        )

    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "admin123456"}).status_code == 200
        ensure_response = client.post(
            "/api/database-backups/uat/ensure-tree",
            json={"domain": "项目管理", "requirement_title": "EPIC-04"},
        )
        assert ensure_response.status_code == 400
        assert "多个顶层 UAT" in ensure_response.json()["detail"]


def test_uat_snapshot_upload_download_and_restore_env(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "admin123456"}).status_code == 200

        response = client.post(
            "/api/database-backups/uat/snapshots",
            data={
                "domain": "项目管理",
                "requirement_title": "EPIC-04 WBS 拆解与执行任务基础",
                "snapshot_name": "基线快照 - 2026-05-08",
                "snapshot_type": "baseline",
                "notion_url": "https://notion.example/epic-04",
                "database_name": "uat_epic04",
                "odoo_version": "18.0",
                "metadata": '{"round":"baseline"}',
            },
            files={"file": ("uat.zip", _zip_bytes("dump.sql", b"dump"), "application/zip")},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["node_kind"] == "snapshot"
        assert payload["snapshot_type"] == "baseline"
        assert "ODOO_RESTORE_NODE_ID=" in payload["restore_env"]
        assert "ODOO_RESTORE_TARGET_DB=uat_epic04" in payload["restore_env"]

        node_id = payload["node_id"]
        detail = client.get(f"/api/database-backups/nodes/{node_id}")
        assert detail.status_code == 200
        assert detail.json()["metadata"]["round"] == "baseline"

        restore = client.post(f"/api/database-backups/nodes/{node_id}/restore-env")
        assert restore.status_code == 200
        assert restore.json()["values"]["ODOO_RESTORE_TARGET_DB"] == "uat_epic04"

        head = client.head(f"/api/database-backups/nodes/{node_id}/zip")
        assert head.status_code == 200
        assert head.headers["x-file-sha256"] == payload["sha256"]


def test_legacy_database_backup_schema_migrates_existing_nodes(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    db_path = tmp_path / "legacy.db"
    settings.database_url = f"sqlite:///{db_path}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    settings.upload_dir.mkdir(parents=True)
    backup_path = settings.upload_dir / "legacy.zip"
    backup_bytes = _zip_bytes("legacy.txt", b"legacy").getvalue()
    backup_path.write_bytes(backup_bytes)

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE uploaded_files (
                id VARCHAR(36) PRIMARY KEY,
                original_name VARCHAR(255) NOT NULL,
                stored_path VARCHAR(500) NOT NULL,
                mime_type VARCHAR(255) NOT NULL,
                size INTEGER NOT NULL,
                sha256 VARCHAR(64) NOT NULL,
                created_by VARCHAR(100) NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE database_backup_nodes (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                database_name VARCHAR(255) NOT NULL,
                odoo_version VARCHAR(50) NOT NULL,
                parent_id VARCHAR(36),
                source_type VARCHAR(50) NOT NULL,
                zip_file_id VARCHAR(36) NOT NULL,
                is_main_root BOOLEAN NOT NULL,
                created_by VARCHAR(100) NOT NULL,
                note TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO uploaded_files VALUES (
                'file-1', 'legacy.zip', ?, 'application/zip', ?, 'sha-legacy',
                'admin', '2026-05-08 00:00:00'
            )
            """,
            (str(backup_path), len(backup_bytes)),
        )
        connection.execute(
            """
            INSERT INTO database_backup_nodes VALUES (
                'node-1', 'legacy-node', 'legacy_db', '18.0', NULL, 'root',
                'file-1', 1, 'admin', 'legacy', '2026-05-08 00:00:00',
                '2026-05-08 00:00:00'
            )
            """
        )
        connection.commit()
    finally:
        connection.close()

    configure_database()
    app = create_app()
    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "admin123456"}).status_code == 200
        detail = client.get("/api/database-backups/nodes/node-1")
        assert detail.status_code == 200
        assert detail.json()["node_kind"] == "snapshot"
        assert detail.json()["zip"]["filename"] == "legacy.zip"
