"""Test tích hợp trần token (task 10.4, spec dòng 217).

Cổng ra của task: migration V7 mở trạng thái `budget_exceeded` trên DB
thật; cắt giữa chừng vì trần rồi chạy tiếp với trần cao hơn, kết quả
giống hệt chạy liền mạch. Chạy bằng backend local (không cần B2 thật):
vòng học thuần + store local trên đĩa + DB Postgres thật cho bảng `run`.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from psycopg.errors import CheckViolation

from praxon_core.adapters.local_store import LocalCheckpointStore
from praxon_core.learning.checkpoint import (
    Checkpoint,
    CheckpointStore,
    checkpoint_prefix,
    read_latest_checkpoint,
)
from praxon_core.learning.coordinator import (
    BudgetExceededError,
    LearningRound,
    ReflectorFn,
    ReflectorResult,
    run_learning_round,
)
from praxon_core.learning.curator import FactRead, Insight, InsightSource
from praxon_core.learning.generator import EpisodeRow, Trajectory
from praxon_core.learning.measures import Measures
from praxon_core.learning.rules import default_rule_table
from praxon_core.repositories import migrate as migrations
from praxon_core.repositories.runs import RunRow, insert_run

from .conftest import ADMIN_DSN, as_role, one

VALID_START = datetime(2030, 1, 1, tzinfo=UTC)
RETIRED_AT = datetime(2030, 2, 1, tzinfo=UTC)
EPISODE_ID = "22222222-2222-2222-2222-222222222222"
SEED = 42
MODEL_ID = "Qwen/Qwen3-8B-GGUF"
MODEL_REVISION = "7c41481f57cb95916b40956ab2f0b139b296d974"
CODE_COMMIT = "d8f9e2a0000000000000000000000000000000000"
CONFIG_HASH = "c" * 64
DATA_HASH = "d" * 64
NO_BUDGET_HASH = "n" * 64

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
    token_budget_total: int = 0,
    token_budget_reserve_per_call: int = 2048,
    reflector_batch_size: int = 10,
    config_hash_no_budget: str = "",
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
        token_budget_total=token_budget_total,
        token_budget_reserve_per_call=token_budget_reserve_per_call,
        reflector_batch_size=reflector_batch_size,
        config_hash_no_budget=config_hash_no_budget,
    )


def _reflect_by_trajectory(
    seen: list[str] | None = None,
) -> ReflectorFn:
    def reflect(
        trajectories: Sequence[Trajectory], facts: Sequence[FactRead]
    ) -> ReflectorResult:
        if seen is not None:
            seen.extend(t.case_id for t in trajectories)
        insights = []
        tokens_in = 0
        tokens_out = 0
        for trajectory in trajectories:
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


def _prefix() -> str:
    return checkpoint_prefix(
        tenant_id="acme", seed=SEED, config_hash=CONFIG_HASH, data_hash=DATA_HASH
    )


def _run_row(seed: int, status: str) -> RunRow:
    return RunRow(
        tenant_id="acme",
        seed=seed,
        model_id=f"model-test-{seed}",
        model_revision="r" * 40,
        code_commit="c" * 40,
        config_hash="f" * 64,
        data_hash="d" * 64,
        tokens_in=7,
        tokens_out=11,
        wall_time=2.5,
        status=status,
    )


def test_migration_v7_mo_budget_exceeded(pg: None) -> None:
    # Chạy lại migrator lần hai là no-op (lũy đẳng).
    assert migrations.apply(ADMIN_DSN) == []
    with as_role("acme__coordinator") as conn:
        run_id = insert_run(conn, _run_row(10401, "budget_exceeded"))
        (status,) = one(conn, "SELECT status FROM run WHERE id = %s", (run_id,))
        assert status == "budget_exceeded"
        # Trạng thái không có trong CHECK vẫn bị từ chối.
        with pytest.raises(CheckViolation, match="run_status_check"):
            conn.execute(
                "INSERT INTO run (tenant_id, seed, model_id, model_revision, "
                "code_commit, config_hash, data_hash, status) "
                "VALUES ('acme', 10402, 'm', 'r', 'c', 'h', 'd', 'khong-co')"
            )


def test_cat_giua_chung_vi_tran_roi_resume_ket_qua_khong_doi(tmp_path: Path, pg: None) -> None:
    store = LocalCheckpointStore(tmp_path / "ckp")
    prefix = _prefix()
    shared_ids = _candidate_ids()
    seen: list[str] = []

    # Lần 1: trần 20 chỉ đủ 2 lô — chạm trần ở lô 3 (4 case đã xong).
    with pytest.raises(BudgetExceededError) as exc_info:
        run_learning_round(
            _round_cases(
                checkpoint_every_n_cases=2,
                checkpoint_store=store,
                token_budget_total=20,
                token_budget_reserve_per_call=10,
                config_hash_no_budget=NO_BUDGET_HASH,
            ),
            reflect=_reflect_by_trajectory(seen=seen),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=shared_ids,
        )
    error = exc_info.value
    assert error.outcome.run_row.status == "budget_exceeded"
    assert (error.outcome.run_row.tokens_in, error.outcome.run_row.tokens_out) == (4, 8)
    assert seen == ["c1", "c2", "c3", "c4"]
    assert store.list_keys(prefix) == [prefix + "/000002.json", prefix + "/000004.json"]
    latest = read_latest_checkpoint(store, prefix)
    assert latest is not None
    assert latest.cases_done == ("c1", "c2", "c3", "c4")

    # Bên gọi ghi `run` budget_exceeded xuống DB thật (V7 cho phép).
    with as_role("acme__coordinator") as conn:
        run_id = insert_run(conn, error.outcome.run_row)
        (status,) = one(conn, "SELECT status FROM run WHERE id = %s", (run_id,))
        assert status == "budget_exceeded"

    # Lần 2: nâng trần lên 1000, chạy tiếp 2 case còn lại.
    seen.clear()
    resumed = run_learning_round(
        _round_cases(
            checkpoint_every_n_cases=2,
            checkpoint_store=store,
            resume_from=latest,
            token_budget_total=1000,
            token_budget_reserve_per_call=10,
            config_hash_no_budget=NO_BUDGET_HASH,
        ),
        reflect=_reflect_by_trajectory(seen=seen),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=shared_ids,
    )
    assert seen == ["c5", "c6"]

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


def test_resume_voi_tran_cu_khong_goi_mo_hinh(tmp_path: Path, pg: None) -> None:
    store = LocalCheckpointStore(tmp_path / "ckp")
    prefix = _prefix()
    shared_ids = _candidate_ids()
    seen: list[str] = []

    # Lần 1: chạm trần ở lô 3 như trên (trần 20, 4 case đã xong).
    with pytest.raises(BudgetExceededError):
        run_learning_round(
            _round_cases(
                checkpoint_every_n_cases=2,
                checkpoint_store=store,
                token_budget_total=20,
                token_budget_reserve_per_call=10,
                config_hash_no_budget=NO_BUDGET_HASH,
            ),
            reflect=_reflect_by_trajectory(seen=seen),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=shared_ids,
        )
    latest = read_latest_checkpoint(store, prefix)
    assert latest is not None
    assert latest.cases_done == ("c1", "c2", "c3", "c4")

    # Lần 2: giữ nguyên trần cũ (không nâng) → từ chối ngay trước khi
    # gọi mô hình (không tốn thêm token nào).
    seen.clear()
    with pytest.raises(BudgetExceededError):
        run_learning_round(
            _round_cases(
                checkpoint_every_n_cases=2,
                checkpoint_store=store,
                resume_from=latest,
                token_budget_total=20,
                token_budget_reserve_per_call=10,
                config_hash_no_budget=NO_BUDGET_HASH,
            ),
            reflect=_reflect_by_trajectory(seen=seen),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=shared_ids,
        )
    assert seen == []
