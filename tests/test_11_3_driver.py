"""Test local cho driver thử nghiệm đứt phiên 11.3 (không cần Kaggle/B2).

Bao phủ: bố cục lô + chỉ số resume, TrialConfig, CountingCachedModel
(hit/miss + ngưỡng giết), CountingCandidateIds, wait_for_checkpoint_key,
build_s3_store, cờ resume qua env, chạy thử 0 (tham chiếu), thử 1 (ngắt
ở ranh giới lô bằng poll — kiểm luồng poll nổ đúng điểm bằng kill ghi
lại, vì os._exit thật không test được trong tiến trình), thử 2 (ngắt
giữa lô bằng bộ đếm lần gọi + chạy tiếp), thử 3 (resume sau dừng thật —
phần dừng bằng nút Stop là thủ công, test chỉ bao phía resume), và
script so sánh (pass/fail từng mục + CLI).

LƯU Ý — xung đột tiền tố giữa các lần thử (đã sửa, Phụ lục A.7): bốn lần
thử cùng một điều kiện (cùng tenant/seed/config/data) nên cùng một tiền
tố checkpoint trên B2 (coordinator tự tính tiền tố từ vòng học). Driver
bọc store bằng `TrialNamespacedStore` để mỗi lần thử một namespace
riêng (`trial-{n}/`): lần thử sau không nhìn thấy checkpoint của lần thử
trước, còn hai phiên của cùng một lần thử dùng chung namespace nên phiên
sau vẫn resume đúng. Vì vậy các test ở đây DÙNG CHUNG một store cho
nhiều lần thử để khẳng định sự tách biệt đó (xem `test_thu_1_khong_thay_
checkpoint_cua_thu_0` và `test_phien_sau_chi_thay_checkpoint_cua_chinh_
lan_thu`); chặn fail-closed ở đầu phiên vẫn còn, nhưng nay nó chỉ nổ
khi CHÍNH lần thử đó đã chạy rồi trên cùng store.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from tools.kaggle.compare_11_3 import compare, load_json, main
from tools.kaggle.driver_11_3 import (
    EXPECTED_KEY_ENV,
    PREFIX_ENV,
    RESUME_ENV,
    CheckpointPollThread,
    ChunkPlan,
    ConditionInputs,
    CountingCachedModel,
    CountingCandidateIds,
    TrialConfig,
    TrialNamespacedStore,
    TrialNotInterruptedError,
    UsageLog,
    build_s3_store,
    plan_chunks,
    read_trial_files,
    resolve_prefix,
    resume_chunk_index,
    run_first_session,
    run_resumed_session,
    should_resume,
    start_checkpoint_poll,
    trial_namespace,
    wait_for_checkpoint_key,
)

from praxon_core.adapters.cache import ResponseCache
from praxon_core.adapters.language_model import CompletionResult
from praxon_core.adapters.s3_store import S3CheckpointStore
from praxon_core.learning.coordinator import compute_config_hash
from praxon_core.learning.generator import EpisodeRow
from praxon_core.learning.measures import Measures
from praxon_core.learning.rules import default_rule_table
from praxon_core.settings import Settings

SEED = 42
CONDITION = "C"
CODE_COMMIT = "test-commit-11-3"
DATA_HASH = "d" * 64
VALID_START = "2030-01-01T00:00:00"
RETIRED_AT = "2030-02-01T00:00:00"


class KillFiredError(Exception):
    """Kill switch đã nổ (giả lập os._exit trong test)."""


def _dt(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def _episode(case_id: str, activity: str, occurred: str, number: int) -> EpisodeRow:
    return EpisodeRow(
        id=UUID(int=number),
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


class FakeModel:
    """Model giả: luôn trả một luật response A→B, usage cố định."""

    def __init__(
        self,
        prompt_tokens: int = 10,
        completion_tokens: int = 5,
        delay: float = 0.0,
    ) -> None:
        """Dựng model giả với usage cố định và độ trễ tùy chọn mỗi lần gọi."""
        self.calls = 0
        self.prompts: list[str] = []
        self._prompt_tokens = prompt_tokens
        self._completion_tokens = completion_tokens
        self._delay = delay

    def complete(
        self,
        prompt: str,
        *,
        json_schema: Mapping[str, Any] | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        """Trả một luật response A→B với usage cố định, đếm lần gọi."""
        self.calls += 1
        self.prompts.append(prompt)
        if self._delay:
            time.sleep(self._delay)
        return CompletionResult(
            text=json.dumps(
                {
                    "rules": [
                        {
                            "template": "response",
                            "activation": "A",
                            "target": "B",
                            "source": "De aanvraag wordt ingediend.",
                        }
                    ]
                }
            ),
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
        )


class MemoryStore:
    """CheckpointStore trong bộ nhớ (dict), đủ cho test local."""

    def __init__(self) -> None:
        """Dựng store rỗng trong bộ nhớ."""
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        """Ghi đè object tại khóa."""
        self.objects[key] = data

    def get(self, key: str) -> bytes | None:
        """Đọc object tại khóa, None khi chưa có."""
        return self.objects.get(key)

    def list_keys(self, prefix: str) -> list[str]:
        """Liệt kê khóa có tiền tố, đã sắp xếp."""
        return sorted(key for key in self.objects if key.startswith(prefix))


def _settings(**overrides: object) -> Settings:
    data: dict[str, Any] = {
        "database_url": "",
        "checkpoint_every_n_cases": 100,
        "checkpoint_store": "s3",
        "s3_endpoint_url": "https://s3.example.test",
        "s3_bucket": "praxon-checkpoints",
        "s3_access_key_id": "fake-id",
        "s3_secret_access_key": "fake-secret",
        "token_budget_total": 0,
    }
    data.update(overrides)
    return Settings(**data)


def _inputs(n_cases: int, *, seed: int = SEED) -> ConditionInputs:
    rows: list[EpisodeRow] = []
    for index in range(1, n_cases + 1):
        case_id = f"c{index:03d}"
        rows.append(_episode(case_id, "A", "2026-11-06T10:00:00", 2 * index - 1))
        rows.append(_episode(case_id, "B", "2026-11-06T11:00:00", 2 * index))
    return ConditionInputs(
        tenant_id="acme",
        seed=seed,
        episode_rows=tuple(rows),
        facts=(),
        rule_table=default_rule_table(),
        measures_for=lambda candidate, delta: _measures(),
        valid_start=_dt(VALID_START),
        retired_at=_dt(RETIRED_AT),
        data_hash=DATA_HASH,
    )


def _run_trial0(
    n_cases: int, store: MemoryStore, out_dir: Path, *, delay: float = 0.0, trial: int = 0
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Chạy một phiên đầu (không công tắc) và trả (outcome, usage log).

    `trial` là số lần thử của phiên này: hai phiên của cùng một lần thử
    phải dùng chung số lần thử (chung namespace, A.7) thì phiên sau mới
    thấy checkpoint của phiên đầu.
    """
    outcome = run_first_session(
        config=TrialConfig(condition=CONDITION, trial=trial),
        inputs=_inputs(n_cases),
        settings=_settings(),
        code_commit=CODE_COMMIT,
        model=FakeModel(delay=delay),
        store=store,
        output_dir=out_dir,
    )
    _outcome, usage_log = read_trial_files(out_dir)
    return outcome, usage_log.to_dict()


