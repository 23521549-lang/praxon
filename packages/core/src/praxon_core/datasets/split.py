"""Chia log BPIC 2015 theo thời điểm bắt đầu case, 60/20/20 (task 3.3, plan con 3).

Mỗi đô thị chia theo thời điểm bắt đầu case: 60% học, 20% hiệu chỉnh,
20% đo (spec dòng 152). Chia ngẫu nhiên thì tương lai lọt vào tập học.
`data_hash` băm tệp log, tham số chia, danh sách tenant (spec dòng 191).

Lệnh: `python -m praxon_core.datasets.split` in số case mỗi phần +
`data_hash` cho cả năm đô thị từ cache; `--dataset m1` chỉ chia một đô thị.
Tham số chia là tham số lúc chạy (`--train-fraction` / `--calibration-fraction` /
`--test-fraction`, mặc định theo spec 0.6/0.2/0.2) — đổi tham số chia thì
`data_hash` đổi.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from praxon_core.datasets.bpic2015 import BPIC2015_DATASETS, DEFAULT_CACHE_DIR
from praxon_core.datasets.xes import iter_traces

# Tỉ lệ chia theo spec dòng 152 (60% học, 20% hiệu chỉnh, 20% đo).
# Đây là mặc định, không phải số bị khóa trong code: tham số chia truyền
# được vào hàm và lệnh, và `data_hash` băm cả tham số chia.
DEFAULT_TRAIN_FRACTION = 0.6
DEFAULT_CALIBRATION_FRACTION = 0.2
DEFAULT_TEST_FRACTION = 0.2

# Mốc thay cho case không có thời điểm bắt đầu khi sắp xếp. Case không có
# start không đặt được vào dòng thời gian nên xếp cuối (coi là mới nhất) —
# không lọt vào phần học.
_MIN_START = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True)
class SplitFractions:
    """Tham số chia: tỉ lệ học / hiệu chỉnh / đo; tổng phải bằng 1."""

    train: float = DEFAULT_TRAIN_FRACTION
    calibration: float = DEFAULT_CALIBRATION_FRACTION
    test: float = DEFAULT_TEST_FRACTION

    def __post_init__(self) -> None:
        """Kiểm tỉ lệ: mỗi tỉ lệ trong (0, 1) và tổng bằng 1."""
        for name, value in (
            ("train", self.train),
            ("calibration", self.calibration),
            ("test", self.test),
        ):
            if not 0.0 < value < 1.0:
                raise ValueError(f"tỉ lệ {name} phải trong (0, 1), nhận {value}")
        if abs(self.train + self.calibration + self.test - 1.0) > 1e-9:
            raise ValueError(
                f"tổng ba tỉ lệ phải bằng 1, nhận {self.train + self.calibration + self.test}"
            )


@dataclass(frozen=True)
class SplitAssignment:
    """Kết quả chia: case id từng phần + ranh giới thời gian.

    `train_max_start` là thời điểm bắt đầu muộn nhất ở phần học (None khi
    phần học rỗng hoặc toàn case không có start); `test_min_start` là thời
    điểm bắt đầu sớm nhất ở phần đo (None khi phần đo rỗng). Khi cả hai
    đều có thì `train_max_start < test_min_start` — mọi case ở phần học
    bắt đầu trước mọi case ở phần đo (cổng ra của task row 3.3).
    """

    train: tuple[str, ...]
    calibration: tuple[str, ...]
    test: tuple[str, ...]
    train_max_start: datetime | None
    test_min_start: datetime | None


def _aware(value: datetime | None) -> datetime:
    """Chuẩn hóa một thời điểm về dạng có múi giờ (naive coi là UTC)."""
    if value is None:
        return _MIN_START
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _sort_key(item: tuple[str, datetime | None]) -> tuple[bool, datetime, str]:
    """Khóa sắp xếp: theo thời điểm bắt đầu, case không có start xếp cuối."""
    case_id, start = item
    return (start is None, _aware(start), case_id)


def _adjust_cut(ordered: list[tuple[str, datetime | None]], index: int, lower: int) -> int:
    """Dời ranh giới cắt tới cuối nhóm cùng mốc thời gian.

    Nếu mốc thời gian tại ranh giới trùng với mốc của case ngay trước nó
    thì ranh giới dời tới hết nhóm cùng mốc đó — không mốc nào nằm vắt qua
    ranh giới, để mọi case ở phần trước bắt đầu trước mọi case ở phần sau.
    """
    total = len(ordered)
    while lower < index < total:
        current = _aware(ordered[index][1])
        previous = _aware(ordered[index - 1][1])
        if ordered[index][1] is not None and current == previous:
            index += 1
        else:
            break
    return index


def split_case_starts(
    items: Sequence[tuple[str, datetime | None]], fractions: SplitFractions
) -> SplitAssignment:
    """Chia (case_id, start) theo thời điểm bắt đầu case.

    Sắp xếp theo thời điểm bắt đầu (case không có start xếp cuối), cắt
    theo số lượng (floor tích lũy: học lấy `int(n * train)`, hiệu chỉnh
    lấy tới `int(n * (train + calibration))`, đo lấy phần còn lại), rồi
    dời ranh giới qua nhóm cùng mốc thời gian nếu cần (xem `_adjust_cut`).
    """
    ordered = sorted(items, key=_sort_key)
    total = len(ordered)
    cut_train = _adjust_cut(ordered, int(total * fractions.train), 0)
    cut_calibration = _adjust_cut(
        ordered, int(total * (fractions.train + fractions.calibration)), cut_train
    )
    train = tuple(case_id for case_id, _ in ordered[:cut_train])
    calibration = tuple(case_id for case_id, _ in ordered[cut_train:cut_calibration])
    test = tuple(case_id for case_id, _ in ordered[cut_calibration:])
    train_max_start = ordered[cut_train - 1][1] if cut_train > 0 else None
    test_min_start = ordered[cut_calibration][1] if cut_calibration < total else None
    return SplitAssignment(
        train=train,
        calibration=calibration,
        test=test,
        train_max_start=train_max_start,
        test_min_start=test_min_start,
    )


def _file_sha256(path: Path) -> str:
    """SHA-256 của một tệp (đọc theo khối, không nạp cả tệp)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_data_hash(
    *,
    log_hashes: tuple[str, ...],
    fractions: SplitFractions,
    tenants: tuple[int, ...],
) -> str:
    """`data_hash`: băm tệp log + tham số chia + danh sách tenant (spec dòng 191).

    Đầu vào chuẩn hóa thành JSON (băm log sắp xếp, tỉ lệ dạng repr, tenant
    sắp xếp, khóa sắp xếp) rồi băm SHA-256 — cùng đầu vào ra cùng băm, đổi
    một tham số (tệp log, tỉ lệ chia, danh sách tenant) thì băm đổi.
    """
    payload = {
        "log_hashes": sorted(log_hashes),
        "train_fraction": repr(fractions.train),
        "calibration_fraction": repr(fractions.calibration),
        "test_fraction": repr(fractions.test),
        "tenants": sorted(tenants),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LogSplit:
    """Kết quả chia một log: case id từng phần + băm."""

    municipality: int
    train: tuple[str, ...]
    calibration: tuple[str, ...]
    test: tuple[str, ...]
    train_max_start: datetime | None
    test_min_start: datetime | None
    file_sha256: str
    data_hash: str


def split_log(
    path: Path, municipality: int, fractions: SplitFractions | None = None
) -> LogSplit:
    """Chia một tệp XES theo thời điểm bắt đầu case (streaming)."""
    split_fractions = fractions if fractions is not None else SplitFractions()
    items = [(trace.case_id, trace.start) for trace in iter_traces(path)]
    assignment = split_case_starts(items, split_fractions)
    file_hash = _file_sha256(path)
    return LogSplit(
        municipality=municipality,
        train=assignment.train,
        calibration=assignment.calibration,
        test=assignment.test,
        train_max_start=assignment.train_max_start,
        test_min_start=assignment.test_min_start,
        file_sha256=file_hash,
        data_hash=compute_data_hash(
            log_hashes=(file_hash,),
            fractions=split_fractions,
            tenants=(municipality,),
        ),
    )


def _format_datetime(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d") if value is not None else "-"


def format_split(split: LogSplit) -> str:
    """Một đô thị thành một khối văn bản (số case mỗi phần + băm)."""
    lines = [
        f"Đô thị {split.municipality}: "
        f"{len(split.train) + len(split.calibration) + len(split.test)} case → "
        f"học {len(split.train)}, hiệu chỉnh {len(split.calibration)}, "
        f"đo {len(split.test)}",
        f"  ranh giới: học tới {_format_datetime(split.train_max_start)}, "
        f"đo từ {_format_datetime(split.test_min_start)}",
        f"  tệp sha256: {split.file_sha256}",
        f"  data_hash: {split.data_hash}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Lệnh chia log: `python -m praxon_core.datasets.split`."""
    parser = argparse.ArgumentParser(
        prog="praxon_core.datasets.split",
        description="Chia log BPIC 2015 theo thời điểm bắt đầu case (60/20/20).",
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
        help="chỉ chia một đô thị (mặc định: cả năm)",
    )
    parser.add_argument(
        "--train-fraction",
        type=float,
        default=DEFAULT_TRAIN_FRACTION,
        help="tỉ lệ phần học (mặc định: %(default)s)",
    )
    parser.add_argument(
        "--calibration-fraction",
        type=float,
        default=DEFAULT_CALIBRATION_FRACTION,
        help="tỉ lệ phần hiệu chỉnh (mặc định: %(default)s)",
    )
    parser.add_argument(
        "--test-fraction",
        type=float,
        default=DEFAULT_TEST_FRACTION,
        help="tỉ lệ phần đo (mặc định: %(default)s)",
    )
    args = parser.parse_args(argv)
    try:
        fractions = SplitFractions(
            train=args.train_fraction,
            calibration=args.calibration_fraction,
            test=args.test_fraction,
        )
    except ValueError as error:
        print(f"tham số chia không hợp lệ: {error}", file=sys.stderr)
        return 2
    datasets = [
        dataset
        for dataset in BPIC2015_DATASETS
        if args.dataset is None or dataset.slug == args.dataset
    ]
    file_hashes: list[str] = []
    municipalities: list[int] = []
    for dataset in datasets:
        path = args.cache_dir / dataset.xes_filename
        if not path.is_file():
            print(f"{dataset.slug}: thiếu tệp {path}", file=sys.stderr)
            return 1
        split = split_log(path, dataset.municipality, fractions)
        print(format_split(split))
        file_hashes.append(split.file_sha256)
        municipalities.append(dataset.municipality)
    if len(datasets) == len(BPIC2015_DATASETS):
        combined = compute_data_hash(
            log_hashes=tuple(file_hashes),
            fractions=fractions,
            tenants=tuple(municipalities),
        )
        print(f"data_hash chung (cả năm đô thị): {combined}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
