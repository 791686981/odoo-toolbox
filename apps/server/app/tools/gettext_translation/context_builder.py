from __future__ import annotations

from collections import Counter

from app.core.config import settings
from app.services.openai_service import openai_service
from app.tools.gettext_translation.parser import ParsedGettextFile
from app.tools.gettext_translation.prompt_builder import build_gettext_context_prompts


def _sample_entries(parsed: ParsedGettextFile, limit: int) -> str:
    lines = []
    for entry in parsed.entries[:limit]:
        lines.append(
            f"- entry={entry.entry_index}, context={entry.msgctxt or '-'}, "
            f"msgid={entry.msgid!r}, plural={entry.msgid_plural!r}, comment={entry.comment!r}"
        )
    return "\n".join(lines)


def build_context_draft(parsed: ParsedGettextFile, source_language: str, target_language: str) -> str:
    contexts = Counter(entry.msgctxt for entry in parsed.entries if entry.msgctxt)
    top_contexts = ", ".join(name for name, _ in contexts.most_common(3)) or "default"
    project_name = parsed.metadata.get("Project-Id-Version", "") or "Odoo gettext"
    examples = _sample_entries(parsed, settings.context_sample_size)

    system_prompt, user_prompt = build_gettext_context_prompts(
        file_type=parsed.file_type,
        top_contexts=top_contexts,
        project_name=project_name,
        examples=examples,
        source_language=source_language,
        target_language=target_language,
    )

    try:
        return openai_service.create_context_draft(system_prompt, user_prompt)
    except Exception:
        sample_text = parsed.entries[0].msgid if parsed.entries else ""
        return (
            f"这是一个 Odoo Gettext {parsed.file_type.upper()} 翻译任务，项目标识为 {project_name}。"
            f"源语言是 {source_language}，目标语言是 {target_language}。"
            f"请保持界面术语统一，优先参考上下文 {top_contexts}，并结合样例文案 {sample_text!r} "
            "输出自然、准确、适合业务界面的翻译。"
        )
