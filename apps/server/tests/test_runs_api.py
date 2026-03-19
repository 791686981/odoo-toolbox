import io

from fastapi.testclient import TestClient


def test_runs_api_returns_platform_runs_for_current_user(tmp_path) -> None:
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

    original_translate_rows = openai_service.translate_rows
    openai_service.translate_rows = lambda system_prompt, user_prompt: [
        TranslationItemResponse(row_number=1, translated_value="报价单"),
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
                            ).encode("utf-8")
                        ),
                        "text/csv",
                    )
                },
            )
            assert upload_response.status_code == 200
            uploaded_file_id = upload_response.json()["id"]

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

            runs_response = client.get("/api/runs")
            assert runs_response.status_code == 200
            assert runs_response.json() == [
                {
                    "id": job_response.json()["id"],
                    "tool_id": "csv-translation",
                    "status": "completed",
                    "summary": "sample.csv · en_US → zh_CN",
                    "error_message": "",
                    "created_at": runs_response.json()[0]["created_at"],
                    "updated_at": runs_response.json()[0]["updated_at"],
                }
            ]
    finally:
        openai_service.translate_rows = original_translate_rows
