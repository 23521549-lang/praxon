"""Applier và Promoter (plan con 7, task 7.6).

Cổng ra: ghi qua vai khác bị cơ sở dữ liệu chặn; áp lại cùng candidate không
làm gì. Chạy trên DB thật, dưới đúng vai ứng dụng (xem `as_role` trong
conftest — fail ngay nếu vai là superuser).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from psycopg.errors import InsufficientPrivilege, RaiseException

from praxon_core.learning.applier import apply_candidate, build_fact_close, promote_candidate
from praxon_core.learning.candidate import Candidate
from praxon_core.repositories.facts import FactClose, close_fact, insert_fact

from .conftest import as_role, one


def _unique_key(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _payload(key: str) -> dict[str, Any]:
    return {
        "canonical_key": key,
        "template": "response",
        "statement": "a response b",
        "status": "trial",
        "valid_start": "2030-01-01T00:00:00+00:00",
        "valid_end": "2035-01-01T00:00:00+00:00",
    }


def _make_approved(
    tenant: str, target_scope: str, payload: dict[str, Any]
) -> tuple[str, Candidate]:
    """Tạo candidate qua curator rồi duyệt qua governor; trả (id, Candidate)."""
    candidate_id = str(uuid.uuid4())
    with as_role(f"{tenant}__curator") as conn:
        conn.execute(
            "INSERT INTO candidate (id, tenant_id, target_scope, payload, rationale) "
            "VALUES (%s, %s, %s, %s::jsonb, %s)",
            (candidate_id, tenant, target_scope, json.dumps(payload), "test"),
        )
    with as_role(f"{tenant}__governor") as conn:
        conn.execute("UPDATE candidate SET status = 'approved' WHERE id = %s", (candidate_id,))
    candidate = Candidate(
        target_scope=target_scope,
        payload=payload,
        rationale="test",
        evidence_episode_ids=[],
        status="approved",
    )
    return candidate_id, candidate


def _make_proposed(
    tenant: str, target_scope: str, payload: dict[str, Any]
) -> tuple[str, Candidate]:
    """Tạo candidate chưa duyệt (status 'proposed'); trả (id, Candidate)."""
    candidate_id = str(uuid.uuid4())
    with as_role(f"{tenant}__curator") as conn:
        conn.execute(
            "INSERT INTO candidate (id, tenant_id, target_scope, payload, rationale) "
            "VALUES (%s, %s, %s, %s::jsonb, %s)",
            (candidate_id, tenant, target_scope, json.dumps(payload), "test"),
        )
    candidate = Candidate(
        target_scope=target_scope,
        payload=payload,
        rationale="test",
        evidence_episode_ids=[],
        status="proposed",
    )
    return candidate_id, candidate


def _fact_row(candidate_id: str) -> tuple[Any, ...]:
    with as_role("acme__reader") as conn:
        return one(
            conn,
            "SELECT tenant_id, scope, canonical_key, template, statement, status, "
            "support, confidence, candidate_id FROM fact WHERE candidate_id = %s",
            (candidate_id,),
        )


def test_applier_ghi_fact_tu_candidate_da_duyet(pg: None) -> None:
    key = _unique_key("applier")
    candidate_id, candidate = _make_approved("acme", "tenant", _payload(key))
    with as_role("acme__applier") as conn:
        assert insert_fact(
            conn, apply_candidate(candidate, candidate_id=candidate_id, tenant_id="acme")
        )
    row = _fact_row(candidate_id)
    assert row[:8] == (
        "acme",
        "tenant",
        key,
        "response",
        "a response b",
        "trial",
        0,
        0.0,
    )
    assert str(row[8]) == candidate_id


def test_applier_ap_lai_khong_lam_gi(pg: None) -> None:
    key = _unique_key("applier")
    candidate_id, candidate = _make_approved("acme", "tenant", _payload(key))
    with as_role("acme__applier") as conn:
        row = apply_candidate(candidate, candidate_id=candidate_id, tenant_id="acme")
        assert insert_fact(conn, row)
        assert not insert_fact(conn, row)
    with as_role("acme__reader") as conn:
        (count,) = one(
            conn, "SELECT count(*) FROM fact WHERE candidate_id = %s", (candidate_id,)
        )
        assert count == 1


def test_applier_tu_choi_candidate_chua_duyet(pg: None) -> None:
    key = _unique_key("applier")
    candidate_id, candidate = _make_proposed("acme", "tenant", _payload(key))
    with pytest.raises(ValueError):
        apply_candidate(candidate, candidate_id=candidate_id, tenant_id="acme")


def test_ghi_fact_qua_vai_curator_bi_chan(pg: None) -> None:
    key = _unique_key("applier")
    candidate_id, candidate = _make_approved("acme", "tenant", _payload(key))
    with as_role("acme__curator") as conn, pytest.raises(InsufficientPrivilege):
        insert_fact(
            conn, apply_candidate(candidate, candidate_id=candidate_id, tenant_id="acme")
        )


def test_ghi_fact_qua_vai_reader_bi_chan(pg: None) -> None:
    key = _unique_key("applier")
    candidate_id, candidate = _make_approved("acme", "tenant", _payload(key))
    with as_role("acme__reader") as conn, pytest.raises(InsufficientPrivilege):
        insert_fact(
            conn, apply_candidate(candidate, candidate_id=candidate_id, tenant_id="acme")
        )


def test_applier_khong_ap_duoc_candidate_cua_tenant_khac(pg: None) -> None:
    key = _unique_key("applier")
    candidate_id, candidate = _make_approved("globex", "tenant", _payload(key))
    with as_role("acme__applier") as conn, pytest.raises(RaiseException):
        insert_fact(
            conn, apply_candidate(candidate, candidate_id=candidate_id, tenant_id="acme")
        )


def test_applier_tu_choi_candidate_nham_global(pg: None) -> None:
    key = _unique_key("applier")
    candidate_id, candidate = _make_approved("acme", "global", _payload(key))
    with pytest.raises(ValueError):
        apply_candidate(candidate, candidate_id=candidate_id, tenant_id="acme")


def test_promoter_tu_choi_candidate_nham_tenant(pg: None) -> None:
    key = _unique_key("applier")
    candidate_id, candidate = _make_approved("acme", "tenant", _payload(key))
    with pytest.raises(ValueError):
        promote_candidate(candidate, candidate_id=candidate_id)


def test_promoter_ghi_fact_global_tu_candidate_da_duyet(pg: None) -> None:
    """Promoter áp candidate đã duyệt lên global (V6 mở đường đọc candidate).

    V6 cho vai `promoter` đọc bảng `candidate` nên trigger V4 (chạy với quyền
    promoter) thấy được candidate để kiểm status. Trước V6, hành vi bị chặn
    được ghi lại ở `test_promoter_bi_chan_boi_v4_trigger_vi_rls` (đã xóa).
    """
    key = _unique_key("applier")
    candidate_id, candidate = _make_approved("acme", "global", _payload(key))
    with as_role("promoter") as conn:
        assert insert_fact(conn, promote_candidate(candidate, candidate_id=candidate_id))
    row = _fact_row(candidate_id)
    assert row[:8] == (
        "global",
        "global",
        key,
        "response",
        "a response b",
        "trial",
        0,
        0.0,
    )
    assert str(row[8]) == candidate_id


def _insert_fact_global(key: str, status: str = "trial") -> tuple[str, str]:
    """Ghi fact global qua promoter; trả (candidate_id, fact_id)."""
    payload = _payload(key)
    payload["status"] = status
    candidate_id, candidate = _make_approved("acme", "global", payload)
    with as_role("promoter") as conn:
        assert insert_fact(conn, promote_candidate(candidate, candidate_id=candidate_id))
    with as_role("acme__reader") as conn:
        (fact_id,) = one(conn, "SELECT id FROM fact WHERE candidate_id = %s", (candidate_id,))
    return candidate_id, str(fact_id)


def test_retire_dong_fact_cu(pg: None) -> None:
    """RETIRE đóng fact cũ: status retired, known_during kết thúc ở retired_at."""
    key = _unique_key("retire")
    _, fact_id = _insert_fact_global(key)
    opp_key = _unique_key("retire-opp")
    payload = _payload(opp_key)
    payload["template"] = "not_response"
    payload["kind"] = "retire"
    payload["fact_id"] = fact_id
    _, candidate = _make_approved("acme", "global", payload)
    retired_at = datetime(2030, 6, 1, tzinfo=UTC)
    with as_role("promoter") as conn:
        assert close_fact(conn, build_fact_close(candidate, retired_at=retired_at))
    with as_role("acme__reader") as conn:
        row = one(
            conn,
            "SELECT status, upper(known_during), canonical_key FROM fact WHERE id = %s::uuid",
            (fact_id,),
        )
        (count,) = one(
            conn,
            "SELECT count(*) FROM fact WHERE canonical_key IN (%s, %s)",
            (key, opp_key),
        )
    assert row == ("retired", retired_at, key)
    assert count == 1


def test_contradict_dong_fact_cu_va_them_fact_moi(pg: None) -> None:
    """CONTRADICT: đóng fact cũ + thêm fact mới khóa đối nghịch, trong MỘT giao dịch.

    Cả hai thao tác chạy trên cùng một kết nối promoter (`as_role` commit khi
    thoát khối, rollback khi lỗi) nên hoặc cùng thành công hoặc cùng biến mất.
    """
    key = _unique_key("contradict")
    _, fact_id = _insert_fact_global(key, status="active")
    opp_key = _unique_key("contradict-opp")
    payload = _payload(opp_key)
    payload["template"] = "not_response"
    payload["statement"] = "a not_response b"
    payload["kind"] = "contradict"
    payload["fact_id"] = fact_id
    candidate_id, candidate = _make_approved("acme", "global", payload)
    retired_at = datetime(2030, 6, 1, tzinfo=UTC)
    with as_role("promoter") as conn:
        assert close_fact(conn, build_fact_close(candidate, retired_at=retired_at))
        assert insert_fact(conn, promote_candidate(candidate, candidate_id=candidate_id))
    with as_role("acme__reader") as conn:
        old = one(
            conn,
            "SELECT status, upper(known_during) FROM fact WHERE id = %s::uuid",
            (fact_id,),
        )
        new = one(
            conn,
            "SELECT canonical_key, template, status FROM fact WHERE candidate_id = %s",
            (candidate_id,),
        )
    assert old == ("retired", retired_at)
    assert new == (opp_key, "not_response", "trial")


def test_close_fact_khong_tim_thay_fact(pg: None) -> None:
    """close_fact trả False khi không có fact nào mang fact_id đó (không raise)."""
    with as_role("promoter") as conn:
        assert not close_fact(
            conn,
            FactClose(
                fact_id="00000000-0000-0000-0000-000000000000",
                retired_at=datetime(2030, 6, 1, tzinfo=UTC),
            ),
        )
