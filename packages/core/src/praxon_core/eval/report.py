"""Báo cáo baseline chỉ-Declare và cách ly (plan con 8, task 8.5; spec: bốn chỉ số).

Báo cáo sinh bằng lệnh (`python -m praxon_core.eval.report`): bốn chỉ
số theo từng tenant kèm khoảng tin cậy 95% cho điều kiện chỉ-Declare
và điều kiện cách ly, trên bộ chuẩn bán tổng hợp và trên năm đô thị
BPIC 2015.

Hai điều kiện, một phép đo (giai đoạn 1): chỉ-Declare là khám phá
Declare trên trace của tenant, không mô hình ngôn ngữ; cách ly là mỗi
tenant tự học, không có `global`. Ở giai đoạn 1 chưa có kho `global`
nên hai điều kiện cho cùng số — báo cáo in cả hai cột với cùng giá trị
và ghi rõ trùng nhau là đúng, không phải lỗi. Khi plan 10 thêm kho
`global`, cách ly sẽ loại fact `global` còn các điều kiện khác không;
lúc đó hai cột mới khác nhau. So sánh các điều kiện bằng CHÊNH LỆCH
(spec, mục Ground truth: đáp án từ phần đo có nhiễu riêng nên số tuyệt
đối hơi bi quan, như nhau cho mọi điều kiện).

Khoảng tin cậy: bootstrap 95% trên các đơn vị quan sát của từng chỉ số
(bootstrap.py, task 8.3) — fact `active` với precision, tỉ lệ vi phạm,
negative transfer; khóa tham chiếu với recall. Cờ vi phạm tính một lần
trên tập đo cố định (`violated_flags`) rồi lấy mẫu lại các cờ, thay vì
tính lại chỉ số trên mỗi lần rút (khám phá lại mỗi lần rút thì một báo
cáo cần hàng nghìn lần khám phá). Số lần rút là tham số (lệnh lấy từ
`Settings.bootstrap_draws`), không hard-code; seed suy từ
(tenant, điều kiện, chỉ số) nên chạy lại ra đúng khoảng cũ.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from praxon_core.datasets.bpic2015 import BPIC2015_DATASETS, DEFAULT_CACHE_DIR
from praxon_core.datasets.split import (
    DEFAULT_CALIBRATION_FRACTION,
    DEFAULT_TRAIN_FRACTION,
    split_log,
)
from praxon_core.datasets.xes import iter_traces
from praxon_core.declare.index import Trace
from praxon_core.declare.miner import discover
from praxon_core.eval.bootstrap import bootstrap_confidence_interval
from praxon_core.eval.ground_truth import (
    GROUND_TRUTH_CONFIDENCE,
    GROUND_TRUTH_SUPPORT,
    GroundTruth,
    facts_from_rules,
    ground_truth_from_generator,
    ground_truth_from_test_traces,
)
from praxon_core.eval.metrics import (
    Fact,
    FactScope,
    compute_metrics,
    violated_flags,
)
from praxon_core.learning.candidate import FactStatus
from praxon_core.settings import Settings, load_settings
from praxon_core.synthetic.generator import (
    BASE_ORDER,
    GeneratorParams,
    generate,
    swap_adjacent,
)

DECLARE_ONLY_CONDITION = "Chỉ Declare"
"""Điều kiện baseline: khám phá Declare trên trace của tenant, không mô hình."""

ISOLATION_CONDITION = "Cách ly"
"""Điều kiện cận an toàn: mỗi tenant tự học, không có `global`."""

CONDITIONS: tuple[str, ...] = (DECLARE_ONLY_CONDITION, ISOLATION_CONDITION)
"""Hai điều kiện plan con 8 báo cáo (năm điều kiện còn lại là của plan 10)."""

SYNTHETIC_TENANT_COUNT = 5
"""Số tenant giả trong báo cáo (cùng cỡ phép thử ngày 3/10 trong spec)."""

SYNTHETIC_SEED = 42
"""Seed bộ sinh cho báo cáo (cùng seed nghiệm thu 5.3)."""

SYNTHETIC_N_CASES = 300
"""Số trace mỗi tenant giả (cùng cỡ mẫu nghiệm thu 5.3)."""


@dataclass(frozen=True)
class MetricCI:
    """Một chỉ số kèm khoảng tin cậy 95% (giá trị, cận dưới, cận trên)."""

    value: float
    lower: float
    upper: float


@dataclass(frozen=True)
class MetricsWithCI:
    """Bốn chỉ số, mỗi cái kèm khoảng tin cậy 95% — luôn báo cùng nhau."""

    precision: MetricCI
    recall: MetricCI
    violation_rate: MetricCI
    negative_transfer: MetricCI


@dataclass(frozen=True)
class TenantEvaluation:
    """Kết quả đo của một tenant (chưa gắn điều kiện — xem ghi chú module)."""

    tenant_id: str
    source: str
    n_train: int
    n_measure: int
    n_reference: int
    n_rules: int
    metrics: MetricsWithCI


@dataclass(frozen=True)
class TenantConditionRow:
    """Một hàng báo cáo: một tenant trong một điều kiện."""

    tenant_id: str
    condition: str
    source: str
    n_train: int
    n_measure: int
    n_reference: int
    n_rules: int
    metrics: MetricsWithCI


@dataclass(frozen=True)
class BaselineReport:
    """Báo cáo baseline: các hàng theo tenant và điều kiện, kèm ghi chú."""

    rows: tuple[TenantConditionRow, ...]
    note: str


def _ci_seed(seed: int, tenant_id: str, condition: str, metric: str) -> int:
    """Seed bootstrap suy từ (seed, tenant, điều kiện, chỉ số): ổn định qua máy."""
    digest = hashlib.sha256(
        f"baseline:{seed}:{tenant_id}:{condition}:{metric}".encode()
    ).digest()
    return int.from_bytes(digest[:8], "big")


def _mean(sample: Sequence[bool]) -> float:
    """Tỉ lệ True trong mẫu; mẫu rỗng thì 0 (bootstrap không rút mẫu rỗng)."""
    if not sample:
        return 0.0
    return sum(sample) / len(sample)


def _bootstrap_fraction(
    indicators: Sequence[bool], *, n_draws: int, seed: int
) -> tuple[float, float]:
    """Khoảng tin cậy cho một tỉ lệ: lấy mẫu lại các cờ True/False."""
    return bootstrap_confidence_interval(_mean, indicators, n_draws=n_draws, seed=seed)


def metrics_with_ci(
    facts: Sequence[Fact],
    reference: frozenset[str],
    measure_traces: Sequence[Trace],
    tenant_id: str,
    *,
    n_draws: int,
    seed: int,
    condition: str = DECLARE_ONLY_CONDITION,
) -> MetricsWithCI:
    """Bốn chỉ số kèm khoảng tin cậy 95% cho một tenant trong một điều kiện.

    `n_draws` lấy từ cấu hình (`Settings.bootstrap_draws`), không
    hard-code. Không có fact `active` thì bốn chỉ số và khoảng đều là 0;
    đáp án rỗng thì recall là 0.
    """
    metrics = compute_metrics(facts, reference, measure_traces, tenant_id)
    active = [fact for fact in facts if fact.status is FactStatus.ACTIVE]
    if not active:
        zero = MetricCI(0.0, 0.0, 0.0)
        return MetricsWithCI(zero, zero, zero, zero)
    active_keys = {fact.canonical_key for fact in active}
    precision_flags = [fact.canonical_key in reference for fact in active]
    recall_flags = [key in active_keys for key in sorted(reference)]
    violated = violated_flags(facts, measure_traces)
    external_flags = [
        flag and (fact.scope is FactScope.GLOBAL or fact.tenant_id != tenant_id)
        for flag, fact in zip(violated, active, strict=True)
    ]
    precision_lo, precision_hi = _bootstrap_fraction(
        precision_flags,
        n_draws=n_draws,
        seed=_ci_seed(seed, tenant_id, condition, "precision"),
    )
    if reference:
        recall_lo, recall_hi = _bootstrap_fraction(
            recall_flags,
            n_draws=n_draws,
            seed=_ci_seed(seed, tenant_id, condition, "recall"),
        )
    else:
        recall_lo, recall_hi = 0.0, 0.0
    violation_lo, violation_hi = _bootstrap_fraction(
        violated,
        n_draws=n_draws,
        seed=_ci_seed(seed, tenant_id, condition, "violation_rate"),
    )
    transfer_lo, transfer_hi = _bootstrap_fraction(
        external_flags,
        n_draws=n_draws,
        seed=_ci_seed(seed, tenant_id, condition, "negative_transfer"),
    )
    return MetricsWithCI(
        precision=MetricCI(metrics.precision, precision_lo, precision_hi),
        recall=MetricCI(metrics.recall, recall_lo, recall_hi),
        violation_rate=MetricCI(metrics.violation_rate, violation_lo, violation_hi),
        negative_transfer=MetricCI(metrics.negative_transfer, transfer_lo, transfer_hi),
    )


def evaluate_tenant(
    *,
    tenant_id: str,
    train_traces: Sequence[Trace],
    measure_traces: Sequence[Trace],
    ground_truth: GroundTruth,
    n_draws: int,
    seed: int,
) -> TenantEvaluation:
    """Đo một tenant: khám phá trên phần học, chấm bằng đáp án (8.1).

    Khám phá dùng hai ngưỡng cố định của ground truth (8.1) — cùng
    ngưỡng với đáp án. Hàm không nhận điều kiện: hai điều kiện của
    plan 8 đo cùng một cách ở giai đoạn 1 (xem ghi chú module); báo
    cáo gắn nhãn điều kiện khi trình bày.
    """
    rules = discover(
        train_traces,
        support=GROUND_TRUTH_SUPPORT,
        confidence=GROUND_TRUTH_CONFIDENCE,
    )
    facts = facts_from_rules(rules, tenant_id)
    return TenantEvaluation(
        tenant_id=tenant_id,
        source=ground_truth.source,
        n_train=len(train_traces),
        n_measure=len(measure_traces),
        n_reference=len(ground_truth.reference),
        n_rules=len(facts),
        metrics=metrics_with_ci(
            facts,
            ground_truth.reference,
            measure_traces,
            tenant_id,
            n_draws=n_draws,
            seed=seed,
        ),
    )


def build_baseline_report(
    evaluations: Sequence[TenantEvaluation],
) -> BaselineReport:
    """Ghép báo cáo: mỗi phép đo thành hai hàng (hai điều kiện).

    Hai hàng của một tenant có cùng số ở giai đoạn 1 (xem ghi chú
    module) — ghi chú của báo cáo nói rõ điều đó để người đọc không
    tưởng là lỗi.
    """
    rows: list[TenantConditionRow] = []
    for evaluation in evaluations:
        for condition in CONDITIONS:
            rows.append(
                TenantConditionRow(
                    tenant_id=evaluation.tenant_id,
                    condition=condition,
                    source=evaluation.source,
                    n_train=evaluation.n_train,
                    n_measure=evaluation.n_measure,
                    n_reference=evaluation.n_reference,
                    n_rules=evaluation.n_rules,
                    metrics=evaluation.metrics,
                )
            )
    note = (
        "Ở giai đoạn 1, hai điều kiện cho cùng số: cùng khám phá Declare "
        "trên trace của tenant, chưa có kho global để cách ly loại ra. "
        "Hai cột trùng nhau là đúng, không phải lỗi; khi plan 10 thêm kho "
        "global, cách ly sẽ loại fact global còn chỉ-Declare không, lúc đó "
        "hai cột mới khác nhau. So sánh các điều kiện bằng chênh lệch: đáp "
        "án BPIC lấy từ phần đo có nhiễu riêng nên số tuyệt đối hơi bi quan, "
        "như nhau cho mọi điều kiện (spec, mục Ground truth)."
    )
    return BaselineReport(rows=tuple(rows), note=note)


def _format_metric(metric: MetricCI) -> str:
    """Một chỉ số thành `giá trị [cận dưới, cận trên]`."""
    return f"{metric.value:.3f} [{metric.lower:.3f}, {metric.upper:.3f}]"


def format_baseline_report(report: BaselineReport) -> str:
    """Báo cáo baseline thành văn bản (lệnh 8.5 in văn bản này)."""
    lines = [
        "Báo cáo baseline chỉ-Declare và cách ly (task 8.5)",
        f"Ngưỡng khám phá và đáp án: support={GROUND_TRUTH_SUPPORT:g}, "
        f"confidence={GROUND_TRUTH_CONFIDENCE:g} (cố định, dùng chung mọi điều kiện)",
        "",
        report.note,
        "",
    ]
    for row in report.rows:
        metrics = row.metrics
        lines.append(
            f"Tenant {row.tenant_id} — {row.condition} "
            f"(đáp án: {row.source}; học {row.n_train} trace, "
            f"đo {row.n_measure} trace; đáp án {row.n_reference} luật, "
            f"khám phá {row.n_rules} luật)"
        )
        lines.append(f"  precision:        {_format_metric(metrics.precision)}")
        lines.append(f"  recall:           {_format_metric(metrics.recall)}")
        lines.append(f"  tỉ lệ vi phạm:    {_format_metric(metrics.violation_rate)}")
        lines.append(f"  negative transfer: {_format_metric(metrics.negative_transfer)}")
    return "\n".join(lines)


def split_generated_traces(
    traces: Sequence[Trace],
) -> tuple[tuple[Trace, ...], tuple[Trace, ...]]:
    """Chia log bộ sinh 60/20/20 theo thứ tự đến: học 60%, đo 20% cuối.

    Cùng tỉ lệ chia của BPIC (datasets/split.py): 60% học, 20% hiệu
    chỉnh (không dùng ở báo cáo này), 20% đo. Thứ tự đến là thứ tự
    sinh — trace sinh sau là case đến sau.
    """
    total = len(traces)
    train_end = int(total * DEFAULT_TRAIN_FRACTION)
    test_start = int(total * (DEFAULT_TRAIN_FRACTION + DEFAULT_CALIBRATION_FRACTION))
    return tuple(traces[:train_end]), tuple(traces[test_start:])


def traces_for_case_ids(path: Path, case_ids: frozenset[str]) -> tuple[Trace, ...]:
    """Trace của một phần chia BPIC: lọc theo case id, đổi sang trace Declare."""
    traces: list[Trace] = []
    for trace in iter_traces(path):
        if trace.case_id in case_ids:
            traces.append(Trace(tuple(event.activity for event in trace.events)))
    return tuple(traces)


def _synthetic_evaluations(*, seed: int, n_cases: int, n_draws: int) -> list[TenantEvaluation]:
    """Đo các tenant giả: mỗi tenant một thứ tự riêng (đáp án khác nhau)."""
    evaluations: list[TenantEvaluation] = []
    for index in range(SYNTHETIC_TENANT_COUNT):
        tenant_id = f"synthetic-{index + 1}"
        order = swap_adjacent(BASE_ORDER, index)
        log = generate(
            tenant_id=tenant_id,
            params=GeneratorParams(seed=seed, n_cases=n_cases, order=order),
        )
        train, measure = split_generated_traces(log.traces)
        evaluations.append(
            evaluate_tenant(
                tenant_id=tenant_id,
                train_traces=train,
                measure_traces=measure,
                ground_truth=ground_truth_from_generator(log),
                n_draws=n_draws,
                seed=seed,
            )
        )
    return evaluations


def _bpic_evaluations(
    *, cache_dir: Path, dataset: str | None, n_draws: int, seed: int
) -> tuple[list[TenantEvaluation], int]:
    """Đo các đô thị BPIC 2015: học trên phần học, đáp án từ phần đo.

    Trả (danh sách phép đo, mã thoát): 1 khi thiếu tệp log.
    """
    evaluations: list[TenantEvaluation] = []
    datasets = [item for item in BPIC2015_DATASETS if dataset is None or item.slug == dataset]
    for item in datasets:
        path = cache_dir / item.xes_filename
        if not path.is_file():
            print(f"thiếu tệp: {path}", file=sys.stderr)
            return evaluations, 1
        split = split_log(path, item.municipality)
        train = traces_for_case_ids(path, frozenset(split.train))
        measure = traces_for_case_ids(path, frozenset(split.test))
        evaluations.append(
            evaluate_tenant(
                tenant_id=item.slug,
                train_traces=train,
                measure_traces=measure,
                ground_truth=ground_truth_from_test_traces(measure, tenant_id=item.slug),
                n_draws=n_draws,
                seed=seed,
            )
        )
    return evaluations, 0


def main(argv: list[str] | None = None) -> int:
    """Lệnh báo cáo baseline: `python -m praxon_core.eval.report`.

    Mã thoát: 0 = xong; 1 = thiếu tệp log BPIC; 2 = tham số không hợp lệ.
    """
    default_draws = Settings.model_fields["bootstrap_draws"].default
    parser = argparse.ArgumentParser(
        prog="praxon_core.eval.report",
        description="Báo cáo baseline chỉ-Declare và cách ly (task 8.5).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="thư mục cache chứa 5 tệp BPIC15_N.xes",
    )
    parser.add_argument(
        "--dataset",
        choices=[item.slug for item in BPIC2015_DATASETS],
        help="chỉ báo cáo một đô thị (mặc định: cả năm)",
    )
    parser.add_argument(
        "--synthetic-only",
        action="store_true",
        help="chỉ báo cáo bộ chuẩn bán tổng hợp, bỏ qua BPIC 2015",
    )
    parser.add_argument("--seed", type=int, default=SYNTHETIC_SEED, help="seed bộ sinh")
    parser.add_argument(
        "--n-cases",
        type=int,
        default=SYNTHETIC_N_CASES,
        help="số trace mỗi tenant giả",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="tệp TOML cấu hình (lấy bootstrap_draws khi không có --draws)",
    )
    parser.add_argument(
        "--draws",
        type=int,
        default=None,
        help="số lần rút bootstrap (mặc định: bootstrap_draws trong cấu hình)",
    )
    args = parser.parse_args(argv)
    n_draws = args.draws
    if n_draws is None:
        if args.config is not None:
            try:
                n_draws = load_settings(args.config).bootstrap_draws
            except (OSError, ValueError) as error:
                print(f"không nạp được cấu hình: {error}", file=sys.stderr)
                return 2
        else:
            n_draws = default_draws
    if n_draws is None or n_draws < 1:
        print(f"số lần rút phải ít nhất 1, nhận {n_draws}", file=sys.stderr)
        return 2
    if args.n_cases < 1:
        print(f"số trace phải ít nhất 1, nhận {args.n_cases}", file=sys.stderr)
        return 2
    evaluations = _synthetic_evaluations(seed=args.seed, n_cases=args.n_cases, n_draws=n_draws)
    if not args.synthetic_only:
        bpic_evaluations, code = _bpic_evaluations(
            cache_dir=args.cache_dir,
            dataset=args.dataset,
            n_draws=n_draws,
            seed=args.seed,
        )
        if code != 0:
            return code
        evaluations.extend(bpic_evaluations)
    print(format_baseline_report(build_baseline_report(evaluations)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
