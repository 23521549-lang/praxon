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
from uuid import UUID

import pytest

from praxon_core.adapters.cache import ResponseCache
from praxon_core.adapters.local_store import LocalCheckpointStore
from praxon_core.learning.candidate import DecisionVerdict, FactStatus
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
    RoundOutcome,
    check_test_split_lock,
    compute_config_hash,
    compute_config_hash_without_budget,
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
        id=UUID(EPISODE_ID),
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


def test_config_hash_khong_doi_khi_doi_s3_hay_xoay_khoa_s3():
    # Task 10.3: đổi nơi lưu checkpoint hay xoay khóa S3 không đổi kết quả
    # nên không đổi hash — giống database_url và openai_api_key.
    base = compute_config_hash(Settings(database_url="postgresql://localhost:5432/praxon"))
    changed = compute_config_hash(
        Settings(
            database_url="postgresql://localhost:5432/praxon",
            s3_endpoint_url="https://s3.us-west-004.backblazeb2.com",
            s3_bucket="praxon-checkpoints",
            s3_access_key_id="key-id-moi",
            s3_secret_access_key="khoa-bi-mat-moi",
        )
    )
    assert base == changed


def test_config_hash_doi_khi_doi_nhip_checkpoint():
    # Task 10.3: nhịp checkpoint đổi thì cách chia lô đổi theo, nên hash đổi.
    base = compute_config_hash(Settings(database_url="postgresql://localhost:5432/praxon"))
    changed = compute_config_hash(
        Settings(
            database_url="postgresql://localhost:5432/praxon",
            checkpoint_every_n_cases=25,
        )
    )
    assert base != changed


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


def test_run_learning_round_scope_ten_tenant_thi_anh_xa_ve_tenant():
    # Hành vi cũ (raise ValueError vì scope "acme" chưa có ánh xạ) đã bị
    # thay bằng map ở `to_candidate` (target_scope: "acme" -> "tenant",
    # theo đề xuất target_scope đã duyệt): vòng học chạy thông, fact row
    # mang scope 'tenant' + tenant_id của vòng. Nhánh `else` của
    # coordinator giữ nguyên làm lưới an toàn phòng thủ.
    outcome = run_learning_round(
        _round(),
        reflect=_reflector([_insight("response", "A", "B", "acme")]),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert outcome.run_row.status == "succeeded"
    assert len(outcome.fact_rows) == 1
    fact_row = outcome.fact_rows[0]
    assert fact_row.scope == "tenant"
    assert fact_row.tenant_id == "acme"


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


# --- Checkpoint (task 10.3) ---

FOUR_CASES = (
    ("c1", ("A", "B")),
    ("c2", ("C", "D")),
    ("c3", ("E", "F")),
    ("c4", ("G", "H")),
)


def _prefix() -> str:
    return checkpoint_prefix(
        tenant_id="acme", seed=SEED, config_hash=CONFIG_HASH, data_hash=DATA_HASH
    )


def _round_cases(
    cases: tuple[tuple[str, tuple[str, ...]], ...] = FOUR_CASES,
    *,
    checkpoint_every_n_cases: int = 0,
    checkpoint_store: CheckpointStore | None = None,
    resume_from: Checkpoint | None = None,
    cache: ResponseCache | None = None,
    token_budget_total: int = 0,
    token_budget_reserve_per_call: int = 2048,
    reflector_batch_size: int = 10,
    config_hash_no_budget: str = "",
) -> LearningRound:
    rows = []
    for index, (case_id, activities) in enumerate(cases):
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
        token_budget_total=token_budget_total,
        token_budget_reserve_per_call=token_budget_reserve_per_call,
        reflector_batch_size=reflector_batch_size,
        config_hash_no_budget=config_hash_no_budget,
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
                _insight(
                    "response",
                    trajectory.activities[0],
                    trajectory.activities[1],
                    "global",
                )
            )
            tokens_in += 1
            tokens_out += 2
        return ReflectorResult(
            insights=tuple(insights), tokens_in=tokens_in, tokens_out=tokens_out
        )

    return reflect


