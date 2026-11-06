"""Báo cáo baseline (task 8.5, plan con 8).

Cổng ra: báo cáo sinh bằng lệnh, bốn chỉ số theo tenant kèm khoảng tin cậy.

Test dùng dữ liệu nhỏ, tự viết (không chạy lệnh BPIC đầy đủ ở đây —
lệnh BPIC chạy thật một lần khi kiểm mảnh, xem báo cáo của task).
Khoảng tin cậy bootstrap dùng ít lần rút (50) để test nhanh; tính
xác định của seed kiểm bằng gọi hai lần.
"""

from pathlib import Path

from praxon_core.declare.index import Trace
from praxon_core.eval.ground_truth import ground_truth_from_generator
from praxon_core.eval.metrics import Fact, FactScope, compute_metrics
from praxon_core.eval.report import (
    DECLARE_ONLY_CONDITION,
    ISOLATION_CONDITION,
    build_baseline_report,
    evaluate_tenant,
    format_baseline_report,
    main,
    metrics_with_ci,
    split_generated_traces,
    traces_for_case_ids,
)
from praxon_core.learning.candidate import FactStatus
from praxon_core.synthetic.generator import GeneratorParams, generate

TENANT = "acme"
FIXTURE = Path(__file__).parent / "fixtures" / "tiny.xes"


def _bo_bon_fact() -> list[Fact]:
    """Bốn fact active (mượn từ test_metrics): 3 trong đáp án, 1 học sai."""
    return [
        Fact(
            "response(a, b)",
            "response",
            "a",
            "b",
            FactStatus.ACTIVE,
            FactScope.TENANT,
            TENANT,
        ),
        Fact(
            "precedence(c, d)",
            "precedence",
            "c",
            "d",
            FactStatus.ACTIVE,
            FactScope.TENANT,
            TENANT,
        ),
        Fact(
            "response(e, f)",
            "response",
            "e",
            "f",
            FactStatus.ACTIVE,
            FactScope.GLOBAL,
            "global",
        ),
        Fact(
            "response(x, y)",
            "response",
            "x",
            "y",
            FactStatus.ACTIVE,
            FactScope.TENANT,
            TENANT,
        ),
    ]


def _muoi_trace() -> list[Trace]:
    return [
        Trace(events=("f", "e")),
        Trace(events=("e",)),
        Trace(events=("d", "c")),
        Trace(events=("a", "b", "c", "d", "e", "f", "x", "y")),
        Trace(events=("a", "b", "c", "d", "e", "f", "x", "y")),
        Trace(events=("a", "b", "c", "d", "e", "f", "x", "y")),
        Trace(events=("a", "b", "c", "d", "e", "f", "x", "y")),
        Trace(events=("a", "b", "c", "d", "e", "f", "x", "y")),
        Trace(events=("a", "b", "c", "d", "e", "f", "x", "y")),
        Trace(events=("a", "b", "c", "d", "e", "f", "x", "y")),
    ]


def _dap_an() -> frozenset[str]:
    return frozenset(
        {"response(a, b)", "precedence(c, d)", "response(e, f)", "precedence(g, h)"}
    )


def test_metrics_with_ci_gia_tri_khop_bon_chi_so_va_khoang_chua_gia_tri():
    facts = _bo_bon_fact()
    result = metrics_with_ci(facts, _dap_an(), _muoi_trace(), TENANT, n_draws=50, seed=7)
    expected = compute_metrics(facts, _dap_an(), _muoi_trace(), TENANT)
    assert result.precision.value == expected.precision == 0.75
    assert result.recall.value == expected.recall == 0.75
    assert result.violation_rate.value == expected.violation_rate == 0.25
    assert result.negative_transfer.value == expected.negative_transfer == 0.25
    for metric in (
        result.precision,
        result.recall,
        result.violation_rate,
        result.negative_transfer,
    ):
        assert 0.0 <= metric.lower <= metric.value <= metric.upper <= 1.0


def test_metrics_with_ci_xac_dinh_theo_seed():
    facts = _bo_bon_fact()
    first = metrics_with_ci(facts, _dap_an(), _muoi_trace(), TENANT, n_draws=50, seed=7)
    second = metrics_with_ci(facts, _dap_an(), _muoi_trace(), TENANT, n_draws=50, seed=7)
    assert first == second