# --- Bố cục lô + chỉ số resume ------------------------------------------


def test_plan_chunks_ba_lo() -> None:
    rows = _inputs(250).episode_rows
    assert plan_chunks(episode_rows=rows, chunk_size=100, batch_size=10) == [
        ChunkPlan(cases=100, calls=10),
        ChunkPlan(cases=100, calls=10),
        ChunkPlan(cases=50, calls=5),
    ]


def test_plan_chunks_khong_case() -> None:
    assert plan_chunks(episode_rows=(), chunk_size=100, batch_size=10) == []


def test_plan_chunks_tham_so_sai() -> None:
    rows = _inputs(1).episode_rows
    with pytest.raises(ValueError, match="chunk_size"):
        plan_chunks(episode_rows=rows, chunk_size=0, batch_size=10)
    with pytest.raises(ValueError, match="batch_size"):
        plan_chunks(episode_rows=rows, chunk_size=100, batch_size=0)


def test_resume_chunk_index() -> None:
    plans = [ChunkPlan(cases=100, calls=10)] * 3
    assert resume_chunk_index(plans, 0) == 0
    assert resume_chunk_index(plans, 200) == 2
    assert resume_chunk_index(plans, 300) == 3
    with pytest.raises(ValueError, match="ranh giới lô"):
        resume_chunk_index(plans, 150)


def test_trial_config_sai() -> None:
    with pytest.raises(ValueError, match="trial"):
        TrialConfig(condition=CONDITION, trial=4)
    with pytest.raises(ValueError, match="interrupt"):
        TrialConfig(condition=CONDITION, trial=1, interrupt="poll")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="interrupt_chunk"):
        TrialConfig(condition=CONDITION, trial=1, interrupt="checkpoint", interrupt_chunk=-1)
    with pytest.raises(ValueError, match="poll_interval_s"):
        TrialConfig(condition=CONDITION, trial=1, poll_interval_s=0)


# --- CountingCachedModel + CountingCandidateIds ---------------------------


def test_dem_model_hit_va_miss() -> None:
    model = FakeModel()
    usage_log = UsageLog()
    counted = CountingCachedModel(
        model=model,
        cache=ResponseCache(),
        model_revision="7c41481f57cb95916b40956ab2f0b139b296d974",
        usage_log=usage_log,
    )
    first = counted.complete("prompt A")
    second = counted.complete("prompt A")
    assert first.text == second.text
    assert model.calls == 1
    assert counted.calls == 1
    assert counted.hits == 1
    assert usage_log.model_calls == 1
    assert usage_log.cache_hits == 1
    assert usage_log.total_tokens == 15


def test_dem_model_giet_khi_toi_nguong() -> None:
    model = FakeModel()
    usage_log = UsageLog()
    counted = CountingCachedModel(
        model=model,
        cache=ResponseCache(),
        model_revision="7c41481f57cb95916b40956ab2f0b139b296d974",
        usage_log=usage_log,
        kill_after_calls=2,
        kill=lambda: (_ for _ in ()).throw(KillFiredError()),
    )
    counted.complete("prompt A")
    with pytest.raises(KillFiredError):
        counted.complete("prompt B")
    assert model.calls == 2
    assert counted.calls == 2
    assert usage_log.model_calls == 2


def test_dem_model_khong_giet_khi_chua_toi_nguong() -> None:
    model = FakeModel()
    counted = CountingCachedModel(
        model=model,
        cache=ResponseCache(),
        model_revision="7c41481f57cb95916b40956ab2f0b139b296d974",
        usage_log=UsageLog(),
        kill_after_calls=5,
        kill=lambda: (_ for _ in ()).throw(KillFiredError()),
    )
    for index in range(3):
        counted.complete(f"prompt {index}")
    assert model.calls == 3


