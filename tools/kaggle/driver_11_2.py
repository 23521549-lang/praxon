"""Driver chạy bảy điều kiện thí nghiệm trên Kaggle (plan con 11, task 11.2).

Một lệnh chạy 50 vòng học (5 điều kiện có mô hình x 5 tenant x 2 nguồn)
qua `run_learning_round`, ghi `run` + event + candidate + fact vào DB,
ghi mục bản đồ vòng→điều kiện, in bốn chỉ số kèm khoảng tin cậy cho mỗi
vòng. Hai điều kiện trong bộ nhớ (Chỉ Declare, Cách ly) đo trực tiếp
không mô hình, không hàng `run` (mục bản đồ ghi `run_id = null`).

Hình dạng CLI mượn `wabo_rules.main` (`--config`, `--seed`, `--condition`,
`--source`, `--limit` cho vòng thử; mã thoát 0/1/2 + 3 khi chạm trần) và
THÊM ghi DB. Trần token là tham số theo phương pháp A.4 của đề xuất
(số lần gọi tối đa x chi phí/lần gọi lớn nhất đã đo x 1,5; vòng thử P0
dùng cận trên an toàn số lần gọi x 2.048) — không có con số trần nào
hard-code trong code. Engine/model là tham số (`--backend`, model theo
Settings) do verdict 11.1 quyết, không hard-code trong driver.

Đường ghi DB (mỗi vai một giao dịch — DB không cho một giao dịch chung
qua nhiều vai, xem ghi chú `write_round_to_db`): coordinator ghi `run` +
event; curator ghi candidate rồi governor duyệt; applier (tenant) /
promoter (global) ghi fact. Fact trùng khóa với fact đã có từ vòng trước
thì đóng cũ rồi mới thêm mới trong cùng giao dịch (giao thức BĐ5).

Luật Wabo cho điều kiện 7 là đầu vào (`--wabo-rules`, tệp JSON do 9.1
sinh ra sau khi đo xong); thiếu tệp thì từ chối (mã 1), tệp rỗng thì
phần tài liệu rỗng và ghi rõ (cùng luật trung thực như 10.2).
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urlparse, urlunparse

import psycopg
from psycopg import Connection

from praxon_core.adapters.cache import ResponseCache
from praxon_core.adapters.language_model import ModelCallError, model_from_settings
from praxon_core.adapters.local_store import LocalCheckpointStore
from praxon_core.adapters.s3_store import S3CheckpointStore
from praxon_core.datasets.bpic2015 import (
    BPIC2015_DATASETS,
    DEFAULT_CACHE_DIR,
    BPIC2015Dataset,
)
from praxon_core.datasets.split import (
    LogSplit,
    SplitFractions,
    split_log,
)
from praxon_core.datasets.split import (
    compute_data_hash as compute_bpic_data_hash,
)
from praxon_core.datasets.xes import Trace as XesTrace
from praxon_core.datasets.xes import iter_traces
from praxon_core.declare.index import Trace
from praxon_core.declare.miner import Rule, discover
from praxon_core.eval.experiments import (
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
    GroundTruth,
    facts_from_rules,
    ground_truth_from_generator,
)
from praxon_core.eval.metrics import Fact, FactScope, f1_score
from praxon_core.eval.report import (
    SYNTHETIC_N_CASES,
    SYNTHETIC_SEED,
    SYNTHETIC_TENANT_COUNT,
    MetricCI,
    MetricsWithCI,
    metrics_with_ci,
    split_generated_traces,
)
from praxon_core.learning.beta import (
    Prior,
    posterior_prob_ge,
    prior_prob_ge,
    wilson_lower,
)
from praxon_core.learning.calibration import (
    FLAT_PRIOR_CONFIDENCE,
    count_rule_evidence,
)
from praxon_core.learning.candidate import (
    Candidate,
    DecisionVerdict,
    FactStatus,
)
from praxon_core.learning.checkpoint import CheckpointStore
from praxon_core.learning.coordinator import (
    BudgetExceededError,
    LearningRound,
    MeasuresFn,
    RoundOutcome,
    compute_config_hash,
    compute_config_hash_without_budget,
    merge_data_hash,
    run_learning_round,
)
from praxon_core.learning.curator import (
    Delta,
    DeltaKind,
    FactRead,
    InsightSource,
)
from praxon_core.learning.generator import EpisodeRow
from praxon_core.learning.measures import Measures
from praxon_core.learning.reflector import Reflector, ReflectorBatchError
from praxon_core.learning.rules import Policy, default_rule_table
from praxon_core.repositories.events import insert_event
from praxon_core.repositories.facts import (
    FactClose,
    FactRow,
    close_fact,
    insert_fact,
)
from praxon_core.repositories.runs import RunRow, insert_run
from praxon_core.settings import Settings, load_settings
from praxon_core.synthetic.generator import (
    BASE_ORDER,
    GeneratorParams,
    generate,
    swap_adjacent,
)
from praxon_core.synthetic.generator import (
    compute_data_hash as compute_generator_data_hash,
)

SYNTHETIC_SOURCE = "synthetic"
"""Nguồn bộ chuẩn bán tổng hợp."""

BPIC_SOURCE = "bpic2015"
"""Nguồn BPIC 2015 thật (năm đô thị)."""

SOURCES: tuple[str, ...] = (SYNTHETIC_SOURCE, BPIC_SOURCE)
"""Hai nguồn dữ liệu, theo thứ tự chạy (bộ chuẩn trước, BPIC sau)."""

MODEL_CONDITIONS: tuple[str, ...] = (POOLED, VOTING, CONSENSUS, VETO, DOCUMENT)
"""Năm điều kiện có mô hình — mỗi điều kiện một vòng học mỗi tenant mỗi nguồn."""

IN_MEMORY_CONDITIONS: tuple[str, ...] = (DECLARE_ONLY, ISOLATION)
"""Hai điều kiện đo trong bộ nhớ — không mô hình, không vòng học, không hàng `run`."""

ALL_CONDITIONS: tuple[str, ...] = (
    DECLARE_ONLY,
    ISOLATION,
    POOLED,
    VOTING,
    CONSENSUS,
    VETO,
    DOCUMENT,
)
"""Bảy điều kiện theo đúng thứ tự spec (dòng 154-165)."""

SYNTHETIC_ORIGIN = datetime(2026, 1, 1, tzinfo=UTC)
"""Ngày gốc cố định cho trace sinh (trace sinh không có ngày thật).

Mọi `EpisodeRow` của bộ chuẩn lấy thời điểm từ ngày này cộng độ dời xác
định theo (case, sự kiện); `valid_start` của vòng bộ chuẩn cũng là ngày
này. Ghi vào bản đồ để lần chạy kiểm chứng được.
"""

BPIC_CALIBRATION_SOURCE = "bpic2015-calibration-split"
"""Nguồn gốc đáp án BPIC 2015 cho 11.2: khám phá trên phần hiệu chỉnh.

Không dùng `ground_truth_from_test_traces` (hàm đó chỉ nhận trace phần
đo và đóng dấu `bpic2015-test-split`); đáp án 11.2 khám phá trên phần
hiệu chỉnh nên driver tự xây `GroundTruth` với nguồn gốc này.
"""

SAFE_MAX_COST_PER_CALL = 2048
"""Cận trên an toàn cho chi phí một lần gọi Reflector (token).

Bằng `token_budget_reserve_per_call` mặc định (= `ctx-size` của server):
một lần gọi không bao giờ tốn hơn ctx-size token. Vòng thử P0 dùng cận
này khi chưa có số đo thật (xem A.4 của đề xuất).
"""

CEILING_SAFETY_FACTOR = 1.5
"""Hệ số an toàn cho công thức trần (A.4): biên cho prompt dài ngắn khác
nhau theo tenant, lần gọi thử lại và cache miss nhiều hơn dự kiến."""

CEILING_USED_WARNING_RATIO = 0.7
"""Ngưỡng cảnh báo: vòng thử P0 phải xong với đã dùng ≤ 70% trần.

Vượt ngưỡng thì xem lại hệ số trần trước khi chạy tiếp (A.4) — driver
in cảnh báo, không tự chặn (quyết định chạy tiếp là của người chạy).
"""

DEFAULT_MANIFEST_NAME = "11.2-manifest.json"
"""Tên mặc định của tệp bản đồ vòng→điều kiện (ghi ở thư mục làm việc)."""


@dataclass(frozen=True)
class TenantRoundData:
    """Dữ liệu một tenant cho một nguồn — đủ để chạy các vòng của nó.

    `tenant_data` mang phần học / phần đo / đáp án / luật tự học cho
    `condition_fact_sets` và cho đo bốn chỉ số. `episode_rows` là hàng
    episode của phần học (một hàng mỗi sự kiện) để `run_learning_round`
    phát lại. `data_hash` là `data_hash` của vòng (đã gộp qua
    `merge_data_hash`: nửa BPIC chung cho BPIC, nửa bộ sinh theo tenant
    cho bộ chuẩn). `origin_date` chỉ có với bộ chuẩn (ngày gốc cố định).
    """

    tenant_id: str
    source: str
    tenant_data: TenantData
    episode_rows: tuple[EpisodeRow, ...]
    valid_start: datetime
    data_hash: str
    origin_date: datetime | None = None


def _episode_rows_for_xes_trace(
    tenant_id: str, trace: XesTrace, fallback_start: datetime | None
) -> list[EpisodeRow]:
    """Một trace XES thành hàng episode (một hàng mỗi sự kiện).

    `occurred_at`/`ingested_at` lấy thời điểm sự kiện; thiếu thì lấy
    start của case, thiếu nữa thì lấy ranh giới học; vẫn thiếu thì từ
    chối (dữ liệu sai hình dạng phải lộ ra, không tự bịa thời điểm).
    """
    rows: list[EpisodeRow] = []
    for event in trace.events:
        occurred = event.timestamp or trace.start or fallback_start
        if occurred is None:
            raise ValueError(
                f"case {trace.case_id}: sự kiện {event.activity!r} không có "
                "thời điểm và case cũng không có start"
            )
        rows.append(
            EpisodeRow(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                case_id=trace.case_id,
                payload={"activity": event.activity},
                occurred_at=occurred,
                ingested_at=occurred,
            )
        )
    return rows


def _episode_rows_for_synthetic(
    tenant_id: str, train_traces: Sequence[Trace]
) -> list[EpisodeRow]:
    """Trace sinh thành hàng episode: case id + thời điểm xác định từ seed.

    Trace sinh không có ngày thật nên thời điểm lấy từ ngày gốc cố định
    cộng độ dời theo (case, sự kiện) — cùng seed ra cùng thời điểm, thứ
    tự sự kiện trong case giữ nguyên sau khi phát lại xếp theo thời gian.
    """
    rows: list[EpisodeRow] = []
    for case_index, trace in enumerate(train_traces):
        case_id = f"{tenant_id}-case-{case_index:04d}"
        for event_index, activity in enumerate(trace.events):
            occurred = SYNTHETIC_ORIGIN + timedelta(minutes=case_index * 100 + event_index)
            rows.append(
                EpisodeRow(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    case_id=case_id,
                    payload={"activity": activity},
                    occurred_at=occurred,
                    ingested_at=occurred,
                )
            )
    return rows


def load_synthetic_round_data(
    *, seed: int = SYNTHETIC_SEED, n_cases: int = SYNTHETIC_N_CASES
) -> list[TenantRoundData]:
    """Năm tenant giả: mỗi tenant một thứ tự riêng (đáp án khác nhau).

    Học 180, đo 60 (20% cuối qua `split_generated_traces`; 60 case giữa
    là phần hiệu chỉnh, 11.2 không dùng). Đáp án là luật đã cài vào bộ
    sinh (tuyệt đối). `data_hash` mỗi tenant gộp từ nửa bộ sinh của nó.
    """
    results: list[TenantRoundData] = []
    for index in range(SYNTHETIC_TENANT_COUNT):
        tenant_id = f"synthetic-{index + 1}"
        params = GeneratorParams(
            seed=seed, n_cases=n_cases, order=swap_adjacent(BASE_ORDER, index)
        )
        log = generate(tenant_id=tenant_id, params=params)
        train, measure = split_generated_traces(log.traces)
        tenant_data = TenantData(
            tenant_id=tenant_id,
            train_traces=train,
            measure_traces=measure,
            ground_truth=ground_truth_from_generator(log),
            own_rules=discover(
                train,
                support=GROUND_TRUTH_SUPPORT,
                confidence=GROUND_TRUTH_CONFIDENCE,
            ),
        )
        results.append(
            TenantRoundData(
                tenant_id=tenant_id,
                source=SYNTHETIC_SOURCE,
                tenant_data=tenant_data,
                episode_rows=tuple(_episode_rows_for_synthetic(tenant_id, train)),
                valid_start=SYNTHETIC_ORIGIN,
                data_hash=merge_data_hash(
                    generator_hash=compute_generator_data_hash(
                        tenant_id=tenant_id, params=params
                    )
                ),
                origin_date=SYNTHETIC_ORIGIN,
            )
        )
    return results


def load_bpic_round_data(*, cache_dir: Path) -> list[TenantRoundData]:
    """Năm đô thị BPIC 2015: học / hiệu chỉnh / đo theo lệnh chia 60/20/20.

    Vòng học học trên phần HỌC; đo bốn chỉ số trên phần HIỆU CHỈNH
    (đáp án khám phá trên trace hiệu chỉnh, ngưỡng 0,5/0,5 cố định).
    Phần ĐO không đọc, không chạy, không ghi — chỉ dùng ở 12.2 sau khóa.
    `data_hash` chung cả năm đô thị (băm của lệnh chia) gộp qua
    `merge_data_hash`, giống nhau cho cả năm vòng BPIC của một lần chạy.
    """
    splits: list[tuple[BPIC2015Dataset, LogSplit]] = []
    file_hashes: list[str] = []
    for dataset in BPIC2015_DATASETS:
        path = cache_dir / dataset.xes_filename
        if not path.is_file():
            raise FileNotFoundError(f"thiếu tệp log BPIC 2015: {path}")
        split = split_log(path, dataset.municipality)
        splits.append((dataset, split))
        file_hashes.append(split.file_sha256)
    shared_bpic_hash = compute_bpic_data_hash(
        log_hashes=tuple(file_hashes),
        fractions=SplitFractions(),
        tenants=tuple(dataset.municipality for dataset, _ in splits),
    )
    run_data_hash = merge_data_hash(bpic_hash=shared_bpic_hash)
    results: list[TenantRoundData] = []
    for dataset, split in splits:
        path = cache_dir / dataset.xes_filename
        train_ids = frozenset(split.train)
        calibration_ids = frozenset(split.calibration)
        train_traces: list[Trace] = []
        calibration_traces: list[Trace] = []
        episode_rows: list[EpisodeRow] = []
        for xes_trace in iter_traces(path):
            declare_trace = Trace(tuple(event.activity for event in xes_trace.events))
            if xes_trace.case_id in train_ids:
                train_traces.append(declare_trace)
                episode_rows.extend(
                    _episode_rows_for_xes_trace(dataset.slug, xes_trace, split.train_max_start)
                )
            elif xes_trace.case_id in calibration_ids:
                calibration_traces.append(declare_trace)
        calibration_rules = discover(
            calibration_traces,
            support=GROUND_TRUTH_SUPPORT,
            confidence=GROUND_TRUTH_CONFIDENCE,
        )
        ground_truth = GroundTruth(
            tenant_id=dataset.slug,
            reference=frozenset(rule.canonical_key for rule in calibration_rules),
            source=BPIC_CALIBRATION_SOURCE,
            support=GROUND_TRUTH_SUPPORT,
            confidence=GROUND_TRUTH_CONFIDENCE,
        )
        tenant_data = TenantData(
            tenant_id=dataset.slug,
            train_traces=tuple(train_traces),
            measure_traces=tuple(calibration_traces),
            ground_truth=ground_truth,
            own_rules=discover(
                train_traces,
                support=GROUND_TRUTH_SUPPORT,
                confidence=GROUND_TRUTH_CONFIDENCE,
            ),
        )
        if split.train_max_start is None:
            raise ValueError(f"đô thị {dataset.slug}: phần học không có ranh giới thời gian")
        results.append(
            TenantRoundData(
                tenant_id=dataset.slug,
                source=BPIC_SOURCE,
                tenant_data=tenant_data,
                episode_rows=tuple(episode_rows),
                valid_start=split.train_max_start,
                data_hash=run_data_hash,
            )
        )
    return results


def eval_fact_to_fact_read(fact: Fact) -> FactRead:
    """Eval `Fact` thành `FactRead` cho vòng học (E19 của đề xuất).

    `id` = `tenant_id` của fact + `":"` + khóa canonical; `scope` là chuỗi
    của `fact.scope`; `condition` = None (fact khám phá không có điều kiện);
    còn lại giữ nguyên. Trạng thái giữ nguyên (fact khám phá là `active`).
    """
    return FactRead(
        id=f"{fact.tenant_id}:{fact.canonical_key}",
        scope=fact.scope.value,
        canonical_key=fact.canonical_key,
        template=fact.template,
        activation=fact.activation,
        target=fact.target,
        condition=None,
        status=fact.status,
    )


def document_facts(
    *, base_facts: Sequence[Fact], wabo_facts_list: Sequence[Fact]
) -> tuple[FactRead, ...]:
    """Tập fact điều kiện Tài liệu: fact của nền (Đồng thuận/Phủ quyết) + luật Wabo.

    Nền đi trước, luật Wabo đi sau; thứ tự này là thứ tự đo (tập đo ghi
    đúng thứ tự này vào bản đồ).
    """
    return tuple(eval_fact_to_fact_read(fact) for fact in base_facts) + tuple(
        eval_fact_to_fact_read(fact) for fact in wabo_facts_list
    )


def fact_read_to_eval_fact(fact: FactRead) -> Fact:
    """`FactRead` thành eval `Fact` để đo bốn chỉ số.

    `tenant_id` lấy từ `id` (phần trước dấu `:` đầu tiên — id do
    `eval_fact_to_fact_read` hoặc `measured_fact_set` đặt theo đúng lược
    đồ đó). `scope`/`status` chuyển từ chuỗi/enum tương ứng.
    """
    tenant_id = fact.id.split(":", 1)[0]
    return Fact(
        canonical_key=fact.canonical_key,
        template=fact.template,
        activation=fact.activation,
        target=fact.target,
        status=fact.status,
        scope=FactScope(fact.scope),
        tenant_id=tenant_id,
    )


def _fact_row_to_fact_read(fact_row: FactRow) -> FactRead:
    """Hàng fact của outcome thành `FactRead` (để gộp vào tập đo)."""
    return FactRead(
        id=f"{fact_row.tenant_id}:{fact_row.canonical_key}",
        scope=fact_row.scope,
        canonical_key=fact_row.canonical_key,
        template=fact_row.template,
        activation=fact_row.activation or "",
        target=fact_row.target or "",
        condition=fact_row.condition,
        status=FactStatus(fact_row.status),
    )


def measured_fact_set(
    *, input_facts: Sequence[FactRead], outcome: RoundOutcome
) -> tuple[FactRead, ...]:
    """Tập fact đo của một vòng: đầu vào + fact_rows, trừ fact_closes.

    Fact đầu vào bị đóng (RETIRE/CONTRADICT) thì trừ ra; fact mới của
    vòng (ADD/CONTRADICT) thì cộng vào. Khóa gộp là (phạm vi, khóa
    canonical) — cùng khóa ở hai phạm vi là hai fact khác nhau, giữ cả
    hai; fact mới cùng khóa cùng phạm vi thì thay fact cũ (mới hơn).
    """
    by_scope_key: dict[tuple[str, str], FactRead] = {}
    closed_ids = {close.fact_id for close in outcome.fact_closes}
    for fact in input_facts:
        if fact.id in closed_ids:
            continue
        by_scope_key[(fact.scope, fact.canonical_key)] = fact
    for fact_row in outcome.fact_rows:
        fact_read = _fact_row_to_fact_read(fact_row)
        by_scope_key[(fact_read.scope, fact_read.canonical_key)] = fact_read
    return tuple(by_scope_key.values())


def compute_round_metrics(
    *,
    measured_facts: Sequence[FactRead],
    tenant_data: TenantData,
    condition: str,
    n_draws: int,
    seed: int,
) -> MetricsWithCI:
    """Bốn chỉ số kèm khoảng tin cậy 95% cho tập fact đo của một vòng.

    Dùng đúng hàm 10.2 (`metrics_with_ci`) trên trace đo của tenant
    (bộ chuẩn: 60 cuối; BPIC: phần hiệu chỉnh) với đáp án của tenant.
    Chỉ fact `active` mới tính vào chỉ số (theo `compute_metrics`).
    """
    facts = [fact_read_to_eval_fact(fact) for fact in measured_facts]
    return metrics_with_ci(
        facts,
        tenant_data.ground_truth.reference,
        tenant_data.measure_traces,
        tenant_data.tenant_id,
        n_draws=n_draws,
        seed=seed,
        condition=condition,
    )


def build_measures_for(
    *,
    train_traces: Sequence[Trace],
    input_facts: Sequence[FactRead],
    policy: Policy,
) -> MeasuresFn:
    """Dựng `measures_for` thật: đếm `Measures` trên trace học.

    Implementation production đầu tiên của `MeasuresFn` (E18): đếm bằng
    chứng của luật trên trace học (`count_rule_evidence`), cận dưới
    Wilson và hậu nghiệm Beta theo đúng `measures.py` với tiên nghiệm
    trung tính (độ tin 0,5) và độ mạnh mặc định của chính sách. Không có
    lần thử nào (luật không kích hoạt trên trace học) thì Wilson là 0 và
    Beta là xác suất từ tiên nghiệm một mình.
    """

    def measures_for(candidate: Candidate, delta: Delta) -> Measures:
        insight = delta.insight
        rule = Rule(
            template=insight.template,
            first=insight.activation,
            second=insight.target,
            support=0.0,
            confidence=0.0,
        )
        evidence = count_rule_evidence(rule, train_traces)
        prior = Prior(
            canonical_key=insight.canonical_key,
            confidence=FLAT_PRIOR_CONFIDENCE,
            strength=None,
        )
        if evidence.trials == 0:
            wilson = 0.0
            beta = prior_prob_ge(
                prior,
                policy.confidence_threshold,
                strength_default=policy.prior_strength_default,
            )
        else:
            wilson = wilson_lower(evidence.successes, evidence.trials)
            beta = posterior_prob_ge(
                prior,
                evidence.successes,
                evidence.trials,
                policy.confidence_threshold,
                strength_default=policy.prior_strength_default,
            )
        return Measures(
            has_direct_conflict=delta.kind in (DeltaKind.CONTRADICT, DeltaKind.RETIRE),
            schema_valid=True,
            from_trace=insight.source is InsightSource.TRACE,
            wilson_lower=wilson,
            beta_prob=beta,
            is_scope_promotion=insight.scope == GLOBAL_TENANT_ID
            and any(
                fact.canonical_key == insight.canonical_key and fact.scope != GLOBAL_TENANT_ID
                for fact in input_facts
            ),
            from_global=insight.scope == GLOBAL_TENANT_ID,
            has_condition=insight.condition is not None,
            matching_cases=evidence.trials,
            fact_status=delta.fact.status if delta.fact is not None else None,
            is_new=delta.kind is DeltaKind.ADD,
            human_early_activate=False,
            has_rubric_clause=False,
        )

    return measures_for


def make_candidate_id_for() -> Callable[[], str]:
    """Bộ đếm `candidate-{n}` từ 0 mỗi vòng (cùng lược đồ 11.3 dùng)."""
    counter = itertools.count()
    return lambda: f"candidate-{next(counter)}"


def max_reflector_calls(*, n_trajectories: int, batch_size: int) -> int:
    """Số lần gọi Reflector tối đa của một vòng (công thức 10.4)."""
    if batch_size < 1:
        raise ValueError(f"reflector_batch_size phải >= 1, nhận {batch_size}")
    if n_trajectories < 0:
        raise ValueError(f"số trajectory phải >= 0, nhận {n_trajectories}")
    return math.ceil(n_trajectories / batch_size)


def compute_ceiling(
    *,
    n_trajectories: int,
    batch_size: int,
    max_cost_per_call: int,
    factor: float = CEILING_SAFETY_FACTOR,
) -> int:
    """Trần token một vòng (A.4).

    Lần gọi tối đa x chi phí/lần gọi lớn nhất đã đo x hệ số an toàn
    (mặc định 1,5). Trần là tham số tính lúc chạy, không phải con số
    viết sẵn.
    """
    if max_cost_per_call < 1:
        raise ValueError(f"chi phí/lần gọi lớn nhất phải >= 1, nhận {max_cost_per_call}")
    if factor <= 0.0:
        raise ValueError(f"hệ số an toàn phải dương, nhận {factor}")
    calls = max_reflector_calls(n_trajectories=n_trajectories, batch_size=batch_size)
    return math.ceil(calls * max_cost_per_call * factor)


def build_reflector(
    *, settings: Settings, seed: int, backend: Literal["cpu", "endpoint"]
) -> Reflector:
    """Dựng Reflector thật từ Settings (backend là tham số do 11.1 quyết).

    Không dùng `wabo_rules.build_reflector` (nó hard-code backend
    `"cpu"`); driver nhận backend qua `--backend` (`cpu`/`endpoint`).
    """
    model = model_from_settings(settings, backend=backend)
    return Reflector(
        model,
        batch_size=settings.reflector_batch_size,
        max_insights_per_batch=settings.reflector_max_insights_per_batch,
        seed=seed,
    )


RoleConnect = Callable[[str], AbstractContextManager["Connection[Any]"]]
"""Hàm mở kết nối DB dưới một vai (`<tenant>__<chức năng>` hay `promoter`).

