"""Ghi event qua vai coordinator (plan con 7, task 7.7).

Nơi DUY NHẤT trong praxon_core được INSERT vào bảng event: mọi truy cập dữ
liệu đi qua repositories (hợp đồng driver-db-chi-trong-repositories). Event
chỉ thêm, không UPDATE/DELETE ở bất cứ vai nào: V2 chỉ cấp SELECT + INSERT
cho coordinator, không vai nào có UPDATE hay DELETE trên bảng này.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg import Connection


@dataclass(frozen=True)
class EventRow:
    """Một hàng event, đủ cột NOT NULL của bảng event (V1)."""

    tenant_id: str
    actor: str
    action: str
    payload_hash: str
    run_id: str | None = None
    target: str | None = None
    decision: str | None = None
    decided_by: str | None = None
    reason: str | None = None


def insert_event(conn: Connection[Any], event: EventRow) -> str:
    """INSERT một event; trả event_id (uuid) của hàng mới.

    Quyền + RLS chặn ở tầng DB: chỉ coordinator được INSERT; không vai nào
    UPDATE hay DELETE được bảng này.
    """
    row = conn.execute(
        "INSERT INTO event (run_id, tenant_id, actor, action, target, decision, "
        "decided_by, reason, payload_hash) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING event_id",
        (
            event.run_id,
            event.tenant_id,
            event.actor,
            event.action,
            event.target,
            event.decision,
            event.decided_by,
            event.reason,
            event.payload_hash,
        ),
    ).fetchone()
    assert row is not None  # INSERT ... RETURNING luôn trả một hàng
    return str(row[0])
