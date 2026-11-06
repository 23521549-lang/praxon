"""Test bộ điều phối (plan con 10, task 10.1).

Khẳng định cổng ra của task: (a) mỗi vai vẫn là hàm thuần — cả vòng học
chạy trong bộ nhớ, không DB, không mô hình (Reflector giả tiêm vào),
chạy lại ra đúng kết quả cũ; (b) `run` có đủ sáu trường điều kiện tái lập.
"""

from __future__ import annotations

import hashlib
import itertools
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from praxon_core.learning.candidate import DecisionVerdict, FactStatus
from praxon_core.learning.coordinator import (
    LearningRound,
    ReflectorFn,
    ReflectorResult,
    check_test_split_lock,
    compute_config_hash,
    is_reproducible,
    merge_data_hash,
    reproducibility_gaps,
    run_learning_round,
)
from praxon_core.learning.curator import FactRead, Insight, InsightSource
from praxon_core.learning.generator import EpisodeRow, Trajectory
from praxon_core.learning.measures import Measures
from praxon_core.learning.rules import RuleTable, default_rule_table, load_rule_table
from praxon_core.repositories.runs import RunRow
from praxon_core.settings import Settings

VALID_START = datetime(2030, 1, 1, tzinfo=UTC)
RETIRED_AT = datetime(2030, 2, 1, tzinfo=UTC)
EPISODE_ID = "22222222-2222-2222-2222-222222222222"
FACT_ID = "33333333-3333-3333-3333-333333333333"
SEED = 42
MODEL_ID = "Qwen/Qwen3-8B-GGUF"
MODEL_REVISION = "7c41481f57cb95916b40956ab2f0b139b296d974"
CODE_COMMIT = "d8f9e2a0000000000000000000000000000000000"
CONFIG_HASH = "c" * 64
DATA_HASH = "d" * 64


def _dt(text: str) -> datetime:
    return datetime.fromisoformat(text)


def _episode(case_id: str, activity: str, occurred: str) -> EpisodeRow:
    return EpisodeRow(
        tenant_id="acme",
        case_id=case_id,
        payload={"activity": activity, "case_attributes": {}},
        occurred_at=_dt(occurred),
        ingested_at=_dt("2026-11-06T00:00:00"),
    )


def _measures(**overrides: object) -> Measures:
    data: dict[str, Any] = {
        "has_direct_conflict": False,
        "schema_valid": True,
        "from_trace": True,
        "wilson_lower": 0.8,
        "beta_prob": 0.5,
        "is_scope_promotion": False,
        "from_global": False,
        "has_condition": False,
        "matching_cases": 0,
        "fact_status": None,
        "is_new": True,
        "human_early_activate": False,
        "has_rubric_clause": False,
    }
    data.update(overrides)
    return Measures(**data)


def _insight(template: str, activation: str, target: str, scope: str) -> Insight:
    return Insight(
        template=template,
        activation=activation,
        target=target,
        condition=None,
        evidence_episode_ids=[EPISODE_ID],
        source=InsightSource.TRACE,
        scope=scope,
    )


def _fact(canonical_key: str, template: str, status: FactStatus, scope: str) -> FactRead:
    return FactRead(
        id=FACT_ID,
        scope=scope,
        canonical_key=canonical_key,
        template=template,
        activation="A",
        target="B",
        condition=None,
        status=status,
    )


def _reflector(insights: list[Insight], tokens_in: int = 0, tokens_out: int = 0) -> ReflectorFn:
    def reflect(
        trajectories: Sequence[Trajectory], facts: Sequence[FactRead]
    ) -> ReflectorResult:
        return ReflectorResult(
            insights=tuple(insights), tokens_in=tokens_in, tokens_out=tokens_out
        )

    return reflect


def _candidate_ids() -> Callable[[], str]:
    counter = itertools.count()
    return lambda: f"candidate-{next(counter)}"


