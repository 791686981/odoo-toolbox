from __future__ import annotations

from typing import Dict, List, Sequence

from sqlalchemy import select

from app.db.session import session_scope
from app.models import ToolRun, TranslationJob, TranslationJobChunk, TranslationRowResult
from app.services.openai_service import openai_service
from app.tools.csv_translation.prompt_builder import build_translation_prompts
from app.tools.csv_translation.schemas import TranslationChunkItem


def build_translation_chunks(parsed, chunk_size: int, overwrite_existing: bool) -> List[List]:
    candidates = []
    for row in parsed.rows:
        if not row.data.get("src", "").strip():
            continue
        if row.data.get("value", "").strip() and not overwrite_existing:
            continue
        candidates.append(row)

    return [candidates[index : index + chunk_size] for index in range(0, len(candidates), chunk_size)]


def execute_translation_job(job_id: str) -> None:
    with session_scope() as db:
        job = db.get(TranslationJob, job_id)
        tool_run = db.get(ToolRun, job_id)
        if job is None:
            raise ValueError("任务不存在。")

        job.status = "running"
        job.error_message = ""
        if tool_run is not None:
            tool_run.status = "running"
            tool_run.error_message = ""
        db.flush()

        chunks = (
            db.execute(
                select(TranslationJobChunk)
                .where(TranslationJobChunk.job_id == job_id)
                .order_by(TranslationJobChunk.chunk_index.asc())
            )
            .scalars()
            .all()
        )
        total = max(job.total_rows, 1)

        for chunk in chunks:
            chunk.status = "running"
            db.flush()

            rows = (
                db.execute(
                    select(TranslationRowResult)
                    .where(TranslationRowResult.job_id == job_id)
                    .where(TranslationRowResult.row_number.in_(chunk.row_numbers))
                    .order_by(TranslationRowResult.row_number.asc())
                )
                .scalars()
                .all()
            )

            items = [
                TranslationChunkItem(
                    row_number=row.row_number,
                    source_text=row.source_text,
                    original_value=row.original_value,
                    raw_data=row.raw_data,
                )
                for row in rows
            ]

            system_prompt, user_prompt = build_translation_prompts(
                context_text=job.context_text,
                source_language=job.source_language,
                target_language=job.target_language,
                items=items,
            )

            try:
                translated = openai_service.translate_rows(system_prompt, user_prompt)
            except Exception as exc:
                chunk.status = "failed"
                chunk.error_message = str(exc)
                job.status = "failed"
                job.error_message = str(exc)
                if tool_run is not None:
                    tool_run.status = "failed"
                    tool_run.error_message = str(exc)
                db.flush()
                return

            mapping: Dict[int, str] = {item.row_number: item.translated_value for item in translated}
            for row in rows:
                row.translated_value = mapping.get(row.row_number, row.translated_value)
                row.status = "translated"

            chunk.status = "completed"
            job.processed_rows += len(rows)
            job.progress = int(job.processed_rows * 100 / total)
            db.flush()

        job.status = "completed"
        job.progress = 100
        if tool_run is not None:
            tool_run.status = "completed"
            tool_run.error_message = ""
        db.flush()
