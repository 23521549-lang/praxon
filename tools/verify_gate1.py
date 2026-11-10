"""Kiểm chứng báo cáo cổng 1 (task 13.3): đối chiếu số trong JSON với phép đo chạy lại.

Đọc `docs/plans/phase-1-core/bao-cao-cong-1-evidence.json` rồi kiểm:

- hình thức: đủ sáu điều kiện C1-C6, verdict chỉ DAT/CHUA_DU/CHUA_KIEM,
  mỗi điều kiện có lệnh hoặc run ID/URL, C4 ghi 25 (plan/spec)
  và 25 (file test đo được);
- đo lại tại chỗ: C4 (chạy `tests/integration/test_invariants.py`),
  C6 (ba file test của ba nền móng), C5-local (11 cổng máy) — số đo được
  phải khớp số trong JSON;
- phần chạy xa (Kaggle, CI GitHub): script KHÔNG chạy lại, chỉ kiểm JSON
  có run ID/URL hợp lệ (đường dẫn http(s) hoặc mã run dạng số) + ngày đo.

Thoát 0 khi mọi kiểm đều khớp, 1 khi có chỗ lệch (in đúng chỗ lệch).

Script này KHÔNG kết luận cổng qua hay không — kết luận là của Thuận
ở review cấp 3. Nó cũng không sửa CI, plan, spec hay code.

Chạy khi không có luồng pytest nào khác đang chạy (DB dùng chung — hai
luồng pytest cùng lúc có thể làm một test DB đỏ giả).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVIDENCE = (
    REPO_ROOT / "docs" / "plans" / "phase-1-core" / "bao-cao-cong-1-evidence.json"
)

VERDICTS = {"DAT", "CHUA_DU", "CHUA_KIEM"}
CONDITION_IDS = ("C1", "C2", "C3", "C4", "C5", "C6")
CONTROL_MARKER = "_thi_qua"

C4_TESTS = "tests/integration/test_invariants.py"
C6_TESTS = (
    "tests/integration/test_event_log.py",
    "tests/test_tool_gateway.py",
    "tests/test_human_decision.py",
)

# `python -m importlinter.cli` là no-op (thoát 0, không in gì kể cả khi hợp
# đồng vỡ); lệnh thật là console script `lint-imports` trong cùng venv.
# Lấy qua PATH (venv bin đứng đầu PATH khi chạy cổng); KHÔNG resolve
# sys.executable vì nó là symlink về /usr/bin/python3.
LINT_IMPORTS = shutil.which("lint-imports") or str(Path(sys.executable).parent / "lint-imports")

TOOL_GATES: tuple[tuple[str, ...], ...] = (
    (sys.executable, "-m", "tools.check_tool_versions"),
    (sys.executable, "-m", "ruff", "check", "."),
    (sys.executable, "-m", "ruff", "format", "--check", "."),
    (sys.executable, "-m", "mypy"),
    (LINT_IMPORTS, "--config", ".importlinter"),
    (sys.executable, "-m", "tools.check_env_access"),
    (sys.executable, "-m", "tools.check_thirdparty_data"),
    (sys.executable, "-m", "tools.check_no_stdlib_shadowing"),
    (sys.executable, "-m", "tools.check_licenses"),
    (sys.executable, "-m", "tools.check_core_standalone"),
)

Runner = Callable[[tuple[str, ...], Path], tuple[int, str]]


def run_command(argv: tuple[str, ...], cwd: Path) -> tuple[int, str]:
    """Chạy một lệnh, trả (mã thoát, stdout + stderr gộp).

    Lệnh không chạy được (không tìm thấy file thực thi) thì trả mã 127
    kèm lý do, thay vì để exception làm sập cả script — cổng đó tính là
    không đạt và được in đúng chỗ lệch như mọi cổng khác.
    """
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)
    except OSError as exc:
        return 127, f"không chạy được {' '.join(argv)}: {exc}"
    return proc.returncode, proc.stdout + proc.stderr


def load_evidence(path: Path) -> dict[str, Any]:
    """Đọc file JSON bằng chứng; lỗi đọc/parse thì raise ValueError."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"không đọc được {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} không phải JSON hợp lệ: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: JSON phải là object, không phải {type(data).__name__}")
    return data


