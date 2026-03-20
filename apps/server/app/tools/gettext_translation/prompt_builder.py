from __future__ import annotations

import json
from typing import Sequence

from app.models.tools import GettextTranslationEntry


def build_gettext_context_prompts(
    file_type: str,
    top_contexts: str,
    project_name: str,
    examples: str,
    source_language: str,
    target_language: str,
) -> tuple[str, str]:
    system_prompt = (
        "你是 Odoo / Gettext 本地化顾问。"
        "请根据 gettext 条目的上下文、项目元数据和样例文案，生成一段适合后续翻译任务复用的术语与上下文说明。"
        "输出必须是结构化字段 background。"
    )
    user_prompt = (
        f"file_type: {file_type}\n"
        f"project_name: {project_name}\n"
        f"top_contexts: {top_contexts}\n"
        f"source_language: {source_language}\n"
        f"target_language: {target_language}\n"
        f"examples:\n{examples}\n"
        "请输出 1 段简洁、可编辑的背景说明，帮助后续翻译保持术语、语气和界面文风一致。"
    )
    return system_prompt, user_prompt


def build_gettext_translation_prompts(
    context_text: str,
    source_language: str,
    target_language: str,
    entries: Sequence[GettextTranslationEntry],
) -> tuple[str, str]:
    system_prompt = (
        "你是专业的 Gettext 翻译助手。"
        "你会收到一组 gettext 条目。"
        "每个条目都必须返回 entry_index、translated_value、translated_plural_values 三个字段。"
        "普通条目把 translated_value 设为译文，translated_plural_values 返回空数组。"
        "复数字段把 translated_value 设为空字符串，translated_plural_values 返回完整数组。"
        "translated_plural_values 中的每一项都必须包含 index 和 value。"
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
        "普通条目必须返回非空 translated_value 和空的 translated_plural_values。"
        "plural 条目必须返回完整的 translated_plural_values 数组，并让 translated_value 为空字符串。\n"
        "JSON_PAYLOAD:\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    return system_prompt, user_prompt


def build_gettext_proofread_prompts(
    context_text: str,
    source_language: str,
    target_language: str,
    items: Sequence[dict[str, object]],
) -> tuple[str, str]:
    system_prompt = (
        "你是专业的 Gettext 翻译审校助手。"
        "你会收到一组已经翻译完成的 gettext 条目。"
        "每个条目都必须返回 entry_index、suggested_value、suggested_plural_values、reason 四个字段。"
        "如果条目无需修改，就不要返回该条。"
        "普通条目把 suggested_value 设为建议译文，suggested_plural_values 返回空数组。"
        "plural 条目把 suggested_value 设为空字符串，suggested_plural_values 返回完整数组。"
        "不要返回 Markdown，不要解释额外内容。"
    )
    user_prompt = (
        "请审校下面的 gettext 条目，关注术语一致性、界面语气、字段语境和复数形式。"
        "只有在你确定当前结果可以改进时才返回该条。\n"
        "JSON_PAYLOAD:\n"
        + json.dumps(
            {
                "context": context_text,
                "source_language": source_language,
                "target_language": target_language,
                "items": list(items),
            },
            ensure_ascii=False,
        )
    )
    return system_prompt, user_prompt
