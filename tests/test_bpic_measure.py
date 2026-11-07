"""Test unit cho driver đo BPIC 2015 (task 12.2) - không cần DB/dữ liệu thật.

Kiểm: đối chiếu khóa, chốt đã-công-bố, file luật sai provenance thì từ
chối, định dạng báo cáo JSON, mã thoát từng trường hợp. Mọi file khóa
đều là file tạm tạo trong thư mục tạm (khóa thật chưa có lúc này).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

import pytest

from praxon_core.eval.bpic_measure import (
    EXIT_BUDGET_EXCEEDED,
    EXIT_DATA,
    EXIT_DB,
    EXIT_OK,
    _bpic_data_hash,
    _code_commit,
    _count_published,
    _dsn_for_tenant,
    _format_text_report,
    _load_and_check_lock,
    _parse_doc_law_key,
    _read_doc_law_file,
    _read_lock_record,
    _repo_root,
    _row_payload_json,
    run,
)
from praxon_core.eval.experiments import CONDITIONS, TenantData
from praxon_core.eval.ground_truth import GroundTruth
from praxon_core.eval.report import (
    MetricCI,
    MetricsWithCI,
    TenantConditionRow,
)
from praxon_core.learning.coordinator import (
    compute_config_hash,
    merge_data_hash,
)
from praxon_core.settings import load_settings

MODEL_ID = "Qwen/Qwen3-8B-GGUF"
MODEL_REVISION = "7c41481f57cb95916b40956ab2f0b139b296d974"
SEED = 42

_CONFIG_TOML = """\
bootstrap_draws = 1000
openai_base_url = "http://localhost:8080/v1"
cpu_model_base_url = "http://localhost:8080/v1"
model_id = "Qwen/Qwen3-8B-GGUF"
model_revision = "7c41481f57cb95916b40956ab2f0b139b296d974"
model_max_retries = 3
model_retry_base_delay_seconds = 1.0
reflector_batch_size = 10
reflector_max_insights_per_batch = 20
checkpoint_every_n_cases = 100
checkpoint_store = "local"
token_budget_total = 0
token_budget_reserve_per_call = 2048
"""

_DOC_LAWS = """\
# model_id: Qwen/Qwen3-8B-GGUF
# model_revision: 7c41481f57cb95916b40956ab2f0b139b296d974
# extracted_at: 2026-11-07T00:00:00Z
# seed: 42
# beta_support: 0.5
# beta_confidence: 0.5
# n_rules_extracted: 2
# n_rules_gated: 2
precedence(hoan_thanh, nop_don)
response(nop_don, duyet)
"""

_FAKE_DATA_HASH = "0" * 64


def _write_lock(tmp_path: Path, *, config_hash: str, data_hash: str = _FAKE_DATA_HASH) -> Path:
    """Bản ghi khóa tạm khớp hash cấu hình đã cho."""
    lock = tmp_path / "phan-do.lock.toml"
    lock.write_text(
        f"""\
