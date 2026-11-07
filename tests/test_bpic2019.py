"""Kiểm điều kiện thuộc tính phân loại trên BPIC 2019 (task 9.5).

Test dùng fixture XES nhỏ tự viết (không commit log thật); test đo thật
dùng log trong cache thì ``pytest.skip`` khi cache trống (theo mẫu 6.5).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from praxon_core.learning import bpic2019
from praxon_core.learning.bpic2019 import (
    BPIC2019_EXPECTED_MD5,
    BPIC2019_FILENAME,
    Bpic2019Error,
    MatchingCounts,
    calibrate_min_matching_cases,
    check_matching_conditions,
    count_matching_cases,
    format_report,
    main,
    verify_bpic2019,
)
from praxon_core.learning.candidate import DecisionVerdict
from praxon_core.learning.rules import default_rule_table

_FIXTURE_XES = """<?xml version="1.0" encoding="UTF-8" ?>
<log xes.version="1.0" xes.features="nested-attributes" xmlns="http://www.xes-standard.org/">
\t<trace>
\t\t<string key="concept:name" value="case-a"/>
\t\t<date key="startDate" value="2018-03-01T00:00:00+01:00"/>
\t\t<string key="Item Category" value="2-way match"/>
\t\t<event>
\t\t\t<string key="concept:name" value="A"/>
\t\t\t<date key="time:timestamp" value="2018-03-01T00:00:00+01:00"/>
\t\t</event>
\t</trace>
\t<trace>
\t\t<string key="concept:name" value="case-b"/>
\t\t<date key="startDate" value="2018-05-01T00:00:00+01:00"/>
\t\t<string key="Item Category" value="2-way match"/>
\t\t<event>
\t\t\t<string key="concept:name" value="A"/>
\t\t\t<date key="time:timestamp" value="2018-05-01T00:00:00+01:00"/>
\t\t</event>
\t</trace>
\t<trace>
\t\t<string key="concept:name" value="case-c"/>
\t\t<date key="startDate" value="2018-02-01T00:00:00+01:00"/>
\t\t<string key="Item Category" value="Consignment"/>
\t\t<event>
\t\t\t<string key="concept:name" value="A"/>
\t\t\t<date key="time:timestamp" value="2018-02-01T00:00:00+01:00"/>
\t\t</event>
\t</trace>
\t<trace>
\t\t<string key="concept:name" value="case-d"/>
\t\t<date key="startDate" value="2019-01-15T00:00:00+01:00"/>
\t\t<string key="Item Category" value="2-way match"/>
\t\t<event>
\t\t\t<string key="concept:name" value="A"/>
\t\t\t<date key="time:timestamp" value="2019-01-15T00:00:00+01:00"/>
\t\t</event>
\t</trace>
\t<trace>
\t\t<string key="concept:name" value="case-e"/>
\t\t<date key="startDate" value="2018-04-01T00:00:00+01:00"/>
\t\t<event>
\t\t\t<string key="concept:name" value="A"/>
\t\t\t<date key="time:timestamp" value="2018-04-01T00:00:00+01:00"/>
\t\t</event>
\t</trace>
\t<trace>
\t\t<string key="concept:name" value="case-f"/>
\t\t<string key="Item Category" value="2-way match"/>
\t\t<event>
\t\t\t<string key="concept:name" value="A"/>
\t\t</event>
\t</trace>
</log>
"""


def _fixture_path(tmp_path: Path) -> Path:
    path = tmp_path / "mini.xes"
    path.write_text(_FIXTURE_XES, encoding="utf-8")
    return path


def _counts(**overrides: object) -> MatchingCounts:
    data: dict[str, object] = {
        "total": 0,
        "counts": {},
        "out_of_year": {},
        "missing_item_category": 0,
        "no_start": 0,
    }
    data.update(overrides)
    return MatchingCounts(**data)  # type: ignore[arg-type]


def test_dem_theo_loai_matching_loai_ngoai_nam_va_thieu_thuoc_tinh(tmp_path):
    counts = count_matching_cases(_fixture_path(tmp_path))
    assert counts.total == 6
    assert counts.counts == {"2-way match": 3, "Consignment": 1}
    assert counts.out_of_year == {"2-way match": 1}
    assert counts.missing_item_category == 1
    assert counts.no_start == 1


def test_duoi_30_case_bi_luat_7_loai():
    table = default_rule_table()
    counts = _counts(counts={"2-way match": 29})
    checks = check_matching_conditions(counts, table)
    assert len(checks) == 1
    assert checks[0].value == "2-way match"
    assert checks[0].cases == 29
    assert checks[0].rule_id == 7
    assert checks[0].verdict == DecisionVerdict.REJECT


def test_du_30_case_duoc_luat_2_duyet_len_trial():
    table = default_rule_table()
    counts = _counts(counts={"2-way match": 30})
    checks = check_matching_conditions(counts, table)
    assert len(checks) == 1
    assert checks[0].rule_id == 2
    assert checks[0].verdict == DecisionVerdict.AUTO_APPROVE


def test_tron_loai_duoi_va_du_nguong():
    table = default_rule_table()
    counts = _counts(counts={"2-way match": 29, "Consignment": 30})
    checks = check_matching_conditions(counts, table)
    by_value = {check.value: check for check in checks}
    assert by_value["2-way match"].rule_id == 7
    assert by_value["2-way match"].verdict == DecisionVerdict.REJECT
    assert by_value["Consignment"].rule_id == 2
    assert by_value["Consignment"].verdict == DecisionVerdict.AUTO_APPROVE


def test_hieu_chinh_tat_ca_du_nguong():
    table = default_rule_table()
    counts = _counts(counts={"2-way match": 891, "Consignment": 14494})
    result = calibrate_min_matching_cases(counts, table)
    assert result.threshold == 30
    assert result.min_cases == 891
    assert result.min_value == "2-way match"
    assert result.n_types == 2
    assert result.all_pass is True
    assert result.below == ()


def test_hieu_chinh_co_loai_duoi_nguong():
    table = default_rule_table()
    counts = _counts(counts={"2-way match": 29, "Consignment": 14494})
    result = calibrate_min_matching_cases(counts, table)
    assert result.all_pass is False
    assert result.below == ("2-way match",)
    assert result.min_cases == 29


def test_hieu_chinh_khong_co_loai_nao():
    table = default_rule_table()
    counts = _counts()
    result = calibrate_min_matching_cases(counts, table)
    assert result.threshold == 30
    assert result.min_cases == 0
    assert result.min_value == ""
    assert result.n_types == 0
    assert result.all_pass is False


def test_bao_cao_in_du_so_case_va_quyet_dinh():
    table = default_rule_table()
    counts = _counts(
        total=6,
        counts={"2-way match": 3, "Consignment": 1},
        out_of_year={"2-way match": 1},
        missing_item_category=1,
        no_start=1,
    )
    checks = check_matching_conditions(counts, table)
    calibration = calibrate_min_matching_cases(counts, table)
    text = format_report(counts, checks, calibration, Path("BPI_Challenge_2019.xes"))
    assert "2-way match | 3 | 7 | reject" in text
    assert "Consignment | 1 | 7 | reject" in text
    assert "tổng case: 6" in text
    assert "ngoài năm: 1" in text
    assert "thiếu Item Category: 1" in text
    assert "min_matching_cases=30" in text
    assert "không dùng được cho luật có điều kiện" in text


def test_thieu_tep_bao_loi_du_lieu(tmp_path):
    with pytest.raises(Bpic2019Error, match="thiếu tệp"):
        verify_bpic2019(tmp_path / "khong-co.xes")


def test_tep_sai_kich_co_bao_loi_du_lieu(tmp_path):
    path = tmp_path / "sai.xes"
    path.write_text("nho", encoding="utf-8")
    with pytest.raises(Bpic2019Error, match="kích cỡ"):
        verify_bpic2019(path)


def test_tep_sai_md5_bao_loi_du_lieu(tmp_path, monkeypatch):
    path = tmp_path / "sai-md5.xes"
    path.write_bytes(b"noi dung sai md5")
    monkeypatch.setattr(bpic2019, "BPIC2019_EXPECTED_SIZE", path.stat().st_size)
    with pytest.raises(Bpic2019Error, match="md5"):
        verify_bpic2019(path)


def test_lenh_thieu_tep_tra_1(tmp_path):
    assert main(["--cache-dir", str(tmp_path)]) == 1


def test_bao_cao_khi_tat_ca_du_nguong():
    table = default_rule_table()
    counts = _counts(counts={"2-way match": 891, "Consignment": 14494})
    checks = check_matching_conditions(counts, table)
    calibration = calibrate_min_matching_cases(counts, table)
    text = format_report(counts, checks, calibration, Path("BPI_Challenge_2019.xes"))
    assert "2-way match | 891 | 2 | auto_approve" in text
    assert "ngưỡng được giữ nguyên" in text


def test_lenh_chay_duoc_voi_du_lieu_gia(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(bpic2019, "verify_bpic2019", lambda path: None)
    monkeypatch.setattr(
        bpic2019,
        "count_matching_cases",
        lambda path: _counts(
            total=3,
            counts={"2-way match": 2, "Consignment": 1},
        ),
    )
    assert main(["--cache-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "2-way match | 2 | 7 | reject" in out
    assert "Consignment | 1 | 7 | reject" in out
    assert "min_matching_cases=30" in out


def test_xac_minh_tep_that_trong_cache():
    path = Path.home() / ".cache" / "praxon" / "bpic2019" / BPIC2019_FILENAME
    if not path.is_file():
        pytest.skip("cache BPIC 2019 trống")
    verify_bpic2019(path)
    assert path.stat().st_size == 728558522
    assert BPIC2019_EXPECTED_MD5 == "4eb909242351193a61e1c15b9c3cc814"
