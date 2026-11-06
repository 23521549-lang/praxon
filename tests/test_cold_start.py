"""Đường cong khởi động lạnh (task 8.4, plan con 8).

Cổng ra: lệnh in đường cong; điểm 0 có nhãn ghi rõ đo trên luật `trial`
chế độ giám sát.

Trace viết tay 40 x (a, b, c, d): mọi luật thứ tự đều đúng trên mọi
trace nên ở mọi điểm n > 0 khám phá ra đúng 12 luật của đáp án
(precision = recall = 1,0, vi phạm = 0) — giá trị tính được bằng tay,
không phụ thuộc bộ sinh. Test bộ sinh kiểm đường cong trên dữ liệu thật
của dự án (seed 42, 300 trace như nghiệm thu 5.3).
"""

import pytest

from praxon_core.declare.index import Trace
from praxon_core.declare.miner import discover
from praxon_core.eval.cold_start import (
    ACTIVE_MODE,
    COLD_START_SIZES,
    TRIAL_SUPERVISED_MODE,
    cold_start_curve,
    format_cold_start_curve,
    main,
)
from praxon_core.eval.ground_truth import (
    GROUND_TRUTH_CONFIDENCE,
    GROUND_TRUTH_SUPPORT,
    facts_from_rules,
    ground_truth_from_generator,
    ground_truth_from_test_traces,
)
from praxon_core.eval.metrics import Fact, FactScope, compute_metrics
from praxon_core.learning.candidate import FactStatus
from praxon_core.synthetic.generator import GeneratorParams, generate

TENANT = "acme"


def _traces() -> tuple[Trace, ...]:
    """40 trace viết tay: a, b, c, d theo thứ tự, mọi luật đều đúng."""
    return tuple(Trace(("a", "b", "c", "d")) for _ in range(40))


def _reference() -> frozenset[str]:
    return ground_truth_from_test_traces(_traces(), tenant_id=TENANT).reference


def test_duong_cong_co_nam_diem_dung_kich_co_va_nhan():
    points = cold_start_curve(
        train_traces=_traces(),
        measure_traces=_traces(),
        ground_truth=ground_truth_from_test_traces(_traces(), tenant_id=TENANT),
        tenant_id=TENANT,
    )
    assert [point.n_traces for point in points] == list(COLD_START_SIZES)
    assert points[0].mode == TRIAL_SUPERVISED_MODE
    assert all(point.mode == ACTIVE_MODE for point in points[1:])


def test_diem_0_khong_co_luat_trial_thi_bang_0_va_ghi_nhan():
    points = cold_start_curve(
        train_traces=_traces(),
        measure_traces=_traces(),
        ground_truth=ground_truth_from_test_traces(_traces(), tenant_id=TENANT),
        tenant_id=TENANT,
    )
    point0 = points[0]
    assert point0.n_traces == 0
    assert point0.n_rules == 0
    assert point0.precision == 0.0
    assert point0.recall == 0.0
    assert point0.violation_rate == 0.0
    assert point0.negative_transfer == 0.0
    assert point0.mode == TRIAL_SUPERVISED_MODE


def test_diem_0_do_dung_luat_trial_khi_co_luat_trial():
    trial = [
        Fact(
            "response(a, b)",
            "response",
            "a",
            "b",
            FactStatus.TRIAL,
            FactScope.TENANT,
            TENANT,
        ),
        Fact(
            "response(x, y)",
            "response",
            "x",
            "y",
            FactStatus.TRIAL,
            FactScope.TENANT,
            TENANT,
        ),
    ]
    points = cold_start_curve(
        train_traces=_traces(),
        measure_traces=_traces(),
        ground_truth=ground_truth_from_test_traces(_traces(), tenant_id=TENANT),
        tenant_id=TENANT,
        trial_facts=trial,
    )
    point0 = points[0]
    # Một trong hai luật trial có trong đáp án (12 luật) → precision 1/2,
    # recall 1/12; cả hai đều không bị trace đo vi phạm.
    assert point0.n_rules == 2
    assert point0.precision == 0.5
    assert point0.recall == 1 / 12
    assert point0.violation_rate == 0.0
    assert point0.negative_transfer == 0.0
    assert point0.mode == TRIAL_SUPERVISED_MODE
    # Chuyển tạm thành active chỉ để tính chỉ số: luật gốc vẫn trial.
    assert all(fact.status is FactStatus.TRIAL for fact in trial)


def test_cac_diem_n_lon_hon_0_kham_pha_dung_12_luat():
    points = cold_start_curve(
        train_traces=_traces(),
        measure_traces=_traces(),
        ground_truth=ground_truth_from_test_traces(_traces(), tenant_id=TENANT),
        tenant_id=TENANT,
    )
    for point in points[1:]:
        assert point.n_rules == 12
        assert point.precision == 1.0
        assert point.recall == 1.0
        assert point.violation_rate == 0.0
        assert point.negative_transfer == 0.0


def test_duong_cong_tren_bo_sinh_khop_tinh_truc_tiep():
    log = generate(tenant_id=TENANT, params=GeneratorParams(seed=42, n_cases=300))
    truth = ground_truth_from_generator(log)
    points = cold_start_curve(
        train_traces=log.traces,
        measure_traces=log.traces,
        ground_truth=truth,
        tenant_id=TENANT,
    )
    assert len(points) == 5
    assert points[0].mode == TRIAL_SUPERVISED_MODE
    assert points[0].precision == 0.0
    # Điểm 40 trace bằng đúng khám phá trên 40 trace đầu rồi tính chỉ số.
    rules = discover(
        log.traces[:40],
        support=GROUND_TRUTH_SUPPORT,
        confidence=GROUND_TRUTH_CONFIDENCE,
    )
    expected = compute_metrics(
        facts_from_rules(rules, TENANT), truth.reference, log.traces, TENANT
    )
    point40 = points[4]
    assert point40.n_traces == 40
    assert point40.n_rules == len(rules)
    assert point40.precision == expected.precision
    assert point40.recall == expected.recall
    assert point40.violation_rate == expected.violation_rate
    assert point40.negative_transfer == expected.negative_transfer


def test_so_trace_am_bi_tu_choi():
    with pytest.raises(ValueError):
        cold_start_curve(
            train_traces=_traces(),
            measure_traces=_traces(),
            ground_truth=ground_truth_from_test_traces(_traces(), tenant_id=TENANT),
            tenant_id=TENANT,
            sizes=[-1],
        )


def test_dinh_dang_duong_cong_ghi_ro_diem_0_la_trial_giam_sat():
    points = cold_start_curve(
        train_traces=_traces(),
        measure_traces=_traces(),
        ground_truth=ground_truth_from_test_traces(_traces(), tenant_id=TENANT),
        tenant_id=TENANT,
    )
    text = format_cold_start_curve(points, tenant_id=TENANT)
    assert TRIAL_SUPERVISED_MODE in text
    assert "40" in text
    first_data_line = text.splitlines()[2]
    assert TRIAL_SUPERVISED_MODE in first_data_line


def test_lenh_in_duong_cong(capsys):
    assert main(["--tenant", "acme", "--seed", "42", "--n-cases", "300"]) == 0
    text = capsys.readouterr().out
    assert TRIAL_SUPERVISED_MODE in text
    assert "40" in text


def test_lenh_tu_choi_so_trace_it_hon_diem_lon_nhat(capsys):
    assert main(["--n-cases", "10"]) == 2
    assert "ít nhất 40" in capsys.readouterr().err
