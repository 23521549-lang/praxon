"""Script báo cáo bảy điều kiện (plan con 11, task 11.2).

Chạy trên máy này (không phải Kaggle): nạp bản đồ vòng→điều kiện
(`11.2-manifest.json`) + đọc hàng `run` từ DB, kiểm đối chiếu hai chiều
(mọi `run` trong đợt 11.2 có đúng một mục bản đồ và ngược lại), tính
lại bốn chỉ số kèm khoảng tin cậy từ tập fact đo trong bản đồ + dữ liệu
gốc rồi đối chiếu với chỉ số đã ghi trong bản đồ, in báo cáo theo đúng
hình dạng 10.2 + giờ chạy mỗi điều kiện + bảng đã dùng/trần mỗi vòng.

Mã thoát: 0 = đối chiếu khớp, báo cáo in xong; 1 = lỗi dữ liệu (thiếu
tệp / thiếu hàng `run` / chỉ số tính lại không khớp bản đồ).
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Sequence
from pathlib import Path

import psycopg

from praxon_core.datasets.bpic2015 import DEFAULT_CACHE_DIR
from praxon_core.eval.experiments import CONDITIONS
from praxon_core.eval.ground_truth import GroundTruth
from praxon_core.eval.metrics import Fact, FactScope
from praxon_core.eval.report import MetricCI, MetricsWithCI, metrics_with_ci
from praxon_core.learning.candidate import FactStatus
from praxon_core.settings import load_settings
from tools.kaggle.driver_11_2 import (
    BPIC_SOURCE,
    DEFAULT_MANIFEST_NAME,
    SYNTHETIC_SOURCE,
    TenantRoundData,
    load_bpic_round_data,
    load_manifest,
    load_synthetic_round_data,
)

RUN_COLUMNS = (
    "tenant_id",
    "seed",
    "model_id",
    "model_revision",
    "code_commit",
    "config_hash",
    "data_hash",
    "tokens_in",
    "tokens_out",
    "wall_time",
    "status",
)
"""Các cột của bảng `run` đem đối chiếu với mục bản đồ."""

METRIC_TOLERANCE = 1e-12
"""Dung sai khi đối chiếu chỉ số tính lại với chỉ số trong bản đồ.

