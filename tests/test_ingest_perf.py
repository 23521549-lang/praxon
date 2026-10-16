"""Hiệu năng (task 2.1) và tính quyết định của data_hash (task 2.3)."""

from __future__ import annotations

import hashlib
import json
import time

from praxon_core.ingest.log import canonical_hash, load_log
from praxon_core.ingest.schema import Log


def _make_lines(n: int, tz: str, hour_shift: int) -> list[str]:
    lines = []
    for i in range(n):
        hour = (i % 12) + hour_shift
        lines.append(
            json.dumps(
                {
                    "case_id": f"case-{i % 500}",
                    "variant": "standard",
                    "activity": f"activity-{i % 7}",
                    "occurred_at": f"2015-06-01T{hour:02d}:00:00{tz}",
                }
            )
        )
    return lines


def test_10000_dong_duoi_2_giay():
    # Đúng tiêu chí nghiệm thu task 2.1. Đo trên máy phát triển ~0.2s,
    # ngưỡng 2s cho headroom ~10x để không flake trên CI.
    lines = _make_lines(10_000, "+07:00", 7)
    start = time.perf_counter()
    log = load_log(lines)
    elapsed = time.perf_counter() - start
    assert len(log.cases) == 500
    assert elapsed < 2.0


def test_cung_log_hai_mui_gio_cho_cung_data_hash():
    # Cùng một thời điểm viết ở hai múi giờ phải cho cùng hash (task 2.3):
    # 07:00+07:00 và 00:00Z là một thời điểm.
    log_a = load_log(_make_lines(200, "+07:00", 7))
    log_b = load_log(_make_lines(200, "Z", 0))
    assert log_a.data_hash == log_b.data_hash
    # Tính lại độc lập, không dùng canonical_hash cần kiểm.
    assert log_a.data_hash == _hash_doc_lap(log_a)
    assert canonical_hash(log_b) == log_b.data_hash


def _hash_doc_lap(log: Log) -> str:
    """Tính lại data_hash độc lập để đối chiếu, không dùng hàm cần kiểm."""
    payload = [
        {
            "case_id": c.case_id,
            "variant": c.variant,
            "events": [
                {"activity": e.activity, "occurred_at": e.occurred_at.isoformat()}
                for e in sorted(c.events, key=lambda e: (e.occurred_at, e.activity))
            ],
        }
        for c in sorted(log.cases, key=lambda c: c.case_id)
    ]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