def test_metrics_with_ci_khong_co_fact_active_thi_bang_khong():
    result = metrics_with_ci([], _dap_an(), _muoi_trace(), TENANT, n_draws=50, seed=7)
    for metric in (
        result.precision,
        result.recall,
        result.violation_rate,
        result.negative_transfer,
    ):
        assert (metric.value, metric.lower, metric.upper) == (0.0, 0.0, 0.0)


def test_evaluate_tenant_tren_bo_sinh():
    log = generate(tenant_id=TENANT, params=GeneratorParams(seed=42, n_cases=300))
    train, measure = split_generated_traces(log.traces)
    assert len(train) == 180
    assert len(measure) == 60
    result = evaluate_tenant(
        tenant_id=TENANT,
        train_traces=train,
        measure_traces=measure,
        ground_truth=ground_truth_from_generator(log),
        n_draws=50,
        seed=42,
    )
    assert result.n_reference == 56
    assert result.n_rules == 20
    assert result.metrics.precision.value == 1.0
    assert result.metrics.recall.value == 20 / 56


def test_split_generated_traces_chia_60_20_20_theo_thu_tu_den():
    traces = tuple(Trace((f"a{i}",)) for i in range(100))
    train, measure = split_generated_traces(traces)
    assert len(train) == 60
    assert len(measure) == 20
    assert train[0].events == ("a0",)
    assert measure[0].events == ("a80",)


def test_traces_for_case_ids_loc_dung_case():
    traces = traces_for_case_ids(FIXTURE, frozenset({"case-2"}))
    assert traces == (Trace(("B", "C")),)
    assert traces_for_case_ids(FIXTURE, frozenset({"khong-co"})) == ()


def test_hai_dieu_kien_cung_so_va_ghi_chu_noi_ro():
    log = generate(tenant_id=TENANT, params=GeneratorParams(seed=42, n_cases=300))
    train, measure = split_generated_traces(log.traces)
    evaluation = evaluate_tenant(
        tenant_id=TENANT,
        train_traces=train,
        measure_traces=measure,
        ground_truth=ground_truth_from_generator(log),
        n_draws=50,
        seed=42,
    )
    report = build_baseline_report([evaluation])
    assert len(report.rows) == 2
    assert [row.condition for row in report.rows] == [
        DECLARE_ONLY_CONDITION,
        ISOLATION_CONDITION,
    ]
    assert report.rows[0].metrics == report.rows[1].metrics
    assert "giai đoạn 1" in report.note
    assert "trùng nhau là đúng" in report.note


def test_format_baseline_report_in_du_bon_chi_so_va_khoang():
    log = generate(tenant_id=TENANT, params=GeneratorParams(seed=42, n_cases=300))
    train, measure = split_generated_traces(log.traces)
    evaluation = evaluate_tenant(
        tenant_id=TENANT,
        train_traces=train,
        measure_traces=measure,
        ground_truth=ground_truth_from_generator(log),
        n_draws=50,
        seed=42,
    )
    text = format_baseline_report(build_baseline_report([evaluation]))
    assert TENANT in text
    assert DECLARE_ONLY_CONDITION in text
    assert ISOLATION_CONDITION in text
    for label in ("precision", "recall", "tỉ lệ vi phạm", "negative transfer"):
        assert label in text
    assert "[" in text and "]" in text


def test_lenh_bao_cao_chi_bo_chuan(capsys):
    assert main(["--synthetic-only", "--draws", "50"]) == 0
    text = capsys.readouterr().out
    assert "synthetic-1" in text
    assert "synthetic-5" in text
    assert DECLARE_ONLY_CONDITION in text
    assert ISOLATION_CONDITION in text
    assert "precision" in text


def test_lenh_tu_choi_draws_khong_hop_le(capsys):
    assert main(["--synthetic-only", "--draws", "0"]) == 2
    assert "ít nhất 1" in capsys.readouterr().err


def test_lenh_thieu_tep_bpic_thi_dung_va_bao_loi(capsys):
    assert main(["--cache-dir", "/tmp/khong-co-thu-muc-nay", "--draws", "10"]) == 1
    assert "thiếu tệp" in capsys.readouterr().err