def test_candidate_id_noi_tiep() -> None:
    counter = CountingCandidateIds(start=5)
    assert counter() == "candidate-5"
    assert counter() == "candidate-6"
    assert CountingCandidateIds(start=0)() == "candidate-0"
    with pytest.raises(ValueError, match="start"):
        CountingCandidateIds(start=-1)


# --- Công tắc poll + build store ------------------------------------------


def test_cho_checkpoint_co_khoa() -> None:
    store = MemoryStore()
    store.put("prefix/000200.json", b"{}")
    fired: list[bool] = []
    assert wait_for_checkpoint_key(
        store=store,
        prefix="prefix",
        target_key="prefix/000200.json",
        poll_interval_s=0.01,
        timeout_s=5.0,
        kill=lambda: fired.append(True),
    )
    assert fired == [True]


def test_cho_checkpoint_het_thoi_gian() -> None:
    store = MemoryStore()
    fired: list[bool] = []
    assert not wait_for_checkpoint_key(
        store=store,
        prefix="prefix",
        target_key="prefix/000200.json",
        poll_interval_s=0.01,
        timeout_s=0.05,
        kill=lambda: fired.append(True),
    )
    assert fired == []


def test_start_checkpoint_poll_no_khi_khoa_co_san() -> None:
    store = MemoryStore()
    store.put("prefix/000200.json", b"{}")
    fired: list[bool] = []
    thread = start_checkpoint_poll(
        store=store,
        prefix="prefix",
        target_key="prefix/000200.json",
        poll_interval_s=0.01,
        kill=lambda: fired.append(True),
    )
    assert thread.daemon
    thread.join(timeout=5.0)
    assert not thread.is_alive()
    assert fired == [True]


def test_poll_dung_duoc_bang_stop() -> None:
    store = MemoryStore()
    fired: list[bool] = []
    thread = start_checkpoint_poll(
        store=store,
        prefix="prefix",
        target_key="prefix/000200.json",
        poll_interval_s=0.01,
        kill=lambda: fired.append(True),
    )
    assert thread.is_alive()
    thread.stop()
    thread.join(timeout=5.0)
    assert not thread.is_alive()
    assert fired == []


def test_build_s3_store_thieu_thong_tin() -> None:
    with pytest.raises(ValueError, match="s3_endpoint_url"):
        build_s3_store(_settings(s3_bucket=None))
    with pytest.raises(ValueError, match="khóa S3"):
        build_s3_store(_settings(s3_access_key_id=None))


def test_build_s3_store_day_du() -> None:
    store = build_s3_store(_settings())
    assert isinstance(store, S3CheckpointStore)


# --- Namespace theo lần thử (A.7) -------------------------------------------


def test_trial_namespace_dung_dinh_dang() -> None:
    assert trial_namespace(0) == "trial-0"
    assert trial_namespace(3) == "trial-3"
    with pytest.raises(ValueError, match="trial"):
        trial_namespace(4)
    with pytest.raises(ValueError, match="trial"):
        trial_namespace(-1)


def test_trial_namespaced_store_tach_hai_lan_thu() -> None:
    raw = MemoryStore()
    trial_0 = TrialNamespacedStore(store=raw, trial=0)
    trial_1 = TrialNamespacedStore(store=raw, trial=1)
    assert trial_0.namespace == "trial-0"
    assert trial_1.namespace == "trial-1"
    trial_0.put("prefix/000100.json", b"a")
    trial_0.put("prefix/000200.json", b"b")
    trial_1.put("prefix/000100.json", b"c")
    # Mỗi lần thử chỉ thấy khóa của mình (cùng khóa gốc, nội dung khác).
    assert trial_0.get("prefix/000100.json") == b"a"
    assert trial_1.get("prefix/000100.json") == b"c"
    assert trial_1.get("prefix/000200.json") is None
    assert trial_0.list_keys("prefix") == ["prefix/000100.json", "prefix/000200.json"]
    assert trial_1.list_keys("prefix") == ["prefix/000100.json"]
    # Store dưới thấy khóa đã thêm namespace; phía gọi thấy khóa gốc.
    assert sorted(raw.objects) == [
        "trial-0/prefix/000100.json",
        "trial-0/prefix/000200.json",
        "trial-1/prefix/000100.json",
    ]


def test_trial_namespaced_store_bo_khoa_la() -> None:
    # Store trong sai hợp đồng (trả cả khóa không nằm dưới namespace đã
    # hỏi) thì wrapper bỏ qua khóa lạ, không để lọt ra ngoài.

    class LeakyStore(MemoryStore):
        """Store rò: list_keys trả mọi khóa bất kể tiền tố."""

        def list_keys(self, prefix: str) -> list[str]:
            """Trả toàn bộ khóa (sai hợp đồng) để test nhánh phòng thủ."""
            return sorted(self.objects)

    raw = LeakyStore()
    raw.put("trial-0/prefix/000100.json", b"a")
    raw.put("other/prefix/000100.json", b"b")
    wrapped = TrialNamespacedStore(store=raw, trial=0)
    assert wrapped.list_keys("prefix") == ["prefix/000100.json"]


# --- Cờ resume qua env -----------------------------------------------------


