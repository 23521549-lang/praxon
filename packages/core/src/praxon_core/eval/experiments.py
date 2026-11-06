"""Bảy điều kiện thí nghiệm chạy bằng một lệnh (plan con 10, task 10.2).

Lệnh (`python -m praxon_core.eval.experiments`): chạy cả bảy điều kiện trên
bộ chuẩn bán tổng hợp, in bốn chỉ số (precision, recall, tỉ lệ vi phạm,
negative transfer) kèm khoảng tin cậy 95% theo từng tenant cho từng điều
kiện. Dùng đáp án (8.1) + chỉ số (8.2) + khoảng tin cậy (8.3) + bộ điều
phối (10.1) — ở đây là đo trong bộ nhớ như báo cáo 8.5, không ghi DB.

Bảy điều kiện, mỗi tenant một tập fact (tất cả đều `active`):

- Chỉ Declare: luật khám phá trên trace của chính tenant.
- Cách ly: mỗi tenant tự học, không có `global` — ở giai đoạn 1 chưa có
  kho `global` nên giống hệt Chỉ Declare, ghi rõ trùng nhau là đúng.
- Gộp chung: một kho chung cho mọi tenant — luật khám phá trên trace gộp
  của cả năm tenant, áp cho từng tenant.
- Phân tầng bỏ phiếu: luật lên `global` khi đủ `VOTE_K` tenant cùng học
  được; tenant dùng luật của mình + luật `global`.
- Phân tầng đồng thuận: `global` chỉ chứa luật mà không tenant nào vi
  phạm (trên phần HỌC của tenant đó); tenant dùng luật của mình + `global`.
- Phân tầng phủ quyết: `global` của số đông (như bỏ phiếu), mỗi tenant
  tự loại luật mà dữ liệu HỌC của nó vi phạm.
- Tài liệu cộng dữ liệu: ứng viên tốt hơn trong hai cái trên (đồng thuận
  hay phủ quyết — chọn theo F1 trung bình qua các tenant) cộng luật LLM
  trích từ luật Wabo vào `global`, vào `trial` của mỗi tenant từ ngày
  đầu. Ở giai đoạn 1, Reflector (6.2) chưa làm nên tập luật tài liệu
  RỖNG — điều kiện này đo đúng ứng viên tốt hơn đó, không tự bịa luật;
  báo cáo ghi rõ điều này.

Quyết định nâng (bỏ phiếu / đồng thuận / phủ quyết) chỉ dùng phần HỌC:
phần ĐO dành riêng cho đánh giá, không rò rỉ vào cách xây điều kiện.
Ngưỡng vi phạm là `VIOLATION_THRESHOLD` của chỉ số (quá 10% trace vi
phạm thì tính là vi phạm). Ngưỡng khám phá và đáp án là hai hằng cố định
của ground truth (8.1), dùng chung mọi điều kiện.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from praxon_core.declare.index import Trace
from praxon_core.declare.miner import Rule, discover
from praxon_core.eval.ground_truth import (
    GROUND_TRUTH_CONFIDENCE,
    GROUND_TRUTH_SUPPORT,
    GroundTruth,
    facts_from_rules,
    ground_truth_from_generator,
)
from praxon_core.eval.metrics import (
    VIOLATION_THRESHOLD,
    Fact,
    FactScope,
    f1_score,
    violated_flags,
)
from praxon_core.eval.report import (
    SYNTHETIC_N_CASES,
    SYNTHETIC_SEED,
    SYNTHETIC_TENANT_COUNT,
    BaselineReport,
    TenantConditionRow,
    metrics_with_ci,
    split_generated_traces,
)
from praxon_core.learning.candidate import FactStatus
from praxon_core.settings import Settings, load_settings
from praxon_core.synthetic.generator import (
    BASE_ORDER,
    GeneratorParams,
    generate,
    swap_adjacent,
)

DECLARE_ONLY = "Chỉ Declare"
"""Điều kiện 1: khám phá Declare trên trace của tenant, không mô hình."""

ISOLATION = "Cách ly"
"""Điều kiện 2: mỗi tenant tự học, không có `global`."""

POOLED = "Gộp chung"
"""Điều kiện 3: một kho chung cho mọi tenant."""

VOTING = "Phân tầng bỏ phiếu"
"""Điều kiện 4: luật lên `global` khi đủ `VOTE_K` tenant cùng học được."""

CONSENSUS = "Phân tầng đồng thuận"
"""Điều kiện 5: `global` chỉ chứa luật không tenant nào vi phạm."""

VETO = "Phân tầng phủ quyết"
"""Điều kiện 6: `global` của số đông, mỗi tenant tự loại luật nó vi phạm."""

DOCUMENT = "Tài liệu cộng dữ liệu"
"""Điều kiện 7: ứng viên tốt hơn (5 hay 6) cộng luật tài liệu."""

CONDITIONS: tuple[str, ...] = (
    DECLARE_ONLY,
    ISOLATION,
    POOLED,
    VOTING,
    CONSENSUS,
    VETO,
    DOCUMENT,
)
"""Bảy điều kiện thí nghiệm, theo đúng thứ tự trong spec (dòng 154-168)."""

VOTE_K = 3
"""Số tenant đồng ý để một luật lên `global` ở điều kiện bỏ phiếu.

