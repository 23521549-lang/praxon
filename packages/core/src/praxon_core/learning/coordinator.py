"""Bộ điều phối mỏng nối sáu vai (plan con 10, task 10.1; spec: Hợp đồng vòng học).

Sáu vai, theo thứ tự một vòng học: Generator (replay trace, không mô hình),
Reflector (một lần gọi mô hình cho mỗi batch — ở lát cắt này chưa có task
6.2 nên vai này được TIÊM VÀO qua tham số `reflect`, không tự bịa),
Curator (Insight thành Delta, không mô hình), Governor (luật thuần),
Applier (scope tenant) và Promoter (scope global). Mỗi vai vẫn là một hàm
thuần trên kiểu dữ liệu có cấu trúc của nó; bộ điều phối chỉ nối chúng lại
và ghi `run` — không vai nào gọi vai khác.

Hàm thuần nghĩa là: không chạm DB, không gọi mô hình, không tự lấy giờ
(`valid_start`, `retired_at`, `wall_time` đều do người gọi truyền vào).
Người gọi chịu trách nhiệm ghi xuống DB: `run` qua
`repositories.runs.insert_run`, event qua `repositories.events.insert_event`,
fact qua `repositories.facts.insert_fact`/`close_fact`, mỗi thứ bằng kết nối
dưới đúng vai — bộ điều phối chỉ xây các hàng đó, không giữ kết nối nào.

Ghi `run`: một lần chạy ghi đủ sáu trường điều kiện tái lập (spec, dòng
191) — `seed`, `model_id`, `model_revision`, `code_commit`, `config_hash`,
`data_hash` — cộng token vào ra và trạng thái. `code_commit` do người gọi
truyền vào (vd `git rev-parse HEAD` lúc chạy); coordinator không tự gọi
git. `config_hash` băm toàn bộ cấu hình TRỪ `database_url` và
`openai_api_key` (đổi DB hay xoay khóa không đổi kết quả nên không đổi
hash; khóa cũng không được đưa vào hash). `data_hash` gộp hai nửa theo
quy tắc F-10 (xem `merge_data_hash`).

Khóa phần đo (spec, dòng 152 + bảng NFR): cấu hình bị khóa bằng commit
trước khi chạm phần đo lần đầu; coordinator từ chối chạy trên phần đo
khi `config_hash` khác khóa.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel

from praxon_core.adapters.cache import ResponseCache
from praxon_core.learning.applier import (
    apply_candidate,
    build_fact_close,
    promote_candidate,
)
from praxon_core.learning.candidate import Candidate, DecisionVerdict, GovernorResult
from praxon_core.learning.checkpoint import (
    Checkpoint,
    CheckpointStore,
    checkpoint_prefix,
    write_checkpoint,
)
from praxon_core.learning.curator import (
    Delta,
    DeltaKind,
    FactRead,
    Insight,
    curate,
    to_candidate,
)
from praxon_core.learning.event_log import (
    governor_decision_event,
    role_call_event,
)
from praxon_core.learning.generator import EpisodeRow, Trajectory, replay
from praxon_core.learning.governor import decide
from praxon_core.learning.measures import Measures
from praxon_core.learning.payload import FactPayload
from praxon_core.learning.rules import RuleTable
from praxon_core.repositories.events import EventRow
from praxon_core.repositories.facts import FactClose, FactRow
from praxon_core.repositories.runs import RunRow
from praxon_core.settings import Settings

REPRODUCIBILITY_CONDITIONS: tuple[str, ...] = (
    "seed",
    "model",
    "code_commit",
    "config_hash",
    "data_hash",
    "cache",
)
"""Sáu điều kiện tái lập (spec, dòng 191).

