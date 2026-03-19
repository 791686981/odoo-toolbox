from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


REQUIRED_HEADERS = ["module", "type", "name", "res_id", "src", "value", "comments"]


@dataclass
class ParsedCsvRow:
    row_number: int
    data: Dict[str, str]


@dataclass
class ParsedCsv:
    headers: List[str]
    rows: List[ParsedCsvRow]


def parse_odoo_csv(path: Path) -> ParsedCsv:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV 文件缺少表头。")

        headers = list(reader.fieldnames)
        missing = [header for header in REQUIRED_HEADERS if header not in headers]
        if missing:
            raise ValueError("CSV 文件缺少必需字段: " + ", ".join(missing))

        rows = []
        for index, row in enumerate(reader, start=1):
            normalized = {key: (value or "") for key, value in row.items()}
            rows.append(ParsedCsvRow(row_number=index, data=normalized))

    return ParsedCsv(headers=headers, rows=rows)