Trả context manager (commit khi thoát bình thường, rollback khi lỗi) —
`psycopg.connect` thỏa giao diện này. Driver nhận hàm này qua tiêm phụ
thuộc để test dùng `as_role` của conftest thay vì DSN thật.
"""


def build_role_dsn(base_dsn: str, role: str, password: str) -> str:
    """DSN cho một vai DB từ DSN gốc (đổi user/password, giữ host/port/db)."""
    parsed = urlparse(base_dsn)
    if not parsed.hostname or not parsed.path or len(parsed.path) < 2:
        raise ValueError(f"DSN cơ sở không có host/db: {base_dsn!r}")
    netloc = f"{role}:{quote(password, safe='')}@{parsed.hostname}"
    if parsed.port is not None:
        netloc += f":{parsed.port}"
    return urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))


def make_role_connect(
    *, base_dsn: str, tenant_password: str, promoter_password: str
) -> RoleConnect:
    """Dựng hàm mở kết nối theo vai từ DSN gốc + mật khẩu hai loại vai.

    Vai `promoter` dùng mật khẩu promoter; mọi vai `<tenant>__*` dùng mật
    khẩu tenant. Mật khẩu do người chạy cấp (cờ CLI hay biến môi trường),
    không hard-code, không ghi vào tệp hay bản đồ.
    """

    def connect(role: str) -> AbstractContextManager[Connection[Any]]:
        password = promoter_password if role == "promoter" else tenant_password
        return psycopg.connect(build_role_dsn(base_dsn, role, password))

    return connect


def resolve_db_passwords(
    *,
    tenant_password_arg: str | None,
    promoter_password_arg: str | None,
) -> tuple[str, str]:
    """Mật khẩu vai DB: cờ CLI thắng, rồi biến môi trường, thiếu thì lỗi.

    Hai biến môi trường là `PRAXON_DB_TENANT_PASSWORD` (mọi vai
    `<tenant>__*`) và `PRAXON_DB_PROMOTER_PASSWORD` (vai `promoter`).
    Driver là tool ngoài `packages/` nên cổng `check_env_access` không
    quét nó; việc đọc hai biến này được ghi rõ ở đây (chỉ dùng để mở
    kết nối theo vai, không ghi vào đâu).
    """
    tenant_password = tenant_password_arg or os.environ.get("PRAXON_DB_TENANT_PASSWORD")
    promoter_password = promoter_password_arg or os.environ.get("PRAXON_DB_PROMOTER_PASSWORD")
    if not tenant_password:
        raise ValueError(
            "thiếu mật khẩu vai tenant: --db-tenant-password / PRAXON_DB_TENANT_PASSWORD"
        )
    if not promoter_password:
        raise ValueError(
            "thiếu mật khẩu vai promoter: --db-promoter-password / PRAXON_DB_PROMOTER_PASSWORD"
        )
    return tenant_password, promoter_password


def _insert_candidate_row(
    conn: Connection[Any],
    *,
    candidate_id: str,
    tenant_id: str,
    candidate: Candidate,
) -> None:
    """Ghi một hàng candidate qua vai curator (trạng thái `proposed`).

    Theo đúng chuỗi BĐ3: curator tạo, governor duyệt, rồi applier/
    promoter mới áp. `candidate_id` là UUID thật cho bảng candidate
    (không phải id logic `candidate-{n}` của outcome — cột `id` là UUID).
    """
    conn.execute(
        "INSERT INTO candidate (id, tenant_id, target_scope, payload, "
        "rationale, evidence_episode_ids, rule_id, metrics_at_decision, "
        "status, decided_by, rubric_clause) "
        "VALUES (%s, %s, %s, %s::jsonb, %s, %s::uuid[], %s, %s::jsonb, "
        "'proposed', %s, %s)",
        (
            candidate_id,
            tenant_id,
            candidate.target_scope,
            json.dumps(candidate.payload),
            candidate.rationale,
            list(candidate.evidence_episode_ids),
            candidate.rule_id,
            json.dumps(candidate.metrics_at_decision)
            if candidate.metrics_at_decision is not None
            else "{}",
            candidate.decided_by,
            candidate.rubric_clause,
        ),
    )


def _approve_candidate_row(conn: Connection[Any], *, candidate_id: str) -> None:
    """Duyệt một candidate qua vai governor (trạng thái `approved`)."""
    conn.execute("UPDATE candidate SET status = 'approved' WHERE id = %s", (candidate_id,))


def _close_colliding_facts(
    conn: Connection[Any], *, fact_row: FactRow, retired_at: datetime
) -> int:
    """Đóng fact cũ trùng khóa trước khi thêm fact mới (giao thức BĐ5).

    Fact cũ cùng (tenant, phạm vi, khóa) và khoảng hiệu lực chồng lấn,
    chưa retired, thì đóng (thu hẹp `known_during`) trong cùng giao dịch
    rồi mới thêm mới — không thì INSERT vi phạm exclusion constraint.
    Trả số fact đã đóng (thường là 0).
    """
    cursor = conn.execute(
        "SELECT id FROM fact WHERE tenant_id = %s AND scope = %s "
        "AND canonical_key = %s AND status <> 'retired' "
        "AND valid_during && tstzrange(%s, %s, '[)')",
        (
            fact_row.tenant_id,
            fact_row.scope,
            fact_row.canonical_key,
            fact_row.valid_start,
            fact_row.valid_end,
        ),
    )
    existing = [row[0] for row in cursor.fetchall()]
    for fact_id in existing:
        close_fact(conn, FactClose(fact_id=str(fact_id), retired_at=retired_at))
    return len(existing)


def _is_uuid(value: str) -> bool:
    """Một chuỗi có phải UUID không (để phân biệt id fact DB với id logic)."""
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def write_round_to_db(
    *,
    outcome: RoundOutcome,
    run_row: RunRow,
    tenant_id: str,
    retired_at: datetime,
    connect: RoleConnect,
) -> dict[str, Any]:
    """Ghi `run` + event + candidate + fact của một vòng xuống DB.

    Mỗi vai một giao dịch (DB không cho một giao dịch chung qua nhiều
    vai — đề xuất nói "một giao dịch mỗi vòng" nhưng không làm được dưới
    quyền theo vai V2/V3; đây là diễn giải trung thực: mỗi vai ghi phần
    của mình nguyên tử, theo đúng thứ tự phụ thuộc):
    coordinator ghi `run` + event; curator ghi candidate rồi governor
    duyệt; applier (tenant) / promoter (global) ghi fact. Fact trùng
    khóa với fact vòng trước thì đóng cũ rồi mới thêm (BĐ5).

    `run_row` đã mang `wall_time` đo thật (người gọi ghi đè sau vòng).
    Trả bản ghi: `run_id`, ánh xạ id logic `candidate-{n}` -> UUID hàng
    candidate trong DB, số fact đã ghi, số fact cũ đã đóng vì trùng khóa,
    và id các lệnh đóng bị bỏ qua (fact đầu vào chưa từng ghi xuống DB
    nên không có gì để đóng — ghi rõ, không im lặng bỏ qua).
    """
    with connect(f"{tenant_id}__coordinator") as conn:
        run_id = insert_run(conn, run_row)
        for event in outcome.events:
            insert_event(conn, replace(event, run_id=run_id))

    candidate_map: dict[str, str] = {}
    for decision, logical_id in zip(outcome.decisions, outcome.candidate_ids, strict=True):
        if decision.decision.verdict is not DecisionVerdict.AUTO_APPROVE:
            continue
        db_candidate_id = str(uuid.uuid4())
        candidate_map[logical_id] = db_candidate_id
        with connect(f"{tenant_id}__curator") as conn:
            _insert_candidate_row(
                conn,
                candidate_id=db_candidate_id,
                tenant_id=tenant_id,
                candidate=decision.candidate,
            )
        with connect(f"{tenant_id}__governor") as conn:
            _approve_candidate_row(conn, candidate_id=db_candidate_id)

    facts_written = 0
    collisions_closed = 0
    skipped_closes: list[str] = []
    tenant_rows = [fact_row for fact_row in outcome.fact_rows if fact_row.scope != "global"]
    global_rows = [fact_row for fact_row in outcome.fact_rows if fact_row.scope == "global"]
    for rows, role in (
        (tenant_rows, f"{tenant_id}__applier"),
        (global_rows, "promoter"),
    ):
        if not rows:
            continue
        with connect(role) as conn:
            for fact_row in rows:
                collisions_closed += _close_colliding_facts(
                    conn, fact_row=fact_row, retired_at=retired_at
                )
                db_id = candidate_map.get(fact_row.candidate_id or "")
                if db_id is None:
                    raise ValueError(
                        f"fact {fact_row.canonical_key}: candidate "
                        f"{fact_row.candidate_id!r} chưa ghi hàng candidate"
                    )
                if insert_fact(conn, replace(fact_row, candidate_id=db_id)):
                    facts_written += 1

    for close in outcome.fact_closes:
        if not _is_uuid(close.fact_id):
            skipped_closes.append(close.fact_id)
            continue
        closed = False
        for role in (f"{tenant_id}__applier", "promoter"):
            with connect(role) as conn:
                if close_fact(conn, close):
                    closed = True
                    break
        if not closed:
            skipped_closes.append(close.fact_id)

    return {
        "run_id": run_id,
        "candidate_map": candidate_map,
        "facts_written": facts_written,
        "collisions_closed": collisions_closed,
        "skipped_closes": skipped_closes,
    }


def _metric_to_dict(metric: MetricCI) -> dict[str, float]:
    """Một chỉ số kèm khoảng tin cậy thành dict JSON."""
    return {
        "value": metric.value,
        "lower": metric.lower,
        "upper": metric.upper,
    }


def _metrics_to_dict(metrics: MetricsWithCI) -> dict[str, dict[str, float]]:
    """Bốn chỉ số kèm khoảng tin cậy thành dict JSON."""
    return {
        "precision": _metric_to_dict(metrics.precision),
        "recall": _metric_to_dict(metrics.recall),
        "violation_rate": _metric_to_dict(metrics.violation_rate),
        "negative_transfer": _metric_to_dict(metrics.negative_transfer),
    }


def _fact_read_to_dict(fact: FactRead) -> dict[str, Any]:
    """Một fact đo thành dict JSON (đủ để script báo cáo dựng lại)."""
    return {
        "canonical_key": fact.canonical_key,
        "template": fact.template,
        "activation": fact.activation,
        "target": fact.target,
        "condition": fact.condition,
        "status": fact.status.value,
        "scope": fact.scope,
        "tenant_id": fact.id.split(":", 1)[0],
    }


def load_manifest(path: Path) -> dict[str, Any]:
    """Nạp bản đồ đã có (thiếu tệp thì bản đồ rỗng)."""
    if not path.is_file():
        return {"task": "11.2", "entries": []}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise ValueError(f"bản đồ {path} sai hình dạng: thiếu 'entries'")
    return data


def append_manifest_entry(path: Path, entry: dict[str, Any]) -> None:
    """Ghi thêm một mục vào bản đồ (ghi nguyên tử qua tệp tạm + đổi tên)."""
    data = load_manifest(path)
    data["entries"].append(entry)
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(text)
    tmp_path.replace(path)


def load_wabo_rules(path: Path) -> tuple[Rule, ...]:
    """Nạp luật Wabo đã trích ở 9.1.

    Tệp JSON là danh sách {template, activation, target}. Thiếu tệp thì
    từ chối (mã 1) — luật là đầu vào bắt buộc của điều kiện 7, không tự
    bịa. Tệp rỗng (`[]`) thì phần tài liệu rỗng, ghi rõ.
    """
    if not path.is_file():
        raise FileNotFoundError(f"thiếu tệp luật Wabo: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"tệp luật Wabo {path} phải là danh sách JSON")
    rules: list[Rule] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError(f"mục luật Wabo phải là object JSON, nhận {item!r}")
        template = item.get("template")
        activation = item.get("activation")
        target = item.get("target")
        if not isinstance(template, str) or not isinstance(activation, str):
            raise ValueError(f"luật Wabo thiếu template/activation: {item!r}")
        if not isinstance(target, str):
            raise ValueError(f"luật Wabo thiếu target: {item!r}")
        if template not in ("response", "precedence"):
            raise ValueError(f"luật Wabo chỉ nhận mẫu response/precedence, nhận {template!r}")
        rules.append(
            Rule(
                template=template,
                first=activation,
                second=target,
                support=0.0,
                confidence=0.0,
            )
        )
    return tuple(rules)


def wabo_facts(rules: Sequence[Rule]) -> tuple[Fact, ...]:
    """Luật Wabo thành fact `global` ở `trial` (điều kiện 7)."""
    return tuple(
        facts_from_rules(
            rules, GLOBAL_TENANT_ID, scope=FactScope.GLOBAL, status=FactStatus.TRIAL
        )
    )


def build_checkpoint_store(*, settings: Settings, checkpoint_dir: Path) -> CheckpointStore:
    """Store checkpoint theo cấu hình: local (thư mục) hay S3 (B2)."""
    if settings.checkpoint_store == "local":
        return LocalCheckpointStore(checkpoint_dir)
    if settings.s3_bucket is None or settings.s3_endpoint_url is None:
        raise ValueError("checkpoint_store='s3' mà thiếu s3_bucket/s3_endpoint_url")
    if settings.s3_access_key_id is None or settings.s3_secret_access_key is None:
        raise ValueError("checkpoint_store='s3' mà thiếu PRAXON_S3_*")
    return S3CheckpointStore(
        bucket=settings.s3_bucket,
        endpoint_url=settings.s3_endpoint_url,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key,
    )


def _mean_f1(entries: Sequence[dict[str, Any]], condition: str) -> float:
    """F1 trung bình qua các tenant của một điều kiện (tiêu chí 10.2)."""
    values = [
        f1_score(
            entry["metrics"]["precision"]["value"],
            entry["metrics"]["recall"]["value"],
        )
        for entry in entries
        if entry["condition"] == condition
    ]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _build_entry(
    *,
    condition: str,
    tenant: TenantRoundData,
    run_id: str | None,
    status: str,
    model_id: str,
    model_revision: str,
    tokens_in: int,
    tokens_out: int,
    token_budget_total: int,
    wall_time: float,
    metrics: MetricsWithCI,
    measured_facts: Sequence[FactRead],
    candidate_map: Mapping[str, str],
    skipped_closes: Sequence[str],
    n_draws: int,
    seed: int,
    code_commit: str,
    config_hash: str,
    document_base: str | None,
    wabo_rule_count: int,
    cache_hits: int,
    note: str,
) -> dict[str, Any]:
    """Một mục bản đồ vòng→điều kiện (đủ để script báo cáo đối chiếu)."""
    return {
        "run_id": run_id,
        "condition": condition,
        "tenant_id": tenant.tenant_id,
        "source": tenant.source,
        "model_id": model_id,
        "model_revision": model_revision,
        "code_commit": code_commit,
        "config_hash": config_hash,
        "data_hash": tenant.data_hash,
        "token_budget_total": token_budget_total,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "wall_time": wall_time,
        "status": status,
        "n_train": len(tenant.tenant_data.train_traces),
        "n_measure": len(tenant.tenant_data.measure_traces),
        "valid_start": tenant.valid_start.isoformat(),
        "origin_date": (
            tenant.origin_date.isoformat() if tenant.origin_date is not None else None
        ),
        "n_draws": n_draws,
        "seed": seed,
        "metrics": _metrics_to_dict(metrics),
        "measured_facts": [_fact_read_to_dict(fact) for fact in measured_facts],
        "candidate_map": dict(candidate_map),
        "skipped_closes": list(skipped_closes),
        "document_base": document_base,
        "wabo_rules": wabo_rule_count,
        "cache_hits": cache_hits,
        "note": note,
    }


def _git_head() -> str | None:
    """Commit HEAD hiện tại (`git rev-parse HEAD`), None nếu không lấy được."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def run_model_round(
    *,
    tenant: TenantRoundData,
    condition: str,
    facts: tuple[FactRead, ...],
    settings: Settings,
    reflector: Reflector,
    seed: int,
    code_commit: str,
    config_hash: str,
    ceiling: int,
    store: CheckpointStore,
    connect: RoleConnect,
    n_draws: int,
) -> dict[str, Any]:
    """Chạy một vòng học có mô hình: round -> DB -> chỉ số -> mục bản đồ.

    Lỗi mô hình (`ModelCallError`/`ReflectorBatchError`) thì ghi hàng
    `run` trạng thái `failed` (spec dòng 219: vòng fail vẫn ghi hàng,
    không nuốt lỗi) rồi trả mục `failed` — người gọi dừng ngay (mã 2).
    Chạm trần thì ghi hàng `budget_exceeded` + outcome dở dang rồi trả
    mục đó — người gọi chạy tiếp vòng sau (trần là theo vòng, mã 3 cuối).
    `wall_time` đo sau vòng rồi ghi đè vào hàng `run` trước khi insert
    (coordinator xây hàng `run` từ `round.wall_time` nên không đo trước
    được; 0.0 lúc dựng round chỉ là chỗ giữ).
    """
    rule_table = default_rule_table()
    policy = rule_table.policy
    measures_for = build_measures_for(
        train_traces=tenant.tenant_data.train_traces,
        input_facts=facts,
        policy=policy,
    )
    retired_at = datetime.now(UTC)
    cache = ResponseCache()
    learning_round = LearningRound(
        tenant_id=tenant.tenant_id,
        episode_rows=tenant.episode_rows,
        facts=facts,
        rule_table=rule_table,
        seed=seed,
        model_id=settings.model_id,
        model_revision=settings.model_revision,
        code_commit=code_commit,
        config_hash=config_hash,
        data_hash=tenant.data_hash,
        valid_start=tenant.valid_start,
        retired_at=retired_at,
        wall_time=0.0,
        locked_config_hash=None,
        on_test_split=False,
        checkpoint_every_n_cases=(settings.checkpoint_every_n_cases if ceiling > 0 else 0),
        checkpoint_store=store if ceiling > 0 else None,
        resume_from=None,
        cache=cache,
        token_budget_total=ceiling,
        token_budget_reserve_per_call=settings.token_budget_reserve_per_call,
        reflector_batch_size=settings.reflector_batch_size,
        config_hash_no_budget=compute_config_hash_without_budget(settings),
    )
    started = time.monotonic()
    try:
        outcome = run_learning_round(
            learning_round,
            reflect=reflector.reflect,
            measures_for=measures_for,
            candidate_id_for=make_candidate_id_for(),
        )
        status = "succeeded"
        error_note = ""
    except BudgetExceededError as exc:
        outcome = exc.outcome
        status = "budget_exceeded"
        error_note = f"chạm trần token {ceiling}"
    except (ModelCallError, ReflectorBatchError) as exc:
        wall_time = time.monotonic() - started
        failed_row = RunRow(
            tenant_id=tenant.tenant_id,
            seed=seed,
            model_id=settings.model_id,
            model_revision=settings.model_revision,
            code_commit=code_commit,
            config_hash=config_hash,
            data_hash=tenant.data_hash,
            tokens_in=0,
            tokens_out=0,
            wall_time=wall_time,
            status="failed",
        )
        with connect(f"{tenant.tenant_id}__coordinator") as conn:
            run_id = insert_run(conn, failed_row)
        metrics = compute_round_metrics(
            measured_facts=facts,
            tenant_data=tenant.tenant_data,
            condition=condition,
            n_draws=n_draws,
            seed=seed,
        )
        return _build_entry(
            condition=condition,
            tenant=tenant,
            run_id=run_id,
            status="failed",
            model_id=settings.model_id,
            model_revision=settings.model_revision,
            tokens_in=0,
            tokens_out=0,
            token_budget_total=ceiling,
            wall_time=wall_time,
            metrics=metrics,
            measured_facts=facts,
            candidate_map={},
            skipped_closes=[],
            n_draws=n_draws,
            seed=seed,
            code_commit=code_commit,
            config_hash=config_hash,
            document_base=None,
            wabo_rule_count=0,
            cache_hits=0,
            note=f"lỗi mô hình: {exc}",
        )
    wall_time = time.monotonic() - started
    run_row = replace(outcome.run_row, wall_time=wall_time)
    db_result = write_round_to_db(
        outcome=outcome,
        run_row=run_row,
        tenant_id=tenant.tenant_id,
        retired_at=retired_at,
        connect=connect,
    )
    measured = measured_fact_set(input_facts=facts, outcome=outcome)
    metrics = compute_round_metrics(
        measured_facts=measured,
        tenant_data=tenant.tenant_data,
        condition=condition,
        n_draws=n_draws,
        seed=seed,
    )
    note = error_note
    if ceiling > 0:
        used = run_row.tokens_in + run_row.tokens_out
        ratio = used / ceiling
        note = (
            f"{error_note}; đã dùng {used}/{ceiling} token ({ratio:.0%} trần)"
            if error_note
            else f"đã dùng {used}/{ceiling} token ({ratio:.0%} trần)"
        )
        if ratio > CEILING_USED_WARNING_RATIO and status == "succeeded":
            note += " — CẢNH BÁO: đã dùng quá 70% trần, xem lại hệ số trần (A.4)"
    return _build_entry(
        condition=condition,
        tenant=tenant,
        run_id=db_result["run_id"],
        status=status,
        model_id=settings.model_id,
        model_revision=settings.model_revision,
        tokens_in=run_row.tokens_in,
        tokens_out=run_row.tokens_out,
        token_budget_total=ceiling,
        wall_time=wall_time,
        metrics=metrics,
        measured_facts=measured,
        candidate_map=db_result["candidate_map"],
        skipped_closes=db_result["skipped_closes"],
        n_draws=n_draws,
        seed=seed,
        code_commit=code_commit,
        config_hash=config_hash,
        document_base=None,
        wabo_rule_count=0,
        cache_hits=0,
        note=note,
    )


