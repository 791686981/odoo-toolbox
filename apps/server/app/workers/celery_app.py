from __future__ import annotations

from celery import Celery

from app.core.config import settings
from app.tools.csv_translation.task_runner import execute_translation_job


celery_app = Celery(
    "odoo_toolbox",
    broker=settings.redis_url,
    backend=settings.redis_url,
)


@celery_app.task(name="csv_translation.run_translation_job")
def run_translation_job(job_id: str) -> None:
    execute_translation_job(job_id)
