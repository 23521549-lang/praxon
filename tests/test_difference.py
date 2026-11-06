"""Test báo cáo khác biệt giữa năm đô thị (task 3.4)."""

from collections import Counter
from pathlib import Path

import pytest

from praxon_core.datasets.difference import (
    ActivityCounts,
    build_difference_report,
    count_activity_cases,
    filter_activities,
    format_difference_report,
    jaccard,
    main,
    validate_fractions,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_count_activity_cases_counts_each_activity_once_per_case():
    counts = count_activity_cases(FIXTURES / "tiny.xes")
    assert counts.n_cases == 2
    assert counts.n_events == 5
    assert counts.problems == []
    # A ở 1 case, B ở 2 case, C ở 1 case (dù A lặp 2 lần trong case-1).
    assert counts.case_counts == Counter({"A": 1, "B": 2, "C": 1})


def test_count_activity_cases_four_cases():
    counts = count_activity_cases(FIXTURES / "four-cases.xes")
    assert counts.n_cases == 4
    assert counts.n_events == 7
    assert counts.problems == []
    assert counts.case_counts == Counter({"A": 3, "B": 2, "C": 2})


def test_count_activity_cases_detects_missing_fields():
    counts = count_activity_cases(FIXTURES / "missing-field.xes")
    assert counts.n_cases == 3
    # Một trace thiếu concept:name, một event thiếu concept:name.
    assert len(counts.problems) == 2
    assert any("thiếu concept:name (case_id rỗng)" in p for p in counts.problems)
    assert any("có event thiếu concept:name" in p for p in counts.problems)
    # Hoạt động rỗng không được đếm.
    assert "" not in counts.case_counts


def test_filter_activities_keeps_frequent():
    remaining, removed = filter_activities(Counter({"A": 3, "B": 2, "C": 2}), 4, 0.5, 0.5)
    assert remaining == frozenset({"A", "B", "C"})
    assert removed == {}


def test_filter_activities_removes_rare():
    remaining, removed = filter_activities(Counter({"A": 3, "B": 2, "C": 2}), 4, 0.8, 0.8)
    # Ngưỡng 0.64: chỉ A (0.75) còn; B và C (0.5) bị loại.
    assert remaining == frozenset({"A"})
    assert removed == {"B": 0.5, "C": 0.5}


def test_filter_activities_rejects_invalid_params():
    with pytest.raises(ValueError):
        filter_activities(Counter({"A": 1}), 1, 0.0, 0.5)
    with pytest.raises(ValueError):
        filter_activities(Counter({"A": 1}), 1, 0.5, 1.5)
    with pytest.raises(ValueError):
        filter_activities(Counter({"A": 1}), 0, 0.5, 0.5)


def test_validate_fractions():
    validate_fractions(0.5, 0.5)
    validate_fractions(1.0, 1.0)
    with pytest.raises(ValueError):
        validate_fractions(0.0, 0.5)


def test_jaccard():
    assert jaccard(frozenset({"A", "B", "C"}), frozenset({"B", "C", "D"})) == 0.5
    assert jaccard(frozenset(), frozenset()) == 1.0
    assert jaccard(frozenset({"A"}), frozenset({"B"})) == 0.0
    assert jaccard(frozenset({"A", "B"}), frozenset({"A", "B"})) == 1.0


def _counts(activities: dict[str, int], n_cases: int = 4) -> ActivityCounts:
    return ActivityCounts(
        n_cases=n_cases,
        n_events=n_cases,
        case_counts=Counter(activities),
    )


def test_build_difference_report():
    report = build_difference_report(
        {
            1: _counts({"A": 4, "B": 3, "C": 2}),
            2: _counts({"B": 4, "C": 3, "D": 2}),
        },
        0.5,
        0.5,
    )
    assert report.union == frozenset({"A", "B", "C", "D"})
    assert report.common == frozenset({"B", "C"})
    assert report.pairwise_jaccard == {(1, 2): 0.5}
    # Ngưỡng 0.25: mọi hoạt động đều còn.
    assert report.municipalities[0].remaining == frozenset({"A", "B", "C"})
    assert report.municipalities[1].remaining == frozenset({"B", "C", "D"})
    assert report.municipalities[0].removed == {}


def test_build_difference_report_filters_rare():
    report = build_difference_report(
        {1: _counts({"A": 4, "B": 1}, n_cases=4)},
        0.8,
        0.8,
    )
    # Ngưỡng 0.64: A (1.0) còn, B (0.25) bị loại.
    assert report.municipalities[0].remaining == frozenset({"A"})
    assert report.municipalities[0].removed == {"B": 0.25}


def test_format_difference_report():
    report = build_difference_report(
        {
            1: _counts({"A": 4, "B": 3, "C": 2}),
            2: _counts({"B": 4, "C": 3, "D": 2}),
        },
        0.5,
        0.5,
    )
    text = format_difference_report(report)
    assert "Đô thị 1: 4 case" in text
    assert "3 hoạt động → còn 3" in text
    assert "Hợp năm đô thị: 4 hoạt động; chung cả năm: 2 hoạt động" in text
    assert "1-2: 0.500" in text


def test_main_missing_file(tmp_path):
    assert main(["--cache-dir", str(tmp_path), "--dataset", "m1"]) == 1


def test_main_broken_log(tmp_path):
    (tmp_path / "BPIC15_1.xes").write_bytes((FIXTURES / "broken.xes").read_bytes())
    assert main(["--cache-dir", str(tmp_path), "--dataset", "m1"]) == 1


def test_main_missing_field(tmp_path):
    (tmp_path / "BPIC15_1.xes").write_bytes((FIXTURES / "missing-field.xes").read_bytes())
    assert main(["--cache-dir", str(tmp_path), "--dataset", "m1"]) == 2


def test_main_invalid_fractions():
    assert main(["--support", "0"]) == 3
    assert main(["--confidence", "1.5"]) == 3


def test_main_real_m1(capsys):
    assert main(["--dataset", "m1", "--support", "0.5", "--confidence", "0.5"]) == 0
    out = capsys.readouterr().out
    assert "Đô thị 1: 1199 case" in out
    assert "hoạt động → còn" in out
