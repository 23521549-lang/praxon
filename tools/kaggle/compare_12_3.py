r"""Script so sánh lần chạy lại với lần đầu (task 12.3, A.1).

Chạy trên máy này (không phải trên Kaggle): nạp manifest 12.2 + manifest
lần chạy lại do `driver_12_3.py` ghi, so từng ô theo A.1 rồi in PASS/FAIL
theo từng ô + verdict tổng, ghi báo cáo file `12.3-report.json` kèm event
`reproducibility_check` cho mỗi ô (gắn `run_id` lần chạy lại).

Một ô PASS khi cả 5 mục đều đạt:

1. Tập khóa canonical của fact `active` bằng nhau tuyệt đối (so theo tập).
2. Bốn giá trị chỉ số bằng nhau tuyệt đối (`==`, không epsilon).
3. Tám cận khoảng tin cậy bằng nhau tuyệt đối.
4. Trạng thái `run` hai lần đều là `succeeded`.
5. Token: đẳng thức có kiểm toán
   `tokens_chay_lai + Σ usage lô cache-hit == tokens_lan_dau` (sai số 0)
   VÀ số lần gọi mô hình mới của lần chạy lại == 0.

Ngoài ra ô chỉ PASS khi không có gap tái lập (`repro_gaps` trên hàng `run`
lần chạy lại rỗng): gap là verdict điều kiện (A), năm mục trên là verdict
số liệu (B); task chỉ PASS khi cả hai đều đạt trên cả 35 ô.

Không so: `wall_time` (thời gian tường không phải kết quả); `events`
(lịch sử phiên khác nhau theo tiền lệ 10.3/11.3 — chỉ in tóm tắt hai bên
cạnh nhau làm chẩn đoán, driver không lưu event vào outcome nên ở đây
không có gì để in; xem ghi chú ở `CellComparison`).

Cách dùng::

    python -m tools.kaggle.compare_12_3 \\
        --reference-manifest ref/12.2-manifest.json \\
        --rerun-manifest out/12.3-manifest.json \\
        [--output 12.3-report.json] [--dsn postgresql://...]

Thoát 0 khi verdict tổng PASS, 1 khi có ô FAIL, 2 khi file sai hình dạng.
`--dsn` là tùy chọn: có thì ghi thêm event vào DB qua `insert_event`,
không thì chỉ ghi báo cáo file (mặc định — script chạy trên máy này,
không có DB đo của Kaggle).
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.kaggle.driver_12_3 import (
    CellManifest,
    CellRef,
    UsageLog,
    build_event_record,
    load_manifest,
    resolve_path,
)

METRIC_NAMES: tuple[str, ...] = ("precision", "recall", "violation_rate", "negative_transfer")
"""Bốn chỉ số, luôn báo cùng nhau (spec dòng 178)."""

N_COUNT_NAMES: tuple[str, ...] = ("n_train", "n_measure", "n_reference")
"""Ba số lượng suy từ dữ liệu — cùng `data_hash` thì cùng số (kiểm rẻ, A.1)."""

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
"""Một giá trị JSON thuần (đệ quy)."""

__all__ = [
    "CellComparison",
    "CheckResult",
    "ComparisonReport",
    "compare_cell",
    "compare_manifests",
    "insert_events",
    "load_json",
    "main",
]


@dataclass(frozen=True)
class CheckResult:
    """Kết quả một mục kiểm: tên, đạt hay không, chi tiết số liệu."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class CellComparison:
    """Kết quả so sánh một ô: gap (verdict A) + từng mục số liệu (verdict B).

    `events` không nằm trong các mục so sánh (theo tiền lệ 10.3/11.3):
    lịch sử phiên của hai lần chạy khác nhau là đương nhiên, và outcome
    của driver 12.3 không lưu event nên không có gì để in cạnh nhau.
    """

    tenant_id: str
    condition: str
    run_id: str | None
    gaps: tuple[str, ...] = ()
    checks: tuple[CheckResult, ...] = ()

    @property
    def passed(self) -> bool:
        """Ô PASS khi không có gap VÀ mọi mục số liệu đều đạt."""
        return not self.gaps and all(check.passed for check in self.checks)

    def to_dict(self) -> dict[str, JsonValue]:
        """Xuất thành dict JSON (ghi vào báo cáo file)."""
        return {
            "tenant_id": self.tenant_id,
            "condition": self.condition,
            "run_id": self.run_id,
            "gaps": list(self.gaps),
            "checks": [
                {"name": check.name, "passed": check.passed, "detail": check.detail}
                for check in self.checks
            ],
            "passed": self.passed,
        }

    def report_lines(self) -> list[str]:
        """Các dòng báo cáo của ô: verdict + từng mục PASS/FAIL + gap."""
        verdict = "PASS" if self.passed else "FAIL"
        lines = [f"[{verdict}] ({self.tenant_id}, {self.condition}) run_id={self.run_id}"]
        if self.gaps:
            lines.append(f"  GAP (khong tai lap duoc): {','.join(self.gaps)}")
        for check in self.checks:
            mark = "PASS" if check.passed else "FAIL"
            lines.append(f"  [{mark}] {check.name}: {check.detail}")
        return lines


