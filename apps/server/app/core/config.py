from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Odoo Toolbox"
    secret_key: str = "change-me-in-production"
    debug: bool = False
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    database_url: str = "sqlite:///./storage/app.db"
    redis_url: str = "redis://redis:6379/0"

    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_translation_model: str = "gpt-4.1-mini"
    openai_review_model: str = ""
    admin_username: str = "admin"
    admin_password: str = "admin123456"

    upload_dir: Path = Path("./storage/uploads")
    output_dir: Path = Path("./storage/outputs")
    eager_tasks: bool = False

    default_source_language: str = "en_US"
    default_target_language: str = "zh_CN"
    default_chunk_size: int = 20
    default_concurrency: int = 2
    default_overwrite_existing: bool = False
    context_sample_size: int = 8

    model_config = SettingsConfigDict(
        env_prefix="TOOLBOX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
