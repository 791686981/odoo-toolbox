from __future__ import annotations

import json
from typing import Sequence

from app.models.tools import GettextTranslationEntry


def build_gettext_translation_prompts(
    context_text: str,
    source_language: str,
    target_language: str,
    entries: Sequence[GettextTranslationEntry],
) -> tuple[str, str]:
    system_prompt = (
        "你是专业的 Gettext 翻译助手。"
        "你会收到一组 gettext 条目。"
        "普通条目必须返回 translated_value；复数字段必须返回 translated_plural_values。"
        "不要遗漏任何 entry_index，不要返回 Markdown。"
    )

    payload = {
        "context": context_text,
        "source_language": source_language,
        "target_language": target_language,
        "items": [
            {
                "entry_index": entry.entry_index,
                "msgctxt": entry.msgctxt,
                "msgid": entry.msgid,
                "msgid_plural": entry.msgid_plural,
                "msgstr": entry.msgstr,
                "msgstr_plural": entry.msgstr_plural,
                "comment": entry.comment,
                "tcomment": entry.tcomment,
                "occurrences": entry.occurrences,
                "flags": entry.flags,
                "is_plural": entry.is_plural,
            }
            for entry in entries
        ],
    }
    user_prompt = (
        "请翻译下面的 gettext 条目，保持术语一致性，并尊重上下文与注释。"
        "如果条目是 plural，请返回完整的 translated_plural_values。\n"
        "JSON_PAYLOAD:\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    return system_prompt, user_prompt
