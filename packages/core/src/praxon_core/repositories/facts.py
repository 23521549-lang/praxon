"""Ghi fact qua vai applier/promoter (plan con 7, task 7.6).

Nơi DUY NHẤT trong praxon_core được INSERT vào bảng fact: mọi truy cập dữ
liệu đi qua repositories (hợp đồng driver-db-chi-trong-repositories). Áp
candidate là lũy đẳng (BĐ6): candidate_id là UNIQUE trên fact nên áp lại
cùng candidate thì ON CONFLICT DO NOTHING, không tạo hàng mới.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection


@dataclass(frozen=True)
class FactRow:
    """Một hàng fact, đủ cột NOT NULL của bảng fact (V1)."""

    tenant_id: str
    scope: str
    canonical_key: str
    template: str
    statement: str
    status: str
    support: int
    confidence: float
    valid_start: datetime
    valid_end: datetime | None
    activation: str | None = None
    target: str | None = None
    condition: str | None = None
    source_episode_ids: tuple[UUID, ...] = ()
    candidate_id: str | None = None


def insert_fact(conn: Connection[Any], fact: FactRow) -> bool:
    """INSERT một fact; trả True nếu ghi hàng mới, False nếu candidate đã áp.

    ON CONFLICT (candidate_id) DO NOTHING: áp lại cùng candidate không làm gì
    (BĐ6). candidate_id NULL thì không xung đột (fact seed, V4 cho qua).
    Quyền + RLS + trigger V4 vẫn chặn ở tầng DB: vai khác, candidate chưa duyệt
    hay sai tenant đều lỗi trước khi tới được đây.
    """
    cursor = conn.execute(
        "INSERT INTO fact (tenant_id, scope, canonical_key, template, activation, "
        "target, condition, statement, status, support, confidence, valid_during, "
        "source_episode_ids, candidate_id) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
        "tstzrange(%s, %s, '[)'), %s::uuid[], %s) "
        "ON CONFLICT (candidate_id) DO NOTHING",
        (
            fact.tenant_id,
            fact.scope,
            fact.canonical_key,
            fact.template,
            fact.activation,
            fact.target,
            fact.condition,
            fact.statement,
            fact.status,
            fact.support,
            fact.confidence,
            fact.valid_start,
            fact.valid_end,
            list(fact.source_episode_ids),
            fact.candidate_id,
        ),
    )
    return cursor.rowcount == 1