@dataclass(frozen=True)
class ComparisonReport:
    """Kết quả so sánh toàn bộ phép đo (35 ô)."""

    cells: tuple[CellComparison, ...] = ()

    @property
    def passed(self) -> bool:
        """Verdict tổng PASS khi cả 35 ô PASS."""
        return bool(self.cells) and all(cell.passed for cell in self.cells)

    def report(self) -> str:
        """Báo cáo từng ô PASS/FAIL + verdict tổng."""
        lines = ["So sánh lần chạy lại với lần đầu (12.3, A.1):"]
        for cell in self.cells:
            lines.extend(cell.report_lines())
        n_pass = sum(1 for cell in self.cells if cell.passed)
        verdict = "PASS" if self.passed else "FAIL"
        lines.append(f"Verdict tong: {verdict} ({n_pass}/{len(self.cells)} o PASS)")
        return "\n".join(lines)

    def event_records(self) -> list[JsonValue]:
        """Event `reproducibility_check` cho mỗi ô (A.4)."""
        records: list[JsonValue] = []
        for cell in self.cells:
            failed = [check.name for check in cell.checks if not check.passed]
            if cell.gaps:
                reason = f"không tái lập được: {','.join(cell.gaps)}"
            elif failed:
                reason = f"kết quả khác: {','.join(failed)}"
            else:
                reason = "tái lập được"
            records.append(
                build_event_record(
                    run_id=cell.run_id,
                    tenant_id=cell.tenant_id,
                    condition=cell.condition,
                    gaps=cell.gaps,
                    checks=[
                        {"name": check.name, "passed": check.passed, "detail": check.detail}
                        for check in cell.checks
                    ],
                    reason=reason,
                )
            )
        return records

    def to_dict(self) -> dict[str, JsonValue]:
        """Xuất thành dict JSON (ghi `12.3-report.json`)."""
        verdict = "PASS" if self.passed else "FAIL"
        return {
            "verdict": verdict,
            "verdict_tong": verdict,
            "cells": [cell.to_dict() for cell in self.cells],
            "events": self.event_records(),
        }


def load_json(path: Path) -> dict[str, Any]:
    """Nạp một file JSON object; sai hình dạng thì lỗi rõ."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"file JSON sai hình dạng (không phải object): {path}")
    return data


def _number(value: object, where: str) -> float:
    """Một số JSON (int/float, không tính bool); sai kiểu thì lỗi rõ."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where} phải là số, nhận {value!r}")
    return float(value)


def _metric_triples(
    metrics_data: Mapping[str, Any], where: str
) -> dict[str, tuple[float, float, float]]:
    """Bốn chỉ số kèm CI từ metrics JSON; thiếu/sai thì lỗi rõ."""
    raw = metrics_data.get("metrics")
    if not isinstance(raw, dict):
        raise ValueError(f"{where} thiếu object 'metrics'")
    triples: dict[str, tuple[float, float, float]] = {}
    for name in METRIC_NAMES:
        item = raw.get(name)
        if not isinstance(item, dict):
            raise ValueError(f"{where} thiếu chỉ số '{name}'")
        triples[name] = (
            _number(item.get("value"), f"{where} {name}.value"),
            _number(item.get("lower"), f"{where} {name}.lower"),
            _number(item.get("upper"), f"{where} {name}.upper"),
        )
    return triples


def _fact_keys(path: Path) -> frozenset[str]:
    """Tập khóa fact `active` từ file `{"fact_keys": [...]}`."""
    data = load_json(path)
    raw = data.get("fact_keys")
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError(f"{path} thiếu danh sách chuỗi 'fact_keys'")
    return frozenset(str(item) for item in raw)


def _usage_by_key(path: Path) -> tuple[dict[str, int], UsageLog]:
    """Usage log thành (usage theo khóa cho miss, log đã nạp)."""
    log = UsageLog.from_dict(load_json(path))
    usage: dict[str, int] = {}
    for entry in log.entries:
        if entry.get("hit") is True:
            continue
        key = str(entry["key"])
        usage[key] = int(entry["prompt_tokens"]) + int(entry["completion_tokens"])
    return usage, log


