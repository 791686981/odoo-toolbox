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
        uploaded_file_id = upload_response.json()["id"]

        draft_response = client.post(
            "/api/tools/gettext-translation/context-draft",
            json={
                "uploaded_file_id": uploaded_file_id,
                "source_language": "en_US",
                "target_language": "zh_CN",
            },
        )
        assert draft_response.status_code == 200
        assert "Odoo" in draft_response.json()["background"]

        run_response = client.post(
            "/api/tools/gettext-translation/jobs",
            json={
                "uploaded_file_id": uploaded_file_id,
                "source_language": "en_US",
                "target_language": "zh_CN",
                "context_text": draft_response.json()["background"],
                "translation_mode": "blank",
                "chunk_size": 10,
                "concurrency": 1,
            },
        )

        assert run_response.status_code == 200
        assert run_response.json()["tool_id"] == "gettext-translation"
        assert run_response.json()["input_file_type"] == "pot"
        assert run_response.json()["context_text"] == draft_response.json()["background"]
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
            translated_plural_values=[],
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


def test_gettext_translation_flow_supports_plural_entry_edit_and_export(tmp_path: Path) -> None:
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
        GettextTranslationItemResponse.model_validate(
            {
                "entry_index": 1,
                "translated_value": "",
                "translated_plural_values": [
                    {"index": 0, "value": "文件"},
                    {"index": 1, "value": "多个文件"},
                ],
            }
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
                                    'msgid "File"',
                                    'msgid_plural "Files"',
                                    'msgstr[0] ""',
                                    'msgstr[1] ""',
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
                    "context_text": "统一使用 Odoo 文件管理相关术语。",
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
            assert entries[0]["translated_plural_values"] == {"0": "文件", "1": "多个文件"}

            patch_response = client.patch(
                f"/api/tools/gettext-translation/runs/{run_id}/entries/{entries[0]['id']}",
                json={"edited_value": "", "edited_plural_values": {"0": "文件", "1": "文件列表"}},
            )
            assert patch_response.status_code == 200
            assert patch_response.json()["edited_plural_values"] == {"0": "文件", "1": "文件列表"}

            export_response = client.post(f"/api/tools/gettext-translation/runs/{run_id}/export")
            assert export_response.status_code == 200
            file_id = export_response.json()["file_id"]

            download_response = client.get(f"/api/files/{file_id}/download")
            assert download_response.status_code == 200
            exported_text = download_response.content.decode("utf-8")
            assert 'msgstr[0] "文件"' in exported_text
            assert 'msgstr[1] "文件列表"' in exported_text
    finally:
        if original_translate_gettext_entries is None:
            delattr(openai_service, "translate_gettext_entries")
        else:
            openai_service.translate_gettext_entries = original_translate_gettext_entries


def test_gettext_translation_flow_supports_proofread_preview_for_normal_and_plural_entries(tmp_path: Path) -> None:
    import io

    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app
    from app.services.openai_service import (
        GettextProofreadItemResponse,
        GettextTranslationItemResponse,
        openai_service,
    )

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    original_translate_gettext_entries = getattr(openai_service, "translate_gettext_entries", None)
    original_proofread_gettext_entries = getattr(openai_service, "proofread_gettext_entries", None)
    openai_service.translate_gettext_entries = lambda system_prompt, user_prompt: [
        GettextTranslationItemResponse.model_validate(
            {
                "entry_index": 1,
                "translated_value": "保存",
                "translated_plural_values": [],
            }
        ),
        GettextTranslationItemResponse.model_validate(
            {
                "entry_index": 2,
                "translated_value": "",
                "translated_plural_values": [
                    {"index": 0, "value": "文件"},
                    {"index": 1, "value": "多个文件"},
                ],
            }
        ),
    ]
    openai_service.proofread_gettext_entries = lambda system_prompt, user_prompt: [
        GettextProofreadItemResponse.model_validate(
            {
                "entry_index": 1,
                "suggested_value": "保存按钮",
                "suggested_plural_values": [],
                "reason": "按钮文案更完整。",
            }
        ),
        GettextProofreadItemResponse.model_validate(
            {
                "entry_index": 2,
                "suggested_value": "",
                "suggested_plural_values": [
                    {"index": 0, "value": "文件"},
                    {"index": 1, "value": "文件列表"},
                ],
                "reason": "复数形式统一术语。",
            }
        ),
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
                                    '',
                                    'msgid "File"',
                                    'msgid_plural "Files"',
                                    'msgstr[0] ""',
                                    'msgstr[1] ""',
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
                    "context_text": "统一使用 Odoo 文件管理相关术语。",
                    "translation_mode": "blank",
                    "chunk_size": 10,
                    "concurrency": 1,
                },
            )
            assert run_response.status_code == 200
            run_id = run_response.json()["id"]
            assert run_response.json()["status"] == "completed"

            preview_response = client.post(f"/api/tools/gettext-translation/runs/{run_id}/proofread-preview")
            assert preview_response.status_code == 200
            payload = preview_response.json()
            assert payload["items"][0]["entry_index"] == 1
            assert payload["items"][0]["suggested_value"] == "保存按钮"
            assert payload["items"][0]["is_plural"] is False
            assert payload["items"][1]["entry_index"] == 2
            assert payload["items"][1]["suggested_plural_values"] == {"0": "文件", "1": "文件列表"}
            assert payload["items"][1]["current_plural_values"] == {"0": "文件", "1": "多个文件"}
            assert payload["items"][1]["is_plural"] is True
    finally:
        if original_translate_gettext_entries is None:
            delattr(openai_service, "translate_gettext_entries")
        else:
            openai_service.translate_gettext_entries = original_translate_gettext_entries

        if original_proofread_gettext_entries is None:
            delattr(openai_service, "proofread_gettext_entries")
        else:
            openai_service.proofread_gettext_entries = original_proofread_gettext_entries
