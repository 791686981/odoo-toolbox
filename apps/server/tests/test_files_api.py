import io

from fastapi.testclient import TestClient


def test_files_api_lists_user_uploads_and_generated_outputs(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database, session_scope
    from app.main import create_app
    from app.services.file_service import store_generated_file

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

        upload_response = client.post(
            "/api/files/upload",
            files={
                "file": (
                    "sample.csv",
                    io.BytesIO(b"module,type,name,res_id,src,value,comments\n"),
                    "text/csv",
                )
            },
        )
        assert upload_response.status_code == 200

        with session_scope() as db:
          store_generated_file(
              db,
              filename="report.csv",
              content=b"header\nvalue\n",
              mime_type="text/csv",
              username="admin",
          )

        files_response = client.get("/api/files")
        assert files_response.status_code == 200

        payload = files_response.json()
        assert [item["kind"] for item in payload] == ["generated", "upload"]
        assert [item["original_name"] for item in payload] == ["report.csv", "sample.csv"]
