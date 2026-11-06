"""Đường cong khởi động lạnh (plan con 8, task 8.4; spec: đường cong khởi động lạnh).

Cho trace của một tenant mới đến dần, đo bốn chỉ số ở 0, 5, 10, 20,
40 trace. Đường cong trả lời câu khách hàng hỏi trước tiên: bản basic
vừa cài thì làm được gì, và bao lâu thì khớp với doanh nghiệp.

Điểm 0: chưa luật nào active, nên điểm này đo trên luật `trial` ở chế
độ giám sát và ghi rõ như vậy (nhãn `trial (giám sát)`). "Chế độ giám
sát" nghĩa là luật trial được chấm như tập dự đoán đối chiếu với đáp
án — bốn chỉ số tính đúng trên luật trial đó, không phải trên luật
active (vì chưa có luật active nào). Trong code, luật trial được
chuyển tạm thành `active` CHỈ để tính chỉ số (bản gốc không đổi);
nhãn của điểm ghi rõ đây là luật trial. Ở giai đoạn 1, điều kiện
chỉ-Declare và cách ly không có nguồn luật trial nào (không `global`,
không tài liệu) nên điểm 0 mặc định là 0 — khi điều kiện tài liệu
cộng dữ liệu (plan 10) có luật trial từ Wabo, điểm 0 sẽ đo giá trị
của chúng.

Ngưỡng khám phá dùng hai hằng cố định của ground truth (8.1): đường
cong đo trên cùng đáp án nên khám phá phải cùng ngưỡng với đáp án.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass, replace

from praxon_core.declare.index import Trace
from praxon_core.declare.miner import discover
from praxon_core.eval.ground_truth import (
    GROUND_TRUTH_CONFIDENCE,
    GROUND_TRUTH_SUPPORT,
    GroundTruth,
    facts_from_rules,
    ground_truth_from_generator,
)
from praxon_core.eval.metrics import Fact, compute_metrics
from praxon_core.learning.candidate import FactStatus
from praxon_core.synthetic.generator import GeneratorParams, generate

COLD_START_SIZES: tuple[int, ...] = (0, 5, 10, 20, 40)
"""Các điểm đo của đường cong (task row 8.4)."""

TRIAL_SUPERVISED_MODE = "trial (giám sát)"
"""Nhãn điểm 0: đo trên luật `trial` ở chế độ giám sát."""

ACTIVE_MODE = "active"
"""Nhãn các điểm còn lại: đo trên luật `active`."""


@dataclass(frozen=True)
class ColdStartPoint:
    """Một điểm trên đường cong: bốn chỉ số ở một số lượng trace.

    `mode` ghi rõ điểm đo trên luật nào: `trial (giám sát)` ở 0 trace,
    `active` ở các điểm còn lại. `n_rules` là số luật trong tập dự đoán
    ở điểm đó (0 ở điểm 0 khi không có luật trial).
    """

    n_traces: int
    n_rules: int
    precision: float
    recall: float
    violation_rate: float
    negative_transfer: float
    mode: str


def cold_start_curve(
    *,
    train_traces: Sequence[Trace],
    measure_traces: Sequence[Trace],
    ground_truth: GroundTruth,
    tenant_id: str,
    sizes: Sequence[int] = COLD_START_SIZES,
    trial_facts: Sequence[Fact] = (),
) -> tuple[ColdStartPoint, ...]:
    """Đường cong khởi động lạnh: bốn chỉ số ở từng số lượng trace.

    `train_traces` là trace đến dần theo thứ tự (điểm n dùng n trace
    đầu); `measure_traces` là tập đo cố định để tính tỉ lệ vi phạm
    (phần đo BPIC, hoặc toàn bộ log với bộ chuẩn); `ground_truth` là
    đáp án của tenant (8.1); `trial_facts` là luật trial có sẵn ở
    điểm 0 (mặc định rỗng ở giai đoạn 1).
    """
    points: list[ColdStartPoint] = []
    for size in sizes:
        if size < 0:
            raise ValueError(f"số trace phải >= 0, nhận {size}")
        used = train_traces[:size]
        if size == 0:
            # Chưa luật nào active: chấm luật trial ở chế độ giám sát.
            # Chuyển tạm thành active CHỈ để tính chỉ số; bản gốc giữ
            # nguyên status trial, nhãn điểm ghi rõ điều đó.
            prediction_facts = [replace(fact, status=FactStatus.ACTIVE) for fact in trial_facts]
            mode = TRIAL_SUPERVISED_MODE
        else:
            rules = discover(
                used,
                support=GROUND_TRUTH_SUPPORT,
                confidence=GROUND_TRUTH_CONFIDENCE,
            )
            prediction_facts = facts_from_rules(rules, tenant_id)
            mode = ACTIVE_MODE
        metrics = compute_metrics(
            prediction_facts,
            ground_truth.reference,
            measure_traces,
            tenant_id,
        )
        points.append(
            ColdStartPoint(
                n_traces=len(used),
                n_rules=len(prediction_facts),
                precision=metrics.precision,
                recall=metrics.recall,
                violation_rate=metrics.violation_rate,
                negative_transfer=metrics.negative_transfer,
                mode=mode,
            )
        )
    return tuple(points)


def format_cold_start_curve(points: Sequence[ColdStartPoint], *, tenant_id: str) -> str:
    """Một đường cong thành bảng văn bản (lệnh 8.4 in bảng này)."""
    lines = [f"Đường cong khởi động lạnh — tenant {tenant_id}"]
    lines.append("trace | luật | precision | recall | vi phạm | neg.transfer | chế độ")
    for point in points:
        lines.append(
            f"{point.n_traces:5d} | {point.n_rules:4d} | "
            f"{point.precision:.3f} | {point.recall:.3f} | "
            f"{point.violation_rate:.3f} | {point.negative_transfer:.3f} | "
            f"{point.mode}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Lệnh in đường cong: `python -m praxon_core.eval.cold_start`.

    Chạy trên bộ chuẩn bán tổng hợp (tenant sinh bằng bộ sinh, đáp án
    từ bộ sinh): khám phá trên trace đến dần, in đường cong ở 0, 5, 10,
    20, 40 trace. Điểm 0 đo trên luật trial ở chế độ giám sát — ở giai
    đoạn 1 chưa có luật trial nên điểm 0 là 0, nhãn ghi rõ như vậy.
    """
    parser = argparse.ArgumentParser(
        prog="praxon_core.eval.cold_start",
        description="In đường cong khởi động lạnh ở 0, 5, 10, 20, 40 trace (task 8.4).",
    )
    parser.add_argument("--tenant", default="acme", help="tenant sinh (mặc định: %(default)s)")
    parser.add_argument(
        "--seed", type=int, default=42, help="seed bộ sinh (mặc định: %(default)s)"
    )
    parser.add_argument(
        "--n-cases",
        type=int,
        default=300,
        help="số trace sinh (mặc định: %(default)s, như nghiệm thu 5.3)",
    )
    args = parser.parse_args(argv)
    if args.n_cases < max(COLD_START_SIZES):
        print(
            f"số trace phải ít nhất {max(COLD_START_SIZES)}, nhận {args.n_cases}",
            file=sys.stderr,
        )
        return 2
    log = generate(
        tenant_id=args.tenant,
        params=GeneratorParams(seed=args.seed, n_cases=args.n_cases),
    )
    points = cold_start_curve(
        train_traces=log.traces,
        measure_traces=log.traces,
        ground_truth=ground_truth_from_generator(log),
        tenant_id=args.tenant,
    )
    print(format_cold_start_curve(points, tenant_id=args.tenant))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
