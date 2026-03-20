from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import (
    GettextTranslationChunk,
    GettextTranslationEntry,
    GettextTranslationRun,
    ToolRun,
    UploadedFile,
    User,
)
from app.schemas.gettext_translation import (
    CreateGettextTranslationJobRequest,
    GettextTranslationRunResponse,
)
from app.tools.gettext_translation.parser import parse_gettext_file
from app.tools.gettext_translation.schemas import GettextEntryCandidate
from app.tools.gettext_translation.task_runner import build_gettext_chunks


router = APIRouter(prefix="/tools/gettext-translation", tags=["gettext-translation"])


def serialize_run(run: GettextTranslationRun) -> GettextTranslationRunResponse:
    return GettextTranslationRunResponse.model_validate(run, from_attributes=True)


@router.post("/jobs", response_model=GettextTranslationRunResponse)
def create_job(
    payload: CreateGettextTranslationJobRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GettextTranslationRunResponse:
    uploaded_file = db.get(UploadedFile, payload.uploaded_file_id)
    if uploaded_file is None:
        raise HTTPException(status_code=404, detail="上传文件不存在。")

    suffix = uploaded_file.original_name.lower().rsplit(".", 1)[-1] if "." in uploaded_file.original_name else ""
    if suffix not in {"po", "pot"}:
        raise HTTPException(status_code=400, detail="仅支持 .po 或 .pot 文件。")

    parsed = parse_gettext_file(Path(uploaded_file.stored_path))
    candidates = [
        GettextEntryCandidate(
            entry_index=entry.entry_index,
            msgid=entry.msgid,
            msgstr=entry.msgstr,
            msgstr_plural=entry.msgstr_plural,
            is_plural=entry.is_plural,
            is_fuzzy=entry.is_fuzzy,
        )
        for entry in parsed.entries
    ]
    chunks = build_gettext_chunks(
        candidates=candidates,
        chunk_size=payload.chunk_size,
        translation_mode=payload.translation_mode,
    )
    selected_entry_indexes = {candidate.entry_index for chunk in chunks for candidate in chunk}

    run = GettextTranslationRun(
        status="queued",
        progress=0,
        input_file_type=parsed.file_type,
        translation_mode=payload.translation_mode,
        source_language=payload.source_language,
        target_language=payload.target_language,
        context_text=payload.context_text,
        chunk_size=payload.chunk_size,
        concurrency=payload.concurrency,
        total_entries=len(selected_entry_indexes),
        processed_entries=0,
        uploaded_file_id=uploaded_file.id,
        created_by=user.username,
    )
    db.add(run)
    db.flush()

    db.add(
        ToolRun(
            id=run.id,
            tool_id=run.tool_id,
            status=run.status,
            summary=f"{uploaded_file.original_name} · {payload.source_language} → {payload.target_language}",
            created_by=user.username,
            input_payload={
                "uploaded_file_id": uploaded_file.id,
                "input_file_type": parsed.file_type,
                "source_language": payload.source_language,
                "target_language": payload.target_language,
                "translation_mode": payload.translation_mode,
                "chunk_size": payload.chunk_size,
                "concurrency": payload.concurrency,
            },
        )
    )

    for entry in parsed.entries:
        db.add(
            GettextTranslationEntry(
                run_id=run.id,
                entry_index=entry.entry_index,
                msgctxt=entry.msgctxt,
                msgid=entry.msgid,
                msgid_plural=entry.msgid_plural,
                msgstr=entry.msgstr,
                msgstr_plural=entry.msgstr_plural,
                occurrences=[[source, line] for source, line in entry.occurrences],
                flags=entry.flags,
                comment=entry.comment,
                tcomment=entry.tcomment,
                status="pending" if entry.entry_index in selected_entry_indexes else "skipped",
                is_plural=entry.is_plural,
                is_fuzzy=entry.is_fuzzy,
            )
        )

    for index, chunk in enumerate(chunks, start=1):
        db.add(
            GettextTranslationChunk(
                run_id=run.id,
                chunk_index=index,
                entry_ids=[candidate.entry_index for candidate in chunk],
                entry_count=len(chunk),
                status="pending",
            )
        )

    if run.total_entries == 0:
        run.status = "completed"
        run.progress = 100
        tool_run = db.get(ToolRun, run.id)
        if tool_run is not None:
            tool_run.status = "completed"

    db.commit()
    db.refresh(run)
    return serialize_run(run)
