import pytest
from fastapi.testclient import TestClient


def test_app_requires_admin_password_configuration(tmp_path) -> None:
    from app.core.config import settings
    from app.db.session import configure_database
    from app.main import create_app

    settings.database_url = f"sqlite:///{tmp_path / 'app.db'}"
    settings.upload_dir = tmp_path / "uploads"
    settings.output_dir = tmp_path / "outputs"
    settings.eager_tasks = True
    settings.admin_username = "admin"
    settings.admin_password = ""
    configure_database()

    app = create_app()

    with pytest.raises(RuntimeError, match="TOOLBOX_ADMIN_PASSWORD"):
        with TestClient(app):
            pass
