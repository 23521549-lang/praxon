"""Test driver bảy điều kiện (plan con 11, task 11.2) — test local, không cần Kaggle/GPU.

Khẳng định cổng ra code của task: tập fact bảy điều kiện đúng logic 10.2;
chuyển eval `Fact` <-> `FactRead`; `measures_for` đếm đúng trên trace học;
trần token đúng công thức A.4; bản đồ ghi đúng; luật Wabo nạp đúng; vòng
trong bộ nhớ không ghi `run`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tools.kaggle.driver_11_2 import (
    TenantRoundData,
    _build_entry,
    _mean_f1,
    _metrics_to_dict,
    append_manifest_entry,
    build_measures_for,
    compute_ceiling,
    compute_round_metrics,
    document_facts,
    eval_fact_to_fact_read,
    fact_read_to_eval_fact,
    load_manifest,
    load_synthetic_round_data,
    load_wabo_rules,
    make_candidate_id_for,
    max_reflector_calls,
    run_in_memory_measurement,
    wabo_facts,
)

from praxon_core.declare.miner import Rule
from praxon_core.eval.experiments import (
    CONSENSUS,
    DECLARE_ONLY,
    ISOLATION,
    POOLED,
    VETO,
    VOTING,
    condition_fact_sets,
)
from praxon_core.eval.metrics import Fact, FactScope
from praxon_core.eval.report import SYNTHETIC_SEED, metrics_with_ci
from praxon_core.learning.beta import (
    Prior,
    posterior_prob_ge,
    prior_prob_ge,
    wilson_lower,
)
from praxon_core.learning.calibration import FLAT_PRIOR_CONFIDENCE, count_rule_evidence
from praxon_core.learning.candidate import FactStatus
from praxon_core.learning.curator import (
    DeltaKind,
    FactRead,
    Insight,
    InsightSource,
    curate,
    to_candidate,
)
from praxon_core.learning.rules import default_rule_table


def _tenant() -> TenantRoundData:
    """Một tenant giả nhỏ (60 case: học 36, đo 12) để test nhanh."""
    return load_synthetic_round_data(seed=SYNTHETIC_SEED, n_cases=60)[0]


def _insight(*, template: str, activation: str, target: str, scope: str = "tenant") -> Insight:
    return Insight(
        template=template,
        activation=activation,
        target=target,
        condition=None,
        evidence_episode_ids=[],
        source=InsightSource.TRACE,
        scope=scope,
    )


def test_chuyen_fact_sang_fact_read_dung_e19() -> None:
    fact = Fact(
        canonical_key="response(step_01, step_02)",
        template="response",
        activation="step_01",
        target="step_02",
        status=FactStatus.ACTIVE,
        scope=FactScope.TENANT,
        tenant_id="synthetic-1",
    )
    read = eval_fact_to_fact_read(fact)
    assert read.id == "synthetic-1:response(step_01, step_02)"
    assert read.scope == "tenant"
    assert read.condition is None
    assert read.canonical_key == fact.canonical_key
    assert read.template == "response"
    assert read.activation == "step_01"
    assert read.target == "step_02"
    assert read.status is FactStatus.ACTIVE


def test_chuyen_fact_read_sang_fact_vong_tron() -> None:
    fact = Fact(
        canonical_key="precedence(step_03, step_04)",
        template="precedence",
        activation="step_03",
        target="step_04",
        status=FactStatus.TRIAL,
        scope=FactScope.GLOBAL,
        tenant_id="global",
    )
    assert fact_read_to_eval_fact(eval_fact_to_fact_read(fact)) == fact


def test_tap_fact_tai_lieu_gop_nen_va_wabo_dung_thu_tu() -> None:
    tenant = _tenant()
    sets = condition_fact_sets([tenant.tenant_data])
    base = sets[CONSENSUS][tenant.tenant_id]
    wabo = wabo_facts(
        (
            Rule(template="response", first="A", second="B", support=0.0, confidence=0.0),
            Rule(
                template="precedence",
                first="C",
                second="D",
                support=0.0,
                confidence=0.0,
            ),
        )
    )
    combined = document_facts(base_facts=base, wabo_facts_list=wabo)
    assert len(combined) == len(base) + 2
    assert [fact.canonical_key for fact in combined[: len(base)]] == [
        fact.canonical_key for fact in base
    ]
    # facts_from_rules sắp xếp theo khóa canonical nên Wabo về sau theo
    # thứ tự đó (precedence trước response), không theo thứ tự truyền vào.
    assert combined[-2].canonical_key == "precedence(C, D)"
    assert combined[-1].canonical_key == "response(A, B)"
    assert all(fact.scope == "global" for fact in combined[-2:])


def test_tap_fact_bay_dieu_kien_co_du_sau_tap_tu_10_2() -> None:
    tenants = load_synthetic_round_data(seed=SYNTHETIC_SEED, n_cases=60)
    sets = condition_fact_sets([item.tenant_data for item in tenants])
    assert {DECLARE_ONLY, ISOLATION, POOLED, CONSENSUS, VETO} <= set(sets)
    for item in tenants:
        own = {fact.canonical_key for fact in sets[DECLARE_ONLY][item.tenant_id]}
        isolated = {fact.canonical_key for fact in sets[ISOLATION][item.tenant_id]}
        assert own == isolated
        # POOLED khám phá lại trên trace gộp (có ngưỡng support/confidence)
        # nên KHÔNG phải hợp của các tập riêng — một luật hiếm của riêng
        # một tenant có thể rớt ngưỡng. Tính chất đúng: cùng một tập cho
        # mọi tenant, và không rỗng.
        pooled = {fact.canonical_key for fact in sets[POOLED][item.tenant_id]}
        assert pooled
        assert pooled == {fact.canonical_key for fact in sets[POOLED][tenants[0].tenant_id]}
        # Phân tầng mở rộng tập riêng (own là tiền tố của mỗi điều kiện).
        for condition in (VOTING, CONSENSUS, VETO):
            extended = {fact.canonical_key for fact in sets[condition][item.tenant_id]}
            assert own <= extended


def test_measures_for_dem_dung_tren_trace_hoc_voi_add() -> None:
    tenant = _tenant()
    sets = condition_fact_sets([tenant.tenant_data])
    input_facts = tuple(
        eval_fact_to_fact_read(fact) for fact in sets[DECLARE_ONLY][tenant.tenant_id]
    )
    policy = default_rule_table().policy
    measures_for = build_measures_for(
        train_traces=tenant.tenant_data.train_traces,
        input_facts=input_facts,
        policy=policy,
    )
    insight = _insight(template="response", activation="step_08", target="step_01")
    deltas = curate(insight, list(input_facts))
    assert len(deltas) == 1 and deltas[0].kind is DeltaKind.ADD
    candidate = to_candidate(deltas[0], valid_start=tenant.valid_start)
    measures = measures_for(candidate, deltas[0])
    rule = Rule(
        template="response",
        first="step_08",
        second="step_01",
        support=0.0,
        confidence=0.0,
    )
    evidence = count_rule_evidence(rule, tenant.tenant_data.train_traces)
    assert measures.matching_cases == evidence.trials
    assert measures.is_new is True
    assert measures.fact_status is None
    assert measures.has_direct_conflict is False
    assert measures.from_trace is True
    assert measures.schema_valid is True
    assert measures.has_condition is False
    if evidence.trials == 0:
        assert measures.wilson_lower == 0.0
        assert measures.beta_prob == prior_prob_ge(
            Prior(
                canonical_key=insight.canonical_key,
                confidence=FLAT_PRIOR_CONFIDENCE,
                strength=None,
            ),
            policy.confidence_threshold,
            strength_default=policy.prior_strength_default,
        )
    else:
        assert measures.wilson_lower == wilson_lower(evidence.successes, evidence.trials)
        assert measures.beta_prob == posterior_prob_ge(
            Prior(
                canonical_key=insight.canonical_key,
                confidence=FLAT_PRIOR_CONFIDENCE,
                strength=None,
            ),
            evidence.successes,
            evidence.trials,
            policy.confidence_threshold,
            strength_default=policy.prior_strength_default,
        )


def test_measures_for_confirm_giu_trang_thai_fact() -> None:
    tenant = _tenant()
    sets = condition_fact_sets([tenant.tenant_data])
    input_facts = tuple(
        eval_fact_to_fact_read(fact) for fact in sets[DECLARE_ONLY][tenant.tenant_id]
    )
    policy = default_rule_table().policy
    measures_for = build_measures_for(
        train_traces=tenant.tenant_data.train_traces,
        input_facts=input_facts,
        policy=policy,
    )
    # synthetic-1 hoán đổi step_01/step_02 nên tập riêng của nó có
    # response(step_02, step_01) (không có response(step_01, step_02)).
    insight = _insight(template="response", activation="step_02", target="step_01")
    deltas = curate(insight, list(input_facts))
    confirm = [delta for delta in deltas if delta.kind is DeltaKind.CONFIRM]
    assert confirm, "response(step_02,step_01) phải đã có trong tập chỉ-Declare"
    candidate = to_candidate(confirm[0], valid_start=tenant.valid_start)
    measures = measures_for(candidate, confirm[0])
    assert measures.is_new is False
    assert measures.fact_status is FactStatus.ACTIVE
    assert measures.has_direct_conflict is False
    assert measures.matching_cases > 0


def test_measures_for_contradict_bao_xung_dot_truc_tiep() -> None:
    tenant = _tenant()
    sets = condition_fact_sets([tenant.tenant_data])
    input_facts = tuple(
        eval_fact_to_fact_read(fact) for fact in sets[DECLARE_ONLY][tenant.tenant_id]
    )
    policy = default_rule_table().policy
    measures_for = build_measures_for(
        train_traces=tenant.tenant_data.train_traces,
        input_facts=input_facts,
        policy=policy,
    )
    # CONTRADICT sinh khi insight đối nghịch trực tiếp với một fact đang
    # active: mẫu đối nghịch của response là not_response. Reflector chỉ
    # sinh tầng 1 nên insight ở đây vẫn là response (đếm được bằng chứng
    # bằng count_rule_evidence); fact not_response là trạng thái giả đặt
    # thêm vào tập đầu vào để curate sinh CONTRADICT — trong luồng thật
    # 11.2 đường này không tới được (không có fact not_response nào).
    opposite_fact = FactRead(
        id=f"{tenant.tenant_id}:not_response(step_02, step_01)",
        scope="tenant",
        canonical_key="not_response(step_02, step_01)",
        template="not_response",
        activation="step_02",
        target="step_01",
        condition=None,
        status=FactStatus.ACTIVE,
    )
    insight = _insight(template="response", activation="step_02", target="step_01")
    deltas = curate(insight, [*input_facts, opposite_fact])
    contradict = [delta for delta in deltas if delta.kind is DeltaKind.CONTRADICT]
    assert contradict, "phải có delta CONTRADICT với fact not_response đang active"
    candidate = to_candidate(contradict[0], valid_start=tenant.valid_start)
    measures = measures_for(candidate, contradict[0])
    assert measures.has_direct_conflict is True
    assert measures.fact_status is FactStatus.ACTIVE


def test_tran_token_theo_cong_thuc_a4() -> None:
    assert max_reflector_calls(n_trajectories=180, batch_size=10) == 18
    assert max_reflector_calls(n_trajectories=181, batch_size=10) == 19
    assert max_reflector_calls(n_trajectories=0, batch_size=10) == 0
    assert (
        compute_ceiling(n_trajectories=180, batch_size=10, max_cost_per_call=2048)
        == 18 * 2048 * 3 // 2
    )
    assert (
        compute_ceiling(n_trajectories=180, batch_size=10, max_cost_per_call=100, factor=2.0)
        == 18 * 100 * 2
    )
    with pytest.raises(ValueError):
        max_reflector_calls(n_trajectories=10, batch_size=0)
    with pytest.raises(ValueError):
        compute_ceiling(n_trajectories=10, batch_size=10, max_cost_per_call=0)


def test_bo_dem_candidate_tu_0_moi_vong() -> None:
    make_id = make_candidate_id_for()
    assert make_id() == "candidate-0"
    assert make_id() == "candidate-1"
    assert make_candidate_id_for()() == "candidate-0"


def test_f1_trung_binh_theo_dieu_kien() -> None:
    entries = [
        {
            "condition": CONSENSUS,
            "metrics": {"precision": {"value": 1.0}, "recall": {"value": 1.0}},
        },
        {
            "condition": CONSENSUS,
            "metrics": {"precision": {"value": 0.5}, "recall": {"value": 0.5}},
        },
        {
            "condition": VETO,
            "metrics": {"precision": {"value": 0.0}, "recall": {"value": 0.0}},
        },
    ]
    assert _mean_f1(entries, CONSENSUS) == pytest.approx(0.75)
    assert _mean_f1(entries, VETO) == 0.0
    assert _mean_f1([], CONSENSUS) == 0.0


def test_nap_luat_wabo(tmp_path: Path) -> None:
    path = tmp_path / "wabo.json"
    path.write_text(
        json.dumps(
            [
                {"template": "response", "activation": "A", "target": "B"},
                {"template": "precedence", "activation": "C", "target": "D"},
            ]
        ),
        encoding="utf-8",
    )
    rules = load_wabo_rules(path)
    assert len(rules) == 2
    assert rules[0].template == "response" and rules[0].first == "A"
    assert rules[1].template == "precedence" and rules[1].second == "D"
    empty = tmp_path / "rong.json"
    empty.write_text("[]", encoding="utf-8")
    assert load_wabo_rules(empty) == ()
    with pytest.raises(FileNotFoundError):
        load_wabo_rules(tmp_path / "khong-co.json")
    bad = tmp_path / "sai.json"
    bad.write_text(
        json.dumps([{"template": "not_follows", "activation": "A", "target": "B"}]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_wabo_rules(bad)
    not_list = tmp_path / "khong-phai-list.json"
    not_list.write_text(json.dumps({"template": "response"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_wabo_rules(not_list)


def test_wabo_facts_la_global_trial() -> None:
    facts = wabo_facts(
        (Rule(template="response", first="A", second="B", support=0.0, confidence=0.0),)
    )
    assert len(facts) == 1
    assert facts[0].scope is FactScope.GLOBAL
    assert facts[0].status is FactStatus.TRIAL
    assert facts[0].tenant_id == "global"


def test_ban_do_ghi_dung_sau_khi_xay_muc(tmp_path: Path) -> None:
    tenant = _tenant()
    sets = condition_fact_sets([tenant.tenant_data])
    measured = tuple(
        eval_fact_to_fact_read(fact) for fact in sets[DECLARE_ONLY][tenant.tenant_id]
    )
    metrics = compute_round_metrics(
        measured_facts=measured,
        tenant_data=tenant.tenant_data,
        condition=DECLARE_ONLY,
        n_draws=50,
        seed=SYNTHETIC_SEED,
    )
    manifest = tmp_path / "11.2-manifest.json"
    entry = _build_entry(
        condition=DECLARE_ONLY,
        tenant=tenant,
        run_id=None,
        status="in_memory",
        model_id="",
        model_revision="",
        tokens_in=0,
        tokens_out=0,
        token_budget_total=0,
        wall_time=1.5,
        metrics=metrics,
        measured_facts=measured,
        candidate_map={},
        skipped_closes=[],
        n_draws=50,
        seed=SYNTHETIC_SEED,
        code_commit="c" * 40,
        config_hash="f" * 64,
        document_base=None,
        wabo_rule_count=0,
        cache_hits=0,
        note="không chạy vòng học (không mô hình)",
    )
    append_manifest_entry(manifest, entry)
    loaded = load_manifest(manifest)
    assert len(loaded["entries"]) == 1
    assert loaded["entries"][0]["condition"] == DECLARE_ONLY
    assert loaded["entries"][0]["tenant_id"] == tenant.tenant_id
    assert loaded["entries"][0]["run_id"] is None
    assert loaded["entries"][0]["metrics"] == _metrics_to_dict(metrics)
    assert loaded["entries"][0]["n_train"] == len(tenant.tenant_data.train_traces)
    assert loaded["entries"][0]["n_measure"] == len(tenant.tenant_data.measure_traces)
    append_manifest_entry(manifest, entry)
    assert len(load_manifest(manifest)["entries"]) == 2
    # Thiếu tệp thì bản đồ rỗng (để append lần đầu tạo tệp).
    assert load_manifest(tmp_path / "khong-co.json") == {"task": "11.2", "entries": []}
    # Sai hình dạng thì từ chối.
    bad = tmp_path / "sai.json"
    bad.write_text(json.dumps({"khong-phai": "ban-do"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_manifest(bad)


def test_vong_trong_bo_nho_khong_ghi_run() -> None:
    tenant = _tenant()
    facts = tuple(
        eval_fact_to_fact_read(fact)
        for fact in condition_fact_sets([tenant.tenant_data])[DECLARE_ONLY][tenant.tenant_id]
    )
    entry = run_in_memory_measurement(
        tenant=tenant,
        condition=DECLARE_ONLY,
        facts=facts,
        seed=SYNTHETIC_SEED,
        code_commit="c" * 40,
        config_hash="f" * 64,
        n_draws=50,
    )
    assert entry["run_id"] is None
    assert entry["status"] == "in_memory"
    assert entry["tokens_in"] == 0 and entry["tokens_out"] == 0
    assert entry["token_budget_total"] == 0
    expected = metrics_with_ci(
        [fact_read_to_eval_fact(fact) for fact in facts],
        tenant.tenant_data.ground_truth.reference,
        tenant.tenant_data.measure_traces,
        tenant.tenant_id,
        n_draws=50,
        seed=SYNTHETIC_SEED,
        condition=DECLARE_ONLY,
    )
    assert entry["metrics"] == _metrics_to_dict(expected)
