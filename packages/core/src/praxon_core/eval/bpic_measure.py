"""Driver đo BPIC 2015 một lần (task 12.2, spec dòng 31/152).

Lệnh (`python -m praxon_core.eval.bpic_measure`): đọc cấu hình đã khóa
(12.1), chạy bảy điều kiện trên phần đo (20%) của năm đô thị BPIC 2015,
in bốn chỉ số theo từng tenant kèm khoảng tin cậy 95%, ghi 35 hàng `run`
+ 35 event vào Postgres và một báo cáo JSON. Chỉ CPU, không gọi mô hình:
module này không import `Reflector`/`model_from_settings` (review bắt
bằng grep); `tokens_in`/`tokens_out` của cả 35 hàng đều bằng 0.

Thứ tự chạy: điều kiện 1-6 cho cả năm tenant (m1 -> m5), rồi điều kiện 7
(chọn nền theo F1 trung bình của điều kiện 5 và 6). Điều kiện 2 (Cách ly)
chia sẻ đúng một hàng đo với điều kiện 1 (như `run_experiments`); điều
kiện 7 chia sẻ hàng của nền tốt hơn khi tập luật tài liệu rỗng. Mỗi cặp
(điều kiện, tenant) ghi đúng một hàng `run` + một event, một giao dịch
cho mỗi tenant gồm 7 cặp.

Mã thoát: 0 = cả 35 cặp succeeded; 1 = lỗi dữ liệu/khóa (thiếu file,
hash lệch, file luật sai, đã công bố rồi, một cặp failed); 2 = lỗi DB;
3 = `budget_exceeded` (giữ chỗ theo quy ước mã thoát với 10.4 - không
thể xảy ra ở driver này vì không gọi mô hình, nên không có đường nào
trả 3).

Mật khẩu của năm vai `<tenant>__coordinator` lấy từ phần mật khẩu của
`settings.database_url` (qua `PRAXON_DATABASE_URL`): driver chỉ đổi user
thành `<tenant>__coordinator`, giữ nguyên mật khẩu trong DSN. Cách này
giữ đúng cổng `check_env_access` (chỉ `settings.py` được đọc biến môi
trường) mà không thêm trường vào `Settings` - thêm trường sẽ đổi
`config_hash` và phá khóa 12.1 đã chốt (13 trường trong hash). Kết nối mở
qua `repositories.migrate._connect` (nơi duy nhất được import driver DB
theo hợp đồng `driver-db-chi-trong-repositories`); module này không
import `psycopg` trực tiếp.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import tomllib
import urllib.parse
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from praxon_core.datasets.bpic2015 import BPIC2015_DATASETS, DEFAULT_CACHE_DIR
from praxon_core.datasets.split import (
    SplitFractions,
    compute_data_hash,
    split_log,
)
from praxon_core.declare.miner import Rule, discover
from praxon_core.eval.experiments import (
    CONDITIONS,
    CONSENSUS,
    DECLARE_ONLY,
    DOCUMENT,
    GLOBAL_TENANT_ID,
    ISOLATION,
    POOLED,
    VETO,
    VOTING,
    TenantData,
    condition_fact_sets,
)
from praxon_core.eval.ground_truth import (
    GROUND_TRUTH_CONFIDENCE,
    GROUND_TRUTH_SUPPORT,
    facts_from_rules,
    ground_truth_from_test_traces,
)
from praxon_core.eval.metrics import Fact, FactScope, f1_score
from praxon_core.eval.report import (
    TenantConditionRow,
    metrics_with_ci,
    traces_for_case_ids,
)
from praxon_core.learning.candidate import FactStatus
from praxon_core.learning.coordinator import merge_data_hash
from praxon_core.learning.test_split_lock import load_locked_config
from praxon_core.repositories.events import EventRow, insert_event
from praxon_core.repositories.migrate import _connect
from praxon_core.repositories.runs import RunRow, insert_run
from praxon_core.settings import Settings

EXIT_OK = 0
"""Cả 35 cặp succeeded."""

EXIT_DATA = 1
"""Lỗi dữ liệu/khóa (thiếu file, hash lệch, file luật sai, đã công bố
rồi, một cặp failed)."""

EXIT_DB = 2
"""Lỗi DB (không nối được, ghi hàng thất bại)."""

EXIT_BUDGET_EXCEEDED = 3
"""Giữ chỗ theo quy ước với 10.4; driver này không gọi mô hình nên không
có đường nào trả mã này."""

_DOC_LAW_KEY_RE = re.compile(r"^(response|precedence)\((.+), (.+)\)$")
"""Khóa canonical: `mẫu(hoạt động thứ nhất, hoạt động thứ hai)`."""

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
"""Một băm SHA-256 hex (64 ký tự)."""


@dataclass(frozen=True)
class LockRecord:
    """Các trường trong bản ghi khóa mà driver dùng (ngoài hash đã khóa)."""

    seed: int
    model_id: str
    model_revision: str
    data_hash: str
    locked_config_hash: str


@dataclass(frozen=True)
class DocLawProvenance:
    """Đầu mục provenance của file luật tài liệu (A.7).

    Chỉ `model_id`/`model_revision` được đối chiếu với bản ghi khóa (R8);
    các trường còn lại là thông tin ghi vào báo cáo.
    """

    model_id: str
    model_revision: str
    extracted_at: str = ""
    seed: int = 0
    beta_support: float = 0.0
    beta_confidence: float = 0.0
    n_rules_extracted: int = 0
    n_rules_gated: int = 0


def _read_lock_record(lock_path: Path) -> LockRecord:
    """Đọc các trường driver dùng trong bản ghi khóa (12.1, A.2).

    Thiếu file, sai TOML, thiếu trường, hoặc trường sai kiểu/rỗng thì
    raise `ValueError`: không chạy đo với khóa không đọc được.
    """
    try:
        raw = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"không đọc được bản ghi khóa {lock_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"bản ghi khóa {lock_path} sai TOML: {exc}") from exc
    locked = raw.get("locked_config_hash")
    seed = raw.get("seed")
    model_id = raw.get("model_id")
    model_revision = raw.get("model_revision")
    data_hash = raw.get("data_hash")
    if not isinstance(locked, str) or not locked:
        raise ValueError(f"bản ghi khóa {lock_path} thiếu locked_config_hash")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError(f"bản ghi khóa {lock_path} thiếu seed (số nguyên)")
    if not isinstance(model_id, str) or not model_id:
        raise ValueError(f"bản ghi khóa {lock_path} thiếu model_id")
    if not isinstance(model_revision, str) or not model_revision:
        raise ValueError(f"bản ghi khóa {lock_path} thiếu model_revision")
    if not isinstance(data_hash, str) or not _HEX64_RE.match(data_hash):
        raise ValueError(f"bản ghi khóa {lock_path} thiếu data_hash (hex 64 ký tự)")
    return LockRecord(
        seed=seed,
        model_id=model_id,
        model_revision=model_revision,
        data_hash=data_hash,
        locked_config_hash=locked,
    )


def _load_and_check_lock(config_path: Path, lock_path: Path) -> tuple[Settings, LockRecord]:
    """Nạp cấu hình đã khóa + bản ghi khóa; lệch thì từ chối trước khi đo.

    `load_locked_config` đối chiếu `config_hash` tính từ TOML với
    `locked_config_hash`; `_read_lock_record` kiểm các trường còn lại.
    """
    settings, locked_hash = load_locked_config(config_path, lock_path)
    record = _read_lock_record(lock_path)
    if record.locked_config_hash != locked_hash:
        raise ValueError(
            f"bản ghi khóa {lock_path} đổi giữa hai lần đọc "
            f"({locked_hash[:12]}... khác {record.locked_config_hash[:12]}...)"
        )
    return settings, record


def _parse_doc_law_key(key: str) -> Rule:
    """Một khóa canonical thành luật Declare (để đổi thành fact `global`).

    Khóa lạ (sai mẫu, sai định dạng, hoạt động chứa `", "`) thì raise
    `ValueError`: driver từ chối chạy thay vì bỏ qua im lặng (A.7).
    `support`/`confidence` đặt 0 vì `facts_from_rules` chỉ dùng
    `canonical_key`/`template`/`first`/`second` của luật.
    """
    match = _DOC_LAW_KEY_RE.match(key)
    if match is None:
        raise ValueError(f"khóa luật tài liệu lạ: {key!r}")
    template, first, second = match.groups()
    if ", " in first or ", " in second:
        raise ValueError(f"khóa luật tài liệu mơ hồ (hoạt động chứa ', '): {key!r}")
    return Rule(template, first, second, 0.0, 0.0)


def _read_doc_law_file(
    path: Path, *, model_id: str, model_revision: str
) -> tuple[DocLawProvenance, tuple[Rule, ...]]:
    """Đọc file luật tài liệu (A.7): đầu mục `# key: value` + khóa mỗi dòng.

    Đầu mục phải ghi `model_id`/`model_revision` trùng bản ghi khóa (R8);
    lệch thì từ chối. Các khóa phải đã sắp xếp, không trùng, parse được;
    sai một khóa thì từ chối cả file.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"không đọc được file luật tài liệu {path}: {exc}") from exc
    header: dict[str, str] = {}
    keys: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            body = stripped[1:].strip()
            if ":" in body:
                name, value = body.split(":", 1)
                header[name.strip()] = value.strip()
            continue
        keys.append(stripped)
    file_model = header.get("model_id", "")
    file_revision = header.get("model_revision", "")
    if file_model != model_id or file_revision != model_revision:
        raise ValueError(
            "file luật tài liệu sai provenance "
            f"(model {file_model}/{file_revision} khác khóa {model_id}/{model_revision})"
        )
    if keys != sorted(keys):
        raise ValueError(f"file luật tài liệu {path}: các khóa chưa sắp xếp")
    if len(set(keys)) != len(keys):
        raise ValueError(f"file luật tài liệu {path}: có khóa trùng nhau")
    rules = tuple(_parse_doc_law_key(key) for key in keys)

    def _header_int(name: str) -> int:
        try:
            return int(header.get(name, "0"))
        except ValueError:
            return 0

    def _header_float(name: str) -> float:
        try:
            return float(header.get(name, "0"))
        except ValueError:
            return 0.0

    provenance = DocLawProvenance(
        model_id=file_model,
        model_revision=file_revision,
        extracted_at=header.get("extracted_at", ""),
        seed=_header_int("seed"),
        beta_support=_header_float("beta_support"),
        beta_confidence=_header_float("beta_confidence"),
        n_rules_extracted=_header_int("n_rules_extracted"),
        n_rules_gated=_header_int("n_rules_gated"),
    )
    return provenance, rules


