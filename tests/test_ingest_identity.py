"""Danh tính case: case_id -> variant là phụ thuộc hàm (task 2.5)."""

from __future__ import annotations

import pytest

from praxon_core.ingest.jsonl import parse_jsonl
from praxon_core.ingest.log import DuplicateCaseError, build_log


def _lines() -> list[str]:
    return [
        '{"case_id": "c1", "variant": "Standard", "activity": "a",'
        ' "occurred_at": "2015-06-01T10:00:00+07:00"}',
        '{"case_id": "c1", "variant": "Standard", "activity": "b",'
        ' "occurred_at": "2015-06-01T11:00:00+07:00"}',
        '{"case_id": "c2", "variant": "Deviant", "activity": "a",'
        ' "occurred_at": "2015-06-01T10:00:00+07:00"}',
    ]


def test_cung_case_id_khac_variant_bi_tu_choi_dung_dong():
    lines = [
        *_lines(),
        '{"case_id": "c1", "variant": "Deviant", "activity": "c",'
        ' "occurred_at": "2015-06-01T12:00:00+07:00"}',
    ]
    parsed, _ = parse_jsonl(lines)
    with pytest.raises(DuplicateCaseError) as exc_info:
        build_log(parsed)
    err = exc_info.value
    assert err.case_id == "c1"
    assert err.line_no == 4
    assert err.expected == "standard"
    assert err.got == "deviant"


def test_variant_chuan_hoa_truoc_khi_so_sanh():
    # "Standard" và "STANDARD " là một variant sau chuẩn hoá —
    # không được báo xung đột giả.
    lines = [
        '{"case_id": "c1", "variant": "Standard", "activity": "a",'
        ' "occurred_at": "2015-06-01T10:00:00+07:00"}',
        '{"case_id": "c1", "variant": "STANDARD ", "activity": "b",'
        ' "occurred_at": "2015-06-01T11:00:00+07:00"}',
    ]
    parsed, _ = parse_jsonl(lines)
    log = build_log(parsed)
    assert len(log.cases) == 1
    assert log.cases[0].variant == "standard"


def test_nhom_event_theo_case_va_sap_theo_thoi_gian():
    parsed, _ = parse_jsonl(_lines())
    log = build_log(parsed)
    assert [c.case_id for c in log.cases] == ["c1", "c2"]
    assert [e.activity for e in log.cases[0].events] == ["a", "b"]
    assert log.data_hash != ""
