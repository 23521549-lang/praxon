"""Báo cáo khác biệt giữa năm đô thị (task 3.4).

Đọc từng log BPIC 2015, đếm mỗi hoạt động xuất hiện ở bao nhiêu case,
lọc hoạt động hiếm theo ngưỡng hỗ trợ x tin cậy (spec dòng 147),
rồi báo cáo mức khác biệt giữa năm đô thị: hợp/giao các tập hoạt động,
Jaccard từng cặp, và số hoạt động còn lại sau lọc.

Ngưỡng lọc KHÔNG hard-code: truyền qua tham số runtime
``--support`` / ``--confidence`` (mặc định 0.5 / 0.5). Spec không cho số
Declare cụ thể; 0.7 / 0.95 / 0.05 là của cổng Beta, không dùng ở đây.

Nếu log hỏng (XML không đọc được) hoặc thiếu trường bắt buộc
(``concept:name`` của trace hoặc event), lệnh dừng ngay và trả mã
lỗi — theo task row 3.4 ("nếu log hỏng hoặc thiếu trường thì dừng
và quay về spec").
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from praxon_core.datasets.bpic2015 import (
    BPIC2015_DATASETS,
    DEFAULT_CACHE_DIR,
    BPIC2015Dataset,
)
from praxon_core.datasets.xes import iter_traces


@dataclass(frozen=True)
class ActivityCounts:
    """Số case mỗi hoạt động xuất hiện, kèm vấn đề về trường bắt buộc."""

    n_cases: int
    n_events: int
    case_counts: Counter[str]
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MunicipalityReport:
    """Một đô thị trong báo cáo khác biệt."""

    municipality: int
    n_cases: int
    n_events: int
    activities: frozenset[str]
    remaining: frozenset[str]
    removed: dict[str, float]


@dataclass(frozen=True)
class DifferenceReport:
    """Báo cáo khác biệt giữa các đô thị."""

    municipalities: tuple[MunicipalityReport, ...]
    union: frozenset[str]
    common: frozenset[str]
    pairwise_jaccard: dict[tuple[int, int], float]
    support: float
    confidence: float


def count_activity_cases(path: Path) -> ActivityCounts:
    """Đếm mỗi hoạt động xuất hiện ở bao nhiêu case.

    Đọc streaming qua ``iter_traces``. Một hoạt động chỉ đếm một lần
    cho mỗi case (kể cả khi nó lặp lại nhiều lần trong case đó).
    Phát hiện trường bắt buộc thiếu: trace không có ``concept:name``
    (case_id rỗng) hoặc event không có ``concept:name`` (activity
    rỗng); các vấn đề được ghi vào ``problems``, không ném ngoại lệ
    để lệnh chính quyết định dừng hay không.
    """
    counts: Counter[str] = Counter()
    problems: list[str] = []
    n_cases = 0
    n_events = 0
    for index, trace in enumerate(iter_traces(path), start=1):
        n_cases += 1
        if not trace.case_id:
            problems.append(f"trace #{index} thiếu concept:name (case_id rỗng)")
        seen: set[str] = set()
        for event in trace.events:
            n_events += 1
            if not event.activity:
                problems.append(
                    f"trace #{index} (case_id={trace.case_id!r}) có event thiếu concept:name"
                )
            else:
                seen.add(event.activity)
        for activity in seen:
            counts[activity] += 1
    return ActivityCounts(
        n_cases=n_cases,
        n_events=n_events,
        case_counts=counts,
        problems=problems,
    )


def validate_fractions(support: float, confidence: float) -> None:
    """Kiểm tra ngưỡng lọc nằm trong (0, 1]."""
    if not 0.0 < support <= 1.0:
        raise ValueError(f"support phải trong (0, 1], nhận {support}")
    if not 0.0 < confidence <= 1.0:
        raise ValueError(f"confidence phải trong (0, 1], nhận {confidence}")


def filter_activities(
    counts: Counter[str],
    n_cases: int,
    support: float,
    confidence: float,
) -> tuple[frozenset[str], dict[str, float]]:
    """Lọc hoạt động hiếm theo spec dòng 147.

    Một hoạt động còn lại khi tỉ lệ case chứa nó >= support x confidence.
    Trả về (tập hoạt động còn lại, dict hoạt động bị loại → tỉ lệ case
    chứa nó). Ngưỡng là tham số runtime, không hard-code.
    """
    validate_fractions(support, confidence)
    if n_cases <= 0:
        raise ValueError(f"n_cases phải > 0, nhận {n_cases}")
    threshold = support * confidence
    remaining: set[str] = set()
    removed: dict[str, float] = {}
    for activity, n in counts.items():
        fraction = n / n_cases
        if fraction >= threshold:
            remaining.add(activity)
        else:
            removed[activity] = fraction
    return frozenset(remaining), removed


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    """Jaccard giữa hai tập hoạt động (1.0 khi cả hai đều rỗng)."""
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / len(union)


def build_difference_report(
    per_municipality: dict[int, ActivityCounts],
    support: float,
    confidence: float,
) -> DifferenceReport:
    """Ghép báo cáo khác biệt từ số đếm từng đô thị."""
    reports: list[MunicipalityReport] = []
    sets: dict[int, frozenset[str]] = {}
    for municipality in sorted(per_municipality):
        counts = per_municipality[municipality]
        activities = frozenset(counts.case_counts)
        remaining, removed = filter_activities(
            counts.case_counts, counts.n_cases, support, confidence
        )
        reports.append(
            MunicipalityReport(
                municipality=municipality,
                n_cases=counts.n_cases,
                n_events=counts.n_events,
                activities=activities,
                remaining=remaining,
                removed=removed,
            )
        )
        sets[municipality] = activities
    union: frozenset[str] = frozenset().union(*sets.values()) if sets else frozenset()
    common: frozenset[str] = frozenset.intersection(*sets.values()) if sets else frozenset()
    pairwise: dict[tuple[int, int], float] = {}
    municipalities = sorted(sets)
    for i, first in enumerate(municipalities):
        for second in municipalities[i + 1 :]:
            pairwise[(first, second)] = jaccard(sets[first], sets[second])
    return DifferenceReport(
        municipalities=tuple(reports),
        union=union,
        common=common,
        pairwise_jaccard=pairwise,
        support=support,
        confidence=confidence,
    )


def format_difference_report(report: DifferenceReport) -> str:
    """Trình bày báo cáo khác biệt thành văn bản."""
    lines: list[str] = []
    lines.append(
        "Báo cáo khác biệt giữa năm đô thị "
        f"(lọc: support={report.support:g}, confidence={report.confidence:g}, "
        f"ngưỡng={report.support * report.confidence:g})"
    )
    lines.append("")
    lines.append("Số hoạt động (trước lọc / sau lọc):")
    for item in report.municipalities:
        lines.append(
            f"  Đô thị {item.municipality}: {item.n_cases} case, "
            f"{item.n_events} sự kiện, "
            f"{len(item.activities)} hoạt động → còn {len(item.remaining)} "
            f"(loại {len(item.removed)})"
        )
    lines.append("")
    lines.append(
        f"Hợp năm đô thị: {len(report.union)} hoạt động; "
        f"chung cả năm: {len(report.common)} hoạt động"
    )
    only: list[str] = []
    for item in report.municipalities:
        others = set()
        for other in report.municipalities:
            if other.municipality != item.municipality:
                others |= set(other.activities)
        unique = set(item.activities) - others
        only.append(f"đô thị {item.municipality}: {len(unique)}")
    lines.append("Hoạt động chỉ có ở một đô thị: " + "; ".join(only))
    lines.append("")
    lines.append("Jaccard từng cặp (tập hoạt động):")
    for (first, second), value in sorted(report.pairwise_jaccard.items()):
        lines.append(f"  {first}-{second}: {value:.3f}")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="praxon_core.datasets.difference",
        description="Báo cáo khác biệt giữa năm đô thị BPIC 2015 (task 3.4).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Thư mục cache chứa 5 tệp BPIC15_N.xes.",
    )
    parser.add_argument(
        "--dataset",
        choices=[d.slug for d in BPIC2015_DATASETS],
        help="Chỉ báo cáo một đô thị (mặc định: cả năm).",
    )
    parser.add_argument(
        "--support",
        type=float,
        default=0.5,
        help="Ngưỡng hỗ trợ cho lọc hoạt động (mặc định 0.5).",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.5,
        help="Ngưỡng tin cậy cho lọc hoạt động (mặc định 0.5).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Chạy báo cáo khác biệt.

    Mã thoát: 0 = xong; 1 = log hỏng (không đọc được XML) hoặc thiếu
    tệp; 2 = log thiếu trường bắt buộc; 3 = tham số lọc không hợp lệ.
    """
    args = _parse_args(argv)
    try:
        validate_fractions(args.support, args.confidence)
    except ValueError as exc:
        print(f"tham số lọc không hợp lệ: {exc}", file=sys.stderr)
        return 3
    datasets: list[BPIC2015Dataset] = [
        d for d in BPIC2015_DATASETS if args.dataset is None or d.slug == args.dataset
    ]
    per_municipality: dict[int, ActivityCounts] = {}
    for dataset in datasets:
        path = args.cache_dir / dataset.xes_filename
        if not path.exists():
            print(f"thiếu tệp: {path}", file=sys.stderr)
            return 1
        try:
            counts = count_activity_cases(path)
        except ET.ParseError as exc:
            print(f"log hỏng (không đọc được XML): {path}: {exc}", file=sys.stderr)
            return 1
        if counts.problems:
            for problem in counts.problems:
                print(f"{path}: {problem}", file=sys.stderr)
            print(
                "dừng: log thiếu trường bắt buộc, quay về spec",
                file=sys.stderr,
            )
            return 2
        per_municipality[dataset.municipality] = counts
    try:
        report = build_difference_report(per_municipality, args.support, args.confidence)
    except ValueError as exc:
        print(f"tham số lọc không hợp lệ: {exc}", file=sys.stderr)
        return 3
    print(format_difference_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