def _bpic_data_hash(file_hashes: tuple[str, ...], municipalities: tuple[int, ...]) -> str:
    """Nửa BPIC của `data_hash`: băm tệp log + tỉ lệ chia + tenant (3.3).

    Cùng cách tính với lệnh `python -m praxon_core.datasets.split`
    (in `data_hash chung` khi chia cả năm đô thị).
    """
    return compute_data_hash(
        log_hashes=file_hashes,
        fractions=SplitFractions(),
        tenants=municipalities,
    )


def _dsn_for_tenant(base_dsn: str, tenant_id: str) -> str:
    """DSN cho vai `<tenant>__coordinator` từ DSN gốc (đổi user, giữ mật khẩu).

    Cùng mẫu `tests/integration/conftest.py`: giữ scheme/host/port/db,
    chỉ thay user thành `<tenant>__coordinator`; mật khẩu trong DSN gốc
    là mật khẩu chung của năm vai (lúc provision truyền cùng mật khẩu
    cho cả năm tenant). DSN gốc không có mật khẩu thì DSN suy ra cũng
    không có (dùng khi pg_hba là `trust`).
    """
    parts = urllib.parse.urlsplit(base_dsn)
    host = parts.hostname or "localhost"
    port = parts.port or 5432
    user = f"{tenant_id}__coordinator"
    if parts.password is None:
        netloc = f"{user}@{host}:{port}"
    else:
        netloc = f"{user}:{urllib.parse.quote(parts.password)}@{host}:{port}"
    path = parts.path or "/praxon"
    return urllib.parse.urlunsplit((parts.scheme, netloc, path, parts.query, ""))


