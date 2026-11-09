"""Test tích hợp driver bảy điều kiện (plan con 11, task 11.2).

Khẳng định cổng ra DB của task: đường ghi DB qua Postgres thật với model
giả (insert run + event + fact, một giao dịch mỗi vai); bản đồ ghi đúng
sau insert_run; vòng chạm trần ghi `budget_exceeded` + chẩn đoán, không
cho qua lặng lẽ; script báo cáo pass/fail đúng trên dữ liệu giả.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tools.kaggle.driver_11_2 import (
    SYNTHETIC_ORIGIN,
    SYNTHETIC_SOURCE,
    TenantRoundData,
    _episode_rows_for_synthetic,
    append_manifest_entry,
    compute_ceiling,
    load_manifest,
    make_role_connect,
    run_model_round,
)
from tools.kaggle.report_11_2 import (
    cross_check_runs,
    format_report,
    recompute_metrics,
)

from praxon_core.adapters.language_model import CompletionResult
from praxon_core.adapters.local_store import LocalCheckpointStore
from praxon_core.declare.miner import discover
from praxon_core.eval.experiments import TenantData
from praxon_core.eval.ground_truth import (
    GROUND_TRUTH_CONFIDENCE,
    GROUND_TRUTH_SUPPORT,
    ground_truth_from_generator,
)
from praxon_core.eval.report import SYNTHETIC_SEED, split_generated_traces
from praxon_core.learning.coordinator import compute_config_hash, merge_data_hash
from praxon_core.learning.reflector import Reflector
from praxon_core.settings import Settings
from praxon_core.synthetic.generator import (
    BASE_ORDER,
    GeneratorParams,
    generate,
)
from praxon_core.synthetic.generator import (
    compute_data_hash as compute_generator_data_hash,
)

from .conftest import ADMIN_DSN, PROMOTER_PASSWORD, TENANT_PASSWORD, as_role, one

SEED = SYNTHETIC_SEED
CODE_COMMIT = "c" * 40
RULES = (
    ("response", "step_01", "step_02"),
    ("response", "step_02", "step_03"),
    ("response", "step_03", "step_04"),
    ("response", "step_04", "step_05"),
    ("response", "step_05", "step_06"),
    ("response", "step_06", "step_07"),
    ("response", "step_07", "step_08"),
    ("precedence", "step_01", "step_02"),
)
"""Luật kề nhau theo thứ tự gốc — đều thuộc đáp án của tenant acme."""


class _FakeModel:
    """Model giả: mỗi lần gọi trả một luật kề nhau (xoay vòng), kèm usage cố định."""

    def __init__(self, *, prompt_tokens: int = 2, completion_tokens: int = 4) -> None:
        self._index = 0
        self._prompt_tokens = prompt_tokens
        self._completion_tokens = completion_tokens

    def complete(
        self,
        prompt: str,
        *,
        json_schema: Mapping[str, Any] | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        template, activation, target = RULES[self._index % len(RULES)]
        self._index += 1
        return CompletionResult(
            text=json.dumps(
                {
                    "rules": [
                        {
                            "template": template,
                            "activation": activation,
                            "target": target,
                            "source": "De aanvraag wordt ingediend.",
                        }
                    ]
                }
            ),
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
        )


def _acme_round_data(*, n_cases: int = 60) -> TenantRoundData:
    """TenantRoundData cho `acme` (vai DB đã provision): thứ tự gốc, seed 42."""
    params = GeneratorParams(seed=SEED, n_cases=n_cases, order=BASE_ORDER)
    log = generate(tenant_id="acme", params=params)
    train, measure = split_generated_traces(log.traces)
    tenant_data = TenantData(
        tenant_id="acme",
        train_traces=train,
        measure_traces=measure,
        ground_truth=ground_truth_from_generator(log),
        own_rules=discover(
            train,
            support=GROUND_TRUTH_SUPPORT,
            confidence=GROUND_TRUTH_CONFIDENCE,
        ),
    )
    return TenantRoundData(
        tenant_id="acme",
        source=SYNTHETIC_SOURCE,
        tenant_data=tenant_data,
        episode_rows=tuple(_episode_rows_for_synthetic("acme", train)),
        valid_start=SYNTHETIC_ORIGIN,
        data_hash=merge_data_hash(
            generator_hash=compute_generator_data_hash(tenant_id="acme", params=params)
        ),
        origin_date=SYNTHETIC_ORIGIN,
    )


def _settings(
    *,
    checkpoint_every_n_cases: int = 100,
    token_budget_reserve_per_call: int = 2048,
) -> Settings:
    return Settings.model_validate(
        {
            "database_url": ADMIN_DSN,
            "checkpoint_every_n_cases": checkpoint_every_n_cases,
            "token_budget_reserve_per_call": token_budget_reserve_per_call,
        }
    )


def _run_round(
    *,
    tenant: TenantRoundData,
    settings: Settings,
    ceiling: int,
    tmp_path: Path,
) -> dict[str, Any]:
    store = LocalCheckpointStore(tmp_path / "ckp")
    reflector = Reflector(
        _FakeModel(),
        batch_size=settings.reflector_batch_size,
        seed=SEED,
    )
    connect = make_role_connect(
        base_dsn=ADMIN_DSN,
        tenant_password=TENANT_PASSWORD,
        promoter_password=PROMOTER_PASSWORD,
    )
    return run_model_round(
        tenant=tenant,
        condition="Gộp chung",
        facts=(),
        settings=settings,
        reflector=reflector,
        seed=SEED,
        code_commit=CODE_COMMIT,
        config_hash=compute_config_hash(settings),
        ceiling=ceiling,
        store=store,
        connect=connect,
        n_draws=50,
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


def test_vong_hoc_ghi_run_event_fact_qua_dung_vai(tmp_path: Path, pg: None) -> None:
    tenant = _acme_round_data()
    settings = _settings()
    ceiling = compute_ceiling(
        n_trajectories=len(tenant.tenant_data.train_traces),
        batch_size=settings.reflector_batch_size,
        max_cost_per_call=2048,
    )
    entry = _run_round(tenant=tenant, settings=settings, ceiling=ceiling, tmp_path=tmp_path)
    assert entry["status"] == "succeeded"
    run_id = entry["run_id"]
    assert isinstance(run_id, str) and run_id
    row = _read_run(run_id)
    assert row[0] == "acme"
    assert row[1] == SEED
    assert row[-1] == "succeeded"
    assert entry["tokens_in"] + entry["tokens_out"] > 0
    assert entry["tokens_in"] + entry["tokens_out"] <= ceiling
    candidate_map = entry["candidate_map"]
    assert candidate_map, "vòng thành công phải có ít nhất một candidate"
    with as_role("acme__reader") as conn:
        events = conn.execute(
            "SELECT actor, action FROM event WHERE run_id = %s", (run_id,)
        ).fetchall()
    actors = {actor for actor, _ in events}
    assert {"generator", "reflector", "curator", "governor"} <= actors
    with as_role("acme__reader") as conn:
        facts = conn.execute(
            "SELECT canonical_key, candidate_id FROM fact "
            "WHERE tenant_id = 'acme' AND status = 'trial'"
        ).fetchall()
    # Chỉ tính fact của vòng này (candidate_id nằm trong candidate_map);
    # fact seed của conftest ('seed-fact-acme') không thuộc vòng này.
    # Governor chỉ duyệt luật qua ngưỡng wilson >= 0,7: step_01->step_02
    # (0,858) và step_03->step_04 (0,741) được duyệt; step_02->step_03
    # (0,186) và step_04->step_05 (0,168) bị từ chối nên không có fact.
    # psycopg trả candidate_id dạng UUID, candidate_map giữ dạng chuỗi.
    round_facts = [
        (key, candidate_id)
        for key, candidate_id in facts
        if candidate_id is not None and str(candidate_id) in set(candidate_map.values())
    ]
    written = {key for key, _ in round_facts}
    assert written == {"response(step_01, step_02)", "response(step_03, step_04)"}
    db_candidate_ids = {str(candidate_id) for _, candidate_id in round_facts}
    assert db_candidate_ids == set(candidate_map.values())
    manifest = tmp_path / "11.2-manifest.json"
    append_manifest_entry(manifest, entry)
    loaded = load_manifest(manifest)
    assert len(loaded["entries"]) == 1
    assert loaded["entries"][0]["run_id"] == run_id
    assert loaded["entries"][0]["status"] == "succeeded"
    assert not cross_check_runs(entries=loaded["entries"], database_url=ADMIN_DSN)
    round_data = {f"{SYNTHETIC_SOURCE}:acme": tenant}
    assert not recompute_metrics(entries=loaded["entries"], round_data=round_data)
    report = format_report(loaded["entries"])
    assert "acme — Gộp chung" in report
    assert "Đã dùng / trần token mỗi vòng" in report


def test_vong_cham_tran_ghi_budget_exceeded_khong_cho_qua(tmp_path: Path, pg: None) -> None:
    tenant = _acme_round_data()
    settings = _settings(checkpoint_every_n_cases=2, token_budget_reserve_per_call=10)
    entry = _run_round(tenant=tenant, settings=settings, ceiling=20, tmp_path=tmp_path)
    assert entry["status"] == "budget_exceeded"
    run_id = entry["run_id"]
    assert isinstance(run_id, str) and run_id
    assert _read_run(run_id)[-1] == "budget_exceeded"
    assert "trần" in entry["note"]
    assert entry["token_budget_total"] == 20
    manifest = tmp_path / "11.2-manifest.json"
    append_manifest_entry(manifest, entry)
    loaded = load_manifest(manifest)
    assert not cross_check_runs(entries=loaded["entries"], database_url=ADMIN_DSN)


def test_bao_cao_that_bai_khi_ban_do_bi_gia_mao(tmp_path: Path, pg: None) -> None:
    tenant = _acme_round_data()
    settings = _settings()
    ceiling = compute_ceiling(
        n_trajectories=len(tenant.tenant_data.train_traces),
        batch_size=settings.reflector_batch_size,
        max_cost_per_call=2048,
    )
    entry = _run_round(tenant=tenant, settings=settings, ceiling=ceiling, tmp_path=tmp_path)
    manifest = tmp_path / "11.2-manifest.json"
    append_manifest_entry(manifest, entry)
    loaded = load_manifest(manifest)
    tampered = json.loads(json.dumps(loaded["entries"]))
    tampered[0]["tokens_in"] = tampered[0]["tokens_in"] + 1
    assert cross_check_runs(entries=tampered, database_url=ADMIN_DSN)
    tampered_metrics = json.loads(json.dumps(loaded["entries"]))
    stored_precision = tampered_metrics[0]["metrics"]["precision"]["value"]
    # Đổi sang giá trị khác hẳn giá trị thật. Vòng này input rỗng nên
    # precision thật là 0.0 (không có fact active) — sửa thành 0.0 như
    # cũ thì không đổi gì nên recompute không phát hiện được.
    tampered_metrics[0]["metrics"]["precision"]["value"] = (
        0.5 if stored_precision == 0.0 else 0.0
    )
    round_data = {f"{SYNTHETIC_SOURCE}:acme": tenant}
    assert recompute_metrics(entries=tampered_metrics, round_data=round_data)