`model` là MỘT điều kiện gồm cả `model_id` + `model_revision`; `cache`
là cache còn nguyên (không phải một cột của bảng `run`).
"""


def _canonical_json(value: object) -> str:
    """JSON chuẩn của một giá trị: khóa sắp xếp, không khoảng trắng thừa.

    Pydantic thì `model_dump(mode="json")`, dãy thì đệ quy từng phần tử,
    còn lại dùng nguyên giá trị; `default=str` cho datetime và các kiểu
    lạ. Cùng một dữ liệu vào thì luôn ra cùng một chuỗi — hash trên chuỗi
    này mới có ý nghĩa tái lập.
    """
    if isinstance(value, BaseModel):
        normalized: object = value.model_dump(mode="json")
    elif isinstance(value, (list, tuple)):
        normalized = [_canonical_json(item) for item in value]
    else:
        normalized = value
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)


def payload_hash(value: object) -> str:
    """SHA-256 của dữ liệu vào một lần gọi vai (cho `event.payload_hash`)."""
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


_CONFIG_HASH_EXCLUDED: tuple[str, ...] = (
    "database_url",
    "openai_api_key",
    "s3_endpoint_url",
    "s3_bucket",
    "s3_access_key_id",
    "s3_secret_access_key",
)
"""Trường Settings không vào `config_hash`: đổi DB, đổi nơi lưu checkpoint
hay xoay khóa không đổi kết quả nên không được đổi hash; khóa thì không bao
giờ được đưa vào hash."""


def _hash_config(settings: Settings, *, without_budget: bool) -> str:
    """Băm cấu hình chạy; `without_budget` thì loại thêm hai trường trần."""
    data = settings.model_dump(mode="json")
    for key in _CONFIG_HASH_EXCLUDED:
        data.pop(key, None)
    if without_budget:
        data.pop("token_budget_total", None)
        data.pop("token_budget_reserve_per_call", None)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_config_hash(settings: Settings) -> str:
    """Băm cấu hình chạy thành `config_hash` (một trong sáu trường của `run`).

    Băm toàn bộ cấu hình TRỪ `database_url`, `openai_api_key` và bốn trường
    S3 (`s3_endpoint_url`, `s3_bucket`, `s3_access_key_id`,
    `s3_secret_access_key`): đổi DB, đổi nơi lưu checkpoint hay xoay khóa
    không đổi kết quả nên không được đổi hash; khóa thì không bao giờ được
    đưa vào hash. Mọi trường còn lại đổi là hash đổi — thận trọng: đổi cấu
    hình thì lần chạy cũ không còn tái lập được.
    """
    return _hash_config(settings, without_budget=False)


def compute_config_hash_without_budget(settings: Settings) -> str:
    """Băm cấu hình đã loại hai trường trần (task 10.4).

    Giống `compute_config_hash` nhưng loại thêm `token_budget_total` và
    `token_budget_reserve_per_call`: hai vòng chỉ khác trần thì có cùng
    hash-trừ-trần, để cổng resume chứng minh được "chỉ khác trần" (xem
    `_check_resume_matches`). CHỈ dùng cho cổng resume — `run` vẫn ghi
    `config_hash` toàn phần (đổi trần là đổi kết quả nên phải đổi hash).
    """
    return _hash_config(settings, without_budget=True)


def merge_data_hash(*, bpic_hash: str | None = None, generator_hash: str | None = None) -> str:
    """Gộp hai nửa `data_hash` thành `data_hash` của một lần chạy (quy tắc F-10).

    `data_hash` của một lần chạy băm TẤT CẢ đầu vào dữ liệu: nửa BPIC
    (log + tham số chia + danh sách tenant, task 3.3) nối tiếp nửa bộ
    sinh (seed + tham số bộ sinh + tenant, task 5.4), theo thứ tự CỐ
    ĐỊNH — BPIC trước, bộ sinh sau. Nửa nào không áp dụng thì bỏ qua;
    chỉ còn một nửa thì băm một mình nửa đó (kết quả KHÁC chính nửa
    đó — vì đây là hash của đầu vào, không phải nửa gốc). Cần ít nhất
    một nửa, không thì không có dữ liệu nào để chạy.
    """
    halves = [part for part in (bpic_hash, generator_hash) if part is not None]
    if not halves:
        raise ValueError("data_hash cần ít nhất một nửa: bpic_hash hoặc generator_hash")
    for part in halves:
        if not part:
            raise ValueError("nửa data_hash không được rỗng")
    joined = "".join(halves)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def reproducibility_gaps(
    record: RunRow,
    *,
    seed: int,
    model_id: str,
    model_revision: str,
    code_commit: str,
    config_hash: str,
    data_hash: str,
    cache_intact: bool,
) -> tuple[str, ...]:
    """Các điều kiện tái lập mà lần chạy `record` KHÔNG thỏa (rỗng = tái lập được).

    So từng điều kiện trong `REPRODUCIBILITY_CONDITIONS` với giá trị
    hiện tại: seed, model (id + revision), code_commit, config_hash,
    data_hash, cache còn nguyên. Thiếu một điều kiện là lần chạy ghi
    "không tái lập được" — không bao giờ lặng lẽ cho qua (spec, dòng 191).
    """
    gaps: list[str] = []
    if record.seed != seed:
        gaps.append("seed")
    if record.model_id != model_id or record.model_revision != model_revision:
        gaps.append("model")
    if record.code_commit != code_commit:
        gaps.append("code_commit")
    if record.config_hash != config_hash:
        gaps.append("config_hash")
    if record.data_hash != data_hash:
        gaps.append("data_hash")
    if not cache_intact:
        gaps.append("cache")
    return tuple(gaps)


def is_reproducible(
    record: RunRow,
    *,
    seed: int,
    model_id: str,
    model_revision: str,
    code_commit: str,
    config_hash: str,
    data_hash: str,
    cache_intact: bool,
) -> bool:
    """Lần chạy `record` có tái lập được với các giá trị hiện tại không."""
    return not reproducibility_gaps(
        record,
        seed=seed,
        model_id=model_id,
        model_revision=model_revision,
        code_commit=code_commit,
        config_hash=config_hash,
        data_hash=data_hash,
        cache_intact=cache_intact,
    )


def check_test_split_lock(*, config_hash: str, locked_config_hash: str | None) -> None:
    """Từ chối chạy trên phần đo khi cấu hình khác khóa (spec, dòng 152).

    `locked_config_hash` là hash đã khóa bằng commit trước khi chạm phần
    đo lần đầu; chưa khóa (`None`) thì cho chạy. Khác khóa thì raise
    trước khi bất kỳ vai nào chạy — không chạm phần đo bằng cấu hình lạ.
    """
    if locked_config_hash is None:
        return
    if config_hash != locked_config_hash:
        raise ValueError(
            "cấu hình đã đổi so với khóa phần đo "
            f"(config_hash {config_hash[:12]}... khác khóa "
            f"{locked_config_hash[:12]}...): không được chạy trên phần đo"
        )


@dataclass(frozen=True)
class ReflectorResult:
    """Kết quả một lần gọi Reflector: insight rút ra + token đã dùng.

    Reflector thật (task 6.2) chưa làm; coordinator nhận kết quả này
    qua vai tiêm vào (`ReflectorFn`) để vòng học chạy được bằng Reflector
    giả trong test và Reflector thật khi có, không đổi code nối vai.
    """

    insights: tuple[Insight, ...]
    tokens_in: int = 0
    tokens_out: int = 0


class ReflectorFn(Protocol):
    """Vai Reflector tiêm vào coordinator: trajectory + fact hiện có thành insight."""

    def __call__(
        self, trajectories: Sequence[Trajectory], facts: Sequence[FactRead]
    ) -> ReflectorResult:
        """Một lần gọi Reflector: nhận trajectory + fact, trả insight + token."""


class MeasuresFn(Protocol):
    """Hàm đếm số đo cho một candidate: người gọi đếm (không phải vai)."""

    def __call__(self, candidate: Candidate, delta: Delta) -> Measures:
        """Đếm số đo cho một candidate (Governor dùng để quyết)."""


@dataclass(frozen=True)
class LearningRound:
    """Đầu vào một vòng học: dữ liệu + sáu trường điều kiện tái lập.

    `valid_start` là đầu khoảng hiệu lực của fact mới (do coordinator
    truyền cho Curator — hàm thuần không tự lấy giờ); `retired_at` là
    thời điểm fact nghỉ khi đóng fact cũ; `wall_time` là thời gian
    tường của vòng (người gọi đo bằng đồng hồ, truyền vào). `locked_
    config_hash` + `on_test_split` là khóa phần đo (xem
    `check_test_split_lock`).

    Checkpoint (task 10.3, spec dòng 215): `checkpoint_every_n_cases`
    là số case mỗi lô (0 = không ghi checkpoint, chạy liền mạch một lô như
    cũ); `checkpoint_store` là nơi ghi checkpoint (None thì không ghi —
    `checkpoint_every_n_cases` > 0 mà không có store thì từ chối);
    `resume_from` là checkpoint để chạy tiếp (con trỏ case phải khớp đầu
    danh sách case, seed/config/data/model phải khớp — xem
    `_check_resume_matches`); `cache` là bộ nhớ đệm phản hồi mà checkpoint
    giữ hộ (khởi động lại thì nạp lại vào cache này trước khi chạy tiếp).

    Trần token (task 10.4, spec dòng 217): `token_budget_total` là trần
    token của vòng (`0` = không đặt trần); `token_budget_reserve_per_call`
    là dự trữ cho một lần gọi mô hình (mặc định 2048 = `ctx-size` của
    server); `reflector_batch_size` là số trajectory mỗi lô Reflector
    (bên gọi điền từ Settings — cần cho công thức dự trữ, xem Phụ lục
    A.1); `config_hash_no_budget` là hash cấu hình đã loại hai trường
    trần (bên gọi tính bằng `compute_config_hash_without_budget` — để
    ghi vào checkpoint cho cổng resume, xem Phụ lục A.3). Trần > 0 mà
    không ghi checkpoint thì vòng bị từ chối từ đầu (chạm trần thì phải
    có checkpoint để chạy tiếp).
    """

    tenant_id: str
    episode_rows: tuple[EpisodeRow, ...]
    facts: tuple[FactRead, ...]
    rule_table: RuleTable
    seed: int
    model_id: str
    model_revision: str
    code_commit: str
    config_hash: str
    data_hash: str
    valid_start: datetime
    retired_at: datetime
    wall_time: float = 0.0
    locked_config_hash: str | None = None
    on_test_split: bool = False
    checkpoint_every_n_cases: int = 0
    checkpoint_store: CheckpointStore | None = None
    resume_from: Checkpoint | None = None
    cache: ResponseCache | None = None
    token_budget_total: int = 0
    token_budget_reserve_per_call: int = 2048
    reflector_batch_size: int = 10
    config_hash_no_budget: str = ""


@dataclass(frozen=True)
class RoundOutcome:
    """Kết quả một vòng học: hàng để người gọi ghi xuống DB.

    `decisions` và `candidate_ids` song song theo thứ tự: `candidate_ids[i]`
    là id người gọi gán cho `decisions[i].candidate` khi ghi bảng
    `candidate`. `fact_rows`/`fact_closes` chỉ có cho candidate
    AUTO_APPROVE (ADD thêm hàng, RETIRE đóng fact cũ, CONTRADICT đóng cũ
    + thêm mới, CONFIRM không làm gì). `events` có một event cho mỗi lần
    gọi vai (generator, reflector, curator, governor) — `run_id` để None:
    người gọi ghi `run` trước, lấy id rồi điền vào event trước khi ghi
    (xem `repositories.events.insert_event`). `run_row` mang đủ sáu
    trường điều kiện tái lập + token vào ra, trạng thái `succeeded`.
    """

    trajectories: tuple[Trajectory, ...]
    insights: tuple[Insight, ...]
    decisions: tuple[GovernorResult, ...]
    candidate_ids: tuple[str, ...]
    fact_rows: tuple[FactRow, ...]
    fact_closes: tuple[FactClose, ...]
    events: tuple[EventRow, ...]
    run_row: RunRow


class BudgetExceededError(Exception):
    """Vòng học chạm trần token (task 10.4, spec dòng 217).

    Mang theo partial `RoundOutcome` (trạng thái tới hết lô đã xong,
    `run_row.status="budget_exceeded"`) để bên gọi ghi `run` + event rồi
    thoát mã 3 — không nuốt lỗi, không trả outcome thành công (L6).
    `checkpoint_key` là khóa checkpoint ở ranh giới lô đã xong (`None`
    nếu ghi checkpoint thất bại — xem R4: mất checkpoint thì bên gọi vẫn
    ghi được `run` `budget_exceeded`, chỉ không có điểm chạy tiếp).
    """

    def __init__(self, *, outcome: RoundOutcome, checkpoint_key: str | None) -> None:
        """Dựng lỗi từ partial outcome + khóa checkpoint (None nếu ghi lỗi)."""
        used = outcome.run_row.tokens_in + outcome.run_row.tokens_out
        checkpoint_note = (
            f"checkpoint {checkpoint_key}"
            if checkpoint_key is not None
            else "ghi checkpoint thất bại (không có điểm chạy tiếp)"
        )
        super().__init__(
            f"vượt trần token: đã dùng {used} token, run "
            f"{outcome.run_row.status}, {checkpoint_note}"
        )
        self.outcome = outcome
        self.checkpoint_key = checkpoint_key


class _BudgetExceededError(Exception):
    """Tín hiệu nội bộ: điểm kiểm trần trong `_run_chunk` vừa chạm trần.

    Chỉ mang `reserve` (dự trữ của lô chưa chạy) và `calls` (số lần gọi
    tối đa của lô) để `run_learning_round` ghi event + checkpoint rồi
    raise `BudgetExceededError` — `_run_chunk` không tự dựng outcome
    (trạng thái tích lũy nằm ở vòng ngoài).
    """

    def __init__(self, *, reserve: int, calls: int) -> None:
        """Dựng tín hiệu từ dự trữ và số lần gọi tối đa của lô chưa chạy."""
        super().__init__(f"vượt trần token: dự trữ lô {reserve} ({calls} lần gọi)")
        self.reserve = reserve
        self.calls = calls


def _budget_calls(trajectory_count: int, batch_size: int) -> int:
    """Số lần gọi mô hình tối đa cho chừng này trajectory.

    Reflector gọi đúng một lần mỗi lô `batch_size` trajectory (E5) nên
    đây là chặn trên đúng của số lần gọi trong lô; lô rỗng thì 0 lần gọi.
    """
    if trajectory_count <= 0:
        return 0
    return math.ceil(trajectory_count / batch_size)


def _check_token_budget(
    *,
    used: int,
    trajectory_count: int,
    token_budget_total: int,
    token_budget_reserve_per_call: int,
    reflector_batch_size: int,
) -> None:
    """Điểm kiểm trần (task 10.4, Phụ lục A.1): kiểm TRƯỚC khi gọi.

    Chỉ kiểm khi `token_budget_total > 0` (`0` = không đặt trần). Dự trữ
    cho lô = số lần gọi tối đa của lô nhân với dự trữ mỗi lần gọi; đã dùng cộng
    dự trữ mà vượt trần thì raise `_BudgetExceededError` — chưa phát ra lệnh
    gọi nào của lô. Chi phí thật mỗi lần gọi ≤ dự trữ theo H1 nên tổng
    token thật sau lô ≤ đã dùng + dự trữ ≤ trần.
    """
    if token_budget_total <= 0:
        return
    calls = _budget_calls(trajectory_count, reflector_batch_size)
    reserve = calls * token_budget_reserve_per_call
    if used + reserve > token_budget_total:
        raise _BudgetExceededError(reserve=reserve, calls=calls)


@dataclass(frozen=True)
class _ChunkResult:
    """Kết quả xử lý một lô case: các phần tích lũy của `RoundOutcome`."""

    trajectories: tuple[Trajectory, ...]
    insights: tuple[Insight, ...]
    decisions: tuple[GovernorResult, ...]
    candidate_ids: tuple[str, ...]
    fact_rows: tuple[FactRow, ...]
    fact_closes: tuple[FactClose, ...]
    events: tuple[EventRow, ...]
    tokens_in: int
    tokens_out: int


def _run_chunk(
    *,
    tenant_id: str,
    chunk_rows: list[EpisodeRow],
    facts: Sequence[FactRead],
    rule_table: RuleTable,
    valid_start: datetime,
    retired_at: datetime,
    reflect: ReflectorFn,
    measures_for: MeasuresFn,
    candidate_id_for: Callable[[], str],
    tokens_in: int = 0,
    tokens_out: int = 0,
    token_budget_total: int = 0,
    token_budget_reserve_per_call: int = 2048,
    reflector_batch_size: int = 10,
) -> _ChunkResult:
    """Xử lý một lô case: Generator replay → Reflector → Curator → Governor → Applier/Promoter.

    Đây là thân cũ của `run_learning_round`, tách ra để vòng học chia được
    thành nhiều lô (task 10.3): mỗi lô chạy đúng chuỗi sáu vai như một vòng
    đầy đủ, chỉ khác là chỉ nhận hàng episode của lô đó.

    Trần token (task 10.4): `tokens_in`/`tokens_out` là token đã dùng từ
    đầu vòng (gồm cả checkpoint resume); điểm kiểm đặt sau `replay`
    (chưa tốn token nào) và trước `reflect` (lần gọi mô hình đầu tiên
    của lô) — xem `_check_token_budget`. Lô rỗng thì không gọi mô hình
    (hành vi cũ giữ nguyên). Server không trả `usage` thì Reflector báo
    0 token cho lô đó (R2): lô đã gọi mô hình mà báo 0 token thì tính phí
    xấu nhất bằng dự trữ mỗi lần gọi thay vì 0 — một lần gọi thật không
    bao giờ tốn 0 token (prompt luôn có nội dung) nên 0 token chỉ có thể
    là thiếu `usage`. Cache ấm không đổi điểm kiểm: dự trữ vẫn tính như
    thể sẽ gọi (bảo thủ — dừng sớm hơn chứ không bao giờ vượt).
    """
    events: list[EventRow] = []
    trajectories = replay(tenant_id, list(chunk_rows))
    events.append(
        role_call_event(
            tenant_id=tenant_id,
            actor="generator",
            action="replay",
            payload_hash=payload_hash(chunk_rows),
        )
    )
    _check_token_budget(
        used=tokens_in + tokens_out,
        trajectory_count=len(trajectories),
        token_budget_total=token_budget_total,
        token_budget_reserve_per_call=token_budget_reserve_per_call,
        reflector_batch_size=reflector_batch_size,
    )
    reflector_result = reflect(trajectories, facts)
    chunk_tokens_in = reflector_result.tokens_in
    chunk_tokens_out = reflector_result.tokens_out
    if token_budget_total > 0 and trajectories and chunk_tokens_in + chunk_tokens_out == 0:
        # R2: server không trả usage nên Reflector báo 0 token cho lô đã
        # gọi mô hình — tính phí xấu nhất bằng dự trữ mỗi lần gọi.
        calls = _budget_calls(len(trajectories), reflector_batch_size)
        chunk_tokens_in = calls * token_budget_reserve_per_call
        chunk_tokens_out = 0
    events.append(
        role_call_event(
            tenant_id=tenant_id,
            actor="reflector",
            action="reflect",
            payload_hash=payload_hash(trajectories),
        )
    )
    decisions: list[GovernorResult] = []
    candidate_ids: list[str] = []
    fact_rows: list[FactRow] = []
    fact_closes: list[FactClose] = []
    for insight in reflector_result.insights:
        deltas = curate(insight, list(facts))
        events.append(
            role_call_event(
                tenant_id=tenant_id,
                actor="curator",
                action="curate",
                payload_hash=payload_hash(insight),
            )
        )
        for delta in deltas:
            candidate = to_candidate(delta, valid_start=valid_start)
            measures = measures_for(candidate, delta)
            result = decide(candidate, rule_table, measures)
            decisions.append(result)
            candidate_id = candidate_id_for()
            candidate_ids.append(candidate_id)
            events.append(
                governor_decision_event(
                    result,
                    tenant_id=tenant_id,
                    run_id=None,
                    candidate_id=candidate_id,
                )
            )
            if result.decision.verdict is not DecisionVerdict.AUTO_APPROVE:
                continue
            approved = result.candidate.model_copy(update={"status": "approved"})
            kind = FactPayload.model_validate(approved.payload).kind
            if kind in (DeltaKind.RETIRE.value, DeltaKind.CONTRADICT.value):
                fact_closes.append(build_fact_close(approved, retired_at=retired_at))
            if kind in (DeltaKind.ADD.value, DeltaKind.CONTRADICT.value):
                if approved.target_scope == "tenant":
                    fact_rows.append(
                        apply_candidate(
                            approved,
                            candidate_id=candidate_id,
                            tenant_id=tenant_id,
                        )
                    )
                elif approved.target_scope == "global":
                    fact_rows.append(promote_candidate(approved, candidate_id=candidate_id))
            # CONFIRM: fact đã có sẵn — không thêm hàng, không đóng fact.
    return _ChunkResult(
        trajectories=tuple(trajectories),
        insights=tuple(reflector_result.insights),
        decisions=tuple(decisions),
        candidate_ids=tuple(candidate_ids),
        fact_rows=tuple(fact_rows),
        fact_closes=tuple(fact_closes),
        events=tuple(events),
        tokens_in=chunk_tokens_in,
        tokens_out=chunk_tokens_out,
    )


def _case_order(rows: Sequence[EpisodeRow]) -> list[str]:
    """Thứ tự case xuất hiện lần đầu trong các hàng episode."""
    order: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row.case_id not in seen:
            seen.add(row.case_id)
            order.append(row.case_id)
    return order


def _check_resume_matches(
    round: LearningRound, checkpoint: Checkpoint, case_order: list[str]
) -> None:
    """Từ chối chạy tiếp khi checkpoint không thuộc về vòng này.

    Kiểm tenant, seed, model, config_hash, data_hash và con trỏ case:
    con trỏ phải là đúng đầu danh sách case của vòng (thứ tự case đã đổi
    thì ranh giới lô đổi theo, chạy tiếp sẽ xử lý sai case). Khác một giá
    trị là raise — không chạy tiếp từ checkpoint lạ, không đoán.

    Trần token (task 10.4, Phụ lục A.3): checkpoint có
    `config_hash_no_budget` thì so hash-trừ-trần thay vì hash toàn phần,
    và trần mới (đổi hay giữ nguyên) phải `== 0` hoặc `>` token đã dùng
    mang theo — trần mới ≤ đã dùng thì từ chối ngay; checkpoint cũ thiếu
    hash-trừ-trần thì dùng luật nghiêm ngặt cũ (hash toàn phần phải khớp).
    """
    mismatches: list[str] = []
    if checkpoint.tenant_id != round.tenant_id:
        mismatches.append("tenant_id")
    if checkpoint.seed != round.seed:
        mismatches.append("seed")
    if (
        checkpoint.model_id != round.model_id
        or checkpoint.model_revision != round.model_revision
    ):
        mismatches.append("model")
    if checkpoint.config_hash_no_budget:
        # Checkpoint viết từ 10.4 trở đi: so hash-trừ-trần (chứng minh
        # "chỉ khác trần") thay vì hash toàn phần. Trần mới (đổi hay giữ
        # nguyên) phải == 0 (tắt) hoặc > số token đã dùng mang theo —
        # trần mới ≤ đã dùng thì từ chối ngay, không chạy rồi mới chạm
        # trần lần nữa (Phụ lục A.3); dự trữ mới đổi tự do (chỉ ảnh
        # hưởng lần kiểm sau).
        if checkpoint.config_hash_no_budget != round.config_hash_no_budget:
            mismatches.append("config_hash_no_budget")
        else:
            used = checkpoint.tokens_in + checkpoint.tokens_out
            if round.token_budget_total != 0 and round.token_budget_total <= used:
                mismatches.append("token_budget_total")
    elif checkpoint.config_hash != round.config_hash:
        # Checkpoint viết trước 10.4 (thiếu hash-trừ-trần): luật nghiêm
        # ngặt cũ — hash toàn phần phải khớp, không cho khác trần.
        mismatches.append("config_hash")
    if checkpoint.data_hash != round.data_hash:
        mismatches.append("data_hash")
    if mismatches:
        raise ValueError(
            "checkpoint không thuộc về vòng này (khác: "
            + ", ".join(mismatches)
            + "): không chạy tiếp từ checkpoint lạ"
        )
    done = list(checkpoint.cases_done)
    if done != case_order[: len(done)]:
        raise ValueError(
            "con trỏ case của checkpoint không khớp đầu danh sách case của vòng "
            f"({done} khác {case_order[: len(done)]}): thứ tự case đã đổi, "
            "không chạy tiếp được"
        )


def run_learning_round(
    round: LearningRound,
    *,
    reflect: ReflectorFn,
    measures_for: MeasuresFn,
    candidate_id_for: Callable[[], str],
) -> RoundOutcome:
    """Chạy một vòng học: nối sáu vai, trả hàng để ghi `run` + event + fact.

    Thứ tự: khóa phần đo (từ chối trước khi vai nào chạy) → Generator
    replay → Reflector (tiêm vào) → mỗi insight: Curator → Governor →
    nếu AUTO_APPROVE thì Applier (scope tenant) hoặc Promoter (scope
    global) xây hàng fact. Candidate AUTO_APPROVE được ghi
    `status="approved"` trước khi áp — Governor chỉ ra verdict, không
    tự đổi trạng thái candidate (xem chuỗi Curator→Governor→Applier).

    `target_scope` ở đây chỉ có thể là `'tenant'`/`'global'`:
    `to_candidate` đã ánh xạ mọi scope Insight về hai giá trị này,
    Governor và `model_copy` không đổi `target_scope` — nên nhánh
    `else` fail-fast cũ (raise khi scope lạ) đã bị xóa vì không còn
    giá trị nào tới được nó. Đường mới tạo Candidate phải giữ bất
    biến này (xem `human_decision_to_candidate`, đã chặn scope lạ).

    Checkpoint (task 10.3, spec dòng 215): khi `checkpoint_every_n_cases`
    > 0 thì episode chia thành lô N case; sau mỗi lô ghi một checkpoint
    (fact, candidate đang chờ, con trỏ case, bộ nhớ đệm) vào
    `checkpoint_store`. Lô đang chạy mà hỏng thì công việc của lô đó bỏ
    hết — checkpoint chỉ ghi ở ranh giới lô, nên chạy tiếp từ checkpoint
    mới nhất là chạy lại đúng lô dở đó, không quyết lại candidate đã
    quyết. `resume_from` cho sẵn thì bỏ qua các case đã xong, nạp lại
    trạng thái tích lũy + bộ nhớ đệm rồi chạy tiếp các case còn lại.

    Trần token (task 10.4, spec dòng 217): khi `token_budget_total` > 0
    thì mỗi lô kiểm trần sau `replay`, trước `reflect` (xem
    `_check_token_budget`); chạm trần thì ghi checkpoint ở ranh giới lô
    đã xong, thêm event `budget_exceeded`, dựng `RunRow`
    `status="budget_exceeded"` rồi raise `BudgetExceededError` mang
    partial outcome để bên gọi ghi `run` và thoát mã 3. Trần > 0 mà
    không ghi checkpoint thì vòng bị từ chối từ đầu (validation).
    """
    if round.on_test_split:
        check_test_split_lock(
            config_hash=round.config_hash,
            locked_config_hash=round.locked_config_hash,
        )
    if round.checkpoint_every_n_cases < 0:
        raise ValueError("checkpoint_every_n_cases không được âm")
    store = round.checkpoint_store
    checkpointing = round.checkpoint_every_n_cases > 0
    if checkpointing and store is None:
        raise ValueError(
            "checkpoint_every_n_cases > 0 mà không có checkpoint_store: "
            "không biết ghi checkpoint vào đâu"
        )
    if round.token_budget_total < 0:
        raise ValueError("token_budget_total không được âm")
    if round.token_budget_reserve_per_call < 0:
        raise ValueError("token_budget_reserve_per_call không được âm")
    if round.token_budget_total > 0:
        if round.token_budget_reserve_per_call < 1:
            raise ValueError(
                "token_budget_total > 0 mà token_budget_reserve_per_call < 1: "
                "dự trữ phải ít nhất 1 token cho một lần gọi"
            )
        if round.reflector_batch_size < 1:
            raise ValueError(
                "token_budget_total > 0 mà reflector_batch_size < 1: "
                "không tính được số lần gọi tối đa của lô"
            )
        if not checkpointing or store is None:
            raise ValueError(
                "token_budget_total > 0 mà checkpoint_every_n_cases == 0 hoặc "
                "không có checkpoint_store: chạm trần thì phải ghi checkpoint "
                "để chạy tiếp"
            )
    case_order = _case_order(round.episode_rows)
    trajectories: list[Trajectory] = []
    insights: list[Insight] = []
    decisions: list[GovernorResult] = []
    candidate_ids: list[str] = []
    fact_rows: list[FactRow] = []
    fact_closes: list[FactClose] = []
    events: list[EventRow] = []
    tokens_in = 0
    tokens_out = 0

    def snapshot() -> Checkpoint:
        """Checkpoint ở ranh giới lô đã xong: trạng thái tích lũy hiện tại.

        Dùng chung cho checkpoint sau mỗi lô (10.3) và checkpoint ở điểm
        chạm trần (10.4) — cùng một hình dạng, tránh nhân đôi khối dựng
        Checkpoint. Không gồm event `budget_exceeded` (event đó chỉ nằm
        trong outcome, không nằm trong checkpoint — xem nhánh chạm trần).
        """
        return Checkpoint(
            tenant_id=round.tenant_id,
            seed=round.seed,
            model_id=round.model_id,
            model_revision=round.model_revision,
            config_hash=round.config_hash,
            data_hash=round.data_hash,
            cases_done=tuple(done),
            trajectories=tuple(trajectories),
            insights=tuple(insights),
            decisions=tuple(decisions),
            candidate_ids=tuple(candidate_ids),
            fact_rows=tuple(fact_rows),
            fact_closes=tuple(fact_closes),
            events=tuple(events),
            cache_entries=(round.cache.export() if round.cache is not None else {}),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            token_budget_total=round.token_budget_total,
            token_budget_reserve_per_call=round.token_budget_reserve_per_call,
            config_hash_no_budget=round.config_hash_no_budget,
        )

    def build_run_row(status: str) -> RunRow:
        """Hàng `run` với trạng thái tích lũy hiện tại (`succeeded`/`budget_exceeded`)."""
        return RunRow(
            tenant_id=round.tenant_id,
            seed=round.seed,
            model_id=round.model_id,
            model_revision=round.model_revision,
            code_commit=round.code_commit,
            config_hash=round.config_hash,
            data_hash=round.data_hash,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            wall_time=round.wall_time,
            status=status,
        )

    def build_outcome(run_row: RunRow) -> RoundOutcome:
        """Outcome từ trạng thái tích lũy hiện tại + hàng `run` đã dựng."""
        return RoundOutcome(
            trajectories=tuple(trajectories),
            insights=tuple(insights),
            decisions=tuple(decisions),
            candidate_ids=tuple(candidate_ids),
            fact_rows=tuple(fact_rows),
            fact_closes=tuple(fact_closes),
            events=tuple(events),
            run_row=run_row,
        )

    if round.resume_from is not None:
        checkpoint = round.resume_from
        _check_resume_matches(round, checkpoint, case_order)
        done = list(checkpoint.cases_done)
        trajectories = list(checkpoint.trajectories)
        insights = list(checkpoint.insights)
        decisions = list(checkpoint.decisions)
        candidate_ids = list(checkpoint.candidate_ids)
        fact_rows = list(checkpoint.fact_rows)
        fact_closes = list(checkpoint.fact_closes)
        events = list(checkpoint.events)
        tokens_in = checkpoint.tokens_in
        tokens_out = checkpoint.tokens_out
        if round.cache is not None:
            round.cache.import_entries(checkpoint.cache_entries)
    else:
        done = []
    remaining = case_order[len(done) :]
    if remaining:
        chunk_size = round.checkpoint_every_n_cases if checkpointing else len(remaining)
        prefix = checkpoint_prefix(
            tenant_id=round.tenant_id,
            seed=round.seed,
            config_hash=round.config_hash,
            data_hash=round.data_hash,
        )
        for start in range(0, len(remaining), chunk_size):
            chunk_cases = remaining[start : start + chunk_size]
            chunk_set = set(chunk_cases)
            chunk_rows = [row for row in round.episode_rows if row.case_id in chunk_set]
            try:
                chunk = _run_chunk(
                    tenant_id=round.tenant_id,
                    chunk_rows=chunk_rows,
                    facts=round.facts,
                    rule_table=round.rule_table,
                    valid_start=round.valid_start,
                    retired_at=round.retired_at,
                    reflect=reflect,
                    measures_for=measures_for,
                    candidate_id_for=candidate_id_for,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    token_budget_total=round.token_budget_total,
                    token_budget_reserve_per_call=round.token_budget_reserve_per_call,
                    reflector_batch_size=round.reflector_batch_size,
                )
            except _BudgetExceededError as exc:
                # Nhánh chạm trần (task 10.4, Phụ lục A.2): lô này chưa chạy
                # nên không có việc dở — checkpoint ở ranh giới lô đã xong,
                # event `budget_exceeded`, RunRow `budget_exceeded`, raise
                # mang partial outcome. Ghi checkpoint lỗi thì vẫn raise
                # với partial outcome trong bộ nhớ (R4); mất checkpoint
                # được ghi rõ trong reason của event.
                try:
                    assert store is not None  # validation đã từ chối trần không store
                    checkpoint_key: str | None = write_checkpoint(store, snapshot(), prefix)
                except Exception:
                    checkpoint_key = None
                used = tokens_in + tokens_out
                reason = (
                    f"vượt trần token: trần {round.token_budget_total}, đã dùng "
                    f"{used} (in {tokens_in}, out {tokens_out}), dự trữ lô "
                    f"{exc.reserve} ({exc.calls} lần gọi), con trỏ "
                    f"{len(done)} case đã xong"
                )
                if checkpoint_key is not None:
                    reason += f", checkpoint {checkpoint_key}"
                else:
                    reason += "; ghi checkpoint thất bại (không có điểm chạy tiếp)"
                events.append(
                    role_call_event(
                        tenant_id=round.tenant_id,
                        actor="coordinator",
                        action="budget_exceeded",
                        payload_hash=payload_hash(
                            {
                                "token_budget_total": round.token_budget_total,
                                "tokens_used": used,
                                "reserve": exc.reserve,
                                "cases_done": list(done),
                            }
                        ),
                        reason=reason,
                    )
                )
                raise BudgetExceededError(
                    outcome=build_outcome(build_run_row("budget_exceeded")),
                    checkpoint_key=checkpoint_key,
                ) from exc
            trajectories.extend(chunk.trajectories)
            insights.extend(chunk.insights)
            decisions.extend(chunk.decisions)
            candidate_ids.extend(chunk.candidate_ids)
            fact_rows.extend(chunk.fact_rows)
            fact_closes.extend(chunk.fact_closes)
            events.extend(chunk.events)
            tokens_in += chunk.tokens_in
            tokens_out += chunk.tokens_out
            done.extend(chunk_cases)
            if checkpointing:
                assert store is not None  # đã từ chối ở đầu hàm
                write_checkpoint(store, snapshot(), prefix)
    return build_outcome(build_run_row("succeeded"))