def _round(
    *,
    facts: tuple[FactRead, ...] = (),
    rule_table: RuleTable | None = None,
    config_hash: str = CONFIG_HASH,
    locked_config_hash: str | None = None,
    on_test_split: bool = False,
) -> LearningRound:
    return LearningRound(
        tenant_id="acme",
        episode_rows=(
            _episode("c1", "A", "2026-11-06T10:00:00"),
            _episode("c1", "B", "2026-11-06T11:00:00"),
        ),
        facts=facts,
        rule_table=rule_table or default_rule_table(),
        seed=SEED,
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION,
        code_commit=CODE_COMMIT,
        config_hash=config_hash,
        data_hash=DATA_HASH,
        valid_start=VALID_START,
        retired_at=RETIRED_AT,
        wall_time=1.5,
        locked_config_hash=locked_config_hash,
        on_test_split=on_test_split,
    )


def _run_row(**overrides: object) -> RunRow:
    data: dict[str, Any] = {
        "tenant_id": "acme",
        "seed": SEED,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "code_commit": CODE_COMMIT,
        "config_hash": CONFIG_HASH,
        "data_hash": DATA_HASH,
    }
    data.update(overrides)
    return RunRow(**data)


def _repro_args(**overrides: object) -> dict[str, Any]:
    args: dict[str, Any] = {
        "seed": SEED,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "code_commit": CODE_COMMIT,
        "config_hash": CONFIG_HASH,
        "data_hash": DATA_HASH,
        "cache_intact": True,
    }
    args.update(overrides)
    return args


def test_config_hash_giong_nhau_voi_cung_cau_hinh():
    settings = Settings(database_url="postgresql://localhost:5432/praxon")
    assert compute_config_hash(settings) == compute_config_hash(settings)


def test_config_hash_doi_khi_doi_model_id():
    base = Settings(database_url="postgresql://localhost:5432/praxon")
    changed = Settings(
        database_url="postgresql://localhost:5432/praxon",
        model_id="mo-hinh-khac",
    )
    assert compute_config_hash(base) != compute_config_hash(changed)


def test_config_hash_khong_doi_khi_doi_db_hay_khoa():
    base = compute_config_hash(Settings(database_url="postgresql://localhost:5432/praxon"))
    changed = compute_config_hash(
        Settings(
            database_url="postgresql://khac@localhost:5432/khac",
            openai_api_key="khoa-moi",
        )
    )
    assert base == changed


def test_merge_data_hash_hai_nua_theo_thu_tu_co_dinh():
    bpic = "a" * 64
    generator = "b" * 64
    expected = hashlib.sha256((bpic + generator).encode("utf-8")).hexdigest()
    assert merge_data_hash(bpic_hash=bpic, generator_hash=generator) == expected


def test_merge_data_hash_mot_nua_bam_rieng_khac_nua_goc():
    bpic = "a" * 64
    merged = merge_data_hash(bpic_hash=bpic)
    assert merged == hashlib.sha256(bpic.encode("utf-8")).hexdigest()
    assert merged != bpic


def test_merge_data_hash_doi_thu_tu_doi_ket_qua():
    first = merge_data_hash(bpic_hash="a" * 64, generator_hash="b" * 64)
    swapped = merge_data_hash(bpic_hash="b" * 64, generator_hash="a" * 64)
    assert first != swapped


def test_merge_data_hash_khong_co_nua_nao_thi_tu_choi():
    with pytest.raises(ValueError, match="ít nhất một nửa"):
        merge_data_hash()


def test_reproducibility_gaps_rong_khi_khop_du_sau_dieu_kien():
    record = _run_row()
    assert reproducibility_gaps(record, **_repro_args()) == ()
    assert is_reproducible(record, **_repro_args())


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("seed", 43, ("seed",)),
        ("model_id", "mo-hinh-khac", ("model",)),
        ("model_revision", "0" * 40, ("model",)),
        ("code_commit", "0" * 40, ("code_commit",)),
        ("config_hash", "0" * 64, ("config_hash",)),
        ("data_hash", "0" * 64, ("data_hash",)),
        ("cache_intact", False, ("cache",)),
    ],
)
def test_reproducibility_gaps_chi_ro_tung_dieu_kien_lech(field, value, expected):
    record = _run_row()
    args = _repro_args(**{field: value})
    assert reproducibility_gaps(record, **args) == expected
    assert not is_reproducible(record, **args)


