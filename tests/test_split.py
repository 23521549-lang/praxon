"""Chia log theo thời điểm bắt đầu case + data_hash (task 3.3, plan con 3)."""

from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from praxon_core.datasets.split import (
    SplitFractions,
    compute_data_hash,
    main,
    split_case_starts,
    split_log,
)

FIXTURE = Path(__file__).parent / "fixtures" / "tiny.xes"


def _day(number: int) -> datetime:
    return datetime(2024, 1, number, tzinfo=UTC)


def test_split_case_starts_counts_ordering_disjoint():
    items = [(f"c{number}", _day(number)) for number in range(1, 11)]
    assignment = split_case_starts(items, SplitFractions())
    assert assignment.train == ("c1", "c2", "c3", "c4", "c5", "c6")
    assert assignment.calibration == ("c7", "c8")
    assert assignment.test == ("c9", "c10")
    all_cases = set(assignment.train) | set(assignment.calibration) | set(assignment.test)
    assert all_cases == {f"c{number}" for number in range(1, 11)}
    assert assignment.train_max_start is not None
    assert assignment.test_min_start is not None
    assert assignment.train_max_start < assignment.test_min_start


def test_split_case_starts_tie_at_boundary_moves_cut():
    items = [
        ("c1", _day(1)),
        ("c2", _day(2)),
        ("c3", _day(3)),
        ("c4", _day(4)),
        ("c5", _day(5)),
        ("c6", _day(5)),
        ("c7", _day(5)),
        ("c8", _day(8)),
        ("c9", _day(9)),
        ("c10", _day(10)),
    ]
    assignment = split_case_starts(items, SplitFractions())
    # Ranh giới 60% (chỉ số 6) rơi giữa nhóm cùng mốc Jan 5 — ranh giới
    # dời tới cuối nhóm, cả ba case Jan 5 ở lại phần học.
    assert assignment.train == ("c1", "c2", "c3", "c4", "c5", "c6", "c7")
    assert assignment.calibration == ("c8",)
    assert assignment.test == ("c9", "c10")
    assert assignment.train_max_start is not None
    assert assignment.test_min_start is not None
    assert assignment.train_max_start < assignment.test_min_start
    assert assignment.train_max_start == _day(5)


def test_split_case_starts_no_start_goes_last():
    items = [("c1", _day(1)), ("c2", _day(2)), ("c3", None)]
    assignment = split_case_starts(items, SplitFractions())
    assert assignment.train == ("c1",)
    assert assignment.calibration == ("c2",)
    assert assignment.test == ("c3",)
    assert assignment.train_max_start == _day(1)


def test_split_fractions_rejects_bad_values():
    with pytest.raises(ValueError):
        SplitFractions(train=0.5, calibration=0.2, test=0.2)
    with pytest.raises(ValueError):
        SplitFractions(train=0.0, calibration=0.5, test=0.5)
    with pytest.raises(ValueError):
        SplitFractions(train=0.6, calibration=0.2, test=1.0)


def test_compute_data_hash_stable_and_sensitive():
    base = compute_data_hash(log_hashes=("a" * 64,), fractions=SplitFractions(), tenants=(1,))
    assert len(base) == 64
    assert all(character in "0123456789abcdef" for character in base)
    assert (
        compute_data_hash(log_hashes=("a" * 64,), fractions=SplitFractions(), tenants=(1,))
        == base
    )
    assert (
        compute_data_hash(
            log_hashes=("a" * 64,),
            fractions=SplitFractions(train=0.5, calibration=0.2, test=0.3),
            tenants=(1,),
        )
        != base
    )
    assert (
        compute_data_hash(log_hashes=("b" * 64,), fractions=SplitFractions(), tenants=(1,))
        != base
    )
    assert (
        compute_data_hash(log_hashes=("a" * 64,), fractions=SplitFractions(), tenants=(2,))
        != base
    )


def test_split_log_tiny_fixture():
    split = split_log(FIXTURE, 1)
    assert split.municipality == 1
    assert split.train == ("case-1",)
    assert split.calibration == ()
    assert split.test == ("case-2",)
    assert split.train_max_start is not None
    assert split.train_max_start.strftime("%Y-%m-%d") == "2024-01-15"
    assert split.test_min_start is not None
    assert split.test_min_start.strftime("%Y-%m-%d") == "2024-02-20"
    assert split.file_sha256 == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert len(split.data_hash) == 64


def test_main_missing_file_returns_1(tmp_path):
    assert main(["--cache-dir", str(tmp_path), "--dataset", "m1"]) == 1


def test_main_invalid_fractions_returns_2(tmp_path):
    assert (
        main(
            [
                "--cache-dir",
                str(tmp_path),
                "--dataset",
                "m1",
                "--train-fraction",
                "0.5",
                "--calibration-fraction",
                "0.2",
                "--test-fraction",
                "0.2",
            ]
        )
        == 2
    )


def test_main_fixture_returns_0_and_hash_changes_with_fractions(tmp_path, capsys):
    shutil.copy(FIXTURE, tmp_path / "BPIC15_1.xes")
    assert main(["--cache-dir", str(tmp_path), "--dataset", "m1"]) == 0
    first = capsys.readouterr().out
    assert "học 1, hiệu chỉnh 0, đo 1" in first
    assert "data_hash: " in first
    first_hash = first.split("data_hash: ")[1].splitlines()[0].strip()
    assert (
        main(
            [
                "--cache-dir",
                str(tmp_path),
                "--dataset",
                "m1",
                "--train-fraction",
                "0.5",
                "--test-fraction",
                "0.3",
            ]
        )
        == 0
    )
    second = capsys.readouterr().out
    second_hash = second.split("data_hash: ")[1].splitlines()[0].strip()
    assert second_hash != first_hash
