from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models import (
    GettextTranslationChunk,
    GettextTranslationEntry,
    GettextTranslationRun,
    ToolArtifact,
    ToolRun,
    UploadedFile,
    User,
)
from app.schemas.gettext_translation import (
    CreateGettextTranslationJobRequest,
    ExportGettextTranslationResponse,
    GettextContextDraftRequest,
    GettextContextDraftResponse,
    GettextProofreadPreviewResponse,
    GettextProofreadSuggestionResponse,
    GettextTranslationEntriesPage,
    GettextTranslationEntryResponse,
    GettextTranslationRunResponse,
    UpdateGettextTranslationEntryRequest,
)
from app.services.openai_service import openai_service
from app.services.file_service import store_generated_file
from app.tools.gettext_translation.context_builder import build_context_draft
from app.tools.gettext_translation.exporter import export_gettext_file
from app.tools.gettext_translation.parser import parse_gettext_file
from app.tools.gettext_translation.prompt_builder import build_gettext_proofread_prompts
from app.tools.gettext_translation.schemas import GettextEntryCandidate
from app.tools.gettext_translation.task_runner import build_gettext_chunks, execute_gettext_translation_job
from app.workers.celery_app import run_gettext_translation_job


router = APIRouter(prefix="/tools/gettext-translation", tags=["gettext-translation"])


def serialize_run(run: GettextTranslationRun) -> GettextTranslationRunResponse:
    return GettextTranslationRunResponse.model_validate(run, from_attributes=True)


def serialize_entry(entry: GettextTranslationEntry) -> GettextTranslationEntryResponse:
    return GettextTranslationEntryResponse.model_validate(entry, from_attributes=True)


def validate_gettext_upload(uploaded_file: UploadedFile) -> None:
    suffix = uploaded_file.original_name.lower().rsplit(".", 1)[-1] if "." in uploaded_file.original_name else ""
    if suffix not in {"po", "pot"}:
        raise HTTPException(status_code=400, detail="仅支持 .po 或 .pot 文件。")


def normalize_plural_value_dict(values: dict[object, str] | None) -> dict[int, str]:
    return {int(key): value for key, value in (values or {}).items()}


def build_effective_plural_values(entry: GettextTranslationEntry) -> dict[int, str]:
    translated_plural_values = normalize_plural_value_dict(entry.translated_plural_values)
    edited_plural_values = normalize_plural_value_dict(entry.edited_plural_values)
    merged_keys = set(translated_plural_values) | set(edited_plural_values)
    values: dict[int, str] = {}
    for key in sorted(merged_keys):
        value = edited_plural_values.get(key) or translated_plural_values.get(key) or ""
        if value.strip():
            values[key] = value
    return values