def _sample_diff(left: frozenset[str], right: frozenset[str]) -> str:
    """Mô tả ngắn phần khác nhau của hai tập (tối đa 3 khóa mỗi bên)."""
    only_left = sorted(left - right)[:3]
    only_right = sorted(right - left)[:3]
    parts = [f"{len(left)} khoa vs {len(right)} khoa"]
    if only_left:
        parts.append(f"chi o lan dau: {only_left}")
    if only_right:
        parts.append(f"chi o lan chay lai: {only_right}")
    return "; ".join(parts)


def compare_cell(
    ref: CellManifest,
    rerun: CellManifest,
    *,
    ref_dir: Path,
    rerun_dir: Path,
) -> CellComparison:
    """So một ô tham chiếu với đúng ô đó của lần chạy lại (A.1, 5 mục + gap)."""
    gaps = tuple(part for part in rerun.run.repro_gaps.split(",") if part)
    ref_metrics = load_json(resolve_path(ref.metrics_path, ref_dir))
    rerun_metrics = load_json(resolve_path(rerun.metrics_path, rerun_dir))
    ref_triples = _metric_triples(
        ref_metrics, f"metrics tham chieu ({ref.tenant_id}, {ref.condition})"
    )
    rerun_triples = _metric_triples(
        rerun_metrics, f"metrics chay lai ({rerun.tenant_id}, {rerun.condition})"
    )
    checks: list[CheckResult] = []

    ref_keys = _fact_keys(resolve_path(ref.fact_keys_path, ref_dir))
    rerun_keys = _fact_keys(resolve_path(rerun.fact_keys_path, rerun_dir))
    checks.append(
        CheckResult(
            name="fact_keys",
            passed=ref_keys == rerun_keys,
            detail=(
                "tap khoa fact active bang nhau"
                if ref_keys == rerun_keys
                else _sample_diff(ref_keys, rerun_keys)
            ),
        )
    )

    differing_values = [
        name for name in METRIC_NAMES if ref_triples[name][0] != rerun_triples[name][0]
    ]
    checks.append(
        CheckResult(
            name="metrics",
            passed=not differing_values,
            detail=(
                "bon gia tri chi so bang nhau"
                if not differing_values
                else "; ".join(
                    f"{name}: {ref_triples[name][0]} -> {rerun_triples[name][0]}"
                    for name in differing_values
                )
            ),
        )
    )

    differing_bounds: list[str] = []
    for name in METRIC_NAMES:
        for bound, index in (("lower", 1), ("upper", 2)):
            if ref_triples[name][index] != rerun_triples[name][index]:
                differing_bounds.append(
                    f"{name}.{bound}: "
                    f"{ref_triples[name][index]} -> {rerun_triples[name][index]}"
                )
    checks.append(
        CheckResult(
            name="ci",
            passed=not differing_bounds,
            detail=(
                "tam can khoang tin cay bang nhau"
                if not differing_bounds
                else "; ".join(differing_bounds)
            ),
        )
    )

    checks.append(
        CheckResult(
            name="run_status",
            passed=ref.run.status == "succeeded" and rerun.run.status == "succeeded",
            detail=f"tham chieu={ref.run.status} chay lai={rerun.run.status}",
        )
    )

    n_differing = [
        name
        for name in N_COUNT_NAMES
        if name not in ref_metrics
        or name not in rerun_metrics
        or ref_metrics[name] != rerun_metrics[name]
    ]
    checks.append(
        CheckResult(
            name="n_counts",
            passed=not n_differing,
            detail=(
                "n_train/n_measure/n_reference bang nhau"
                if not n_differing
                else f"lech/thieu: {','.join(n_differing)}"
            ),
        )
    )

    ref_usage, _ = _usage_by_key(resolve_path(ref.usage_log_path, ref_dir))
    _, rerun_log = _usage_by_key(resolve_path(rerun.usage_log_path, rerun_dir))
    tokens_reference = ref.run.tokens_in + ref.run.tokens_out
    tokens_rerun = rerun.run.tokens_in + rerun.run.tokens_out
    saved = 0
    missing_keys: list[str] = []
    for entry in rerun_log.entries:
        if entry.get("hit") is not True:
            continue
        key = str(entry["key"])
        if key in ref_usage:
            saved += ref_usage[key]
        else:
            missing_keys.append(key)
    if missing_keys:
        token_passed = False
        token_detail = (
            f"khong tra duoc usage cho {len(missing_keys)} khoa hit, vd {missing_keys[0]}"
        )
    else:
        audited = tokens_rerun + saved
        token_passed = audited == tokens_reference
        token_detail = (
            f"tokens_chay_lai + tiet_kiem == tokens_lan_dau "
            f"({tokens_rerun} + {saved} == {tokens_reference})"
        )
    checks.append(CheckResult(name="token_audit", passed=token_passed, detail=token_detail))
    checks.append(
        CheckResult(
            name="new_calls",
            passed=rerun_log.model_calls == 0,
            detail=f"so lan goi mo hinh moi cua lan chay lai: {rerun_log.model_calls}",
        )
    )
    return CellComparison(
        tenant_id=ref.tenant_id,
        condition=ref.condition,
        run_id=rerun.run.run_id,
        gaps=gaps,
        checks=tuple(checks),
    )


