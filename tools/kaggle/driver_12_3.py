"""Driver chạy lại để kiểm tái lập (task 12.3, spec dòng 191).

Driver này là thư viện cho notebook Kaggle gọi (giống driver 11.3): nó
nạp bản ghi khóa phần đo (12.1) + manifest lần đầu của 12.2 (giao diện H1),
pre-check 35 ô, rồi chạy lại từng ô bằng đúng hàm chạy của 12.2 qua giao
diện `RunCellFn` (giả thuyết H4 — driver 12.2 chưa xong lúc viết file này
nên hàm chạy là tham số, không phải import). Mỗi ô chạy lại mang
`is_rerun=True` + `repro_gaps` tính trước vào `LearningRound`, để hàng
`run` ghi verdict tái lập (V8). Kết quả mỗi ô (outcome + metrics JSON +
tập khóa fact `active` + log usage từng lô) ghi ra thư mục output để tải
về so bằng `compare_12_3.py` trên máy này.

Trường hợp khóa từ chối (`config_hash` khác khóa 12.1): KHÔNG có hàng
`run` lần chạy lại — driver ghi verdict vào báo cáo file + event với
`run_id` NULL rồi thoát mã 2 (xem A.2). Các gap khác không chặn chạy
(xem L3): pre-check chỉ in gap nổi bật, lần chạy lại vẫn chạy để lấy
chẩn đoán.

Tiền tố checkpoint của lần chạy lại mặc định là tiền tố chuẩn cộng thêm
"-rerun": lần chạy lại dùng cùng tenant/seed/config/data với lần đầu nên
tiền tố chuẩn sẽ trùng — không đổi tiền tố thì checkpoint lần chạy lại
ghi đè checkpoint lần đầu trên cùng store. Hàm chạy nhận tiền tố này qua
`RunCellFn` và phải truyền nó vào `LearningRound` (xem giao diện đó).

Tên file theo tiền lệ 11.3 (`driver_11_3.py`): đề xuất ghi
`12.3-driver.py`, nhưng tên có dấu chấm không import được trong test
local, nên dùng tên import được `driver_12_3.py` như 11.3 đã làm.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from praxon_core.adapters.cache import ResponseCache, cache_key
from praxon_core.adapters.language_model import CompletionResult, LanguageModel
from praxon_core.learning.checkpoint import checkpoint_prefix
from praxon_core.learning.coordinator import compute_config_hash, reproducibility_gaps
from praxon_core.learning.test_split_lock import load_locked_config
from praxon_core.repositories.runs import RunRow
from praxon_core.settings import Settings

EXPECTED_CELLS = 35
"""Số ô của một lần đo đầy đủ: bảy điều kiện nhân năm đô thị."""

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
"""Một giá trị JSON thuần (đệ quy): vô hướng, danh sách hoặc object."""

__all__ = [
    "EXPECTED_CELLS",
    "CellManifest",
    "CellOutcome",
    "CellRef",
    "CellRunRecord",
    "CountingCachedModel",
    "LockRecord",
    "PrecheckCell",
    "PrecheckResult",
    "RunCellFn",
    "UsageLog",
    "build_event_record",
    "cache_fingerprint",
    "load_lock_record",
    "load_manifest",
    "main",
    "precheck",
    "rerun_checkpoint_prefix",
    "run_rerun",
    "write_lock_refusal_report",
]


def _repro_gaps(data: Mapping[str, Any], where: str) -> str:
    """Lấy trường `repro_gaps` (chuỗi nối phẩy, mặc định rỗng khi vắng)."""
    value = data.get("repro_gaps", "")
    if not isinstance(value, str):
        raise ValueError(f"{where} trường 'repro_gaps' phải là chuỗi")
    return value


def _canonical_json(value: Mapping[str, Any] | Sequence[Any] | str) -> str:
    """JSON chuẩn: sắp xếp khóa, không khoảng trắng thừa (để băm ổn định)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    """SHA-256 hex của một chuỗi UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require_str(data: Mapping[str, Any], key: str, where: str) -> str:
    """Lấy một trường chuỗi bắt buộc; sai hình dạng thì lỗi rõ."""
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where} thiếu trường chuỗi '{key}'")
    return value


def _require_int(data: Mapping[str, Any], key: str, where: str) -> int:
    """Lấy một trường số nguyên bắt buộc; bool không tính là số nguyên."""
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{where} thiếu trường số nguyên '{key}'")
    return value


def _optional_str(data: Mapping[str, Any], key: str, where: str) -> str | None:
    """Lấy một trường chuỗi tùy chọn (None khi vắng); sai kiểu thì lỗi rõ."""
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{where} trường '{key}' phải là chuỗi hoặc vắng")
    return value


@dataclass(frozen=True)
class LockRecord:
    """Bản ghi khóa phần đo (12.1): sáu điều kiện tái lập + ngày/người khóa.

    Đọc từ `configs/phan-do.lock.toml`. `code_commit` là commit đã khóa
    cấu hình, KHÔNG phải commit lần đo chạy — không so nó với
    `code_commit` của hàng `run` tham chiếu (lần đo chạy ở commit sau
    khóa, gồm cả code 12.3, nên hai giá trị này khác nhau theo thiết kế).
    """

    locked_config_hash: str
    lock_commit: str
    code_commit: str
    seed: int
    model_id: str
    model_revision: str
    data_hash: str
    cache: str
    locked_at: str
    locked_by: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], where: str) -> LockRecord:
        """Dựng từ dict TOML đã parse; thiếu trường thì từ chối ngay."""
        return cls(
            locked_config_hash=_require_str(data, "locked_config_hash", where),
            lock_commit=_require_str(data, "lock_commit", where),
            code_commit=_require_str(data, "code_commit", where),
            seed=_require_int(data, "seed", where),
            model_id=_require_str(data, "model_id", where),
            model_revision=_require_str(data, "model_revision", where),
            data_hash=_require_str(data, "data_hash", where),
            cache=_require_str(data, "cache", where),
            locked_at=_require_str(data, "locked_at", where),
            locked_by=_require_str(data, "locked_by", where),
        )


def load_lock_record(path: Path) -> LockRecord:
    """Nạp bản ghi khóa từ file TOML; không đọc được thì từ chối ngay."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"không đọc được bản ghi khóa {path}: {exc}") from exc
    return LockRecord.from_dict(raw, f"bản ghi khóa {path}")


