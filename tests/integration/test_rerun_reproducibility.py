"""Test tích hợp verdict tái lập (task 12.3, spec dòng 191).

Cổng ra của task: migration V8 thêm hai cột verdict vào bảng `run` trên DB
thật; `is_rerun` + `repro_gaps` đi qua `run_learning_round` tới hàng `run`
(gap rỗng → `reproducible`; có gap → `not_reproducible` + đúng tên gap);
`is_rerun` mà không ở trên phần đo thì từ chối; lần chạy thường (không
phải chạy lại) có verdict NULL. Chạy bằng vòng học thuần + DB Postgres
thật cho bảng `run` (không cần B2, không cần mô hình).
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from uuid import UUID

import pytest
from psycopg.errors import CheckViolation

from praxon_core.learning.coordinator import (
    LearningRound,
    ReflectorFn,
    ReflectorResult,
    run_learning_round,
)
from praxon_core.learning.curator import FactRead, Insight
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


def _reflector(insights: list[Insight]) -> ReflectorFn:
    def reflect(
        trajectories: Sequence[Trajectory], facts: Sequence[FactRead]
    ) -> ReflectorResult:
        return ReflectorResult(insights=tuple(insights), tokens_in=0, tokens_out=0)

    return reflect


def _counting_reflector(calls: list[bool]) -> ReflectorFn:
    def reflect(
        trajectories: Sequence[Trajectory], facts: Sequence[FactRead]
    ) -> ReflectorResult:
        calls.append(True)
        return ReflectorResult(insights=(), tokens_in=0, tokens_out=0)

    return reflect


def _candidate_ids() -> Callable[[], str]:
    counter = itertools.count()
    return lambda: f"candidate-{next(counter)}"


def _round(
    *,
    is_rerun: bool = False,
    repro_gaps: tuple[str, ...] = (),
    on_test_split: bool = False,
    locked_config_hash: str | None = None,
) -> LearningRound:
    return LearningRound(
        tenant_id="acme",
        episode_rows=(
            _episode("c1", "A", "2026-11-06T10:00:00"),
            _episode("c1", "B", "2026-11-06T11:00:00"),
        ),
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
        locked_config_hash=locked_config_hash,
        on_test_split=on_test_split,
        is_rerun=is_rerun,
        repro_gaps=repro_gaps,
    )


def _run_row(
    seed: int,
    status: str,
    reproducibility: str | None = None,
    repro_gaps: str = "",
) -> RunRow:
    return RunRow(
        tenant_id="acme",
        seed=seed,
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION,
        code_commit=CODE_COMMIT,
        config_hash=CONFIG_HASH,
        data_hash=DATA_HASH,
        status=status,
        reproducibility=reproducibility,
        repro_gaps=repro_gaps,
    )


def test_migration_v8_them_hai_cot_verdict(pg: None) -> None:
    # Chạy lại migrator lần hai là no-op (lũy đẳng).
    assert migrations.apply(ADMIN_DSN) == []
    with as_role("acme__coordinator") as conn:
        # Ghi verdict `not_reproducible` + gap rồi đọc lại đúng hai cột.
        run_id = insert_run(conn, _run_row(12301, "succeeded", "not_reproducible", "cache"))
        (reproducibility, repro_gaps) = one(
            conn,
            "SELECT reproducibility, repro_gaps FROM run WHERE id = %s",
            (run_id,),
        )
        assert reproducibility == "not_reproducible"
        assert repro_gaps == "cache"
        # Ghi verdict `reproducible` (gap rỗng) rồi đọc lại.
        run_id = insert_run(conn, _run_row(12302, "succeeded", "reproducible", ""))
        (reproducibility, repro_gaps) = one(
            conn,
            "SELECT reproducibility, repro_gaps FROM run WHERE id = %s",
            (run_id,),
        )
        assert reproducibility == "reproducible"
        assert repro_gaps == ""
        # Lần chạy thường: verdict NULL, gap rỗng (mặc định).
        run_id = insert_run(conn, _run_row(12303, "succeeded"))
        (reproducibility, repro_gaps) = one(
            conn,
            "SELECT reproducibility, repro_gaps FROM run WHERE id = %s",
            (run_id,),
        )
        assert reproducibility is None
        assert repro_gaps == ""
        # Giá trị verdict không có trong CHECK vẫn bị từ chối.
        with pytest.raises(CheckViolation, match="run_reproducibility_check"):
            conn.execute(
                "INSERT INTO run (tenant_id, seed, model_id, model_revision, "
                "code_commit, config_hash, data_hash, status, reproducibility) "
                "VALUES ('acme', 12304, 'm', 'r', 'c', 'h', 'd', 'succeeded', 'sai')"
            )


def test_rerun_gap_rong_ghi_reproducible_xuong_db(pg: None) -> None:
    outcome = run_learning_round(
        _round(
            is_rerun=True,
            repro_gaps=(),
            on_test_split=True,
            locked_config_hash=CONFIG_HASH,
        ),
        reflect=_reflector([]),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert outcome.run_row.status == "succeeded"
    with as_role("acme__coordinator") as conn:
        run_id = insert_run(conn, outcome.run_row)
        (reproducibility, repro_gaps) = one(
            conn,
            "SELECT reproducibility, repro_gaps FROM run WHERE id = %s",
            (run_id,),
        )
        assert reproducibility == "reproducible"
        assert repro_gaps == ""


def test_rerun_co_gap_ghi_not_reproducible_xuong_db(pg: None) -> None:
    outcome = run_learning_round(
        _round(
            is_rerun=True,
            repro_gaps=("cache", "code_commit"),
            on_test_split=True,
            locked_config_hash=CONFIG_HASH,
        ),
        reflect=_reflector([]),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert outcome.run_row.status == "succeeded"
    with as_role("acme__coordinator") as conn:
        run_id = insert_run(conn, outcome.run_row)
        (reproducibility, repro_gaps) = one(
            conn,
            "SELECT reproducibility, repro_gaps FROM run WHERE id = %s",
            (run_id,),
        )
        assert reproducibility == "not_reproducible"
        assert repro_gaps == "cache,code_commit"


def test_vong_thuong_ghi_verdict_null_xuong_db(pg: None) -> None:
    outcome = run_learning_round(
        _round(),
        reflect=_reflector([]),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert outcome.run_row.status == "succeeded"
    with as_role("acme__coordinator") as conn:
        run_id = insert_run(conn, outcome.run_row)
        (reproducibility, repro_gaps) = one(
            conn,
            "SELECT reproducibility, repro_gaps FROM run WHERE id = %s",
            (run_id,),
        )
        assert reproducibility is None
        assert repro_gaps == ""


def test_rerun_khong_o_phan_do_thi_tu_choi() -> None:
    # Chạy lại mà không ở trên phần đo thì từ chối trước khi Reflector chạy.
    calls: list[bool] = []
    with pytest.raises(ValueError, match="chạy lại đo thì phải ở trên phần đo"):
        run_learning_round(
            _round(is_rerun=True, on_test_split=False),
            reflect=_counting_reflector(calls),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )
    assert calls == []
