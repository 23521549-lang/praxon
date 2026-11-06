"""Bảng hồ sơ log XES (task 3.2, plan con 3)."""

from __future__ import annotations

import shutil
from pathlib import Path

from praxon_core.datasets.profile import format_profile, main, profile_log
from praxon_core.datasets.xes import iter_traces

FIXTURE = Path(__file__).parent / "fixtures" / "tiny.xes"


def test_iter_traces_doc_hai_case():
    traces = list(iter_traces(FIXTURE))
    assert len(traces) == 2
    assert traces[0].case_id == "case-1"
    assert traces[1].case_id == "case-2"
    assert traces[0].start is not None and traces[0].start.strftime("%Y-%m-%d") == "2024-01-15"
    assert traces[1].start is not None and traces[1].start.strftime("%Y-%m-%d") == "2024-02-20"
    assert len(traces[0].events) == 3
    assert len(traces[1].events) == 2
    assert [event.activity for event in traces[0].events] == ["A", "B", "A"]
    assert [event.activity for event in traces[1].events] == ["B", "C"]


def test_profile_log_dem_dung():
    profile = profile_log(FIXTURE, 1)
    assert profile.municipality == 1
    assert profile.cases == 2
    assert profile.events == 5
    assert profile.activity_types == frozenset({"A", "B", "C"})
    assert profile.start_min is not None
    assert profile.start_min.strftime("%Y-%m-%d") == "2024-01-15"
    assert profile.start_max is not None
    assert profile.start_max.strftime("%Y-%m-%d") == "2024-02-20"
    assert profile.cases_by_month == {"2024-01": 1, "2024-02": 1}
    assert "concept:name" in profile.trace_attributes
    assert "caseStatus" in profile.trace_attributes
    assert "startDate" in profile.trace_attributes
    assert "concept:name" in profile.event_attributes
    assert "time:timestamp" in profile.event_attributes
    assert "org:resource" in profile.event_attributes
    assert "lifecycle:transition" in profile.event_attributes


def test_format_profile_co_so_chinh():
    profile = profile_log(FIXTURE, 1)
    text = format_profile(profile)
    assert "2 case" in text
    assert "5 sự kiện" in text
    assert "3 loại hoạt động" in text
    assert "2024-01-15" in text
    assert "2024-02-20" in text


def test_main_thieu_tep_tra_1(tmp_path):
    assert main(["--cache-dir", str(tmp_path), "--dataset", "m1"]) == 1


def test_main_sai_so_case_tra_1(tmp_path):
    shutil.copy(FIXTURE, tmp_path / "BPIC15_1.xes")
    assert main(["--cache-dir", str(tmp_path), "--dataset", "m1"]) == 1
