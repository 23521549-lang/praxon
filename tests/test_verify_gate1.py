"""Test cho tools/verify_gate1.py — runner giả, không chạy phép đo thật."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from tools.verify_gate1 import (
    C4_TESTS,
    C6_TESTS,
    TOOL_GATES,
    Runner,
    check_structure,
    load_evidence,
    verify,
)

PY = sys.executable


def _mau_evidence(pytest_passed: int = 706) -> dict[str, Any]:
    """JSON bằng chứng mẫu khớp với đầu ra giả của _runner_mau."""
    return {
        "report_status": "DRAFT",
        "head_commit": "3c27472",
        "written_at": "2026-11-07",
        "conditions": [
            {
                "id": "C1",
                "verdict": "CHUA_DU",
                "test_or_number": "lệnh 13.1 chạy từ máy trống qua compose",
                "command": "<lệnh 13.1, điền khi có>",
                "measured_at_commit": None,
                "measured_at": None,
                "run_id_or_url": None,
                "open_items": ["task 13.1 chưa làm"],
            },
            {
                "id": "C2",
                "verdict": "CHUA_DU",
                "test_or_number": "bốn chỉ số theo tenant kèm CI 95%",
                "command": "<lệnh 13.1, điền khi có>",
                "measured_at_commit": None,
                "measured_at": None,
                "run_id_or_url": None,
                "open_items": ["task 13.1 chưa làm"],
            },
            {
                "id": "C3",
                "verdict": "CHUA_DU",
                "test_or_number": "chạy lệnh 13.1 hai lần, so đầu ra",
                "command": "<lệnh 13.1, điền khi có>",
                "measured_at_commit": None,
                "measured_at": None,
                "run_id_or_url": None,
                "open_items": ["task 13.1 chưa làm", "task 12.3 chưa làm"],
            },
            {
                "id": "C4",
                "verdict": "DAT",
                "test_or_number": "25/25 phép tấn công bị chặn (34/34 test)",
                "command": "python -m pytest tests/integration/test_invariants.py",
                "measured_at_commit": "3c27472",
                "measured_at": "2026-11-07",
                "run_id_or_url": None,
                "plan_number": 21,
                "measured_number": 25,
                "total_tests": 34,
                "open_items": ["Thuận quyết số 21/25"],
            },
            {
                "id": "C5",
                "verdict": "CHUA_DU",
                "test_or_number": "tại chỗ 11/11 cổng xanh; GitHub ĐỎ (run 42368407153)",
                "command": "11 cổng máy",
                "measured_at_commit": "3c27472",
                "measured_at": "2026-11-07",
                "run_id_or_url": (
                    "https://github.com/23521549-lang/praxon/actions/runs/42368407153"
                ),
                "local": {
                    "gates_passed": 11,
                    "pytest_passed": pytest_passed,
                    "perf_passed": 1,
                },
                "open_items": ["sửa CI (task riêng)", "một lần chạy CI xanh trên HEAD"],
            },
            {
                "id": "C6",
                "verdict": "DAT",
                "test_or_number": "20 test qua: bảng event 7, ToolGateway 6, Candidate 7",
                "command": (
                    "python -m pytest tests/integration/test_event_log.py "
                    "tests/test_tool_gateway.py tests/test_human_decision.py"
                ),
                "measured_at_commit": "3c27472",
                "measured_at": "2026-11-07",
                "run_id_or_url": None,
                "counts": {
                    "tests/integration/test_event_log.py": 7,
                    "tests/test_tool_gateway.py": 6,
                    "tests/test_human_decision.py": 7,
                },
                "open_items": [],
            },
        ],
    }


def _runner_mau(
    pytest_passed: int = 706,
    overrides: dict[tuple[str, ...], tuple[int, str]] | None = None,
) -> Runner:
    """Runner giả: trả đầu ra khớp với _mau_evidence."""
    c4_ids = "\n".join(
        [f"{C4_TESTS}::test_bd{i}_tan_cong" for i in range(1, 26)]
        + [f"{C4_TESTS}::test_bd5_khoa_giong_nhau_nhung_valid_during_ke_nhau_thi_qua"]
        + [f"{C4_TESTS}::test_cau_truc_{i}" for i in range(1, 9)]
    )
    mapping = {
        (PY, "-m", "pytest", C4_TESTS, "--collect-only", "--no-cov"): (
            0,
            f"{c4_ids}\n34 tests collected in 0.50s",
        ),
        (PY, "-m", "pytest", C4_TESTS, "--no-cov"): (0, "34 passed in 1.23s"),
    }
    for path, count in zip(C6_TESTS, (7, 6, 7), strict=True):
        mapping[(PY, "-m", "pytest", path, "--collect-only", "--no-cov")] = (
            0,
            f"{count} tests collected in 0.20s",
        )
        mapping[(PY, "-m", "pytest", path, "--no-cov")] = (
            0,
            f"{count} passed in 0.50s",
        )
    for gate in TOOL_GATES:
        mapping[gate] = (0, "")
    mapping[(PY, "-m", "pytest", "--ignore=tests/perf")] = (0, "")
    mapping[(PY, "-m", "pytest", "--ignore=tests/perf", "--collect-only", "--no-cov")] = (
        0,
        f"{pytest_passed} tests collected in 2.00s",
    )
    mapping[(PY, "-m", "pytest", "tests/perf", "--no-cov")] = (
        0,
        "1 passed in 0.50s",
    )
    if overrides:
        mapping.update(overrides)

    def fake(argv: tuple[str, ...], cwd: Path) -> tuple[int, str]:
        if argv in mapping:
            return mapping[argv]
        raise AssertionError(f"lệnh không lường trước: {argv}")

    return fake


def _ghi_json(tmp_path: Path, evidence: dict[str, Any]) -> Path:
    """Ghi evidence mẫu ra file tạm, trả đường dẫn."""
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(evidence, ensure_ascii=False), encoding="utf-8")
    return path


def test_json_mau_khop_thi_pass(tmp_path):
    errors = verify(_ghi_json(tmp_path, _mau_evidence()), tmp_path, _runner_mau())
    assert errors == []


def test_json_lech_so_c4_thi_fail_dung_cho(tmp_path):
    evidence = _mau_evidence()
    evidence["conditions"][3]["measured_number"] = 24
    errors = verify(_ghi_json(tmp_path, evidence), tmp_path, _runner_mau())
    assert errors
    assert any("C4" in e and "24" in e for e in errors)


def test_json_lech_tong_test_c4_thi_fail(tmp_path):
    evidence = _mau_evidence()
    evidence["conditions"][3]["total_tests"] = 33
    errors = verify(_ghi_json(tmp_path, evidence), tmp_path, _runner_mau())
    assert errors
    assert any("C4" in e for e in errors)


def test_json_thieu_run_id_phan_chay_xa_thi_fail(tmp_path):
    evidence = _mau_evidence()
    evidence["conditions"][4]["command"] = None
    evidence["conditions"][4]["run_id_or_url"] = None
    errors = verify(_ghi_json(tmp_path, evidence), tmp_path, _runner_mau())
    assert errors
    assert any("C5" in e for e in errors)


def test_json_c4_thieu_mot_trong_hai_so_thi_fail(tmp_path):
    evidence = _mau_evidence()
    del evidence["conditions"][3]["plan_number"]
    errors = check_structure(evidence)
    assert errors
    assert any("C4" in e and "21" in e for e in errors)


def test_verdict_la_thi_fail(tmp_path):
    evidence = _mau_evidence()
    evidence["conditions"][0]["verdict"] = "DAT_X"
    errors = check_structure(evidence)
    assert errors
    assert any("C1" in e for e in errors)


def test_final_ma_con_chua_du_thi_fail(tmp_path):
    evidence = _mau_evidence()
    evidence["report_status"] = "FINAL"
    errors = check_structure(evidence)
    assert errors
    assert any("FINAL" in e for e in errors)


def test_c6_lech_so_thi_fail_dung_cho(tmp_path):
    evidence = _mau_evidence()
    evidence["conditions"][5]["counts"]["tests/integration/test_event_log.py"] = 6
    errors = verify(_ghi_json(tmp_path, evidence), tmp_path, _runner_mau())
    assert errors
    assert any("test_event_log.py" in e for e in errors)


def test_c5_local_lech_so_test_thi_fail(tmp_path):
    evidence = _mau_evidence(pytest_passed=700)
    errors = verify(_ghi_json(tmp_path, evidence), tmp_path, _runner_mau())
    assert errors
    assert any("C5-local" in e and "700" in e for e in errors)


def test_chay_that_c4_that_bai_thi_fail(tmp_path):
    overrides: dict[tuple[str, ...], tuple[int, str]] = {
        (PY, "-m", "pytest", C4_TESTS, "--no-cov"): (
            1,
            "1 failed, 33 passed in 1.10s",
        ),
    }
    errors = verify(
        _ghi_json(tmp_path, _mau_evidence()), tmp_path, _runner_mau(overrides=overrides)
    )
    assert errors
    assert any("C4" in e for e in errors)


def test_json_khong_doc_duoc_thi_fail(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_text("{không phải json", encoding="utf-8")
    errors = verify(path, tmp_path, _runner_mau())
    assert errors
    assert any("JSON" in e for e in errors)


def test_load_evidence_thieu_file_thi_raise(tmp_path):
    with pytest.raises(ValueError, match="không đọc được"):
        load_evidence(tmp_path / "khong-co.json")
