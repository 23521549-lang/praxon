"""Lọc trước theo support x confidence: tập luật sau lọc trùng khi không lọc.

Lát nhỏ dùng trong test: 8 trace, hoạt động a/b/c thường xuyên, d/e hiếm
(chỉ 1/8 case). Với support=0,5 và confidence=0,5, ngưỡng lọc là 0,25 nên
d/e bị bỏ trước; không luật nào qua ngưỡng mà dính d/e nên hai tập luật
phải trùng nhau — đúng cổng ra của task 4.3.
"""

import random

import pytest

from praxon_core.declare.index import Trace
from praxon_core.declare.miner import (
    Rule,
    discover,
    discover_brute_force,
    frequent_activities,
)


def _lat_nho() -> list[Trace]:
    """8 trace: 6 trace (a, b, c), 1 trace (a, b, d), 1 trace (a, c, e)."""
    return [
        Trace(events=("a", "b", "c")),
        Trace(events=("a", "b", "c")),
        Trace(events=("a", "b", "c")),
        Trace(events=("a", "b", "c")),
        Trace(events=("a", "b", "c")),
        Trace(events=("a", "b", "c")),
        Trace(events=("a", "b", "d")),
        Trace(events=("a", "c", "e")),
    ]


def test_loc_truoc_khong_doi_tap_luat():
    traces = _lat_nho()
    expected = {
        Rule("response", "a", "b", 7 / 8, 7 / 8),
        Rule("response", "a", "c", 7 / 8, 7 / 8),
        Rule("response", "b", "c", 6 / 8, 6 / 7),
        Rule("precedence", "a", "b", 7 / 8, 1.0),
        Rule("precedence", "a", "c", 7 / 8, 1.0),
        Rule("precedence", "b", "c", 6 / 8, 6 / 7),
    }
    assert discover(traces, support=0.5, confidence=0.5) == expected
    assert discover_brute_force(traces, support=0.5, confidence=0.5) == expected


def test_loc_truoc_bang_khong_loc_tren_nhieu_nguong():
    traces = _lat_nho()
    for support, confidence in [(0.5, 0.5), (0.7, 0.9), (0.3, 0.8), (0.9, 0.9)]:
        assert discover(traces, support=support, confidence=confidence) == (
            discover_brute_force(traces, support=support, confidence=confidence)
        )


def test_loc_loai_hoat_dong_hiem():
    traces = _lat_nho()
    assert frequent_activities(traces, min_frequency=0.25) == {"a", "b", "c"}
    assert frequent_activities(traces, min_frequency=0.1) == {"a", "b", "c", "d", "e"}


def test_khoa_canonical_theo_spec():
    assert Rule("precedence", "a", "b", 0.5, 0.5).canonical_key == "precedence(a, b)"
    assert Rule("response", "a", "b", 0.5, 0.5).canonical_key == "response(a, b)"


def test_log_rong_thi_khong_co_luat():
    assert discover([], support=0.5, confidence=0.5) == frozenset()
    assert discover_brute_force([], support=0.5, confidence=0.5) == frozenset()
    assert frequent_activities([], min_frequency=0.25) == frozenset()


def test_mot_trace_thi_hai_bo_kham_pha_trung_nhau():
    traces = [Trace(events=("a", "b", "a", "c"))]
    assert discover(traces, support=0.5, confidence=0.5) == (
        discover_brute_force(traces, support=0.5, confidence=0.5)
    )


def test_ngau_nhien_lu_t_nho_hai_bo_kham_pha_trung_nhau():
    rng = random.Random(20261003)
    activities = ("a", "b", "c", "d")
    for _ in range(12):
        traces = [
            Trace(events=tuple(rng.choice(activities) for _ in range(rng.randint(1, 6))))
            for _ in range(rng.randint(1, 10))
        ]
        for support, confidence in [(0.5, 0.5), (0.2, 0.7), (0.8, 0.4)]:
            assert discover(traces, support=support, confidence=confidence) == (
                discover_brute_force(traces, support=support, confidence=confidence)
            )


def test_nguong_ngoai_khoang_bi_tu_choi():
    traces = _lat_nho()
    for support, confidence in [(-0.1, 0.5), (1.5, 0.5), (0.5, -0.1), (0.5, 1.5)]:
        with pytest.raises(ValueError):
            discover(traces, support=support, confidence=confidence)
        with pytest.raises(ValueError):
            discover_brute_force(traces, support=support, confidence=confidence)


def test_luat_khong_kich_hoat_thi_khong_qua():
    traces = [Trace(events=("x", "y")), Trace(events=("x", "y"))]
    found = discover(traces, support=0.5, confidence=0.5)
    assert all(rule.first != "z" and rule.second != "z" for rule in found)
    assert discover(traces, support=0.5, confidence=0.5) == (
        discover_brute_force(traces, support=0.5, confidence=0.5)
    )
