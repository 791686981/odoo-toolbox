from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polib


@dataclass
class ParsedGettextEntry:
    entry_index: int
    msgctxt: str
    msgid: str
    msgid_plural: str
    msgstr: str
    msgstr_plural: dict[int, str]
    flags: list[str]
    comment: str
    tcomment: str
    occurrences: list[tuple[str, str]]
    is_plural: bool
    is_fuzzy: bool


@dataclass
class ParsedGettextFile:
    file_type: str
    path: Path
    metadata: dict[str, str]
    entries: list[ParsedGettextEntry]


def parse_gettext_file(path: Path) -> ParsedGettextFile:
    catalog = polib.pofile(str(path))
    entries: list[ParsedGettextEntry] = []

    for index, entry in enumerate(catalog, start=1):
        if entry.obsolete or not entry.msgid:
            continue

        entries.append(
            ParsedGettextEntry(
                entry_index=index,
                msgctxt=entry.msgctxt or "",
                msgid=entry.msgid,
                msgid_plural=entry.msgid_plural or "",
                msgstr=entry.msgstr or "",
                msgstr_plural={int(key): value for key, value in entry.msgstr_plural.items()},
                flags=list(entry.flags),
                comment=entry.comment or "",
                tcomment=entry.tcomment or "",
                occurrences=list(entry.occurrences),
                is_plural=bool(entry.msgid_plural),
                is_fuzzy="fuzzy" in entry.flags,
            )
        )

    return ParsedGettextFile(
        file_type=path.suffix.lstrip(".").lower(),
        path=path,
        metadata=dict(catalog.metadata),
        entries=entries,
    )