@dataclass(frozen=True)
class CellRef:
    """Một ô đo: một tenant trong một điều kiện."""

    tenant_id: str
    condition: str


@dataclass(frozen=True)
class CellRunRecord:
    """Hàng `run` của một ô (đủ sáu điều kiện + token + trạng thái + verdict).

    Gương của `RunRow` (V8): `reproducibility`/`repro_gaps` là verdict
    tái lập — ô tham chiếu (12.2, không phải chạy lại) để mặc định
    NULL/`''`; ô chạy lại mang verdict do `build_run_row` ghi.
    """

    run_id: str
    seed: int
    model_id: str
    model_revision: str
    code_commit: str
    config_hash: str
    data_hash: str
    tokens_in: int
    tokens_out: int
    status: str
    reproducibility: str | None = None
    repro_gaps: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], where: str) -> CellRunRecord:
        """Dựng từ dict JSON; thiếu trường bắt buộc thì từ chối ngay."""
        return cls(
            run_id=_require_str(data, "run_id", where),
            seed=_require_int(data, "seed", where),
            model_id=_require_str(data, "model_id", where),
            model_revision=_require_str(data, "model_revision", where),
            code_commit=_require_str(data, "code_commit", where),
            config_hash=_require_str(data, "config_hash", where),
            data_hash=_require_str(data, "data_hash", where),
            tokens_in=_require_int(data, "tokens_in", where),
            tokens_out=_require_int(data, "tokens_out", where),
            status=_require_str(data, "status", where),
            reproducibility=_optional_str(data, "reproducibility", where),
            repro_gaps=_repro_gaps(data, where),
        )

    def to_run_row(self, tenant_id: str) -> RunRow:
        """Chuyển thành hàng `run` của core (để tính gap bằng `reproducibility_gaps`).

        `RunRow` không có `run_id` (id do DB sinh khi INSERT) nên cần
        `tenant_id` từ ô chứa bản ghi này.
        """
        return RunRow(
            tenant_id=tenant_id,
            seed=self.seed,
            model_id=self.model_id,
            model_revision=self.model_revision,
            code_commit=self.code_commit,
            config_hash=self.config_hash,
            data_hash=self.data_hash,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            wall_time=0.0,
            status=self.status,
            reproducibility=self.reproducibility,
            repro_gaps=self.repro_gaps,
        )

    def to_dict(self) -> dict[str, JsonValue]:
        """Xuất thành dict JSON (ghi vào manifest lần chạy lại)."""
        out: dict[str, JsonValue] = {
            "run_id": self.run_id,
            "seed": self.seed,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "code_commit": self.code_commit,
            "config_hash": self.config_hash,
            "data_hash": self.data_hash,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "status": self.status,
            "repro_gaps": self.repro_gaps,
        }
        if self.reproducibility is not None:
            out["reproducibility"] = self.reproducibility
        return out


