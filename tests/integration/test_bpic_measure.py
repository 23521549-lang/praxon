"""Test tích hợp cho driver đo BPIC 2015 (task 12.2) trên Postgres thật.

Chạy driver trên dữ liệu sinh nhỏ (20 trace giả mỗi đô thị, không phải
BPIC thật) + file khóa tạm + vai coordinator tạm - chứng minh toàn bộ
đường đi (khóa -> đo -> ghi 35 hàng `run` + event -> báo cáo) qua DB thật.
Không chạy đo BPIC thật trong test (đó là lần chạy 12.2).
"""

from __future__ import annotations

import json
import secrets
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from psycopg import connect

from praxon_core.datasets.split import split_log
from praxon_core.eval.bpic_measure import (
    EXIT_DATA,
    EXIT_OK,
    _bpic_data_hash,
    main,
)
from praxon_core.eval.experiments import CONDITIONS
from praxon_core.learning.coordinator import (
    compute_config_hash,
    merge_data_hash,
)
from praxon_core.repositories import migrate as migrations
from praxon_core.settings import load_settings

from .conftest import ADMIN_DSN, one

MODEL_ID = "Qwen/Qwen3-8B-GGUF"
MODEL_REVISION = "7c41481f57cb95916b40956ab2f0b139b296d974"
SEED = 42
TENANTS = ("m1", "m2", "m3", "m4", "m5")

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

_ACTIVITIES = ("nop_don", "duyet", "hoan_thanh")


def _write_tiny_xes(path: Path, municipality: int) -> None:
    """20 trace giả: mỗi trace xoay thứ tự 3 hoạt động, ngày bắt đầu tăng dần."""
    base = datetime(2012, 1, 1, tzinfo=UTC) + timedelta(days=30 * municipality)
    lines = [
        '<?xml version="1.0" encoding="UTF-8" ?>',
        '<log xes.version="1.0" xes.features="nested-attributes" '
        'xmlns="http://www.xes-standard.org/">',
    ]
    for case_index in range(20):
        start = base + timedelta(days=case_index)
        order = [_ACTIVITIES[(case_index + offset) % len(_ACTIVITIES)] for offset in range(3)]
        stamp = start.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        lines.append("\t<trace>")
        lines.append(f'\t\t<string key="concept:name" value="case-{case_index}"/>')
        lines.append(f'\t\t<date key="startDate" value="{stamp}"/>')
        for step, activity in enumerate(order):
            event_stamp = (start + timedelta(hours=step)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
            lines.append("\t\t<event>")
            lines.append(f'\t\t\t<string key="concept:name" value="{activity}"/>')
            lines.append(f'\t\t\t<date key="time:timestamp" value="{event_stamp}"/>')
            lines.append("\t\t</event>")
        lines.append("\t</trace>")
    lines.append("</log>")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_lock(tmp_path: Path, config: Path, *, data_hash: str) -> Path:
    """Bản ghi khóa tạm: hash cấu hình tính thật + data_hash tính thật."""
    config_hash = compute_config_hash(load_settings(config))
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


def _count_runs(tenant_id: str, *, status: str | None = None) -> int:
    """Đếm hàng `run` của một tenant (lọc trạng thái nếu có)."""
    with connect(ADMIN_DSN) as conn:
        if status is None:
            return int(
                one(conn, "SELECT COUNT(*) FROM run WHERE tenant_id = %s", (tenant_id,))[0]
            )
        return int(
            one(
                conn,
                "SELECT COUNT(*) FROM run WHERE tenant_id = %s AND status = %s",
                (tenant_id, status),
            )[0]
        )


def _count_events_for_runs(run_ids: list[str]) -> int:
    """Đếm event gắn với các run id đã cho."""
    with connect(ADMIN_DSN) as conn:
        return int(
            one(
                conn,
                "SELECT COUNT(*) FROM event WHERE run_id = ANY(%s)",
                (run_ids,),
            )[0]
        )


def test_driver_do_35_cap_va_ghi_db_va_bao_cao(
    pg: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    file_hashes: list[str] = []
    for index in range(1, 6):
        path = cache_dir / f"BPIC15_{index}.xes"
        _write_tiny_xes(path, index)
        file_hashes.append(split_log(path, index).file_sha256)
    data_hash = merge_data_hash(bpic_hash=_bpic_data_hash(tuple(file_hashes), (1, 2, 3, 4, 5)))
    config = tmp_path / "phan-do.toml"
    config.write_text(_CONFIG_TOML, encoding="utf-8")
    password = secrets.token_hex(8)
    # DSN gốc mang mật khẩu chung của năm vai coordinator: driver đổi user
    # thành <tenant>__coordinator, giữ nguyên mật khẩu này.
    parts = urllib.parse.urlsplit(ADMIN_DSN)
    base_dsn = urllib.parse.urlunsplit(
        (
            parts.scheme,
            f"{parts.username}:{urllib.parse.quote(password)}"
            f"@{parts.hostname}:{parts.port or 5432}",
            parts.path,
            "",
            "",
        )
    )
    monkeypatch.setenv("PRAXON_DATABASE_URL", base_dsn)
    lock = _write_lock(tmp_path, config, data_hash=data_hash)
    doc_laws = tmp_path / "luat.txt"
    doc_laws.write_text(_DOC_LAWS, encoding="utf-8")
    report_path = tmp_path / "ket-qua.json"

    for tenant_id in TENANTS:
        migrations.provision_tenant(ADMIN_DSN, tenant_id, password)

    args = [
        "--config",
        str(config),
        "--lock",
        str(lock),
        "--doc-laws",
        str(doc_laws),
        "--cache-dir",
        str(cache_dir),
        "--report",
        str(report_path),
    ]
    assert main(args) == EXIT_OK

    # 35 hàng run: 7 mỗi tenant, đều succeeded, token 0, khớp khóa.
    total = 0
    all_run_ids: list[str] = []
    with connect(ADMIN_DSN) as conn:
        for tenant_id in TENANTS:
            count = _count_runs(tenant_id, status="succeeded")
            assert count == 7
            total += count
            rows = conn.execute(
                "SELECT id::text, tokens_in, tokens_out, config_hash, data_hash, seed "
                "FROM run WHERE tenant_id = %s AND status = 'succeeded'",
                (tenant_id,),
            ).fetchall()
            assert len(rows) == 7
            for run_id, tokens_in, tokens_out, config_hash, row_data_hash, seed in rows:
                assert tokens_in == 0
                assert tokens_out == 0
                assert config_hash == compute_config_hash(load_settings(config))
                assert row_data_hash == data_hash
                assert seed == SEED
                all_run_ids.append(run_id)
    assert total == 35
    assert _count_events_for_runs(all_run_ids) == 35

    # Báo cáo JSON: 35 hàng, run id khớp DB, đã công bố, chỉ số trong [0, 1].
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["task"] == "12.2"
    assert report["published"] is True
    assert report["data_hash"] == data_hash
    assert report["seed"] == SEED
    assert report["document_rules"] == 2
    assert report["document_base_condition"] in ("Phân tầng đồng thuận", "Phân tầng phủ quyết")
    assert len(report["rows"]) == 35
    assert [row["condition"] for row in report["rows"][:7]] == list(CONDITIONS)
    assert [row["tenant_id"] for row in report["rows"][:7]] == ["m1"] * 7
    assert {row["run_id"] for row in report["rows"]} == set(all_run_ids)
    for row in report["rows"]:
        assert row["status"] == "succeeded"
        assert row["n_measure"] == 4
        for metric in row["metrics"].values():
            assert 0.0 <= metric["value"] <= 1.0
            assert metric["lower"] <= metric["value"] <= metric["upper"]

    # Chạy lại cùng khóa/commit/seed thì bị chốt đã-công-bố chặn (mã 1).
    assert main(args) == EXIT_DATA
    assert sum(_count_runs(tenant_id) for tenant_id in TENANTS) == 35

    # Chỉ 12.3 được mở chốt bằng --allow-rerun: chạy lại được (mã 0, +35 hàng).
    assert main([*args, "--allow-rerun"]) == EXIT_OK
    assert sum(_count_runs(tenant_id) for tenant_id in TENANTS) == 70
