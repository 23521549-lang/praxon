"""Test tích hợp cho bộ điều phối một lệnh (task 13.1).

Chạy `run_phase1` thật (chế độ smoke) trên DB test thật: áp migration,
nạp cấu hình khóa, sinh bộ chuẩn, driver BPIC giả, ghi JSON. Không gọi
model, không cần Docker/B2: dữ liệu BPIC là 5 file stub (chỉ để tính
băm — băm nửa BPIC thật đã kiểm ở test đơn vị), Wabo bỏ qua ở smoke.

Chế độ smoke dùng driver giả; driver thật (12.2) thay vào khi có — xem
báo cáo cuối task. Phép thử máy trống full chưa chạy ở task này.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from praxon_core.datasets.bpic2015 import BPIC2015_DATASETS
from praxon_core.eval.ground_truth import BPIC_TEST_SPLIT_SOURCE
from praxon_core.eval.run_all import (
    _bpic_half_hash,
    _mock_bpic_runner,
    main,
    run_phase1,
)
from praxon_core.learning.coordinator import compute_config_hash
from praxon_core.learning.test_split_lock import load_locked_config
from praxon_core.settings import load_settings

ADMIN_DSN = os.environ.get(
    "PRAXON_TEST_DATABASE_URL", "postgresql://postgres@localhost:5432/praxon"
)
CODE_COMMIT = "test-commit-13-1"
SEED = 0


def _write_stub_bpic(cache_dir: Path) -> Path:
    """5 file XES stub (chỉ để tính băm, không phải dữ liệu thật)."""
    bpic_dir = cache_dir / "bpic2015"
    bpic_dir.mkdir(parents=True, exist_ok=True)
    for dataset in BPIC2015_DATASETS:
        (bpic_dir / dataset.xes_filename).write_bytes(f"stub-xes-{dataset.slug}".encode())
    return bpic_dir


def _write_locked_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, checkpoint_store: str = "local"
) -> tuple[Path, Path]:
    """TOML cấu hình + bản ghi khóa có hash đúng (tính sau khi đặt env).

    Env ghi đè mọi trường nên hash phải tính sau khi monkeypatch đặt xong
    — đúng cách `load_locked_config` tính khi chạy thật.
    """
    monkeypatch.setenv("PRAXON_DATABASE_URL", ADMIN_DSN)
    monkeypatch.setenv("PRAXON_CHECKPOINT_STORE", checkpoint_store)
    monkeypatch.setenv("PRAXON_TOKEN_BUDGET_TOTAL", "0")
    monkeypatch.delenv("PRAXON_S3_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("PRAXON_S3_SECRET_ACCESS_KEY", raising=False)
    config_path = tmp_path / "phan-do.toml"
    config_path.write_text(
        f'database_url = ""\ncheckpoint_store = "{checkpoint_store}"\ntoken_budget_total = 0\n',
        encoding="utf-8",
    )
    settings = load_settings(config_path)
    locked_hash = compute_config_hash(settings)
    lock_path = tmp_path / "phan-do.lock.toml"
    lock_path.write_text(
        f'locked_config_hash = "{locked_hash}"\nseed = {SEED}\n',
        encoding="utf-8",
    )
    # Khóa phải nạp được (đúng như `run_phase1` sẽ nạp).
    loaded, locked = load_locked_config(config_path, lock_path)
    assert locked == locked_hash
    assert loaded.checkpoint_store == checkpoint_store
    return config_path, lock_path


def _run_smoke(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    reference_path: Path | None = None,
    bpic_runner: Callable[[Path, Path, Path], int] | None = None,
    checkpoint_store: str = "local",
) -> tuple[int, dict[str, object] | None, Path, Path]:
    """Chạy `run_phase1` smoke; trả (mã thoát, báo cáo JSON, out_dir, bpic_dir)."""
    config_path, lock_path = _write_locked_config(
        tmp_path, monkeypatch, checkpoint_store=checkpoint_store
    )
    cache_dir = tmp_path / "cache"
    bpic_dir = _write_stub_bpic(cache_dir)
    out_dir = tmp_path / "out"
    reference = reference_path or tmp_path / "khong-co-tham-chieu.json"
    code = run_phase1(
        config_path=config_path,
        lock_path=lock_path,
        reference_path=reference,
        out_dir=out_dir,
        cache_dir=cache_dir,
        smoke=True,
        code_commit=CODE_COMMIT,
        bpic_runner=bpic_runner,
    )
    report_path = out_dir / "phase1-report.json"
    report = None
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    return code, report, out_dir, bpic_dir


def _matching_reference(report: dict[str, object], bpic_dir: Path) -> dict[str, object]:
    """Tham chiếu 12.2 khớp đúng lần chạy: hàng BPIC + metadata khớp.

    `data_hash` của tham chiếu là nửa BPIC đã gộp (12.2 A.4) — không phải
    băm đầy đủ hai nửa trong báo cáo lần chạy (`run_phase1` tự đổi về
    nửa BPIC trước khi so).
    """
    from praxon_core.learning.coordinator import merge_data_hash

    rows = report["rows"]
    assert isinstance(rows, list)
    bpic_rows = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("source") == BPIC_TEST_SPLIT_SOURCE
    ]
    return {
        "code_commit": report["code_commit"],
        "config_hash": report["config_hash"],
        "data_hash": merge_data_hash(bpic_hash=_bpic_half_hash(bpic_dir)),
        "seed": report["seed"],
        "model_id": report["model_id"],
        "model_revision": report["model_revision"],
        "cache_intact": True,
        "rows": bpic_rows,
    }


def test_smoke_exit_0_va_json_du_hang(pg, tmp_path, monkeypatch):
    code, report, _out_dir, _bpic_dir = _run_smoke(tmp_path, monkeypatch)
    assert code == 0
    assert report is not None
    assert report["code_commit"] == CODE_COMMIT
    assert report["seed"] == SEED
    rows = report["rows"]
    assert isinstance(rows, list)
    # 35 hàng BPIC giả + 35 hàng bộ chuẩn (7 điều kiện x 5 tenant giả).
    assert len(rows) == 70
    bpic_rows = [r for r in rows if r["source"] == BPIC_TEST_SPLIT_SOURCE]
    assert len(bpic_rows) == 35
    assert all(r["tenant_id"] in ("m1", "m2", "m3", "m4", "m5") for r in bpic_rows)


def test_tham_chieu_khop_thi_exit_0(pg, tmp_path, monkeypatch):
    _code, report, _out, bpic_dir = _run_smoke(tmp_path, monkeypatch)
    assert report is not None
    reference_path = tmp_path / "tham-chieu.json"
    reference_path.write_text(
        json.dumps(_matching_reference(report, bpic_dir), indent=2),
        encoding="utf-8",
    )
    code, _report2, _out2, _bpic2 = _run_smoke(
        tmp_path, monkeypatch, reference_path=reference_path
    )
    assert code == 0


def test_tham_chieu_lech_mot_chi_so_thi_exit_4(pg, tmp_path, monkeypatch):
    _code, report, _out, bpic_dir = _run_smoke(tmp_path, monkeypatch)
    assert report is not None
    reference = _matching_reference(report, bpic_dir)
    rows = reference["rows"]
    assert isinstance(rows, list) and rows
    first = dict(rows[0])
    metrics = dict(first["metrics"])
    precision = dict(metrics["precision"])
    precision["value"] = precision["value"] + 0.01
    metrics["precision"] = precision
    first["metrics"] = metrics
    rows[0] = first
    reference_path = tmp_path / "tham-chieu-lech.json"
    reference_path.write_text(json.dumps(reference, indent=2), encoding="utf-8")
    code, _report2, _out2, _bpic2 = _run_smoke(
        tmp_path, monkeypatch, reference_path=reference_path
    )
    assert code == 4


def test_khoa_lech_thi_exit_2(pg, tmp_path, monkeypatch):
    config_path, lock_path = _write_locked_config(tmp_path, monkeypatch)
    # Sửa TOML sau khi khóa: hash tính lại lệch khỏi bản ghi khóa.
    config_path.write_text(
        'database_url = ""\ncheckpoint_store = "local"\ntoken_budget_total = 0\n'
        "bootstrap_draws = 5\n",
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"
    _write_stub_bpic(cache_dir)
    code = run_phase1(
        config_path=config_path,
        lock_path=lock_path,
        reference_path=tmp_path / "khong-co.json",
        out_dir=tmp_path / "out",
        cache_dir=cache_dir,
        smoke=True,
        code_commit=CODE_COMMIT,
        bpic_runner=_mock_bpic_runner,
    )
    assert code == 2


def test_smoke_mien_kiem_key_b2_khi_khoa_bat_s3(pg, tmp_path, monkeypatch):
    # Khóa bắt "s3" nhưng smoke không chạm S3: miễn bước kiểm, chạy hết.
    code, report, _out, _bpic = _run_smoke(tmp_path, monkeypatch, checkpoint_store="s3")
    assert code == 0
    assert report is not None


def test_driver_tra_2_thi_exit_2(pg, tmp_path, monkeypatch):
    def _runner(_config: Path, _lock: Path, _report: Path) -> int:
        return 2

    code, report, _out, _bpic = _run_smoke(tmp_path, monkeypatch, bpic_runner=_runner)
    assert code == 2
    assert report is None


def test_driver_tra_3_thi_exit_3(pg, tmp_path, monkeypatch):
    def _runner(_config: Path, _lock: Path, _report: Path) -> int:
        return 3

    code, report, _out, _bpic = _run_smoke(tmp_path, monkeypatch, bpic_runner=_runner)
    assert code == 3
    assert report is None


# ---------------------------------------------------------------- cờ --compare của CLI


def test_main_compare_trung_thi_exit_0(tmp_path):
    report_path = tmp_path / "a.json"
    assert _mock_bpic_runner(tmp_path / "c.toml", tmp_path / "l.toml", report_path) == 0
    assert main(["--compare", str(report_path), str(report_path)]) == 0


def test_main_compare_lech_thi_exit_4(tmp_path):
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    assert _mock_bpic_runner(tmp_path / "c.toml", tmp_path / "l.toml", path_a) == 0
    assert _mock_bpic_runner(tmp_path / "c.toml", tmp_path / "l.toml", path_b) == 0
    report = json.loads(path_b.read_text(encoding="utf-8"))
    rows = report["rows"]
    first = dict(rows[0])
    metrics = dict(first["metrics"])
    precision = dict(metrics["precision"])
    precision["value"] = precision["value"] + 0.01
    metrics["precision"] = precision
    first["metrics"] = metrics
    rows[0] = first
    path_b.write_text(json.dumps(report, indent=2), encoding="utf-8")
    assert main(["--compare", str(path_a), str(path_b)]) == 4


def test_main_compare_thieu_file_thi_exit_2(tmp_path):
    assert main(["--compare", str(tmp_path / "a.json"), str(tmp_path / "b.json")]) == 2
