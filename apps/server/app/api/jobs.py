from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import ToolArtifact, TranslationJob, TranslationRowResult, UploadedFile, User
from app.schemas.jobs import (
    ExportJobResponse,
    ProofreadPreviewResponse,
    ProofreadSuggestionResponse,
    TranslationJobResponse,
    TranslationRowResponse,
    TranslationRowsPage,
    UpdateTranslationRowRequest,
)
from app.services.openai_service import openai_service
from app.services.file_service import store_generated_file
from app.tools.csv_translation.exporter import export_translated_csv
from app.tools.csv_translation.parser import parse_odoo_csv
from app.tools.csv_translation.prompt_builder import build_proofread_prompts
from app.core.config import settings


router = APIRouter(tags=["jobs"])


def serialize_job(job: TranslationJob) -> TranslationJobResponse:
    return TranslationJobResponse.model_validate(job, from_attributes=True)


def serialize_row(row: TranslationRowResult) -> TranslationRowResponse:
    return TranslationRowResponse.model_validate(row, from_attributes=True)


@router.get("/jobs", response_model=list[TranslationJobResponse])
def list_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TranslationJobResponse]:
    jobs = (
        db.execute(
            select(TranslationJob)
            .where(TranslationJob.created_by == user.username)
            .order_by(TranslationJob.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [serialize_job(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=TranslationJobResponse)
def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranslationJobResponse:
    job = db.get(TranslationJob, job_id)
    if job is None or job.created_by != user.username:
        raise HTTPException(status_code=404, detail="任务不存在。")
    return serialize_job(job)


@router.get("/jobs/{job_id}/rows", response_model=TranslationRowsPage)
def list_job_rows(
    job_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranslationRowsPage:
    job = db.get(TranslationJob, job_id)
    if job is None or job.created_by != user.username:
        raise HTTPException(status_code=404, detail="任务不存在。")

    total = (
        db.execute(select(func.count()).select_from(TranslationRowResult).where(TranslationRowResult.job_id == job_id))
        .scalar_one()
    )
    rows = (
        db.execute(
            select(TranslationRowResult)
            .where(TranslationRowResult.job_id == job_id)
            .order_by(TranslationRowResult.row_number.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return TranslationRowsPage(
        items=[serialize_row(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/jobs/{job_id}/rows/{row_id}", response_model=TranslationRowResponse)
def update_job_row(
    job_id: str,
    row_id: str,
    payload: UpdateTranslationRowRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranslationRowResponse:
    job = db.get(TranslationJob, job_id)
    if job is None or job.created_by != user.username:
        raise HTTPException(status_code=404, detail="任务不存在。")

    row = db.get(TranslationRowResult, row_id)
    if row is None or row.job_id != job_id:
        raise HTTPException(status_code=404, detail="结果行不存在。")

    row.edited_value = payload.edited_value
    row.status = "edited" if payload.edited_value else ("translated" if row.translated_value else row.status)
    db.commit()
    db.refresh(row)
    return serialize_row(row)


@router.post("/jobs/{job_id}/export", response_model=ExportJobResponse)
def export_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportJobResponse:
    job = db.get(TranslationJob, job_id)
    if job is None or job.created_by != user.username:
        raise HTTPException(status_code=404, detail="任务不存在。")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="任务未完成，无法导出。")

    source_file = db.get(UploadedFile, job.uploaded_file_id)
    if source_file is None:
        raise HTTPException(status_code=404, detail="源文件不存在。")

    parsed = parse_odoo_csv(Path(source_file.stored_path))
    rows = (
        db.execute(
            select(TranslationRowResult)
            .where(TranslationRowResult.job_id == job_id)
            .order_by(TranslationRowResult.row_number.asc())
        )
        .scalars()
        .all()
    )
    row_results = {
        row.row_number: {
            "translated_value": row.translated_value,
            "edited_value": row.edited_value,
        }
        for row in rows
    }
    content = export_translated_csv(parsed, row_results)
    exported_file = store_generated_file(
        db,
        filename=f"{job_id}.csv",
        content=content,
        mime_type="text/csv",
        username=user.username,
    )
    db.add(
        ToolArtifact(
            run_id=job.id,
            kind="export",
            file_id=exported_file.id,
            label="CSV 导出",
            artifact_metadata={"job_id": job.id},
        )
    )
    job.exported_file_id = exported_file.id
    db.commit()
    return ExportJobResponse(file_id=exported_file.id, filename=exported_file.original_name)


@router.post("/jobs/{job_id}/proofread-preview", response_model=ProofreadPreviewResponse)
def proofread_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProofreadPreviewResponse:
    job = db.get(TranslationJob, job_id)
    if job is None or job.created_by != user.username:
        raise HTTPException(status_code=404, detail="任务不存在。")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="请在任务完成后再发起 AI 校对。")

    rows = (
        db.execute(
            select(TranslationRowResult)
            .where(TranslationRowResult.job_id == job_id)
            .order_by(TranslationRowResult.row_number.asc())
        )
        .scalars()
        .all()
    )
    review_items: list[dict[str, object]] = []
    row_by_number: dict[int, TranslationRowResult] = {}
    for row in rows:
        current_value = (row.edited_value or "").strip() or (row.translated_value or "").strip()
        if not current_value:
            continue
        row_by_number[row.row_number] = row
        review_items.append(
            {
                "row_number": row.row_number,
                "source_text": row.source_text,
                "current_value": current_value,
                "module": row.module,
                "name": row.name,
                "comments": row.comments,
            }
        )

    model_name = settings.openai_review_model or settings.openai_translation_model
    if not review_items:
        return ProofreadPreviewResponse(model=model_name, items=[])

    system_prompt, user_prompt = build_proofread_prompts(
        context_text=job.context_text,
        source_language=job.source_language,
        target_language=job.target_language,
        items=review_items,
    )
    try:
        suggestions = openai_service.proofread_rows(system_prompt, user_prompt)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    preview_items: list[ProofreadSuggestionResponse] = []
    for item in suggestions:
        row = row_by_number.get(item.row_number)
        if row is None:
            continue
        current_value = (row.edited_value or "").strip() or (row.translated_value or "").strip()
        suggested_value = item.suggested_value.strip()
        if not suggested_value or suggested_value == current_value:
            continue
        preview_items.append(
            ProofreadSuggestionResponse(
                row_id=row.id,
                row_number=row.row_number,
                source_text=row.source_text,
                current_value=current_value,
                suggested_value=suggested_value,
                reason=item.reason.strip(),
            )
        )
    return ProofreadPreviewResponse(model=model_name, items=preview_items)