class _RowCursor(Protocol):
    """Con trỏ chỉ đọc một hàng (phần nhỏ driver tự truy vấn)."""

    def fetchone(self) -> tuple[Any, ...] | None: ...


class _Executor(Protocol):
    """Kết nối DB ở mức driver tự truy vấn (chỉ `SELECT COUNT(*)` chốt).

    Dùng Protocol thay cho kiểu `Connection` của psycopg vì chỉ repositories
    được import driver DB (hợp đồng driver-db-chi-trong-repositories);
    kết nối thật do `repositories.migrate._connect` mở.
    """

    def execute(self, query: str, params: Sequence[Any] | None = None) -> _RowCursor: ...


def _count_published(
    conn: _Executor,
    *,
    tenant_id: str,
    config_hash: str,
    data_hash: str,
    code_commit: str,
    seed: int,
) -> int:
    """Số hàng `run` succeeded của một tenant khớp lần chạy đang xét.

    Vai coordinator chỉ thấy hàng của chính tenant đó (RLS) nên đếm theo
    tenant rồi cộng lại ở ngoài.
    """
    row = conn.execute(
        "SELECT COUNT(*) FROM run WHERE tenant_id = %s AND status = 'succeeded' "
        "AND config_hash = %s AND data_hash = %s AND code_commit = %s AND seed = %s",
        (tenant_id, config_hash, data_hash, code_commit, seed),
    ).fetchone()
    assert row is not None
    return int(row[0])


def _repo_root() -> Path:
    """Thư mục gốc của repo (đi lên từ file này tới khi gặp `.git`).

    Worktree có `.git` là tệp (không phải thư mục) nên chỉ kiểm tồn tại.
    """
    current = Path(__file__).resolve().parent
    while True:
        if (current / ".git").exists():
            return current
        if current.parent == current:
            raise ValueError("không tìm được thư mục gốc của repo (thiếu .git)")
        current = current.parent


