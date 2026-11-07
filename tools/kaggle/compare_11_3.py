r"""Script so sánh kết quả lần resume với lần tham chiếu (task 11.3, A.4).

Chạy trên máy này (không phải trên Kaggle): nạp outcome JSON + usage log
JSON của lần tham chiếu (thử 0) và của lần resume (thử 1/2/3), rồi kiểm
bốn mục trong A.4 và in PASS/FAIL theo từng mục, không so bằng mắt.

1. Bảy trường nội dung bằng nhau tuyệt đối (`trajectories`, `insights`,
   `decisions`, `candidate_ids`, `fact_rows`, `fact_closes`,
   `run_status == "succeeded"` ở cả hai lần). `events` không so (theo
   tiền lệ 10.3) mà chỉ in tóm tắt hai bên cạnh nhau làm chẩn đoán.
2. Token: đẳng thức có kiểm toán
   `tokens_resumed + Σ usage lô cache-hit == tokens_reference` (sai số 0).
   `tokens_resumed` là token của OUTCOME phiên sau — nó là tổng TÍCH LŨY
   (coordinator mang `tokens_in`/`tokens_out` của checkpoint vào vòng
   chạy tiếp, `coordinator.py` dòng 823-824, rồi cộng thêm các lô mới;
   đã kiểm bằng lần chạy thật: phiên sau 10 lần gọi mới ra 450 token
   = 300 của checkpoint + 150 mới). Vì vậy token của các lô đã xong đã
   nằm trong `tokens_resumed` rồi, không cộng thêm. Phần duy nhất còn
   thiếu là các lô phiên sau phục vụ từ cache (hit): phiên sau đóng 0
   token cho chúng nhưng lần tham chiếu đã gọi thật, nên cộng usage của
   chúng (tra theo khóa đệm từ log tham chiếu; cùng prompt + revision +
   tham số + schema thì cùng usage). Một khóa hit nào không có trong log
   tham chiếu thì FAIL rõ (không đoán usage).
3. Số lần gọi mô hình: mỗi lô còn lại hoặc gọi thật hoặc phục vụ từ
   cache, nên `model_calls + cache_hits == expected_remaining_calls`.
   (Khi không có hit thì đúng bằng "gọi đúng số lần cho phần việc còn
   lại"; cộng cache_hits để một hit hợp lệ không bị tính là thiếu việc.)
4. Checkpoint đã dùng: khóa checkpoint và `cases_done` đúng điểm đã định
   (chỉ kiểm khi người gọi truyền `--expected-checkpoint-key` /
   `--expected-cases-done`; nếu lần thử phân loại lại theo điểm dừng thật
   (R1) thì truyền đúng điểm thật). Namespace của checkpoint cũng kiểm
   được: driver ghi `checkpoint_namespace` (dạng `trial-{n}`, Phụ lục A.7)
   vào outcome, người gọi truyền `--expected-checkpoint-namespace` để
   chắc checkpoint phiên sau nạp đúng là của lần thử đang so, không phải
   của lần thử khác cùng tiền tố gốc.

Cách dùng::

    python -m tools.kaggle.compare_11_3 \
        --reference-outcome ref/outcome.json --reference-usage ref/usage_log.json \
        --resumed-outcome res/outcome.json --resumed-usage res/usage_log.json \
        [--expected-checkpoint-key checkpoints/.../000200.json]
        [--expected-cases-done 200]
        [--expected-checkpoint-namespace trial-1]

Thoát 0 khi mọi mục PASS, 1 khi có mục FAIL (hoặc file sai hình dạng).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["CheckResult", "ComparisonResult", "compare", "load_json", "main"]

CONTENT_FIELDS: tuple[str, ...] = (
    "trajectories",
    "insights",
    "decisions",
    "candidate_ids",
    "fact_rows",
    "fact_closes",
)
"""Bảy trường nội dung so bằng nhau tuyệt đối (trừ `run_status` kiểm riêng)."""


@dataclass(frozen=True)
class CheckResult:
    """Kết quả một mục kiểm: tên, đạt hay không, chi tiết số liệu."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ComparisonResult:
    """Kết quả so sánh đầy đủ: từng mục + tóm tắt event hai bên."""

    checks: tuple[CheckResult, ...]
    reference_events: dict[str, Any] = field(default_factory=dict)
    resumed_events: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """PASS khi mọi mục đều đạt."""
        return all(check.passed for check in self.checks)

    def report(self) -> str:
        """Báo cáo từng mục PASS/FAIL + tóm tắt event hai bên."""
        lines = ["So sánh lần resume với lần tham chiếu (11.3, A.4):"]
        for check in self.checks:
            mark = "PASS" if check.passed else "FAIL"
            lines.append(f"  [{mark}] {check.name}: {check.detail}")
        verdict = "PASS" if self.passed else "FAIL"
        lines.append(f"Verdict: {verdict}")
        lines.append(
            "Events (chẩn đoán, không so): "
            f"tham chiếu={self.reference_events} resume={self.resumed_events}"
        )
        return "\n".join(lines)


