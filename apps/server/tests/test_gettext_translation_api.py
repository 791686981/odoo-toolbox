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


def test_gettext_translation_flow_supports_entry_edit_and_export(tmp_path: Path) -> None:
    import io

    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app
    from app.services.openai_service import GettextTranslationItemResponse, openai_service

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    original_translate_gettext_entries = getattr(openai_service, "translate_gettext_entries", None)
    openai_service.translate_gettext_entries = lambda system_prompt, user_prompt: [
        GettextTranslationItemResponse(
            entry_index=1,
            translated_value="保存",
            translated_plural_values={},
        )
    ]

    app = create_app()
    try:
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
            run_id = run_response.json()["id"]
            assert run_response.json()["status"] == "completed"

            entries_response = client.get(f"/api/tools/gettext-translation/runs/{run_id}/entries")
            assert entries_response.status_code == 200
            entries = entries_response.json()["items"]
            assert entries[0]["translated_value"] == "保存"

            patch_response = client.patch(
                f"/api/tools/gettext-translation/runs/{run_id}/entries/{entries[0]['id']}",
                json={"edited_value": "保存按钮", "edited_plural_values": {}},
            )
            assert patch_response.status_code == 200
            assert patch_response.json()["edited_value"] == "保存按钮"

            export_response = client.post(f"/api/tools/gettext-translation/runs/{run_id}/export")
            assert export_response.status_code == 200
            file_id = export_response.json()["file_id"]

            download_response = client.get(f"/api/files/{file_id}/download")
            assert download_response.status_code == 200
            assert 'msgstr "保存按钮"' in download_response.content.decode("utf-8")
    finally:
        if original_translate_gettext_entries is None:
            delattr(openai_service, "translate_gettext_entries")
        else:
            openai_service.translate_gettext_entries = original_translate_gettext_entries
