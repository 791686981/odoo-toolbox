from __future__ import annotations

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
