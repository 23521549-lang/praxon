"""Test tích hợp bộ điều phối (plan con 10, task 10.1): ghi `run` xuống DB thật.

Khẳng định nửa DB của cổng ra: `insert_run` ghi đủ sáu trường điều kiện
tái lập, RLS chỉ cho đúng tenant đọc, chỉ coordinator được ghi — và cả
vòng học (run + event + fact) ghi thông một lượt qua đúng vai của nó.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest
from psycopg.errors import InsufficientPrivilege

from praxon_core.learning.candidate import Candidate
from praxon_core.learning.coordinator import (
    LearningRound,
    ReflectorResult,
    run_learning_round,
)
from praxon_core.learning.curator import Delta, FactRead, Insight, InsightSource
from praxon_core.learning.generator import EpisodeRow, Trajectory
from praxon_core.learning.measures import Measures
from praxon_core.learning.rules import default_rule_table
from praxon_core.repositories.events import insert_event
from praxon_core.repositories.facts import insert_fact
from praxon_core.repositories.runs import RunRow, insert_run

from .conftest import as_role, one

VALID_START = datetime(2030, 1, 1, tzinfo=UTC)
RETIRED_AT = datetime(2030, 2, 1, tzinfo=UTC)
EPISODE_ID = "22222222-2222-2222-2222-222222222222"


def _run_row(seed: int) -> RunRow:
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
        status="succeeded",
    )


def _read_run(run_id: str) -> tuple[Any, ...]:
    with as_role("acme__reader") as conn:
        return one(
            conn,
            "SELECT tenant_id, seed, model_id, model_revision, code_commit, "
            "config_hash, data_hash, tokens_in, tokens_out, wall_time, status "
            "FROM run WHERE id = %s",
            (run_id,),
        )


def test_insert_run_ghi_du_sau_truong(pg: None) -> None:
    seed = 42042
    run_id = ""
    with as_role("acme__coordinator") as conn:
        run_id = insert_run(conn, _run_row(seed))
        conn.commit()
    assert _read_run(run_id) == (
        "acme",
        seed,
        f"model-test-{seed}",
        "r" * 40,
        "c" * 40,
        "f" * 64,
        "d" * 64,
        7,
        11,
        2.5,
        "succeeded",
    )


def test_insert_run_mac_dinh_token_va_trang_thai(pg: None) -> None:
    seed = 42043
    run_id = ""
    with as_role("acme__coordinator") as conn:
        run_id = insert_run(
            conn,
            RunRow(
                tenant_id="acme",
                seed=seed,
                model_id="model-mac-dinh",
                model_revision="r" * 40,
                code_commit="c" * 40,
                config_hash="f" * 64,
                data_hash="d" * 64,
            ),
        )
        conn.commit()
    row = _read_run(run_id)
    assert row[7:11] == (0, 0, 0.0, "running")


def test_run_rls_tenant_khac_khong_doc_duoc(pg: None) -> None:
    seed = 42044
    run_id = ""
    with as_role("acme__coordinator") as conn:
        run_id = insert_run(conn, _run_row(seed))
        conn.commit()
    with as_role("globex__coordinator") as conn:
        (count,) = one(conn, "SELECT count(*) FROM run WHERE id = %s", (run_id,))
    assert count == 0
    with as_role("acme__reader") as conn:
        (count,) = one(conn, "SELECT count(*) FROM run WHERE id = %s", (run_id,))
    assert count == 1


def test_run_chi_coordinator_duoc_ghi(pg: None) -> None:
    with as_role("acme__applier") as conn, pytest.raises(InsufficientPrivilege):
        insert_run(conn, _run_row(42045))


def test_vong_hoc_ghi_run_event_fact_thong(pg: None) -> None:
    suffix = uuid.uuid4().hex[:8]
    candidate_id = str(uuid.uuid4())
    seed = 42046

    def reflect(
        trajectories: Sequence[Trajectory], facts: Sequence[FactRead]
    ) -> ReflectorResult:
        return ReflectorResult(
            insights=(
                Insight(
                    template="response",
                    activation=f"A-{suffix}",
                    target=f"B-{suffix}",
                    condition=None,
                    evidence_episode_ids=[EPISODE_ID],
                    source=InsightSource.TRACE,
                    scope="global",
                ),
            ),
            tokens_in=7,
            tokens_out=11,
        )

    def measures_for(candidate: Candidate, delta: Delta) -> Measures:
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

    outcome = run_learning_round(
        LearningRound(
            tenant_id="acme",
            episode_rows=(
                EpisodeRow(
                    tenant_id="acme",
                    case_id="c1",
                    payload={"activity": f"A-{suffix}", "case_attributes": {}},
                    occurred_at=datetime(2026, 11, 6, 10, tzinfo=UTC),
                    ingested_at=datetime(2026, 11, 6, tzinfo=UTC),
                ),
                EpisodeRow(
                    tenant_id="acme",
                    case_id="c1",
                    payload={"activity": f"B-{suffix}", "case_attributes": {}},
                    occurred_at=datetime(2026, 11, 6, 11, tzinfo=UTC),
                    ingested_at=datetime(2026, 11, 6, tzinfo=UTC),
                ),
            ),
            facts=(),
            rule_table=default_rule_table(),
            seed=seed,
            model_id=f"model-test-{seed}",
            model_revision="r" * 40,
            code_commit="c" * 40,
            config_hash="f" * 64,
            data_hash="d" * 64,
            valid_start=VALID_START,
            retired_at=RETIRED_AT,
            wall_time=2.5,
        ),
        reflect=reflect,
        measures_for=measures_for,
        candidate_id_for=lambda: candidate_id,
    )
    assert len(outcome.fact_rows) == 1

    candidate = outcome.decisions[0].candidate
    with as_role("acme__curator") as conn:
        conn.execute(
            "INSERT INTO candidate (id, tenant_id, target_scope, payload, rationale) "
            "VALUES (%s, %s, %s, %s::jsonb, %s)",
            (
                candidate_id,
                "acme",
                "global",
                json.dumps(candidate.payload),
                "test",
            ),
        )
        conn.commit()
    with as_role("acme__governor") as conn:
        conn.execute("UPDATE candidate SET status = 'approved' WHERE id = %s", (candidate_id,))
        conn.commit()
    run_id = ""
    with as_role("acme__coordinator") as conn:
        run_id = insert_run(conn, outcome.run_row)
        for event in outcome.events:
            insert_event(conn, replace(event, run_id=run_id))
        conn.commit()
    with as_role("promoter") as conn:
        assert insert_fact(conn, outcome.fact_rows[0])
        conn.commit()

    assert _read_run(run_id) == (
        "acme",
        seed,
        f"model-test-{seed}",
        "r" * 40,
        "c" * 40,
        "f" * 64,
        "d" * 64,
        7,
        11,
        2.5,
        "succeeded",
    )
    with as_role("acme__reader") as conn:
        rows = conn.execute(
            "SELECT actor, action FROM event WHERE run_id = %s",
            (run_id,),
        ).fetchall()
        # Thứ tự gọi vai đã khẳng định ở test đơn vị trên outcome trong bộ
        # nhớ; ở DB chỉ khẳng định đủ bốn event (event_id là uuid ngẫu
        # nhiên, occurred_at cùng một transaction nên không sắp theo đó).
        assert {(row[0], row[1]) for row in rows} == {
            ("generator", "replay"),
            ("reflector", "reflect"),
            ("curator", "curate"),
            ("governor", "decide"),
        }
        row = one(
            conn,
            "SELECT canonical_key, tenant_id, scope FROM fact WHERE candidate_id = %s",
            (candidate_id,),
        )
    assert row == (f"response(A-{suffix}, B-{suffix})", "global", "global")
