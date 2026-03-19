from __future__ import annotations

import json
from typing import Iterable, Sequence

from app.tools.csv_translation.schemas import TranslationChunkItem


def build_context_prompts(
    headers: str,
    top_modules: str,
    examples: str,
    source_language: str,
    target_language: str,
) -> tuple[str, str]:
    system_prompt = (
        "你是 Odoo 本地化翻译助手。"
        "请根据字段头、模块名和样本文本，总结一段适合后续翻译任务复用的背景说明。"
        "输出必须是结构化字段 background。"
    )
    user_prompt = (
        f"这是一个 Odoo CSV。\n"
        f"headers: {headers}\n"
        f"top_modules: {top_modules}\n"
        f"source_language: {source_language}\n"
        f"target_language: {target_language}\n"
        f"examples:\n{examples}\n"
        "请输出 1 段简洁、可编辑的背景说明，帮助后续翻译保持术语和语气一致。"
    )
    return system_prompt, user_prompt


def build_translation_prompts(
    context_text: str,
    source_language: str,
    target_language: str,
    items: Sequence[TranslationChunkItem],
) -> tuple[str, str]:
    system_prompt = (
        "你是 Odoo 专业翻译助手。"
        "你会收到一个固定背景说明和多条 CSV 行。"
        "必须逐条返回对应 row_number 的 translated_value。"
        "不要遗漏，不要新增字段，不要返回 Markdown。"
    )

    payload = {
        "context": context_text,
        "source_language": source_language,
        "target_language": target_language,
        "items": [
            {
                "row_number": item.row_number,
                "source_text": item.source_text,
                "module": item.raw_data.get("module", ""),
                "name": item.raw_data.get("name", ""),
                "comments": item.raw_data.get("comments", ""),
            }
            for item in items
        ],
    }
    user_prompt = (
        "请翻译下面的 Odoo 文本，保留业务术语一致性。"
        "每个 row_number 都必须返回一个 translated_value。\n"
        "JSON_PAYLOAD:\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    return system_prompt, user_prompt


def build_proofread_prompts(
    context_text: str,
    source_language: str,
    target_language: str,
    items: Sequence[dict[str, object]],
) -> tuple[str, str]:
    system_prompt = (
        "你是 Odoo 专业翻译审校助手。"
        "你会收到一个完整任务的背景说明与多条当前译文。"
        "只在确实需要改进时返回建议。"
        "每条建议必须包含 row_number、suggested_value、reason。"
        "不要返回 Markdown，不要返回未修改项。"
    )

    payload = {
        "context": context_text,
        "source_language": source_language,
        "target_language": target_language,
        "items": list(items),
    }
    user_prompt = (
        "请审校下面的 Odoo 译文，关注术语一致性、语气自然度、字段语境和可用性。"
        "如果当前译文已经合适，就不要返回该行。\n"
        "JSON_PAYLOAD:\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    return system_prompt, user_prompt