def _is_non_empty_str(value: object) -> bool:
    """Đúng khi value là chuỗi không rỗng."""
    return isinstance(value, str) and bool(value)


def _find_condition(conditions: list[Any], cid: str) -> dict[str, Any] | None:
    """Tìm điều kiện theo id, không tìm thấy thì None."""
    for cond in conditions:
        if isinstance(cond, dict) and cond.get("id") == cid:
            return cond
    return None


def check_structure(evidence: dict[str, Any]) -> list[str]:
    """Kiểm hình thức JSON (không chạy phép đo nào)."""
    errors: list[str] = []
    status = evidence.get("report_status")
    if status not in {"DRAFT", "FINAL"}:
        errors.append(f"report_status phải là DRAFT hoặc FINAL, đang là {status!r}")
    conditions = evidence.get("conditions")
    if not isinstance(conditions, list) or len(conditions) != 6:
        errors.append("conditions phải là danh sách đúng 6 điều kiện")
        return errors
    for want in CONDITION_IDS:
        cond = _find_condition(conditions, want)
        if cond is None:
            errors.append(f"thiếu điều kiện {want}")
            continue
        verdict = cond.get("verdict")
        if verdict not in VERDICTS:
            errors.append(f"{want}: verdict phải là DAT/CHUA_DU/CHUA_KIEM, đang là {verdict!r}")
        if not _is_non_empty_str(cond.get("command")) and not _is_non_empty_str(
            cond.get("run_id_or_url")
        ):
            errors.append(f"{want}: thiếu cả command lẫn run_id_or_url")
        if not isinstance(cond.get("open_items"), list):
            errors.append(f"{want}: open_items phải là danh sách")
        if verdict == "DAT":
            if not cond.get("measured_at_commit"):
                errors.append(f"{want}: verdict DAT mà thiếu measured_at_commit")
            if not cond.get("measured_at"):
                errors.append(f"{want}: verdict DAT mà thiếu measured_at")
        if status == "FINAL":
            if verdict != "DAT":
                errors.append(
                    f"{want}: báo cáo FINAL mà verdict đang là {verdict!r} (phải DAT)"
                )
            for field in ("command", "run_id_or_url"):
                value = cond.get(field)
                if isinstance(value, str) and "<" in value:
                    errors.append(f"{want}: báo cáo FINAL mà {field} còn chỗ trống {value!r}")
    c4 = _find_condition(conditions, "C4")
    if c4 is not None:
        if c4.get("plan_number") != 25:
            errors.append(
                f"C4: plan_number đang là {c4.get('plan_number')!r}, phải là 25 "
                "(plan/spec nói 25 phép tấn công)"
            )
        if c4.get("measured_number") != 25:
            errors.append(
                f"C4: measured_number đang là {c4.get('measured_number')!r}, phải là 25 "
                "(file test có 25 phép tấn công)"
            )
    return errors


def parse_collected(output: str) -> int | None:
    """Số test thu thập được từ `pytest --collect-only` ("N tests collected")."""
    match = re.search(r"(\d+) tests? collected", output)
    return int(match.group(1)) if match else None


def parse_passed(output: str) -> int | None:
    """Số test qua từ dòng tóm tắt `pytest` ("N passed")."""
    matches = re.findall(r"(\d+) passed", output)
    return int(matches[-1]) if matches else None


def collect_test_names(output: str) -> list[str]:
    """Tên test từ `pytest --collect-only` (mỗi dòng `đường/dẫn::tên_test`).

    Chỉ đọc phần liệt kê (trước dòng tóm tắt "N tests collected") và
    khử trùng — phần cảnh báo ở cuối đầu ra có thể nhắc lại một nodeid.
    """
    names: list[str] = []
    for line in output.splitlines():
        if "tests collected" in line:
            break
        if "::" in line:
            name = line.split("::", 1)[1].strip()
            if name not in names:
                names.append(name)
    return names


def pytest_collect(run: Runner, repo_root: Path, *paths: str) -> tuple[int, str]:
    """Chạy `pytest --collect-only --no-cov`, trả (mã thoát, đầu ra).

    Không thêm `-q` ở đây: addopts của repo đã có `-q`, thêm nữa thành
    `-qq` sẽ nuốt dòng tóm tắt "N tests collected".
    """
    return run(
        (sys.executable, "-m", "pytest", *paths, "--collect-only", "--no-cov"),
        repo_root,
    )


