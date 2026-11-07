"""Test tích hợp khóa phần đo (task 12.1, spec dòng 152).

Cổng ra của task: test đi qua FILE khóa thật (nạp TOML, tính hash, đối
chiếu bản ghi, chạy hoặc từ chối qua `run_learning_round` với Reflector
giả). Không cần DB: vòng học chạy thuần trong bộ nhớ. Test qua hash viết
tay đã có trong tests/test_coordinator.py (dòng 490-527); test ở đây
khác ở chỗ đi qua file khóa thật.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from uuid import UUID

import pytest

from praxon_core.learning.coordinator import (
    LearningRound,
    ReflectorFn,
    ReflectorResult,
    compute_config_hash,
    run_learning_round,
)
from praxon_core.learning.curator import FactRead
from praxon_core.learning.generator import EpisodeRow, Trajectory
from praxon_core.learning.measures import Measures
from praxon_core.learning.rules import default_rule_table
from praxon_core.learning.test_split_lock import load_locked_config
from praxon_core.settings import Settings
from tests.paths import REPO_ROOT

CONFIG = REPO_ROOT / "configs" / "phan-do.toml"
LOCK = REPO_ROOT / "configs" / "phan-do.lock.toml"
#: DSN dev local (không mật khẩu, không phải bí mật): TOML khóa không chứa
#: `database_url` theo đề xuất (driver lấy từ env lúc chạy), nên test cấp
#: qua biến môi trường khi nạp file thật.
DEV_DATABASE_URL = "postgresql://postgres@localhost:5432/praxon"
VALID_START = datetime(2030, 1, 1, tzinfo=UTC)
RETIRED_AT = datetime(2030, 2, 1, tzinfo=UTC)
EPISODE_ID = "22222222-2222-2222-2222-222222222222"
SEED = 42
MODEL_ID = "Qwen/Qwen3-8B-GGUF"
MODEL_REVISION = "7c41481f57cb95916b40956ab2f0b139b296d974"
CODE_COMMIT = "d8f9e2a0000000000000000000000000000000000"
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


def _candidate_ids() -> Callable[[], str]:
    counter = itertools.count()
    return lambda: f"candidate-{next(counter)}"


def _reflector(calls: list[bool]) -> ReflectorFn:
    def reflect(
        trajectories: Sequence[Trajectory], facts: Sequence[FactRead]
    ) -> ReflectorResult:
        calls.append(True)
        return ReflectorResult(insights=())

    return reflect


def _round(
    *,
    config_hash: str,
    locked_config_hash: str | None,
    on_test_split: bool,
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
        config_hash=config_hash,
        data_hash=DATA_HASH,
        valid_start=VALID_START,
        retired_at=RETIRED_AT,
        wall_time=1.5,
        locked_config_hash=locked_config_hash,
        on_test_split=on_test_split,
    )


def _load(monkeypatch: pytest.MonkeyPatch) -> tuple[Settings, str]:
    monkeypatch.setenv("PRAXON_DATABASE_URL", DEV_DATABASE_URL)
    return load_locked_config(CONFIG, LOCK)


def test_file_cau_hinh_va_ban_ghi_khoa_khop_nhau(monkeypatch):
    settings, locked = _load(monkeypatch)
    assert compute_config_hash(settings) == locked
    assert len(locked) == 64 and all(c in "0123456789abcdef" for c in locked)


def test_khop_khoa_thi_chay_phan_do(monkeypatch):
    settings, locked = _load(monkeypatch)
    outcome = run_learning_round(
        _round(
            config_hash=compute_config_hash(settings),
            locked_config_hash=locked,
            on_test_split=True,
        ),
        reflect=_reflector([]),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert outcome.run_row.status == "succeeded"


def test_doi_mot_truong_thi_tu_choi_truoc_khi_chay(monkeypatch):
    settings, locked = _load(monkeypatch)
    changed = settings.model_copy(update={"reflector_batch_size": 11})
    calls: list[bool] = []
    with pytest.raises(ValueError, match="không được chạy trên phần đo"):
        run_learning_round(
            _round(
                config_hash=compute_config_hash(changed),
                locked_config_hash=locked,
                on_test_split=True,
            ),
            reflect=_reflector(calls),
            measures_for=lambda candidate, delta: _measures(),
            candidate_id_for=_candidate_ids(),
        )
    assert calls == []


def test_doi_mot_truong_nhung_khong_phai_phan_do_thi_chay(monkeypatch):
    settings, locked = _load(monkeypatch)
    changed = settings.model_copy(update={"reflector_batch_size": 11})
    outcome = run_learning_round(
        _round(
            config_hash=compute_config_hash(changed),
            locked_config_hash=locked,
            on_test_split=False,
        ),
        reflect=_reflector([]),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert outcome.run_row.status == "succeeded"


def test_thieu_ban_ghi_khoa_thi_tu_choi():
    with pytest.raises(ValueError, match="không đọc được bản ghi khóa"):
        load_locked_config(CONFIG, REPO_ROOT / "configs" / "khong-co.lock.toml")


def test_ban_ghi_thieu_khoa_hash_thi_tu_choi(tmp_path):
    lock = tmp_path / "phan-do.lock.toml"
    lock.write_text("seed = 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="thiếu locked_config_hash"):
        load_locked_config(CONFIG, lock)


def test_ban_ghi_khoa_hash_rong_thi_tu_choi(tmp_path):
    lock = tmp_path / "phan-do.lock.toml"
    lock.write_text('locked_config_hash = ""\n', encoding="utf-8")
    with pytest.raises(ValueError, match="thiếu locked_config_hash"):
        load_locked_config(CONFIG, lock)


def test_toml_va_ban_ghi_lech_nhau_thi_tu_choi(monkeypatch, tmp_path):
    monkeypatch.setenv("PRAXON_DATABASE_URL", DEV_DATABASE_URL)
    lock = tmp_path / "phan-do.lock.toml"
    lock.write_text('locked_config_hash = "' + "0" * 64 + '"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="khác khóa"):
        load_locked_config(CONFIG, lock)


def test_thieu_toml_cau_hinh_thi_tu_choi():
    with pytest.raises(ValueError, match="không đọc được cấu hình đo"):
        load_locked_config(REPO_ROOT / "configs" / "khong-co.toml", LOCK)


def test_doi_truong_loai_khoi_hash_thi_van_chay(monkeypatch):
    settings, locked = _load(monkeypatch)
    changed = settings.model_copy(update={"s3_bucket": "bucket-khac"})
    assert compute_config_hash(changed) == locked
    outcome = run_learning_round(
        _round(
            config_hash=compute_config_hash(changed),
            locked_config_hash=locked,
            on_test_split=True,
        ),
        reflect=_reflector([]),
        measures_for=lambda candidate, delta: _measures(),
        candidate_id_for=_candidate_ids(),
    )
    assert outcome.run_row.status == "succeeded"
