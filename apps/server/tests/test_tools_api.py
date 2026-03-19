from fastapi.testclient import TestClient


def test_tools_api_returns_manifests_from_registry(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app
    from app.tools.registry import list_tool_manifests

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

        tools_response = client.get("/api/tools")
        assert tools_response.status_code == 200
        assert tools_response.json() == list_tool_manifests()

        assert tools_response.json() == [
            {
                "id": "csv-translation",
                "title": "CSV 翻译",
                "description": "上传 Odoo CSV，生成背景说明、分块翻译、人工修订并导出结果。",
                "route": "/tools/csv-translation",
                "icon": "translation",
                "category": "translation",
                "enabled": True,
                "order": 10,
                "capabilities": ["upload", "translation", "proofread", "export"],
            }
        ]
