"""Từ vựng Declare khớp ADR 0004 (task 4.1, Q6).

ADR 0004 (`docs/decisions/0004-nguon-cua-tung-mau-declare.md`) chốt từ vựng
hai tầng của giai đoạn 1: tầng 1 = `response`, `precedence` (miner khám phá,
eval đo, pm4py đối chiếu); tầng 2 = `succession`, `init`, `end`,
`not_response`, `not_precedence` (chỉ ghi nguồn để diễn giải, không phát sinh
fact). Test này khẳng định code khớp ADR: nếu ai đó thêm mẫu mới vào miner,
eval hay bảng đối nghịch của Curator mà không cập nhật ADR thì test đỏ.
"""

import pytest

from praxon_core.declare.index import Trace
from praxon_core.declare.miner import discover
from praxon_core.eval.metrics import Fact, FactScope, violation_rate
from praxon_core.learning.candidate import FactStatus
from praxon_core.learning.curator import OPPOSITE_TEMPLATES, opposite_template

TIER_1 = {"response", "precedence"}
TIER_2 = {"succession", "init", "end", "not_response", "not_precedence"}


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


def _fact(template: str) -> Fact:
    """Một fact `active` mẫu bất kỳ (activation/target không quan trọng ở đây)."""
    return Fact(
        canonical_key=f"{template}(a, b)",
        template=template,
        activation="a",
        target="b",
        status=FactStatus.ACTIVE,
        scope=FactScope.TENANT,
        tenant_id="acme",
    )


def test_miner_chi_sinh_mau_tang_1():
    rules = discover(_lat_nho(), support=0.5, confidence=0.5)
    assert len(rules) > 0
    assert {rule.template for rule in rules} == TIER_1


def test_eval_chi_chap_nhan_mau_tang_1():
    traces = _lat_nho()
    for template in sorted(TIER_1):
        assert isinstance(violation_rate([_fact(template)], traces), float)
    for template in sorted(TIER_2):
        with pytest.raises(ValueError):
            violation_rate([_fact(template)], traces)


def test_bang_doi_nghich_chi_co_hai_cap():
    assert OPPOSITE_TEMPLATES == {
        "response": "not_response",
        "not_response": "response",
        "precedence": "not_precedence",
        "not_precedence": "precedence",
    }
    assert opposite_template("response") == "not_response"
    assert opposite_template("not_response") == "response"
    assert opposite_template("precedence") == "not_precedence"
    assert opposite_template("not_precedence") == "precedence"
    for template in ("succession", "init", "end"):
        assert opposite_template(template) is None
