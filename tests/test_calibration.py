"""Hiệu chỉnh cổng Beta (task 9.6): từ chối phần đo, ≥3 độ mạnh trong vùng."""

from __future__ import annotations

import pytest

from praxon_core.declare.index import Trace
from praxon_core.declare.miner import Rule, _brute_counts, discover
from praxon_core.eval.ground_truth import ground_truth_from_generator
from praxon_core.eval.report import split_generated_traces
from praxon_core.learning.beta import PriorInvariantError
from praxon_core.learning.calibration import (
    CALIBRATION_STRENGTHS,
    calibrate_beta,
    count_rule_evidence,
    evaluate_strength,
)
from praxon_core.learning.rules import Policy, default_rule_table
from praxon_core.synthetic.generator import GeneratorParams, generate


def _benchmark() -> tuple[tuple[Trace, ...], tuple[Trace, ...], frozenset[str], Policy]:
    """Bộ chuẩn (hạt 42, 300 trace): 180 học / 60 hiệu chỉnh / đáp án."""
    log = generate(tenant_id="acme", params=GeneratorParams(seed=42, n_cases=300))
    train, _test = split_generated_traces(log.traces)
    calibration = tuple(log.traces[len(train) : len(train) + 60])
    return (
        train,
        calibration,
        ground_truth_from_generator(log).reference,
        default_rule_table().policy,
    )


def _traces(*events_list: tuple[str, ...]) -> tuple[Trace, ...]:
    return tuple(Trace(events=tuple(events)) for events in events_list)


def test_tu_choi_hieu_chinh_tren_phan_do():
    train, calibration, ground_truth, policy = _benchmark()
    with pytest.raises(ValueError, match="phần đo"):
        calibrate_beta(
            split="test",
            train_traces=train,
            calibration_traces=calibration,
            ground_truth=ground_truth,
            policy=policy,
        )
    # Từ chối đứng trước mọi đánh giá: dữ liệu rỗng vẫn ra lỗi phần đo,
    # không phải lỗi dữ liệu rỗng hay lỗi không có luật thử.
    with pytest.raises(ValueError, match="phần đo"):
        calibrate_beta(
            split="test",
            train_traces=(),
            calibration_traces=(),
            ground_truth=frozenset(),
            policy=policy,
        )


def test_do_manh_thu_it_nhat_ba_gia_tri_trong_vung_bat_bien():
    train, calibration, ground_truth, policy = _benchmark()
    result = calibrate_beta(
        split="calibration",
        train_traces=train,
        calibration_traces=calibration,
        ground_truth=ground_truth,
        policy=policy,
    )
    assert result.strengths == CALIBRATION_STRENGTHS
    assert len(result.strengths) >= 3
    assert result.selected_strength == 2.0
    by_strength = {outcome.strength: outcome for outcome in result.outcomes}
    # Tất cả trong vùng bất biến: biên > 0, tức tiên nghiệm xấu nhất
    # (độ tin 1,0) một mình vẫn dưới ngưỡng lên 0,95.
    assert by_strength[2.0].invariant_margin == pytest.approx(0.2930, abs=1e-4)
    assert by_strength[4.0].invariant_margin == pytest.approx(0.1181, abs=1e-4)
    assert by_strength[6.0].invariant_margin == pytest.approx(0.0324, abs=1e-4)
    # 20 luật thử, tất cả đúng, tất cả lên, không lỗi nào.
    for outcome in result.outcomes:
        assert outcome.false_promotes == 0
        assert outcome.false_retires == 0
        assert outcome.promoted == 20
        assert outcome.retired == 0
        assert outcome.undecided == 0
    # Lên nhanh dần theo độ mạnh giảm — tiêu chí hòa để chọn 2,0.
    assert by_strength[2.0].median_traces_to_promote == 13.0
    assert by_strength[4.0].median_traces_to_promote == 16.0
    assert by_strength[6.0].median_traces_to_promote == 20.0


def test_do_manh_ngoai_vung_bi_tu_choi():
    train, calibration, ground_truth, policy = _benchmark()
    with pytest.raises(PriorInvariantError):
        calibrate_beta(
            split="calibration",
            train_traces=train,
            calibration_traces=calibration,
            ground_truth=ground_truth,
            policy=policy,
            strengths=[8.0],
        )


def test_dem_bang_chung_khop_miner():
    log = generate(tenant_id="acme", params=GeneratorParams(seed=7, n_cases=50))
    rules = discover(log.traces, support=0.5, confidence=0.5)
    assert len(rules) == 20
    templates = {rule.template for rule in rules}
    assert templates == {"response", "precedence"}
    for rule in rules:
        evidence = count_rule_evidence(rule, log.traces)
        satisfied, activated = _brute_counts(log.traces, rule.first, rule.second, rule.template)
        assert (evidence.successes, evidence.trials) == (satisfied, activated)


def test_luat_sai_len_sai_bi_dem():
    policy = default_rule_table().policy
    false_rule = Rule(template="response", first="a", second="b", support=1.0, confidence=1.0)
    holds = _traces(("a", "b")) * 30
    outcome = evaluate_strength(
        trial_rules=[false_rule],
        calibration_traces=holds,
        ground_truth=frozenset(),
        policy=policy,
        strength=2.0,
    )
    assert outcome.promoted == 1
    assert outcome.false_promotes == 1
    assert outcome.false_retires == 0


def test_luat_dung_go_sai_bi_dem():
    policy = default_rule_table().policy
    true_rule = Rule(template="response", first="a", second="b", support=1.0, confidence=1.0)
    violates = _traces(("a",)) * 30
    outcome = evaluate_strength(
        trial_rules=[true_rule],
        calibration_traces=violates,
        ground_truth=frozenset({"response(a, b)"}),
        policy=policy,
        strength=2.0,
    )
    assert outcome.retired == 1
    assert outcome.false_retires == 1
    assert outcome.false_promotes == 0


def test_khong_co_luat_thu_thi_tu_choi():
    _train, calibration, ground_truth, policy = _benchmark()
    with pytest.raises(ValueError, match="không khám phá được luật"):
        calibrate_beta(
            split="calibration",
            train_traces=(),
            calibration_traces=calibration,
            ground_truth=ground_truth,
            policy=policy,
        )
    train, _calibration, _ground_truth, _policy = _benchmark()
    with pytest.raises(ValueError, match="phần hiệu chỉnh rỗng"):
        calibrate_beta(
            split="calibration",
            train_traces=train,
            calibration_traces=(),
            ground_truth=ground_truth,
            policy=policy,
        )
    with pytest.raises(ValueError, match="ít nhất một độ mạnh"):
        calibrate_beta(
            split="calibration",
            train_traces=train,
            calibration_traces=calibration,
            ground_truth=ground_truth,
            policy=policy,
            strengths=[],
        )


def test_ket_qua_xac_dinh():
    train, calibration, ground_truth, policy = _benchmark()
    first = calibrate_beta(
        split="calibration",
        train_traces=train,
        calibration_traces=calibration,
        ground_truth=ground_truth,
        policy=policy,
    )
    second = calibrate_beta(
        split="calibration",
        train_traces=train,
        calibration_traces=calibration,
        ground_truth=ground_truth,
        policy=policy,
    )
    assert first == second


def test_nguong_chinh_sach_mac_dinh():
    policy: Policy = default_rule_table().policy
    assert policy.confidence_threshold == 0.7
    assert policy.promote_probability == 0.95
    assert policy.retire_probability == 0.05
    assert policy.prior_strength_default == 2.0
    assert policy.min_matching_cases == 30
