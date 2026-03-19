from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.platform.runs import router as platform_runs_router
from app.api.auth import router as auth_router
from app.api.files import router as files_router
from app.api.jobs import router as jobs_router
from app.api.settings import router as settings_router
from app.api.tools import router as tools_router
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db import session as db_session
from app.db.session import session_scope
from app.models import SystemSetting, User


def validate_runtime_settings() -> None:
    if not settings.admin_password.strip():
        raise RuntimeError("TOOLBOX_ADMIN_PASSWORD 未配置，请先在环境变量或 .env 中设置管理员密码。")


def ensure_default_data() -> None:
    validate_runtime_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    with session_scope() as db:
        admin = db.execute(select(User).where(User.username == settings.admin_username)).scalar_one_or_none()
        if admin is None:
            db.add(
                User(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                )
            )

        defaults = {
            "default_source_language": settings.default_source_language,
            "default_target_language": settings.default_target_language,
            "default_chunk_size": str(settings.default_chunk_size),
            "default_concurrency": str(settings.default_concurrency),
            "default_overwrite_existing": "true" if settings.default_overwrite_existing else "false",
        }
        for key, value in defaults.items():
            record = db.get(SystemSetting, key)
            if record is None:
                db.add(SystemSetting(key=key, value=value))


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=db_session.engine)
    ensure_default_data()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def healthcheck() -> dict:
        return {"status": "ok"}

    app.include_router(auth_router, prefix="/api")
    app.include_router(files_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")
    app.include_router(platform_runs_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(tools_router, prefix="/api")
    return app


app = create_app()
