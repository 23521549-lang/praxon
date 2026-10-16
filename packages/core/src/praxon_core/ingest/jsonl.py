r"""Parse JSONL: mỗi dòng một event, lỗi báo đúng số dòng (task 2.2).

Bảng hành vi (mỗi ô có test tương ứng trong tests/test_ingest_jsonl.py):
- BOM ở đầu luồng: strip — tự loại `\\ufeff` ở dòng đầu, không tin caller.
- CRLF: xử lý bình thường (universal newlines).
- Dòng trống / chỉ whitespace: bỏ qua, đếm vào stats (file thực tế hay có
  newline thừa cuối file — từ chối nó thì parser giòn không cần thiết).
- JSON vỡ / không phải object / sai lược đồ: `JsonlError` mang `line_no`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import NamedTuple

from pydantic import ValidationError

from praxon_core.ingest.schema import Event


class JsonlError(ValueError):
    """Một dòng JSONL hỏng: mang số dòng (1-based) và mã lý do."""

    def __init__(self, line_no: int, reason: str, line: str) -> None:
        """Ghi nhận dòng hỏng. `reason` là mã máy đọc, không phải câu văn."""
        super().__init__(f"dòng {line_no}: {reason}")
        self.line_no = line_no
        self.reason = reason
        self.line = line


class ParsedLine(NamedTuple):
    """Một dòng parse xong, giữ số dòng để tầng trên báo lỗi chính xác."""

    line_no: int
    event: Event


class ParseStats(NamedTuple):
    """Thống kê một lần parse: đọc bao nhiêu, bỏ bao nhiêu, được bao nhiêu."""

    lines_read: int
    lines_skipped_blank: int
    events: int


def parse_jsonl(lines: Iterable[str]) -> tuple[list[ParsedLine], ParseStats]:
    """Parse từng dòng thành Event. Dòng hỏng -> JsonlError mang số dòng."""
    parsed: list[ParsedLine] = []
    lines_read = 0
    skipped_blank = 0
    for line_no, raw in enumerate(lines, start=1):
        lines_read += 1
        if line_no == 1:
            raw = raw.lstrip("\ufeff")
        if not raw.strip():
            skipped_blank += 1
            continue
        parsed.append(ParsedLine(line_no, _parse_line(raw, line_no)))
    return parsed, ParseStats(lines_read, skipped_blank, len(parsed))


def _parse_line(raw: str, line_no: int) -> Event:
    """Parse một dòng: JSON phải là object đúng lược đồ Event."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JsonlError(line_no, "json_vo", raw) from exc
    if not isinstance(data, dict):
        raise JsonlError(line_no, "khong_phai_object", raw)
    try:
        return Event.model_validate(data)
    except ValidationError as exc:
        raise JsonlError(line_no, "sai_luoc_do", raw) from exc
