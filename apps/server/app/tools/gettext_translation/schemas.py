from __future__ import annotations

from pydantic import BaseModel, Field


class GettextEntryCandidate(BaseModel):
    entry_index: int
    msgid: str
    msgstr: str = ""
    msgstr_plural: dict[int, str] = Field(default_factory=dict)
    is_plural: bool = False
    is_fuzzy: bool = False
    obsolete: bool = False
