"""Driver thử nghiệm đứt phiên Kaggle (task 11.3, spec dòng 215).

Một lần thử là bốn lần chạy một điều kiện C (tham số, không hard-code):
thử 0 chạy liền mạch làm tham chiếu; thử 1 tự ngắt ở ranh giới lô; thử 2
tự ngắt giữa lô; thử 3 dừng thật bằng nút Stop của Kaggle (người vận hành
bấm, driver không có công tắc cho lần này). Phiên sau là phiên Kaggle mới,
nạp checkpoint mới nhất từ B2 bằng `read_latest_checkpoint` rồi chạy tiếp.

Driver chỉ là thư viện cho notebook Kaggle gọi: notebook dựng model thật
(vLLM qua adapter tương thích OpenAI) và đầu vào của điều kiện C, rồi gọi
`run_first_session` (phiên đầu) hoặc `run_resumed_session` (phiên sau, khi
`PRAXON_113_RESUME=1`). Driver ghi outcome JSON + usage log JSON ra thư
mục output (trên Kaggle là `/kaggle/working`) để tải về so bằng
`compare_11_3.py` trên máy này.

Công tắc ngắt chỉ ở driver, không sửa core:

- Thử 1: một luồng nền poll tiền tố checkpoint trên B2; thấy checkpoint
  đích thì giết process bằng `os._exit(137)` (mặc định). Giết muộn vài
  giây vẫn đúng: checkpoint dùng để resume là checkpoint đã ghi xong,
  lô đang chạy dở bị bỏ hết theo đúng 10.3.
- Thử 2: `CountingCachedModel` đếm lần gọi mô hình thật; tới ngưỡng
  (số lần gọi của các lô đã xong + 1) thì giết ngay trong lần gọi đó,
  trước khi trả phản hồi, nên lô đích chưa hoàn thành và chưa ghi
  checkpoint. Ngưỡng tính trước từ bố cục lô, in ra log trước khi chạy.

Trần token tắt trong mọi lần thử (`token_budget_total = 0`): biến duy nhất
bị thử là "đứt phiên". Checkpoint luôn ghi sang S3 (B2): checkpoint chỉ
nằm trên Kaggle là vi phạm bất biến plan con 11 nên driver từ chối chạy
khi `checkpoint_store` khác "s3".

Về cache: driver bọc model bằng `ResponseCache.get_or_call` (lần đầu cache
được nối ở production, xem E12 trong đề xuất). Cache hit không gọi mô
hình nên đóng 0 token; usage của lần gọi thật ghi vào usage log theo khóa
đệm (băm prompt + model_revision + tham số giải mã + schema). Phiên sau
nhập mục đệm từ checkpoint (`import_entries`) rồi chạy tiếp.

Về namespace lần thử (Phụ lục A.7): bốn lần thử cùng điều kiện nên cùng
tiền tố checkpoint gốc (`checkpoint_prefix` chỉ gồm tenant/seed/config/
data). Driver bọc store bằng `TrialNamespacedStore` để mỗi lần thử một
namespace riêng (`trial-{n}/` đặt trước mọi khóa) trên cùng bucket: lần
thử sau không nhìn thấy checkpoint của lần thử trước, còn hai phiên của
cùng một lần thử dùng chung namespace nên phiên sau vẫn resume đúng.
Wrapper trong suốt — phía gọi (coordinator, `read_latest_checkpoint`,
luồng poll) thấy khóa đúng dạng gốc, namespace chỉ tồn tại ở store dưới.
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from praxon_core.adapters.cache import ResponseCache, cache_key
from praxon_core.adapters.language_model import CompletionResult, LanguageModel
from praxon_core.adapters.s3_store import S3CheckpointStore
from praxon_core.learning.checkpoint import (
    Checkpoint,
    CheckpointStore,
    checkpoint_key,
    checkpoint_prefix,
    read_latest_checkpoint,
)
from praxon_core.learning.coordinator import (
    LearningRound,
    MeasuresFn,
    RoundOutcome,
    compute_config_hash,
    compute_config_hash_without_budget,
    run_learning_round,
)
from praxon_core.learning.curator import FactRead
from praxon_core.learning.generator import EpisodeRow
from praxon_core.learning.reflector import Reflector
from praxon_core.learning.rules import RuleTable
from praxon_core.settings import Settings

RESUME_ENV = "PRAXON_113_RESUME"
"""Biến môi trường báo phiên này chạy tiếp (`1`) thay vì chạy từ đầu."""

PREFIX_ENV = "PRAXON_113_PREFIX"
"""Biến môi trường cho tiền tố checkpoint (không đặt thì tự tính)."""

EXPECTED_KEY_ENV = "PRAXON_113_EXPECTED_KEY"
"""Biến môi trường cho khóa checkpoint đã định (không đặt thì không assert)."""

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
"""Một giá trị JSON thuần (đệ quy): vô hướng, danh sách hoặc object."""

__all__ = [
    "EXPECTED_KEY_ENV",
    "PREFIX_ENV",
    "RESUME_ENV",
    "CheckpointPollThread",
    "ChunkPlan",
    "ConditionInputs",
    "CountingCachedModel",
    "CountingCandidateIds",
    "TrialConfig",
    "TrialNamespacedStore",
    "TrialNotInterruptedError",
    "UsageLog",
    "build_s3_store",
    "outcome_to_dict",
    "plan_chunks",
    "read_trial_files",
    "resolve_prefix",
    "run_first_session",
    "run_resumed_session",
    "should_resume",
    "start_checkpoint_poll",
    "trial_namespace",
    "wait_for_checkpoint_key",
    "write_trial_files",
]


@dataclass(frozen=True)
class ChunkPlan:
    """Một lô case: số case và số lần gọi mô hình tối đa của lô đó.

    Một case cho đúng một trajectory (`generator.replay` nhóm theo case),
    nên số lần gọi của lô là trần của (số case / `reflector_batch_size`).
    """

    cases: int
    calls: int


def plan_chunks(
    *,
    episode_rows: Sequence[EpisodeRow],
    chunk_size: int,
    batch_size: int,
) -> list[ChunkPlan]:
    """Chia case thành lô theo đúng cách coordinator chia.

    Thứ tự case là thứ tự xuất hiện lần đầu trong `episode_rows` (giống
    `coordinator._case_order`); mỗi lô `chunk_size` case, lô cuối có thể
    ít hơn. Lô rỗng không tồn tại: không có case thì không có lô nào.
    """
    if chunk_size < 1:
        raise ValueError(f"chunk_size phải >= 1, nhận {chunk_size}")
    if batch_size < 1:
        raise ValueError(f"batch_size phải >= 1, nhận {batch_size}")
    case_order: list[str] = []
    seen: set[str] = set()
    for row in episode_rows:
        if row.case_id not in seen:
            seen.add(row.case_id)
            case_order.append(row.case_id)
    plans: list[ChunkPlan] = []
    for start in range(0, len(case_order), chunk_size):
        chunk = case_order[start : start + chunk_size]
        plans.append(ChunkPlan(cases=len(chunk), calls=math.ceil(len(chunk) / batch_size)))
    return plans


def resume_chunk_index(plans: Sequence[ChunkPlan], cases_done: int) -> int:
    """Lô đầu tiên chưa xong khi đã xong `cases_done` case.

    Checkpoint chỉ ghi ở ranh giới lô nên `cases_done` phải đúng bằng tổng
    số case của một số lô đầu; không đúng ranh giới thì từ chối ngay thay
    vì chạy tiếp từ điểm không hợp lệ.
    """
    done = 0
    for index, plan in enumerate(plans):
        if done == cases_done:
            return index
        done += plan.cases
    if done == cases_done:
        return len(plans)
    raise ValueError(
        f"cases_done={cases_done} không nằm ở ranh giới lô "
        f"(tổng case các lô: {[p.cases for p in plans]}): checkpoint lạ"
    )


@dataclass(frozen=True)
class TrialConfig:
    """Tham số một lần thử (điều kiện C là tham số, không hard-code).

    `trial`: 0 tham chiếu, 1 ranh giới lô, 2 giữa lô, 3 dừng thật.
    `interrupt`: "none" (thử 0 và 3, không có công tắc trong driver),
    "checkpoint" (thử 1: giết khi checkpoint sau lô `interrupt_chunk`
    xuất hiện), "calls" (thử 2: giết trong lần gọi đầu của lô
    `interrupt_chunk`). `interrupt_chunk` đếm từ 0.
    """

    condition: str
    trial: int
    interrupt: Literal["none", "checkpoint", "calls"] = "none"
    interrupt_chunk: int = 0
    poll_interval_s: float = 5.0

    def __post_init__(self) -> None:
        """Từ chối cấu hình thử không hợp lệ ngay lúc dựng."""
        if self.trial not in (0, 1, 2, 3):
            raise ValueError(f"trial phải là 0..3, nhận {self.trial}")
        if self.interrupt not in ("none", "checkpoint", "calls"):
            raise ValueError(f"interrupt lạ: {self.interrupt}")
        if self.interrupt_chunk < 0:
            raise ValueError(f"interrupt_chunk phải >= 0, nhận {self.interrupt_chunk}")
        if self.poll_interval_s <= 0:
            raise ValueError(f"poll_interval_s phải > 0, nhận {self.poll_interval_s}")


@dataclass(frozen=True)
class ConditionInputs:
    """Đầu vào dữ liệu của một điều kiện: episode, fact, bảng luật, hàm đếm.

    Điều kiện C do notebook (đường 11.2) dựng; driver chỉ nhận và chạy,
    không biết điều kiện đó là gì. `seed` là seed của vòng học (không nằm
    trong Settings); `data_hash` băm đầu vào dữ liệu của lần chạy.
    """

    tenant_id: str
    seed: int
    episode_rows: tuple[EpisodeRow, ...]
    facts: tuple[FactRead, ...]
    rule_table: RuleTable
    measures_for: MeasuresFn
    valid_start: datetime
    retired_at: datetime
    data_hash: str


@dataclass
class UsageLog:
    """Log usage từng lần gọi mô hình của một phiên.

    Mỗi mục là một lần Reflector gọi model: miss ghi usage thật
    (`prompt_tokens`/`completion_tokens`), hit ghi `{"hit": true}` (cache
    hit không gọi mô hình nên đóng 0 token). Khóa là khóa đệm
    (`cache_key`): cùng prompt + revision + tham số + schema thì cùng
    khóa ở cả hai phiên, nên script so sánh tra được usage đã tiết kiệm.
    """

    entries: list[dict[str, Any]] = field(default_factory=list)

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
        """Số lần gọi mô hình thật trong phiên (hit không tính)."""
        return sum(1 for entry in self.entries if "hit" not in entry)

    @property
    def cache_hits(self) -> int:
        """Số lần phục vụ từ cache trong phiên."""
        return sum(1 for entry in self.entries if entry.get("hit") is True)

    @property
    def total_tokens(self) -> int:
        """Tổng token đã đóng trong phiên (hit đóng 0)."""
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
        entries: list[dict[str, Any]] = []
        for entry in raw:
            if not isinstance(entry, dict) or not isinstance(entry.get("key"), str):
                raise ValueError(f"mục usage log sai hình dạng: {entry!r}")
            if entry.get("hit") is True:
                entries.append({"key": entry["key"], "hit": True})
            elif isinstance(entry.get("prompt_tokens"), int) and isinstance(
                entry.get("completion_tokens"), int
            ):
                entries.append(
                    {
                        "key": entry["key"],
                        "prompt_tokens": entry["prompt_tokens"],
                        "completion_tokens": entry["completion_tokens"],
                    }
                )
            else:
                raise ValueError(f"mục usage log sai hình dạng: {entry!r}")
        return cls(entries=entries)


class TrialNotInterruptedError(RuntimeError):
    """Công tắc ngắt đã gài mà vòng chạy xong không đứt.

    Lần thử như vậy không đo được gì (không có phiên đứt để chạy tiếp)
    nên phải báo lỗi rõ thay vì ghi một outcome "đầy đủ" giả.
    """


def trial_namespace(trial: int) -> str:
    """Namespace khóa của một lần thử trên store (`trial-{n}`).

    Mỗi lần thử một namespace riêng trên cùng bucket (Phụ lục A.7):
    bốn lần thử cùng điều kiện nên cùng tiền tố checkpoint gốc, nhưng
    namespace tách chúng ra — lần thử sau không nhìn thấy checkpoint
    của lần thử trước, còn hai phiên của cùng một lần thử dùng chung
    namespace nên phiên sau vẫn resume đúng checkpoint của phiên trước.
    """
    if trial not in (0, 1, 2, 3):
        raise ValueError(f"trial phải là 0..3, nhận {trial}")
    return f"trial-{trial}"


class TrialNamespacedStore:
    """CheckpointStore bọc một store khác, đặt mọi khóa dưới namespace lần thử.

    Trong suốt với phía gọi (Phụ lục A.7): `put`/`get` thêm
    `trial-{n}/` vào đầu khóa; `list_keys(prefix)` hỏi store trong bằng
    tiền tố đã thêm namespace rồi LỘT namespace khỏi khóa trả về, nên
    coordinator, `read_latest_checkpoint` (lọc `key.startswith(prefix +
    "/")`) và luồng poll đều thấy khóa đúng dạng gốc — namespace chỉ
    tồn tại ở store dưới. Khóa nào store trong trả về mà không nằm dưới
    namespace (store trong sai hợp đồng) thì bị bỏ qua, không lọt ra
    ngoài dưới dạng khóa lạ.
    """

    def __init__(self, *, store: CheckpointStore, trial: int) -> None:
        """Bọc store với namespace của lần thử `trial`."""
        self._store = store
        self._namespace = trial_namespace(trial)

    @property
    def namespace(self) -> str:
        """Tiền tố namespace của lần thử này (`trial-{n}`)."""
        return self._namespace

    def _namespaced(self, key: str) -> str:
        return f"{self._namespace}/{key}"

    def put(self, key: str, data: bytes) -> None:
        """Ghi object vào khóa, dưới namespace lần thử."""
        self._store.put(self._namespaced(key), data)

    def get(self, key: str) -> bytes | None:
        """Đọc object tại khóa, dưới namespace lần thử."""
        return self._store.get(self._namespaced(key))

    def list_keys(self, prefix: str) -> list[str]:
        """Liệt kê khóa có tiền tố, đã lột namespace, đã sắp xếp."""
        namespaced_prefix = self._namespaced(prefix)
        stripped: list[str] = []
        for key in self._store.list_keys(namespaced_prefix):
            if not key.startswith(self._namespace + "/"):
                continue
            stripped.append(key[len(self._namespace) + 1 :])
        return stripped


class CountingCachedModel:
    """LanguageModel bọc cache + đếm lần gọi + công tắc ngắt (thử 2).

    Miss thì gọi model thật, ghi usage vào log; hit thì trả phản hồi đã
    lưu với 0 token (không gọi model). Tới ngưỡng `kill_after_calls`
    (số lần gọi thật) thì gọi `kill()` ngay trong lần gọi đó, trước khi
    trả phản hồi: lô đang chạy chưa hoàn thành nên chưa ghi checkpoint.
    Mặc định `kill` là `os._exit(137)` (giết process không cleanup, giống
    SIGKILL nhất); test truyền kill giả để không giết process test.
    """

    def __init__(
        self,
        *,
        model: LanguageModel,
        cache: ResponseCache,
        model_revision: str,
        usage_log: UsageLog,
        kill_after_calls: int | None = None,
        kill: Callable[[], None] | None = None,
    ) -> None:
        """Giữ model + cache + log; chưa gọi mạng lúc dựng."""
        self._model = model
        self._cache = cache
        self._model_revision = model_revision
        self._usage_log = usage_log
        self._kill_after_calls = kill_after_calls
        self._kill = kill if kill is not None else (lambda: os._exit(137))
        self._calls = 0
        self._hits = 0

    @property
    def calls(self) -> int:
        """Số lần gọi mô hình thật từ đầu phiên."""
        return self._calls

    @property
    def hits(self) -> int:
        """Số lần phục vụ từ cache từ đầu phiên."""
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
        """Hoàn thành một prompt, qua cache; tới ngưỡng thì giết trước khi trả."""
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
        if self._kill_after_calls is not None and self._calls >= self._kill_after_calls:
            self._kill()
        return CompletionResult(
            text=text,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
        )


class CountingCandidateIds:
    """Sinh candidate ID theo bộ đếm, nối tiếp từ một điểm bắt đầu (R4).

    Phiên 1 đếm từ 0; phiên sau đếm tiếp từ `len(checkpoint.candidate_ids)`
    để ID không trùng và không đếm lại. Không dùng UUID/ngẫu nhiên: ID
    phải giống hệt lần tham chiếu thì `candidate_ids` mới bằng nhau.
    """

    def __init__(self, *, start: int = 0) -> None:
        """Bắt đầu đếm từ `start`."""
        if start < 0:
            raise ValueError(f"start phải >= 0, nhận {start}")
        self._next = start

    def __call__(self) -> str:
        """Trả ID tiếp theo (`candidate-{n}`)."""
        candidate_id = f"candidate-{self._next}"
        self._next += 1
        return candidate_id


def should_resume() -> bool:
    """Phiên này có phải phiên chạy tiếp không (env `PRAXON_113_RESUME=1`)."""
    return os.environ.get(RESUME_ENV) == "1"


def resolve_prefix(*, tenant_id: str, seed: int, config_hash: str, data_hash: str) -> str:
    """Tiền tố checkpoint: env `PRAXON_113_PREFIX` nếu có, không thì tự tính."""
    explicit = os.environ.get(PREFIX_ENV)
    if explicit:
        return explicit
    return checkpoint_prefix(
        tenant_id=tenant_id, seed=seed, config_hash=config_hash, data_hash=data_hash
    )


def build_s3_store(settings: Settings) -> S3CheckpointStore:
    """Dựng store S3 từ Settings; thiếu endpoint/bucket/khóa thì từ chối ngay."""
    if settings.s3_endpoint_url is None or settings.s3_bucket is None:
        raise ValueError(
            "checkpoint_store=s3 mà thiếu s3_endpoint_url/s3_bucket trong Settings"
        )
    if settings.s3_access_key_id is None or settings.s3_secret_access_key is None:
        raise ValueError(
            "checkpoint_store=s3 mà thiếu khóa S3 trong Settings (env PRAXON_S3_*)"
        )
    return S3CheckpointStore(
        bucket=settings.s3_bucket,
        endpoint_url=settings.s3_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
    )


def wait_for_checkpoint_key(
    *,
    store: CheckpointStore,
    prefix: str,
    target_key: str,
    poll_interval_s: float = 5.0,
    timeout_s: float | None = None,
    kill: Callable[[], None],
    stop: threading.Event | None = None,
) -> bool:
    """Poll store đến khi `target_key` xuất hiện thì gọi `kill()`.

    Trả True nếu đã giết, False nếu hết `timeout_s` mà khóa chưa xuất
    hiện (`timeout_s=None` thì poll tới khi khóa xuất hiện) hoặc khi
    `stop` được đặt (dừng có chủ đích, không giết). Chỉ đọc B2,
    không ghi gì. Lỗi mạng lúc list thì để lỗi lan ra (không nuốt rồi
    giết nhầm): lần thử hỏng vì lý do rõ thay vì đứt sai điểm.
    """
    if poll_interval_s <= 0:
        raise ValueError(f"poll_interval_s phải > 0, nhận {poll_interval_s}")
    deadline = None if timeout_s is None else time.monotonic() + timeout_s
    while True:
        if target_key in store.list_keys(prefix):
            kill()
            return True
        if stop is not None and stop.is_set():
            return False
        if deadline is not None and time.monotonic() >= deadline:
            return False
        time.sleep(poll_interval_s)


class CheckpointPollThread(threading.Thread):
    """Luồng poll checkpoint, dừng được bằng `stop()`.

    Dừng có chủ đích khi vòng chạy kết thúc mà checkpoint đích chưa xuất
    hiện (ví dụ công tắc không nổ): luồng daemon không tự dừng sẽ poll
    mãi trong tiến trình gọi, làm rò rỉ luồng và nhiễu các test khác
    (đã gặp: luồng rò gọi `time.sleep` bị test khác monkeypatch ghi lại).
    """

    def __init__(
        self,
        *,
        store: CheckpointStore,
        prefix: str,
        target_key: str,
        poll_interval_s: float = 5.0,
        kill: Callable[[], None],
    ) -> None:
        """Dựng luồng poll (chưa chạy); `stop()` đặt cờ dừng."""
        self.stop_event = threading.Event()
        super().__init__(
            target=wait_for_checkpoint_key,
            kwargs={
                "store": store,
                "prefix": prefix,
                "target_key": target_key,
                "poll_interval_s": poll_interval_s,
                "timeout_s": None,
                "kill": kill,
                "stop": self.stop_event,
            },
            daemon=True,
        )

    def stop(self) -> None:
        """Đặt cờ dừng; luồng thoát ở lần kiểm tiếp theo."""
        self.stop_event.set()


def start_checkpoint_poll(
    *,
    store: CheckpointStore,
    prefix: str,
    target_key: str,
    poll_interval_s: float = 5.0,
    kill: Callable[[], None],
) -> CheckpointPollThread:
    """Chạy `wait_for_checkpoint_key` trên luồng nền (daemon).

    Luồng chỉ đọc B2 và giết process khi checkpoint đích xuất hiện; nó
    không chặn vòng chạy kết thúc (daemon). Driver dừng luồng này sau
    khi vòng chạy xong (kể cả khi vòng chạy lỗi) để không rò rỉ luồng.
    """
    thread = CheckpointPollThread(
        store=store,
        prefix=prefix,
        target_key=target_key,
        poll_interval_s=poll_interval_s,
        kill=kill,
    )
    thread.start()
    return thread


def _json_scalar(value: object) -> str | int | float | bool | None:
    """Chuyển một giá trị vô hướng thành giá trị JSON thuần.

    datetime/date thành ISO, UUID thành chuỗi, Enum thành giá trị của nó;
    str/int/float/bool/None giữ nguyên; loại khác thì lỗi rõ thay vì bị
    `str()` nuốt lặng lẽ thành chuỗi khó so.
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"không chuyển được {type(value).__name__} thành JSON")