def test_should_resume_va_resolve_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(RESUME_ENV, raising=False)
    assert not should_resume()
    monkeypatch.setenv(RESUME_ENV, "1")
    assert should_resume()
    monkeypatch.setenv(RESUME_ENV, "true")
    assert not should_resume()
    monkeypatch.setenv(RESUME_ENV, "0")
    assert not should_resume()
    monkeypatch.delenv(PREFIX_ENV, raising=False)
    computed = resolve_prefix(
        tenant_id="acme",
        seed=SEED,
        config_hash=compute_config_hash(_settings()),
        data_hash=DATA_HASH,
    )
    assert computed.startswith("checkpoints/acme/42-")
    monkeypatch.setenv(PREFIX_ENV, "prefix/trial-1")
    assert (
        resolve_prefix(
            tenant_id="acme",
            seed=SEED,
            config_hash=compute_config_hash(_settings()),
            data_hash=DATA_HASH,
        )
        == "prefix/trial-1"
    )
    monkeypatch.delenv(EXPECTED_KEY_ENV, raising=False)
    assert EXPECTED_KEY_ENV == "PRAXON_113_EXPECTED_KEY"


def test_validate_settings_tran_token_phai_tat(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="token_budget_total"):
        run_first_session(
            config=TrialConfig(condition=CONDITION, trial=0),
            inputs=_inputs(10),
            settings=_settings(token_budget_total=100),
            code_commit=CODE_COMMIT,
            model=FakeModel(),
            store=MemoryStore(),
            output_dir=tmp_path,
        )


def test_validate_settings_store_phai_la_s3(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="checkpoint_store"):
        run_first_session(
            config=TrialConfig(condition=CONDITION, trial=0),
            inputs=_inputs(10),
            settings=_settings(checkpoint_store="local"),
            code_commit=CODE_COMMIT,
            model=FakeModel(),
            store=MemoryStore(),
            output_dir=tmp_path,
        )


# --- Thử 0: tham chiếu ------------------------------------------------------


def test_thu_0_tham_chieu_300_case(tmp_path: Path) -> None:
    store = MemoryStore()
    outcome, usage = _run_trial0(300, store, tmp_path / "ref")
    assert outcome["run_status"] == "succeeded"
    assert outcome["model_calls"] == 30
    assert outcome["cache_hits"] == 0
    assert outcome["tokens_in"] + outcome["tokens_out"] == 450
    assert len(outcome["trajectories"]) == 300
    assert len(outcome["insights"]) == 30
    assert len(outcome["candidate_ids"]) == len(outcome["decisions"])
    assert outcome["cases_per_chunk"] == [100, 100, 100]
    assert outcome["calls_per_chunk"] == [10, 10, 10]
    assert outcome["session"] == "first"
    assert outcome["checkpoint_namespace"] == "trial-0"
    assert usage["entries"] is not None
    assert len(usage["entries"]) == 30
    assert (tmp_path / "ref" / "outcome.json").is_file()
    assert (tmp_path / "ref" / "usage_log.json").is_file()
    keys = store.list_keys(f"{trial_namespace(0)}/checkpoints")
    assert len(keys) == 3
    assert all(key.endswith((".json",)) for key in keys)


def test_thu_0_checkpoint_o_ranh_gioi_lo(tmp_path: Path) -> None:
    store = MemoryStore()
    _run_trial0(150, store, tmp_path / "ref")
    keys = store.list_keys(f"{trial_namespace(0)}/checkpoints")
    assert len(keys) == 2
    assert all(key.endswith(("000100.json", "000150.json")) for key in keys)


# --- Thử 1: ngắt ở ranh giới lô --------------------------------------------


def test_thu_1_poll_no_dung_diem(tmp_path: Path) -> None:
    # Luồng poll nổ khi checkpoint 000200 xuất hiện (kill ghi lại; kill
    # thật os._exit không test được trong tiến trình nên chỉ kiểm kill
    # đã được gọi đúng điểm, phiên vẫn chạy hết trong test).
    store = MemoryStore()
    fired: list[bool] = []
    outcome = run_first_session(
        config=TrialConfig(
            condition=CONDITION,
            trial=1,
            interrupt="checkpoint",
            interrupt_chunk=1,
            poll_interval_s=0.01,
        ),
        inputs=_inputs(300),
        settings=_settings(),
        code_commit=CODE_COMMIT,
        model=FakeModel(delay=0.005),
        store=store,
        output_dir=tmp_path / "trial1",
        kill=lambda: fired.append(True),
    )
    assert fired, "luồng poll phải nổ khi checkpoint 000200 xuất hiện"
    assert outcome["run_status"] == "succeeded"


def test_thu_1_chan_khi_khoa_dich_da_ton_tai(tmp_path: Path) -> None:
    # Fail-closed: chạy lại phiên đầu của CÙNG lần thử trên cùng store
    # (khóa đích đã tồn tại trong namespace của chính lần thử đó, vì lần
    # chạy trước đã ghi) thì từ chối chạy thay vì nổ sai điểm. Trước A.7
    # test này gieo checkpoint bằng lần thử 0; nay hai lần thử tách
    # namespace nên lần thử 0 không còn làm lần thử 1 nổ được nữa.
    store = MemoryStore()
    run_first_session(
        config=TrialConfig(
            condition=CONDITION,
            trial=1,
            interrupt="checkpoint",
            interrupt_chunk=1,
            poll_interval_s=0.01,
        ),
        inputs=_inputs(300),
        settings=_settings(),
        code_commit=CODE_COMMIT,
        model=FakeModel(delay=0.005),
        store=store,
        output_dir=tmp_path / "trial1-lan1",
        kill=lambda: None,
    )
    with pytest.raises(ValueError, match="đã tồn tại"):
        run_first_session(
            config=TrialConfig(
                condition=CONDITION, trial=1, interrupt="checkpoint", interrupt_chunk=1
            ),
            inputs=_inputs(300),
            settings=_settings(),
            code_commit=CODE_COMMIT,
            model=FakeModel(),
            store=store,
            output_dir=tmp_path / "trial1-lan2",
        )


