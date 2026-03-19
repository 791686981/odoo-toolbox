from pathlib import Path


def test_settings_no_longer_expose_fake_openai_switch() -> None:
    from app.core.config import settings

    assert not hasattr(settings, "use_fake_openai")


def test_parse_odoo_csv_preserves_multiline_and_metadata(tmp_path: Path) -> None:
    source = tmp_path / "sample.csv"
    source.write_text(
        "\n".join(
            [
                "module,type,name,res_id,src,value,comments",
                'document_page,model,"ir.model.fields,help",field_1,"Line 1',
                'Line 2",,',
                'document_page,model,"ir.model.fields,field_description",field_2,Title,,',
            ]
        ),
        encoding="utf-8",
    )

    from app.tools.csv_translation.parser import parse_odoo_csv

    parsed = parse_odoo_csv(source)

    assert parsed.headers == [
        "module",
        "type",
        "name",
        "res_id",
        "src",
        "value",
        "comments",
    ]
    assert len(parsed.rows) == 2
    assert parsed.rows[0].row_number == 1
    assert parsed.rows[0].data["src"] == "Line 1\nLine 2"
    assert parsed.rows[1].data["module"] == "document_page"


def test_build_context_draft_uses_headers_and_sample_rows() -> None:
    from app.tools.csv_translation.context_builder import build_context_draft
    from app.tools.csv_translation.parser import ParsedCsv, ParsedCsvRow
    from app.services.openai_service import openai_service

    parsed = ParsedCsv(
        headers=["module", "type", "name", "res_id", "src", "value", "comments"],
        rows=[
            ParsedCsvRow(
                row_number=1,
                data={
                    "module": "sale",
                    "type": "model",
                    "name": "ir.model.fields,field_description",
                    "res_id": "sale.field_order_name",
                    "src": "Quotation",
                    "value": "",
                    "comments": "",
                },
            ),
            ParsedCsvRow(
                row_number=2,
                data={
                    "module": "sale",
                    "type": "model_terms",
                    "name": "ir.actions.act_window,help",
                    "res_id": "sale.action_orders",
                    "src": "Create a new quotation to start selling.",
                    "value": "",
                    "comments": "",
                },
            ),
        ],
    )

    calls: dict[str, str] = {}
    original_create_context_draft = openai_service.create_context_draft
    openai_service.create_context_draft = lambda system_prompt, user_prompt: (
        calls.update({"system_prompt": system_prompt, "user_prompt": user_prompt})
        or "这是一个 Odoo 销售模块翻译任务，请统一术语。"
    )

    try:
        draft = build_context_draft(parsed, source_language="en_US", target_language="zh_CN")
    finally:
        openai_service.create_context_draft = original_create_context_draft

    assert "Odoo" in draft
    assert "sale" in calls["user_prompt"]
    assert "en_US" in calls["user_prompt"]
    assert "zh_CN" in calls["user_prompt"]
    assert "Quotation" in calls["user_prompt"]


def test_build_translation_chunks_skips_existing_values_by_default() -> None:
    from app.tools.csv_translation.parser import ParsedCsv, ParsedCsvRow
    from app.tools.csv_translation.task_runner import build_translation_chunks

    parsed = ParsedCsv(
        headers=["module", "src", "value"],
        rows=[
            ParsedCsvRow(row_number=1, data={"module": "sale", "src": "Quotation", "value": ""}),
            ParsedCsvRow(row_number=2, data={"module": "sale", "src": "Order", "value": "订单"}),
            ParsedCsvRow(row_number=3, data={"module": "sale", "src": "Invoice", "value": ""}),
        ],
    )

    chunks = build_translation_chunks(parsed, chunk_size=1, overwrite_existing=False)

    assert len(chunks) == 2
    assert [item.row_number for item in chunks[0]] == [1]
    assert [item.row_number for item in chunks[1]] == [3]