def load_json(path: Path) -> dict[str, Any]:
    """Nạp một file JSON object; sai hình dạng thì lỗi rõ."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"file JSON sai hình dạng (không phải object): {path}")
    return data


def _usage_of(entry: Mapping[str, Any], usage_by_key: Mapping[str, int]) -> int:
    """Usage của một mục log: miss lấy usage của nó, hit tra theo khóa.

    Khóa hit không có trong log tham chiếu thì lỗi rõ (không đoán usage).
    """
    key = entry.get("key")
    if not isinstance(key, str):
        raise ValueError(f"mục usage log thiếu khóa: {entry!r}")
    if entry.get("hit") is True:
        if key not in usage_by_key:
            raise ValueError(
                f"khóa hit {key} không có trong log tham chiếu: "
                "không tra được usage đã tiết kiệm"
            )
        return usage_by_key[key]
    prompt_tokens = entry.get("prompt_tokens")
    completion_tokens = entry.get("completion_tokens")
    if not isinstance(prompt_tokens, int) or not isinstance(completion_tokens, int):
        raise ValueError(f"mục usage log sai hình dạng: {entry!r}")
    return prompt_tokens + completion_tokens


def _usage_by_key(entries: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Map khóa đệm thành usage từ các mục miss (lần xuất hiện đầu thắng)."""
    usage: dict[str, int] = {}
    for entry in entries:
        if entry.get("hit") is True:
            continue
        key = entry.get("key")
        if not isinstance(key, str):
            raise ValueError(f"mục usage log thiếu khóa: {entry!r}")
        if key not in usage:
            usage[key] = _usage_of(entry, usage)
    return usage


def _resume_chunk_index(cases_per_chunk: Sequence[int], cases_done: int) -> int:
    """Lô đầu tiên chưa xong khi đã xong `cases_done` case (như driver)."""
    done = 0
    for index, cases in enumerate(cases_per_chunk):
        if done == cases_done:
            return index
        done += cases
    if done == cases_done:
        return len(cases_per_chunk)
    raise ValueError(
        f"cases_done={cases_done} không nằm ở ranh giới lô "
        f"(số case mỗi lô: {list(cases_per_chunk)})"
    )


def _first_difference(left: object, right: object) -> str:
    """Mô tả ngắn chỗ khác nhau đầu tiên giữa hai giá trị JSON."""
    if type(left) is not type(right):
        return f"kiểu khác nhau ({type(left).__name__} != {type(right).__name__})"
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return f"dài khác nhau ({len(left)} != {len(right)})"
        for index, (item_left, item_right) in enumerate(zip(left, right, strict=True)):
            if item_left != item_right:
                return f"khác ở phần tử {index}"
        return "bằng nhau"
    return "khác nhau"