def test_thu_1_ngat_roi_chay_tiep_khong_doi(tmp_path: Path) -> None:
    ref_store = MemoryStore()
    ref_outcome, ref_usage = _run_trial0(300, ref_store, tmp_path / "ref")
    # Mô phỏng phiên đầu của thử 1: chạy 200 case đầu rồi dừng ở ranh
    # giới lô (checkpoint 000200 đã có trên store của lần thử này).
    # Phiên đầu dùng cùng số lần thử (1) với phiên sau — chung namespace
    # (A.7) thì phiên sau mới thấy checkpoint của phiên đầu.
    trial_store = MemoryStore()
    first_outcome = run_first_session(
        config=TrialConfig(condition=CONDITION, trial=1),
        inputs=_inputs(200),
        settings=_settings(),
        code_commit=CODE_COMMIT,
        model=FakeModel(),
        store=trial_store,
        output_dir=tmp_path / "trial1-first",
    )
    assert first_outcome["run_status"] == "succeeded"
    resumed = run_resumed_session(
        config=TrialConfig(condition=CONDITION, trial=1),
        inputs=_inputs(300),
        settings=_settings(),
        code_commit=CODE_COMMIT,
        model=FakeModel(),
        store=trial_store,
        output_dir=tmp_path / "trial1-resumed",
    )
    _resumed_outcome, resumed_usage = read_trial_files(tmp_path / "trial1-resumed")
    assert resumed["cases_done_at_resume"] == 200
    assert resumed["expected_remaining_calls"] == 10
    assert resumed["model_calls"] == 10
    assert resumed["checkpoint_key"].endswith("000200.json")
    assert resumed["checkpoint_namespace"] == "trial-1"
    assert resumed["session"] == "resumed"
    result = compare(
        reference_outcome=ref_outcome,
        reference_usage=ref_usage,
        resumed_outcome=resumed,
        resumed_usage=resumed_usage.to_dict(),
        expected_checkpoint_key=resumed["checkpoint_key"],
        expected_cases_done=200,
    )
    assert result.passed, result.report()


def test_thu_1_resume_khong_co_checkpoint(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="không có checkpoint"):
        run_resumed_session(
            config=TrialConfig(condition=CONDITION, trial=1),
            inputs=_inputs(300),
            settings=_settings(),
            code_commit=CODE_COMMIT,
            model=FakeModel(),
            store=MemoryStore(),
            output_dir=tmp_path / "trial1-resumed",
        )


def test_thu_1_khong_thay_checkpoint_cua_thu_0(tmp_path: Path) -> None:
    # Hồi quy cho lỗ hổng A.7: lần thử 0 đã chạy xong trên CÙNG store
    # (checkpoint 000100/000200/000300 còn đó, cùng tiền tố gốc), lần
    # thử 1 vẫn bắt đầu được — không raise fail-closed, luồng poll chỉ
    # nổ khi checkpoint 000200 của CHÍNH lần thử 1 xuất hiện. Trước A.7
    # lần gọi này raise "đã tồn tại" ngay từ đầu.
    store = MemoryStore()
    _run_trial0(300, store, tmp_path / "ref")
    fired: list[bool] = []
    outcome = run_first_session(
        config=TrialConfig(
            condition=CONDITION,
            trial=1,
            interrupt="checkpoint",
            interrupt_chunk=1,
            poll_interval_s=0.01,
        ),
        inputs=_inputs(300),
        settings=_settings(),
        code_commit=CODE_COMMIT,
        model=FakeModel(delay=0.005),
        store=store,
        output_dir=tmp_path / "trial1",
        kill=lambda: fired.append(True),
    )
    assert fired, "luồng poll phải nổ khi checkpoint 000200 của thử 1 xuất hiện"
    assert outcome["run_status"] == "succeeded"
    assert outcome["checkpoint_namespace"] == "trial-1"
    # Store dưới giữ đủ checkpoint của cả hai lần thử, tách namespace.
    assert len(store.list_keys("trial-0/checkpoints")) == 3
    assert len(store.list_keys("trial-1/checkpoints")) == 3


def test_phien_sau_chi_thay_checkpoint_cua_chinh_lan_thu(tmp_path: Path) -> None:
    # Cùng store đã có checkpoint cuối của lần thử 0 (000300): phiên sau
    # của lần thử 1 vẫn phải resume từ 000200 của CHÍNH lần thử 1, không
    # đọc nhầm checkpoint mới nhất của lần thử 0 (nếu đọc nhầm thì đã
    # raise "không còn case nào" vì 000300 là toàn bộ điều kiện).
    ref_store = MemoryStore()
    ref_outcome, ref_usage = _run_trial0(300, ref_store, tmp_path / "ref")
    store = MemoryStore()
    _run_trial0(300, store, tmp_path / "trial0")
    _run_trial0(200, store, tmp_path / "trial1-first", trial=1)
    resumed = run_resumed_session(
        config=TrialConfig(condition=CONDITION, trial=1),
        inputs=_inputs(300),
        settings=_settings(),
        code_commit=CODE_COMMIT,
        model=FakeModel(),
        store=store,
        output_dir=tmp_path / "trial1-resumed",
    )
    _resumed_outcome, resumed_usage = read_trial_files(tmp_path / "trial1-resumed")
    assert resumed["cases_done_at_resume"] == 200
    assert resumed["checkpoint_key"].endswith("000200.json")
    assert resumed["checkpoint_namespace"] == "trial-1"
    result = compare(
        reference_outcome=ref_outcome,
        reference_usage=ref_usage,
        resumed_outcome=resumed,
        resumed_usage=resumed_usage.to_dict(),
        expected_checkpoint_key=resumed["checkpoint_key"],
        expected_cases_done=200,
        expected_checkpoint_namespace="trial-1",
    )
    assert result.passed, result.report()