def _assert_same_outcome_without_events(first: RoundOutcome, second: RoundOutcome) -> None:
    # Events khác nhau theo cách chia lô (một event generator/reflector mỗi
    # lô) nên so từng phần còn lại, không so cả outcome.
    assert first.trajectories == second.trajectories
    assert first.insights == second.insights
    assert first.decisions == second.decisions
    assert first.candidate_ids == second.candidate_ids
    assert first.fact_rows == second.fact_rows
    assert first.fact_closes == second.fact_closes
    assert (first.run_row.tokens_in, first.run_row.tokens_out) == (
        second.run_row.tokens_in,
        second.run_row.tokens_out,
    )
    assert first.run_row.status == second.run_row.status == "succeeded"


def test_run_learning_round_checkpoint_khong_store_thi_tu_choi():
    with pytest.raises(ValueError, match="không có checkpoint_store"):
        run_learning_round(
            _round_cases(checkpoint_every_n_cases=2),
            reflect=_reflect_by_trajectory(),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )


def test_run_learning_round_checkpoint_n_am_thi_tu_choi():
    with pytest.raises(ValueError, match="không được âm"):
        run_learning_round(
            _round_cases(checkpoint_every_n_cases=-1),
            reflect=_reflect_by_trajectory(),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )


def test_run_learning_round_chia_lo_ghi_checkpoint(tmp_path):
    store = LocalCheckpointStore(tmp_path / "ckp")
    outcome = run_learning_round(
        _round_cases(checkpoint_every_n_cases=2, checkpoint_store=store),
        reflect=_reflect_by_trajectory(),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert [t.case_id for t in outcome.trajectories] == ["c1", "c2", "c3", "c4"]
    assert len(outcome.decisions) == 4
    assert outcome.candidate_ids == ("candidate-0", "candidate-1", "candidate-2", "candidate-3")
    assert [row.canonical_key for row in outcome.fact_rows] == [
        "response(A, B)",
        "response(C, D)",
        "response(E, F)",
        "response(G, H)",
    ]
    assert (outcome.run_row.tokens_in, outcome.run_row.tokens_out) == (4, 8)
    # Hai checkpoint đã ghi, đúng ranh giới lô; checkpoint giữ đủ trạng thái.
    prefix = _prefix()
    assert store.list_keys(prefix) == [prefix + "/000002.json", prefix + "/000004.json"]
    latest = read_latest_checkpoint(store, prefix)
    assert latest is not None
    assert latest.cases_done == ("c1", "c2", "c3", "c4")
    assert latest.decisions == outcome.decisions
    assert latest.candidate_ids == outcome.candidate_ids
    assert latest.fact_rows == outcome.fact_rows
    # Chia lô không đổi kết quả so với chạy liền mạch.
    reference = run_learning_round(
        _round_cases(),
        reflect=_reflect_by_trajectory(),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    _assert_same_outcome_without_events(outcome, reference)


def test_run_learning_round_resume_chay_tiep_tu_con_tro(tmp_path):
    store = LocalCheckpointStore(tmp_path / "ckp")
    prefix = _prefix()
    shared_ids = _candidate_ids()
    seen: list[str] = []
    with pytest.raises(RuntimeError, match="đứt giữa chừng"):
        run_learning_round(
            _round_cases(checkpoint_every_n_cases=2, checkpoint_store=store),
            reflect=_reflect_by_trajectory(fail_on=("c3",), seen=seen),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=shared_ids,
        )
    # Lô 1 đã ghi checkpoint; lô 2 đứt nên chưa có checkpoint 000004.
    assert seen == ["c1", "c2", "c3", "c4"]
    assert store.list_keys(prefix) == [prefix + "/000002.json"]
    latest = read_latest_checkpoint(store, prefix)
    assert latest is not None
    assert latest.cases_done == ("c1", "c2")

    # Chạy tiếp từ checkpoint: reflector chỉ thấy c3, c4; id candidate nối tiếp.
    seen.clear()
    resumed = run_learning_round(
        _round_cases(
            checkpoint_every_n_cases=2,
            checkpoint_store=store,
            resume_from=latest,
        ),
        reflect=_reflect_by_trajectory(seen=seen),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=shared_ids,
    )
    assert seen == ["c3", "c4"]
    assert store.list_keys(prefix) == [prefix + "/000002.json", prefix + "/000004.json"]
    reference = run_learning_round(
        _round_cases(),
        reflect=_reflect_by_trajectory(),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    _assert_same_outcome_without_events(resumed, reference)


def _checkpoint_for_resume(**overrides: object) -> Checkpoint:
    checkpoint = Checkpoint(
        tenant_id="acme",
        seed=SEED,
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION,
        config_hash=CONFIG_HASH,
        data_hash=DATA_HASH,
        cases_done=("c1", "c2"),
    )
    return checkpoint.model_copy(update=overrides)


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", "globex"),
        ("seed", 43),
        ("model_id", "mo-hinh-khac"),
        ("model_revision", "0" * 40),
        ("config_hash", "0" * 64),
        ("data_hash", "0" * 64),
    ],
)
def test_run_learning_round_resume_sai_vong_thi_tu_choi(field, value):
    with pytest.raises(ValueError, match="không thuộc về vòng này"):
        run_learning_round(
            _round_cases(resume_from=_checkpoint_for_resume(**{field: value})),
            reflect=_reflect_by_trajectory(),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )


@pytest.mark.parametrize(
    "cases_done",
    [
        ("c2", "c1"),
        ("c1", "c3"),
        ("c9",),
    ],
)
def test_run_learning_round_resume_con_tro_sai_thi_tu_choi(cases_done):
    with pytest.raises(ValueError, match="con trỏ case"):
        run_learning_round(
            _round_cases(resume_from=_checkpoint_for_resume(cases_done=cases_done)),
            reflect=_reflect_by_trajectory(),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )


def test_run_learning_round_resume_da_xong_het_thi_khong_chay_lai(tmp_path):
    store = LocalCheckpointStore(tmp_path / "ckp")
    outcome = run_learning_round(
        _round_cases(checkpoint_every_n_cases=2, checkpoint_store=store),
        reflect=_reflect_by_trajectory(),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    latest = read_latest_checkpoint(store, _prefix())
    assert latest is not None
    assert latest.cases_done == ("c1", "c2", "c3", "c4")
    calls = []

    def reflect(
        trajectories: Sequence[Trajectory], facts: Sequence[FactRead]
    ) -> ReflectorResult:
        calls.append(True)
        return ReflectorResult(insights=())

    resumed = run_learning_round(
        _round_cases(resume_from=latest),
        reflect=reflect,
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert calls == []
    assert resumed.trajectories == outcome.trajectories
    assert resumed.decisions == outcome.decisions
    assert resumed.fact_rows == outcome.fact_rows


def test_run_learning_round_resume_nap_lai_cache(tmp_path):
    store = LocalCheckpointStore(tmp_path / "ckp")
    cache = ResponseCache()
    model = _CountingModel()
    # Lần 1: đứt ở lô 2 sau khi lô 1 đã ghi checkpoint kèm mục đệm.
    with pytest.raises(RuntimeError, match="đứt giữa chừng"):
        run_learning_round(
            _round_cases(checkpoint_every_n_cases=2, checkpoint_store=store, cache=cache),
            reflect=_reflect_by_trajectory(cache=cache, model=model, fail_on=("c3",)),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )
    assert model.calls == 2
    latest = read_latest_checkpoint(store, _prefix())
    assert latest is not None
    assert len(latest.cache_entries) == 2

    # Lần 2: cache mới toanh; chạy tiếp nạp lại mục đệm, mô hình chỉ gọi cho c3, c4.
    fresh_cache = ResponseCache()
    resumed = run_learning_round(
        _round_cases(
            checkpoint_every_n_cases=2,
            checkpoint_store=store,
            resume_from=latest,
            cache=fresh_cache,
        ),
        reflect=_reflect_by_trajectory(cache=fresh_cache, model=model),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert model.calls == 4
    assert len(fresh_cache) == 4
    assert len(resumed.fact_rows) == 4
    # Mục đệm đã nạp dùng được ngay, không gọi lại mô hình.
    assert (
        fresh_cache.get_or_call(
            "reflect:c1",
            model_revision=MODEL_REVISION,
            decode_params={},
            json_schema={},
            call=model,
        )
        == "phan-hoi"
    )
    assert model.calls == 4


# --- Trần token (task 10.4) ---


def _reflector_khong_usage(calls: list[str]) -> ReflectorFn:
    """Reflector giả mô phỏng server không trả `usage`: 0 token mọi lô."""

    def reflect(
        trajectories: Sequence[Trajectory], facts: Sequence[FactRead]
    ) -> ReflectorResult:
        calls.extend(t.case_id for t in trajectories)
        return ReflectorResult(insights=(), tokens_in=0, tokens_out=0)

    return reflect


def test_budget_du_cho_lo_1_khong_du_cho_lo_2(tmp_path):
    # Trần 15, dự trữ 10/lần gọi: lô 1 qua (0 + 10 <= 15), lô 2 chạm
    # (6 + 10 > 15) — không lệnh gọi nào của lô 2 được phát ra.
    store = LocalCheckpointStore(tmp_path / "ckp")
    seen: list[str] = []
    with pytest.raises(BudgetExceededError) as exc_info:
        run_learning_round(
            _round_cases(
                checkpoint_every_n_cases=2,
                checkpoint_store=store,
                token_budget_total=15,
                token_budget_reserve_per_call=10,
            ),
            reflect=_reflect_by_trajectory(seen=seen),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )
    error = exc_info.value
    outcome = error.outcome
    assert outcome.run_row.status == "budget_exceeded"
    assert (outcome.run_row.tokens_in, outcome.run_row.tokens_out) == (2, 4)
    # Reflector chỉ thấy lô 1; partial outcome chỉ tới hết lô 1.
    assert seen == ["c1", "c2"]
    assert len(outcome.decisions) == 2
    assert [row.canonical_key for row in outcome.fact_rows] == [
        "response(A, B)",
        "response(C, D)",
    ]
    # Checkpoint ở ranh giới lô đã xong (2 case), event budget_exceeded kèm theo.
    prefix = _prefix()
    assert store.list_keys(prefix) == [prefix + "/000002.json"]
    assert error.checkpoint_key == prefix + "/000002.json"
    latest = read_latest_checkpoint(store, prefix)
    assert latest is not None
    assert latest.cases_done == ("c1", "c2")
    assert latest.tokens_in == 2
    budget_events = [e for e in outcome.events if e.action == "budget_exceeded"]
    assert len(budget_events) == 1
    assert budget_events[0].actor == "coordinator"
    assert "15" in (budget_events[0].reason or "")
    assert "000002.json" in (budget_events[0].reason or "")


def test_budget_ranh_gioi_bang_tran_thi_qua(tmp_path):
    # Đã dùng + dự trữ == trần thì qua (chỉ > trần mới chạm).
    outcome = run_learning_round(
        _round_cases(
            checkpoint_every_n_cases=2,
            checkpoint_store=LocalCheckpointStore(tmp_path / "ckp"),
            token_budget_total=16,
            token_budget_reserve_per_call=10,
        ),
        reflect=_reflect_by_trajectory(),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert outcome.run_row.status == "succeeded"
    assert (outcome.run_row.tokens_in, outcome.run_row.tokens_out) == (4, 8)


def test_budget_0_mac_dinh_chay_het(tmp_path):
    store = LocalCheckpointStore(tmp_path / "ckp")
    outcome = run_learning_round(
        _round_cases(checkpoint_every_n_cases=2, checkpoint_store=store),
        reflect=_reflect_by_trajectory(),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert outcome.run_row.status == "succeeded"
    assert (outcome.run_row.tokens_in, outcome.run_row.tokens_out) == (4, 8)


def test_budget_nho_hon_du_tru_lo_dau_cham_ngay(tmp_path):
    # Trần 5 < dự trữ 10 của lô đầu: chạm ngay với 0 token đã dùng.
    store = LocalCheckpointStore(tmp_path / "ckp")
    seen: list[str] = []
    with pytest.raises(BudgetExceededError) as exc_info:
        run_learning_round(
            _round_cases(
                checkpoint_every_n_cases=2,
                checkpoint_store=store,
                token_budget_total=5,
                token_budget_reserve_per_call=10,
            ),
            reflect=_reflect_by_trajectory(seen=seen),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )
    error = exc_info.value
    assert error.outcome.run_row.status == "budget_exceeded"
    assert (error.outcome.run_row.tokens_in, error.outcome.run_row.tokens_out) == (0, 0)
    assert seen == []
    prefix = _prefix()
    assert error.checkpoint_key == prefix + "/000000.json"
    latest = read_latest_checkpoint(store, prefix)
    assert latest is not None
    assert latest.cases_done == ()


def test_usage_none_tinh_phi_bang_du_tru(tmp_path):
    # Server không trả usage: lô báo 0 token thì tính phí bằng dự trữ
    # mỗi lần gọi (R2) — trần vẫn chạm đúng lúc.
    store = LocalCheckpointStore(tmp_path / "ckp")
    calls: list[str] = []
    with pytest.raises(BudgetExceededError) as exc_info:
        run_learning_round(
            _round_cases(
                checkpoint_every_n_cases=2,
                checkpoint_store=store,
                token_budget_total=15,
                token_budget_reserve_per_call=10,
            ),
            reflect=_reflector_khong_usage(calls),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )
    error = exc_info.value
    # Lô 1: 0 token báo về → tính phí 1 lần gọi nhân 10 = 10; lô 2:
    # 10 + 10 > 15 nên chạm. Reflector chỉ gọi đúng 1 lần (lô 1).
    assert (error.outcome.run_row.tokens_in, error.outcome.run_row.tokens_out) == (10, 0)
    assert calls == ["c1", "c2"]


def test_cache_am_khong_goi_moi_nhung_van_tinh_du_tru(tmp_path):
    # Cache ấm: không phát ra lệnh gọi mới, nhưng điểm kiểm vẫn tính dự
    # trữ như thể sẽ gọi (bảo thủ — dừng sớm hơn chứ không bao giờ vượt).
    store = LocalCheckpointStore(tmp_path / "ckp")
    cache = ResponseCache()
    model = _CountingModel()
    for case_id in ("c1", "c2", "c3", "c4"):
        cache.get_or_call(
            f"reflect:{case_id}",
            model_revision=MODEL_REVISION,
            decode_params={},
            json_schema={},
            call=model,
        )
    assert model.calls == 4
    with pytest.raises(BudgetExceededError):
        run_learning_round(
            _round_cases(
                checkpoint_every_n_cases=2,
                checkpoint_store=store,
                cache=cache,
                token_budget_total=15,
                token_budget_reserve_per_call=10,
            ),
            reflect=_reflect_by_trajectory(cache=cache, model=model),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )
    assert model.calls == 4


@pytest.mark.parametrize(
    "overrides",
    [
        {"token_budget_total": -1},
        {"token_budget_reserve_per_call": -1},
        {"token_budget_total": 10, "token_budget_reserve_per_call": 0},
        {"token_budget_total": 10, "reflector_batch_size": 0},
        {"token_budget_total": 10, "checkpoint_every_n_cases": 0},
        {
            "token_budget_total": 10,
            "checkpoint_every_n_cases": 2,
            "checkpoint_store": None,
        },
    ],
)
def test_budget_validation_dau_vong_tu_choi_truoc_khi_chay(overrides):
    seen: list[str] = []
    with pytest.raises(ValueError):
        run_learning_round(
            _round_cases(**overrides),
            reflect=_reflect_by_trajectory(seen=seen),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )
    assert seen == []


def test_config_hash_doi_khi_doi_tran_nhung_hash_tru_tran_khong_doi():
    settings = Settings(database_url="postgresql://localhost/praxon")
    nang_tran = settings.model_copy(update={"token_budget_total": 5000})
    assert compute_config_hash(nang_tran) != compute_config_hash(settings)
    assert compute_config_hash_without_budget(nang_tran) == compute_config_hash_without_budget(
        settings
    )
    doi_model = settings.model_copy(update={"model_id": "model-khac"})
    assert compute_config_hash_without_budget(doi_model) != compute_config_hash_without_budget(
        settings
    )


def test_resume_nang_tran_cho_phep(tmp_path):
    # Checkpoint ở điểm chạm trần (trần 100, đã dùng 12); vòng mới nâng
    # trần lên 1000 (dự trữ đổi 10 → 20 cũng được phép) thì chạy tiếp.
    store = LocalCheckpointStore(tmp_path / "ckp")
    shared_ids = _candidate_ids()
    seen: list[str] = []
    checkpoint = _checkpoint_for_resume(
        cases_done=("c1", "c2"),
        tokens_in=4,
        tokens_out=8,
        token_budget_total=100,
        token_budget_reserve_per_call=10,
        config_hash_no_budget="n" * 64,
    )
    resumed = run_learning_round(
        _round_cases(
            checkpoint_every_n_cases=2,
            checkpoint_store=store,
            resume_from=checkpoint,
            token_budget_total=1000,
            token_budget_reserve_per_call=20,
            config_hash_no_budget="n" * 64,
        ),
        reflect=_reflect_by_trajectory(seen=seen),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=shared_ids,
    )
    assert seen == ["c3", "c4"]
    assert resumed.run_row.status == "succeeded"
    assert (resumed.run_row.tokens_in, resumed.run_row.tokens_out) == (6, 12)


def test_resume_giu_nguyen_tran_khi_da_dung_het_thi_tu_choi(tmp_path):
    # Trần giữ nguyên 12 mà đã dùng đúng 12 token: trần mới không > đã
    # dùng nên cổng resume từ chối ngay, trước khi gọi mô hình.
    checkpoint = _checkpoint_for_resume(
        cases_done=("c1", "c2"),
        tokens_in=4,
        tokens_out=8,
        token_budget_total=12,
        token_budget_reserve_per_call=10,
        config_hash_no_budget="n" * 64,
    )
    seen: list[str] = []
    with pytest.raises(ValueError, match="không thuộc về vòng này"):
        run_learning_round(
            _round_cases(
                checkpoint_every_n_cases=2,
                checkpoint_store=LocalCheckpointStore(tmp_path / "ckp"),
                resume_from=checkpoint,
                token_budget_total=12,
                token_budget_reserve_per_call=10,
                config_hash_no_budget="n" * 64,
            ),
            reflect=_reflect_by_trajectory(seen=seen),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )
    assert seen == []


def test_resume_doi_seed_du_nang_tran_van_tu_choi(tmp_path):
    checkpoint = _checkpoint_for_resume(
        seed=43,
        cases_done=("c1", "c2"),
        tokens_in=4,
        tokens_out=8,
        token_budget_total=100,
        token_budget_reserve_per_call=10,
        config_hash_no_budget="n" * 64,
    )
    with pytest.raises(ValueError, match="không thuộc về vòng này"):
        run_learning_round(
            _round_cases(
                checkpoint_every_n_cases=2,
                checkpoint_store=LocalCheckpointStore(tmp_path / "ckp"),
                resume_from=checkpoint,
                token_budget_total=1000,
                token_budget_reserve_per_call=10,
                config_hash_no_budget="n" * 64,
            ),
            reflect=_reflect_by_trajectory(),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )


def test_resume_checkpoint_cu_thieu_hash_tru_tran_voi_tran_khac_thi_tu_choi(tmp_path):
    # Checkpoint viết trước 10.4 (thiếu config_hash_no_budget): luật
    # nghiêm ngặt cũ — hash toàn phần khác thì từ chối dù trần mới cao hơn.
    checkpoint = _checkpoint_for_resume(
        config_hash="0" * 64,
        cases_done=("c1", "c2"),
        tokens_in=4,
        tokens_out=8,
        token_budget_total=1000,
        token_budget_reserve_per_call=10,
    )
    with pytest.raises(ValueError, match="không thuộc về vòng này"):
        run_learning_round(
            _round_cases(
                checkpoint_every_n_cases=2,
                checkpoint_store=LocalCheckpointStore(tmp_path / "ckp"),
                resume_from=checkpoint,
                token_budget_total=1000,
                token_budget_reserve_per_call=10,
                config_hash_no_budget="n" * 64,
            ),
            reflect=_reflect_by_trajectory(),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )
