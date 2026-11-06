"""Bảng hồ sơ log BPIC 2015 (task 3.2, plan con 3).

Hồ sơ một đô thị: số case, số sự kiện, số loại hoạt động, phân phối
theo thời gian (case bắt đầu theo tháng), danh sách thuộc tính phân
loại có mặt (tên thuộc tính dạng chuỗi ở trace và event).

Lệnh: `python -m praxon_core.datasets.profile` in bảng cả năm đô thị
từ cache; `--dataset m1` chỉ in một đô thị. Số case phải khớp bài báo
số 1 của BPIC 2015: 1.199 / 832 / 1.409 / 1.053 / 1.156.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from praxon_core.datasets.bpic2015 import BPIC2015_DATASETS, DEFAULT_CACHE_DIR
from praxon_core.datasets.xes import iter_traces


@dataclass(frozen=True)
class LogProfile:
    """Hồ sơ một log: đếm và phân phối, không giữ toàn bộ trace."""

    municipality: int
    cases: int
    events: int
    activity_types: frozenset[str]
    start_min: datetime | None
    start_max: datetime | None
    cases_by_month: dict[str, int]
    trace_attributes: frozenset[str]
    event_attributes: frozenset[str]


def profile_log(path: Path, municipality: int) -> LogProfile:
    """Đọc một tệp XES bằng streaming, trả hồ sơ của nó."""
    cases = 0
    events = 0
    activity_types: set[str] = set()
    trace_attributes: set[str] = set()
    event_attributes: set[str] = set()
    start_min: datetime | None = None
    start_max: datetime | None = None
    cases_by_month: Counter[str] = Counter()
    for trace in iter_traces(path):
        cases += 1
        events += len(trace.events)
        trace_attributes.update(trace.attributes.keys())
        for event in trace.events:
            if event.activity:
                activity_types.add(event.activity)
            event_attributes.update(event.attributes.keys())
        if trace.start is not None:
            if start_min is None or trace.start < start_min:
                start_min = trace.start
            if start_max is None or trace.start > start_max:
                start_max = trace.start
            cases_by_month[trace.start.strftime("%Y-%m")] += 1
    return LogProfile(
        municipality=municipality,
        cases=cases,
        events=events,
        activity_types=frozenset(activity_types),
        start_min=start_min,
        start_max=start_max,
        cases_by_month=dict(sorted(cases_by_month.items())),
        trace_attributes=frozenset(trace_attributes),
        event_attributes=frozenset(event_attributes),
    )


def _format_datetime(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d") if value is not None else "-"


def format_profile(profile: LogProfile) -> str:
    """Một đô thị thành một khối văn bản (bảng hồ sơ)."""
    lines = [
        f"Đô thị {profile.municipality}: "
        f"{profile.cases} case, {profile.events} sự kiện, "
        f"{len(profile.activity_types)} loại hoạt động",
        f"  case bắt đầu: {_format_datetime(profile.start_min)} → "
        f"{_format_datetime(profile.start_max)}",
        "  case theo tháng: "
        + ", ".join(f"{month}={count}" for month, count in profile.cases_by_month.items()),
        "  thuộc tính trace: " + ", ".join(sorted(profile.trace_attributes)),
        "  thuộc tính event: " + ", ".join(sorted(profile.event_attributes)),
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Lệnh in bảng hồ sơ: `python -m praxon_core.datasets.profile`."""
    parser = argparse.ArgumentParser(
        prog="praxon_core.datasets.profile",
        description="In bảng hồ sơ log BPIC 2015 từ cache lúc chạy.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="thư mục cache ngoài kho (mặc định: %(default)s)",
    )
    parser.add_argument(
        "--dataset",
        choices=[dataset.slug for dataset in BPIC2015_DATASETS],
        help="chỉ in một đô thị (mặc định: cả năm)",
    )
    args = parser.parse_args(argv)
    datasets = [
        dataset
        for dataset in BPIC2015_DATASETS
        if args.dataset is None or dataset.slug == args.dataset
    ]
    for dataset in datasets:
        path = args.cache_dir / dataset.xes_filename
        if not path.is_file():
            print(f"{dataset.slug}: thiếu tệp {path}", file=sys.stderr)
            return 1
        profile = profile_log(path, dataset.municipality)
        print(format_profile(profile))
        if profile.cases != dataset.expected_cases:
            print(
                f"{dataset.slug}: số case {profile.cases} khác kỳ vọng "
                f"{dataset.expected_cases} (bài báo số 1 BPIC 2015)",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