def compare_manifests(
    ref_manifest: Sequence[CellManifest],
    rerun_manifest: Sequence[CellManifest],
    *,
    ref_dir: Path,
    rerun_dir: Path,
) -> ComparisonReport:
    """So toàn bộ manifest: từng ô tham chiếu với đúng ô đó của lần chạy lại."""
    rerun_by_key: dict[CellRef, CellManifest] = {cell.key: cell for cell in rerun_manifest}
    seen: set[CellRef] = set()
    cells: list[CellComparison] = []
    for ref in ref_manifest:
        rerun = rerun_by_key.get(ref.key)
        if rerun is None:
            cells.append(
                CellComparison(
                    tenant_id=ref.tenant_id,
                    condition=ref.condition,
                    run_id=None,
                    checks=(
                        CheckResult(
                            name="lan_chay_lai",
                            passed=False,
                            detail="thieu o trong manifest lan chay lai",
                        ),
                    ),
                )
            )
            continue
        seen.add(ref.key)
        cells.append(compare_cell(ref, rerun, ref_dir=ref_dir, rerun_dir=rerun_dir))
    for rerun in rerun_manifest:
        if rerun.key not in seen:
            cells.append(
                CellComparison(
                    tenant_id=rerun.tenant_id,
                    condition=rerun.condition,
                    run_id=rerun.run.run_id,
                    checks=(
                        CheckResult(
                            name="thua_o",
                            passed=False,
                            detail="o chi co trong manifest lan chay lai",
                        ),
                    ),
                )
            )
    return ComparisonReport(cells=tuple(cells))


def insert_events(report: ComparisonReport, dsn: str) -> list[str]:
    """Ghi các event `reproducibility_check` vào DB; trả danh sách event_id.

    Chỉ gọi khi có `--dsn`: mặc định script chỉ ghi báo cáo file.
    """
    from psycopg import connect

    from praxon_core.repositories.events import EventRow, insert_event

    ids: list[str] = []
    with connect(dsn) as conn:
        for record in report.event_records():
            assert isinstance(record, dict)
            event = EventRow(
                tenant_id=str(record["tenant_id"]),
                actor="coordinator",
                action="reproducibility_check",
                payload_hash=str(record["payload_hash"]),
                run_id=(str(record["run_id"]) if record["run_id"] is not None else None),
                reason=str(record["reason"]),
            )
            ids.append(insert_event(conn, event))
        conn.commit()
    return ids


def main(argv: Sequence[str] | None = None) -> int:
    """CLI so sánh: hai manifest -> in báo cáo -> ghi `12.3-report.json`.

    Thoát 0 khi verdict tổng PASS, 1 khi có ô FAIL, 2 khi file sai hình dạng.
    """
    parser = argparse.ArgumentParser(
        description="So sánh lần chạy lại 12.3 với lần đầu 12.2 (từng ô, A.1)."
    )
    parser.add_argument("--reference-manifest", required=True)
    parser.add_argument("--rerun-manifest", required=True)
    parser.add_argument("--output", default="12.3-report.json")
    parser.add_argument("--dsn", default=None, help="tùy chọn: ghi event vào DB này")
    args = parser.parse_args(argv)

    ref_path = Path(args.reference_manifest)
    rerun_path = Path(args.rerun_manifest)
    try:
        ref_manifest = load_manifest(ref_path)
        rerun_manifest = load_manifest(rerun_path)
        report = compare_manifests(
            ref_manifest,
            rerun_manifest,
            ref_dir=ref_path.absolute().parent,
            rerun_dir=rerun_path.absolute().parent,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Loi: {exc}")
        return 2
    print(report.report())
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Bao cao ghi vao {output_path}")
    if args.dsn is not None:
        ids = insert_events(report, str(args.dsn))
        print(f"Da ghi {len(ids)} event reproducibility_check vao DB")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
