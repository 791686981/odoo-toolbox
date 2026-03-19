from __future__ import annotations

import csv
import io
from typing import Dict

from app.tools.csv_translation.parser import ParsedCsv


def export_translated_csv(parsed: ParsedCsv, row_results: Dict[int, Dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=parsed.headers)
    writer.writeheader()

    for row in parsed.rows:
        current = dict(row.data)
        result = row_results.get(row.row_number, {})
        edited_value = result.get("edited_value", "")
        translated_value = result.get("translated_value", "")
        current["value"] = edited_value or translated_value or current.get("value", "")
        writer.writerow(current)

    return ("\ufeff" + buffer.getvalue()).encode("utf-8")
