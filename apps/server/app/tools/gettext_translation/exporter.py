from __future__ import annotations

from app.tools.gettext_translation.parser import ParsedGettextFile

import polib


def normalize_plural_values(values: dict[object, str]) -> dict[int, str]:
    return {int(key): value for key, value in values.items()}


def export_gettext_file(
    parsed: ParsedGettextFile,
    target_language: str,
    entry_results: dict[int, dict[str, object]],
) -> bytes:
    catalog = polib.pofile(str(parsed.path))
    catalog.metadata["Language"] = target_language

    for index, entry in enumerate(catalog, start=1):
        if entry.obsolete or not entry.msgid:
            continue

        result = entry_results.get(index, {})
        edited_value = result.get("edited_value", "")
        translated_value = result.get("translated_value", "")
        edited_plural_values = normalize_plural_values(result.get("edited_plural_values", {}))
        translated_plural_values = normalize_plural_values(result.get("translated_plural_values", {}))

        if entry.msgid_plural:
            merged_plural_values = dict(entry.msgstr_plural)
            for plural_index in sorted(set(merged_plural_values) | set(translated_plural_values) | set(edited_plural_values)):
                plural_key = int(plural_index)
                merged_plural_values[plural_key] = (
                    edited_plural_values.get(plural_key)
                    or translated_plural_values.get(plural_key)
                    or merged_plural_values.get(plural_key, "")
                )
            entry.msgstr_plural = {int(key): value for key, value in merged_plural_values.items()}
        else:
            entry.msgstr = edited_value or translated_value or entry.msgstr

    return catalog.__unicode__().encode("utf-8")
