"""Hiệu chỉnh cổng Beta (task 9.6; spec: Cổng Beta + Phép chia + Cổng khóa).

Hiệu chỉnh các tham số cổng Beta — ngưỡng tin 0,7; ngưỡng lên 0,95; ngưỡng
gỡ 0,05; độ mạnh tiên nghiệm — CHỈ trên phần hiệu chỉnh (calibration
split), KHÔNG BAO GIỜ trên phần đo (test split). Bộ điều phối từ chối
hiệu chỉnh trên phần đo ngay ở đầu hàm, trước mọi đánh giá (spec dòng
152: cấu hình khóa bằng commit trước khi chạm phần đo; plan 9.6).

Phương pháp (đo được, lặp lại được):
- Dữ liệu: bộ chuẩn bán tổng hợp (bộ sinh 5.1) — đáp án độc lập với dữ
  liệu (luật đã cài vào bộ sinh), nên không cần đáp án từ phần đo. Cùng
  một hàm này áp dụng được cho trace BPIC 2015 phần hiệu chỉnh nếu có
  đáp án tham chiếu, nhưng đáp án BPIC lấy từ phần đo nên KHÔNG dùng
  cho hiệu chỉnh.
- Chia 60/20/20 theo thứ tự đến: khám phá luật trên phần học (ngưỡng cố
  định 0,5/0,5 như 8.1), đếm bằng chứng trên phần hiệu chỉnh theo đúng
  quy ước đếm của miner (``_brute_counts``), đánh giá từng độ mạnh
  tiên nghiệm bằng mô phỏng cổng chạy tuần tự: sau mỗi trace hiệu
  chỉnh, tính hậu nghiệm Beta; luật vượt ngưỡng lên trước thì lên,
  chạm ngưỡng gỡ trước thì gỡ, không chạm ngưỡng nào thì chờ.
- Vùng bất biến: mỗi độ mạnh ứng viên phải qua ``check_prior_invariant``
  với tiên nghiệm xấu nhất (độ tin 1,0) — tiên nghiệm một mình không
  bao giờ được lên (P < 0,95). Độ mạnh ngoài vùng (ví dụ 8,0) bị từ
  chối ngay, không được đánh giá.

Kết quả đo (bộ chuẩn, hạt 42, 300 trace; 180 học / 60 hiệu chỉnh / 60
đo; khám phá ra 20 luật, tất cả đều đúng so với đáp án 56 luật):
- độ mạnh 2,0: 0 lên sai, 0 gỡ sai, 20/20 luật lên, lên ở trace hiệu
  chỉnh thứ 13 (trung vị), biên bất biến 0,2930.
- độ mạnh 4,0 (mặc định lúc đo): 0 lên sai, 0 gỡ sai, 20/20 luật lên, lên ở
  trace hiệu chỉnh thứ 16 (trung vị), biên bất biến 0,1181.
- độ mạnh 6,0: 0 lên sai, 0 gỡ sai, 20/20 luật lên, lên ở trace hiệu
  chỉnh thứ 20 (trung vị), biên bất biến 0,0324.
- Chọn 2,0: ít lỗi nhất (hòa 0-0-0), rồi lên nhanh nhất, rồi nhỏ nhất.
  Độ mạnh 2,0 cũng có biên bất biến lớn nhất — an toàn nhất trước tiên
  nghiệm độ tin cao từ gói toàn cục.

Hàm hiệu chỉnh CHỈ trả về kết quả, KHÔNG ghi lại tệp cấu hình chính
sách (``default_rule_table.toml`` giữ độ mạnh mặc định 2,0 theo quyết định hiệu chỉnh 9.6): đổi
mặc định là quyết định chính sách, phải duyệt riêng. Phần tối thiểu 30
case (``min_matching_cases``) là điều kiện của Governor cho luật có
điều kiện thuộc tính (quy tắc 7), không phải tham số cổng Beta; bộ
chuẩn bán tổng hợp không có luật điều kiện nên không đo được ở đây —
nó được hiệu chỉnh ở task 9.5 trên BPIC 2019 (có điều kiện thuộc tính),
và vẫn nằm trong ``Policy`` như một giá trị đã khóa.
"""

