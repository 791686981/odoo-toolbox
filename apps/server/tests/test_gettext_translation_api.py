from pathlib import Path

from fastapi.testclient import TestClient


def test_gettext_translation_flow_supports_pot_upload_and_job_creation(tmp_path: Path) -> None:
    import io

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

        upload_response = client.post(
            "/api/files/upload",
            files={
                "file": (
                    "sample.pot",
                    io.BytesIO(
                        '\n'.join(
                            [
                                'msgid ""',
                                'msgstr ""',
                                '"Project-Id-Version: demo\\n"',
                                '',
                                'msgid "Save"',
                                'msgstr ""',
                            ]
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert upload_response.status_code == 200

        run_response = client.post(
            "/api/tools/gettext-translation/jobs",
            json={
                "uploaded_file_id": upload_response.json()["id"],
                "source_language": "en_US",
                "target_language": "zh_CN",
                "context_text": "统一使用 Odoo 后台常见术语。",
                "translation_mode": "blank",
                "chunk_size": 10,
                "concurrency": 1,
            },
        )

        assert run_response.status_code == 200
        assert run_response.json()["tool_id"] == "gettext-translation"
        assert run_response.json()["input_file_type"] == "pot"
        assert run_response.json()["total_entries"] == 1
