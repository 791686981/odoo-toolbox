from __future__ import annotations

from app.tools.gettext_translation.parser import ParsedGettextFile

import polib


def export_gettext_file(
    parsed: ParsedGettextFile,
    target_language: str,
    entry_results: dict[int, dict[str, str]],
) -> bytes:
    catalog = polib.pofile(str(parsed.path))
    catalog.metadata["Language"] = target_language

    for index, entry in enumerate(catalog, start=1):
        if entry.obsolete or not entry.msgid:
            continue

        result = entry_results.get(index, {})
        edited_value = result.get("edited_value", "")
        translated_value = result.get("translated_value", "")
        entry.msgstr = edited_value or translated_value or entry.msgstr

    return catalog.__unicode__().encode("utf-8")
