"""Điểm kiểm tra của vòng học (task 10.3, spec dòng 215).

Mỗi N case, vòng học ghi một điểm kiểm tra gồm đủ bốn thành phần spec yêu
cầu — fact, candidate đang chờ, con trỏ case, bộ nhớ đệm phản hồi — rồi đẩy
sang store (local trên máy hoặc object storage S3-compatible như Backblaze
B2). Khởi động lại thì đọc checkpoint mới nhất, chạy tiếp từ con trỏ.

Checkpoint là một model Pydantic có `version` (hiện là 1): reader từ chối
version lạ bằng lỗi rõ, không đoán format cũ (rủi ro R3 trong đề xuất).
Khóa checkpoint mã số case đã xong (`{prefix}/{cases_done:06d}.json`) nên
checkpoint mới nhất là khóa lớn nhất — không cần đọc nội dung để so sánh.

Module này thuần: chỉ định dạng + đọc/ghi qua `CheckpointStore` (Protocol),
không biết store là local hay S3, không chạm DB, không gọi mô hình.
"""

from __future__ import annotations

import json
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from praxon_core.learning.candidate import GovernorResult
from praxon_core.learning.curator import Insight
from praxon_core.learning.generator import Trajectory
from praxon_core.repositories.events import EventRow
from praxon_core.repositories.facts import FactClose, FactRow

CHECKPOINT_VERSION = 1
"""Version format checkpoint hiện tại; reader chỉ đọc đúng version này."""


class Checkpoint(BaseModel):
    """Một điểm kiểm tra của vòng học: đủ bốn thành phần spec dòng 215.

    - Fact: `fact_rows` (fact mới đã duyệt) + `fact_closes` (fact cũ đã đóng).
    - Candidate đang chờ: `decisions` (quyết định Governor cho từng
      candidate) + `candidate_ids` song song theo thứ tự — đây là các
      candidate đã quyết nhưng người gọi chưa ghi xuống DB; khởi động lại
      không quyết lại chúng.
    - Con trỏ case: `cases_done` là các `case_id` đã xử lý xong, theo đúng
      thứ tự xuất hiện của case; chạy tiếp thì bỏ qua đúng các case này.
    - Bộ nhớ đệm: `cache_entries` là dict khóa → phản hồi của `ResponseCache`.

    `seed` + `model_id` + `model_revision` + `config_hash` + `data_hash`
    là khóa chống chạy tiếp sai vòng (rủi ro R4): resume chỉ chạy khi mọi
    giá trị này khớp với vòng mới; khác một giá trị là từ chối.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = CHECKPOINT_VERSION
    tenant_id: str
    seed: int
    model_id: str
    model_revision: str
    config_hash: str
    data_hash: str
    cases_done: tuple[str, ...] = ()
    trajectories: tuple[Trajectory, ...] = ()
    insights: tuple[Insight, ...] = ()
    decisions: tuple[GovernorResult, ...] = ()
    candidate_ids: tuple[str, ...] = ()
    fact_rows: tuple[FactRow, ...] = ()
    fact_closes: tuple[FactClose, ...] = ()
    events: tuple[EventRow, ...] = ()
    cache_entries: dict[str, str] = {}
    tokens_in: int = 0
    tokens_out: int = 0


class CheckpointStore(Protocol):
    """Nơi ghi checkpoint: một kho khóa → bytes.

    Hai backend: filesystem (`adapters.local_store`) và object storage
    S3-compatible (`adapters.s3_store`). `put` phải ghi đủ bytes đã đưa
    (không ghi dở); `get` trả `None` khi khóa chưa có; `list_keys` trả mọi
    khóa bắt đầu bằng `prefix`, sắp xếp tăng dần.
    """

    def put(self, key: str, data: bytes) -> None:
        """Ghi `data` vào `key` (ghi đè nếu khóa đã có)."""

    def get(self, key: str) -> bytes | None:
        """Đọc bytes tại `key`; khóa chưa có thì `None`."""

    def list_keys(self, prefix: str) -> list[str]:
        """Mọi khóa bắt đầu bằng `prefix`, sắp xếp tăng dần."""


def checkpoint_prefix(*, tenant_id: str, seed: int, config_hash: str, data_hash: str) -> str:
    """Tiền tố khóa cho mọi checkpoint của một vòng học.

    Gồm tenant + seed + 12 ký tự đầu của `config_hash` và `data_hash`:
    hai vòng khác cấu hình/dữ liệu không bao giờ chung tiền tố, nên resume
    không bao giờ đọc nhầm checkpoint của vòng khác.
    """
    return f"checkpoints/{tenant_id}/{seed}-{config_hash[:12]}-{data_hash[:12]}"


def checkpoint_key(prefix: str, cases_done: int) -> str:
    """Khóa của checkpoint: `{prefix}/{cases_done:06d}.json`.

    Số case đã xong nằm ngay trong khóa, đệm 0 tới 6 chữ số, nên thứ tự từ
    điển của khóa cũng là thứ tự số case — checkpoint mới nhất là khóa lớn
    nhất dưới tiền tố.
    """
    return f"{prefix}/{cases_done:06d}.json"


def write_checkpoint(store: CheckpointStore, checkpoint: Checkpoint, prefix: str) -> str:
    """Ghi checkpoint vào store, trả khóa đã ghi."""
    key = checkpoint_key(prefix, len(checkpoint.cases_done))
    store.put(key, checkpoint.model_dump_json().encode("utf-8"))
    return key


def read_checkpoint(store: CheckpointStore, key: str) -> Checkpoint:
    """Đọc checkpoint theo khóa.

    Khóa chưa có, JSON hỏng, không phải object, hay version khác
    `CHECKPOINT_VERSION` thì `ValueError` với lý do rõ — không đoán, không
    lặng lẽ trả checkpoint rỗng.
    """
    raw = store.get(key)
    if raw is None:
        raise ValueError(f"không có checkpoint tại khóa {key!r}")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"checkpoint tại khóa {key!r} không phải JSON hợp lệ") from exc
    if not isinstance(document, dict):
        raise ValueError(f"checkpoint tại khóa {key!r} phải là một object JSON")
    version = document.get("version")
    if version != CHECKPOINT_VERSION:
        raise ValueError(
            f"checkpoint tại khóa {key!r} có version {version!r}, "
            f"chỉ đọc được version {CHECKPOINT_VERSION} (không đoán format cũ)"
        )
    return Checkpoint.model_validate(document)


def _cases_done_of_key(key: str) -> int | None:
    """Số case đã xong mã trong khóa checkpoint; khóa không đúng dạng thì `None`."""
    name = key.rsplit("/", 1)[-1]
    if not name.endswith(".json"):
        return None
    stem = name[:-5]
    if not stem.isdigit():
        return None
    return int(stem)


def read_latest_checkpoint(store: CheckpointStore, prefix: str) -> Checkpoint | None:
    """Checkpoint mới nhất (số case đã xong lớn nhất) dưới `prefix`.

    Không có checkpoint nào dưới tiền tố thì `None`. Khóa không đúng dạng
    checkpoint (vd file lạ trong cùng thư mục) bị bỏ qua, không làm hỏng
    lần đọc.
    """
    candidates: list[tuple[int, str]] = []
    for key in store.list_keys(prefix):
        if not key.startswith(prefix + "/"):
            continue
        count = _cases_done_of_key(key)
        if count is not None:
            candidates.append((count, key))
    if not candidates:
        return None
    return read_checkpoint(store, max(candidates)[1])
