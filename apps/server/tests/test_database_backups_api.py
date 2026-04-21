import io
import zipfile

from fastapi.testclient import TestClient


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
        assert payload["items"][0]["children"] == [
            {
                "id": child_payload["id"],
                "name": "prod-main-branch",
                "database_name": "prod_main_branch",
                "odoo_version": "18.0",
                "parent_id": root_payload["id"],
                "source_type": "branch",
                "is_main_root": False,
                "created_at": child_payload["created_at"],
                "children": [],
            }
        ]


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

        forbidden_patch = client.patch(
            f"/api/database-backups/nodes/{first_root['id']}",
            json={"database_name": "should_fail"},
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
