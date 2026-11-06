"""Governor: hàm thuần đánh giá candidate theo bảng luật.

Duyệt luật từ trên xuống, luật đầu tiên khớp thì thắng. Không luật nào khớp
thì cần người duyệt. Trả Decision kèm bản sao candidate đã ghi `rule_id` và
`metrics_at_decision`, để chạy lại ra đúng quyết định cũ.
"""

from __future__ import annotations

from typing import cast

from praxon_core.learning.candidate import (
    Candidate,
    Decision,
    DecisionVerdict,
    GovernorResult,
)
from praxon_core.learning.measures import MeasureName, Measures, measures_to_dict
from praxon_core.learning.rules import (
    AllCondition,
    AnyCondition,
    Comparison,
    ComparisonOp,
    Condition,
    NotCondition,
    RuleTable,
)

_MeasureValue = bool | float | int | str | None
_ConditionValue = bool | float | int | str | list[bool | float | int | str]


def _measure_value(measures: Measures, name: MeasureName) -> _MeasureValue:
    """Đọc một đại lượng theo tên (tên khớp đúng tên trường của Measures)."""
    return cast(_MeasureValue, getattr(measures, name.value))


def _compare_numbers(actual: float | int, op: ComparisonOp, expected: float | int) -> bool:
    """So sánh thứ tự khi cả hai vế đều là số."""
    if op is ComparisonOp.LT:
        return actual < expected
    if op is ComparisonOp.LE:
        return actual <= expected
    if op is ComparisonOp.GT:
        return actual > expected
    return actual >= expected


def _compare_strings(actual: str, op: ComparisonOp, expected: str) -> bool:
    """So sánh thứ tự khi cả hai vế đều là str."""
    if op is ComparisonOp.LT:
        return actual < expected
    if op is ComparisonOp.LE:
        return actual <= expected
    if op is ComparisonOp.GT:
        return actual > expected
    return actual >= expected


def _compare(actual: _MeasureValue, op: ComparisonOp, expected: _ConditionValue) -> bool:
    """So sánh một đại lượng với giá trị trong điều kiện."""
    if op is ComparisonOp.EQ:
        return actual == expected
    if op is ComparisonOp.NE:
        return actual != expected
    if op is ComparisonOp.IN:
        return isinstance(expected, list) and actual in expected
    if op is ComparisonOp.NOT_IN:
        return isinstance(expected, list) and actual not in expected
    if (
        actual is None
        or expected is None
        or isinstance(actual, bool)
        or isinstance(expected, (bool, list))
    ):
        raise ValueError(f"phép {op.value} không dùng cho giá trị {actual!r}")
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return _compare_numbers(actual, op, expected)
    if isinstance(actual, str) and isinstance(expected, str):
        return _compare_strings(actual, op, expected)
    raise ValueError(f"không so sánh được {actual!r} với {expected!r}")


def evaluate_condition(condition: Condition, measures: Measures) -> bool:
    """Đánh giá một điều kiện trên số đo; cây dữ liệu, không dùng eval."""
    if isinstance(condition, Comparison):
        value = _measure_value(measures, condition.measure)
        return _compare(value, condition.op, condition.value)
    if isinstance(condition, AllCondition):
        return all(evaluate_condition(child, measures) for child in condition.children)
    if isinstance(condition, AnyCondition):
        return any(evaluate_condition(child, measures) for child in condition.children)
    if isinstance(condition, NotCondition):
        return not evaluate_condition(condition.child, measures)
    raise ValueError(f"điều kiện lạ: {condition!r}")  # pragma: no cover


def decide(candidate: Candidate, table: RuleTable, measures: Measures) -> GovernorResult:
    """Đánh giá candidate theo bảng luật, luật đầu khớp thì thắng.

    Ghi `rule_id` và `metrics_at_decision` vào bản sao candidate rồi trả cùng
    Decision. Không luật nào khớp thì cần người duyệt (rule_id None).
    """
    metrics = measures_to_dict(measures)
    for rule in table.rules:
        if evaluate_condition(rule.condition, measures):
            decision = Decision(
                verdict=rule.verdict,
                target_status=rule.target_status,
                rule_id=rule.id,
                reason=f"Luật {rule.id} khớp: {rule.applies_to}",
            )
            updated = candidate.model_copy(
                update={"rule_id": rule.id, "metrics_at_decision": metrics}
            )
            return GovernorResult(decision=decision, candidate=updated)
    decision = Decision(
        verdict=DecisionVerdict.NEEDS_HUMAN,
        target_status=None,
        rule_id=None,
        reason="Không luật nào khớp",
    )
    updated = candidate.model_copy(update={"rule_id": None, "metrics_at_decision": metrics})
    return GovernorResult(decision=decision, candidate=updated)
