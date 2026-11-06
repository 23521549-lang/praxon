"""Bảng event ghi mỗi lần gọi vai và mỗi quyết định của Governor (task 7.7).

Cổng ra: event từ chối UPDATE và DELETE; mỗi hàng có run_id, tenant_id,
actor, decision, decided_by. Chạy trên DB thật, dưới đúng vai ứng dụng (xem
`as_role` trong conftest — fail ngay nếu vai là superuser).
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

import pytest
from psycopg.errors import InsufficientPrivilege

from praxon_core.learning.candidate import (
    Candidate,
    Decision,
    DecisionVerdict,
    FactStatus,
    GovernorResult,
)
from praxon_core.learning.event_log import governor_decision_event, role_call_event
from praxon_core.repositories.events import insert_event

from .conftest import as_role, one


def _run_id(tenant: str) -> str:
    """ID của run mẫu mà fixture đã seed cho tenant."""
    with as_role(f"{tenant}__reader") as conn:
        (run_id,) = one(conn, "SELECT id FROM run WHERE tenant_id = %s", (tenant,))
        return str(run_id)


def _event_row(event_id: str) -> tuple[Any, ...]:
    with as_role("acme__reader") as conn:
        return one(
            conn,
            "SELECT run_id, tenant_id, actor, action, target, decision, decided_by, "
            "reason, payload_hash FROM event WHERE event_id = %s",
            (event_id,),
        )


def _governor_result(decided_by: str | None) -> GovernorResult:
    """Kết quả Governor mẫu: auto-approve theo luật 1."""
    candidate = Candidate(
        target_scope="tenant",
        payload={"canonical_key": "k", "template": "t", "statement": "s"},
        rationale="test",
        evidence_episode_ids=[],
        rule_id=1,
        status="approved",
        decided_by=decided_by,
    )
    decision = Decision(
        verdict=DecisionVerdict.AUTO_APPROVE,
        target_status=FactStatus.TRIAL,
        rule_id=1,
        reason="Luật 1 khớp",
    )
    return GovernorResult(decision=decision, candidate=candidate)


def test_event_ghi_quyet_dinh_cua_governor(pg: None) -> None:
    run_id = _run_id("acme")
    candidate_id = str(uuid.uuid4())
    result = _governor_result("nguoi-duyet")
    event = governor_decision_event(
        result, tenant_id="acme", run_id=run_id, candidate_id=candidate_id
    )
    with as_role("acme__coordinator") as conn:
        event_id = insert_event(conn, event)
    row = _event_row(event_id)
    assert str(row[0]) == run_id
    assert row[1:8] == (
        "acme",
        "governor",
        "decide",
        candidate_id,
        "auto_approve",
        "nguoi-duyet",
        "Luật 1 khớp",
    )
    assert (
        row[8] == hashlib.sha256(result.candidate.model_dump_json().encode("utf-8")).hexdigest()
    )


def test_event_ghi_lan_goi_vai(pg: None) -> None:
    run_id = _run_id("acme")
    event = role_call_event(
        tenant_id="acme",
        actor="curator",
        action="propose",
        payload_hash="hash-cua-payload",
        run_id=run_id,
        target="candidate-1",
    )
    with as_role("acme__coordinator") as conn:
        event_id = insert_event(conn, event)
    row = _event_row(event_id)
    assert str(row[0]) == run_id
    assert row[1:7] == ("acme", "curator", "propose", "candidate-1", None, None)
    assert row[7] is None
    assert row[8] == "hash-cua-payload"


def test_event_tu_choi_update(pg: None) -> None:
    event = role_call_event(
        tenant_id="acme", actor="curator", action="propose", payload_hash="hash"
    )
    with as_role("acme__coordinator") as conn:
        event_id = insert_event(conn, event)
        with pytest.raises(InsufficientPrivilege):
            conn.execute("UPDATE event SET action = 'sua' WHERE event_id = %s", (event_id,))


def test_event_tu_choi_delete(pg: None) -> None:
    event = role_call_event(
        tenant_id="acme", actor="curator", action="propose", payload_hash="hash"
    )
    with as_role("acme__coordinator") as conn:
        event_id = insert_event(conn, event)
        with pytest.raises(InsufficientPrivilege):
            conn.execute("DELETE FROM event WHERE event_id = %s", (event_id,))


def test_ghi_event_qua_vai_curator_bi_chan(pg: None) -> None:
    event = role_call_event(
        tenant_id="acme", actor="curator", action="propose", payload_hash="hash"
    )
    with as_role("acme__curator") as conn, pytest.raises(InsufficientPrivilege):
        insert_event(conn, event)


def test_governor_decision_event_khong_co_nguoi_duyet(pg: None) -> None:
    """Governor tự quyết mà candidate chưa có người duyệt thì ghi 'governor'."""
    result = _governor_result(None)
    event = governor_decision_event(
        result,
        tenant_id="acme",
        run_id=str(uuid.uuid4()),
        candidate_id=str(uuid.uuid4()),
    )
    assert event.actor == "governor"
    assert event.action == "decide"
    assert event.decision == "auto_approve"
    assert event.decided_by == "governor"


def test_role_call_event_tu_choi_payload_hash_rong(pg: None) -> None:
    with pytest.raises(ValueError):
        role_call_event(tenant_id="acme", actor="curator", action="propose", payload_hash="   ")