def pytest_run(run: Runner, repo_root: Path, *paths: str) -> tuple[int, str]:
    """Chạy `pytest --no-cov`, trả (mã thoát, đầu ra).

    Không thêm `-q` ở đây: addopts của repo đã có `-q`, thêm nữa thành
    `-qq` sẽ nuốt dòng tóm tắt "N passed".
    """
    return run((sys.executable, "-m", "pytest", *paths, "--no-cov"), repo_root)


def measure_c4(repo_root: Path, run: Runner) -> tuple[dict[str, int], list[str]]:
    """Đo lại C4: số phép tấn công + tổng số test + số test qua."""
    errors: list[str] = []
    measured: dict[str, int] = {}
    code, out = pytest_collect(run, repo_root, C4_TESTS)
    if code != 0:
        errors.append(f"C4: thu thập test lỗi (mã thoát {code})")
        return measured, errors
    collected = parse_collected(out)
    if collected is None:
        errors.append("C4: không đọc được số test thu thập được")
        return measured, errors
    names = collect_test_names(out)
    attacks = [name for name in names if name.startswith("test_bd")]
    controls = [name for name in attacks if CONTROL_MARKER in name]
    if len(controls) != 1:
        errors.append(
            f"C4: cần đúng 1 control dương ({CONTROL_MARKER}) trong test_bd*, "
            f"đang có {len(controls)}"
        )
        return measured, errors
    measured["total_tests"] = collected
    measured["attacks"] = len(attacks) - len(controls)
    code, out = pytest_run(run, repo_root, C4_TESTS)
    if code != 0:
        errors.append(f"C4: chạy test lỗi (mã thoát {code})")
        return measured, errors
    passed = parse_passed(out)
    if passed is None:
        errors.append("C4: không đọc được số test qua")
        return measured, errors
    measured["passed"] = passed
    if passed != collected:
        errors.append(f"C4: chỉ {passed}/{collected} test qua")
    return measured, errors


def measure_c6(
    repo_root: Path, run: Runner, expected: dict[str, int]
) -> tuple[dict[str, int], list[str]]:
    """Đo lại C6: số test qua từng file trong ba nền móng."""
    errors: list[str] = []
    measured: dict[str, int] = {}
    for path, want in expected.items():
        code, out = pytest_collect(run, repo_root, path)
        if code != 0:
            errors.append(f"C6: thu thập test {path} lỗi (mã thoát {code})")
            continue
        collected = parse_collected(out)
        if collected is None:
            errors.append(f"C6: không đọc được số test thu thập được ở {path}")
            continue
        code, out = pytest_run(run, repo_root, path)
        if code != 0:
            errors.append(f"C6: chạy test {path} lỗi (mã thoát {code})")
            continue
        passed = parse_passed(out)
        if passed is None:
            errors.append(f"C6: không đọc được số test qua ở {path}")
            continue
        measured[path] = passed
        if passed != collected or passed != want:
            errors.append(
                f"C6: {path} đo được {passed} test qua (thu thập {collected}, JSON ghi {want})"
            )
    return measured, errors


def measure_local_gates(repo_root: Path, run: Runner) -> tuple[dict[str, int], list[str]]:
    """Chạy lại 11 cổng máy: 10 cổng tool + pytest chính + pytest perf."""
    errors: list[str] = []
    measured: dict[str, int] = {}
    tool_passed = 0
    for gate in TOOL_GATES:
        code, _ = run(gate, repo_root)
        if code != 0:
            errors.append(f"C5-local: cổng {' '.join(gate[2:])} lỗi (mã thoát {code})")
        else:
            tool_passed += 1
    code, _ = run((sys.executable, "-m", "pytest", "--ignore=tests/perf"), repo_root)
    pytest_ok = code == 0
    if not pytest_ok:
        errors.append(f"C5-local: pytest chính (có coverage) lỗi (mã thoát {code})")
    code, out = pytest_collect(run, repo_root, "--ignore=tests/perf")
    collected = parse_collected(out) if code == 0 else None
    if collected is None:
        errors.append("C5-local: không đọc được số test thu thập được ở pytest chính")
    else:
        measured["pytest_passed"] = collected
    code, out = pytest_run(run, repo_root, "tests/perf")
    perf_passed = parse_passed(out) if code == 0 else None
    if code != 0 or perf_passed is None:
        errors.append(f"C5-local: pytest perf lỗi (mã thoát {code})")
    else:
        measured["perf_passed"] = perf_passed
    if tool_passed == len(TOOL_GATES) and pytest_ok and perf_passed is not None:
        measured["gates_passed"] = len(TOOL_GATES) + 1
    return measured, errors