def run_in_memory_measurement(
    *,
    tenant: TenantRoundData,
    condition: str,
    facts: tuple[FactRead, ...],
    seed: int,
    code_commit: str,
    config_hash: str,
    n_draws: int,
) -> dict[str, Any]:
    """Đo một điều kiện trong bộ nhớ (không mô hình, không vòng học).

    Tập đo chính là tập fact đầu vào (không có vòng học nên không thêm
    hay đóng fact nào). Không hàng `run` (`run_id = null`), không tốn
    GPU; mục bản đồ ghi rõ lý do.
    """
    started = time.monotonic()
    metrics = compute_round_metrics(
        measured_facts=facts,
        tenant_data=tenant.tenant_data,
        condition=condition,
        n_draws=n_draws,
        seed=seed,
    )
    wall_time = time.monotonic() - started
    return _build_entry(
        condition=condition,
        tenant=tenant,
        run_id=None,
        status="in_memory",
        model_id="",
        model_revision="",
        tokens_in=0,
        tokens_out=0,
        token_budget_total=0,
        wall_time=wall_time,
        metrics=metrics,
        measured_facts=facts,
        candidate_map={},
        skipped_closes=[],
        n_draws=n_draws,
        seed=seed,
        code_commit=code_commit,
        config_hash=config_hash,
        document_base=None,
        wabo_rule_count=0,
        cache_hits=0,
        note="không chạy vòng học (không mô hình)",
    )