@router.post("/context-draft", response_model=GettextContextDraftResponse)
def context_draft(
    payload: GettextContextDraftRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GettextContextDraftResponse:
    uploaded_file = db.get(UploadedFile, payload.uploaded_file_id)
    if uploaded_file is None:
        raise HTTPException(status_code=404, detail="上传文件不存在。")

    validate_gettext_upload(uploaded_file)
    parsed = parse_gettext_file(Path(uploaded_file.stored_path))
    background = build_context_draft(parsed, payload.source_language, payload.target_language)
    return GettextContextDraftResponse(background=background)


@router.post("/jobs", response_model=GettextTranslationRunResponse)
def create_job(
    payload: CreateGettextTranslationJobRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GettextTranslationRunResponse:
    uploaded_file = db.get(UploadedFile, payload.uploaded_file_id)
    if uploaded_file is None:
        raise HTTPException(status_code=404, detail="上传文件不存在。")

    validate_gettext_upload(uploaded_file)
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

    if run.total_entries > 0:
        if settings.eager_tasks:
            execute_gettext_translation_job(run.id)
        else:
            run_gettext_translation_job.delay(run.id)
        db.refresh(run)

    return serialize_run(run)


@router.get("/runs/{run_id}", response_model=GettextTranslationRunResponse)
def get_run(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GettextTranslationRunResponse:
    run = db.get(GettextTranslationRun, run_id)
    if run is None or run.created_by != user.username:
        raise HTTPException(status_code=404, detail="任务不存在。")
    return serialize_run(run)


@router.get("/runs/{run_id}/entries", response_model=GettextTranslationEntriesPage)
def list_entries(
    run_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GettextTranslationEntriesPage:
    run = db.get(GettextTranslationRun, run_id)
    if run is None or run.created_by != user.username:
        raise HTTPException(status_code=404, detail="任务不存在。")

    total = (
        db.execute(select(func.count()).select_from(GettextTranslationEntry).where(GettextTranslationEntry.run_id == run_id))
        .scalar_one()
    )
    entries = (
        db.execute(
            select(GettextTranslationEntry)
            .where(GettextTranslationEntry.run_id == run_id)
            .order_by(GettextTranslationEntry.entry_index.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    return GettextTranslationEntriesPage(
        items=[serialize_entry(entry) for entry in entries],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/runs/{run_id}/proofread-preview", response_model=GettextProofreadPreviewResponse)
def proofread_run(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GettextProofreadPreviewResponse:
    run = db.get(GettextTranslationRun, run_id)
    if run is None or run.created_by != user.username:
        raise HTTPException(status_code=404, detail="任务不存在。")
    if run.status != "completed":
        raise HTTPException(status_code=400, detail="请在任务完成后再发起 AI 校对。")

    entries = (
        db.execute(
            select(GettextTranslationEntry)
            .where(GettextTranslationEntry.run_id == run_id)
            .order_by(GettextTranslationEntry.entry_index.asc())
        )
        .scalars()
        .all()
    )

    review_items: list[dict[str, object]] = []
    entry_by_index: dict[int, GettextTranslationEntry] = {}
    for entry in entries:
        if entry.is_plural:
            current_plural_values = build_effective_plural_values(entry)
            if not current_plural_values:
                continue
            review_items.append(
                {
                    "entry_index": entry.entry_index,
                    "msgctxt": entry.msgctxt,
                    "msgid": entry.msgid,
                    "msgid_plural": entry.msgid_plural,
                    "current_value": "",
                    "current_plural_values": current_plural_values,
                    "comment": entry.comment,
                    "tcomment": entry.tcomment,
                    "occurrences": entry.occurrences,
                    "flags": entry.flags,
                    "is_plural": True,
                }
            )
        else:
            current_value = (entry.edited_value or "").strip() or (entry.translated_value or "").strip()
            if not current_value:
                continue
            review_items.append(
                {
                    "entry_index": entry.entry_index,
                    "msgctxt": entry.msgctxt,
                    "msgid": entry.msgid,
                    "msgid_plural": entry.msgid_plural,
                    "current_value": current_value,
                    "current_plural_values": {},
                    "comment": entry.comment,
                    "tcomment": entry.tcomment,
                    "occurrences": entry.occurrences,
                    "flags": entry.flags,
                    "is_plural": False,
                }
            )
        entry_by_index[entry.entry_index] = entry

    model_name = settings.openai_review_model or settings.openai_translation_model
    if not review_items:
        return GettextProofreadPreviewResponse(model=model_name, items=[])

    system_prompt, user_prompt = build_gettext_proofread_prompts(
        context_text=run.context_text,
        source_language=run.source_language,
        target_language=run.target_language,
        items=review_items,
    )
    try:
        suggestions = openai_service.proofread_gettext_entries(system_prompt, user_prompt)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    preview_items: list[GettextProofreadSuggestionResponse] = []
    for item in suggestions:
        entry = entry_by_index.get(item.entry_index)
        if entry is None:
            continue

        current_plural_values = build_effective_plural_values(entry)
        suggested_plural_values = {
            plural_value.index: plural_value.value
            for plural_value in item.suggested_plural_values
            if plural_value.value.strip()
        }
        current_value = (entry.edited_value or "").strip() or (entry.translated_value or "").strip()
        suggested_value = item.suggested_value.strip()

        if entry.is_plural:
            if not suggested_plural_values or suggested_plural_values == current_plural_values:
                continue
        else:
            if not suggested_value or suggested_value == current_value:
                continue

        preview_items.append(
            GettextProofreadSuggestionResponse(
                entry_id=entry.id,
                entry_index=entry.entry_index,
                msgid=entry.msgid,
                msgid_plural=entry.msgid_plural,
                current_value=current_value,
                current_plural_values=current_plural_values,
                suggested_value=suggested_value,
                suggested_plural_values=suggested_plural_values,
                reason=item.reason.strip(),
                is_plural=entry.is_plural,
            )
        )

    return GettextProofreadPreviewResponse(model=model_name, items=preview_items)


@router.patch("/runs/{run_id}/entries/{entry_id}", response_model=GettextTranslationEntryResponse)
def update_entry(
    run_id: str,
    entry_id: str,
    payload: UpdateGettextTranslationEntryRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GettextTranslationEntryResponse:
    run = db.get(GettextTranslationRun, run_id)
    if run is None or run.created_by != user.username:
        raise HTTPException(status_code=404, detail="任务不存在。")

    entry = db.get(GettextTranslationEntry, entry_id)
    if entry is None or entry.run_id != run_id:
        raise HTTPException(status_code=404, detail="条目不存在。")

    entry.edited_value = payload.edited_value
    entry.edited_plural_values = payload.edited_plural_values
    has_edit = bool(payload.edited_value.strip()) or any(value.strip() for value in payload.edited_plural_values.values())
    entry.status = "edited" if has_edit else ("translated" if entry.translated_value or entry.translated_plural_values else entry.status)
    db.commit()
    db.refresh(entry)
    return serialize_entry(entry)


@router.post("/runs/{run_id}/export", response_model=ExportGettextTranslationResponse)
def export_run(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExportGettextTranslationResponse:
    run = db.get(GettextTranslationRun, run_id)
    if run is None or run.created_by != user.username:
        raise HTTPException(status_code=404, detail="任务不存在。")
    if run.status != "completed":
        raise HTTPException(status_code=400, detail="任务未完成，无法导出。")

    source_file = db.get(UploadedFile, run.uploaded_file_id)
    if source_file is None:
        raise HTTPException(status_code=404, detail="源文件不存在。")

    parsed = parse_gettext_file(Path(source_file.stored_path))
    entries = (
        db.execute(
            select(GettextTranslationEntry)
            .where(GettextTranslationEntry.run_id == run_id)
            .order_by(GettextTranslationEntry.entry_index.asc())
        )
        .scalars()
        .all()
    )
    entry_results = {
        entry.entry_index: {
            "translated_value": entry.translated_value,
            "translated_plural_values": entry.translated_plural_values,
            "edited_value": entry.edited_value,
            "edited_plural_values": entry.edited_plural_values,
        }
        for entry in entries
    }
    content = export_gettext_file(
        parsed=parsed,
        target_language=run.target_language,
        entry_results=entry_results,
    )

    stem = Path(source_file.original_name).stem
    filename = (
        f"{stem}.{run.target_language}.po"
        if run.input_file_type == "pot"
        else source_file.original_name
    )
    exported_file = store_generated_file(
        db=db,
        filename=filename,
        content=content,
        mime_type="text/x-gettext-translation",
        username=user.username,
    )
    db.add(
        ToolArtifact(
            run_id=run.id,
            kind="export",
            file_id=exported_file.id,
            label="Gettext 导出",
            artifact_metadata={"run_id": run.id},
        )
    )
    run.exported_file_id = exported_file.id
    db.commit()
    return ExportGettextTranslationResponse(file_id=exported_file.id, filename=exported_file.original_name)
