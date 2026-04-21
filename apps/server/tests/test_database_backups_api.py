from fastapi.testclient import TestClient


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
