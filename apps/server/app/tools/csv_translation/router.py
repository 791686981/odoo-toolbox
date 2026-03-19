from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models import ToolRun, TranslationJob, TranslationJobChunk, TranslationRowResult, UploadedFile, User
from app.schemas.jobs import TranslationJobResponse
from app.tools.csv_translation.context_builder import build_context_draft
from app.tools.csv_translation.parser import parse_odoo_csv
from app.tools.csv_translation.task_runner import build_translation_chunks, execute_translation_job
from app.workers.celery_app import run_translation_job
from pydantic import BaseModel, Field


class ContextDraftRequest(BaseModel):
    uploaded_file_id: str
    source_language: str
    target_language: str


class ContextDraftResponse(BaseModel):
    background: str


class CreateTranslationJobRequest(BaseModel):
    uploaded_file_id: str
    source_language: str
    target_language: str
    background_context: str
    chunk_size: int = Field(default=20, ge=1, le=200)
    concurrency: int = Field(default=1, ge=1, le=10)
    overwrite_existing: bool = False


router = APIRouter(prefix="/tools/csv-translation", tags=["csv-translation"])


def serialize_job(job: TranslationJob) -> TranslationJobResponse:
    return TranslationJobResponse.model_validate(job, from_attributes=True)


@router.post("/context-draft", response_model=ContextDraftResponse)
def context_draft(
    payload: ContextDraftRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContextDraftResponse:
    uploaded_file = db.get(UploadedFile, payload.uploaded_file_id)
    if uploaded_file is None:
        raise HTTPException(status_code=404, detail="上传文件不存在。")

    parsed = parse_odoo_csv(Path(uploaded_file.stored_path))
    background = build_context_draft(parsed, payload.source_language, payload.target_language)
    return ContextDraftResponse(background=background)


@router.post("/jobs", response_model=TranslationJobResponse)
def create_job(
    payload: CreateTranslationJobRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranslationJobResponse:
    uploaded_file = db.get(UploadedFile, payload.uploaded_file_id)
    if uploaded_file is None:
        raise HTTPException(status_code=404, detail="上传文件不存在。")

    parsed = parse_odoo_csv(Path(uploaded_file.stored_path))
    chunks = build_translation_chunks(parsed, payload.chunk_size, payload.overwrite_existing)
    translatable_row_numbers = {row.row_number for chunk in chunks for row in chunk}
    job = TranslationJob(
        status="queued",
        progress=0,
        source_language=payload.source_language,
        target_language=payload.target_language,
        context_text=payload.background_context,
        overwrite_existing=payload.overwrite_existing,
        chunk_size=payload.chunk_size,
        concurrency=payload.concurrency,
        total_rows=sum(len(chunk) for chunk in chunks),
        processed_rows=0,
        uploaded_file_id=uploaded_file.id,
        created_by=user.username,
    )
    db.add(job)
    db.flush()
    db.add(
        ToolRun(
            id=job.id,
            tool_id=job.tool_id,
            status=job.status,
            summary=f"{uploaded_file.original_name} · {payload.source_language} → {payload.target_language}",
            created_by=user.username,
            input_payload={
                "uploaded_file_id": uploaded_file.id,
                "source_language": payload.source_language,
                "target_language": payload.target_language,
                "chunk_size": payload.chunk_size,
                "concurrency": payload.concurrency,
                "overwrite_existing": payload.overwrite_existing,
            },
        )
    )

    for row in parsed.rows:
        row_result = TranslationRowResult(
            job_id=job.id,
            row_number=row.row_number,
            module=row.data.get("module", ""),
            record_type=row.data.get("type", ""),
            name=row.data.get("name", ""),
            res_id=row.data.get("res_id", ""),
            source_text=row.data.get("src", ""),
            original_value=row.data.get("value", ""),
            comments=row.data.get("comments", ""),
            raw_data=row.data,
            status=(
                "pending"
                if row.row_number in translatable_row_numbers
                else ("skipped" if row.data.get("value", "").strip() and not payload.overwrite_existing else "pending")
            ),
        )
        db.add(row_result)

    for index, chunk in enumerate(chunks, start=1):
        db.add(
            TranslationJobChunk(
                job_id=job.id,
                chunk_index=index,
                row_numbers=[row.row_number for row in chunk],
                row_count=len(chunk),
                status="pending",
            )
        )

    if job.total_rows == 0:
        job.status = "completed"
        job.progress = 100
        tool_run = db.get(ToolRun, job.id)
        if tool_run is not None:
            tool_run.status = "completed"

    db.commit()
    db.refresh(job)

    if job.total_rows > 0:
        if settings.eager_tasks:
            execute_translation_job(job.id)
        else:
            run_translation_job.delay(job.id)

        db.refresh(job)

    return serialize_job(job)