from __future__ import annotations

import argparse
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from praxon_core.declare.index import (
    ActivityIndex,
    Trace,
    build_index,
    precedence_holds,
    response_holds,
)
from praxon_core.declare.miner import Rule, discover
from praxon_core.eval.ground_truth import ground_truth_from_generator
from praxon_core.eval.report import split_generated_traces
from praxon_core.learning.beta import (
    Prior,
    check_prior_invariant,
    posterior_prob_ge,
    prior_prob_ge,
)
from praxon_core.learning.rules import Policy, default_rule_table
from praxon_core.synthetic.generator import GeneratorParams, generate

CALIBRATION_STRENGTHS: tuple[float, ...] = (2.0, 4.0, 6.0)
"""Độ mạnh tiên nghiệm thử khi hiệu chỉnh: ít nhất ba giá trị, tất cả
trong vùng bất biến cho phép (kiểm bằng ``check_prior_invariant`` với
tiên nghiệm xấu nhất độ tin 1,0: 6,0 cho P = 0,9176 < 0,95; 8,0 cho
P = 0,9596 ≥ 0,95 nên ngoài vùng — xem test)."""

DISCOVERY_SUPPORT = 0.5
"""Ngưỡng support khi khám phá luật trên phần học: cùng cặp ngưỡng cố
định 8.1 đã dùng cho đáp án (``eval/ground_truth.py``)."""

DISCOVERY_CONFIDENCE = 0.5
"""Ngưỡng confidence khi khám phá luật trên phần học (cùng cặp 8.1)."""

WORST_CASE_PRIOR_CONFIDENCE = 1.0
"""Độ tin xấu nhất khi kiểm bất biến: tiên nghiệm độ tin càng cao càng
dễ lên một mình, nên kiểm ở 1,0 là đủ cho mọi độ tin thấp hơn."""

FLAT_PRIOR_CONFIDENCE = 0.5
"""Độ tin của tiên nghiệm phẳng cho luật học từ trace (không có gói
toàn cục): không thiên về đúng hay sai."""


@dataclass(frozen=True)
class RuleEvidence:
    """(Thành công, lần thử) của một luật trên các trace đã cho."""

    canonical_key: str
    successes: int
    trials: int


@dataclass(frozen=True)
class StrengthOutcome:
    """Kết quả đánh giá một độ mạnh tiên nghiệm trên phần hiệu chỉnh."""

    strength: float
    false_promotes: int
    false_retires: int
    promoted: int
    retired: int
    undecided: int
    median_traces_to_promote: float | None
    invariant_margin: float


@dataclass(frozen=True)
class CalibrationResult:
    """Kết quả hiệu chỉnh: các độ mạnh đã thử + độ mạnh được chọn."""

    strengths: tuple[float, ...]
    outcomes: tuple[StrengthOutcome, ...]
    selected_strength: float


def _evidence_in_index(rule: Rule, index: ActivityIndex) -> tuple[int, int]:
    """(Thành công, lần thử) của một luật trên một trace đã lập chỉ mục.

    Đúng quy ước đếm của miner (``_brute_counts``): ``response`` kích
    hoạt khi ``first`` xuất hiện, thỏa mãn khi ``second`` xuất hiện sau
    lần ``first`` cuối cùng; ``precedence`` kích hoạt khi ``second``
    xuất hiện, thỏa mãn khi ``first`` xuất hiện trước lần ``second``
    đầu tiên.
    """
    if rule.template == "response":
        activated = rule.first in index
        if not activated:
            return 0, 0
        return (1, 1) if response_holds(index, rule.first, rule.second) else (0, 1)
    if rule.template == "precedence":
        activated = rule.second in index
        if not activated:
            return 0, 0
        return (1, 1) if precedence_holds(index, rule.first, rule.second) else (0, 1)
    raise ValueError(f"mẫu không hỗ trợ: {rule.template}")


