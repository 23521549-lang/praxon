"""Một lệnh chạy bảy điều kiện trên cả hai nguồn (task 13.1, spec dòng 31).

Bộ điều phối chạy trong container `eval` (xem `Dockerfile` + `compose.yml`):
nạp cấu hình khóa bằng `load_locked_config` (12.1), áp migration, đảm bảo
dữ liệu (tải BPIC 2015 nếu thiếu, sinh bộ chuẩn từ seed 42, tải HTML Wabo
nếu thiếu), trích luật Wabo bằng model service, chạy bảy điều kiện trên bộ
chuẩn bằng `run_experiments` và trên phần đo BPIC 2015 bằng driver 12.2,
in bốn chỉ số + bản ghi ra stdout + JSON, rồi so với JSON đã ghi của 12.2.

Mã thoát (kế thừa quy ước `wabo_rules` 0/1/2 + 10.4 mã 3, đề xuất 13.1 A.1):
0 = xong và trùng; 1 = thiếu dữ liệu / model không tới được; 2 = tham số
sai / khóa sai / cấu hình lệch / driver đo chưa có; 3 = chạm trần token
(`budget_exceeded`); 4 = chạy xong nhưng KHÔNG trùng số đã ghi.

Hai điểm lệch so với đề xuất 13.1 (đã kiểm bằng code, ghi rõ để review):

1. Đường dẫn JSON tham chiếu: đề xuất 13.1 A.4 ghi
   `docs/plans/phase-1-core/ket-qua-12.2.json`, nhưng bên sản xuất (đề xuất
   12.2 A.4) chốt `docs/plans/phase-1-core/ket-qua-do-bpic2015.json`.
   Theo R5 của 13.1 ("nếu 12.2 chốt đường dẫn/schema khác thì 13.1 theo
   12.2"), module này dùng đường dẫn của 12.2.
2. Luật tài liệu: đề xuất 13.1 A.1 bước 4 trích lại luật Wabo bằng model
   trong lúc chạy; đề xuất 12.2 (L2) cấm trích lại vì tập luật trích lại có
   thể khác lần trích của 9.1. Module này vẫn trích theo 13.1 cho đường bộ
   chuẩn (số đó không có tham chiếu 12.2 để so), nhưng đường BPIC KHÔNG
   dùng luật trích lại — driver 12.2 tự đọc file đã ghi
   `luat-tai-lieu-wabo.txt` (12.2 A.7), nên phép so BPIC không bị ảnh
   hưởng. Trích lại cũng cổng Beta trên trace gộp cả năm đô thị (kể cả
   phần đo, như 9.1) — khác với tái cổng chỉ trên phần học của 12.2 (R2);
   đó là hạn chế đã biết của đường bộ chuẩn, ghi trong ghi chú báo cáo.

Ba điểm khác (đã kiểm bằng code, không phải lệch mà là làm rõ):

3. `data_hash` so với tham chiếu: JSON của 12.2 chỉ có nửa BPIC
   (`merge_data_hash(bpic_hash="0edb706d…")`), còn lần chạy 13.1 bao cả
   hai nguồn nên `data_hash` đầy đủ của nó gộp thêm nửa bộ sinh. So sánh
   chỉ dùng nửa BPIC (tính lại từ 5 file XES + tham số chia + tenant),
   chấp nhận cả dạng đã gộp lẫn dạng nửa thô — hai dạng là cùng một đầu
   vào, chỉ khác mức gộp.
4. `code_commit`: ghi `git rev-parse HEAD` lúc chạy (quy tắc đóng băng
   của 12.3 — H7 đã chốt theo 12.3, không dùng hướng "kiểm diff rỗng rồi
   ghi commit khóa"). Code 13.1 phải merge TRƯỚC khi 12.2 chạy đo để
   commit của 12.2 chứa code này; chạy lại trên HEAD khác thì so sánh
   báo khoảng `code_commit` (đúng kết quả, không phải lỗi lệnh).
5. `cache_intact`: JSON tham chiếu không mang dấu vân tay đệm (dấu đó nằm
   trong manifest của 12.2, do 12.3 đối chiếu). Module này suy ra từ quan
   sát: driver đo BPIC không gọi mô hình lần nào (12.2 H2) nên không tiêu
   thụ đệm nào — `cache_intact` là đúng theo nghĩa rỗng. Phép so dấu vân
   tay chặt vẫn là việc của 12.3.

Chế độ `--smoke`: lát cắt nhỏ để chứng minh ống dẫn (CI mọi push) — bỏ
qua trích Wabo (luật tài liệu rỗng), bộ chuẩn rút gọn, driver BPIC giả
(`_mock_bpic_driver`, xác định, ghi rõ MOCK trong stdout). Không thay
phép thử full. Driver BPIC thật chưa có trong repo lúc viết module này
nên đường full dùng nó qua tiến trình con (xem `_run_bpic_driver`); thiếu
module driver thì thoát 2 rõ ràng thay vì chạy với số giả im lặng.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypedDict, cast

from praxon_core.datasets.bpic2015 import BPIC2015_DATASETS, download_all_bpic2015
from praxon_core.datasets.split import SplitFractions, compute_data_hash
from praxon_core.declare.miner import Rule
from praxon_core.eval.experiments import (
    CONDITIONS,
    format_experiments_report,
    run_experiments,
)
from praxon_core.eval.ground_truth import BPIC_TEST_SPLIT_SOURCE
from praxon_core.eval.report import (
    SYNTHETIC_N_CASES,
    SYNTHETIC_SEED,
    SYNTHETIC_TENANT_COUNT,
    MetricCI,
    TenantConditionRow,
)
from praxon_core.learning.coordinator import (
    BudgetExceededError,
    merge_data_hash,
    reproducibility_gaps,
)
from praxon_core.learning.dutch_mapping import default_dutch_mapping
from praxon_core.learning.rules import default_rule_table
from praxon_core.learning.test_split_lock import load_locked_config
from praxon_core.learning.wabo_rules import (
    WABO_DEFAULT_HTML_FILENAME,
    build_reflector,
    extract_wabo_rules,
    load_bpic_traces,
    load_wabo_document,
)
from praxon_core.repositories import migrate
from praxon_core.repositories.runs import RunRow
from praxon_core.settings import Settings
from praxon_core.synthetic.generator import (
    BASE_ORDER,
    GeneratorParams,
    swap_adjacent,
)
from praxon_core.synthetic.generator import (
    compute_data_hash as generator_data_hash,
)

#: Đường dẫn mặc định (tương đối gốc kho) của hai file khóa 12.1.
DEFAULT_CONFIG_PATH = Path("configs/phan-do.toml")
DEFAULT_LOCK_PATH = Path("configs/phan-do.lock.toml")
#: Đường dẫn JSON đã ghi của 12.2 — nguồn sự thật duy nhất để so (12.2 A.4).
DEFAULT_REFERENCE_PATH = Path("docs/plans/phase-1-core/ket-qua-do-bpic2015.json")
#: Tên file báo cáo của lần chạy này trong thư mục `--out`.
REPORT_FILENAME = "phase1-report.json"
#: Seed trích Wabo: trùng mặc định của `wabo_rules.main` (lần trích 9.1).
WABO_EXTRACT_SEED = 42
#: Lát cắt smoke: bộ chuẩn nhỏ + ít lần rút bootstrap (chỉ chứng minh ống dẫn).
SMOKE_N_CASES = 30
SMOKE_N_DRAWS = 100
#: Bốn chỉ số, luôn báo cùng nhau (spec dòng 178).
METRIC_NAMES = ("precision", "recall", "violation_rate", "negative_transfer")
#: Module driver đo BPIC (12.2) — chạy qua tiến trình con khi đã có.
BPIC_DRIVER_MODULE = "praxon_core.eval.bpic_measure"


def _repo_root() -> Path:
    """Gốc kho: từ vị trí file này, rơi về thư mục làm việc nếu lạ."""
    candidate = Path(__file__).resolve().parents[5]
    if (candidate / "configs" / "phan-do.toml").is_file():
        return candidate
    return Path.cwd()


def _read_lock_seed(lock_path: Path) -> int:
    """Seed lần chạy đo trong bản ghi khóa (không phải seed mặc định code)."""
    try:
        raw = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"không đọc được bản ghi khóa {lock_path}: {exc}") from exc
    seed = raw.get("seed")
    if not isinstance(seed, int):
        raise ValueError(f"bản ghi khóa {lock_path} thiếu seed (số nguyên)")
    return seed


def _current_code_commit(explicit: str | None) -> str:
    """`code_commit` lúc chạy: cờ `--code-commit`, rồi git, rồi `"unknown"`."""
    if explicit:
        return explicit
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else "unknown"


def _bpic_half_hash(cache_dir: Path) -> str:
    """Nửa BPIC của `data_hash`: băm 5 file XES + tham số chia + tenant."""
    log_hashes: list[str] = []
    for dataset in BPIC2015_DATASETS:
        path = cache_dir / dataset.xes_filename
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        log_hashes.append(digest.hexdigest())
    return compute_data_hash(
        log_hashes=tuple(log_hashes),
        fractions=SplitFractions(),
        tenants=tuple(dataset.municipality for dataset in BPIC2015_DATASETS),
    )


def _generator_half_hash(*, seed: int, n_cases: int) -> str:
    """Nửa bộ sinh của `data_hash`: băm 5 tenant giả, cùng cách sinh của `run_experiments`.

    Chưa có hàm gộp chuẩn cho nhiều tenant (mỗi tenant một băm riêng theo
    `synthetic.compute_data_hash`) nên gộp bằng băm của 5 băm con đã sắp
    xếp — xác định, đổi một tham số thì đổi băm. Chỉ dùng cho `data_hash`
    đầy đủ của chính lần chạy này (so run-vs-run); phép so với tham chiếu
    12.2 chỉ dùng nửa BPIC, không dùng nửa này.
    """
    per_tenant = sorted(
        generator_data_hash(
            tenant_id=f"synthetic-{index + 1}",
            params=GeneratorParams(
                seed=seed,
                n_cases=n_cases,
                order=swap_adjacent(BASE_ORDER, index),
            ),
        )
        for index in range(SYNTHETIC_TENANT_COUNT)
    )
    return hashlib.sha256("".join(per_tenant).encode()).hexdigest()


def _metric_dict(metric: MetricCI) -> dict[str, float]:
    """Một chỉ số kèm khoảng thành dict JSON."""
    return {"value": metric.value, "lower": metric.lower, "upper": metric.upper}


def _row_dict(row: TenantConditionRow) -> dict[str, object]:
    """Một hàng `TenantConditionRow` thành dict JSON (khớp schema 12.2 A.4)."""
    return {
        "tenant_id": row.tenant_id,
        "condition": row.condition,
        "source": row.source,
        "n_train": row.n_train,
        "n_measure": row.n_measure,
        "n_reference": row.n_reference,
        "n_rules": row.n_rules,
        "metrics": {name: _metric_dict(getattr(row.metrics, name)) for name in METRIC_NAMES},
    }


def normalize_row(row: object) -> dict[str, object] | None:
    """Chuẩn hóa một hàng báo cáo về dạng lồng `metrics` (12.2 A.4).

    Chấp nhận cả hai dạng: bốn chỉ số lồng dưới `metrics` (dạng
    `TenantConditionRow`, bên sản xuất 12.2 dùng) và bốn chỉ số trải phẳng
    ở đỉnh hàng (dạng ví dụ trong đề xuất 13.1 A.4). Trả `None` khi thiếu
    trường, sai kiểu, hoặc khoảng tin cậy vô nghĩa (lower > value hoặc
    value > upper) — gọi là sai schema, không đoán.
    """
    if not isinstance(row, dict):
        return None
    required_ints = ("n_train", "n_measure", "n_reference", "n_rules")
    for field in ("tenant_id", "condition", "source", *required_ints):
        if field not in row:
            return None
    if not all(isinstance(row[field], str) for field in ("tenant_id", "condition", "source")):
        return None
    if not all(isinstance(row[field], int) for field in required_ints):
        return None
    metrics_raw = row.get("metrics")
    if metrics_raw is None:
        metrics_raw = {name: row.get(name) for name in METRIC_NAMES if name in row}
    if not isinstance(metrics_raw, dict):
        return None
    metrics: dict[str, dict[str, float]] = {}
    for name in METRIC_NAMES:
        entry = metrics_raw.get(name)
        if not isinstance(entry, dict):
            return None
        values = [entry.get(key) for key in ("value", "lower", "upper")]
        if not all(isinstance(value, (int, float)) for value in values):
            return None
        value, lower, upper = (float(item) for item in values)  # type: ignore[arg-type]
        if not lower <= value <= upper:
            return None
        metrics[name] = {"value": value, "lower": lower, "upper": upper}
    return {
        "tenant_id": row["tenant_id"],
        "condition": row["condition"],
        "source": row["source"],
        "n_train": row["n_train"],
        "n_measure": row["n_measure"],
        "n_reference": row["n_reference"],
        "n_rules": row["n_rules"],
        "metrics": metrics,
    }


def _row_key(row: dict[str, object]) -> tuple[str, str, str]:
    """Khóa một hàng: (nguồn, tenant, điều kiện)."""
    return (
        str(row["source"]),
        str(row["tenant_id"]),
        str(row["condition"]),
    )


def _metrics_equal(
    left: dict[str, dict[str, float]], right: dict[str, dict[str, float]]
) -> list[str]:
    """Các chỉ số lệch nhau (bằng nhau tuyệt đối, không dung sai — 12.3 H6)."""
    diffs: list[str] = []
    for name in METRIC_NAMES:
        for bound in ("value", "lower", "upper"):
            if left[name][bound] != right[name][bound]:
                diffs.append(f"{name}.{bound}: {left[name][bound]} != {right[name][bound]}")
    return diffs


class _RunMetadata(TypedDict):
    """Sáu trường metadata của một lần chạy, đã kiểm kiểu (seed là số nguyên)."""

    code_commit: str
    config_hash: str
    data_hash: str
    seed: int
    model_id: str
    model_revision: str


def _reference_metadata(reference: dict[str, object]) -> _RunMetadata | None:
    """Sáu trường metadata của lần chạy tham chiếu (đỉnh hoặc trong `note`).

    Đề xuất 13.1 A.4 ghi chúng ở đỉnh JSON; đề xuất 12.2 A.4 ghi chúng
    trong "ghi chú". Chấp nhận cả hai chỗ, thiếu một trường hoặc sai kiểu
    thì trả `None` (fail-closed, không đoán, không ép kiểu).
    """
    str_fields = (
        "code_commit",
        "config_hash",
        "data_hash",
        "model_id",
        "model_revision",
    )
    note = reference.get("note")
    sources: list[dict[str, object]] = [reference]
    if isinstance(note, dict):
        sources.append(note)
    for source in sources:
        seed = source.get("seed")
        if not isinstance(seed, int) or isinstance(seed, bool):
            continue
        if not all(isinstance(source.get(field), str) for field in str_fields):
            continue
        return _RunMetadata(
            code_commit=str(source["code_commit"]),
            config_hash=str(source["config_hash"]),
            data_hash=str(source["data_hash"]),
            seed=seed,
            model_id=str(source["model_id"]),
            model_revision=str(source["model_revision"]),
        )
    return None


def _compare_row_maps(
    first: dict[tuple[str, str, str], dict[str, object]],
    second: dict[tuple[str, str, str], dict[str, object]],
    extra_label: str,
    missing_label: str,
) -> list[str]:
    """So hai bản đồ hàng theo khóa (nguồn, tenant, điều kiện).

    Hàng chỉ có ở một phía báo thừa/thiếu; hàng chung so bốn chỉ số
    bằng nhau tuyệt đối trên giá trị + cả hai cận (12.3 H6, không dung
    sai). Trả danh sách khoảng; rỗng = trùng.
    """
    gaps: list[str] = []
    for key in sorted(set(first) - set(second)):
        gaps.append(f"{extra_label}: {key}")
    for key in sorted(set(second) - set(first)):
        gaps.append(f"{missing_label}: {key}")
    for key in sorted(set(first) & set(second)):
        left = first[key]
        right = second[key]
        for diff in _metrics_equal(
            cast(dict[str, dict[str, float]], left["metrics"]),
            cast(dict[str, dict[str, float]], right["metrics"]),
        ):
            gaps.append(f"{key}: {diff}")
    return gaps


def _metadata_gaps(
    run: dict[str, object],
    reference: dict[str, object],
    run_missing: str,
    reference_missing: str,
) -> list[str]:
    """Sáu điều kiện tái lập spec 191 giữa hai báo cáo; rỗng = trùng.

    Metadata lấy từ đỉnh báo cáo (hoặc trong `note`, xem
    `_reference_metadata`); thiếu một trường hoặc sai kiểu thì báo thiếu
    metadata (fail-closed, không đoán). `cache_intact` lấy từ phía lần
    chạy, mặc định đúng khi báo cáo không mang trường này.
    """
    ref_meta = _reference_metadata(reference)
    run_meta = _reference_metadata(run)
    if ref_meta is None:
        return [reference_missing]
    if run_meta is None:
        return [run_missing]
    record = RunRow(
        tenant_id="",
        seed=ref_meta["seed"],
        model_id=ref_meta["model_id"],
        model_revision=ref_meta["model_revision"],
        code_commit=ref_meta["code_commit"],
        config_hash=ref_meta["config_hash"],
        data_hash=ref_meta["data_hash"],
    )
    return list(
        reproducibility_gaps(
            record,
            seed=run_meta["seed"],
            model_id=run_meta["model_id"],
            model_revision=run_meta["model_revision"],
            code_commit=run_meta["code_commit"],
            config_hash=run_meta["config_hash"],
            data_hash=run_meta["data_hash"],
            cache_intact=bool(run.get("cache_intact", True)),
        )
    )


def compare_reports(run: dict[str, object], reference: dict[str, object]) -> list[str]:
    """So báo cáo lần chạy này với JSON đã ghi của 12.2; rỗng = trùng.

    So hai lớp: (a) sáu điều kiện tái lập spec 191 bằng
    `reproducibility_gaps` (seed, model, code_commit, config_hash,
    data_hash nửa BPIC, đệm); (b) bốn chỉ số từng hàng BPIC bằng nhau
    tuyệt đối trên giá trị + cả hai cận (12.3 H6, không dung sai). Hàng
    bộ chuẩn không có trong tham chiếu nên không so ở đây — chúng do
    `compare_runs` (phép so run1-vs-run2 của job CI) kiểm. Sai schema ở
    bên nào cũng là một khoảng (fail-closed, không bỏ qua im lặng).
    """
    run_rows_raw = run.get("rows")
    ref_rows_raw = reference.get("rows")
    if not isinstance(run_rows_raw, list) or not isinstance(ref_rows_raw, list):
        return ["thiếu danh sách hàng (rows) ở báo cáo hoặc tham chiếu"]
    run_rows = [normalize_row(row) for row in run_rows_raw]
    ref_rows = [normalize_row(row) for row in ref_rows_raw]
    if any(row is None for row in run_rows):
        return ["một hàng của báo cáo lần chạy sai schema"]
    if any(row is None for row in ref_rows):
        return ["một hàng của tham chiếu 12.2 sai schema"]
    run_bpic = {
        _row_key(row): row
        for row in run_rows
        if row is not None and row["source"] == BPIC_TEST_SPLIT_SOURCE
    }
    ref_map = {_row_key(row): row for row in ref_rows if row is not None}
    gaps = _compare_row_maps(
        run_bpic,
        ref_map,
        "hàng thừa so với tham chiếu",
        "hàng thiếu so với tham chiếu",
    )
    gaps.extend(
        _metadata_gaps(
            run,
            reference,
            "báo cáo lần chạy thiếu metadata (code_commit/config_hash/...)",
            "tham chiếu 12.2 thiếu metadata (code_commit/config_hash/...)",
        )
    )
    return gaps


def compare_runs(first: dict[str, object], second: dict[str, object]) -> list[str]:
    """So hai báo cáo của hai lần chạy (job CI `--compare`); rỗng = trùng.

    Khác `compare_reports`: so TOÀN BỘ hàng cả hai phía (bộ chuẩn + BPIC)
    vì hai lần chạy cùng commit/cấu hình/dữ liệu phải cho cùng số. Dùng
    cho bước "so hai lần chạy" của job clean-machine; KHÔNG dùng cho bước
    8 (so với JSON đã ghi của 12.2) vì tham chiếu 12.2 chỉ có hàng BPIC.
    """
    first_rows_raw = first.get("rows")
    second_rows_raw = second.get("rows")
    if not isinstance(first_rows_raw, list) or not isinstance(second_rows_raw, list):
        return ["thiếu danh sách hàng (rows) ở báo cáo hoặc tham chiếu"]
    first_rows = [normalize_row(row) for row in first_rows_raw]
    second_rows = [normalize_row(row) for row in second_rows_raw]
    if any(row is None for row in first_rows):
        return ["một hàng của báo cáo thứ nhất sai schema"]
    if any(row is None for row in second_rows):
        return ["một hàng của báo cáo thứ hai sai schema"]
    first_map = {_row_key(row): row for row in first_rows if row is not None}
    second_map = {_row_key(row): row for row in second_rows if row is not None}
    gaps = _compare_row_maps(
        first_map,
        second_map,
        "hàng chỉ có ở lần chạy thứ nhất",
        "hàng chỉ có ở lần chạy thứ hai",
    )
    gaps.extend(
        _metadata_gaps(
            first,
            second,
            "báo cáo thứ nhất thiếu metadata (code_commit/config_hash/...)",
            "báo cáo thứ hai thiếu metadata (code_commit/config_hash/...)",
        )
    )
    return gaps


#: Số case học/đo thật của từng đô thị (12.2 A.1, đo bằng lệnh chia).
_BPOC_SPLIT_COUNTS = {
    "m1": (719, 240),
    "m2": (499, 167),
    "m3": (846, 282),
    "m4": (631, 211),
    "m5": (694, 232),
}


def _mock_bpic_rows() -> list[dict[str, object]]:
    """35 hàng BPIC giả, xác định (MOCK — không phải đo thật).

    Mỗi chỉ số suy từ băm SHA-256 của (tenant, điều kiện, tên chỉ số) nên
    chạy lại cho cùng số — phép so run1-vs-run2 ở chế độ smoke có ý
    nghĩa. Số case học/đo là số thật (12.2 A.1); `n_reference`/`n_rules`
    là số giả hợp lý. Chỉ dùng khi `--smoke` hoặc khi test chèn driver
    giả; đường full không bao giờ gọi hàm này.
    """
    rows: list[dict[str, object]] = []
    for dataset in BPIC2015_DATASETS:
        tenant = dataset.slug
        n_train, n_measure = _BPOC_SPLIT_COUNTS[tenant]
        for condition in CONDITIONS:
            metrics: dict[str, dict[str, float]] = {}
            for name in METRIC_NAMES:
                digest = hashlib.sha256(f"{tenant}:{condition}:{name}".encode()).hexdigest()
                value = int(digest[:8], 16) / 0xFFFFFFFF
                value = 0.05 + 0.9 * value
                metrics[name] = {
                    "value": round(value, 4),
                    "lower": round(max(0.0, value - 0.05), 4),
                    "upper": round(min(1.0, value + 0.05), 4),
                }
            counts_digest = hashlib.sha256(f"{tenant}:{condition}:counts".encode()).hexdigest()
            rows.append(
                {
                    "tenant_id": tenant,
                    "condition": condition,
                    "source": BPIC_TEST_SPLIT_SOURCE,
                    "n_train": n_train,
                    "n_measure": n_measure,
                    "n_reference": 1000 + int(counts_digest[:4], 16) % 800,
                    "n_rules": 20 + int(counts_digest[4:8], 16) % 60,
                    "metrics": metrics,
                }
            )
    return rows


def _mock_bpic_runner(_config: Path, _lock: Path, report_path: Path) -> int:
    """Adapter: driver giả khớp chữ ký runner (bỏ qua config/lock)."""
    return _mock_bpic_driver(report_path)


def _mock_bpic_driver(report_path: Path) -> int:
    """Driver BPIC giả: ghi báo cáo giả (35 hàng MOCK), trả 0.

    Báo cáo giả mang metadata rõ ràng là mock (`code_commit="mock"`,
    ghi chú "MOCK DRIVER") để không ai tưởng là số đo thật. Dùng cho
    `--smoke` và test; đường full gọi driver thật qua `_run_bpic_driver`.
    """
    report = {
        "code_commit": "mock",
        "config_hash": "mock",
        "data_hash": "mock",
        "seed": 0,
        "model_id": "mock",
        "model_revision": "mock",
        "cache_intact": True,
        "note": "MOCK DRIVER — không phải đo thật (chế độ smoke / test).",
        "rows": _mock_bpic_rows(),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


def _run_bpic_driver(config_path: Path, lock_path: Path, report_path: Path) -> int:
    """Chạy driver đo BPIC thật (12.2) qua tiến trình con, trả mã thoát của nó.

    Driver là CLI `python -m praxon_core.eval.bpic_measure` với cờ
    `--config`/`--lock` (hai file khóa), `--report` (JSON ra) và
    `--allow-rerun` (lần chạy 13.1 là phép kiểm tái lập, như 12.3 — xem
    12.2 A.5). Thiếu module driver thì raise `FileNotFoundError` để
    `run_phase1` thoát 2 rõ ràng thay vì chạy với số giả im lặng. Mã
    thoát của driver đổi sang mã của 13.1: 0 giữ nguyên, 1/2 (lỗi dữ
    liệu/DB) thành 1, 3 (`budget_exceeded`) giữ nguyên 3.
    """
    if importlib.util.find_spec(BPIC_DRIVER_MODULE) is None:
        raise FileNotFoundError(
            f"driver đo BPIC chưa có: module {BPIC_DRIVER_MODULE} "
            "chưa tồn tại trong repo (task 12.2 chưa viết code). "
            "Chạy ở chế độ --smoke để dùng driver giả, hoặc chờ driver thật."
        )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            BPIC_DRIVER_MODULE,
            "--config",
            str(config_path),
            "--lock",
            str(lock_path),
            "--report",
            str(report_path),
            "--allow-rerun",
        ],
        text=True,
        timeout=21600,
        check=False,
    )
    if result.returncode == 0:
        return 0
    if result.returncode == 3:
        return 3
    return 1


def _download_wabo_html(cache_dir: Path) -> Path:
    """Tải HTML Wabo từ URL trong bảng gắn 9.2 (chỉ khi thiếu trong cache)."""
    mapping = default_dutch_mapping()
    target = cache_dir / "wabo" / WABO_DEFAULT_HTML_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(mapping.wabo.source_url, target)
    except urllib.error.URLError as exc:
        raise ValueError(
            f"không tải được HTML Wabo từ {mapping.wabo.source_url}: {exc}"
        ) from exc
    return target


def _ensure_bpic_data(cache_dir: Path) -> str:
    """Đảm bảo đủ 5 file XES trong cache (tải nếu thiếu, kiểm md5); trả nửa BPIC."""
    bpic_dir = cache_dir / "bpic2015"
    missing = [
        dataset.xes_filename
        for dataset in BPIC2015_DATASETS
        if not (bpic_dir / dataset.xes_filename).is_file()
    ]
    if missing:
        download_all_bpic2015(bpic_dir)
    return _bpic_half_hash(bpic_dir)


def _extract_document_rules(settings: Settings, cache_dir: Path) -> frozenset[Rule]:
    """Trích luật Wabo bằng model service (đúng đường `wabo_rules.main`).

    Cần model service sống (qua proxy chèn khóa — xem `tools/llm_auth_proxy.py`).
    Seed trích là 42 (trùng lần trích 9.1), không phải seed khóa — xem ghi
    chú module. Lỗi dữ liệu (thiếu tệp / SHA lệch) raise
    `FileNotFoundError`/`ValueError`; lỗi mô hình raise `ModelCallError`/
    `ReflectorBatchError`; chạm trần raise `BudgetExceededError`.
    """
    from praxon_core.adapters.language_model import ModelCallError
    from praxon_core.learning.reflector import ReflectorBatchError

    mapping = default_dutch_mapping()
    html_path = cache_dir / "wabo" / WABO_DEFAULT_HTML_FILENAME
    if not html_path.is_file():
        _download_wabo_html(cache_dir)
    document = load_wabo_document(html_path, mapping=mapping)
    traces = load_bpic_traces(cache_dir / "bpic2015")
    policy = default_rule_table().policy
    reflector = build_reflector(settings, seed=WABO_EXTRACT_SEED)
    try:
        extraction = extract_wabo_rules(
            reflect_document=reflector.reflect_document,
            document=document,
            mapping=mapping,
            traces=traces,
            policy=policy,
        )
    except (ModelCallError, ReflectorBatchError):
        raise
    return frozenset(outcome.rule for outcome in extraction.outcomes if outcome.accepted)


def _format_bpic_rows(rows: list[dict[str, object]]) -> str:
    """In hàng BPIC thành bảng đọc được (cùng dạng `format_experiments_report`)."""
    lines = ["BPIC 2015 (phần đo, driver 12.2):"]
    header = (
        f"{'tenant':<6}{'điều kiện':<22}{'precision':>18}"
        f"{'recall':>18}{'vi phạm':>18}{'chuyển âm':>18}"
    )
    lines.append(header)
    for row in sorted(rows, key=_row_key):
        metrics = cast(dict[str, dict[str, float]], row["metrics"])
        cells = []
        for name in METRIC_NAMES:
            entry = metrics[name]
            cells.append(f"{entry['value']:.4f} [{entry['lower']:.4f}, {entry['upper']:.4f}]")
        lines.append(
            f"{row['tenant_id']!s:<6}{row['condition']!s:<22}"
            + "".join(f"{cell:>18}" for cell in cells)
        )
    return "\n".join(lines)


def _sorted_rows(rows: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    """Hàng báo cáo theo thứ tự cố định (nguồn, tenant, điều kiện) để JSON xác định."""
    return sorted(rows, key=_row_key)


def _s3_keys_missing(settings: Settings, smoke: bool) -> bool:
    """Trả True khi bước kiểm key B2 phải chặn.

    Khóa bắt `checkpoint_store="s3"`, không phải chế độ smoke, mà thiếu một
    trong hai key B2.

    Chế độ smoke được miễn vì nó không bao giờ chạm S3: driver BPIC giả chỉ
    ghi JSON cục bộ, trích Wabo bị bỏ qua, không khởi tạo checkpoint store.
    13.1 A.3 viết cho lần chạy đo thật nên lần chạy không-smoke thiếu key
    vẫn chặn fail-closed, không tự đổi sang "local".
    """
    return (
        settings.checkpoint_store == "s3"
        and not smoke
        and (not settings.s3_access_key_id or not settings.s3_secret_access_key)
    )


def run_phase1(
    *,
    config_path: Path,
    lock_path: Path,
    reference_path: Path,
    out_dir: Path,
    cache_dir: Path,
    smoke: bool = False,
    code_commit: str | None = None,
    bpic_runner: Callable[[Path, Path, Path], int] | None = None,
    extract_rules: Callable[[Settings, Path], frozenset[Rule]] | None = None,
) -> int:
    """Chạy toàn bộ đánh giá giai đoạn 1; trả mã thoát 0/1/2/3/4 (xem docstring module)."""
    started = time.monotonic()
    root = _repo_root()
    config_path = config_path if config_path.is_absolute() else root / config_path
    lock_path = lock_path if lock_path.is_absolute() else root / lock_path
    reference_path = reference_path if reference_path.is_absolute() else root / reference_path
    out_dir = out_dir if out_dir.is_absolute() else root / out_dir
    # 1. Nạp cấu hình khóa — lệch/thiếu thì thoát 2, chưa chạy gì.
    try:
        settings, locked_hash = load_locked_config(config_path, lock_path)
        lock_seed = _read_lock_seed(lock_path)
    except ValueError as exc:
        print(f"lỗi khóa: {exc}", file=sys.stderr)
        return 2
    # Cấu hình khóa bắt checkpoint_store="s3" thì key B2 phải có; thiếu thì
    # thoát 2 fail-closed, không tự đổi sang "local" (13.1 A.3). Chế độ
    # smoke được miễn (xem `_s3_keys_missing`): smoke không chạm S3.
    if _s3_keys_missing(settings, smoke):
        print(
            'lỗi cấu hình: cấu hình khóa bắt checkpoint_store="s3" nhưng '
            "thiếu key B2 (PRAXON_S3_ACCESS_KEY_ID / PRAXON_S3_SECRET_ACCESS_KEY)",
            file=sys.stderr,
        )
        return 2
    if not settings.database_url:
        print(
            "lỗi cấu hình: thiếu database_url (đặt PRAXON_DATABASE_URL)",
            file=sys.stderr,
        )
        return 2
    # 2. Áp migration lên db.
    try:
        migrate.apply(settings.database_url)
    except Exception as exc:  # DB lỗi là lỗi hạ tầng, thoát 1
        print(f"lỗi cơ sở dữ liệu: {exc}", file=sys.stderr)
        return 1
    # 3. Đảm bảo dữ liệu BPIC (tải nếu thiếu, kiểm md5); tính nửa BPIC.
    try:
        bpic_half = _ensure_bpic_data(cache_dir)
    except Exception as exc:  # thiếu/sai dữ liệu, thoát 1
        print(f"lỗi dữ liệu: {exc}", file=sys.stderr)
        return 1
    # 4. Trích luật Wabo (bỏ qua ở chế độ smoke — luật tài liệu rỗng).
    if smoke:
        print("MOCK: chế độ smoke — bỏ qua trích Wabo, luật tài liệu rỗng.")
        document_rules: frozenset[Rule] = frozenset()
    else:
        extract = extract_rules or _extract_document_rules
        try:
            document_rules = extract(settings, cache_dir)
        except BudgetExceededError as exc:
            print(f"chạm trần token: {exc}", file=sys.stderr)
            return 3
        except (FileNotFoundError, ValueError) as exc:
            print(f"lỗi dữ liệu: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:  # lỗi mô hình, thoát 1
            print(f"lỗi mô hình: {exc}", file=sys.stderr)
            return 1
    # 5. Bảy điều kiện trên bộ chuẩn bán tổng hợp (không gọi mô hình).
    n_cases = SMOKE_N_CASES if smoke else SYNTHETIC_N_CASES
    n_draws = SMOKE_N_DRAWS if smoke else settings.bootstrap_draws
    try:
        synthetic = run_experiments(
            seed=SYNTHETIC_SEED,
            n_cases=n_cases,
            n_draws=n_draws,
            document_rules=document_rules,
        )
    except BudgetExceededError as exc:
        print(f"chạm trần token: {exc}", file=sys.stderr)
        return 3
    # 6. Bảy điều kiện trên phần đo BPIC 2015 bằng driver 12.2.
    bpic_report_path = out_dir / "bpic-driver-report.json"
    runner: Callable[[Path, Path, Path], int]
    if smoke and bpic_runner is None:
        runner = _mock_bpic_runner
    else:
        runner = bpic_runner or _run_bpic_driver
    try:
        driver_code = runner(config_path, lock_path, bpic_report_path)
    except FileNotFoundError as exc:
        print(f"lỗi driver: {exc}", file=sys.stderr)
        return 2
    except BudgetExceededError as exc:
        print(f"chạm trần token: {exc}", file=sys.stderr)
        return 3
    if driver_code != 0:
        print(f"driver đo BPIC thoát mã {driver_code}", file=sys.stderr)
        # Giữ nguyên ngữ nghĩa mã thoát của driver (1 dữ liệu, 2 khóa/cấu
        # hình, 3 trần token); mã lạ thì gộp về 1 (lỗi chung).
        return driver_code if driver_code in (1, 2, 3) else 1
    try:
        bpic_report = json.loads(bpic_report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"lỗi dữ liệu: không đọc được báo cáo driver: {exc}", file=sys.stderr)
        return 1
    if not isinstance(bpic_report, dict) or not isinstance(bpic_report.get("rows"), list):
        print("lỗi dữ liệu: báo cáo driver sai schema (thiếu rows)", file=sys.stderr)
        return 1
    bpic_rows = [row for row in (normalize_row(r) for r in bpic_report["rows"]) if row]
    if len(bpic_rows) != len(bpic_report["rows"]):
        print("lỗi dữ liệu: một hàng BPIC của driver sai schema", file=sys.stderr)
        return 1
    # 7. In bốn chỉ số + bản ghi ra stdout + JSON.
    commit = _current_code_commit(code_commit)
    bpic_data_hash = merge_data_hash(bpic_hash=bpic_half)
    full_data_hash = merge_data_hash(
        bpic_hash=bpic_half,
        generator_hash=_generator_half_hash(seed=SYNTHETIC_SEED, n_cases=n_cases),
    )
    synthetic_rows = [_row_dict(row) for row in synthetic.rows]
    report = {
        "code_commit": commit,
        "config_hash": locked_hash,
        "data_hash": full_data_hash,
        "seed": lock_seed,
        "model_id": settings.model_id,
        "model_revision": settings.model_revision,
        "cache_intact": True,
        "note": synthetic.note,
        "rows": _sorted_rows([*synthetic_rows, *bpic_rows]),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / REPORT_FILENAME
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(format_experiments_report(synthetic))
    print(_format_bpic_rows(bpic_rows))
    wall_time = time.monotonic() - started
    print(
        f"bản ghi lần chạy: code_commit={commit}, config_hash={locked_hash[:12]}..., "
        f"data_hash(bpic)={bpic_data_hash[:12]}..., seed={lock_seed}, "
        f"model={settings.model_id}@{settings.model_revision[:12]}, "
        f"giờ chạy={wall_time:.1f}s"
    )
    print(f"báo cáo JSON: {report_path}")
    # 8. So với JSON đã ghi của 12.2 (chỉ hàng BPIC có tham chiếu).
    if not reference_path.is_file():
        print(
            "CẢNH BÁO: chưa có JSON đã ghi của 12.2 "
            f"({reference_path}) — bỏ qua bước so sánh, "
            "lần chạy này chưa chứng minh được tái lập.",
        )
        return 0
    try:
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"lỗi dữ liệu: không đọc được tham chiếu 12.2: {exc}", file=sys.stderr)
        return 2
    if not isinstance(reference, dict):
        print("lỗi dữ liệu: tham chiếu 12.2 sai schema", file=sys.stderr)
        return 2
    comparison_run = dict(report)
    comparison_run["data_hash"] = bpic_data_hash
    gaps = compare_reports(comparison_run, reference)
    if gaps:
        print("KHÔNG TRÙNG số đã ghi của 12.2:")
        for gap in gaps:
            print(f"  - {gap}")
        return 4
    print("TRÙNG số đã ghi của 12.2.")
    return 0


def _load_report(path: Path) -> dict[str, object] | None:
    """Đọc một báo cáo JSON; `None` khi thiếu/sai."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def main(argv: list[str] | None = None) -> int:
    """Lệnh `python -m praxon_core.eval.run_all` (xem docstring module)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="tệp TOML cấu hình khóa (mặc định %(default)s)",
    )
    parser.add_argument(
        "--lock",
        type=Path,
        default=DEFAULT_LOCK_PATH,
        help="bản ghi khóa (mặc định %(default)s)",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=DEFAULT_REFERENCE_PATH,
        help="JSON đã ghi của 12.2 để so (mặc định %(default)s)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("out"),
        help="thư mục ghi báo cáo JSON (mặc định %(default)s)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / ".cache" / "praxon",
        help="thư mục cache chứa wabo/ và bpic2015/ (mặc định %(default)s)",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="lát cắt nhỏ: bỏ qua trích Wabo, bộ chuẩn rút gọn, driver BPIC giả",
    )
    parser.add_argument(
        "--code-commit",
        default=None,
        help="code_commit ghi vào báo cáo (mặc định: git rev-parse HEAD)",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        type=Path,
        metavar=("A", "B"),
        help="so hai báo cáo JSON của hai lần chạy (A lần 1, B lần 2): 0 trùng, 4 lệch",
    )
    args = parser.parse_args(argv)
    if args.compare is not None:
        first = _load_report(args.compare[0])
        second = _load_report(args.compare[1])
        if first is None or second is None:
            print("lỗi dữ liệu: không đọc được một trong hai báo cáo", file=sys.stderr)
            return 2
        gaps = compare_runs(first, second)
        if gaps:
            print("Hai báo cáo KHÔNG trùng:")
            for gap in gaps:
                print(f"  - {gap}")
            return 4
        print("Hai báo cáo trùng nhau.")
        return 0
    return run_phase1(
        config_path=args.config,
        lock_path=args.lock,
        reference_path=args.reference,
        out_dir=args.out,
        cache_dir=args.cache_dir,
        smoke=args.smoke,
        code_commit=args.code_commit,
    )


if __name__ == "__main__":
    raise SystemExit(main())