def _to_jsonable(value: object) -> JsonValue:
    """Chuyển một giá trị (pydantic/dataclass/dict/list) thành JSON thuần.

    Pydantic dùng `model_dump(mode="json")`; dataclass dùng `asdict` rồi
    đệ quy từng giá trị (asdict không chạm tới Enum/datetime/UUID nên
    phải chuyển thêm ở đây); dict/list/tuple đệ quy theo phần tử.
    """
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {key: _to_jsonable(item) for key, item in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return _json_scalar(value)


def outcome_to_dict(
    *,
    trial: int,
    condition: str,
    session: str,
    outcome: RoundOutcome,
    model_calls: int,
    cache_hits: int,
    cases_per_chunk: Sequence[int],
    calls_per_chunk: Sequence[int],
    checkpoint_key: str | None,
    checkpoint_namespace: str,
    cases_done_at_resume: int | None,
    expected_remaining_calls: int | None,
    stop_point_note: str | None,
    wall_time_s: float,
) -> dict[str, Any]:
    """Outcome một phiên thành dict JSON (ghi ra `outcome.json`).

    Bảy trường nội dung so bằng nhau tuyệt đối ở A.4 là `trajectories`,
    `insights`, `decisions`, `candidate_ids`, `fact_rows`, `fact_closes`
    và `run_status`. `events` không nằm trong bảy trường (theo tiền lệ
    10.3: lịch sử event của lần resume khác lần tham chiếu) nên chỉ ghi
    tóm tắt số lượng + loại làm bằng chứng chẩn đoán. `wall_time_s` là
    thời gian tường do driver đo (không nằm trong `run_row`).
    """
    actions: dict[str, int] = {}
    for event in outcome.events:
        actions[event.action] = actions.get(event.action, 0) + 1
    raw: dict[str, Any] = {
        "trial": trial,
        "condition": condition,
        "session": session,
        "checkpoint_key": checkpoint_key,
        "checkpoint_namespace": checkpoint_namespace,
        "cases_done_at_resume": cases_done_at_resume,
        "expected_remaining_calls": expected_remaining_calls,
        "stop_point_note": stop_point_note,
        "model_calls": model_calls,
        "cache_hits": cache_hits,
        "cases_per_chunk": list(cases_per_chunk),
        "calls_per_chunk": list(calls_per_chunk),
        "trajectories": [_to_jsonable(item) for item in outcome.trajectories],
        "insights": [_to_jsonable(item) for item in outcome.insights],
        "decisions": [_to_jsonable(item) for item in outcome.decisions],
        "candidate_ids": list(outcome.candidate_ids),
        "fact_rows": [_to_jsonable(item) for item in outcome.fact_rows],
        "fact_closes": [_to_jsonable(item) for item in outcome.fact_closes],
        "run_status": outcome.run_row.status,
        "tokens_in": outcome.run_row.tokens_in,
        "tokens_out": outcome.run_row.tokens_out,
        "wall_time_s": wall_time_s,
        "events_summary": {"count": len(outcome.events), "actions": actions},
    }
    converted = _to_jsonable(raw)
    if not isinstance(converted, dict):
        raise TypeError("outcome không phải object JSON")
    return converted


def write_trial_files(
    output_dir: Path, outcome: Mapping[str, Any], usage_log: UsageLog
) -> tuple[Path, Path]:
    """Ghi `outcome.json` + `usage_log.json` vào `output_dir`.

    Tạo thư mục nếu chưa có. Trả đường dẫn hai file đã ghi.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    outcome_path = output_dir / "outcome.json"
    usage_path = output_dir / "usage_log.json"
    outcome_path.write_text(json.dumps(outcome, indent=2, ensure_ascii=False), encoding="utf-8")
    usage_path.write_text(
        json.dumps(usage_log.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return outcome_path, usage_path


def read_trial_files(output_dir: Path) -> tuple[dict[str, Any], UsageLog]:
    """Nạp lại `outcome.json` + `usage_log.json` từ `output_dir`."""
    outcome_path = output_dir / "outcome.json"
    usage_path = output_dir / "usage_log.json"
    outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
    if not isinstance(outcome, dict):
        raise ValueError(f"outcome.json sai hình dạng (không phải object): {outcome_path}")
    usage = UsageLog.from_dict(json.loads(usage_path.read_text(encoding="utf-8")))
    return outcome, usage


@dataclass
class _Session:
    """Trạng thái một phiên chạy: vòng học + reflector + model bọc + log."""

    round: LearningRound
    reflector: Reflector
    wrapped: CountingCachedModel
    candidate_ids: CountingCandidateIds
    usage_log: UsageLog
    cache: ResponseCache


def _validate_settings(settings: Settings) -> None:
    """Ép điều kiện chạy của 11.3 trước khi vòng học bắt đầu.

    Trần token phải tắt (biến duy nhất bị thử là "đứt phiên"); phải ghi
    checkpoint (không có checkpoint thì không có gì để resume); checkpoint
    phải sang S3 (ghi local trên Kaggle là vi phạm bất biến "checkpoint
    không bao giờ chỉ nằm trên Kaggle").
    """
    if settings.token_budget_total != 0:
        raise ValueError("11.3 tắt trần token: token_budget_total phải bằng 0")
    if settings.checkpoint_every_n_cases < 1:
        raise ValueError("11.3 cần checkpoint_every_n_cases >= 1 để có checkpoint mà resume")
    if settings.checkpoint_store != "s3":
        raise ValueError("11.3 ghi checkpoint sang S3: checkpoint_store phải là 's3'")
    if settings.reflector_batch_size < 1:
        raise ValueError(
            f"reflector_batch_size phải >= 1, nhận {settings.reflector_batch_size}"
        )


def _prepare_session(
    *,
    config: TrialConfig,
    inputs: ConditionInputs,
    settings: Settings,
    code_commit: str,
    model: LanguageModel,
    store: CheckpointStore,
    resume_from: Checkpoint | None,
    kill_after_calls: int | None,
    kill: Callable[[], None],
) -> _Session:
    """Dựng vòng học + reflector + model bọc cho một phiên.

    Phiên sau nhập mục đệm từ checkpoint và đếm candidate ID nối tiếp từ
    `len(checkpoint.candidate_ids)`; phiên đầu bắt đầu từ đệm rỗng và ID
    0. Reflector dựng với `seed` của vòng học và temperature 0.0 (xác
    định, spec dòng 191). Trần tắt nên `token_budget_total=0` ở cả hai
    phiên; `config_hash_no_budget` ghi vào checkpoint cho cổng resume.
    """
    cache = ResponseCache()
    if resume_from is not None:
        cache.import_entries(resume_from.cache_entries)
    usage_log = UsageLog()
    wrapped = CountingCachedModel(
        model=model,
        cache=cache,
        model_revision=settings.model_revision,
        usage_log=usage_log,
        kill_after_calls=kill_after_calls,
        kill=kill,
    )
    reflector = Reflector(
        wrapped,
        batch_size=settings.reflector_batch_size,
        max_insights_per_batch=settings.reflector_max_insights_per_batch,
        seed=inputs.seed,
        temperature=0.0,
    )
    candidate_ids = CountingCandidateIds(
        start=len(resume_from.candidate_ids) if resume_from is not None else 0
    )
    round_ = LearningRound(
        tenant_id=inputs.tenant_id,
        episode_rows=inputs.episode_rows,
        facts=inputs.facts,
        rule_table=inputs.rule_table,
        seed=inputs.seed,
        model_id=settings.model_id,
        model_revision=settings.model_revision,
        code_commit=code_commit,
        config_hash=compute_config_hash(settings),
        data_hash=inputs.data_hash,
        valid_start=inputs.valid_start,
        retired_at=inputs.retired_at,
        checkpoint_every_n_cases=settings.checkpoint_every_n_cases,
        checkpoint_store=store,
        resume_from=resume_from,
        cache=cache,
        token_budget_total=0,
        token_budget_reserve_per_call=settings.token_budget_reserve_per_call,
        reflector_batch_size=settings.reflector_batch_size,
        config_hash_no_budget=compute_config_hash_without_budget(settings),
    )
    return _Session(
        round=round_,
        reflector=reflector,
        wrapped=wrapped,
        candidate_ids=candidate_ids,
        usage_log=usage_log,
        cache=cache,
    )


def run_first_session(
    *,
    config: TrialConfig,
    inputs: ConditionInputs,
    settings: Settings,
    code_commit: str,
    model: LanguageModel,
    store: CheckpointStore,
    output_dir: Path,
    kill: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Chạy phiên đầu của một lần thử (tham chiếu hoặc phiên bị đứt).

    Thử 1 gài luồng poll checkpoint (thấy checkpoint đích thì giết);
    thử 2 gài ngưỡng đếm lần gọi (tới ngưỡng thì giết trong lần gọi đó);
    thử 0 và 3 không gài công tắc nào (thử 3 do người vận hành bấm Stop).
    `kill` mặc định là `os._exit(137)`; test truyền kill giả để không
    giết process test. Nếu công tắc đã gài mà vòng chạy xong không đứt
    thì raise `TrialNotInterruptedError` (lần thử không đo được gì).
    Trả outcome dict (đã ghi ra `output_dir`).
    """
    _validate_settings(settings)
    # Bọc store theo lần thử (A.7): mọi khóa coordinator/store dùng đều
    # đi qua namespace `trial-{n}` của lần thử này, kể cả luồng poll và
    # lần đọc checkpoint mới nhất ở phiên sau. Notebook truyền store S3
    # trần vào; driver tự bọc, phía gọi không cần biết namespace.
    store = TrialNamespacedStore(store=store, trial=config.trial)
    plans = plan_chunks(
        episode_rows=inputs.episode_rows,
        chunk_size=settings.checkpoint_every_n_cases,
        batch_size=settings.reflector_batch_size,
    )
    if not plans:
        raise ValueError("điều kiện không có case nào: không có gì để thử")
    if config.interrupt == "checkpoint" and config.interrupt_chunk >= len(plans) - 1:
        raise ValueError(
            f"interrupt_chunk={config.interrupt_chunk} là lô cuối: checkpoint sau nó "
            "là checkpoint cuối, không còn gì để chạy tiếp"
        )
    if config.interrupt == "calls" and config.interrupt_chunk >= len(plans):
        raise ValueError(
            f"interrupt_chunk={config.interrupt_chunk} vượt số lô ({len(plans)} lô)"
        )
    kill_fn = kill if kill is not None else (lambda: os._exit(137))
    kill_fired = threading.Event()

    def _kill_once() -> None:
        """Ghi nhận công tắc đã nổ rồi mới giết thật (để driver kiểm được)."""
        kill_fired.set()
        kill_fn()

    prefix = resolve_prefix(
        tenant_id=inputs.tenant_id,
        seed=inputs.seed,
        config_hash=compute_config_hash(settings),
        data_hash=inputs.data_hash,
    )
    poll_thread: CheckpointPollThread | None = None
    kill_after_calls: int | None = None
    if config.interrupt == "checkpoint":
        cases_done = sum(plan.cases for plan in plans[: config.interrupt_chunk + 1])
        target_key = checkpoint_key(prefix, cases_done)
        if target_key in store.list_keys(prefix):
            raise ValueError(
                f"checkpoint đích {target_key} đã tồn tại trước khi phiên bắt đầu: "
                f"lần thử {config.trial} đã chạy rồi trên cùng store (checkpoint "
                "của chính lần thử này còn trong namespace của nó) nên luồng poll "
                "sẽ giết ngay lập tức. Dọn namespace của lần thử này trên store "
                "hoặc dùng store/bucket khác trước khi chạy lại."
            )
        poll_thread = start_checkpoint_poll(
            store=store,
            prefix=prefix,
            target_key=target_key,
            poll_interval_s=config.poll_interval_s,
            kill=_kill_once,
        )
    elif config.interrupt == "calls":
        kill_after_calls = sum(plan.calls for plan in plans[: config.interrupt_chunk]) + 1
    session = _prepare_session(
        config=config,
        inputs=inputs,
        settings=settings,
        code_commit=code_commit,
        model=model,
        store=store,
        resume_from=None,
        kill_after_calls=kill_after_calls,
        kill=_kill_once,
    )
    start = time.perf_counter()
    try:
        outcome = run_learning_round(
            session.round,
            reflect=session.reflector.reflect,
            measures_for=inputs.measures_for,
            candidate_id_for=session.candidate_ids,
        )
    finally:
        wall_time_s = time.perf_counter() - start
        if poll_thread is not None:
            poll_thread.stop()
            poll_thread.join(timeout=config.poll_interval_s * 2 + 1.0)
    if config.interrupt != "none" and not kill_fired.is_set():
        raise TrialNotInterruptedError(
            f"công tắc ngắt ({config.interrupt}) đã gài mà vòng chạy xong không đứt: "
            "lần thử không đo được gì, kiểm lại điểm ngắt"
        )
    result = outcome_to_dict(
        trial=config.trial,
        condition=config.condition,
        session="first",
        outcome=outcome,
        model_calls=session.wrapped.calls,
        cache_hits=session.wrapped.hits,
        cases_per_chunk=[plan.cases for plan in plans],
        calls_per_chunk=[plan.calls for plan in plans],
        checkpoint_key=None,
        checkpoint_namespace=trial_namespace(config.trial),
        cases_done_at_resume=None,
        expected_remaining_calls=None,
        stop_point_note=None,
        wall_time_s=wall_time_s,
    )
    write_trial_files(output_dir, result, session.usage_log)
    return result


def run_resumed_session(
    *,
    config: TrialConfig,
    inputs: ConditionInputs,
    settings: Settings,
    code_commit: str,
    model: LanguageModel,
    store: CheckpointStore,
    output_dir: Path,
    expected_checkpoint_key: str | None = None,
    kill: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Chạy phiên sau: nạp checkpoint mới nhất từ B2 rồi chạy tiếp.

    List tiền tố và in khóa sẽ dùng; đọc checkpoint mới nhất bằng
    `read_latest_checkpoint`. Khóa thực tế khác khóa đã định thì KHÔNG
    dừng lại mà ghi vào `stop_point_note` và phân loại lại lần thử theo
    điểm dừng thật (R1): checkpoint mới hơn vẫn là điểm dừng hợp lệ ở
    ranh giới lô, chỉ khác điểm đã định. Không có checkpoint nào, reader
    từ chối, hoặc cổng resume từ chối thì dừng ngay với lỗi rõ (không
    chạy tiếp mù). Không còn case nào để chạy tiếp (phiên đầu đã chạy
    hết) thì cũng từ chối: lần thử đó không đứt nên so sánh sẽ rỗng.
    Trả outcome dict (đã ghi ra `output_dir`).
    """
    _validate_settings(settings)
    # Bọc store theo lần thử (A.7) như phiên đầu: phiên sau chỉ thấy
    # checkpoint của chính lần thử này, dù các lần thử khác đã ghi cùng
    # tiền tố gốc lên cùng bucket.
    store = TrialNamespacedStore(store=store, trial=config.trial)
    plans = plan_chunks(
        episode_rows=inputs.episode_rows,
        chunk_size=settings.checkpoint_every_n_cases,
        batch_size=settings.reflector_batch_size,
    )
    if not plans:
        raise ValueError("điều kiện không có case nào: không có gì để thử")
    config_hash = compute_config_hash(settings)
    prefix = resolve_prefix(
        tenant_id=inputs.tenant_id,
        seed=inputs.seed,
        config_hash=config_hash,
        data_hash=inputs.data_hash,
    )
    keys = store.list_keys(prefix)
    if not keys:
        raise ValueError(
            f"không có checkpoint nào dưới tiền tố {prefix}: chưa có phiên đầu hay tiền tố sai"
        )
    checkpoint = read_latest_checkpoint(store, prefix)
    if checkpoint is None:
        raise ValueError(f"không đọc được checkpoint mới nhất dưới tiền tố {prefix}")
    actual_key = checkpoint_key(prefix, len(checkpoint.cases_done))
    expected_key = expected_checkpoint_key
    if expected_key is None:
        expected_key = os.environ.get(EXPECTED_KEY_ENV) or None
    stop_point_note: str | None = None
    if expected_key is not None and actual_key != expected_key:
        stop_point_note = (
            f"điểm dừng thật khác điểm đã định: checkpoint dùng {actual_key}, "
            f"đã định {expected_key} (phân loại lại theo điểm thật, xem R1)"
        )
    cases_done = len(checkpoint.cases_done)
    resume_at = resume_chunk_index(plans, cases_done)
    expected_remaining_calls = sum(plan.calls for plan in plans[resume_at:])
    if expected_remaining_calls == 0:
        raise ValueError(
            "không còn case nào để chạy tiếp: phiên đầu đã chạy hết, "
            "lần thử không đứt nên không có gì để so"
        )
    kill_fn = kill if kill is not None else (lambda: os._exit(137))
    session = _prepare_session(
        config=config,
        inputs=inputs,
        settings=settings,
        code_commit=code_commit,
        model=model,
        store=store,
        resume_from=checkpoint,
        kill_after_calls=None,
        kill=kill_fn,
    )
    start = time.perf_counter()
    outcome = run_learning_round(
        session.round,
        reflect=session.reflector.reflect,
        measures_for=inputs.measures_for,
        candidate_id_for=session.candidate_ids,
    )
    wall_time_s = time.perf_counter() - start
    result = outcome_to_dict(
        trial=config.trial,
        condition=config.condition,
        session="resumed",
        outcome=outcome,
        model_calls=session.wrapped.calls,
        cache_hits=session.wrapped.hits,
        cases_per_chunk=[plan.cases for plan in plans],
        calls_per_chunk=[plan.calls for plan in plans],
        checkpoint_key=actual_key,
        checkpoint_namespace=trial_namespace(config.trial),
        cases_done_at_resume=cases_done,
        expected_remaining_calls=expected_remaining_calls,
        stop_point_note=stop_point_note,
        wall_time_s=wall_time_s,
    )
    write_trial_files(output_dir, result, session.usage_log)
    return result