# --- Thử 2: ngắt giữa lô ----------------------------------------------------


def test_thu_2_giet_giua_lo_roi_chay_tiep_khong_doi(tmp_path: Path) -> None:
    ref_store = MemoryStore()
    ref_outcome, ref_usage = _run_trial0(300, ref_store, tmp_path / "ref")
    trial_store = MemoryStore()
    # Ngưỡng giết: 20 lần gọi của 2 lô đầu + 1 = lần gọi đầu của lô 3.
    with pytest.raises(KillFiredError):
        run_first_session(
            config=TrialConfig(
                condition=CONDITION, trial=2, interrupt="calls", interrupt_chunk=2
            ),
            inputs=_inputs(300),
            settings=_settings(),
            code_commit=CODE_COMMIT,
            model=FakeModel(),
            store=trial_store,
            output_dir=tmp_path / "trial2-first",
            kill=lambda: (_ for _ in ()).throw(KillFiredError()),
        )
    keys = trial_store.list_keys(f"{trial_namespace(2)}/checkpoints")
    assert len(keys) == 2
    assert all(key.endswith(("000100.json", "000200.json")) for key in keys)
    resumed = run_resumed_session(
        config=TrialConfig(condition=CONDITION, trial=2),
        inputs=_inputs(300),
        settings=_settings(),
        code_commit=CODE_COMMIT,
        model=FakeModel(),
        store=trial_store,
        output_dir=tmp_path / "trial2-resumed",
    )
    _resumed_outcome, resumed_usage = read_trial_files(tmp_path / "trial2-resumed")
    assert resumed["cases_done_at_resume"] == 200
    assert resumed["expected_remaining_calls"] == 10
    assert resumed["model_calls"] == 10
    result = compare(
        reference_outcome=ref_outcome,
        reference_usage=ref_usage,
        resumed_outcome=resumed,
        resumed_usage=resumed_usage.to_dict(),
        expected_checkpoint_key=resumed["checkpoint_key"],
        expected_cases_done=200,
    )
    assert result.passed, result.report()


def test_thu_2_nguong_giet_sai_thi_bao_loi(tmp_path: Path) -> None:
    # interrupt_chunk ngoài bố cục lô thì báo lỗi rõ trước khi chạy.
    with pytest.raises(ValueError, match="interrupt_chunk"):
        run_first_session(
            config=TrialConfig(
                condition=CONDITION, trial=2, interrupt="calls", interrupt_chunk=5
            ),
            inputs=_inputs(100),
            settings=_settings(),
            code_commit=CODE_COMMIT,
            model=FakeModel(),
            store=MemoryStore(),
            output_dir=tmp_path / "trial2",
        )


def test_cong_tac_gai_ma_khong_no_thi_bao_loi(tmp_path: Path) -> None:
    # Thử 1 mà luồng poll không bao giờ thấy checkpoint đích (store mù:
    # ghi được nhưng list_keys luôn rỗng) thì driver raise rõ thay vì
    # ghi outcome "đầy đủ" giả.
    class BlindStore(MemoryStore):
        """Store ghi được nhưng list_keys luôn rỗng (mô phỏng poll mù)."""

        def list_keys(self, prefix: str) -> list[str]:
            """Không thấy khóa nào, dù đã ghi."""
            return []

    with pytest.raises(TrialNotInterruptedError):
        run_first_session(
            config=TrialConfig(
                condition=CONDITION,
                trial=1,
                interrupt="checkpoint",
                interrupt_chunk=1,
                poll_interval_s=0.01,
            ),
            inputs=_inputs(300),
            settings=_settings(),
            code_commit=CODE_COMMIT,
            model=FakeModel(),
            store=BlindStore(),
            output_dir=tmp_path / "trial1",
        )
    # Không rò luồng: driver dừng luồng poll khi vòng chạy kết thúc.
    assert not any(
        isinstance(thread, CheckpointPollThread) and thread.is_alive()
        for thread in threading.enumerate()
    )


# --- Thử 3: resume sau dừng thật --------------------------------------------


def test_thu_3_resume_sau_dung_that(tmp_path: Path) -> None:
    # Phần dừng bằng nút Stop là thủ công (không test được); test bao
    # phía resume: checkpoint 000200 đã có sẵn, phiên sau chạy tiếp.
    ref_store = MemoryStore()
    ref_outcome, ref_usage = _run_trial0(300, ref_store, tmp_path / "ref")
    trial_store = MemoryStore()
    _run_trial0(200, trial_store, tmp_path / "trial3-first", trial=3)
    resumed = run_resumed_session(
        config=TrialConfig(condition=CONDITION, trial=3),
        inputs=_inputs(300),
        settings=_settings(),
        code_commit=CODE_COMMIT,
        model=FakeModel(),
        store=trial_store,
        output_dir=tmp_path / "trial3-resumed",
    )
    _resumed_outcome, resumed_usage = read_trial_files(tmp_path / "trial3-resumed")
    result = compare(
        reference_outcome=ref_outcome,
        reference_usage=ref_usage,
        resumed_outcome=resumed,
        resumed_usage=resumed_usage.to_dict(),
        expected_checkpoint_key=resumed["checkpoint_key"],
        expected_cases_done=200,
    )
    assert result.passed, result.report()