def _code_commit() -> str:
    """Mã commit lúc chạy (`git rev-parse HEAD`); không lấy được thì từ chối."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise ValueError(f"không lấy được code_commit (git rev-parse HEAD): {exc}") from exc
    commit = result.stdout.strip()
    if len(commit) != 40 or not _HEX40_RE.match(commit):
        raise ValueError(f"code_commit không hợp lệ: {commit!r}")
    return commit


def _measure(
    *,
    tenant: TenantData,
    facts: Sequence[Fact],
    condition: str,
    n_draws: int,
    seed: int,
) -> TenantConditionRow:
    """Đo một tenant trong một điều kiện: bốn chỉ số kèm khoảng tin cậy.

    Cùng hình dạng `_evaluate` của `experiments.py` (lọc fact `active`,
    `metrics_with_ci`); không viết lại cách tính chỉ số.
    """
    active = [fact for fact in facts if fact.status is FactStatus.ACTIVE]
    return TenantConditionRow(
        tenant_id=tenant.tenant_id,
        condition=condition,
        source=tenant.ground_truth.source,
        n_train=len(tenant.train_traces),
        n_measure=len(tenant.measure_traces),
        n_reference=len(tenant.ground_truth.reference),
        n_rules=len(active),
        metrics=metrics_with_ci(
            facts,
            tenant.ground_truth.reference,
            tenant.measure_traces,
            tenant.tenant_id,
            n_draws=n_draws,
            seed=seed,
            condition=condition,
        ),
    )


def _mean_f1(rows: list[TenantConditionRow]) -> float:
    """F1 trung bình qua các tenant (tiêu chí chọn nền cho điều kiện 7)."""
    if not rows:
        return 0.0
    return sum(
        f1_score(row.metrics.precision.value, row.metrics.recall.value) for row in rows
    ) / len(rows)


def _row_payload_json(row: TenantConditionRow) -> dict[str, Any]:
    """Hàng báo cáo thành JSON (8 trường của `TenantConditionRow`)."""
    return {
        "tenant_id": row.tenant_id,
        "condition": row.condition,
        "source": row.source,
        "n_train": row.n_train,
        "n_measure": row.n_measure,
        "n_reference": row.n_reference,
        "n_rules": row.n_rules,
        "metrics": {
            "precision": {
                "value": row.metrics.precision.value,
                "lower": row.metrics.precision.lower,
                "upper": row.metrics.precision.upper,
            },
            "recall": {
                "value": row.metrics.recall.value,
                "lower": row.metrics.recall.lower,
                "upper": row.metrics.recall.upper,
            },
            "violation_rate": {
                "value": row.metrics.violation_rate.value,
                "lower": row.metrics.violation_rate.lower,
                "upper": row.metrics.violation_rate.upper,
            },
            "negative_transfer": {
                "value": row.metrics.negative_transfer.value,
                "lower": row.metrics.negative_transfer.lower,
                "upper": row.metrics.negative_transfer.upper,
            },
        },
    }


def _payload_hash(payload: dict[str, Any]) -> str:
    """SHA-256 của một hàng đã chuẩn hóa JSON (ghi vào event)."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _format_metric(value: float, lower: float, upper: float) -> str:
    """Một chỉ số thành `giá trị [cận dưới, cận trên]`."""
    return f"{value:.3f} [{lower:.3f}, {upper:.3f}]"


def _format_text_report(
    rows: list[dict[str, Any]], *, note: str, published: bool, wall_time: float
) -> str:
    """Báo cáo đo thành văn bản (in ra stdout sau lần chạy)."""
    lines = [
        "Báo cáo đo BPIC 2015 (task 12.2)",
        f"Đã công bố: {'có' if published else 'không (lần chạy hỏng)'}; "
        f"giờ chạy: {wall_time:.1f} giây",
        "",
        note,
        "",
    ]
    for row in rows:
        metrics = row["metrics"]
        if metrics is None:
            lines.append(
                f"Tenant {row['tenant_id']} - {row['condition']}: FAILED "
                f"({row.get('reason', '')})"
            )
            continue
        lines.append(
            f"Tenant {row['tenant_id']} - {row['condition']} "
            f"(đáp án: {row['source']}; học {row['n_train']} trace, "
            f"đo {row['n_measure']} trace; đáp án {row['n_reference']} luật, "
            f"khám phá {row['n_rules']} luật)"
        )
        lines.append(
            "  precision:        "
            + _format_metric(
                metrics["precision"]["value"],
                metrics["precision"]["lower"],
                metrics["precision"]["upper"],
            )
        )
        lines.append(
            "  recall:           "
            + _format_metric(
                metrics["recall"]["value"],
                metrics["recall"]["lower"],
                metrics["recall"]["upper"],
            )
        )
        lines.append(
            "  tỉ lệ vi phạm:    "
            + _format_metric(
                metrics["violation_rate"]["value"],
                metrics["violation_rate"]["lower"],
                metrics["violation_rate"]["upper"],
            )
        )
        lines.append(
            "  negative transfer: "
            + _format_metric(
                metrics["negative_transfer"]["value"],
                metrics["negative_transfer"]["lower"],
                metrics["negative_transfer"]["upper"],
            )
        )
    return "\n".join(lines)