def test_check_test_split_lock_chua_khoa_thi_cho_chay():
    check_test_split_lock(config_hash=CONFIG_HASH, locked_config_hash=None)


def test_check_test_split_lock_khop_khoa_thi_cho_chay():
    check_test_split_lock(config_hash=CONFIG_HASH, locked_config_hash=CONFIG_HASH)


def test_check_test_split_lock_khac_khoa_thi_tu_choi():
    with pytest.raises(ValueError, match="không được chạy trên phần đo"):
        check_test_split_lock(config_hash=CONFIG_HASH, locked_config_hash="0" * 64)


def test_run_learning_round_add_toan_cuc():
    outcome = run_learning_round(
        _round(),
        reflect=_reflector([_insight("response", "A", "B", "global")], 10, 20),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert [t.activities for t in outcome.trajectories] == [("A", "B")]
    assert len(outcome.decisions) == 1
    assert outcome.decisions[0].decision.verdict is DecisionVerdict.AUTO_APPROVE
    assert outcome.decisions[0].decision.rule_id == 2
    assert outcome.candidate_ids == ("candidate-0",)
    assert len(outcome.fact_rows) == 1
    row = outcome.fact_rows[0]
    assert row.canonical_key == "response(A, B)"
    assert row.scope == "global"
    assert row.tenant_id == "global"
    assert row.status == "trial"
    assert row.candidate_id == "candidate-0"
    assert outcome.fact_closes == ()
    assert [event.actor for event in outcome.events] == [
        "generator",
        "reflector",
        "curator",
        "governor",
    ]
    assert all(event.run_id is None for event in outcome.events)
    run = outcome.run_row
    assert (run.seed, run.model_id, run.model_revision) == (
        SEED,
        MODEL_ID,
        MODEL_REVISION,
    )
    assert (run.code_commit, run.config_hash, run.data_hash) == (
        CODE_COMMIT,
        CONFIG_HASH,
        DATA_HASH,
    )
    assert (run.tokens_in, run.tokens_out) == (10, 20)
    assert run.wall_time == 1.5
    assert run.status == "succeeded"


def test_run_learning_round_add_tenant():
    outcome = run_learning_round(
        _round(),
        reflect=_reflector([_insight("response", "A", "B", "tenant")]),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert len(outcome.fact_rows) == 1
    assert outcome.fact_rows[0].scope == "tenant"
    assert outcome.fact_rows[0].tenant_id == "acme"


def test_run_learning_round_chay_lai_ra_dung_ket_qua_cu():
    first = run_learning_round(
        _round(),
        reflect=_reflector([_insight("response", "A", "B", "global")], 10, 20),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    second = run_learning_round(
        _round(),
        reflect=_reflector([_insight("response", "A", "B", "global")], 10, 20),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert first == second


def test_run_learning_round_retire_can_nguoi_duyet():
    outcome = run_learning_round(
        _round(facts=(_fact("response(A, B)", "response", FactStatus.TRIAL, "global"),)),
        reflect=_reflector([_insight("not_response", "A", "B", "global")]),
        measures_for=lambda candidate, delta: _measures(has_direct_conflict=True),
        candidate_id_for=_candidate_ids(),
    )
    assert outcome.decisions[0].decision.verdict is DecisionVerdict.NEEDS_HUMAN
    assert outcome.decisions[0].decision.rule_id == 1
    assert outcome.fact_rows == ()
    assert outcome.fact_closes == ()


def test_run_learning_round_confirm_khong_them_fact():
    outcome = run_learning_round(
        _round(facts=(_fact("response(A, B)", "response", FactStatus.ACTIVE, "global"),)),
        reflect=_reflector([_insight("response", "A", "B", "global")]),
        measures_for=lambda candidate, delta: _measures(
            has_direct_conflict=False, is_new=False
        ),
        candidate_id_for=_candidate_ids(),
    )
    assert outcome.fact_rows == ()
    assert outcome.fact_closes == ()


def _auto_approve_conflict_table(tmp_path: Path) -> RuleTable:
    path = tmp_path / "bang.toml"
    path.write_text(
        """
[policy]
confidence_threshold = 0.7
promote_probability = 0.95
retire_probability = 0.05
prior_strength_default = 4
min_matching_cases = 30

[[rules]]
id = 1
applies_to = "Xung đột trực tiếp (bảng riêng cho test)"
verdict = "auto_approve"
target_status = "trial"
[rules.condition]
kind = "compare"
measure = "has_direct_conflict"
op = "=="
value = true
""",
        encoding="utf-8",
    )
    return load_rule_table(path)


def test_run_learning_round_retire_tu_dong_dong_fact_cu(tmp_path):
    outcome = run_learning_round(
        _round(
            facts=(_fact("response(A, B)", "response", FactStatus.TRIAL, "global"),),
            rule_table=_auto_approve_conflict_table(tmp_path),
        ),
        reflect=_reflector([_insight("not_response", "A", "B", "global")]),
        measures_for=lambda candidate, delta: _measures(has_direct_conflict=True),
        candidate_id_for=_candidate_ids(),
    )
    assert outcome.decisions[0].decision.verdict is DecisionVerdict.AUTO_APPROVE
    assert outcome.fact_rows == ()
    assert len(outcome.fact_closes) == 1
    assert outcome.fact_closes[0].fact_id == FACT_ID
    assert outcome.fact_closes[0].retired_at == RETIRED_AT


def test_run_learning_round_contradict_dong_cu_them_moi(tmp_path):
    outcome = run_learning_round(
        _round(
            facts=(_fact("response(A, B)", "response", FactStatus.ACTIVE, "global"),),
            rule_table=_auto_approve_conflict_table(tmp_path),
        ),
        reflect=_reflector([_insight("not_response", "A", "B", "global")]),
        measures_for=lambda candidate, delta: _measures(has_direct_conflict=True),
        candidate_id_for=_candidate_ids(),
    )
    assert outcome.decisions[0].decision.verdict is DecisionVerdict.AUTO_APPROVE
    assert len(outcome.fact_closes) == 1
    assert outcome.fact_closes[0].fact_id == FACT_ID
    assert len(outcome.fact_rows) == 1
    assert outcome.fact_rows[0].canonical_key == "not_response(A, B)"
    assert outcome.fact_rows[0].candidate_id == "candidate-0"


def test_run_learning_round_scope_ten_tenant_thi_tu_choi():
    with pytest.raises(ValueError, match="chưa có ánh xạ"):
        run_learning_round(
            _round(),
            reflect=_reflector([_insight("response", "A", "B", "acme")]),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )


def test_run_learning_round_khoa_phan_do_tu_choi_truoc_khi_chay():
    calls = []

    def reflect(
        trajectories: Sequence[Trajectory], facts: Sequence[FactRead]
    ) -> ReflectorResult:
        calls.append(True)
        return ReflectorResult(insights=())

    with pytest.raises(ValueError, match="không được chạy trên phần đo"):
        run_learning_round(
            _round(
                config_hash=CONFIG_HASH,
                locked_config_hash="0" * 64,
                on_test_split=True,
            ),
            reflect=reflect,
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )
    assert calls == []


def test_run_learning_round_khoa_phan_do_khop_thi_chay():
    outcome = run_learning_round(
        _round(
            config_hash=CONFIG_HASH,
            locked_config_hash=CONFIG_HASH,
            on_test_split=True,
        ),
        reflect=_reflector([_insight("response", "A", "B", "global")]),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert outcome.run_row.status == "succeeded"