locked_config_hash = "{config_hash}"
lock_commit = "{"0" * 40}"
code_commit = "{"0" * 40}"
seed = {SEED}
model_id = "{MODEL_ID}"
model_revision = "{MODEL_REVISION}"
data_hash = "{data_hash}"
cache = "empty"
locked_at = "CHUA-KHOA"
locked_by = "CHUA-KHOA"
""",
        encoding="utf-8",
    )
    return lock


@pytest.fixture
def locked_pair(tmp_path, monkeypatch):
    """Cặp (config, lock) tạm khớp nhau; trả (config_path, lock_path)."""
    monkeypatch.setenv(
        "PRAXON_DATABASE_URL", "postgresql://praxon:praxon@localhost:5432/praxon"
    )
    config = tmp_path / "phan-do.toml"
    config.write_text(_CONFIG_TOML, encoding="utf-8")
    config_hash = compute_config_hash(load_settings(config))
    lock = _write_lock(tmp_path, config_hash=config_hash)
    return config, lock


def _fake_metrics() -> MetricsWithCI:
    """Bốn chỉ số giả (mỗi cái kèm khoảng tin cậy) cho hàng báo cáo giả."""
    return MetricsWithCI(
        precision=MetricCI(0.8, 0.7, 0.9),
        recall=MetricCI(0.6, 0.5, 0.7),
        violation_rate=MetricCI(0.05, 0.01, 0.09),
        negative_transfer=MetricCI(0.02, 0.0, 0.04),
    )


def _fake_row(tenant_id: str, condition: str) -> TenantConditionRow:
    """Một hàng báo cáo giả (35 hàng giả ghép thành báo cáo mẫu)."""
    return TenantConditionRow(
        tenant_id=tenant_id,
        condition=condition,
        source="bpic2015-test-split",
        n_train=719,
        n_measure=240,
        n_reference=1730,
        n_rules=732,
        metrics=_fake_metrics(),
    )


def _fake_tenant(tenant_id: str) -> TenantData:
    """Một tenant giả (chỉ cần tenant_id cho kiểm tra trước của driver)."""
    return TenantData(
        tenant_id=tenant_id,
        train_traces=(),
        measure_traces=(),
        ground_truth=GroundTruth(
            tenant_id=tenant_id,
            reference=frozenset(),
            source="bpic2015-test-split",
        ),
        own_rules=frozenset(),
    )


class _FakeCursor:
    """Con trỏ giả: trả một hàng đếm (COUNT) hoặc (1,) cho SELECT 1."""

    def __init__(self, count: int) -> None:
        self._count = count

    def fetchone(self) -> tuple[int]:
        return (self._count,)


class _FakeConnection:
    """Kết nối DB giả cho kiểm chốt đã-công-bố (không nối DB thật)."""

    def __init__(self, published_count: int) -> None:
        self._published_count = published_count
        self.closed = False

    def execute(self, query: str, params: Sequence[Any] | None = None) -> _FakeCursor:
        if "COUNT(*)" in query:
            return _FakeCursor(self._published_count)
        return _FakeCursor(1)

    def close(self) -> None:
        self.closed = True


def test_khoa_khop_nhau_thi_nap_duoc(locked_pair):
    config, lock = locked_pair
    settings, record = _load_and_check_lock(config, lock)
    assert settings.model_id == MODEL_ID
    assert record.seed == SEED
    assert record.model_revision == MODEL_REVISION
    assert record.data_hash == _FAKE_DATA_HASH


def test_khoa_lech_hash_thi_tu_choi(tmp_path, locked_pair, monkeypatch):
    config, _lock = locked_pair
    monkeypatch.setenv(
        "PRAXON_DATABASE_URL", "postgresql://praxon:praxon@localhost:5432/praxon"
    )
    bad_lock = _write_lock(tmp_path, config_hash="0" * 64)
    with pytest.raises(ValueError, match="khác khóa"):
        _load_and_check_lock(config, bad_lock)


def test_thieu_file_khoa_thi_tu_choi(locked_pair, tmp_path):
    config, _lock = locked_pair
    with pytest.raises(ValueError, match="không đọc được bản ghi khóa"):
        _load_and_check_lock(config, tmp_path / "khong-co.lock.toml")


def test_thieu_file_cau_hinh_thi_tu_choi(locked_pair, tmp_path):
    _config, lock = locked_pair
    with pytest.raises(ValueError, match="không đọc được cấu hình đo"):
        _load_and_check_lock(tmp_path / "khong-co.toml", lock)


def test_ban_ghi_khoa_thieu_truong_thi_tu_choi(tmp_path):
    lock = tmp_path / "thieu.lock.toml"
    lock.write_text(
        'locked_config_hash = "' + "a" * 64 + '"\nmodel_id = "Qwen/Qwen3-8B-GGUF"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="thiếu seed"):
        _read_lock_record(lock)


def test_ban_ghi_khoa_data_hash_sai_dinh_dang_thi_tu_choi(tmp_path):
    lock = tmp_path / "sai-hash.lock.toml"
    lock.write_text(
        'locked_config_hash = "'
        + "a" * 64
        + '"\nseed = 42\nmodel_id = "Qwen/Qwen3-8B-GGUF"\n'
        + 'model_revision = "7c41481f57cb95916b40956ab2f0b139b296d974"\n'
        + 'data_hash = "khong-phai-hex"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="data_hash"):
        _read_lock_record(lock)


def test_file_luat_hop_le_thi_doc_duoc(tmp_path):
    path = tmp_path / "luat.txt"
    path.write_text(_DOC_LAWS, encoding="utf-8")
    provenance, rules = _read_doc_law_file(
        path, model_id=MODEL_ID, model_revision=MODEL_REVISION
    )
    assert provenance.model_id == MODEL_ID
    assert provenance.n_rules_extracted == 2
    assert provenance.n_rules_gated == 2
    assert [rule.canonical_key for rule in rules] == [
        "precedence(hoan_thanh, nop_don)",
        "response(nop_don, duyet)",
    ]


def test_file_luat_sai_model_thi_tu_choi(tmp_path):
    path = tmp_path / "luat-sai-model.txt"
    path.write_text(
        _DOC_LAWS.replace(MODEL_ID, "Khac/Khac-8B"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="sai provenance"):
        _read_doc_law_file(path, model_id=MODEL_ID, model_revision=MODEL_REVISION)


def test_file_luat_sai_revision_thi_tu_choi(tmp_path):
    path = tmp_path / "luat-sai-rev.txt"
    path.write_text(
        _DOC_LAWS.replace(MODEL_REVISION, "0" * 40),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="sai provenance"):
        _read_doc_law_file(path, model_id=MODEL_ID, model_revision=MODEL_REVISION)


def test_file_luat_khoa_la_thi_tu_choi(tmp_path):
    path = tmp_path / "luat-la.txt"
    path.write_text(
        "# model_id: Qwen/Qwen3-8B-GGUF\n"
        f"# model_revision: {MODEL_REVISION}\n"
        "khong_phai_luat\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="khóa luật tài liệu lạ"):
        _read_doc_law_file(path, model_id=MODEL_ID, model_revision=MODEL_REVISION)


def test_file_luat_trung_khoa_thi_tu_choi(tmp_path):
    path = tmp_path / "luat-trung.txt"
    path.write_text(
        "# model_id: Qwen/Qwen3-8B-GGUF\n"
        f"# model_revision: {MODEL_REVISION}\n"
        "response(nop_don, duyet)\n"
        "response(nop_don, duyet)\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="trùng nhau"):
        _read_doc_law_file(path, model_id=MODEL_ID, model_revision=MODEL_REVISION)


def test_file_luat_chua_sap_xep_thi_tu_choi(tmp_path):
    path = tmp_path / "luat-chua-xep.txt"
    path.write_text(
        "# model_id: Qwen/Qwen3-8B-GGUF\n"
        f"# model_revision: {MODEL_REVISION}\n"
        "response(nop_don, duyet)\n"
        "precedence(hoan_thanh, nop_don)\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="chưa sắp xếp"):
        _read_doc_law_file(path, model_id=MODEL_ID, model_revision=MODEL_REVISION)


def test_thieu_file_luat_thi_tu_choi(tmp_path):
    with pytest.raises(ValueError, match="không đọc được file luật tài liệu"):
        _read_doc_law_file(
            tmp_path / "khong-co.txt",
            model_id=MODEL_ID,
            model_revision=MODEL_REVISION,
        )


def test_khoa_luat_hop_le():
    rule = _parse_doc_law_key("response(nop_don, duyet)")
    assert rule.template == "response"
    assert rule.first == "nop_don"
    assert rule.second == "duyet"
    assert rule.canonical_key == "response(nop_don, duyet)"


def test_khoa_luat_mau_la_thi_tu_choi():
    with pytest.raises(ValueError, match="khóa luật tài liệu lạ"):
        _parse_doc_law_key("eventually(nop_don, duyet)")


def test_khoa_luat_thieu_ngoac_thi_tu_choi():
    with pytest.raises(ValueError, match="khóa luật tài liệu lạ"):
        _parse_doc_law_key("response nop_don, duyet")


def test_khoa_luat_hoat_dong_chua_phay_thi_tu_choi():
    with pytest.raises(ValueError, match="mơ hồ"):
        _parse_doc_law_key("response(nop_don, x, duyet)")


def test_data_hash_nua_bpic_on_dinh_va_khac_nua_goc():
    hashes = ("a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64)
    first = _bpic_data_hash(hashes, (1, 2, 3, 4, 5))
    second = _bpic_data_hash(hashes, (1, 2, 3, 4, 5))
    assert first == second
    merged = merge_data_hash(bpic_hash=first)
    assert merged != first
    assert re.fullmatch(r"[0-9a-f]{64}", merged)


def test_data_hash_doi_thu_tu_dau_vao_khong_doi():
    hashes = ("a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64)
    assert _bpic_data_hash(hashes, (1, 2, 3, 4, 5)) == _bpic_data_hash(
        tuple(reversed(hashes)), (5, 4, 3, 2, 1)
    )


def test_dsn_doi_user_giu_mat_khau_host_port_db():
    dsn = _dsn_for_tenant("postgresql://praxon:mat-khau-moi@localhost:5432/praxon", "m1")
    assert dsn == "postgresql://m1__coordinator:mat-khau-moi@localhost:5432/praxon"


def test_dsn_khong_mat_khau_thi_suy_ra_cung_khong_co():
    dsn = _dsn_for_tenant("postgresql://postgres@localhost:5432/praxon", "m1")
    assert dsn == "postgresql://m1__coordinator@localhost:5432/praxon"


def test_dem_da_cong_bo_bang_ket_noi_gia():
    assert (
        _count_published(
            _FakeConnection(35),
            tenant_id="m1",
            config_hash="a" * 64,
            data_hash="b" * 64,
            code_commit="c" * 40,
            seed=SEED,
        )
        == 35
    )
    assert (
        _count_published(
            _FakeConnection(10),
            tenant_id="m1",
            config_hash="a" * 64,
            data_hash="b" * 64,
            code_commit="c" * 40,
            seed=SEED,
        )
        == 10
    )


def test_bao_cao_json_35_hang_du_truong():
    rows = [
        _row_payload_json(_fake_row(f"m{index}", condition))
        for index in range(1, 6)
        for condition in CONDITIONS
    ]
    assert len(rows) == 35
    first = rows[0]
    assert first["tenant_id"] == "m1"
    assert first["condition"] == CONDITIONS[0]
    assert first["n_train"] == 719
    assert first["n_measure"] == 240
    assert first["n_reference"] == 1730
    assert first["n_rules"] == 732
    assert set(first["metrics"]) == {
        "precision",
        "recall",
        "violation_rate",
        "negative_transfer",
    }
    assert first["metrics"]["precision"] == {"value": 0.8, "lower": 0.7, "upper": 0.9}
    assert [row["condition"] for row in rows[:7]] == list(CONDITIONS)


def test_bao_cao_chu_hien_du_35_hang_va_hang_failed():
    rows = [
        {
            **_row_payload_json(_fake_row("m1", CONDITIONS[0])),
            "run_id": "r1",
            "status": "succeeded",
            "wall_time": 1.0,
        },
        {
            "tenant_id": "m1",
            "condition": CONDITIONS[1],
            "source": "",
            "n_train": 0,
            "n_measure": 0,
            "n_reference": 0,
            "n_rules": 0,
            "metrics": None,
            "run_id": "r2",
            "status": "failed",
            "wall_time": 0.5,
            "reason": "đo hỏng: lỗi giả",
        },
    ]
    text = _format_text_report(rows, note="ghi chú giả", published=False, wall_time=1.5)
    assert "Tenant m1 - Chỉ Declare" in text
    assert "precision:        0.800 [0.700, 0.900]" in text
    assert "Tenant m1 - Cách ly: FAILED (đo hỏng: lỗi giả)" in text
    assert "không (lần chạy hỏng)" in text


def test_ma_thoat_theo_quy_uoc_voi_10_4():
    assert EXIT_OK == 0
    assert EXIT_DATA == 1
    assert EXIT_DB == 2
    assert EXIT_BUDGET_EXCEEDED == 3


def test_code_commit_la_hex_40_ky_tu():
    assert re.fullmatch(r"[0-9a-f]{40}", _code_commit())


def test_thu_muc_goc_repo_co_git():
    assert (_repo_root() / ".git").exists()


def test_khoa_lech_thi_main_tra_1(locked_pair, tmp_path, monkeypatch):
    config, _lock = locked_pair
    monkeypatch.setenv(
        "PRAXON_DATABASE_URL", "postgresql://praxon:praxon@localhost:5432/praxon"
    )
    bad_lock = _write_lock(tmp_path, config_hash="0" * 64)
    doc_laws = tmp_path / "luat.txt"
    doc_laws.write_text(_DOC_LAWS, encoding="utf-8")
    assert (
        run(
            config_path=config,
            lock_path=bad_lock,
            doc_laws_path=doc_laws,
            cache_dir=tmp_path,
            report_path=tmp_path / "ket-qua.json",
            allow_rerun=False,
        )
        == EXIT_DATA
    )


def test_thieu_file_luat_thi_main_tra_1(locked_pair, tmp_path):
    config, lock = locked_pair
    assert (
        run(
            config_path=config,
            lock_path=lock,
            doc_laws_path=tmp_path / "khong-co.txt",
            cache_dir=tmp_path,
            report_path=tmp_path / "ket-qua.json",
            allow_rerun=False,
        )
        == EXIT_DATA
    )


def test_thieu_file_xes_thi_main_tra_1(locked_pair, tmp_path):
    config, lock = locked_pair
    doc_laws = tmp_path / "luat.txt"
    doc_laws.write_text(_DOC_LAWS, encoding="utf-8")
    assert (
        run(
            config_path=config,
            lock_path=lock,
            doc_laws_path=doc_laws,
            cache_dir=tmp_path,
            report_path=tmp_path / "ket-qua.json",
            allow_rerun=False,
        )
        == EXIT_DATA
    )


def test_chot_da_cong_bo_chan_chay_lai(locked_pair, tmp_path, monkeypatch):
    """Đủ 35 hàng succeeded khớp khóa/commit/seed thì từ chối mã 1."""
    import praxon_core.eval.bpic_measure as measure

    config, _lock = locked_pair
    doc_laws = tmp_path / "luat.txt"
    doc_laws.write_text(_DOC_LAWS, encoding="utf-8")
    file_hashes = ("a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64)
    data_hash = merge_data_hash(bpic_hash=_bpic_data_hash(file_hashes, (1, 2, 3, 4, 5)))
    lock = _write_lock(
        tmp_path,
        config_hash=compute_config_hash(load_settings(config)),
        data_hash=data_hash,
    )
    tenants = [_fake_tenant(f"m{index}") for index in range(1, 6)]
    monkeypatch.setattr(
        measure,
        "_load_tenant_data",
        lambda cache_dir: (tenants, file_hashes, (1, 2, 3, 4, 5)),
    )
    fake_conns = {f"m{index}": _FakeConnection(7) for index in range(1, 6)}
    monkeypatch.setattr(
        measure, "_connect", lambda dsn: fake_conns[dsn.split("://")[1].split("__")[0]]
    )
    called: list[str] = []

    def _fake_measure_and_write(**kwargs: object) -> int:
        called.append("do")
        return EXIT_OK

    monkeypatch.setattr(measure, "_measure_and_write", _fake_measure_and_write)
    code_commit = "c" * 40
    exit_code = run(
        config_path=config,
        lock_path=lock,
        doc_laws_path=doc_laws,
        cache_dir=tmp_path,
        report_path=tmp_path / "ket-qua.json",
        allow_rerun=False,
        code_commit=code_commit,
    )
    assert exit_code == EXIT_DATA
    assert called == []


def test_chot_da_cong_bo_khong_chan_khi_chua_du_35(locked_pair, tmp_path, monkeypatch):
    """Mới 10 hàng succeeded thì chạy tiếp (lần chạy dở trước đó)."""
    import praxon_core.eval.bpic_measure as measure

    config, _lock = locked_pair
    doc_laws = tmp_path / "luat.txt"
    doc_laws.write_text(_DOC_LAWS, encoding="utf-8")
    file_hashes = ("a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64)
    data_hash = merge_data_hash(bpic_hash=_bpic_data_hash(file_hashes, (1, 2, 3, 4, 5)))
    lock = _write_lock(
        tmp_path,
        config_hash=compute_config_hash(load_settings(config)),
        data_hash=data_hash,
    )
    tenants = [_fake_tenant(f"m{index}") for index in range(1, 6)]
    monkeypatch.setattr(
        measure,
        "_load_tenant_data",
        lambda cache_dir: (tenants, file_hashes, (1, 2, 3, 4, 5)),
    )
    fake_conns = {f"m{index}": _FakeConnection(2) for index in range(1, 6)}
    monkeypatch.setattr(
        measure, "_connect", lambda dsn: fake_conns[dsn.split("://")[1].split("__")[0]]
    )
    called: list[str] = []

    def _fake_measure_and_write(**kwargs: object) -> int:
        called.append("do")
        return EXIT_OK

    monkeypatch.setattr(measure, "_measure_and_write", _fake_measure_and_write)
    exit_code = run(
        config_path=config,
        lock_path=lock,
        doc_laws_path=doc_laws,
        cache_dir=tmp_path,
        report_path=tmp_path / "ket-qua.json",
        allow_rerun=False,
        code_commit="c" * 40,
    )
    assert exit_code == EXIT_OK
    assert called == ["do"]


def test_allow_rerun_mo_chot_da_cong_bo(locked_pair, tmp_path, monkeypatch):
    """Đủ 35 hàng nhưng có --allow-rerun (12.3) thì chạy tiếp."""
    import praxon_core.eval.bpic_measure as measure

    config, _lock = locked_pair
    doc_laws = tmp_path / "luat.txt"
    doc_laws.write_text(_DOC_LAWS, encoding="utf-8")
    file_hashes = ("a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64)
    data_hash = merge_data_hash(bpic_hash=_bpic_data_hash(file_hashes, (1, 2, 3, 4, 5)))
    lock = _write_lock(
        tmp_path,
        config_hash=compute_config_hash(load_settings(config)),
        data_hash=data_hash,
    )
    tenants = [_fake_tenant(f"m{index}") for index in range(1, 6)]
    monkeypatch.setattr(
        measure,
        "_load_tenant_data",
        lambda cache_dir: (tenants, file_hashes, (1, 2, 3, 4, 5)),
    )
    fake_conns = {f"m{index}": _FakeConnection(7) for index in range(1, 6)}
    monkeypatch.setattr(
        measure, "_connect", lambda dsn: fake_conns[dsn.split("://")[1].split("__")[0]]
    )
    called: list[str] = []

    def _fake_measure_and_write(**kwargs: object) -> int:
        called.append("do")
        return EXIT_OK

    monkeypatch.setattr(measure, "_measure_and_write", _fake_measure_and_write)
    exit_code = run(
        config_path=config,
        lock_path=lock,
        doc_laws_path=doc_laws,
        cache_dir=tmp_path,
        report_path=tmp_path / "ket-qua.json",
        allow_rerun=True,
        code_commit="c" * 40,
    )
    assert exit_code == EXIT_OK
    assert called == ["do"]


def test_loi_noi_db_thi_main_tra_2(locked_pair, tmp_path, monkeypatch):
    """Không nối được DB thì mã 2 (không phải lỗi dữ liệu)."""
    import praxon_core.eval.bpic_measure as measure

    config, _lock = locked_pair
    doc_laws = tmp_path / "luat.txt"
    doc_laws.write_text(_DOC_LAWS, encoding="utf-8")
    file_hashes = ("a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64)
    data_hash = merge_data_hash(bpic_hash=_bpic_data_hash(file_hashes, (1, 2, 3, 4, 5)))
    lock = _write_lock(
        tmp_path,
        config_hash=compute_config_hash(load_settings(config)),
        data_hash=data_hash,
    )
    tenants = [_fake_tenant(f"m{index}") for index in range(1, 6)]
    monkeypatch.setattr(
        measure,
        "_load_tenant_data",
        lambda cache_dir: (tenants, file_hashes, (1, 2, 3, 4, 5)),
    )

    def _connect_that_fails(dsn: str) -> NoReturn:
        raise ConnectionError("không nối được DB giả")

    monkeypatch.setattr(measure, "_connect", _connect_that_fails)
    assert (
        run(
            config_path=config,
            lock_path=lock,
            doc_laws_path=doc_laws,
            cache_dir=tmp_path,
            report_path=tmp_path / "ket-qua.json",
            allow_rerun=False,
            code_commit="c" * 40,
        )
        == EXIT_DB
    )


def test_module_khong_import_reflector_hay_model():
    """Driver đo không gọi mô hình: không có dòng import Reflector/model."""
    source = Path(__file__).resolve().parents[1] / (
        "packages/core/src/praxon_core/eval/bpic_measure.py"
    )
    import_lines = [
        line
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.startswith(("import ", "from "))
    ]
    assert not any("Reflector" in line for line in import_lines)
    assert not any("model_from_settings" in line for line in import_lines)