Cùng đầu vào, cùng thứ tự fact, cùng seed bootstrap thì hai lần tính
ra đúng bit; dung sai chỉ để khỏi vỡ vì nhiễu biểu diễn float.
"""


def _fact_from_dict(data: dict[str, object]) -> Fact:
    """Một fact đo trong bản đồ thành eval `Fact`."""
    status = data["status"]
    scope = data["scope"]
    tenant_id = data["tenant_id"]
    if not isinstance(status, str) or not isinstance(scope, str):
        raise ValueError(f"fact trong bản đồ sai hình dạng: {data!r}")
    if not isinstance(tenant_id, str):
        raise ValueError(f"fact trong bản đồ thiếu tenant_id: {data!r}")
    template = data["template"]
    activation = data["activation"]
    target = data["target"]
    canonical_key = data["canonical_key"]
    if not isinstance(template, str) or not isinstance(activation, str):
        raise ValueError(f"fact trong bản đồ sai hình dạng: {data!r}")
    if not isinstance(target, str) or not isinstance(canonical_key, str):
        raise ValueError(f"fact trong bản đồ sai hình dạng: {data!r}")
    return Fact(
        canonical_key=canonical_key,
        template=template,
        activation=activation,
        target=target,
        status=FactStatus(status),
        scope=FactScope(scope),
        tenant_id=tenant_id,
    )


def _metrics_from_dict(data: dict[str, object]) -> MetricsWithCI:
    """Bốn chỉ số trong bản đồ thành `MetricsWithCI` (để đối chiếu)."""

    def one(name: str) -> MetricCI:
        item = data[name]
        if not isinstance(item, dict):
            raise ValueError(f"chỉ số {name} trong bản đồ sai hình dạng")
        value = item["value"]
        lower = item["lower"]
        upper = item["upper"]
        if not isinstance(value, (int, float)):
            raise ValueError(f"chỉ số {name} trong bản đồ sai hình dạng")
        if not isinstance(lower, (int, float)) or not isinstance(upper, (int, float)):
            raise ValueError(f"chỉ số {name} trong bản đồ sai hình dạng")
        return MetricCI(float(value), float(lower), float(upper))

    return MetricsWithCI(
        precision=one("precision"),
        recall=one("recall"),
        violation_rate=one("violation_rate"),
        negative_transfer=one("negative_transfer"),
    )


def _metrics_match(left: MetricsWithCI, right: MetricsWithCI) -> str | None:
    """Hai bộ bốn chỉ số có khớp nhau không (trả tên chỉ số lệch, None nếu khớp)."""
    for name in ("precision", "recall", "violation_rate", "negative_transfer"):
        a = getattr(left, name)
        b = getattr(right, name)
        for field in ("value", "lower", "upper"):
            if not math.isclose(
                getattr(a, field), getattr(b, field), rel_tol=0.0, abs_tol=METRIC_TOLERANCE
            ):
                return name
    return None


def _format_metric(value: float, lower: float, upper: float) -> str:
    """Một chỉ số thành `giá trị [cận dưới, cận trên]` (đúng hình dạng 10.2)."""
    return f"{value:.3f} [{lower:.3f}, {upper:.3f}]"


def _entry_int(entry: dict[str, object], name: str) -> int:
    """Đọc một trường số nguyên của mục bản đồ (sai hình dạng thì lỗi rõ)."""
    value = entry[name]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"mục bản đồ sai hình dạng: {name} = {value!r}")
    return value


def _entry_str(entry: dict[str, object], name: str) -> str:
    """Đọc một trường chuỗi của mục bản đồ (sai hình dạng thì lỗi rõ)."""
    value = entry[name]
    if not isinstance(value, str):
        raise ValueError(f"mục bản đồ sai hình dạng: {name} = {value!r}")
    return value


def _entry_float(entry: dict[str, object], name: str) -> float:
    """Đọc một trường số thực của mục bản đồ (sai hình dạng thì lỗi rõ)."""
    value = entry[name]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"mục bản đồ sai hình dạng: {name} = {value!r}")
    return float(value)


def cross_check_runs(*, entries: Sequence[dict[str, object]], database_url: str) -> list[str]:
    """Đối chiếu hai chiều bản đồ <-> hàng `run` trong DB.

    (a) Không hai mục bản đồ nào chung một `run_id`; (b) mọi mục có
    `run_id` đều có hàng `run` tương ứng trong DB với đủ 11 trường khớp
    (trừ `wall_time` cho dung sai float nhỏ). Trả danh sách lỗi (rỗng
    thì khớp). Giới hạn: hàng `run` trong DB không mang nhãn task nên
    không liệt kê được "run 11.2 nào thiếu mục bản đồ" — chiều ngược
    chỉ kiểm được qua (a) + (b).
    """
    errors: list[str] = []
    seen: set[str] = set()
    with psycopg.connect(database_url) as conn:
        for entry in entries:
            run_id = entry.get("run_id")
            if run_id is None:
                continue
            if not isinstance(run_id, str):
                errors.append(f"mục {entry.get('condition')}: run_id sai dạng")
                continue
            if run_id in seen:
                errors.append(f"run_id {run_id} xuất hiện hai lần trong bản đồ")
                continue
            seen.add(run_id)
            row = conn.execute(
                "SELECT tenant_id, seed, model_id, model_revision, code_commit, "
                "config_hash, data_hash, tokens_in, tokens_out, wall_time, status "
                "FROM run WHERE id = %s",
                (run_id,),
            ).fetchone()
            if row is None:
                errors.append(
                    f"run_id {run_id} ({entry.get('condition')}/"
                    f"{entry.get('tenant_id')}): không có hàng run trong DB"
                )
                continue
            for column, value in zip(RUN_COLUMNS, row, strict=True):
                if column == "wall_time":
                    expected = _entry_float(entry, column)
                    if not math.isclose(float(value), expected, rel_tol=0.0, abs_tol=1e-9):
                        errors.append(
                            f"run_id {run_id}: {column} DB={value} != bản đồ={expected}"
                        )
                    continue
                expected_raw = entry.get(column)
                if value != expected_raw:
                    errors.append(
                        f"run_id {run_id}: {column} DB={value!r} != bản đồ={expected_raw!r}"
                    )
    return errors


def recompute_metrics(
    *,
    entries: Sequence[dict[str, object]],
    round_data: dict[str, TenantRoundData],
) -> list[str]:
    """Tính lại bốn chỉ số từ tập fact đo trong bản đồ + dữ liệu gốc.

    Dùng đúng hàm 10.2 (`metrics_with_ci`) với đáp án + trace đo của
    tenant và `n_draws`/`seed`/`condition` đã ghi trong mục. Trả danh
    sách lỗi (rỗng thì khớp).
    """
    errors: list[str] = []
    for entry in entries:
        condition = _entry_str(entry, "condition")
        tenant_id = _entry_str(entry, "tenant_id")
        source = _entry_str(entry, "source")
        key = f"{source}:{tenant_id}"
        tenant = round_data.get(key)
        if tenant is None:
            errors.append(f"{key}: không có dữ liệu tenant để tính lại")
            continue
        measured_raw = entry.get("measured_facts")
        if not isinstance(measured_raw, list):
            errors.append(f"{key}/{condition}: measured_facts sai hình dạng")
            continue
        facts = [_fact_from_dict(item) for item in measured_raw]
        ground_truth: GroundTruth = tenant.tenant_data.ground_truth
        recomputed = metrics_with_ci(
            facts,
            ground_truth.reference,
            tenant.tenant_data.measure_traces,
            tenant_id,
            n_draws=_entry_int(entry, "n_draws"),
            seed=_entry_int(entry, "seed"),
            condition=condition,
        )
        stored_raw = entry.get("metrics")
        if not isinstance(stored_raw, dict):
            errors.append(f"{key}/{condition}: metrics sai hình dạng")
            continue
        stored = _metrics_from_dict(stored_raw)
        mismatch = _metrics_match(recomputed, stored)
        if mismatch is not None:
            errors.append(f"{key}/{condition}: chỉ số {mismatch} tính lại không khớp bản đồ")
    return errors


def format_report(entries: Sequence[dict[str, object]]) -> str:
    """Báo cáo bảy điều kiện theo đúng hình dạng 10.2 + giờ + bảng trần."""
    lines = [
        "Báo cáo bảy điều kiện thí nghiệm (task 11.2)",
        "Ngưỡng khám phá và đáp án: support=0.5, confidence=0.5 (cố định, "
        "dùng chung mọi điều kiện); ngưỡng vi phạm: quá 10% trace đo",
        "",
    ]
    for entry in entries:
        metrics = entry["metrics"]
        if not isinstance(metrics, dict):
            raise ValueError("mục bản đồ sai hình dạng: metrics")
        precision = metrics["precision"]
        recall = metrics["recall"]
        violation = metrics["violation_rate"]
        transfer = metrics["negative_transfer"]
        if not isinstance(precision, dict) or not isinstance(recall, dict):
            raise ValueError("mục bản đồ sai hình dạng: metrics")
        if not isinstance(violation, dict) or not isinstance(transfer, dict):
            raise ValueError("mục bản đồ sai hình dạng: metrics")
        measured_raw = entry.get("measured_facts")
        n_measured = len(measured_raw) if isinstance(measured_raw, list) else 0
        lines.append(
            f"Tenant {entry['tenant_id']} — {entry['condition']} "
            f"({entry['source']}; học {_entry_int(entry, 'n_train')} trace, "
            f"đo {_entry_int(entry, 'n_measure')} trace; "
            f"{n_measured} fact đo)"
        )
        lines.append(
            "  precision:        "
            + _format_metric(
                float(precision["value"]),
                float(precision["lower"]),
                float(precision["upper"]),
            )
        )
        lines.append(
            "  recall:           "
            + _format_metric(
                float(recall["value"]), float(recall["lower"]), float(recall["upper"])
            )
        )
        lines.append(
            "  tỉ lệ vi phạm:    "
            + _format_metric(
                float(violation["value"]),
                float(violation["lower"]),
                float(violation["upper"]),
            )
        )
        lines.append(
            "  negative transfer: "
            + _format_metric(
                float(transfer["value"]),
                float(transfer["lower"]),
                float(transfer["upper"]),
            )
        )
    lines.append("")
    lines.append("Giờ chạy mỗi điều kiện:")
    hours: dict[str, float] = {}
    for entry in entries:
        condition = _entry_str(entry, "condition")
        hours[condition] = hours.get(condition, 0.0) + _entry_float(entry, "wall_time")
    for condition in CONDITIONS:
        if condition in hours:
            lines.append(f"  {condition}: {hours[condition] / 3600.0:.2f} giờ")
    lines.append("")
    lines.append("Đã dùng / trần token mỗi vòng:")
    for entry in entries:
        used = _entry_int(entry, "tokens_in") + _entry_int(entry, "tokens_out")
        ceiling = _entry_int(entry, "token_budget_total")
        lines.append(
            f"  {entry['tenant_id']} — {entry['condition']} "
            f"({entry['source']}): {used}/{ceiling} "
            f"({entry['status']})"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Lệnh báo cáo 11.2: `python -m tools.kaggle.report_11_2`.

    Mã thoát: 0 = đối chiếu khớp, báo cáo in xong; 1 = lỗi dữ liệu hay
    đối chiếu không khớp.
    """
    parser = argparse.ArgumentParser(
        prog="tools.kaggle.report_11_2",
        description="Báo cáo bảy điều kiện thí nghiệm (task 11.2).",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(DEFAULT_MANIFEST_NAME),
        help="tệp bản đồ vòng→điều kiện (mặc định: 11.2-manifest.json)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="tệp TOML cấu hình (lấy database_url để đọc hàng run)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="thư mục cache chứa 5 tệp BPIC15_N.xes",
    )
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.config)
    except (OSError, ValueError) as exc:
        print(f"không nạp được cấu hình: {exc}", file=sys.stderr)
        return 1
    try:
        manifest = load_manifest(args.manifest)
    except (OSError, ValueError) as exc:
        print(f"không nạp được bản đồ: {exc}", file=sys.stderr)
        return 1
    entries = manifest["entries"]
    if not entries:
        print("bản đồ rỗng: chưa có vòng nào", file=sys.stderr)
        return 1
    seeds = {_entry_int(entry, "seed") for entry in entries}
    if len(seeds) != 1:
        print(f"bản đồ có nhiều seed khác nhau: {sorted(seeds)}", file=sys.stderr)
        return 1
    seed = seeds.pop()
    sources = {_entry_str(entry, "source") for entry in entries}
    try:
        round_data: dict[str, TenantRoundData] = {}
        if SYNTHETIC_SOURCE in sources:
            for item in load_synthetic_round_data(seed=seed):
                round_data[f"{SYNTHETIC_SOURCE}:{item.tenant_id}"] = item
        if BPIC_SOURCE in sources:
            for item in load_bpic_round_data(cache_dir=args.cache_dir):
                round_data[f"{BPIC_SOURCE}:{item.tenant_id}"] = item
    except (FileNotFoundError, ValueError) as exc:
        print(f"lỗi dữ liệu: {exc}", file=sys.stderr)
        return 1
    errors = cross_check_runs(entries=entries, database_url=settings.database_url)
    errors.extend(recompute_metrics(entries=entries, round_data=round_data))
    if errors:
        for error in errors:
            print(f"KHÔNG KHỚP: {error}", file=sys.stderr)
        return 1
    print(format_report(entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