def _load_tenant_data(
    *, cache_dir: Path
) -> tuple[list[TenantData], tuple[str, ...], tuple[int, ...]]:
    """Nạp 5 log BPIC 2015, chia 60/20/20, đáp án từ phần đo.

    Trả (danh sách tenant, băm tệp từng log, số hiệu đô thị) - băm tệp
    dùng để tính nửa BPIC của `data_hash` trước khi đo. Thiếu tệp thì
    raise `ValueError` (mã 1), chưa chạm phần đo để đo.
    """
    tenants: list[TenantData] = []
    file_hashes: list[str] = []
    municipalities: list[int] = []
    for dataset in BPIC2015_DATASETS:
        path = cache_dir / dataset.xes_filename
        if not path.is_file():
            raise ValueError(f"thiếu tệp log BPIC 2015: {path}")
        split = split_log(path, dataset.municipality)
        train = traces_for_case_ids(path, frozenset(split.train))
        measure = traces_for_case_ids(path, frozenset(split.test))
        tenants.append(
            TenantData(
                tenant_id=dataset.slug,
                train_traces=train,
                measure_traces=measure,
                ground_truth=ground_truth_from_test_traces(measure, tenant_id=dataset.slug),
                own_rules=discover(
                    train,
                    support=GROUND_TRUTH_SUPPORT,
                    confidence=GROUND_TRUTH_CONFIDENCE,
                ),
            )
        )
        file_hashes.append(split.file_sha256)
        municipalities.append(dataset.municipality)
    return tenants, tuple(file_hashes), tuple(municipalities)


def run(
    *,
    config_path: Path,
    lock_path: Path,
    doc_laws_path: Path,
    cache_dir: Path,
    report_path: Path,
    allow_rerun: bool,
    code_commit: str | None = None,
) -> int:
    """Chạy đo một lần: khóa -> kiểm tra trước -> đo 35 cặp -> ghi DB + báo cáo.

    Trả mã thoát (0/1/2; xem docstring module). Mọi kiểm tra fail-closed
    đều chạy TRƯỚC khi đo cặp nào: khóa lệch, file luật sai, `data_hash`
    lệch, không nối được DB, đã công bố rồi.
    """
    started = datetime.now(UTC)
    run_started = time.monotonic()
    try:
        settings, record = _load_and_check_lock(config_path, lock_path)
    except ValueError as exc:
        print(f"từ chối chạy đo: {exc}", file=sys.stderr)
        return EXIT_DATA
    try:
        provenance, doc_rules = _read_doc_law_file(
            doc_laws_path,
            model_id=record.model_id,
            model_revision=record.model_revision,
        )
    except ValueError as exc:
        print(f"từ chối chạy đo: {exc}", file=sys.stderr)
        return EXIT_DATA
    try:
        tenants, file_hashes, municipalities = _load_tenant_data(cache_dir=cache_dir)
    except ValueError as exc:
        print(f"từ chối chạy đo: {exc}", file=sys.stderr)
        return EXIT_DATA
    bpic_half = _bpic_data_hash(file_hashes, municipalities)
    data_hash = merge_data_hash(bpic_hash=bpic_half)
    if data_hash != record.data_hash:
        print(
            "từ chối chạy đo: data_hash tính lại "
            f"({data_hash[:12]}...) khác bản ghi khóa ({record.data_hash[:12]}...)",
            file=sys.stderr,
        )
        return EXIT_DATA
    if code_commit is None:
        try:
            code_commit = _code_commit()
        except ValueError as exc:
            print(f"từ chối chạy đo: {exc}", file=sys.stderr)
            return EXIT_DATA

    tenant_ids = [tenant.tenant_id for tenant in tenants]
    connections: dict[str, Any] = {}

    def close_all() -> None:
        """Đóng mọi kết nối đã mở (đường từ chối sớm cũng đóng)."""
        for conn in connections.values():
            with suppress(Exception):
                conn.close()

    try:
        for tenant_id in tenant_ids:
            try:
                conn = _connect(_dsn_for_tenant(settings.database_url, tenant_id))
            except Exception as exc:
                print(
                    f"lỗi DB: không nối được dưới vai {tenant_id}__coordinator: {exc}",
                    file=sys.stderr,
                )
                close_all()
                return EXIT_DB
            connections[tenant_id] = conn
            try:
                conn.execute("SELECT 1").fetchone()
            except Exception as exc:
                print(
                    f"lỗi DB: kiểm kết nối vai {tenant_id}__coordinator hỏng: {exc}",
                    file=sys.stderr,
                )
                close_all()
                return EXIT_DB
        published = sum(
            _count_published(
                connections[tenant_id],
                tenant_id=tenant_id,
                config_hash=record.locked_config_hash,
                data_hash=data_hash,
                code_commit=code_commit,
                seed=record.seed,
            )
            for tenant_id in tenant_ids
        )
        if published >= 35 and not allow_rerun:
            print(
                "từ chối chạy đo: đã có lần chạy công bố "
                f"({published} hàng succeeded khớp khóa/commit/seed này); "
                "chỉ 12.3 được chạy lại với --allow-rerun",
                file=sys.stderr,
            )
            close_all()
            return EXIT_DATA
    except Exception as exc:  # Lỗi DB lúc kiểm tra trước.
        print(f"lỗi DB: {exc}", file=sys.stderr)
        close_all()
        return EXIT_DB

    return _measure_and_write(
        tenants=tenants,
        connections=connections,
        settings=settings,
        record=record,
        data_hash=data_hash,
        code_commit=code_commit,
        doc_rules=doc_rules,
        provenance=provenance,
        report_path=report_path,
        allow_rerun=allow_rerun,
        started=started,
        run_started=run_started,
    )


