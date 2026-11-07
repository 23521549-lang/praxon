"""Test tích hợp checkpoint (task 10.3, spec dòng 215).

Cổng ra của task: cắt giữa lần chạy rồi khởi động lại, chạy tiếp từ con
trỏ, kết quả không đổi. Chạy bằng backend local (không cần B2 thật, không
cần DB): vòng học thuần + store local trên đĩa. Lần push B2 thật kiểm riêng
khi có credentials.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from uuid import UUID

import pytest

from praxon_core.adapters.cache import ResponseCache
from praxon_core.adapters.local_store import LocalCheckpointStore
from praxon_core.learning.checkpoint import (
    Checkpoint,
    CheckpointStore,
    checkpoint_prefix,
    read_latest_checkpoint,
)
from praxon_core.learning.coordinator import (
    LearningRound,
    ReflectorFn,
    ReflectorResult,
    run_learning_round,
)
from praxon_core.learning.curator import FactRead, Insight, InsightSource
from praxon_core.learning.generator import EpisodeRow, Trajectory
from praxon_core.learning.measures import Measures
from praxon_core.learning.rules import default_rule_table

VALID_START = datetime(2030, 1, 1, tzinfo=UTC)
RETIRED_AT = datetime(2030, 2, 1, tzinfo=UTC)
EPISODE_ID = "22222222-2222-2222-2222-222222222222"
SEED = 42
MODEL_ID = "Qwen/Qwen3-8B-GGUF"
MODEL_REVISION = "7c41481f57cb95916b40956ab2f0b139b296d974"
CODE_COMMIT = "d8f9e2a0000000000000000000000000000000000"
CONFIG_HASH = "c" * 64
DATA_HASH = "d" * 64

SIX_CASES = (
    ("c1", ("A", "B")),
    ("c2", ("C", "D")),
    ("c3", ("E", "F")),
    ("c4", ("G", "H")),
    ("c5", ("I", "J")),
    ("c6", ("K", "L")),
)


def _episode(case_id: str, activity: str, occurred: str) -> EpisodeRow:
    return EpisodeRow(
        id=UUID(EPISODE_ID),
        tenant_id="acme",
        case_id=case_id,
        payload={"activity": activity, "case_attributes": {}},
        occurred_at=datetime.fromisoformat(occurred),
        ingested_at=datetime(2026, 11, 6, tzinfo=UTC),
    )


def _measures() -> Measures:
    return Measures(
        has_direct_conflict=False,
        schema_valid=True,
        from_trace=True,
        wilson_lower=0.8,
        beta_prob=0.5,
        is_scope_promotion=False,
        from_global=False,
        has_condition=False,
        matching_cases=0,
        fact_status=None,
        is_new=True,
        human_early_activate=False,
        has_rubric_clause=False,
    )


def _candidate_ids() -> Callable[[], str]:
    counter = itertools.count()
    return lambda: f"candidate-{next(counter)}"


def _round_cases(
    *,
    checkpoint_every_n_cases: int = 0,
    checkpoint_store: CheckpointStore | None = None,
    resume_from: Checkpoint | None = None,
    cache: ResponseCache | None = None,
) -> LearningRound:
    rows = []
    for index, (case_id, activities) in enumerate(SIX_CASES):
        for step, activity in enumerate(activities):
            rows.append(
                _episode(case_id, activity, f"2026-11-06T{10 + index:02d}:{step:02d}:00")
            )
    return LearningRound(
        tenant_id="acme",
        episode_rows=tuple(rows),
        facts=(),
        rule_table=default_rule_table(),
        seed=SEED,
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION,
        code_commit=CODE_COMMIT,
        config_hash=CONFIG_HASH,
        data_hash=DATA_HASH,
        valid_start=VALID_START,
        retired_at=RETIRED_AT,
        wall_time=1.5,
        checkpoint_every_n_cases=checkpoint_every_n_cases,
        checkpoint_store=checkpoint_store,
        resume_from=resume_from,
        cache=cache,
    )


class _CountingModel:
    """Mô hình giả: đếm số lần gọi, trả phản hồi cố định."""

    def __init__(self) -> None:
        """Chưa gọi lần nào."""
        self.calls: int = 0

    def __call__(self, prompt: str) -> str:
        """Đếm một lần gọi rồi trả phản hồi cố định."""
        self.calls += 1
        return "phan-hoi"


def _reflect_by_trajectory(
    cache: ResponseCache | None = None,
    model: Callable[[str], str] | None = None,
    fail_on: tuple[str, ...] = (),
    seen: list[str] | None = None,
) -> ReflectorFn:
    def reflect(
        trajectories: Sequence[Trajectory], facts: Sequence[FactRead]
    ) -> ReflectorResult:
        if seen is not None:
            seen.extend(t.case_id for t in trajectories)
        if any(t.case_id in fail_on for t in trajectories):
            raise RuntimeError("đứt giữa chừng")
        insights = []
        tokens_in = 0
        tokens_out = 0
        for trajectory in trajectories:
            if cache is not None and model is not None:
                cache.get_or_call(
                    f"reflect:{trajectory.case_id}",
                    model_revision=MODEL_REVISION,
                    decode_params={},
                    json_schema={},
                    call=model,
                )
            insights.append(
                Insight(
                    template="response",
                    activation=trajectory.activities[0],
                    target=trajectory.activities[1],
                    condition=None,
                    evidence_episode_ids=[EPISODE_ID],
                    source=InsightSource.TRACE,
                    scope="global",
                )
            )
            tokens_in += 1
            tokens_out += 2
        return ReflectorResult(
            insights=tuple(insights), tokens_in=tokens_in, tokens_out=tokens_out
        )

    return reflect


def test_cat_giua_chung_roi_chay_tiep_ket_qua_khong_doi(tmp_path):
    store = LocalCheckpointStore(tmp_path / "ckp")
    prefix = checkpoint_prefix(
        tenant_id="acme", seed=SEED, config_hash=CONFIG_HASH, data_hash=DATA_HASH
    )
    cache = ResponseCache()
    model = _CountingModel()
    shared_ids = _candidate_ids()
    seen: list[str] = []

    # Lần 1: đứt ở lô 3 (c5) — hai lô đầu đã ghi checkpoint.
    with pytest.raises(RuntimeError, match="đứt giữa chừng"):
        run_learning_round(
            _round_cases(checkpoint_every_n_cases=2, checkpoint_store=store, cache=cache),
            reflect=_reflect_by_trajectory(
                cache=cache, model=model, fail_on=("c5",), seen=seen
            ),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=shared_ids,
        )
    assert seen == ["c1", "c2", "c3", "c4", "c5", "c6"]
    assert model.calls == 4
    assert store.list_keys(prefix) == [prefix + "/000002.json", prefix + "/000004.json"]
    latest = read_latest_checkpoint(store, prefix)
    assert latest is not None
    assert latest.cases_done == ("c1", "c2", "c3", "c4")
    assert len(latest.fact_rows) == 4
    assert len(latest.cache_entries) == 4

    # Lần 2: khởi động lại với cache mới, chạy tiếp từ con trỏ.
    fresh_cache = ResponseCache()
    seen.clear()
    resumed = run_learning_round(
        _round_cases(
            checkpoint_every_n_cases=2,
            checkpoint_store=store,
            resume_from=latest,
            cache=fresh_cache,
        ),
        reflect=_reflect_by_trajectory(cache=fresh_cache, model=model, seen=seen),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=shared_ids,
    )
    assert seen == ["c5", "c6"]
    assert model.calls == 6
    assert store.list_keys(prefix) == [
        prefix + "/000002.json",
        prefix + "/000004.json",
        prefix + "/000006.json",
    ]

    # Chạy liền mạch để đối chiếu: kết quả phải giống hệt (trừ event theo lô).
    reference = run_learning_round(
        _round_cases(),
        reflect=_reflect_by_trajectory(),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert resumed.trajectories == reference.trajectories
    assert resumed.insights == reference.insights
    assert resumed.decisions == reference.decisions
    assert resumed.candidate_ids == reference.candidate_ids
    assert resumed.fact_rows == reference.fact_rows
    assert resumed.fact_closes == reference.fact_closes
    assert (resumed.run_row.tokens_in, resumed.run_row.tokens_out) == (
        reference.run_row.tokens_in,
        reference.run_row.tokens_out,
    )
    assert resumed.run_row.status == reference.run_row.status == "succeeded"