def verify(evidence_path: Path, repo_root: Path, run: Runner = run_command) -> list[str]:
    """Kiểm toàn bộ JSON: hình thức + đo lại tại chỗ + đối chiếu."""
    try:
        evidence = load_evidence(evidence_path)
    except ValueError as exc:
        return [str(exc)]
    errors = check_structure(evidence)
    if errors:
        return errors
    conditions = evidence["conditions"]
    by_id = {cond["id"]: cond for cond in conditions if isinstance(cond, dict)}

    c4 = by_id["C4"]
    measured_c4, errs = measure_c4(repo_root, run)
    errors.extend(errs)
    if measured_c4.get("attacks") is not None and measured_c4["attacks"] != c4.get(
        "measured_number"
    ):
        errors.append(
            f"C4: đo lại được {measured_c4['attacks']} phép tấn công, "
            f"JSON ghi {c4.get('measured_number')}"
        )
    if measured_c4.get("total_tests") is not None and measured_c4["total_tests"] != (
        c4.get("total_tests")
    ):
        errors.append(
            f"C4: đo lại được {measured_c4['total_tests']} test, "
            f"JSON ghi {c4.get('total_tests')}"
        )

    c6 = by_id["C6"]
    expected_c6 = c6.get("counts")
    if not isinstance(expected_c6, dict) or set(expected_c6) != set(C6_TESTS):
        errors.append(f"C6: counts phải ghi đúng ba file {list(C6_TESTS)}")
    else:
        _, errs = measure_c6(repo_root, run, expected_c6)
        errors.extend(errs)

    c5 = by_id["C5"]
    local = c5.get("local")
    if not isinstance(local, dict):
        errors.append("C5: thiếu local (số cổng máy đo tại chỗ)")
    else:
        measured_gates, errs = measure_local_gates(repo_root, run)
        errors.extend(errs)
        if measured_gates.get("gates_passed") is not None and measured_gates[
            "gates_passed"
        ] != local.get("gates_passed"):
            errors.append(
                f"C5-local: đo lại được {measured_gates['gates_passed']}/11 cổng xanh, "
                f"JSON ghi {local.get('gates_passed')}"
            )
        if measured_gates.get("pytest_passed") is not None and measured_gates[
            "pytest_passed"
        ] != local.get("pytest_passed"):
            errors.append(
                f"C5-local: đo lại được {measured_gates['pytest_passed']} test qua "
                f"ở pytest chính, JSON ghi {local.get('pytest_passed')}"
            )
        if measured_gates.get("perf_passed") is not None and measured_gates[
            "perf_passed"
        ] != local.get("perf_passed"):
            errors.append(
                f"C5-local: đo lại được {measured_gates['perf_passed']} test qua "
                f"ở pytest perf, JSON ghi {local.get('perf_passed')}"
            )

    for cid in CONDITION_IDS:
        ref = by_id[cid].get("run_id_or_url")
        if ref is not None and not (
            isinstance(ref, str)
            and (ref.startswith("http://") or ref.startswith("https://") or ref.isdigit())
        ):
            errors.append(f"{cid}: run_id_or_url không hợp lệ: {ref!r}")
    return errors


def main(argv: list[str] | None = None) -> int:
    """Chạy kiểm chứng, trả 0 khi khớp, 1 khi lệch."""
    args = list(sys.argv[1:] if argv is None else argv)
    evidence_path = DEFAULT_EVIDENCE
    if args:
        if len(args) != 2 or args[0] != "--evidence":
            print(
                "Cách dùng: python -m tools.verify_gate1 [--evidence <đường dẫn JSON>]",
                file=sys.stderr,
            )
            return 1
        evidence_path = Path(args[1])
    errors = verify(evidence_path, REPO_ROOT)
    if errors:
        print(f"Kiểm chứng cổng 1 LỆCH ({len(errors)} chỗ):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"Kiểm chứng cổng 1 KHỚP: {evidence_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