def test_resume_khong_con_viec_thi_bao_loi(tmp_path: Path) -> None:
    # Checkpoint cuối đã là toàn bộ điều kiện: không còn việc để chạy
    # tiếp thì từ chối (tránh một lần "pass" rỗng). Phiên đầu dùng cùng
    # số lần thử (1) với phiên sau để checkpoint nằm đúng namespace.
    trial_store = MemoryStore()
    _run_trial0(300, trial_store, tmp_path / "trial-first", trial=1)
    with pytest.raises(ValueError, match="không còn case nào"):
        run_resumed_session(
            config=TrialConfig(condition=CONDITION, trial=1),
            inputs=_inputs(300),
            settings=_settings(),
            code_commit=CODE_COMMIT,
            model=FakeModel(),
            store=trial_store,
            output_dir=tmp_path / "resumed",
        )


# --- Script so sánh ---------------------------------------------------------


def _fake_outcome(**overrides: object) -> dict[str, Any]:
    outcome: dict[str, Any] = {
        "trajectories": [{"case_id": "c1"}],
        "insights": [{"template": "response"}],
        "decisions": [{"verdict": "promote"}],
        "candidate_ids": ["candidate-0"],
        "fact_rows": [{"id": "f1"}],
        "fact_closes": [],
        "run_status": "succeeded",
        "calls_per_chunk": [2, 1],
        "cases_per_chunk": [100, 50],
        "cases_done_at_resume": 100,
        "checkpoint_key": "prefix/000100.json",
        "checkpoint_namespace": "trial-1",
        "expected_remaining_calls": 1,
        "model_calls": 1,
        "cache_hits": 0,
        "tokens_in": 30,
        "tokens_out": 15,
    }
    outcome.update(overrides)
    return outcome


