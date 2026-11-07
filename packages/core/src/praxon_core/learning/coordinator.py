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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel

from praxon_core.learning.applier import (
    apply_candidate,
    build_fact_close,
    promote_candidate,
)
from praxon_core.learning.candidate import Candidate, DecisionVerdict, GovernorResult
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


def compute_config_hash(settings: Settings) -> str:
    """Băm cấu hình chạy thành `config_hash` (một trong sáu trường của `run`).

    Băm toàn bộ cấu hình TRỪ `database_url` và `openai_api_key`: đổi DB
    hay xoay khóa không đổi kết quả nên không được đổi hash; khóa thì
    không bao giờ được đưa vào hash. Mọi trường còn lại đổi là hash đổi
    — thận trọng: đổi cấu hình thì lần chạy cũ không còn tái lập được.
    """
    data = settings.model_dump(mode="json")
    data.pop("database_url", None)
    data.pop("openai_api_key", None)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
    """
    if round.on_test_split:
        check_test_split_lock(
            config_hash=round.config_hash,
            locked_config_hash=round.locked_config_hash,
        )
    events: list[EventRow] = []
    trajectories = replay(round.tenant_id, list(round.episode_rows))
    events.append(
        role_call_event(
            tenant_id=round.tenant_id,
            actor="generator",
            action="replay",
            payload_hash=payload_hash(round.episode_rows),
        )
    )
    reflector_result = reflect(trajectories, round.facts)
    events.append(
        role_call_event(
            tenant_id=round.tenant_id,
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
        deltas = curate(insight, list(round.facts))
        events.append(
            role_call_event(
                tenant_id=round.tenant_id,
                actor="curator",
                action="curate",
                payload_hash=payload_hash(insight),
            )
        )
        for delta in deltas:
            candidate = to_candidate(delta, valid_start=round.valid_start)
            measures = measures_for(candidate, delta)
            result = decide(candidate, round.rule_table, measures)
            decisions.append(result)
            candidate_id = candidate_id_for()
            candidate_ids.append(candidate_id)
            events.append(
                governor_decision_event(
                    result,
                    tenant_id=round.tenant_id,
                    run_id=None,
                    candidate_id=candidate_id,
                )
            )
            if result.decision.verdict is not DecisionVerdict.AUTO_APPROVE:
                continue
            approved = result.candidate.model_copy(update={"status": "approved"})
            kind = FactPayload.model_validate(approved.payload).kind
            if kind in (DeltaKind.RETIRE.value, DeltaKind.CONTRADICT.value):
                fact_closes.append(build_fact_close(approved, retired_at=round.retired_at))
            if kind in (DeltaKind.ADD.value, DeltaKind.CONTRADICT.value):
                if approved.target_scope == "tenant":
                    fact_rows.append(
                        apply_candidate(
                            approved,
                            candidate_id=candidate_id,
                            tenant_id=round.tenant_id,
                        )
                    )
                elif approved.target_scope == "global":
                    fact_rows.append(promote_candidate(approved, candidate_id=candidate_id))
            # CONFIRM: fact đã có sẵn — không thêm hàng, không đóng fact.
    run_row = RunRow(
        tenant_id=round.tenant_id,
        seed=round.seed,
        model_id=round.model_id,
        model_revision=round.model_revision,
        code_commit=round.code_commit,
        config_hash=round.config_hash,
        data_hash=round.data_hash,
        tokens_in=reflector_result.tokens_in,
        tokens_out=reflector_result.tokens_out,
        wall_time=round.wall_time,
        status="succeeded",
    )
    return RoundOutcome(
        trajectories=tuple(trajectories),
        insights=tuple(reflector_result.insights),
        decisions=tuple(decisions),
        candidate_ids=tuple(candidate_ids),
        fact_rows=tuple(fact_rows),
        fact_closes=tuple(fact_closes),
        events=tuple(events),
        run_row=run_row,
    )
