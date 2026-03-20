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
