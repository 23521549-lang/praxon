"""JSONL: BOM, CRLF, dòng trống, và 6 test âm báo đúng số dòng."""

from __future__ import annotations

import pytest

from praxon_core.ingest.jsonl import JsonlError, parse_jsonl


def _line(
    case: str = "c1",
    variant: str = "standard",
    activity: str = "approve",
    ts: str = "2015-06-01T10:00:00+07:00",
) -> str:
    return (
        f'{{"case_id": "{case}", "variant": "{variant}", '
        f'"activity": "{activity}", "occurred_at": "{ts}"}}'
    )


def test_bom_duoc_strip():
    parsed, stats = parse_jsonl(["\ufeff" + _line(), _line(case="c2")])
    assert [p.event.case_id for p in parsed] == ["c1", "c2"]
    assert stats.events == 2


def test_crlf_duoc_xu_ly():
    parsed, _ = parse_jsonl([_line() + "\r\n", _line(case="c2") + "\r\n"])
    assert len(parsed) == 2


def test_dong_trong_duoc_bo_qua_va_dem():
    parsed, stats = parse_jsonl([_line(), "", "   ", _line(case="c2")])
    assert stats.lines_read == 4
    assert stats.lines_skipped_blank == 2
    assert stats.events == 2
    assert [p.line_no for p in parsed] == [1, 4]


def test_json_vo_bao_dung_so_dong():
    with pytest.raises(JsonlError) as exc_info:
        parse_jsonl([_line(), _line(case="c2"), "{voooo"])
    assert exc_info.value.line_no == 3
    assert exc_info.value.reason == "json_vo"


def test_json_khong_phai_object_bao_dung_so_dong():
    with pytest.raises(JsonlError) as exc_info:
        parse_jsonl(["[1, 2]"])
    assert exc_info.value.line_no == 1
    assert exc_info.value.reason == "khong_phai_object"


def test_thieu_truong_bat_buoc_bao_dung_so_dong():
    with pytest.raises(JsonlError) as exc_info:
        parse_jsonl([_line(), '{"case_id": "c2"}'])
    assert exc_info.value.line_no == 2
    assert exc_info.value.reason == "sai_luoc_do"