def _fake_usage(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {"entries": entries}


def _miss(key: str, prompt_tokens: int = 10, completion_tokens: int = 5) -> dict[str, Any]:
    return {
        "key": key,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }


def _hit(key: str) -> dict[str, Any]:
    return {"key": key, "hit": True}


def test_compare_pass() -> None:
    ref = _fake_outcome()
    res = _fake_outcome()
    ref_usage = _fake_usage([_miss("k1"), _miss("k2"), _miss("k3")])
    res_usage = _fake_usage([_miss("k3")])
    result = compare(
        reference_outcome=ref,
        reference_usage=ref_usage,
        resumed_outcome=res,
        resumed_usage=res_usage,
        expected_checkpoint_key="prefix/000100.json",
        expected_cases_done=100,
    )
    assert result.passed, result.report()


def test_compare_noi_dung_khac() -> None:
    ref = _fake_outcome()
    res = _fake_outcome(insights=[{"template": "precedence"}])
    result = compare(
        reference_outcome=ref,
        reference_usage=_fake_usage([_miss("k1"), _miss("k2"), _miss("k3")]),
        resumed_outcome=res,
        resumed_usage=_fake_usage([_miss("k3")]),
    )
    assert not result.passed
    failed = [check.name for check in result.checks if not check.passed]
    assert failed == ["nội dung: insights"]


def test_compare_token_lech() -> None:
    ref = _fake_outcome()
    res = _fake_outcome(tokens_in=31)
    result = compare(
        reference_outcome=ref,
        reference_usage=_fake_usage([_miss("k1"), _miss("k2"), _miss("k3")]),
        resumed_outcome=res,
        resumed_usage=_fake_usage([_miss("k3")]),
    )
    assert not result.passed
    failed = [check.name for check in result.checks if not check.passed]
    assert failed == ["token: đẳng thức kiểm toán"]


def test_compare_goi_sai_so() -> None:
    ref = _fake_outcome()
    res = _fake_outcome(model_calls=2)
    result = compare(
        reference_outcome=ref,
        reference_usage=_fake_usage([_miss("k1"), _miss("k2"), _miss("k3")]),
        resumed_outcome=res,
        resumed_usage=_fake_usage([_miss("k3")]),
    )
    assert not result.passed
    failed = [check.name for check in result.checks if not check.passed]
    assert failed == ["số lần gọi mô hình phiên sau"]


def test_compare_checkpoint_sai_khoa() -> None:
    ref = _fake_outcome()
    res = _fake_outcome()
    result = compare(
        reference_outcome=ref,
        reference_usage=_fake_usage([_miss("k1"), _miss("k2"), _miss("k3")]),
        resumed_outcome=res,
        resumed_usage=_fake_usage([_miss("k3")]),
        expected_checkpoint_key="prefix/000200.json",
    )
    assert not result.passed
    failed = [check.name for check in result.checks if not check.passed]
    assert failed == ["checkpoint đã dùng"]


def test_compare_namespace_dung() -> None:
    ref = _fake_outcome()
    res = _fake_outcome()
    result = compare(
        reference_outcome=ref,
        reference_usage=_fake_usage([_miss("k1"), _miss("k2"), _miss("k3")]),
        resumed_outcome=res,
        resumed_usage=_fake_usage([_miss("k3")]),
        expected_checkpoint_key="prefix/000100.json",
        expected_cases_done=100,
        expected_checkpoint_namespace="trial-1",
    )
    assert result.passed, result.report()


def test_compare_namespace_sai() -> None:
    # Checkpoint đúng khóa nhưng sai namespace (của lần thử khác) thì
    # FAIL đúng một mục namespace, các mục khác vẫn PASS.
    ref = _fake_outcome()
    res = _fake_outcome()
    result = compare(
        reference_outcome=ref,
        reference_usage=_fake_usage([_miss("k1"), _miss("k2"), _miss("k3")]),
        resumed_outcome=res,
        resumed_usage=_fake_usage([_miss("k3")]),
        expected_checkpoint_key="prefix/000100.json",
        expected_cases_done=100,
        expected_checkpoint_namespace="trial-2",
    )
    assert not result.passed
    failed = [check.name for check in result.checks if not check.passed]
    assert failed == ["checkpoint đã dùng (namespace)"]


def test_compare_namespace_khong_truyen_thi_khong_kiem() -> None:
    # Không truyền namespace kỳ vọng thì không kiểm mục đó (tương thích
    # outcome cũ chưa ghi namespace).
    ref = _fake_outcome()
    res = _fake_outcome(checkpoint_namespace="trial-0")
    result = compare(
        reference_outcome=ref,
        reference_usage=_fake_usage([_miss("k1"), _miss("k2"), _miss("k3")]),
        resumed_outcome=res,
        resumed_usage=_fake_usage([_miss("k3")]),
    )
    assert result.passed, result.report()


def test_compare_hit_khong_co_trong_log_tham_chieu() -> None:
    ref = _fake_outcome()
    res = _fake_outcome()
    result = compare(
        reference_outcome=ref,
        reference_usage=_fake_usage([_miss("k1"), _miss("k2"), _miss("k3")]),
        resumed_outcome=res,
        resumed_usage=_fake_usage([_hit("k-la")]),
    )
    assert not result.passed
    failed = [check.name for check in result.checks if not check.passed]
    assert failed == ["token: đẳng thức kiểm toán"]


def test_compare_cache_hit_tinh_dung() -> None:
    # Lần resume phục vụ 1 lô từ cache: usage của lô đó vẫn tính đủ.
    # Outcome resume là tổng tích lũy (30 = 2 lô đã xong) + 0 mới; hit k3
    # bù 15 nên 30 + 15 = 45 bằng tham chiếu; gọi 0 + hit 1 = 1 lô còn lại.
    ref = _fake_outcome()
    res = _fake_outcome(
        tokens_in=20, tokens_out=10, model_calls=0, cache_hits=1, expected_remaining_calls=1
    )
    ref_usage = _fake_usage([_miss("k1"), _miss("k2"), _miss("k3")])
    res_usage = _fake_usage([_hit("k3")])
    result = compare(
        reference_outcome=ref,
        reference_usage=ref_usage,
        resumed_outcome=res,
        resumed_usage=res_usage,
    )
    assert result.passed, result.report()


def test_load_json_sai_hinh_dang(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError, match="không phải object"):
        load_json(path)


def test_compare_main_cli(tmp_path: Path) -> None:
    ref_outcome = tmp_path / "ref-outcome.json"
    ref_usage = tmp_path / "ref-usage.json"
    res_outcome = tmp_path / "res-outcome.json"
    res_usage = tmp_path / "res-usage.json"
    ref_outcome.write_text(json.dumps(_fake_outcome()), encoding="utf-8")
    ref_usage.write_text(
        json.dumps(_fake_usage([_miss("k1"), _miss("k2"), _miss("k3")])), encoding="utf-8"
    )
    res_outcome.write_text(json.dumps(_fake_outcome()), encoding="utf-8")
    res_usage.write_text(json.dumps(_fake_usage([_miss("k3")])), encoding="utf-8")
    argv = [
        "--reference-outcome",
        str(ref_outcome),
        "--reference-usage",
        str(ref_usage),
        "--resumed-outcome",
        str(res_outcome),
        "--resumed-usage",
        str(res_usage),
        "--expected-checkpoint-key",
        "prefix/000100.json",
        "--expected-cases-done",
        "100",
        "--expected-checkpoint-namespace",
        "trial-1",
    ]
    assert main(argv) == 0
    res_outcome.write_text(json.dumps(_fake_outcome(tokens_in=31)), encoding="utf-8")
    assert main(argv) == 1
    res_outcome.write_text(
        json.dumps(_fake_outcome(checkpoint_namespace="trial-2")), encoding="utf-8"
    )
    assert main(argv) == 1


def test_read_trial_files_vong_tron(tmp_path: Path) -> None:
    store = MemoryStore()
    outcome, usage = _run_trial0(100, store, tmp_path / "ref")
    outcome_dict, usage_log = read_trial_files(tmp_path / "ref")
    assert outcome_dict == outcome
    assert usage_log.to_dict() == usage


def test_usage_log_vong_tron_json() -> None:
    log = UsageLog()
    log.record_miss("k1", 10, 5)
    log.record_hit("k1")
    assert UsageLog.from_dict(log.to_dict()).to_dict() == log.to_dict()
    assert log.model_calls == 1
    assert log.cache_hits == 1
    assert log.total_tokens == 15
    with pytest.raises(ValueError, match="entries"):
        UsageLog.from_dict({"entries": "khong-phai-list"})


def test_trial_not_interrupted_error() -> None:
    # Lỗi dùng khi công tắc đã gài mà không nổ (định nghĩa ở driver).
    assert issubclass(TrialNotInterruptedError, RuntimeError)
    assert str(TrialNotInterruptedError("không nổ")) == "không nổ"
