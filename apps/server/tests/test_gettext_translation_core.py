from pathlib import Path


def test_parse_gettext_file_collects_context_plural_and_flags(tmp_path: Path) -> None:
    source = tmp_path / "sample.pot"
    source.write_text(
        '\n'.join(
            [
                'msgid ""',
                'msgstr ""',
                '"Project-Id-Version: demo\\n"',
                '',
                '#, fuzzy',
                'msgctxt "button"',
                'msgid "Save"',
                'msgstr ""',
                '',
                'msgid "File"',
                'msgid_plural "Files"',
                'msgstr[0] ""',
                'msgstr[1] ""',
            ]
        ),
        encoding="utf-8",
    )

    from app.tools.gettext_translation.parser import parse_gettext_file

    parsed = parse_gettext_file(source)

    assert parsed.file_type == "pot"
    assert len(parsed.entries) == 2
    assert parsed.entries[0].msgctxt == "button"
    assert parsed.entries[0].is_fuzzy is True
    assert parsed.entries[1].is_plural is True
    assert parsed.entries[1].msgid_plural == "Files"


def test_export_gettext_file_prefers_manual_edits_and_updates_language(tmp_path: Path) -> None:
    source = tmp_path / "sample.po"
    source.write_text(
        '\n'.join(
            [
                'msgid ""',
                'msgstr ""',
                '"Language: en_US\\n"',
                '',
                'msgid "Save"',
                'msgstr "Save"',
            ]
        ),
        encoding="utf-8",
    )

    from app.tools.gettext_translation.exporter import export_gettext_file
    from app.tools.gettext_translation.parser import parse_gettext_file

    parsed = parse_gettext_file(source)
    content = export_gettext_file(
        parsed,
        target_language="zh_CN",
        entry_results={
            1: {
                "translated_value": "保存",
                "edited_value": "保存按钮",
            }
        },
    )

    exported_text = content.decode("utf-8")
    assert 'Language: zh_CN\\n' in exported_text
    assert 'msgstr "保存按钮"' in exported_text


def test_build_gettext_chunks_respects_translation_mode() -> None:
    from app.tools.gettext_translation.schemas import GettextEntryCandidate
    from app.tools.gettext_translation.task_runner import build_gettext_chunks

    candidates = [
        GettextEntryCandidate(
            entry_index=1,
            msgid="Save",
            msgstr="",
            msgstr_plural={},
            is_plural=False,
            is_fuzzy=False,
        ),
        GettextEntryCandidate(
            entry_index=2,
            msgid="Cancel",
            msgstr="取消",
            msgstr_plural={},
            is_plural=False,
            is_fuzzy=True,
        ),
        GettextEntryCandidate(
            entry_index=3,
            msgid="Archive",
            msgstr="归档",
            msgstr_plural={},
            is_plural=False,
            is_fuzzy=False,
        ),
    ]

    chunks = build_gettext_chunks(candidates, chunk_size=1, translation_mode="blank_and_fuzzy")

    assert [[item.entry_index for item in chunk] for chunk in chunks] == [[1], [2]]


def test_gettext_translation_item_response_accepts_plural_value_list() -> None:
    from app.services.openai_service import GettextTranslationItemResponse

    item = GettextTranslationItemResponse.model_validate(
        {
            "entry_index": 7,
            "translated_value": "",
            "translated_plural_values": [
                {"index": 0, "value": "文件"},
                {"index": 1, "value": "多个文件"},
            ],
        }
    )

    assert item.entry_index == 7
    assert len(item.translated_plural_values) == 2
    assert item.translated_plural_values[0].index == 0
    assert item.translated_plural_values[1].value == "多个文件"


def test_gettext_translation_batch_response_schema_uses_array_for_plural_values() -> None:
    from openai.lib._pydantic import to_strict_json_schema

    from app.services.openai_service import GettextTranslationBatchResponse

    schema = to_strict_json_schema(GettextTranslationBatchResponse)
    item_schema = schema["$defs"]["GettextTranslationItemResponse"]
    plural_schema = item_schema["properties"]["translated_plural_values"]
    plural_item_schema = (
        schema["$defs"]["GettextPluralValueResponse"]
        if "$ref" in plural_schema["items"]
        else plural_schema["items"]
    )

    assert plural_schema["type"] == "array"
    assert plural_item_schema["type"] == "object"
    assert plural_item_schema["additionalProperties"] is False
    assert set(plural_item_schema["properties"]) == {"index", "value"}


def test_gettext_proofread_item_response_accepts_plural_value_list() -> None:
    from app.services.openai_service import GettextProofreadItemResponse

    item = GettextProofreadItemResponse.model_validate(
        {
            "entry_index": 2,
            "suggested_value": "",
            "suggested_plural_values": [
                {"index": 0, "value": "文件"},
                {"index": 1, "value": "文件列表"},
            ],
            "reason": "统一文件模块术语。",
        }
    )

    assert item.entry_index == 2
    assert item.suggested_plural_values[1].value == "文件列表"
    assert item.reason == "统一文件模块术语。"