def count_rule_evidence(rule: Rule, traces: Sequence[Trace]) -> RuleEvidence:
    """(Thành công, lần thử) của một luật trên các trace, theo miner."""
    successes = 0
    trials = 0
    for trace in traces:
        one_success, one_trial = _evidence_in_index(rule, build_index(trace))
        successes += one_success
        trials += one_trial
    return RuleEvidence(
        canonical_key=rule.canonical_key,
        successes=successes,
        trials=trials,
    )


def _worst_case_prior() -> Prior:
    """Tiên nghiệm xấu nhất cho kiểm bất biến: độ tin 1,0, độ mạnh mặc định."""
    return Prior(
        canonical_key="xau-nhat",
        confidence=WORST_CASE_PRIOR_CONFIDENCE,
        strength=None,
    )


def evaluate_strength(
    *,
    trial_rules: Sequence[Rule],
    calibration_traces: Sequence[Trace],
    ground_truth: frozenset[str],
    policy: Policy,
    strength: float,
) -> StrengthOutcome:
    """Đánh giá một độ mạnh tiên nghiệm trên phần hiệu chỉnh.

    Kiểm bất biến trước (tiên nghiệm xấu nhất độ tin 1,0 không được lên
    một mình — độ mạnh ngoài vùng thì ``PriorInvariantError``), rồi mô
    phỏng cổng chạy tuần tự trên các trace hiệu chỉnh: sau mỗi trace,
    tính hậu nghiệm Beta của từng luật; luật vượt ngưỡng lên trước thì
    lên, chạm ngưỡng gỡ trước thì gỡ, không chạm ngưỡng nào thì chờ.
    """
    check_prior_invariant(
        [_worst_case_prior()],
        confidence_threshold=policy.confidence_threshold,
        promote_probability=policy.promote_probability,
        prior_strength_default=strength,
    )
    invariant_margin = policy.promote_probability - prior_prob_ge(
        _worst_case_prior(),
        policy.confidence_threshold,
        strength_default=strength,
    )
    indices = [build_index(trace) for trace in calibration_traces]
    false_promotes = 0
    false_retires = 0
    promoted = 0
    retired = 0
    undecided = 0
    promote_at: list[int] = []
    for rule in trial_rules:
        successes = 0
        trials = 0
        crossed: str | None = None
        for position, index in enumerate(indices, start=1):
            one_success, one_trial = _evidence_in_index(rule, index)
            successes += one_success
            trials += one_trial
            prior = Prior(
                canonical_key=rule.canonical_key,
                confidence=FLAT_PRIOR_CONFIDENCE,
                strength=strength,
            )
            if trials == 0:
                probability = prior_prob_ge(
                    prior,
                    policy.confidence_threshold,
                    strength_default=strength,
                )
            else:
                probability = posterior_prob_ge(
                    prior,
                    successes,
                    trials,
                    policy.confidence_threshold,
                    strength_default=strength,
                )
            if probability >= policy.promote_probability:
                crossed = "promote"
                promote_at.append(position)
                break
            if probability < policy.retire_probability:
                crossed = "retire"
                break
        in_truth = rule.canonical_key in ground_truth
        if crossed is None:
            undecided += 1
        elif crossed == "promote":
            promoted += 1
            if not in_truth:
                false_promotes += 1
        else:
            retired += 1
            if in_truth:
                false_retires += 1
    return StrengthOutcome(
        strength=strength,
        false_promotes=false_promotes,
        false_retires=false_retires,
        promoted=promoted,
        retired=retired,
        undecided=undecided,
        median_traces_to_promote=(float(statistics.median(promote_at)) if promote_at else None),
        invariant_margin=invariant_margin,
    )


def _selection_key(outcome: StrengthOutcome) -> tuple[int, float, float]:
    """Ít lỗi nhất, rồi lên nhanh nhất, rồi độ mạnh nhỏ nhất."""
    return (
        outcome.false_promotes + outcome.false_retires,
        (
            outcome.median_traces_to_promote
            if outcome.median_traces_to_promote is not None
            else float("inf")
        ),
        outcome.strength,
    )


