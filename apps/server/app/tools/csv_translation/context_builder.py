from __future__ import annotations

from collections import Counter
from typing import Iterable

from app.core.config import settings
from app.services.openai_service import openai_service
from app.tools.csv_translation.parser import ParsedCsv
from app.tools.csv_translation.prompt_builder import build_context_prompts


def _sample_lines(parsed: ParsedCsv, limit: int) -> str:
    lines = []
    for row in parsed.rows[:limit]:
        lines.append(
            f"- row={row.row_number}, module={row.data.get('module', '')}, "
            f"name={row.data.get('name', '')}, src={row.data.get('src', '')!r}"
        )
    return "\n".join(lines)


def build_context_draft(parsed: ParsedCsv, source_language: str, target_language: str) -> str:
    modules = Counter(row.data.get("module", "") for row in parsed.rows if row.data.get("module"))
    top_modules = ", ".join(name for name, _ in modules.most_common(3)) or "unknown"
    headers = ", ".join(parsed.headers)
    examples = _sample_lines(parsed, settings.context_sample_size)

    system_prompt, user_prompt = build_context_prompts(
        headers=headers,
        top_modules=top_modules,
        examples=examples,
        source_language=source_language,
        target_language=target_language,
    )

    try:
        return openai_service.create_context_draft(system_prompt, user_prompt)
    except Exception:
        return (
            f"这是一个来自 Odoo 的翻译 CSV，主要模块包含 {top_modules}。"
            f"源语言是 {source_language}，目标语言是 {target_language}。"
            f"请保持 Odoo 界面术语统一，参考字段头 {headers}，并结合样例文本如 {parsed.rows[0].data.get('src', '') if parsed.rows else ''} "
            f"进行自然、准确、适合业务界面的翻译。"
        )
