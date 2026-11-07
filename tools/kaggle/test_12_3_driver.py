"""Test driver chạy lại (task 12.3) trên dữ liệu giả + hàm chạy giả.

Không cần Kaggle/B2: pre-check tính đúng gap, lần chạy lại ghi đúng file
+ manifest, khóa lệch thì từ chối trước khi chạy ô nào, trường hợp khóa
từ chối ghi báo cáo verdict với `run_id` NULL.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from praxon_core.adapters.cache import ResponseCache
from praxon_core.adapters.language_model import CompletionResult
from praxon_core.learning.coordinator import compute_config_hash
from praxon_core.settings import Settings, load_settings
from tools.kaggle.driver_12_3 import (
    CellManifest,
    CellOutcome,
    CellRef,
    CountingCachedModel,
    LockRecord,
    UsageLog,
    load_lock_record,
    load_manifest,
    main,
    precheck,
    run_rerun,
    write_lock_refusal_report,
)

MODEL_ID = "Qwen/Qwen3-8B-GGUF"
MODEL_REVISION = "7c41481f57cb95916b40956ab2f0b139b296d974"
CODE_COMMIT = "a" * 40
DATA_HASH = "d" * 64
CACHE_ENTRIES = {"k1": "tra-loi-mot", "k2": "tra-loi-hai"}


def _settings() -> Settings:
    """Dựng Settings đo tối thiểu (mọi trường khác lấy mặc định)."""
    return Settings(database_url="")


def _lock_dict(*, locked_config_hash: str, code_commit: str = CODE_COMMIT) -> dict[str, Any]:
    """Bản ghi khóa khớp với Settings mặc định + hash đã cho."""
    return {
        "locked_config_hash": locked_config_hash,
        "lock_commit": CODE_COMMIT,
        "code_commit": code_commit,
        "seed": 0,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "data_hash": DATA_HASH,
        "cache": "empty",
        "locked_at": "2026-11-07",
        "locked_by": "test",
    }


def _run_dict(*, config_hash: str, status: str = "succeeded") -> dict[str, Any]:
    """Hàng `run` tham chiếu khớp bản ghi khóa."""
    return {
        "run_id": "run-tham-chieu",
        "seed": 0,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "code_commit": CODE_COMMIT,
        "config_hash": config_hash,
        "data_hash": DATA_HASH,
        "tokens_in": 300,
        "tokens_out": 150,
        "status": status,
    }


def _write_manifest(
    tmp_path: Path,
    *,
    config_hash: str,
    cache_entries: dict[str, str] | None = None,
    write_metrics: bool = True,
    status: str = "succeeded",
) -> tuple[Path, Path]:
    """Ghi một manifest một ô + file của nó; trả (đường dẫn manifest, thư mục)."""
    from tools.kaggle.driver_12_3 import cache_fingerprint

    side = tmp_path / "ref"
    side.mkdir(parents=True, exist_ok=True)
    if write_metrics:
        (side / "metrics.json").write_text(json.dumps({"metrics": {}}), encoding="utf-8")
    (side / "fact_keys.json").write_text(
        json.dumps({"fact_keys": ["a", "b"]}), encoding="utf-8"
    )
    (side / "cache.json").write_text(
        json.dumps(cache_entries if cache_entries is not None else CACHE_ENTRIES),
        encoding="utf-8",
    )
    (side / "usage_log.json").write_text(json.dumps({"entries": []}), encoding="utf-8")
    (side / "gt.json").write_text(json.dumps({}), encoding="utf-8")
    manifest = {
        "cells": [
            {
                "tenant_id": "M1",
                "condition": "C1",
                "run": _run_dict(config_hash=config_hash, status=status),
                "metrics_path": "metrics.json",
                "fact_keys_path": "fact_keys.json",
                "cache_export_path": "cache.json",
                "cache_fingerprint": cache_fingerprint(CACHE_ENTRIES),
                "usage_log_path": "usage_log.json",
                "ground_truth_path": "gt.json",
            }
        ]
    }
    path = side / "12.2-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, side


def _context(
    tmp_path: Path,
) -> tuple[Settings, LockRecord, tuple[CellManifest, ...], Path, Path]:
    """Bối cảnh pre-check khớp nhau hoàn toàn: lock + manifest + settings."""
    settings = _settings()
    locked = compute_config_hash(settings)
    lock = LockRecord.from_dict(_lock_dict(locked_config_hash=locked), "test")
    manifest_path, side = _write_manifest(tmp_path, config_hash=locked)
    manifest = load_manifest(manifest_path)
    return settings, lock, manifest, manifest_path, side


class FakeModel:
    """Model giả: trả một phản hồi cố định + usage cố định."""

    def __init__(self) -> None:
        """Chưa gọi lần nào."""
        self.calls = 0

    def complete(
        self,
        prompt: str,
        *,
        json_schema: Mapping[str, Any] | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        """Trả phản hồi cố định, đếm lần gọi."""
        self.calls += 1
        return CompletionResult(text='{"ok": true}', prompt_tokens=10, completion_tokens=5)


class FakeRunCell:
    """Hàm chạy ô giả: ghi lại tham số nhận được, trả outcome cố định."""

    def __init__(self) -> None:
        """Chưa chạy ô nào."""
        self.calls: list[tuple[CellRef, bool, tuple[str, ...], str | None]] = []

    def __call__(
        self,
        cell: CellRef,
        *,
        is_rerun: bool,
        repro_gaps: tuple[str, ...],
        checkpoint_prefix: str | None,
    ) -> CellOutcome:
        """Trả outcome thành công, verdict theo gap nhận được."""
        self.calls.append((cell, is_rerun, repro_gaps, checkpoint_prefix))
        return CellOutcome(
            run_id="run-chay-lai",
            run_status="succeeded",
            reproducibility="reproducible" if not repro_gaps else "not_reproducible",
            repro_gaps=repro_gaps,
            metrics={"metrics": {}},
            fact_keys=("a", "b"),
            usage_log={"entries": [{"key": "k1", "hit": True}]},
            model_calls=0,
            cache_hits=1,
            tokens_in=0,
            tokens_out=0,
        )


def test_counting_cached_model_miss_roi_hit(tmp_path: Path) -> None:
    """Model bọc cache: gọi lần đầu miss (ghi usage), lần hai hit (0 token)."""
    cache = ResponseCache()
    log = UsageLog()
    wrapped = CountingCachedModel(
        model=FakeModel(), cache=cache, model_revision=MODEL_REVISION, usage_log=log
    )
    first = wrapped.complete("xin chao")
    second = wrapped.complete("xin chao")
    assert first.text == second.text == '{"ok": true}'
    assert first.prompt_tokens == 10 and first.completion_tokens == 5
    assert second.prompt_tokens == 0 and second.completion_tokens == 0
    assert wrapped.calls == 1 and wrapped.hits == 1
    assert log.model_calls == 1 and log.cache_hits == 1 and log.total_tokens == 15
    assert len(cache) == 1


def test_usage_log_round_trip_va_sai_hinh_dang() -> None:
    """UsageLog xuất rồi nạp lại giống nhau; mục sai hình dạng thì từ chối."""
    log = UsageLog()
    log.record_miss("k1", 10, 5)
    log.record_hit("k2")
    restored = UsageLog.from_dict(log.to_dict())
    assert restored.to_dict() == log.to_dict()
    try:
        UsageLog.from_dict({"entries": [{"prompt_tokens": 1}]})
    except ValueError as exc:
        assert "sai hình dạng" in str(exc)
    else:
        raise AssertionError("from_dict phải từ chối mục thiếu khóa")


def test_load_manifest_trung_o_va_thieu_truong(tmp_path: Path) -> None:
    """Manifest trùng ô hoặc thiếu trường thì từ chối ngay."""
    settings = _settings()
    locked = compute_config_hash(settings)
    path, _ = _write_manifest(tmp_path, config_hash=locked)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["cells"].append(data["cells"][0])
    path.write_text(json.dumps(data), encoding="utf-8")
    try:
        load_manifest(path)
    except ValueError as exc:
        assert "trùng ô" in str(exc)
    else:
        raise AssertionError("load_manifest phải từ chối ô trùng")
    data["cells"] = [dict(data["cells"][0])]
    del data["cells"][0]["cache_fingerprint"]
    path.write_text(json.dumps(data), encoding="utf-8")
    try:
        load_manifest(path)
    except ValueError as exc:
        assert "cache_fingerprint" in str(exc)
    else:
        raise AssertionError("load_manifest phải từ chối ô thiếu trường")


def test_precheck_khop_du_gap_rong(tmp_path: Path) -> None:
    """Pre-check khớp hoàn toàn: không gap, ô đủ điều kiện chạy lại."""
    settings, lock, manifest, manifest_path, _ = _context(tmp_path)
    result = precheck(
        manifest,
        manifest_dir=manifest_path.absolute().parent,
        lock=lock,
        settings=settings,
        code_commit=CODE_COMMIT,
        data_hash=DATA_HASH,
    )
    assert len(result.cells) == 1
    assert result.cells[0].gaps == ()
    assert result.cells[0].ok is True
    assert result.reference_problems == ()


def test_precheck_code_commit_khac_gap_code_commit(tmp_path: Path) -> None:
    """Code commit khác lần đầu -> gap code_commit (không chặn chạy)."""
    settings, lock, manifest, manifest_path, _ = _context(tmp_path)
    result = precheck(
        manifest,
        manifest_dir=manifest_path.absolute().parent,
        lock=lock,
        settings=settings,
        code_commit="f" * 40,
        data_hash=DATA_HASH,
    )
    assert result.cells[0].gaps == ("code_commit",)
    assert result.cells[0].ok is True


def test_precheck_van_tay_cache_lech_gap_cache(tmp_path: Path) -> None:
    """Cache export khác vân tay đã ghi -> gap cache + ô không đủ điều kiện."""
    settings, lock, manifest, manifest_path, _ = _context(tmp_path)
    side = manifest_path.absolute().parent
    (side / "cache.json").write_text(json.dumps({"k1": "tra-loi-khac"}), encoding="utf-8")
    result = precheck(
        manifest,
        manifest_dir=manifest_path.absolute().parent,
        lock=lock,
        settings=settings,
        code_commit=CODE_COMMIT,
        data_hash=DATA_HASH,
    )
    assert result.cells[0].gaps == ("cache",)
    assert result.cells[0].fingerprint_ok is False
    assert result.cells[0].ok is False


def test_precheck_thieu_file_va_tham_chieu_fail(tmp_path: Path) -> None:
    """Thiếu file metrics -> ô thiếu tham chiếu; hàng tham chiếu fail cũng vậy."""
    settings = _settings()
    locked = compute_config_hash(settings)
    lock = LockRecord.from_dict(_lock_dict(locked_config_hash=locked), "test")
    manifest_path, _ = _write_manifest(tmp_path, config_hash=locked, write_metrics=False)
    manifest = load_manifest(manifest_path)
    result = precheck(
        manifest,
        manifest_dir=manifest_path.absolute().parent,
        lock=lock,
        settings=settings,
        code_commit=CODE_COMMIT,
        data_hash=DATA_HASH,
    )
    assert result.cells[0].missing_files == ("metrics",)
    assert result.cells[0].ok is False
    manifest_path, _ = _write_manifest(tmp_path, config_hash=locked, status="failed")
    manifest = load_manifest(manifest_path)
    result = precheck(
        manifest,
        manifest_dir=manifest_path.absolute().parent,
        lock=lock,
        settings=settings,
        code_commit=CODE_COMMIT,
        data_hash=DATA_HASH,
    )
    assert result.cells[0].reference_ok is False


def test_precheck_hang_tham_chieu_lech_khoa(tmp_path: Path) -> None:
    """Hàng tham chiếu lệch bản ghi khóa (config_hash) -> ô không đủ điều kiện."""
    settings = _settings()
    locked = compute_config_hash(settings)
    lock = LockRecord.from_dict(_lock_dict(locked_config_hash=locked), "test")
    manifest_path, _ = _write_manifest(tmp_path, config_hash="0" * 64)
    manifest = load_manifest(manifest_path)
    result = precheck(
        manifest,
        manifest_dir=manifest_path.absolute().parent,
        lock=lock,
        settings=settings,
        code_commit=CODE_COMMIT,
        data_hash=DATA_HASH,
    )
    assert result.cells[0].lock_mismatch == ("config_hash",)
    assert result.cells[0].reference_ok is False


def test_run_rerun_ghi_file_va_manifest(tmp_path: Path) -> None:
    """Chạy lại giả: ghi đủ file từng ô + manifest, tiền tố checkpoint có -rerun."""
    settings, lock, manifest, manifest_path, _ = _context(tmp_path)
    fake = FakeRunCell()
    output_dir = tmp_path / "out"
    report = run_rerun(
        manifest,
        manifest_dir=manifest_path.absolute().parent,
        lock=lock,
        settings=settings,
        code_commit=CODE_COMMIT,
        data_hash=DATA_HASH,
        run_cell=fake,
        output_dir=output_dir,
    )
    assert len(fake.calls) == 1
    cell, is_rerun, gaps, prefix = fake.calls[0]
    assert cell == CellRef(tenant_id="M1", condition="C1")
    assert is_rerun is True and gaps == ()
    assert prefix is not None and prefix.endswith("-rerun")
    cell_dir = output_dir / "M1" / "C1"
    for name in ("outcome.json", "metrics.json", "fact_keys.json", "usage_log.json"):
        assert (cell_dir / name).is_file()
    outcome = json.loads((cell_dir / "outcome.json").read_text(encoding="utf-8"))
    assert outcome["run_id"] == "run-chay-lai"
    rerun_manifest = load_manifest(output_dir / "12.3-manifest.json")
    assert len(rerun_manifest) == 1
    assert rerun_manifest[0].run.reproducibility == "reproducible"
    assert rerun_manifest[0].run.repro_gaps == ""
    assert report["code_commit"] == CODE_COMMIT
    report_cells = report["cells"]
    assert isinstance(report_cells, list) and len(report_cells) == 1
    first_cell = report_cells[0]
    assert isinstance(first_cell, dict)
    assert first_cell["run_id"] == "run-chay-lai"


def test_run_rerun_chuyen_gap_cho_ham_chay(tmp_path: Path) -> None:
    """Chạy lại có gap: gap truyền đúng cho hàm chạy, verdict ghi vào manifest."""
    settings, lock, manifest, manifest_path, _ = _context(tmp_path)
    fake = FakeRunCell()
    output_dir = tmp_path / "out"
    run_rerun(
        manifest,
        manifest_dir=manifest_path.absolute().parent,
        lock=lock,
        settings=settings,
        code_commit="f" * 40,
        data_hash=DATA_HASH,
        run_cell=fake,
        output_dir=output_dir,
    )
    assert fake.calls[0][2] == ("code_commit",)
    rerun_manifest = load_manifest(output_dir / "12.3-manifest.json")
    assert rerun_manifest[0].run.reproducibility == "not_reproducible"
    assert rerun_manifest[0].run.repro_gaps == "code_commit"


def test_run_rerun_khoa_lech_tu_choi_truoc_khi_chay(tmp_path: Path) -> None:
    """Cấu hình khác khóa -> từ chối trước khi gọi hàm chạy lần nào."""
    _, lock, manifest, manifest_path, _ = _context(tmp_path)
    other = Settings(database_url="", model_id="model-khac")
    fake = FakeRunCell()
    try:
        run_rerun(
            manifest,
            manifest_dir=manifest_path.absolute().parent,
            lock=lock,
            settings=other,
            code_commit=CODE_COMMIT,
            data_hash=DATA_HASH,
            run_cell=fake,
            output_dir=tmp_path / "out",
        )
    except ValueError as exc:
        assert "khác khóa phần đo" in str(exc)
    else:
        raise AssertionError("run_rerun phải từ chối khi cấu hình khác khóa")
    assert fake.calls == []


def test_run_rerun_thieu_tham_chieu_tu_choi(tmp_path: Path) -> None:
    """Pre-check thiếu tham chiếu -> từ chối, không gọi hàm chạy."""
    settings = _settings()
    locked = compute_config_hash(settings)
    lock = LockRecord.from_dict(_lock_dict(locked_config_hash=locked), "test")
    manifest_path, _ = _write_manifest(tmp_path, config_hash=locked, write_metrics=False)
    manifest = load_manifest(manifest_path)
    fake = FakeRunCell()
    try:
        run_rerun(
            manifest,
            manifest_dir=manifest_path.absolute().parent,
            lock=lock,
            settings=settings,
            code_commit=CODE_COMMIT,
            data_hash=DATA_HASH,
            run_cell=fake,
            output_dir=tmp_path / "out",
        )
    except ValueError as exc:
        assert "thiếu tham chiếu" in str(exc)
    else:
        raise AssertionError("run_rerun phải từ chối khi thiếu tham chiếu")
    assert fake.calls == []


def test_write_lock_refusal_report(tmp_path: Path) -> None:
    """Báo cáo khóa từ chối: verdict not_reproducible, run_id NULL, event NULL."""
    output_dir = tmp_path / "out"
    path = write_lock_refusal_report(
        output_dir,
        error="cấu hình đo khác khóa",
        code_commit=CODE_COMMIT,
        locked_config_hash="c" * 64,
    )
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["verdict"] == "not_reproducible"
    assert report["verdict_tong"] == "FAIL"
    assert report["gaps"] == ["config_hash"]
    assert report["run_id"] is None
    assert len(report["events"]) == 1
    assert report["events"][0]["run_id"] is None
    assert report["events"][0]["action"] == "reproducibility_check"
    assert len(report["events"][0]["payload_hash"]) == 64


def _write_lock_files(tmp_path: Path, *, locked_config_hash: str) -> tuple[Path, Path]:
    """Ghi cặp config + lock TOML tạm (lock khớp hash đã cho hoặc không)."""
    config_path = tmp_path / "phan-do.toml"
    config_path.write_text('database_url = ""\n', encoding="utf-8")
    lock_path = tmp_path / "phan-do.lock.toml"
    lock_path.write_text(
        "\n".join(
            [
                f'locked_config_hash = "{locked_config_hash}"',
                f'lock_commit = "{CODE_COMMIT}"',
                f'code_commit = "{CODE_COMMIT}"',
                "seed = 0",
                f'model_id = "{MODEL_ID}"',
                f'model_revision = "{MODEL_REVISION}"',
                f'data_hash = "{DATA_HASH}"',
                'cache = "empty"',
                'locked_at = "2026-11-07"',
                'locked_by = "test"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config_path, lock_path


def test_main_precheck_only_exit_0(tmp_path: Path) -> None:
    """CLI --precheck-only với mọi thứ khớp -> thoát 0."""
    config_path = tmp_path / "phan-do.toml"
    config_path.write_text('database_url = ""\n', encoding="utf-8")
    settings = load_settings(config_path)
    locked = compute_config_hash(settings)
    _, lock_path = _write_lock_files(tmp_path, locked_config_hash=locked)
    manifest_path, _ = _write_manifest(tmp_path, config_hash=locked)
    code = main(
        [
            "--config",
            str(config_path),
            "--lock",
            str(lock_path),
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--data-hash",
            DATA_HASH,
            "--code-commit",
            CODE_COMMIT,
            "--precheck-only",
        ]
    )
    assert code == 0
    assert load_lock_record(lock_path).locked_config_hash == locked


def test_main_khoa_tu_choi_exit_2_va_ghi_bao_cao(tmp_path: Path) -> None:
    """CLI khóa lệch -> thoát 2, báo cáo verdict ghi ra output-dir."""
    config_path, lock_path = _write_lock_files(tmp_path, locked_config_hash="0" * 64)
    output_dir = tmp_path / "out"
    code = main(
        [
            "--config",
            str(config_path),
            "--lock",
            str(lock_path),
            "--manifest",
            str(tmp_path / "khong-co-manifest.json"),
            "--output-dir",
            str(output_dir),
            "--data-hash",
            DATA_HASH,
            "--code-commit",
            CODE_COMMIT,
        ]
    )
    assert code == 2
    report = json.loads((output_dir / "12.3-report.json").read_text(encoding="utf-8"))
    assert report["verdict"] == "not_reproducible"
    assert report["run_id"] is None
