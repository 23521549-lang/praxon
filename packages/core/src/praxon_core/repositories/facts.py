"""Ghi fact qua vai applier/promoter (plan con 7, task 7.6).

Nơi DUY NHẤT trong praxon_core được INSERT vào bảng fact: mọi truy cập dữ
liệu đi qua repositories (hợp đồng driver-db-chi-trong-repositories). Áp
candidate là lũy đẳng (BĐ6): candidate_id là UNIQUE trên fact nên áp lại
cùng candidate thì ON CONFLICT DO NOTHING, không tạo hàng mới.

Đóng fact (task P, ngữ nghĩa RETIRE/CONTRADICT) cũng chỉ ở đây:
`close_fact` là hàm UPDATE duy nhất, chỉ chạm 2 cột `known_during` +
`status` (đúng GRANT ở V2 — sửa cột khác bị chặn ở tầng quyền).
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


@dataclass(frozen=True)
class FactClose:
    """Lệnh đóng một fact hiện hành (task P, ngữ nghĩa RETIRE/CONTRADICT).

    `fact_id` là id của fact cần đóng; `retired_at` là thời điểm fact nghỉ
    (do coordinator truyền vào — thời điểm duyệt/áp; hàm thuần không tự
    lấy giờ). `retired_at` phải sau thời điểm fact bắt đầu được tin
    (`lower(known_during)`, tức lúc INSERT) — coordinator luôn truyền
    thời điểm duyệt/áp nên điều kiện này thỏa.
    """

    fact_id: str
    retired_at: datetime


def close_fact(conn: Connection[Any], close: FactClose) -> bool:
    """Đóng một fact: status → 'retired', thu hẹp `known_during` về lúc nghỉ.

    Chỉ UPDATE 2 cột `known_during` + `status` (đúng GRANT ở V2 + policy
    `fact_close` ở V3). Trả True nếu có hàng được cập nhật, False nếu
    không tìm thấy fact hoặc fact đã retired (đóng lại không làm gì).

    Thu hẹp `known_during` là giả thuyết H1 (đúng mô hình song thời gian,
    spec dòng 41: `known_during` là khoảng hệ tin fact đúng — khi fact
    nghỉ, hệ không còn tin nó): fact đã nghỉ vẫn còn lại làm lịch sử, và
    sau này thêm lại cùng khóa không bị BĐ5 chặn (vì `known_during` đã
    đóng). Phương án dự phòng (nếu không đồng ý thu hẹp): chỉ UPDATE
    `status`.

    CONTRADICT cần đóng cũ + thêm mới trong MỘT giao dịch (BĐ5, spec dòng
    64): coordinator gọi `close_fact` rồi `insert_fact` trên cùng một
    connection — không gọi riêng lẻ.
    """
    cursor = conn.execute(
        "UPDATE fact SET status = 'retired', "
        "known_during = tstzrange(lower(known_during), %s, '[)') "
        "WHERE id = %s::uuid AND status <> 'retired'",
        (close.retired_at, close.fact_id),
    )
    return cursor.rowcount == 1
