"""Ghi event cho mỗi lần gọi vai và mỗi quyết định của Governor (task 7.7).

Bảng `event` ghi dấu mỗi bước của vòng học (BĐ1: append-only). Hai hàm ở đây
đều thuần: chúng chỉ xây một `EventRow`; người gọi ghi hàng đó qua
`repositories.events.insert_event` bằng kết nối dưới vai `coordinator` —
vai duy nhất được INSERT vào event (V2). Không hàm nào ở đây chạm DB hay
import driver DB (hợp đồng driver-db-chi-trong-repositories).
"""

from __future__ import annotations

import hashlib

from praxon_core.learning.candidate import GovernorResult
from praxon_core.repositories.events import EventRow


def _khong_rong(value: str, field: str) -> str:
    """Từ chối chuỗi rỗng/chỉ có khoảng trắng (cột NOT NULL vẫn nuốt được '')."""
    if not value.strip():
        raise ValueError(f"event thiếu {field}")
    return value


def role_call_event(
    *,
    tenant_id: str,
    actor: str,
    action: str,
    payload_hash: str,
    run_id: str | None = None,
    target: str | None = None,
    decision: str | None = None,
    decided_by: str | None = None,
    reason: str | None = None,
) -> EventRow:
    """Xây event cho một lần gọi vai (thuần, không ghi DB).

    `actor` là vai được gọi (curator/governor/applier/...), `action` là việc
    vai đó làm, `payload_hash` là hash của dữ liệu vào của lần gọi đó.
    """
    return EventRow(
        tenant_id=_khong_rong(tenant_id, "tenant_id"),
        actor=_khong_rong(actor, "actor"),
        action=_khong_rong(action, "action"),
        payload_hash=_khong_rong(payload_hash, "payload_hash"),
        run_id=run_id,
        target=target,
        decision=decision,
        decided_by=decided_by,
        reason=reason,
    )


def governor_decision_event(
    result: GovernorResult,
    *,
    tenant_id: str,
    run_id: str | None = None,
    candidate_id: str,
) -> EventRow:
    """Xây event cho một quyết định của Governor (thuần, không ghi DB).

    `actor` luôn là 'governor', `action` là 'decide', `target` là candidate
    được quyết, `decision` là verdict. `decided_by` lấy từ candidate (người
    duyệt ghi, luật 8); nếu Governor tự quyết mà candidate chưa có người
    duyệt thì ghi 'governor'. `payload_hash` là SHA-256 của candidate đã ghi
    `rule_id`/`metrics_at_decision`, để chạy lại ra đúng quyết định cũ.

    `run_id` để None khi coordinator xây event trước lúc ghi `run` (id
    chỉ có sau `insert_run` — người gọi điền vào bằng `dataclasses.replace`
    trước khi ghi event); `EventRow` vốn đã cho `run_id` None.
    """
    candidate = result.candidate
    payload_hash = hashlib.sha256(candidate.model_dump_json().encode("utf-8")).hexdigest()
    return EventRow(
        tenant_id=_khong_rong(tenant_id, "tenant_id"),
        actor="governor",
        action="decide",
        payload_hash=payload_hash,
        run_id=run_id,
        target=_khong_rong(candidate_id, "candidate_id"),
        decision=result.decision.verdict.value,
        decided_by=candidate.decided_by or "governor",
        reason=result.decision.reason,
    )
