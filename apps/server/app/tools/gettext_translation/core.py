from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.services.openai_service import openai_service
from app.tools.gettext_translation.context_builder import build_context_draft
from app.tools.gettext_translation.exporter import export_gettext_file
from app.tools.gettext_translation.parser import parse_gettext_file
from app.tools.gettext_translation.prompt_builder import (
    build_gettext_proofread_prompts,
    build_gettext_translation_prompts,
)
from app.tools.gettext_translation.schemas import GettextEntryCandidate
from app.tools.gettext_translation.task_runner import build_gettext_chunks


@dataclass
class AutoTranslateResult:
    output_path: str
    total_entries: int
    translated_entries: int
    proofread_applied: int
    content: str


def auto_translate(
    file_content: str,
    filename: str,
    source_language: str,
    target_language: str,
    output_path: str | None = None,
    translation_mode: str = "blank",
    chunk_size: int = 20,
    proofread: bool = False,
    context_text: str = "",
) -> AutoTranslateResult:
    suffix = Path(filename).suffix or ".pot"
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8") as tmp:
        tmp.write(file_content)
        tmp_path = Path(tmp.name)

    try:
        parsed = parse_gettext_file(tmp_path)

        if not context_text.strip():
            context_text = build_context_draft(parsed, source_language, target_language)

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
        chunks = build_gettext_chunks(candidates, chunk_size, translation_mode)
        entries_by_index = {e.entry_index: e for e in parsed.entries}

        entry_results: dict[int, dict[str, object]] = {}

        for chunk in chunks:
            chunk_entries = [entries_by_index[c.entry_index] for c in chunk]
            system_prompt, user_prompt = build_gettext_translation_prompts(
                context_text=context_text,
                source_language=source_language,
                target_language=target_language,
                entries=chunk_entries,
            )
            translated_items = openai_service.translate_gettext_entries(system_prompt, user_prompt)

            for item in translated_items:
                entry_results[item.entry_index] = {
                    "translated_value": item.translated_value,
                    "translated_plural_values": {
                        pv.index: pv.value for pv in item.translated_plural_values
                    },
                    "edited_value": "",
                    "edited_plural_values": {},
                }

        proofread_applied = 0
        if proofread and entry_results:
            proofread_applied = _apply_proofread(
                parsed_entries=parsed.entries,
                entry_results=entry_results,
                context_text=context_text,
                source_language=source_language,
                target_language=target_language,
            )

        exported = export_gettext_file(
            parsed=parsed,
            target_language=target_language,
            entry_results=entry_results,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    translated_content = exported.decode("utf-8")

    if output_path is None:
        stem = Path(filename).stem
        file_type = suffix.lstrip(".").lower()
        out_suffix = f".{target_language}.po" if file_type == "pot" else ".po"
        output_path = f"{stem}{out_suffix}"

    return AutoTranslateResult(
        output_path=output_path,
        total_entries=len(parsed.entries),
        translated_entries=len(entry_results),
        proofread_applied=proofread_applied,
        content=translated_content,
    )


def _apply_proofread(
    parsed_entries: list,
    entry_results: dict[int, dict[str, object]],
    context_text: str,
    source_language: str,
    target_language: str,
) -> int:
    review_items: list[dict[str, object]] = []
    for entry in parsed_entries:
        result = entry_results.get(entry.entry_index)
        if result is None:
            continue

        if entry.is_plural:
            plural_values = result.get("translated_plural_values", {})
            if not plural_values:
                continue
            review_items.append({
                "entry_index": entry.entry_index,
                "msgctxt": entry.msgctxt,
                "msgid": entry.msgid,
                "msgid_plural": entry.msgid_plural,
                "current_value": "",
                "current_plural_values": plural_values,
                "comment": entry.comment,
                "tcomment": entry.tcomment,
                "occurrences": entry.occurrences,
                "flags": entry.flags,
                "is_plural": True,
            })
        else:
            translated_value = result.get("translated_value", "")
            if not translated_value:
                continue
            review_items.append({
                "entry_index": entry.entry_index,
                "msgctxt": entry.msgctxt,
                "msgid": entry.msgid,
                "msgid_plural": entry.msgid_plural,
                "current_value": translated_value,
                "current_plural_values": {},
                "comment": entry.comment,
                "tcomment": entry.tcomment,
                "occurrences": entry.occurrences,
                "flags": entry.flags,
                "is_plural": False,
            })

    if not review_items:
        return 0

    system_prompt, user_prompt = build_gettext_proofread_prompts(
        context_text=context_text,
        source_language=source_language,
        target_language=target_language,
        items=review_items,
    )
    suggestions = openai_service.proofread_gettext_entries(system_prompt, user_prompt)

    applied = 0
    for item in suggestions:
        result = entry_results.get(item.entry_index)
        if result is None:
            continue

        if item.suggested_value.strip():
            current = result.get("translated_value", "")
            if item.suggested_value.strip() != current:
                result["edited_value"] = item.suggested_value.strip()
                applied += 1
        elif item.suggested_plural_values:
            suggested = {pv.index: pv.value for pv in item.suggested_plural_values if pv.value.strip()}
            current = result.get("translated_plural_values", {})
            if suggested and suggested != current:
                result["edited_plural_values"] = suggested
                applied += 1

    return applied
