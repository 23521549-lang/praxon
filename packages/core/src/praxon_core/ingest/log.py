"""Lắp event thành log: nhóm theo case, kiểm danh tính, tính data_hash.

Bất biến danh tính (task 2.5): `case_id → variant` là phụ thuộc hàm — một
case_id chỉ gắn đúng một variant. Dòng nào khai variant khác với variant đã
thấy của cùng case_id thì bị từ chối, báo đúng số dòng (bắt log bị trộn
hoặc gán nhãn sai trước khi nó lọt vào Declare mining).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import datetime

from praxon_core.ingest.jsonl import ParsedLine, parse_jsonl
from praxon_core.ingest.schema import Case, Log


class DuplicateCaseError(ValueError):
    """Cùng case_id nhưng khai variant khác nhau: dữ liệu hỏng."""

    def __init__(self, case_id: str, expected: str, got: str, line_no: int) -> None:
        """Ghi nhận xung đột: variant đã thấy, variant mới, và dòng gây lỗi."""
        super().__init__(
            f"case {case_id!r}: đã thấy variant {expected!r}, "
            f"dòng {line_no} khai variant {got!r}"
        )
        self.case_id = case_id
        self.expected = expected
        self.got = got
        self.line_no = line_no


def build_log(parsed: Iterable[ParsedLine]) -> Log:
    """Nhóm event theo case, kiểm phụ thuộc hàm case_id → variant."""
    groups: dict[str, list[ParsedLine]] = {}
    variants: dict[str, str] = {}
    for item in parsed:
        case_id = item.event.case_id
        variant = item.event.variant
        known = variants.get(case_id)
        if known is None:
            variants[case_id] = variant
            groups[case_id] = []
        elif known != variant:
            raise DuplicateCaseError(case_id, known, variant, item.line_no)
        groups[case_id].append(item)

    cases = tuple(
        Case(
            case_id=case_id,
            variant=variants[case_id],
            events=tuple(p.event for p in sorted(groups[case_id], key=_event_order)),
        )
        for case_id in groups
    )
    ordered = tuple(sorted(cases, key=lambda c: c.case_id))
    return Log(cases=ordered, data_hash=_hash_cases(ordered))


def load_log(lines: Iterable[str]) -> Log:
    """Entry point duy nhất: parse JSONL rồi build log. Dùng cho plan con 3/5."""
    parsed, _stats = parse_jsonl(lines)
    return build_log(parsed)


def canonical_hash(log: Log) -> str:
    """Tính lại data_hash từ log — để test kiểm độc lập với build_log."""
    return _hash_cases(log.cases)


def _event_order(item: ParsedLine) -> tuple[datetime, str]:
    """Khoá sắp event trong case: theo thời điểm, rồi theo tên cho quyết định."""
    return (item.event.occurred_at, item.event.activity)


def _hash_cases(cases: tuple[Case, ...]) -> str:
    """Băm dạng chuẩn: sort keys, UTC ISO, sha256.

    Mọi timestamp đã về UTC từ lúc parse (task 2.3) nên cùng một log viết ở
    hai múi giờ cho cùng một hash. Dạng chuẩn này plan con 5 dùng lại cho
    trường `data_hash` của bảng `run` — định nghĩa một lần ở đây.
    """
    canonical = json.dumps(
        [
            {
                "case_id": case.case_id,
                "variant": case.variant,
                "events": [
                    {"activity": e.activity, "occurred_at": e.occurred_at.isoformat()}
                    for e in case.events
                ],
            }
            for case in sorted(cases, key=lambda c: c.case_id)
        ],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