Đa số của 5 tenant giả trong bộ chuẩn (spec chỉ nói "đủ k tenant" mà
không cho số; 3/5 là đa số nhỏ nhất). Đổi cỡ bộ chuẩn thì xem lại hằng này.
"""

GLOBAL_TENANT_ID = "global"
"""tenant_id của fact `global` (quy ước V1: fact global mang tenant_id 'global')."""

DOCUMENT_RULES_EMPTY_NOTE = (
    "Tập luật tài liệu RỖNG ở giai đoạn 1: chưa có Reflector (task 6.2) nên "
    "không có luật nào trích từ văn bản; điều kiện 'Tài liệu cộng dữ liệu' "
    "đo đúng ứng viên tốt hơn trong hai điều kiện phân tầng (đồng thuận hay "
    "phủ quyết), chưa cộng thêm luật tài liệu nào."
)
"""Ghi chú khi điều kiện 7 chạy với tập luật tài liệu rỗng."""


@dataclass(frozen=True)
class TenantData:
    """Dữ liệu một tenant giả: phần học, phần đo, đáp án, luật tự học."""

    tenant_id: str
    train_traces: tuple[Trace, ...]
    measure_traces: tuple[Trace, ...]
    ground_truth: GroundTruth
    own_rules: frozenset[Rule]


def _tenant_data(*, seed: int, n_cases: int) -> list[TenantData]:
    """Sinh năm tenant giả: mỗi tenant một thứ tự riêng (đáp án khác nhau)."""
    tenants: list[TenantData] = []
    for index in range(SYNTHETIC_TENANT_COUNT):
        tenant_id = f"synthetic-{index + 1}"
        order = swap_adjacent(BASE_ORDER, index)
        log = generate(
            tenant_id=tenant_id,
            params=GeneratorParams(seed=seed, n_cases=n_cases, order=order),
        )
        train, measure = split_generated_traces(log.traces)
        tenants.append(
            TenantData(
                tenant_id=tenant_id,
                train_traces=train,
                measure_traces=measure,
                ground_truth=ground_truth_from_generator(log),
                own_rules=discover(
                    train,
                    support=GROUND_TRUTH_SUPPORT,
                    confidence=GROUND_TRUTH_CONFIDENCE,
                ),
            )
        )
    return tenants


def _rule_by_key(rules: Sequence[frozenset[Rule]]) -> dict[str, Rule]:
    """Gộp các tập luật thành dict khóa canonical → một luật mẫu."""
    by_key: dict[str, Rule] = {}
    for rule_set in rules:
        for rule in rule_set:
            by_key.setdefault(rule.canonical_key, rule)
    return by_key


def _global_facts(rules: frozenset[Rule] | Sequence[Rule]) -> list[Fact]:
    """Luật thành fact `global` (scope global, tenant_id 'global')."""
    return facts_from_rules(rules, GLOBAL_TENANT_ID, scope=FactScope.GLOBAL)


def condition_fact_sets(
    tenants: Sequence[TenantData],
) -> dict[str, dict[str, tuple[Fact, ...]]]:
    """Tập fact của từng tenant trong từng điều kiện (trừ điều kiện 7).

    Trả dict điều kiện → dict tenant → fact. Điều kiện 7 không có ở đây:
    nó cần số đo của điều kiện 5 và 6 để chọn ứng viên tốt hơn, cộng
    luật tài liệu (xem `run_experiments`).
    """
    by_key = _rule_by_key([tenant.own_rules for tenant in tenants])
    own_facts = {
        tenant.tenant_id: tuple(facts_from_rules(tenant.own_rules, tenant.tenant_id))
        for tenant in tenants
    }
    pooled_rules = discover(
        tuple(trace for tenant in tenants for trace in tenant.train_traces),
        support=GROUND_TRUTH_SUPPORT,
        confidence=GROUND_TRUTH_CONFIDENCE,
    )
    pooled_facts = tuple(_global_facts(pooled_rules))

    counts: dict[str, int] = {}
    for tenant in tenants:
        for rule in tenant.own_rules:
            counts[rule.canonical_key] = counts.get(rule.canonical_key, 0) + 1
    vote_rules = [by_key[key] for key, count in counts.items() if count >= VOTE_K]
    vote_facts = tuple(_global_facts(vote_rules))

    union_facts = tuple(_global_facts([by_key[key] for key in sorted(by_key)]))
    violated_by_tenant: dict[str, tuple[bool, ...]] = {
        tenant.tenant_id: tuple(violated_flags(union_facts, tenant.train_traces))
        for tenant in tenants
    }
    consensus_rules = [
        by_key[fact.canonical_key]
        for index, fact in enumerate(union_facts)
        if not any(violated_by_tenant[tenant.tenant_id][index] for tenant in tenants)
    ]
    consensus_facts = tuple(_global_facts(consensus_rules))

    veto_facts: dict[str, tuple[Fact, ...]] = {}
    for tenant in tenants:
        flags = violated_flags(vote_facts, tenant.train_traces)
        veto_facts[tenant.tenant_id] = tuple(
            fact for fact, violated in zip(vote_facts, flags, strict=True) if not violated
        )

    return {
        DECLARE_ONLY: {tenant.tenant_id: own_facts[tenant.tenant_id] for tenant in tenants},
        ISOLATION: {tenant.tenant_id: own_facts[tenant.tenant_id] for tenant in tenants},
        POOLED: {tenant.tenant_id: pooled_facts for tenant in tenants},
        VOTING: {
            tenant.tenant_id: own_facts[tenant.tenant_id] + vote_facts for tenant in tenants
        },
        CONSENSUS: {
            tenant.tenant_id: own_facts[tenant.tenant_id] + consensus_facts
            for tenant in tenants
        },
        VETO: {
            tenant.tenant_id: own_facts[tenant.tenant_id] + veto_facts[tenant.tenant_id]
            for tenant in tenants
        },
    }


def _evaluate(
    *,
    tenant: TenantData,
    facts: Sequence[Fact],
    condition: str,
    n_draws: int,
    seed: int,
) -> TenantConditionRow:
    """Đo một tenant trong một điều kiện: bốn chỉ số kèm khoảng tin cậy."""
    active = [fact for fact in facts if fact.status is FactStatus.ACTIVE]
    return TenantConditionRow(
        tenant_id=tenant.tenant_id,
        condition=condition,
        source=tenant.ground_truth.source,
        n_train=len(tenant.train_traces),
        n_measure=len(tenant.measure_traces),
        n_reference=len(tenant.ground_truth.reference),
        n_rules=len(active),
        metrics=metrics_with_ci(
            facts,
            tenant.ground_truth.reference,
            tenant.measure_traces,
            tenant.tenant_id,
            n_draws=n_draws,
            seed=seed,
            condition=condition,
        ),
    )


def _mean_f1(rows: Sequence[TenantConditionRow]) -> float:
    """F1 trung bình qua các tenant (tiêu chí chọn ứng viên tốt hơn cho điều kiện 7)."""
    if not rows:
        return 0.0
    return sum(
        f1_score(row.metrics.precision.value, row.metrics.recall.value) for row in rows
    ) / len(rows)


def run_experiments(
    *,
    seed: int = SYNTHETIC_SEED,
    n_cases: int = SYNTHETIC_N_CASES,
    n_draws: int,
    document_rules: frozenset[Rule] = frozenset(),
) -> BaselineReport:
    """Chạy bảy điều kiện trên bộ chuẩn bán tổng hợp, trả báo cáo đầy đủ.

    Điều kiện 7 lấy ứng viên tốt hơn trong hai điều kiện phân tầng
    (đồng thuận / phủ quyết) theo F1 trung bình, cộng luật tài liệu
    (`document_rules` — rỗng ở giai đoạn 1). Ghi chú của báo cáo nói rõ
    điều kiện nào trùng nhau ở giai đoạn 1 và tập luật tài liệu có rỗng
    hay không, để người đọc không tưởng là lỗi.
    """
    tenants = _tenant_data(seed=seed, n_cases=n_cases)
    sets = condition_fact_sets(tenants)
    measured: dict[str, dict[str, TenantConditionRow]] = {}
    for condition in (DECLARE_ONLY, POOLED, VOTING, CONSENSUS, VETO):
        measured[condition] = {
            tenant.tenant_id: _evaluate(
                tenant=tenant,
                facts=sets[condition][tenant.tenant_id],
                condition=condition,
                n_draws=n_draws,
                seed=seed,
            )
            for tenant in tenants
        }
    # Cách ly là CÙNG một phép đo với Chỉ Declare ở giai đoạn 1 (cùng tập
    # fact, cùng trace, cùng đáp án) nên chia sẻ đúng một hàng — khoảng tin
    # cậy cũng giống hệt, không phải hai lần rút bootstrap khác nhau.
    measured[ISOLATION] = {
        tenant_id: replace(row, condition=ISOLATION)
        for tenant_id, row in measured[DECLARE_ONLY].items()
    }
    consensus_rows = list(measured[CONSENSUS].values())
    veto_rows = list(measured[VETO].values())
    base_condition = CONSENSUS if _mean_f1(consensus_rows) >= _mean_f1(veto_rows) else VETO
    document_facts = tuple(_global_facts(document_rules))
    if not document_rules:
        # Tập luật tài liệu rỗng thì điều kiện 7 là đúng ứng viên tốt hơn
        # đó — chia sẻ hàng như cách ly, không đo lại.
        measured[DOCUMENT] = {
            tenant_id: replace(row, condition=DOCUMENT)
            for tenant_id, row in measured[base_condition].items()
        }
    else:
        measured[DOCUMENT] = {
            tenant.tenant_id: _evaluate(
                tenant=tenant,
                facts=sets[base_condition][tenant.tenant_id] + document_facts,
                condition=DOCUMENT,
                n_draws=n_draws,
                seed=seed,
            )
            for tenant in tenants
        }
    rows = [
        measured[condition][tenant.tenant_id] for tenant in tenants for condition in CONDITIONS
    ]
    note = (
        "Ở giai đoạn 1, điều kiện 1 (Chỉ Declare) và điều kiện 2 (Cách ly) cho "
        "cùng số: cùng khám phá Declare trên trace của tenant, chưa có kho "
        "global để cách ly loại ra — hai cột trùng nhau là đúng, không phải "
        "lỗi. Điều kiện 7 lấy ứng viên tốt hơn trong hai điều kiện phân tầng "
        f"theo F1 trung bình: {base_condition}. "
    )
    if not document_rules:
        note += DOCUMENT_RULES_EMPTY_NOTE
    else:
        note += f"Tập luật tài liệu có {len(document_rules)} luật trích từ văn bản."
    return BaselineReport(rows=tuple(rows), note=note)


def _format_metric(value: float, lower: float, upper: float) -> str:
    """Một chỉ số thành `giá trị [cận dưới, cận trên]`."""
    return f"{value:.3f} [{lower:.3f}, {upper:.3f}]"


def format_experiments_report(report: BaselineReport) -> str:
    """Báo cáo bảy điều kiện thành văn bản (lệnh 10.2 in văn bản này)."""
    lines = [
        "Báo cáo bảy điều kiện thí nghiệm (task 10.2)",
        f"Ngưỡng khám phá và đáp án: support={GROUND_TRUTH_SUPPORT:g}, "
        f"confidence={GROUND_TRUTH_CONFIDENCE:g} (cố định, dùng chung mọi điều kiện); "
        f"ngưỡng vi phạm: quá {VIOLATION_THRESHOLD:.0%} trace đo",
        "",
        report.note,
        "",
    ]
    for row in report.rows:
        metrics = row.metrics
        precision = _format_metric(
            metrics.precision.value, metrics.precision.lower, metrics.precision.upper
        )
        recall = _format_metric(
            metrics.recall.value, metrics.recall.lower, metrics.recall.upper
        )
        violation = _format_metric(
            metrics.violation_rate.value,
            metrics.violation_rate.lower,
            metrics.violation_rate.upper,
        )
        transfer = _format_metric(
            metrics.negative_transfer.value,
            metrics.negative_transfer.lower,
            metrics.negative_transfer.upper,
        )
        lines.append(
            f"Tenant {row.tenant_id} — {row.condition} "
            f"(đáp án: {row.source}; học {row.n_train} trace, "
            f"đo {row.n_measure} trace; đáp án {row.n_reference} luật, "
            f"khám phá {row.n_rules} luật)"
        )
        lines.append(f"  precision:        {precision}")
        lines.append(f"  recall:           {recall}")
        lines.append(f"  tỉ lệ vi phạm:    {violation}")
        lines.append(f"  negative transfer: {transfer}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Lệnh bảy điều kiện: `python -m praxon_core.eval.experiments`.

    Mã thoát: 0 = xong; 2 = tham số không hợp lệ.
    """
    default_draws = Settings.model_fields["bootstrap_draws"].default
    parser = argparse.ArgumentParser(
        prog="praxon_core.eval.experiments",
        description="Bảy điều kiện thí nghiệm trên bộ chuẩn bán tổng hợp (task 10.2).",
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
    report = run_experiments(seed=args.seed, n_cases=args.n_cases, n_draws=n_draws)
    print(format_experiments_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