def compare(
    *,
    reference_outcome: Mapping[str, Any],
    reference_usage: Mapping[str, Any],
    resumed_outcome: Mapping[str, Any],
    resumed_usage: Mapping[str, Any],
    expected_checkpoint_key: str | None = None,
    expected_cases_done: int | None = None,
    expected_checkpoint_namespace: str | None = None,
) -> ComparisonResult:
    """So lần resume với lần tham chiếu theo A.4, trả từng mục PASS/FAIL.

    Không raise khi một mục FAIL (chỉ trả kết quả để in báo cáo); chỉ
    raise khi file sai hình dạng tới mức không so được (thiếu trường,
    thiếu usage tra cứu, `cases_done` không ở ranh giới lô).
    """
    checks: list[CheckResult] = []
    for name in CONTENT_FIELDS:
        left = reference_outcome.get(name, "<thiếu>")
        right = resumed_outcome.get(name, "<thiếu>")
        passed = left == right and left != "<thiếu>"
        detail = "bằng nhau" if passed else f"khác nhau ({_first_difference(left, right)})"
        checks.append(CheckResult(name=f"nội dung: {name}", passed=passed, detail=detail))
    ref_status = reference_outcome.get("run_status")
    res_status = resumed_outcome.get("run_status")
    checks.append(
        CheckResult(
            name="nội dung: run_status",
            passed=ref_status == "succeeded" and res_status == "succeeded",
            detail=f"tham chiếu={ref_status}, resume={res_status}",
        )
    )
    ref_layout = reference_outcome.get("calls_per_chunk")
    res_layout = resumed_outcome.get("calls_per_chunk")
    checks.append(
        CheckResult(
            name="bố cục: calls_per_chunk",
            passed=ref_layout == res_layout and isinstance(ref_layout, list),
            detail=f"tham chiếu={ref_layout}, resume={res_layout}",
        )
    )
    ref_tokens = int(reference_outcome["tokens_in"]) + int(reference_outcome["tokens_out"])
    res_tokens = int(resumed_outcome["tokens_in"]) + int(resumed_outcome["tokens_out"])
    ref_entries = reference_usage.get("entries")
    res_entries = resumed_usage.get("entries")
    if not isinstance(ref_entries, list) or not isinstance(res_entries, list):
        raise ValueError("usage log thiếu danh sách 'entries'")
    usage_by_key = _usage_by_key(ref_entries)
    cases_per_chunk = resumed_outcome.get("cases_per_chunk")
    cases_done = resumed_outcome.get("cases_done_at_resume")
    if not isinstance(cases_per_chunk, list) or not isinstance(cases_done, int):
        raise ValueError("outcome resume thiếu cases_per_chunk/cases_done_at_resume")
    if not isinstance(res_layout, list):
        raise ValueError("outcome resume thiếu calls_per_chunk")
    # Điểm resume phải đúng ranh giới lô (checkpoint chỉ ghi ở ranh giới);
    # không đúng thì dữ liệu resume hỏng, từ chối so thay vì đoán.
    _resume_chunk_index(cases_per_chunk, cases_done)
    try:
        saved_hits = sum(
            _usage_of(entry, usage_by_key) for entry in res_entries if entry.get("hit") is True
        )
    except ValueError as exc:
        checks.append(
            CheckResult(name="token: đẳng thức kiểm toán", passed=False, detail=str(exc))
        )
        saved_hits = 0
    else:
        passed = res_tokens + saved_hits == ref_tokens
        checks.append(
            CheckResult(
                name="token: đẳng thức kiểm toán",
                passed=passed,
                detail=(
                    f"resume (tích lũy)={res_tokens} "
                    f"+ cache hit={saved_hits} = {res_tokens + saved_hits}, "
                    f"tham chiếu={ref_tokens}"
                ),
            )
        )
    expected_remaining = resumed_outcome.get("expected_remaining_calls")
    model_calls = resumed_outcome.get("model_calls")
    cache_hits = resumed_outcome.get("cache_hits")
    calls_done = (
        model_calls + cache_hits
        if isinstance(model_calls, int) and isinstance(cache_hits, int)
        else None
    )
    checks.append(
        CheckResult(
            name="số lần gọi mô hình phiên sau",
            passed=calls_done == expected_remaining and isinstance(calls_done, int),
            detail=(
                f"gọi={model_calls} + cache hit={cache_hits} = {calls_done}, "
                f"còn lại phải làm={expected_remaining}"
            ),
        )
    )
    if expected_checkpoint_key is not None:
        actual_key = resumed_outcome.get("checkpoint_key")
        checks.append(
            CheckResult(
                name="checkpoint đã dùng",
                passed=actual_key == expected_checkpoint_key,
                detail=f"dùng={actual_key}, đã định={expected_checkpoint_key}",
            )
        )
    if expected_checkpoint_namespace is not None:
        actual_namespace = resumed_outcome.get("checkpoint_namespace")
        checks.append(
            CheckResult(
                name="checkpoint đã dùng (namespace)",
                passed=actual_namespace == expected_checkpoint_namespace,
                detail=f"namespace={actual_namespace}, đã định={expected_checkpoint_namespace}",
            )
        )
    if expected_cases_done is not None:
        checks.append(
            CheckResult(
                name="cases_done tại điểm resume",
                passed=cases_done == expected_cases_done,
                detail=f"resume từ {cases_done} case, đã định {expected_cases_done}",
            )
        )
    reference_events = reference_outcome.get("events_summary")
    resumed_events = resumed_outcome.get("events_summary")
    return ComparisonResult(
        checks=tuple(checks),
        reference_events=reference_events if isinstance(reference_events, dict) else {},
        resumed_events=resumed_events if isinstance(resumed_events, dict) else {},
    )


def main(argv: list[str] | None = None) -> int:
    """CLI so sánh: nạp 4 file, in báo cáo, thoát 0 khi PASS, 1 khi FAIL."""
    parser = argparse.ArgumentParser(
        description="So sánh lần resume 11.3 với lần tham chiếu (A.4)."
    )
    parser.add_argument("--reference-outcome", type=Path, required=True)
    parser.add_argument("--reference-usage", type=Path, required=True)
    parser.add_argument("--resumed-outcome", type=Path, required=True)
    parser.add_argument("--resumed-usage", type=Path, required=True)
    parser.add_argument("--expected-checkpoint-key", type=str, default=None)
    parser.add_argument("--expected-cases-done", type=int, default=None)
    parser.add_argument("--expected-checkpoint-namespace", type=str, default=None)
    args = parser.parse_args(argv)
    try:
        result = compare(
            reference_outcome=load_json(args.reference_outcome),
            reference_usage=load_json(args.reference_usage),
            resumed_outcome=load_json(args.resumed_outcome),
            resumed_usage=load_json(args.resumed_usage),
            expected_checkpoint_key=args.expected_checkpoint_key,
            expected_cases_done=args.expected_cases_done,
            expected_checkpoint_namespace=args.expected_checkpoint_namespace,
        )
    except (ValueError, KeyError) as exc:
        print(f"FAIL: không so được: {exc}", file=sys.stderr)
        return 1
    print(result.report())
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
