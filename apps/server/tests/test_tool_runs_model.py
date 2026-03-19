import hashlib

from fastapi.testclient import TestClient


def test_tool_run_and_tool_artifact_can_be_created(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database, session_scope
    from app.main import create_app
    from app.models import ToolArtifact, ToolRun, UploadedFile

    upload_path = tmp_path / "uploads" / "sample.csv"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_text("header\nvalue\n", encoding="utf-8")

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = "admin123456"
    configure_database()

    app = create_app()
    with TestClient(app):
        with session_scope() as db:
            file_record = UploadedFile(
                original_name="sample.csv",
                stored_path=str(upload_path),
                mime_type="text/csv",
                size=13,
                sha256=hashlib.sha256(b"header\nvalue\n").hexdigest(),
                created_by="admin",
            )
            db.add(file_record)
            db.flush()

            run = ToolRun(
                tool_id="csv-translation",
                status="completed",
                summary="CSV 翻译测试运行",
                created_by="admin",
                input_payload={"uploaded_file_id": file_record.id},
            )
            db.add(run)
            db.flush()

            artifact = ToolArtifact(
                run_id=run.id,
                kind="export",
                file_id=file_record.id,
                label="导出 CSV",
                artifact_metadata={"source": "test"},
            )
            db.add(artifact)
            db.flush()

            assert db.get(ToolRun, run.id) is not None
            stored_artifact = db.get(ToolArtifact, artifact.id)
            assert stored_artifact is not None
            assert stored_artifact.run_id == run.id
            assert stored_artifact.artifact_metadata == {"source": "test"}
