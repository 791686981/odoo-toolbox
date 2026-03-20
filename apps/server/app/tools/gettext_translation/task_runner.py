from __future__ import annotations

from sqlalchemy import select

from app.db.session import session_scope
from app.models import GettextTranslationChunk, GettextTranslationEntry, GettextTranslationRun, ToolRun
from app.services.openai_service import openai_service
from app.tools.gettext_translation.prompt_builder import build_gettext_translation_prompts
from app.tools.gettext_translation.schemas import GettextEntryCandidate


def should_translate_entry(candidate: GettextEntryCandidate, translation_mode: str) -> bool:
    if candidate.obsolete:
        return False

    if translation_mode == "overwrite_all":
        return True

    has_blank_translation = not candidate.msgstr.strip() and not any(
        value.strip() for value in candidate.msgstr_plural.values()
    )

    if translation_mode == "blank_and_fuzzy":
        return has_blank_translation or candidate.is_fuzzy

    return has_blank_translation


def build_gettext_chunks(
    candidates: list[GettextEntryCandidate],
    chunk_size: int,
    translation_mode: str,
) -> list[list[GettextEntryCandidate]]:
    selected = [
        candidate
        for candidate in candidates
        if should_translate_entry(candidate, translation_mode=translation_mode)
    ]
    return [selected[index : index + chunk_size] for index in range(0, len(selected), chunk_size)]


def execute_gettext_translation_job(run_id: str) -> None:
    with session_scope() as db:
        run = db.get(GettextTranslationRun, run_id)
        tool_run = db.get(ToolRun, run_id)
        if run is None:
            raise ValueError("任务不存在。")

        run.status = "running"
        run.error_message = ""
        if tool_run is not None:
            tool_run.status = "running"
            tool_run.error_message = ""
        db.flush()

        chunks = (
            db.execute(
                select(GettextTranslationChunk)
                .where(GettextTranslationChunk.run_id == run_id)
                .order_by(GettextTranslationChunk.chunk_index.asc())
            )
            .scalars()
            .all()
        )
        total = max(run.total_entries, 1)

        for chunk in chunks:
            chunk.status = "running"
            db.flush()

            entries = (
                db.execute(
                    select(GettextTranslationEntry)
                    .where(GettextTranslationEntry.run_id == run_id)
                    .where(GettextTranslationEntry.entry_index.in_(chunk.entry_ids))
                    .order_by(GettextTranslationEntry.entry_index.asc())
                )
                .scalars()
                .all()
            )

            system_prompt, user_prompt = build_gettext_translation_prompts(
                context_text=run.context_text,
                source_language=run.source_language,
                target_language=run.target_language,
                entries=entries,
            )

            try:
                translated_items = openai_service.translate_gettext_entries(system_prompt, user_prompt)
            except Exception as exc:
                chunk.status = "failed"
                chunk.error_message = str(exc)
                run.status = "failed"
                run.error_message = str(exc)
                if tool_run is not None:
                    tool_run.status = "failed"
                    tool_run.error_message = str(exc)
                db.flush()
                return

            translated_by_index = {item.entry_index: item for item in translated_items}
            for entry in entries:
                translated_item = translated_by_index.get(entry.entry_index)
                if translated_item is None:
                    continue

                if entry.is_plural:
                    entry.translated_plural_values = {
                        int(key): value
                        for key, value in translated_item.translated_plural_values.items()
                    }
                else:
                    entry.translated_value = translated_item.translated_value
                entry.status = "translated"

            chunk.status = "completed"
            run.processed_entries += len(entries)
            run.progress = int(run.processed_entries * 100 / total)
            db.flush()

        run.status = "completed"
        run.progress = 100
        if tool_run is not None:
            tool_run.status = "completed"
            tool_run.error_message = ""
        db.flush()