@dataclass(frozen=True)
class CellManifest:
    """Một ô trong manifest 12.2 (giao diện H1, mở rộng thêm hàng `run`).

    Đề xuất A.4 liệt kê từng ô: `tenant_id`, `condition`, `run_id`,
    `metrics_path`, `fact_keys_path`, `cache_export_path` +
    `cache_fingerprint`, `usage_log_path`, `ground_truth_path`. Mở rộng ở
    đây: `run_id` là một object `run` đầy đủ mười trường của hàng `run`
    (A.2 cần hàng `run` tham chiếu để tính gap bằng
    `reproducibility_gaps`; chỉ `run_id` thì không đủ). Các đường dẫn
    tương đối tính từ thư mục chứa manifest.
    """

    tenant_id: str
    condition: str
    run: CellRunRecord
    metrics_path: str
    fact_keys_path: str
    cache_export_path: str
    cache_fingerprint: str
    usage_log_path: str
    ground_truth_path: str

    @property
    def key(self) -> CellRef:
        """Ô (tenant, điều kiện) của bản ghi này."""
        return CellRef(tenant_id=self.tenant_id, condition=self.condition)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], where: str) -> CellManifest:
        """Dựng từ dict JSON; thiếu trường thì từ chối ngay."""
        run_raw = data.get("run")
        if not isinstance(run_raw, dict):
            raise ValueError(f"{where} thiếu object 'run'")
        return cls(
            tenant_id=_require_str(data, "tenant_id", where),
            condition=_require_str(data, "condition", where),
            run=CellRunRecord.from_dict(run_raw, where),
            metrics_path=_require_str(data, "metrics_path", where),
            fact_keys_path=_require_str(data, "fact_keys_path", where),
            cache_export_path=_require_str(data, "cache_export_path", where),
            cache_fingerprint=_require_str(data, "cache_fingerprint", where),
            usage_log_path=_require_str(data, "usage_log_path", where),
            ground_truth_path=_require_str(data, "ground_truth_path", where),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        """Xuất thành dict JSON (ghi manifest lần chạy lại)."""
        return {
            "tenant_id": self.tenant_id,
            "condition": self.condition,
            "run": self.run.to_dict(),
            "metrics_path": self.metrics_path,
            "fact_keys_path": self.fact_keys_path,
            "cache_export_path": self.cache_export_path,
            "cache_fingerprint": self.cache_fingerprint,
            "usage_log_path": self.usage_log_path,
            "ground_truth_path": self.ground_truth_path,
        }


def resolve_path(path: str, base: Path) -> Path:
    """Đường dẫn trong manifest: tuyệt đối thì giữ, tương đối thì tính từ `base`."""
    given = Path(path)
    return given if given.is_absolute() else base / given


def load_manifest(path: Path) -> tuple[CellManifest, ...]:
    """Nạp manifest 12.2: object JSON `{"cells": [...]}`; sai hình dạng thì lỗi rõ.

    Chỉ kiểm hình dạng từng ô + không trùng (tenant, điều kiện). Không
    kiểm đủ 35 ô ở đây — đó là việc của pre-check (thiếu ô tham chiếu thì
    verdict tổng FAIL, xem R8).
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"không đọc được manifest {path}: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("cells"), list):
        raise ValueError(f"manifest sai hình dạng (thiếu danh sách 'cells'): {path}")
    cells: list[CellManifest] = []
    seen: set[CellRef] = set()
    for index, item in enumerate(raw["cells"]):
        where = f"manifest {path} ô #{index}"
        if not isinstance(item, dict):
            raise ValueError(f"{where} không phải object")
        cell = CellManifest.from_dict(item, where)
        if cell.key in seen:
            raise ValueError(f"{where} trùng ô ({cell.tenant_id}, {cell.condition})")
        seen.add(cell.key)
        cells.append(cell)
    return tuple(cells)


def cache_fingerprint(entries: Mapping[str, str]) -> str:
    """Vân tay SHA-256 của một cache export (dict khóa đệm -> phản hồi).

    Cùng nội dung thì cùng vân tay dù thứ tự khóa khác nhau (JSON chuẩn
    sắp xếp khóa trước khi băm). Pre-check so vân tay này với vân tay đã
    ghi trong manifest 12.2 để biết đệm còn nguyên hay không.
    """
    return _sha256_text(_canonical_json(entries))


class UsageLog:
    """Log usage từng lần gọi mô hình của một ô (định dạng JSON giống 11.3).

    Mỗi mục là một lần Reflector gọi model: miss ghi usage thật
    (`prompt_tokens`/`completion_tokens`), hit ghi `{"hit": true}` (cache
    hit không gọi mô hình nên đóng 0 token). Khóa là khóa đệm
    (`cache_key`): cùng prompt + revision + tham số + schema thì cùng
    khóa ở cả hai lần, nên script so sánh tra được usage đã tiết kiệm.
    """

    def __init__(self) -> None:
        """Log rỗng."""
        self.entries: list[dict[str, Any]] = []

    def record_miss(self, key: str, prompt_tokens: int, completion_tokens: int) -> None:
        """Ghi một lần gọi mô hình thật cùng usage của nó."""
        self.entries.append(
            {"key": key, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
        )

    def record_hit(self, key: str) -> None:
        """Ghi một lần phục vụ từ cache (không gọi mô hình)."""
        self.entries.append({"key": key, "hit": True})

    @property
    def model_calls(self) -> int:
        """Số lần gọi mô hình thật trong ô (hit không tính)."""
        return sum(1 for entry in self.entries if "hit" not in entry)

    @property
    def cache_hits(self) -> int:
        """Số lần phục vụ từ cache trong ô."""
        return sum(1 for entry in self.entries if entry.get("hit") is True)

    @property
    def total_tokens(self) -> int:
        """Tổng token đã đóng trong ô (hit đóng 0)."""
        return sum(
            int(entry.get("prompt_tokens", 0)) + int(entry.get("completion_tokens", 0))
            for entry in self.entries
            if "hit" not in entry
        )

    def to_dict(self) -> dict[str, Any]:
        """Xuất log thành dict JSON (ghi ra `usage_log.json`)."""
        return {"entries": [dict(entry) for entry in self.entries]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> UsageLog:
        """Nạp log từ dict JSON; mục sai hình dạng thì từ chối ngay."""
        raw = data.get("entries")
        if not isinstance(raw, list):
            raise ValueError("usage log thiếu danh sách 'entries'")
        log = cls()
        for entry in raw:
            if not isinstance(entry, dict) or not isinstance(entry.get("key"), str):
                raise ValueError(f"mục usage log sai hình dạng: {entry!r}")
            if entry.get("hit") is True:
                log.record_hit(str(entry["key"]))
            elif isinstance(entry.get("prompt_tokens"), int) and isinstance(
                entry.get("completion_tokens"), int
            ):
                log.record_miss(
                    str(entry["key"]),
                    int(entry["prompt_tokens"]),
                    int(entry["completion_tokens"]),
                )
            else:
                raise ValueError(f"mục usage log sai hình dạng: {entry!r}")
        return log


class CountingCachedModel:
    """LanguageModel bọc cache + đếm lần gọi (không có công tắc ngắt).

    Cùng hình dạng với `CountingCachedModel` của 11.3 nhưng KHÔNG có
    `kill_after_calls`: lần chạy lại không tự ngắt, chỉ đếm. Miss thì gọi
    model thật, ghi usage vào log; hit thì trả phản hồi đã lưu với 0
    token (không gọi model). Notebook dựng model này quanh model thật,
    nhập cache export tham chiếu vào `cache` trước, rồi đưa vào Reflector
    của hàm chạy 12.2.
    """

    def __init__(
        self,
        *,
        model: LanguageModel,
        cache: ResponseCache,
        model_revision: str,
        usage_log: UsageLog,
    ) -> None:
        """Giữ model + cache + log; chưa gọi mạng lúc dựng."""
        self._model = model
        self._cache = cache
        self._model_revision = model_revision
        self._usage_log = usage_log
        self._calls = 0
        self._hits = 0

    @property
    def calls(self) -> int:
        """Số lần gọi mô hình thật từ đầu ô."""
        return self._calls

    @property
    def hits(self) -> int:
        """Số lần phục vụ từ cache từ đầu ô."""
        return self._hits

    def complete(
        self,
        prompt: str,
        *,
        json_schema: Mapping[str, Any] | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        """Hoàn thành một prompt, qua cache; hit thì 0 token, miss thì ghi usage."""
        decode_params: dict[str, Any] = {"temperature": temperature, "seed": seed}
        schema = json_schema if json_schema is not None else {}
        key = cache_key(prompt, self._model_revision, decode_params, schema)
        invoked = False
        usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}

        def call(text: str) -> str:
            """Gọi model thật một lần, giữ lại usage vào closure."""
            nonlocal invoked
            invoked = True
            result = self._model.complete(
                text,
                json_schema=json_schema,
                temperature=temperature,
                seed=seed,
                max_tokens=max_tokens,
            )
            usage["prompt_tokens"] = result.prompt_tokens or 0
            usage["completion_tokens"] = result.completion_tokens or 0
            return result.text

        text = self._cache.get_or_call(
            prompt,
            model_revision=self._model_revision,
            decode_params=decode_params,
            json_schema=schema,
            call=call,
        )
        if not invoked:
            self._hits += 1
            self._usage_log.record_hit(key)
            return CompletionResult(text=text, prompt_tokens=0, completion_tokens=0)
        self._calls += 1
        self._usage_log.record_miss(key, usage["prompt_tokens"], usage["completion_tokens"])
        return CompletionResult(
            text=text,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
        )


@dataclass(frozen=True)
class CellOutcome:
    """Kết quả một ô chạy lại, do hàm chạy 12.2 trả về (giao diện H4).

    `metrics` là metrics JSON của ô (dạng `TenantConditionRow`: bốn chỉ
    số kèm CI + `n_train`/`n_measure`/`n_reference`); `fact_keys` là tập
    khóa canonical của fact `active`, đã sắp xếp; `usage_log` là log JSON
    dạng `UsageLog`; `run_id` là id hàng `run` lần chạy lại (None khi vòng
    học bị từ chối trước khi ghi hàng `run` — khi đó ô không có outcome
    để so).
    """

    run_id: str | None
    run_status: str
    reproducibility: str | None
    repro_gaps: tuple[str, ...]
    metrics: dict[str, Any]
    fact_keys: tuple[str, ...]
    usage_log: dict[str, Any]
    model_calls: int
    cache_hits: int
    tokens_in: int
    tokens_out: int

    def to_dict(self) -> dict[str, JsonValue]:
        """Xuất thành dict JSON (ghi ra `outcome.json`)."""
        out: dict[str, JsonValue] = {
            "run_status": self.run_status,
            "repro_gaps": list(self.repro_gaps),
            "metrics": self.metrics,
            "fact_keys": list(self.fact_keys),
            "usage_log": self.usage_log,
            "model_calls": self.model_calls,
            "cache_hits": self.cache_hits,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
        }
        if self.run_id is not None:
            out["run_id"] = self.run_id
        if self.reproducibility is not None:
            out["reproducibility"] = self.reproducibility
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], where: str) -> CellOutcome:
        """Dựng từ dict JSON; thiếu trường thì từ chối ngay."""
        metrics = data.get("metrics")
        if not isinstance(metrics, dict):
            raise ValueError(f"{where} thiếu object 'metrics'")
        fact_keys = data.get("fact_keys")
        if not isinstance(fact_keys, list) or not all(
            isinstance(item, str) for item in fact_keys
        ):
            raise ValueError(f"{where} thiếu danh sách chuỗi 'fact_keys'")
        usage_log = data.get("usage_log")
        if not isinstance(usage_log, dict):
            raise ValueError(f"{where} thiếu object 'usage_log'")
        gaps = data.get("repro_gaps", [])
        if not isinstance(gaps, list) or not all(isinstance(item, str) for item in gaps):
            raise ValueError(f"{where} trường 'repro_gaps' phải là danh sách chuỗi")
        return cls(
            run_id=_optional_str(data, "run_id", where),
            run_status=_require_str(data, "run_status", where),
            reproducibility=_optional_str(data, "reproducibility", where),
            repro_gaps=tuple(str(item) for item in gaps),
            metrics=dict(metrics),
            fact_keys=tuple(str(item) for item in fact_keys),
            usage_log=dict(usage_log),
            model_calls=_require_int(data, "model_calls", where),
            cache_hits=_require_int(data, "cache_hits", where),
            tokens_in=_require_int(data, "tokens_in", where),
            tokens_out=_require_int(data, "tokens_out", where),
        )


class RunCellFn(Protocol):
    """Giao diện H4: hàm chạy một ô đo của driver 12.2, tái dùng cho lần chạy lại.

    Driver 12.2 chưa xong lúc viết file này nên hàm chạy là tham số do
    notebook truyền vào, không phải import. Hàm nhận một ô + cờ chạy lại
    và phải:

    - dựng `LearningRound` với `is_rerun=is_rerun`,
      `repro_gaps=repro_gaps`, `on_test_split=True` và
      `checkpoint_prefix` nhận được (tiền tố riêng của lần chạy lại —
      không dùng tiền tố chuẩn, nếu không checkpoint lần chạy lại ghi đè
      checkpoint lần đầu trên cùng store);
    - nhập cache export tham chiếu của ô vào một `ResponseCache` mới và
      bọc model bằng `CountingCachedModel` trước khi dựng Reflector, để
      lần chạy lại phục vụ từ đệm và ghi log usage từng lô;
    - trả `CellOutcome` với đầy đủ metrics JSON + tập khóa fact +
      usage log + token của hàng `run` lần chạy lại.
    """

    def __call__(
        self,
        cell: CellRef,
        *,
        is_rerun: bool,
        repro_gaps: tuple[str, ...],
        checkpoint_prefix: str | None,
    ) -> CellOutcome:
        """Chạy một ô đo, trả outcome của ô đó (xem docstring của giao diện)."""
        ...


@dataclass(frozen=True)
class PrecheckCell:
    """Kết quả pre-check một ô: gap + đủ tham chiếu + đủ file + khớp khóa.

    `gaps` KHÔNG làm ô này "không ok": gap chỉ ghi vào hàng `run` lần
    chạy lại, không chặn chạy (xem L3). Chỉ ba thứ chặn chạy lại: hàng
    `run` tham chiếu không `succeeded`, thiếu file, hoặc hàng tham chiếu
    lệch bản ghi khóa (lỗi ở 12.2, xem A.2).
    """

    cell: CellRef
    gaps: tuple[str, ...]
    reference_ok: bool
    missing_files: tuple[str, ...]
    fingerprint_ok: bool
    lock_mismatch: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Ô đủ điều kiện để chạy lại (tham chiếu tốt + đủ file + khớp khóa)."""
        return (
            self.reference_ok
            and not self.missing_files
            and self.fingerprint_ok
            and not self.lock_mismatch
        )

    def report_line(self) -> str:
        """Một dòng báo cáo: trạng thái + gap nổi bật (nếu có)."""
        mark = "OK " if self.ok else "THIEU"
        parts = [f"[{mark}] ({self.cell.tenant_id}, {self.cell.condition})"]
        if self.gaps:
            parts.append(f"GAP: {','.join(self.gaps)}")
        if not self.reference_ok:
            parts.append("tham chieu khong succeeded")
        if self.missing_files:
            parts.append(f"thieu file: {','.join(self.missing_files)}")
        if not self.fingerprint_ok:
            parts.append("van tay cache lech")
        if self.lock_mismatch:
            parts.append(f"lech khoa: {','.join(self.lock_mismatch)}")
        return " ".join(parts)


@dataclass(frozen=True)
class PrecheckResult:
    """Kết quả pre-check toàn bộ manifest."""

    cells: tuple[PrecheckCell, ...]

    @property
    def reference_problems(self) -> tuple[PrecheckCell, ...]:
        """Các ô không đủ điều kiện chạy lại (thiếu tham chiếu / thiếu file / lệch khóa)."""
        return tuple(cell for cell in self.cells if not cell.ok)

    @property
    def gaps_by_cell(self) -> dict[CellRef, tuple[str, ...]]:
        """Gap từng ô (kể cả ô có vấn đề tham chiếu — gap vẫn tính được)."""
        return {cell.cell: cell.gaps for cell in self.cells}

    def report(self) -> str:
        """Báo cáo pre-check: từng ô (gap in nổi bật) + tóm tắt."""
        lines = ["Pre-check 12.3 (35 o):"]
        lines.extend(cell.report_line() for cell in self.cells)
        n_ok = sum(1 for cell in self.cells if cell.ok)
        n_gaps = sum(1 for cell in self.cells if cell.gaps)
        lines.append(
            f"Tom tat: {n_ok}/{len(self.cells)} o du tham chieu, "
            f"{n_gaps} o co gap (gap khong chan chay, chi ghi vao hang run)"
        )
        return "\n".join(lines)


def _read_cache_export(path: Path) -> dict[str, str] | None:
    """Nạp cache export (dict khóa -> phản hồi); hỏng thì None (không đoán)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in raw.items()):
        return None
    return dict(raw)


def precheck(
    manifest: Sequence[CellManifest],
    *,
    manifest_dir: Path,
    lock: LockRecord,
    settings: Settings,
    code_commit: str,
    data_hash: str,
    seed: int | None = None,
) -> PrecheckResult:
    """Pre-check 35 ô trước lần chạy lại (A.2): đủ tham chiếu, đủ file, gap.

    `seed` là seed lần chạy lại sẽ dùng (mặc định lấy từ bản ghi khóa —
    cùng một nguồn nên gap `seed` chỉ xảy ra khi người gọi truyền seed
    khác). `data_hash` là hash dữ liệu lần chạy lại sẽ dùng, tính bằng
    `merge_data_hash` với cùng đầu vào như 12.2 (driver không tự tính
    được vì không giữ log). `model_id`/`model_revision` lấy từ Settings
    đang dùng (đã khớp khóa qua `load_locked_config`).
    """
    config_hash = compute_config_hash(settings)
    current_seed = lock.seed if seed is None else seed
    checked: list[PrecheckCell] = []
    for cell in manifest:
        missing: list[str] = []
        for label, given in (
            ("metrics", cell.metrics_path),
            ("fact_keys", cell.fact_keys_path),
            ("cache_export", cell.cache_export_path),
            ("usage_log", cell.usage_log_path),
            ("ground_truth", cell.ground_truth_path),
        ):
            if not resolve_path(given, manifest_dir).is_file():
                missing.append(label)
        export = _read_cache_export(resolve_path(cell.cache_export_path, manifest_dir))
        fingerprint_ok = (
            export is not None and cache_fingerprint(export) == cell.cache_fingerprint
        )
        mismatch: list[str] = []
        if cell.run.seed != lock.seed:
            mismatch.append("seed")
        if cell.run.model_id != lock.model_id or cell.run.model_revision != lock.model_revision:
            mismatch.append("model")
        if cell.run.config_hash != lock.locked_config_hash:
            mismatch.append("config_hash")
        if cell.run.data_hash != lock.data_hash:
            mismatch.append("data_hash")
        gaps = reproducibility_gaps(
            cell.run.to_run_row(cell.tenant_id),
            seed=current_seed,
            model_id=settings.model_id,
            model_revision=settings.model_revision,
            code_commit=code_commit,
            config_hash=config_hash,
            data_hash=data_hash,
            cache_intact=fingerprint_ok,
        )
        checked.append(
            PrecheckCell(
                cell=cell.key,
                gaps=gaps,
                reference_ok=cell.run.status == "succeeded" and not mismatch,
                missing_files=tuple(missing),
                fingerprint_ok=fingerprint_ok,
                lock_mismatch=tuple(mismatch),
            )
        )
    return PrecheckResult(cells=tuple(checked))


def rerun_checkpoint_prefix(
    *,
    cell: CellRef,
    lock: LockRecord,
    config_hash: str,
    data_hash: str,
    explicit: str | None = None,
) -> str:
    """Tiền tố checkpoint cho lần chạy lại của một ô.

    Mặc định là tiền tố chuẩn cộng "-rerun" (xem docstring module).
    Người gọi truyền `explicit` để dùng tiền tố khác khi cần.
    """
    if explicit is not None:
        return explicit
    base = checkpoint_prefix(
        tenant_id=cell.tenant_id,
        seed=lock.seed,
        config_hash=config_hash,
        data_hash=data_hash,
    )
    return f"{base}-rerun"


def _write_json(path: Path, data: Mapping[str, Any] | Sequence[Any]) -> None:
    """Ghi dict/list thành file JSON chuẩn (sắp xếp khóa, indent 2)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n")


def run_rerun(
    manifest: Sequence[CellManifest],
    *,
    manifest_dir: Path,
    lock: LockRecord,
    settings: Settings,
    code_commit: str,
    data_hash: str,
    run_cell: RunCellFn,
    output_dir: Path,
    checkpoint_prefix: str | None = None,
) -> dict[str, JsonValue]:
    """Chạy lại toàn bộ manifest rồi ghi outcome + manifest lần chạy lại.

    Khóa cấu hình lệch thì từ chối trước khi gọi hàm chạy lần nào (không
    có hàng `run` lần chạy lại — trường hợp này thuộc về
    `write_lock_refusal_report`, xem A.2). Tham chiếu thiếu/thiếu file
    thì từ chối với danh sách ô (R8). Gap không chặn chạy (L3).
    """
    config_hash = compute_config_hash(settings)
    if config_hash != lock.locked_config_hash:
        raise ValueError(
            "cấu hình đo khác khóa phần đo "
            f"(config_hash {config_hash[:12]}... khác khóa "
            f"{lock.locked_config_hash[:12]}...): không được chạy trên phần đo"
        )
    checked = precheck(
        manifest,
        manifest_dir=manifest_dir,
        lock=lock,
        settings=settings,
        code_commit=code_commit,
        data_hash=data_hash,
    )
    if checked.reference_problems:
        details = "; ".join(cell.report_line() for cell in checked.reference_problems)
        raise ValueError(f"pre-check thiếu tham chiếu, chưa chạy lại: {details}")
    gaps_by_cell = checked.gaps_by_cell
    output_dir.mkdir(parents=True, exist_ok=True)
    rerun_cells: list[CellManifest] = []
    report_cells: list[JsonValue] = []
    for cell in manifest:
        gaps = gaps_by_cell[cell.key]
        prefix = rerun_checkpoint_prefix(
            cell=cell.key,
            lock=lock,
            config_hash=config_hash,
            data_hash=data_hash,
            explicit=checkpoint_prefix,
        )
        outcome = run_cell(cell.key, is_rerun=True, repro_gaps=gaps, checkpoint_prefix=prefix)
        if outcome.run_id is None:
            raise ValueError(
                f"ô ({cell.tenant_id}, {cell.condition}) không có run_id: "
                "vòng học bị từ chối trước khi ghi hàng run"
            )
        cell_dir = output_dir / cell.tenant_id / cell.condition
        _write_json(cell_dir / "outcome.json", outcome.to_dict())
        _write_json(cell_dir / "metrics.json", outcome.metrics)
        _write_json(cell_dir / "fact_keys.json", {"fact_keys": sorted(outcome.fact_keys)})
        _write_json(cell_dir / "usage_log.json", outcome.usage_log)
        rerun_cells.append(
            CellManifest(
                tenant_id=cell.tenant_id,
                condition=cell.condition,
                run=CellRunRecord(
                    run_id=outcome.run_id,
                    seed=lock.seed,
                    model_id=settings.model_id,
                    model_revision=settings.model_revision,
                    code_commit=code_commit,
                    config_hash=config_hash,
                    data_hash=data_hash,
                    tokens_in=outcome.tokens_in,
                    tokens_out=outcome.tokens_out,
                    status=outcome.run_status,
                    reproducibility=outcome.reproducibility,
                    repro_gaps=",".join(outcome.repro_gaps),
                ),
                # Đường dẫn file của lần chạy lại tính tương đối từ thư mục
                # chứa manifest này (output_dir); export + đáp án tham
                # chiếu ghi tuyệt đối vì chúng nằm ở thư mục manifest 12.2.
                metrics_path=f"{cell.tenant_id}/{cell.condition}/metrics.json",
                fact_keys_path=f"{cell.tenant_id}/{cell.condition}/fact_keys.json",
                cache_export_path=str(resolve_path(cell.cache_export_path, manifest_dir)),
                cache_fingerprint=cell.cache_fingerprint,
                usage_log_path=f"{cell.tenant_id}/{cell.condition}/usage_log.json",
                ground_truth_path=str(resolve_path(cell.ground_truth_path, manifest_dir)),
            )
        )
        report_cells.append(
            {
                "tenant_id": cell.tenant_id,
                "condition": cell.condition,
                "run_id": outcome.run_id,
                "run_status": outcome.run_status,
                "reproducibility": outcome.reproducibility,
                "repro_gaps": list(outcome.repro_gaps),
                "checkpoint_prefix": prefix,
            }
        )
    _write_json(
        output_dir / "12.3-manifest.json",
        {"cells": [cell.to_dict() for cell in rerun_cells]},
    )
    return {
        "code_commit": code_commit,
        "locked_config_hash": lock.locked_config_hash,
        "cells": report_cells,
    }


def build_event_record(
    *,
    run_id: str | None,
    tenant_id: str,
    condition: str,
    gaps: Sequence[str],
    checks: Sequence[Mapping[str, Any]],
    reason: str,
) -> dict[str, JsonValue]:
    """Bản ghi event `reproducibility_check` (A.4): gap + so sánh + token.

    `payload_hash` là băm JSON chuẩn của bản ghi so sánh. `run_id` NULL
    chỉ xảy ra ở trường hợp khóa từ chối (không có lần chạy nào để gắn);
    `tenant_id`/`condition` rỗng cũng chỉ ở trường hợp đó (event toàn
    cục, không gắn ô cụ thể).
    """
    payload: dict[str, JsonValue] = {
        "tenant_id": tenant_id,
        "condition": condition,
        "gaps": list(gaps),
        "checks": [dict(check) for check in checks],
        "reason": reason,
    }
    return {
        "run_id": run_id,
        "tenant_id": tenant_id,
        "condition": condition,
        "actor": "coordinator",
        "action": "reproducibility_check",
        "payload_hash": _sha256_text(_canonical_json(payload)),
        "reason": reason,
    }


def write_lock_refusal_report(
    output_dir: Path,
    *,
    error: str,
    code_commit: str,
    locked_config_hash: str | None,
) -> Path:
    """Ghi báo cáo verdict khi khóa 12.1 từ chối (không có hàng `run`).

    Trường hợp duy nhất không có hàng `run` lần chạy lại (A.2): verdict
    `not_reproducible` + gap `config_hash` + event `run_id` NULL ghi vào
    `12.3-report.json` trong thư mục output. Trả đường dẫn file đã ghi.
    """
    reason = (
        "cấu hình đo khác khóa phần đo (config_hash): không được chạy trên "
        "phần đo; không có hàng run lần chạy lại"
    )
    report: dict[str, JsonValue] = {
        "verdict": "not_reproducible",
        "verdict_tong": "FAIL",
        "gaps": ["config_hash"],
        "run_id": None,
        "code_commit": code_commit,
        "locked_config_hash": locked_config_hash,
        "error": error,
        "events": [
            build_event_record(
                run_id=None,
                tenant_id="",
                condition="",
                gaps=("config_hash",),
                checks=[],
                reason=reason,
            )
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "12.3-report.json"
    _write_json(path, report)
    return path


def _git_rev_parse_head() -> str:
    """`code_commit` hiện tại (git rev-parse HEAD); không lấy được thì lỗi rõ."""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"không lấy được code_commit (git rev-parse HEAD): {exc}") from exc
    return done.stdout.strip()


def _import_run_cell(dotted: str) -> RunCellFn:
    """Nạp hàm chạy ô từ đường dẫn `module:attr` (giao diện H4 của 12.2)."""
    if ":" not in dotted:
        raise ValueError(f"--run-cell phải có dạng 'module:attr', nhận {dotted!r}")
    module_name, _, attr = dotted.partition(":")
    if not module_name or not attr:
        raise ValueError(f"--run-cell phải có dạng 'module:attr', nhận {dotted!r}")
    module = importlib.import_module(module_name)
    fn = getattr(module, attr, None)
    if not callable(fn):
        raise ValueError(f"--run-cell {dotted!r} không phải callable")
    return cast("RunCellFn", fn)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI chạy lại trên Kaggle: khóa -> pre-check -> chạy 35 ô.

    Thoát 0 khi chạy lại xong; 1 khi pre-check thiếu tham chiếu; 2 khi
    khóa từ chối hoặc thiếu hàm chạy (`--run-cell`). `--precheck-only`
    chỉ chạy pre-check rồi thoát 0 khi đủ tham chiếu (gap không chặn).
    """
    parser = argparse.ArgumentParser(
        description="Chạy lại phép đo 12.2 để kiểm tái lập (12.3)."
    )
    parser.add_argument("--config", default="configs/phan-do.toml")
    parser.add_argument("--lock", default="configs/phan-do.lock.toml")
    parser.add_argument("--manifest", required=True, help="manifest 12.2 (12.2-manifest.json)")
    parser.add_argument("--output-dir", required=True, help="thư mục ghi outcome lần chạy lại")
    parser.add_argument(
        "--data-hash",
        required=True,
        help="data_hash lần chạy lại sẽ dùng (merge_data_hash, cùng đầu vào như 12.2)",
    )
    parser.add_argument("--code-commit", default=None, help="mặc định: git rev-parse HEAD")
    parser.add_argument(
        "--run-cell",
        default=None,
        help="hàm chạy một ô của driver 12.2, dạng 'module:attr' (giao diện H4)",
    )
    parser.add_argument("--precheck-only", action="store_true")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    lock_path = Path(args.lock)
    manifest_path = Path(args.manifest)
    output_dir = Path(args.output_dir)
    code_commit = args.code_commit or _git_rev_parse_head()
    try:
        settings, _ = load_locked_config(config_path, lock_path)
    except ValueError as exc:
        locked_hash: str | None = None
        try:
            locked_hash = load_lock_record(lock_path).locked_config_hash
        except ValueError:
            locked_hash = None
        path = write_lock_refusal_report(
            output_dir,
            error=str(exc),
            code_commit=code_commit,
            locked_config_hash=locked_hash,
        )
        print(f"KHOA TU CHOI (config_hash): {exc}")
        print(f"Verdict ghi vao {path} (run_id NULL), thoat 2")
        return 2
    lock = load_lock_record(lock_path)
    manifest = load_manifest(manifest_path)
    checked = precheck(
        manifest,
        manifest_dir=manifest_path.absolute().parent,
        lock=lock,
        settings=settings,
        code_commit=code_commit,
        data_hash=args.data_hash,
    )
    print(checked.report())
    if checked.reference_problems:
        print("Pre-check thieu tham chieu: sua o 12.2 roi moi kiem 12.3 (R8)")
        return 1
    if args.precheck_only:
        return 0
    if args.run_cell is None:
        print("Thieu --run-cell: chua co ham chay o cua driver 12.2 (H4)")
        return 2
    run_cell = _import_run_cell(args.run_cell)
    report = run_rerun(
        manifest,
        manifest_dir=manifest_path.absolute().parent,
        lock=lock,
        settings=settings,
        code_commit=code_commit,
        data_hash=args.data_hash,
        run_cell=run_cell,
        output_dir=output_dir,
    )
    _write_json(output_dir / "12.3-rerun-report.json", report)
    manifest_out = output_dir / "12.3-manifest.json"
    print(f"Chay lai xong {len(manifest)} o, manifest: {manifest_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