def test_export_csv_prefers_manual_edits_and_preserves_original_columns() -> None:
    from app.tools.csv_translation.exporter import export_translated_csv
    from app.tools.csv_translation.parser import ParsedCsv, ParsedCsvRow

    parsed = ParsedCsv(
        headers=["module", "src", "value", "comments"],
        rows=[
            ParsedCsvRow(
                row_number=1,
                data={"module": "sale", "src": "Quotation", "value": "", "comments": ""},
            ),
            ParsedCsvRow(
                row_number=2,
                data={"module": "sale", "src": "Order", "value": "订单", "comments": "keep"},
            ),
        ],
    )

    content = export_translated_csv(
        parsed,
        row_results={
            1: {"translated_value": "报价单", "edited_value": ""},
            2: {"translated_value": "订单", "edited_value": "销售订单"},
        },
    )

    lines = content.decode("utf-8-sig").splitlines()
    assert lines[0] == "module,src,value,comments"
    assert "sale,Quotation,报价单," in lines[1]
    assert "sale,Order,销售订单,keep" in lines[2]


def test_api_translation_flow_supports_context_job_edit_and_export(tmp_path: Path) -> None:
    import io

    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app
    from app.services.openai_service import TranslationItemResponse, openai_service

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    original_create_context_draft = openai_service.create_context_draft
    original_translate_rows = openai_service.translate_rows
    openai_service.create_context_draft = lambda system_prompt, user_prompt: (
        "这是一个 Odoo 导出的多语言翻译 CSV，建议保持术语统一，并优先使用业务界面中自然的中文表达。"
    )
    openai_service.translate_rows = lambda system_prompt, user_prompt: [
        TranslationItemResponse(row_number=1, translated_value="报价单"),
        TranslationItemResponse(row_number=2, translated_value="订单"),
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
                        "sample.csv",
                        io.BytesIO(
                            (
                                "module,type,name,res_id,src,value,comments\n"
                                "sale,model,field_1,res_1,Quotation,,\n"
                                "sale,model,field_2,res_2,Order,,\n"
                            ).encode("utf-8")
                        ),
                        "text/csv",
                    )
                },
            )
            assert upload_response.status_code == 200
            uploaded_file_id = upload_response.json()["id"]

            draft_response = client.post(
                "/api/tools/csv-translation/context-draft",
                json={
                    "uploaded_file_id": uploaded_file_id,
                    "source_language": "en_US",
                    "target_language": "zh_CN",
                },
            )
            assert draft_response.status_code == 200
            assert "Odoo" in draft_response.json()["background"]

            job_response = client.post(
                "/api/tools/csv-translation/jobs",
                json={
                    "uploaded_file_id": uploaded_file_id,
                    "source_language": "en_US",
                    "target_language": "zh_CN",
                    "background_context": "这是一个销售模块翻译任务。",
                    "chunk_size": 1,
                    "concurrency": 1,
                    "overwrite_existing": False,
                },
            )
            assert job_response.status_code == 200
            job_id = job_response.json()["id"]
            assert job_response.json()["status"] == "completed"

            rows_response = client.get(f"/api/jobs/{job_id}/rows")
            assert rows_response.status_code == 200
            rows = rows_response.json()["items"]
            assert rows[0]["translated_value"] == "报价单"

            patch_response = client.patch(
                f"/api/jobs/{job_id}/rows/{rows[0]['id']}",
                json={"edited_value": "报价单（人工校对）"},
            )
            assert patch_response.status_code == 200
            assert patch_response.json()["edited_value"] == "报价单（人工校对）"

            export_response = client.post(f"/api/jobs/{job_id}/export")
            assert export_response.status_code == 200
            file_id = export_response.json()["file_id"]

            download_response = client.get(f"/api/files/{file_id}/download")
            assert download_response.status_code == 200
            content = download_response.content.decode("utf-8-sig")
            assert "报价单（人工校对）" in content
    finally:
        openai_service.create_context_draft = original_create_context_draft
        openai_service.translate_rows = original_translate_rows