def _format_entry_line(entry: dict[str, Any]) -> str:
    """Một mục bản đồ thành một dòng tóm tắt (in sau mỗi vòng)."""
    metrics = entry["metrics"]
    return (
        f"{entry['tenant_id']} — {entry['condition']} ({entry['source']}): "
        f"precision {metrics['precision']['value']:.3f}, "
        f"recall {metrics['recall']['value']:.3f}, "
        f"vi phạm {metrics['violation_rate']['value']:.3f}, "
        f"negative transfer {metrics['negative_transfer']['value']:.3f}; "
        f"token {entry['tokens_in'] + entry['tokens_out']} "
        f"(trần {entry['token_budget_total']}); "
        f"{entry['wall_time']:.1f}s; {entry['status']}"
    )


def main(argv: list[str] | None = None) -> int:
    """Lệnh chạy bảy điều kiện (task 11.2): `python -m tools.kaggle.driver_11_2`.

    Mã thoát: 0 = mọi vòng xong; 1 = lỗi dữ liệu (thiếu tệp / SHA không
    khớp / dữ liệu sai hình dạng); 2 = tham số không hợp lệ hay lỗi mô
    hình; 3 = có vòng chạm trần token (các vòng khác vẫn chạy xong).
    """
    parser = argparse.ArgumentParser(
        prog="tools.kaggle.driver_11_2",
        description="Chạy bảy điều kiện thí nghiệm (task 11.2).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="tệp TOML cấu hình (bắt buộc: driver cần database_url + store)",
    )
    parser.add_argument("--seed", type=int, default=SYNTHETIC_SEED, help="seed (mặc định 42)")
    parser.add_argument(
        "--condition",
        choices=[*ALL_CONDITIONS, "all"],
        default="all",
        help="một điều kiện hay 'all' (mặc định: cả bảy, theo thứ tự spec)",
    )
    parser.add_argument(
        "--source",
        choices=[*SOURCES, "all"],
        default="all",
        help="nguồn dữ liệu: synthetic, bpic2015 hay all (mặc định)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="chỉ chạy N vòng có mô hình đầu (vòng thử P0)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(DEFAULT_MANIFEST_NAME),
        help="tệp bản đồ vòng→điều kiện (mặc định: 11.2-manifest.json)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="thư mục cache chứa 5 tệp BPIC15_N.xes",
    )
    parser.add_argument(
        "--backend",
        choices=["cpu", "endpoint"],
        default="cpu",
        help="backend mô hình (do verdict 11.1 quyết; mặc định cpu)",
    )
    parser.add_argument(
        "--document-base",
        choices=[CONSENSUS, VETO],
        default=None,
        help="nền cho điều kiện Tài liệu (mặc định: chọn theo F1 trung bình)",
    )
    parser.add_argument(
        "--wabo-rules",
        type=Path,
        default=None,
        help="tệp JSON luật Wabo đã trích ở 9.1 (bắt buộc khi chạy Tài liệu)",
    )
    parser.add_argument(
        "--max-cost-per-call",
        type=int,
        default=SAFE_MAX_COST_PER_CALL,
        help="chi phí/lần gọi lớn nhất đã đo, để tính trần (mặc định 2048)",
    )
    parser.add_argument(
        "--ceiling-factor",
        type=float,
        default=CEILING_SAFETY_FACTOR,
        help="hệ số an toàn cho công thức trần (mặc định 1,5)",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=Path("checkpoints"),
        help="thư mục checkpoint khi store là local",
    )
    parser.add_argument(
        "--db-tenant-password",
        default=None,
        help="mật khẩu vai <tenant>__* (mặc định: PRAXON_DB_TENANT_PASSWORD)",
    )
    parser.add_argument(
        "--db-promoter-password",
        default=None,
        help="mật khẩu vai promoter (mặc định: PRAXON_DB_PROMOTER_PASSWORD)",
    )
    parser.add_argument(
        "--code-commit",
        default=None,
        help="commit code của lần chạy (mặc định: git rev-parse HEAD)",
    )
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        print(f"--limit phải >= 1, nhận {args.limit}", file=sys.stderr)
        return 2
    if args.max_cost_per_call < 1:
        print(
            f"--max-cost-per-call phải >= 1, nhận {args.max_cost_per_call}",
            file=sys.stderr,
        )
        return 2
    if args.ceiling_factor <= 0.0:
        print(f"--ceiling-factor phải dương, nhận {args.ceiling_factor}", file=sys.stderr)
        return 2
    try:
        settings = load_settings(args.config)
    except (OSError, ValueError) as exc:
        print(f"không nạp được cấu hình: {exc}", file=sys.stderr)
        return 2
    config_hash = compute_config_hash(settings)
    code_commit = args.code_commit or _git_head()
    if code_commit is None:
        print(
            "không lấy được code_commit: chạy trong repo git hay truyền --code-commit",
            file=sys.stderr,
        )
        return 2
    if settings.checkpoint_every_n_cases < 1:
        print(
            "checkpoint_every_n_cases phải >= 1 (vòng có trần mà không ghi "
            "checkpoint thì coordinator từ chối từ đầu)",
            file=sys.stderr,
        )
        return 2
    try:
        tenant_password, promoter_password = resolve_db_passwords(
            tenant_password_arg=args.db_tenant_password,
            promoter_password_arg=args.db_promoter_password,
        )
    except ValueError as exc:
        print(f"thiếu mật khẩu DB: {exc}", file=sys.stderr)
        return 2
    connect = make_role_connect(
        base_dsn=settings.database_url,
        tenant_password=tenant_password,
        promoter_password=promoter_password,
    )
    try:
        store = build_checkpoint_store(settings=settings, checkpoint_dir=args.checkpoint_dir)
    except ValueError as exc:
        print(f"không dựng được checkpoint store: {exc}", file=sys.stderr)
        return 2
    reflector = build_reflector(settings=settings, seed=args.seed, backend=args.backend)
    conditions = ALL_CONDITIONS if args.condition == "all" else (args.condition,)
    sources = SOURCES if args.source == "all" else (args.source,)
    try:
        round_data: dict[str, list[TenantRoundData]] = {}
        if SYNTHETIC_SOURCE in sources:
            round_data[SYNTHETIC_SOURCE] = load_synthetic_round_data(seed=args.seed)
        if BPIC_SOURCE in sources:
            round_data[BPIC_SOURCE] = load_bpic_round_data(cache_dir=args.cache_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"lỗi dữ liệu: {exc}", file=sys.stderr)
        return 1
    fact_sets = {
        source: condition_fact_sets([item.tenant_data for item in tenants])
        for source, tenants in round_data.items()
    }
    wabo_rule_list: tuple[Rule, ...] = ()
    wabo_fact_list: tuple[Fact, ...] = ()
    if DOCUMENT in conditions:
        if args.wabo_rules is None:
            print(
                "điều kiện Tài liệu cần --wabo-rules (tệp JSON luật Wabo đã trích ở 9.1)",
                file=sys.stderr,
            )
            return 2
        try:
            wabo_rule_list = load_wabo_rules(args.wabo_rules)
        except (FileNotFoundError, ValueError) as exc:
            print(f"lỗi dữ liệu: {exc}", file=sys.stderr)
            return 1
        wabo_fact_list = wabo_facts(wabo_rule_list)
    document_base = args.document_base
    if (
        DOCUMENT in conditions
        and document_base is None
        and (CONSENSUS not in conditions or VETO not in conditions)
    ):
        print(
            "điều kiện Tài liệu cần --document-base (nền Đồng thuận hay "
            "Phủ quyết) khi chạy một mình — chạy kèm cả hai điều kiện "
            "5/6 thì driver tự chọn theo F1 trung bình",
            file=sys.stderr,
        )
        return 2
    entries: list[dict[str, Any]] = []
    model_rounds_run = 0
    exit_code = 0
    for condition in conditions:
        for source in sources:
            tenants = round_data[source]
            sets = fact_sets[source]
            for tenant in tenants:
                if condition in IN_MEMORY_CONDITIONS:
                    facts = tuple(
                        eval_fact_to_fact_read(fact)
                        for fact in sets[condition][tenant.tenant_id]
                    )
                    entry = run_in_memory_measurement(
                        tenant=tenant,
                        condition=condition,
                        facts=facts,
                        seed=args.seed,
                        code_commit=code_commit,
                        config_hash=config_hash,
                        n_draws=settings.bootstrap_draws,
                    )
                    append_manifest_entry(args.manifest, entry)
                    entries.append(entry)
                    print(_format_entry_line(entry))
                    continue
                if args.limit is not None and model_rounds_run >= args.limit:
                    break
                if condition == DOCUMENT:
                    base = document_base
                    if base is None:
                        consensus_f1 = _mean_f1(
                            [e for e in entries if e["source"] == source], CONSENSUS
                        )
                        veto_f1 = _mean_f1([e for e in entries if e["source"] == source], VETO)
                        base = CONSENSUS if consensus_f1 >= veto_f1 else VETO
                        print(
                            f"nền Tài liệu ({source}): {base} "
                            f"(F1 Đồng thuận {consensus_f1:.3f}, "
                            f"Phủ quyết {veto_f1:.3f})"
                        )
                    base_facts = sets[base][tenant.tenant_id]
                    facts = document_facts(
                        base_facts=base_facts, wabo_facts_list=wabo_fact_list
                    )
                    doc_base = base
                    wabo_count = len(wabo_rule_list)
                else:
                    facts = tuple(
                        eval_fact_to_fact_read(fact)
                        for fact in sets[condition][tenant.tenant_id]
                    )
                    doc_base = None
                    wabo_count = 0
                ceiling = compute_ceiling(
                    n_trajectories=len(tenant.tenant_data.train_traces),
                    batch_size=settings.reflector_batch_size,
                    max_cost_per_call=args.max_cost_per_call,
                    factor=args.ceiling_factor,
                )
                entry = run_model_round(
                    tenant=tenant,
                    condition=condition,
                    facts=facts,
                    settings=settings,
                    reflector=reflector,
                    seed=args.seed,
                    code_commit=code_commit,
                    config_hash=config_hash,
                    ceiling=ceiling,
                    store=store,
                    connect=connect,
                    n_draws=settings.bootstrap_draws,
                )
                entry["document_base"] = doc_base
                entry["wabo_rules"] = wabo_count
                append_manifest_entry(args.manifest, entry)
                entries.append(entry)
                model_rounds_run += 1
                print(_format_entry_line(entry))
                if entry["status"] == "failed":
                    print(
                        f"dừng: vòng {condition}/{tenant.tenant_id} lỗi mô hình",
                        file=sys.stderr,
                    )
                    return 2
                if entry["status"] == "budget_exceeded":
                    exit_code = 3
    total_hours = sum(entry["wall_time"] for entry in entries) / 3600.0
    print(
        f"xong: {len(entries)} mục bản đồ ({model_rounds_run} vòng học), "
        f"{total_hours:.2f} giờ tường; bản đồ: {args.manifest}"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