class _DbError(Exception):
    """Lỗi DB lúc ghi hàng `run`/event (thoát mã 2)."""


def _measure_and_write(
    *,
    tenants: list[TenantData],
    connections: dict[str, Any],
    settings: Settings,
    record: LockRecord,
    data_hash: str,
    code_commit: str,
    doc_rules: tuple[Rule, ...],
    provenance: DocLawProvenance,
    report_path: Path,
    allow_rerun: bool,
    started: datetime,
    run_started: float,
) -> int:
    """Đo 35 cặp, ghi hàng `run` + event, in/ghi báo cáo.

    Một giao dịch cho mỗi tenant gồm 7 cặp; commit sau cặp thứ 7 của
    tenant đó. Cặp nào đo hỏng thì ghi hàng `failed` rồi đo tiếp; lỗi DB
    lúc ghi thì dừng cả lần chạy (mã 2).
    """
    n_draws = settings.bootstrap_draws
    seed = record.seed
    sets = condition_fact_sets(tenants)
    doc_facts = tuple(facts_from_rules(doc_rules, GLOBAL_TENANT_ID, scope=FactScope.GLOBAL))
    measured: dict[str, dict[str, TenantConditionRow]] = {}
    failed: dict[tuple[str, str], str] = {}
    report_rows: list[dict[str, Any]] = []
    any_failed = False

    def insert_pair(
        *,
        tenant_id: str,
        condition: str,
        row: TenantConditionRow | None,
        wall_time: float,
        status: str,
        reason: str,
    ) -> str:
        """Ghi một cặp vào giao dịch đang mở của tenant; trả run_id."""
        payload: dict[str, Any]
        if row is None:
            payload = {
                "tenant_id": tenant_id,
                "condition": condition,
                "status": "failed",
                "reason": reason,
            }
        else:
            payload = _row_payload_json(row)
        run_id = insert_run(
            connections[tenant_id],
            RunRow(
                tenant_id=tenant_id,
                seed=seed,
                model_id=record.model_id,
                model_revision=record.model_revision,
                code_commit=code_commit,
                config_hash=record.locked_config_hash,
                data_hash=data_hash,
                tokens_in=0,
                tokens_out=0,
                wall_time=wall_time,
                status=status,
            ),
        )
        event = EventRow(
            tenant_id=tenant_id,
            actor="coordinator",
            action="measure",
            payload_hash=_payload_hash(payload),
            run_id=run_id,
            target=condition,
            decision=status,
            decided_by="coordinator",
            reason=reason,
        )
        insert_event(connections[tenant_id], event)
        return run_id

    def record_row(
        *,
        tenant_id: str,
        condition: str,
        row: TenantConditionRow | None,
        wall_time: float,
        status: str,
        reason: str,
    ) -> None:
        """Ghi một cặp vào DB (trong giao dịch của tenant) + vào báo cáo."""
        nonlocal any_failed
        try:
            run_id = insert_pair(
                tenant_id=tenant_id,
                condition=condition,
                row=row,
                wall_time=wall_time,
                status=status,
                reason=reason,
            )
        except Exception as exc:
            raise _DbError(str(exc)) from exc
        if row is None:
            report_rows.append(
                {
                    "tenant_id": tenant_id,
                    "condition": condition,
                    "source": "",
                    "n_train": 0,
                    "n_measure": 0,
                    "n_reference": 0,
                    "n_rules": 0,
                    "metrics": None,
                    "run_id": run_id,
                    "status": status,
                    "wall_time": wall_time,
                    "reason": reason,
                }
            )
            any_failed = True
            return
        entry = _row_payload_json(row)
        entry["run_id"] = run_id
        entry["status"] = status
        entry["wall_time"] = wall_time
        report_rows.append(entry)

    def measure_pair(
        *, tenant: TenantData, facts: Sequence[Fact], condition: str
    ) -> tuple[TenantConditionRow | None, float, str]:
        """Đo một cặp; hỏng thì trả (None, giờ đã chạy, lý do)."""
        start = time.monotonic()
        try:
            row = _measure(
                tenant=tenant,
                facts=facts,
                condition=condition,
                n_draws=n_draws,
                seed=seed,
            )
        except Exception as exc:
            return None, time.monotonic() - start, f"đo hỏng: {exc}"
        return row, time.monotonic() - start, ""

    def summarize(row: TenantConditionRow) -> str:
        """Tóm tắt một cặp cho event (số fact, số luật đáp án, bốn chỉ số)."""
        metrics = row.metrics
        return (
            f"fact active {row.n_rules}, đáp án {row.n_reference} luật; "
            f"precision {metrics.precision.value:.4f}, "
            f"recall {metrics.recall.value:.4f}, "
            f"vi phạm {metrics.violation_rate.value:.4f}, "
            f"negative transfer {metrics.negative_transfer.value:.4f}"
        )

    try:
        for condition in (DECLARE_ONLY, POOLED, VOTING, CONSENSUS, VETO):
            for tenant in tenants:
                row, wall, error = measure_pair(
                    tenant=tenant,
                    facts=list(sets[condition][tenant.tenant_id]),
                    condition=condition,
                )
                if row is None:
                    failed[(condition, tenant.tenant_id)] = error
                    record_row(
                        tenant_id=tenant.tenant_id,
                        condition=condition,
                        row=None,
                        wall_time=wall,
                        status="failed",
                        reason=error,
                    )
                    continue
                measured.setdefault(condition, {})[tenant.tenant_id] = row
                record_row(
                    tenant_id=tenant.tenant_id,
                    condition=condition,
                    row=row,
                    wall_time=wall,
                    status="succeeded",
                    reason=summarize(row),
                )
        for tenant in tenants:
            base_row = measured.get(DECLARE_ONLY, {}).get(tenant.tenant_id)
            if base_row is None:
                error = failed.get((DECLARE_ONLY, tenant.tenant_id), "thiếu hàng Chỉ Declare")
                failed[(ISOLATION, tenant.tenant_id)] = error
                record_row(
                    tenant_id=tenant.tenant_id,
                    condition=ISOLATION,
                    row=None,
                    wall_time=0.0,
                    status="failed",
                    reason=error,
                )
                continue
            shared = replace(base_row, condition=ISOLATION)
            measured.setdefault(ISOLATION, {})[tenant.tenant_id] = shared
            record_row(
                tenant_id=tenant.tenant_id,
                condition=ISOLATION,
                row=shared,
                wall_time=0.0,
                status="succeeded",
                reason=summarize(shared),
            )
        consensus_rows = [measured.get(CONSENSUS, {}).get(t.tenant_id) for t in tenants]
        veto_rows = [measured.get(VETO, {}).get(t.tenant_id) for t in tenants]
        base_condition = (
            CONSENSUS
            if _mean_f1([row for row in consensus_rows if row is not None])
            >= _mean_f1([row for row in veto_rows if row is not None])
            else VETO
        )
        for tenant in tenants:
            if doc_rules:
                row, wall, error = measure_pair(
                    tenant=tenant,
                    facts=list(sets[base_condition][tenant.tenant_id]) + list(doc_facts),
                    condition=DOCUMENT,
                )
                if row is None:
                    failed[(DOCUMENT, tenant.tenant_id)] = error
                    record_row(
                        tenant_id=tenant.tenant_id,
                        condition=DOCUMENT,
                        row=None,
                        wall_time=wall,
                        status="failed",
                        reason=error,
                    )
                    continue
                measured.setdefault(DOCUMENT, {})[tenant.tenant_id] = row
                record_row(
                    tenant_id=tenant.tenant_id,
                    condition=DOCUMENT,
                    row=row,
                    wall_time=wall,
                    status="succeeded",
                    reason=summarize(row),
                )
            else:
                base_row = measured.get(base_condition, {}).get(tenant.tenant_id)
                if base_row is None:
                    error = failed.get(
                        (base_condition, tenant.tenant_id), f"thiếu hàng {base_condition}"
                    )
                    failed[(DOCUMENT, tenant.tenant_id)] = error
                    record_row(
                        tenant_id=tenant.tenant_id,
                        condition=DOCUMENT,
                        row=None,
                        wall_time=0.0,
                        status="failed",
                        reason=error,
                    )
                    continue
                shared = replace(base_row, condition=DOCUMENT)
                measured.setdefault(DOCUMENT, {})[tenant.tenant_id] = shared
                record_row(
                    tenant_id=tenant.tenant_id,
                    condition=DOCUMENT,
                    row=shared,
                    wall_time=0.0,
                    status="succeeded",
                    reason=summarize(shared),
                )
        for conn in connections.values():
            conn.commit()
    except _DbError as exc:
        for conn in connections.values():
            with suppress(Exception):
                conn.rollback()
        print(f"lỗi DB lúc ghi: {exc}", file=sys.stderr)
        return EXIT_DB
    finally:
        for conn in connections.values():
            with suppress(Exception):
                conn.close()

    published = not any_failed and len(report_rows) == 35
    wall_time = time.monotonic() - run_started
    # Báo cáo xếp theo tenant trước rồi điều kiện (m1..m5 x thứ tự
    # CONDITIONS), như `run_experiments` - vòng đo ghi theo điều kiện.
    tenant_order = {tenant.tenant_id: index for index, tenant in enumerate(tenants)}
    condition_order = {name: index for index, name in enumerate(CONDITIONS)}
    report_rows.sort(
        key=lambda row: (
            tenant_order[row["tenant_id"]],
            condition_order[row["condition"]],
        )
    )
    note = (
        "Điều kiện 1 (Chỉ Declare) và điều kiện 2 (Cách ly) cho cùng số: "
        "cùng khám phá Declare trên trace của tenant, chưa có kho global để "
        "cách ly loại ra. Điều kiện 7 lấy nền tốt hơn trong hai điều kiện "
        f"phân tầng theo F1 trung bình: {base_condition}. "
        f"Tập luật tài liệu có {len(doc_rules)} luật "
        f"(trích {provenance.n_rules_extracted}, qua cổng trên phần học "
        f"{provenance.n_rules_gated}); "
        f"mô hình {record.model_id}@{record.model_revision}; "
        f"chạy lại với --allow-rerun: {'có' if allow_rerun else 'không'}."
    )
    report = {
        "task": "12.2",
        "measured_at": started.astimezone(UTC).isoformat(),
        "code_commit": code_commit,
        "config_hash": record.locked_config_hash,
        "data_hash": data_hash,
        "seed": seed,
        "model_id": record.model_id,
        "model_revision": record.model_revision,
        "document_rules": len(doc_rules),
        "document_base_condition": base_condition,
        "published": published,
        "wall_time_seconds": round(wall_time, 1),
        "note": note,
        "rows": report_rows,
    }
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        print(f"không ghi được báo cáo {report_path}: {exc}", file=sys.stderr)
        return EXIT_DATA
    print(_format_text_report(report_rows, note=note, published=published, wall_time=wall_time))
    if any_failed:
        print(
            "lần chạy hỏng: có cặp failed (xem báo cáo); sửa nguyên nhân rồi "
            "chạy lại TOÀN BỘ 35 cặp trong một lần gọi mới",
            file=sys.stderr,
        )
        return EXIT_DATA
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Lệnh đo BPIC 2015: `python -m praxon_core.eval.bpic_measure`.

    Mã thoát: 0 = cả 35 cặp succeeded; 1 = lỗi dữ liệu/khóa (thiếu file,
    hash lệch, file luật sai, đã công bố rồi, một cặp failed); 2 = lỗi DB;
    3 = `budget_exceeded` (giữ chỗ, không xảy ra ở driver này).
    """
    parser = argparse.ArgumentParser(
        prog="praxon_core.eval.bpic_measure",
        description="Đo BPIC 2015 một lần, bảy điều kiện, năm đô thị (task 12.2).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="tệp TOML cấu hình đo (configs/phan-do.toml)",
    )
    parser.add_argument(
        "--lock",
        type=Path,
        required=True,
        help="bản ghi khóa (configs/phan-do.lock.toml)",
    )
    parser.add_argument(
        "--doc-laws",
        type=Path,
        default=Path("docs/plans/phase-1-core/luat-tai-lieu-wabo.txt"),
        help="file luật tài liệu (A.7)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="thư mục cache chứa 5 tệp BPIC15_N.xes",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("docs/plans/phase-1-core/ket-qua-do-bpic2015.json"),
        help="file báo cáo JSON ghi ra",
    )
    parser.add_argument(
        "--allow-rerun",
        action="store_true",
        help="mở chốt đã-công-bố (chỉ 12.3 dùng để kiểm tái lập)",
    )
    args = parser.parse_args(argv)
    return run(
        config_path=args.config,
        lock_path=args.lock,
        doc_laws_path=args.doc_laws,
        cache_dir=args.cache_dir,
        report_path=args.report,
        allow_rerun=args.allow_rerun,
    )


if __name__ == "__main__":
    raise SystemExit(main())
