"""Test script so sánh lần chạy lại (task 12.3, A.1) trên dữ liệu giả.

Không cần Kaggle/B2: cặp giống nhau -> PASS; cặp khác một chỉ số -> FAIL
đúng ô + đúng chỉ số; cặp thiếu điều kiện -> verdict không tái lập được
đúng gap; cặp khác token audit -> FAIL mục token.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.kaggle.compare_12_3 import ComparisonReport, compare_manifests, load_json, main
from tools.kaggle.driver_12_3 import cache_fingerprint, load_manifest

MODEL_ID = "Qwen/Qwen3-8B-GGUF"
MODEL_REVISION = "7c41481f57cb95916b40956ab2f0b139b296d974"
CODE_COMMIT = "a" * 40
CONFIG_HASH = "c" * 64
DATA_HASH = "d" * 64
CACHE_ENTRIES = {"k1": "tra-loi-mot", "k2": "tra-loi-hai"}
CACHE_FINGERPRINT = cache_fingerprint(CACHE_ENTRIES)


def _metrics(
    *,
    precision: float = 0.8,
    recall: float = 0.7,
    violation_rate: float = 0.1,
    negative_transfer: float = 0.05,
) -> dict[str, Any]:
    """Metrics JSON một ô (bốn chỉ số kèm CI + ba số lượng)."""
    return {
        "tenant_id": "M1",
        "condition": "C1",
        "n_train": 10,
        "n_measure": 5,
        "n_reference": 8,
        "metrics": {
            "precision": {"value": precision, "lower": 0.7, "upper": 0.9},
            "recall": {"value": recall, "lower": 0.6, "upper": 0.8},
            "violation_rate": {"value": violation_rate, "lower": 0.05, "upper": 0.15},
            "negative_transfer": {"value": negative_transfer, "lower": 0.0, "upper": 0.1},
        },
    }


def _run(
    *,
    run_id: str = "run-tham-chieu",
    tokens_in: int = 300,
    tokens_out: int = 150,
    status: str = "succeeded",
    repro_gaps: str = "",
) -> dict[str, Any]:
    """Hàng `run` một ô trong manifest."""
    return {
        "run_id": run_id,
        "seed": 42,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "code_commit": CODE_COMMIT,
        "config_hash": CONFIG_HASH,
        "data_hash": DATA_HASH,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "status": status,
        "repro_gaps": repro_gaps,
    }


def _usage_reference() -> dict[str, Any]:
    """Log usage lần đầu: 2 lần gọi thật, tổng 450 token."""
    return {
        "entries": [
            {"key": "k1", "prompt_tokens": 100, "completion_tokens": 50},
            {"key": "k2", "prompt_tokens": 200, "completion_tokens": 100},
        ]
    }


def _usage_rerun() -> dict[str, Any]:
    """Log usage lần chạy lại: 2 hit, 0 lần gọi mới, tiết kiệm 450 token."""
    return {"entries": [{"key": "k1", "hit": True}, {"key": "k2", "hit": True}]}


def _write_side(
    base: Path,
    *,
    metrics: dict[str, Any],
    fact_keys: set[str],
    usage: dict[str, Any],
) -> dict[str, str]:
    """Ghi file một bên (tham chiếu / chạy lại) vào thư mục, trả đường dẫn tương đối."""
    base.mkdir(parents=True, exist_ok=True)
    (base / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    (base / "fact_keys.json").write_text(
        json.dumps({"fact_keys": sorted(fact_keys)}), encoding="utf-8"
    )
    (base / "cache.json").write_text(json.dumps(CACHE_ENTRIES), encoding="utf-8")
    (base / "usage_log.json").write_text(json.dumps(usage), encoding="utf-8")
    (base / "gt.json").write_text(json.dumps({}), encoding="utf-8")
    return {
        "metrics_path": "metrics.json",
        "fact_keys_path": "fact_keys.json",
        "cache_export_path": "cache.json",
        "usage_log_path": "usage_log.json",
        "ground_truth_path": "gt.json",
    }


def _write_manifests(
    tmp_path: Path,
    *,
    ref_metrics: dict[str, Any] | None = None,
    rerun_metrics: dict[str, Any] | None = None,
    ref_keys: set[str] | None = None,
    rerun_keys: set[str] | None = None,
    ref_usage: dict[str, Any] | None = None,
    rerun_usage: dict[str, Any] | None = None,
    ref_run: dict[str, Any] | None = None,
    rerun_run: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    """Ghi hai manifest (tham chiếu + chạy lại) cho một ô; trả hai đường dẫn."""
    ref_dir = tmp_path / "ref"
    rerun_dir = tmp_path / "rerun"
    ref_paths = _write_side(
        ref_dir,
        metrics=ref_metrics or _metrics(),
        fact_keys=ref_keys or {"a", "b"},
        usage=ref_usage or _usage_reference(),
    )
    rerun_paths = _write_side(
        rerun_dir,
        metrics=rerun_metrics or _metrics(),
        fact_keys=rerun_keys or {"a", "b"},
        usage=rerun_usage or _usage_rerun(),
    )
    ref_manifest = {
        "cells": [
            {
                "tenant_id": "M1",
                "condition": "C1",
                "run": ref_run or _run(),
                **ref_paths,
                "cache_fingerprint": CACHE_FINGERPRINT,
            }
        ]
    }
    rerun_manifest = {
        "cells": [
            {
                "tenant_id": "M1",
                "condition": "C1",
                "run": rerun_run or _run(run_id="run-chay-lai", tokens_in=0, tokens_out=0),
                **rerun_paths,
                "cache_fingerprint": CACHE_FINGERPRINT,
            }
        ]
    }
    ref_path = ref_dir / "12.2-manifest.json"
    rerun_path = rerun_dir / "12.3-manifest.json"
    ref_path.write_text(json.dumps(ref_manifest), encoding="utf-8")
    rerun_path.write_text(json.dumps(rerun_manifest), encoding="utf-8")
    return ref_path, rerun_path


def _compare(
    tmp_path: Path,
    *,
    ref_metrics: dict[str, Any] | None = None,
    rerun_metrics: dict[str, Any] | None = None,
    ref_keys: set[str] | None = None,
    rerun_keys: set[str] | None = None,
    ref_usage: dict[str, Any] | None = None,
    rerun_usage: dict[str, Any] | None = None,
    ref_run: dict[str, Any] | None = None,
    rerun_run: dict[str, Any] | None = None,
) -> ComparisonReport:
    """So một cặp manifest giả; trả báo cáo so sánh."""
    ref_path, rerun_path = _write_manifests(
        tmp_path,
        ref_metrics=ref_metrics,
        rerun_metrics=rerun_metrics,
        ref_keys=ref_keys,
        rerun_keys=rerun_keys,
        ref_usage=ref_usage,
        rerun_usage=rerun_usage,
        ref_run=ref_run,
        rerun_run=rerun_run,
    )
    return compare_manifests(
        load_manifest(ref_path),
        load_manifest(rerun_path),
        ref_dir=ref_path.absolute().parent,
        rerun_dir=rerun_path.absolute().parent,
    )


def test_cap_giong_nhau_pass(tmp_path: Path) -> None:
    """Cặp giống nhau -> PASS toàn bộ (cả 5 mục + không gap)."""
    report = _compare(tmp_path)
    assert report.passed is True
    assert len(report.cells) == 1
    assert report.cells[0].passed is True
    assert [check.name for check in report.cells[0].checks] == [
        "fact_keys",
        "metrics",
        "ci",
        "run_status",
        "n_counts",
        "token_audit",
        "new_calls",
    ]


def test_cap_khac_mot_chi_so_fail_dung_o_dung_chi_so(tmp_path: Path) -> None:
    """Cặp khác một chỉ số -> FAIL đúng ô, đúng mục metrics, đúng chỉ số đó."""
    report = _compare(tmp_path, rerun_metrics=_metrics(recall=0.71))
    assert report.passed is False
    cell = report.cells[0]
    assert cell.tenant_id == "M1" and cell.condition == "C1"
    by_name = {check.name: check for check in cell.checks}
    assert by_name["metrics"].passed is False
    assert "recall" in by_name["metrics"].detail
    assert by_name["fact_keys"].passed is True
    assert by_name["ci"].passed is True
    assert by_name["token_audit"].passed is True


def test_cap_khac_can_ci_fail_muc_ci(tmp_path: Path) -> None:
    """Cặp khác một cận CI -> FAIL mục ci (giá trị chỉ số vẫn bằng nhau)."""
    changed = _metrics()
    changed["metrics"]["precision"]["upper"] = 0.91
    report = _compare(tmp_path, rerun_metrics=changed)
    by_name = {check.name: check for check in report.cells[0].checks}
    assert by_name["ci"].passed is False
    assert "precision.upper" in by_name["ci"].detail
    assert by_name["metrics"].passed is True


def test_cap_khac_tap_fact_fail_muc_fact_keys(tmp_path: Path) -> None:
    """Cặp khác tập khóa fact -> FAIL mục fact_keys dù chỉ số trùng nhau."""
    report = _compare(tmp_path, rerun_keys={"a", "c"})
    by_name = {check.name: check for check in report.cells[0].checks}
    assert by_name["fact_keys"].passed is False
    assert by_name["metrics"].passed is True


def test_cap_thieu_dieu_kien_verdict_khong_tai_lap_duoc_dung_gap(tmp_path: Path) -> None:
    """Cặp thiếu điều kiện (gap cache) -> ô FAIL với đúng gap, dù số liệu trùng."""
    report = _compare(
        tmp_path,
        rerun_run=_run(run_id="run-chay-lai", tokens_in=0, tokens_out=0, repro_gaps="cache"),
    )
    cell = report.cells[0]
    assert cell.passed is False
    assert cell.gaps == ("cache",)
    assert all(check.passed for check in cell.checks)


def test_cap_khac_token_audit_fail_muc_token(tmp_path: Path) -> None:
    """Hit khóa không có trong log tham chiếu -> FAIL mục token_audit (0 lần gọi mới)."""
    rerun_usage = {"entries": [{"key": "k-la", "hit": True}, {"key": "k2", "hit": True}]}
    report = _compare(tmp_path, rerun_usage=rerun_usage)
    by_name = {check.name: check for check in report.cells[0].checks}
    assert by_name["token_audit"].passed is False
    assert "khong tra duoc usage" in by_name["token_audit"].detail
    assert by_name["new_calls"].passed is True


def test_cap_token_audit_lech_so_fail(tmp_path: Path) -> None:
    """Đẳng thức token lệch số -> FAIL mục token_audit."""
    rerun_run = _run(run_id="run-chay-lai", tokens_in=10, tokens_out=0)
    report = _compare(tmp_path, rerun_run=rerun_run)
    by_name = {check.name: check for check in report.cells[0].checks}
    assert by_name["token_audit"].passed is False
    assert "10 + 450 == 450" in by_name["token_audit"].detail


def test_cap_lan_chay_lai_goi_moi_fail_muc_new_calls(tmp_path: Path) -> None:
    """Lần chạy lại gọi mới mô hình -> FAIL mục new_calls (đệm không nguyên)."""
    rerun_usage = {
        "entries": [
            {"key": "k1", "hit": True},
            {"key": "k2", "prompt_tokens": 200, "completion_tokens": 100},
        ]
    }
    # Lần chạy lại gọi mới k2 (300 token) + hit k1 (tiết kiệm 150):
    # đẳng thức token vẫn thỏa (300 + 150 == 450), chỉ mục new_calls FAIL.
    report = _compare(
        tmp_path,
        rerun_usage=rerun_usage,
        rerun_run=_run(run_id="run-chay-lai", tokens_in=200, tokens_out=100),
    )
    by_name = {check.name: check for check in report.cells[0].checks}
    assert by_name["new_calls"].passed is False
    assert by_name["token_audit"].passed is True


def test_cap_thieu_o_chay_lai_fail(tmp_path: Path) -> None:
    """Thiếu ô trong manifest lần chạy lại -> FAIL mục lan_chay_lai."""
    ref_path, rerun_path = _write_manifests(tmp_path)
    rerun_path.write_text(json.dumps({"cells": []}), encoding="utf-8")
    report = compare_manifests(
        load_manifest(ref_path),
        load_manifest(rerun_path),
        ref_dir=ref_path.absolute().parent,
        rerun_dir=rerun_path.absolute().parent,
    )
    assert report.passed is False
    assert report.cells[0].checks[0].name == "lan_chay_lai"
    assert report.cells[0].checks[0].passed is False


def test_cap_trang_thai_run_fail_fail_muc_run_status(tmp_path: Path) -> None:
    """Lần chạy lại fail -> FAIL mục run_status (không có outcome để so)."""
    report = _compare(
        tmp_path,
        rerun_run=_run(run_id="run-chay-lai", tokens_in=0, tokens_out=0, status="failed"),
    )
    by_name = {check.name: check for check in report.cells[0].checks}
    assert by_name["run_status"].passed is False


def test_main_cap_giong_nhau_exit_0_va_ghi_bao_cao(tmp_path: Path) -> None:
    """CLI: cặp giống nhau -> thoát 0, ghi 12.3-report.json + event gắn run_id."""
    ref_path, rerun_path = _write_manifests(tmp_path)
    output = tmp_path / "12.3-report.json"
    code = main(
        [
            "--reference-manifest",
            str(ref_path),
            "--rerun-manifest",
            str(rerun_path),
            "--output",
            str(output),
        ]
    )
    assert code == 0
    report = load_json(output)
    assert report["verdict_tong"] == "PASS"
    assert report["cells"][0]["passed"] is True
    assert report["events"][0]["run_id"] == "run-chay-lai"
    assert report["events"][0]["action"] == "reproducibility_check"
    assert report["events"][0]["reason"] == "tái lập được"


def test_main_cap_khac_nhau_exit_1(tmp_path: Path) -> None:
    """CLI: cặp khác nhau -> thoát 1, báo cáo ghi verdict FAIL."""
    ref_path, rerun_path = _write_manifests(tmp_path, rerun_metrics=_metrics(recall=0.71))
    output = tmp_path / "12.3-report.json"
    code = main(
        [
            "--reference-manifest",
            str(ref_path),
            "--rerun-manifest",
            str(rerun_path),
            "--output",
            str(output),
        ]
    )
    assert code == 1
    report = load_json(output)
    assert report["verdict_tong"] == "FAIL"


def test_main_file_sai_hinh_dang_exit_2(tmp_path: Path) -> None:
    """CLI: manifest sai hình dạng -> thoát 2, không ghi báo cáo."""
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"khong-phai": "manifest"}), encoding="utf-8")
    _, rerun_path = _write_manifests(tmp_path)
    output = tmp_path / "12.3-report.json"
    code = main(
        [
            "--reference-manifest",
            str(bad),
            "--rerun-manifest",
            str(rerun_path),
            "--output",
            str(output),
        ]
    )
    assert code == 2
    assert not output.exists()