def calibrate_beta(
    *,
    split: Literal["calibration", "test"],
    train_traces: Sequence[Trace],
    calibration_traces: Sequence[Trace],
    ground_truth: frozenset[str],
    policy: Policy,
    strengths: Sequence[float] = CALIBRATION_STRENGTHS,
) -> CalibrationResult:
    """Hiệu chỉnh cổng Beta trên phần hiệu chỉnh, trả về độ mạnh được chọn.

    Từ chối hiệu chỉnh trên phần đo ngay ở đầu hàm, trước mọi đánh giá
    — gọi với ``split="test"`` thì ``ValueError`` dù dữ liệu vào có ra
    sao. Khám phá luật thử trên phần học (ngưỡng cố định 0,5/0,5),
    đánh giá từng độ mạnh ứng viên trên phần hiệu chỉnh, chọn độ mạnh
    ít lỗi nhất, rồi lên nhanh nhất, rồi nhỏ nhất. Không ghi lại tệp
    cấu hình chính sách.
    """
    if split != "calibration":
        raise ValueError(
            "không hiệu chỉnh trên phần đo (test split): hiệu chỉnh chỉ "
            "chạy trên phần hiệu chỉnh (calibration split)"
        )
    if not strengths:
        raise ValueError("phải thử ít nhất một độ mạnh tiên nghiệm")
    if not calibration_traces:
        raise ValueError("phần hiệu chỉnh rỗng: không có gì để hiệu chỉnh")
    trial_rules = discover(
        train_traces,
        support=DISCOVERY_SUPPORT,
        confidence=DISCOVERY_CONFIDENCE,
    )
    if not trial_rules:
        raise ValueError("không khám phá được luật thử nào trên phần học")
    outcomes = tuple(
        evaluate_strength(
            trial_rules=sorted(trial_rules, key=lambda r: r.canonical_key),
            calibration_traces=calibration_traces,
            ground_truth=ground_truth,
            policy=policy,
            strength=strength,
        )
        for strength in strengths
    )
    selected = min(outcomes, key=_selection_key)
    return CalibrationResult(
        strengths=tuple(strengths),
        outcomes=outcomes,
        selected_strength=selected.strength,
    )


def format_calibration_table(result: CalibrationResult) -> str:
    """Bảng hiệu chỉnh: một hàng mỗi độ mạnh (trung vị trace + biên + số lỗi)."""
    lines = [
        "Hiệu chỉnh cổng Beta (task 9.6)",
        "Bộ chuẩn: hạt 42, 300 trace (180 học / 60 hiệu chỉnh / 60 đo)",
        "độ mạnh | trung vị trace | biên bất biến | lên sai | gỡ sai | lên",
    ]
    for outcome in result.outcomes:
        median = outcome.median_traces_to_promote
        median_text = f"{median:.1f}" if median is not None else "-"
        lines.append(
            f"{outcome.strength:.1f} | {median_text} | {outcome.invariant_margin:.4f} | "
            f"{outcome.false_promotes} | {outcome.false_retires} | {outcome.promoted}"
        )
    lines.append(f"Chọn: {result.selected_strength:.1f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Lệnh in bảng hiệu chỉnh: `python -m praxon_core.learning.calibration`.

    Chạy đúng bộ chuẩn của 9.6 (hạt 42, 300 trace) rồi in bảng ba độ mạnh.
    Không ghi lại tệp cấu hình, không đổi ngưỡng hay mặc định.
    """
    parser = argparse.ArgumentParser(
        prog="praxon_core.learning.calibration",
        description="In bảng hiệu chỉnh cổng Beta (task 9.6).",
    )
    parser.parse_args(argv)
    log = generate(tenant_id="acme", params=GeneratorParams(seed=42, n_cases=300))
    train, _test = split_generated_traces(log.traces)
    calibration = tuple(log.traces[len(train) : len(train) + 60])
    result = calibrate_beta(
        split="calibration",
        train_traces=train,
        calibration_traces=calibration,
        ground_truth=ground_truth_from_generator(log).reference,
        policy=default_rule_table().policy,
    )
    print(format_calibration_table(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
