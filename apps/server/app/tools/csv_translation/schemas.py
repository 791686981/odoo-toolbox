from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class TranslationChunkItem:
    row_number: int
    source_text: str
    original_value: str
    raw_data: Dict[str, str]


@dataclass
class TranslationChunk:
    chunk_index: int
    items: List[TranslationChunkItem]
