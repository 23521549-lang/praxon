"""Chuỗi Curator → Governor → Applier trên DB thật (sửa khoảng trống D+F).

§10 test 6: Insight → curate → to_candidate → decide (luật 2 auto_approve)
→ ghi candidate xuống DB qua curator/governor → promote_candidate →
insert_fact qua promoter → đọc lại fact. Đường global (Insight
scope="global") — toàn bộ chuỗi chạy thông tới DB, chứng minh khoảng trống
payload đã đóng. Đường tenant qua apply_candidate + INSERT candidate từng bị chặn bởi
lệch tên scope (to_candidate đặt target_scope = tên tenant, DB chỉ
nhận 'tenant'/'global') — đã sửa bằng ánh xạ ở to_candidate
('global' → 'global', tên tenant → 'tenant'); test
test_chuoi_tenant_thong_toi_db chứng minh đường tenant chạy thông tới DB.

Task P mở rộng chuỗi cho RETIRE/CONTRADICT/CONFIRM: Insight đối nghịch +
fact trial → RETIRE (Governor needs_human luật 1, người duyệt rồi đóng
fact cũ, không thêm hàng); Insight đối nghịch + fact active → CONTRADICT
(needs_human luật 1, đóng cũ + thêm mới khóa đối nghịch trong một giao
dịch); Insight khớp fact active → CONFIRM (Governor wait luật 9,
build_fact_row từ chối — không INSERT, số hàng fact không đổi).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

from praxon_core.learning.applier import (
    apply_candidate,
    build_fact_close,
    promote_candidate,
)
from praxon_core.learning.candidate import Candidate, DecisionVerdict, FactStatus
from praxon_core.learning.curator import (
    DeltaKind,
    FactRead,
    Insight,
    InsightSource,
    curate,
    to_candidate,
)
from praxon_core.learning.governor import decide
from praxon_core.learning.measures import Measures
from praxon_core.learning.payload import FactPayload
from praxon_core.learning.rules import default_rule_table
from praxon_core.repositories.facts import close_fact, insert_fact

from .conftest import as_role, one

#: Thời điểm hiệu lực cố định cho test (xác định — không dùng giờ thật).
VALID_START = datetime(2030, 1, 1, tzinfo=UTC)
#: Thời điểm fact nghỉ (do coordinator truyền vào — không dùng giờ thật).
RETIRED_AT = datetime(2030, 6, 1, tzinfo=UTC)
#: Một episode id hợp lệ dạng UUID (build_fact_row parse evidence thành UUID).
EPISODE_ID = "22222222-2222-2222-2222-222222222222"


def _approve_candidate(candidate: Candidate) -> tuple[str, Candidate]:
    """Ghi candidate qua curator rồi duyệt qua governor (mô phỏng người duyệt)."""
    candidate_id = str(uuid.uuid4())
    with as_role("acme__curator") as conn:
        conn.execute(
            "INSERT INTO candidate (id, tenant_id, target_scope, payload, rationale) "
            "VALUES (%s, %s, %s, %s::jsonb, %s)",
            (
                candidate_id,
                "acme",
                candidate.target_scope,
                json.dumps(candidate.payload),
                "test",
            ),
        )
    with as_role("acme__governor") as conn:
        conn.execute("UPDATE candidate SET status = 'approved' WHERE id = %s", (candidate_id,))
    return candidate_id, candidate.model_copy(update={"status": "approved"})


def _setup_fact_global(activation: str, target: str, status: FactStatus) -> FactRead:
    """Ghi fact global qua chuỗi ADD; trả FactRead để đưa vào curate."""
    insight = Insight(
        template="response",
        activation=activation,
        target=target,
        condition=None,
        evidence_episode_ids=[EPISODE_ID],
        source=InsightSource.TRACE,
        scope="global",
    )
    deltas = curate(insight, [])
    assert [d.kind for d in deltas] == [DeltaKind.ADD]
    candidate = to_candidate(deltas[0], valid_start=VALID_START)
    candidate_id, approved = _approve_candidate(candidate)
    with as_role("promoter") as conn:
        assert insert_fact(conn, promote_candidate(approved, candidate_id=candidate_id))
        if status is not FactStatus.TRIAL:
            conn.execute(
                "UPDATE fact SET status = %s WHERE candidate_id = %s",
                (status.value, candidate_id),
            )
    with as_role("acme__reader") as conn:
        (fact_id,) = one(conn, "SELECT id FROM fact WHERE candidate_id = %s", (candidate_id,))
    return FactRead(
        id=str(fact_id),
        scope="global",
        canonical_key=f"response({activation}, {target})",
        template="response",
        activation=activation,
        target=target,
        condition=None,
        status=status,
    )


def _measures(
    *, has_direct_conflict: bool, fact_status: FactStatus | None, is_new: bool
) -> Measures:
    return Measures(
        has_direct_conflict=has_direct_conflict,
        schema_valid=True,
        from_trace=True,
        wilson_lower=0.8,
        beta_prob=0.5,
        is_scope_promotion=False,
        from_global=False,
        has_condition=False,
        matching_cases=0,
        fact_status=fact_status,
        is_new=is_new,
        human_early_activate=False,
        has_rubric_clause=False,
    )


def _insight_not_response(activation: str, target: str) -> Insight:
    return Insight(
        template="not_response",
        activation=activation,
        target=target,
        condition=None,
        evidence_episode_ids=[EPISODE_ID],
        source=InsightSource.TRACE,
        scope="global",
    )


def test_chuoi_curator_governor_applier_thong(pg: None) -> None:
    insight = Insight(
        template="response",
        activation="A",
        target="B",
        condition=None,
        evidence_episode_ids=[EPISODE_ID],
        source=InsightSource.TRACE,
        scope="global",
    )
    deltas = curate(insight, [])
    assert [d.kind for d in deltas] == [DeltaKind.ADD]
    candidate = to_candidate(deltas[0], valid_start=VALID_START)
    # Payload Curator tạo khớp hợp đồng chung (0 lỗi — trước đây là 6 lỗi).
    FactPayload.model_validate(candidate.payload)
    measures = Measures(
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
    result = decide(candidate, default_rule_table(), measures)
    assert result.decision.verdict is DecisionVerdict.AUTO_APPROVE
    assert result.decision.rule_id == 2
    candidate_id = str(uuid.uuid4())
    with as_role("acme__curator") as conn:
        # json.dumps trên payload — gãy ngay nếu payload còn datetime object.
        conn.execute(
            "INSERT INTO candidate (id, tenant_id, target_scope, payload, rationale) "
            "VALUES (%s, %s, %s, %s::jsonb, %s)",
            (candidate_id, "acme", "global", json.dumps(candidate.payload), "test"),
        )
    with as_role("acme__governor") as conn:
        conn.execute("UPDATE candidate SET status = 'approved' WHERE id = %s", (candidate_id,))
    approved = result.candidate.model_copy(update={"status": "approved"})
    with as_role("promoter") as conn:
        assert insert_fact(conn, promote_candidate(approved, candidate_id=candidate_id))
    with as_role("acme__reader") as conn:
        row = one(
            conn,
            "SELECT tenant_id, scope, canonical_key, template, statement, status, "
            "support, confidence, candidate_id, lower(valid_during) "
            "FROM fact WHERE candidate_id = %s",
            (candidate_id,),
        )
    assert row[:8] == (
        "global",
        "global",
        "response(A, B)",
        "response",
        "A response B",
        "trial",
        0,
        0.0,
    )
    assert str(row[8]) == candidate_id
    assert row[9] == VALID_START


def test_chuoi_retire_dong_fact_cu(pg: None) -> None:
    """Chuỗi RETIRE: Insight đối nghịch + fact trial → needs_human → duyệt → đóng fact."""
    suffix = uuid.uuid4().hex[:8]
    act, tgt = f"A-{suffix}", f"B-{suffix}"
    fact = _setup_fact_global(act, tgt, FactStatus.TRIAL)
    deltas = curate(_insight_not_response(act, tgt), [fact])
    assert [d.kind for d in deltas] == [DeltaKind.RETIRE]
    candidate = to_candidate(deltas[0], valid_start=VALID_START)
    FactPayload.model_validate(candidate.payload)
    assert candidate.payload["kind"] == "retire"
    assert candidate.payload["fact_id"] == fact.id
    result = decide(
        candidate,
        default_rule_table(),
        _measures(has_direct_conflict=True, fact_status=FactStatus.TRIAL, is_new=False),
    )
    assert result.decision.verdict is DecisionVerdict.NEEDS_HUMAN
    assert result.decision.rule_id == 1
    _, approved = _approve_candidate(candidate)
    with as_role("promoter") as conn:
        assert close_fact(conn, build_fact_close(approved, retired_at=RETIRED_AT))
    with as_role("acme__reader") as conn:
        row = one(
            conn,
            "SELECT status, upper(known_during) FROM fact WHERE id = %s::uuid",
            (fact.id,),
        )
        (count,) = one(
            conn,
            "SELECT count(*) FROM fact WHERE canonical_key IN (%s, %s)",
            (f"response({act}, {tgt})", f"not_response({act}, {tgt})"),
        )
    assert row == ("retired", RETIRED_AT)
    assert count == 1


def test_chuoi_contradict_dong_cu_them_moi(pg: None) -> None:
    """Chuỗi CONTRADICT: Insight đối nghịch + fact active → đóng cũ + thêm mới, 1 giao dịch."""
    suffix = uuid.uuid4().hex[:8]
    act, tgt = f"A-{suffix}", f"B-{suffix}"
    fact = _setup_fact_global(act, tgt, FactStatus.ACTIVE)
    deltas = curate(_insight_not_response(act, tgt), [fact])
    assert [d.kind for d in deltas] == [DeltaKind.CONTRADICT]
    candidate = to_candidate(deltas[0], valid_start=VALID_START)
    FactPayload.model_validate(candidate.payload)
    assert candidate.payload["kind"] == "contradict"
    assert candidate.payload["canonical_key"] == f"not_response({act}, {tgt})"
    assert candidate.payload["fact_id"] == fact.id
    result = decide(
        candidate,
        default_rule_table(),
        _measures(has_direct_conflict=True, fact_status=FactStatus.ACTIVE, is_new=False),
    )
    assert result.decision.verdict is DecisionVerdict.NEEDS_HUMAN
    assert result.decision.rule_id == 1
    candidate_id, approved = _approve_candidate(candidate)
    with as_role("promoter") as conn:
        assert close_fact(conn, build_fact_close(approved, retired_at=RETIRED_AT))
        assert insert_fact(conn, promote_candidate(approved, candidate_id=candidate_id))
    with as_role("acme__reader") as conn:
        old = one(
            conn,
            "SELECT status, upper(known_during) FROM fact WHERE id = %s::uuid",
            (fact.id,),
        )
        new = one(
            conn,
            "SELECT canonical_key, template, status FROM fact WHERE candidate_id = %s",
            (candidate_id,),
        )
    assert old == ("retired", RETIRED_AT)
    assert new == (f"not_response({act}, {tgt})", "not_response", "trial")


def test_chuoi_confirm_khong_them_fact(pg: None) -> None:
    """Chuỗi CONFIRM: Insight khớp fact active → Governor wait, Applier không INSERT."""
    suffix = uuid.uuid4().hex[:8]
    act, tgt = f"A-{suffix}", f"B-{suffix}"
    fact = _setup_fact_global(act, tgt, FactStatus.ACTIVE)
    insight = Insight(
        template="response",
        activation=act,
        target=tgt,
        condition=None,
        evidence_episode_ids=[EPISODE_ID],
        source=InsightSource.TRACE,
        scope="global",
    )
    deltas = curate(insight, [fact])
    assert [d.kind for d in deltas] == [DeltaKind.CONFIRM]
    candidate = to_candidate(deltas[0], valid_start=VALID_START)
    FactPayload.model_validate(candidate.payload)
    assert candidate.payload["kind"] == "confirm"
    result = decide(
        candidate,
        default_rule_table(),
        _measures(has_direct_conflict=False, fact_status=FactStatus.ACTIVE, is_new=False),
    )
    assert result.decision.verdict is DecisionVerdict.WAIT
    assert result.decision.rule_id == 9
    _, approved = _approve_candidate(candidate)
    with pytest.raises(ValueError, match="CONFIRM"):
        promote_candidate(approved, candidate_id=str(uuid.uuid4()))
    with as_role("acme__reader") as conn:
        (count,) = one(
            conn,
            "SELECT count(*) FROM fact WHERE canonical_key = %s",
            (f"response({act}, {tgt})",),
        )
    assert count == 1


def test_chuoi_tenant_thong_toi_db(pg: None) -> None:
    """Chuỗi tenant: Insight mang tên tenant → áp qua applier → fact scope 'tenant'.

    Trước khi sửa, đường này vỡ ở INSERT candidate (to_candidate đặt
    target_scope = tên tenant, CHECK của DB từ chối); nay chạy thông tới DB.
    """
    suffix = uuid.uuid4().hex[:8]
    act, tgt = f"A-{suffix}", f"B-{suffix}"
    insight = Insight(
        template="response",
        activation=act,
        target=tgt,
        condition=None,
        evidence_episode_ids=[EPISODE_ID],
        source=InsightSource.TRACE,
        scope="acme",
    )
    deltas = curate(insight, [])
    assert [d.kind for d in deltas] == [DeltaKind.ADD]
    candidate = to_candidate(deltas[0], valid_start=VALID_START)
    # to_candidate ánh xạ tên tenant về 'tenant' (DB chỉ nhận 'tenant'/'global').
    assert candidate.target_scope == "tenant"
    FactPayload.model_validate(candidate.payload)
    result = decide(
        candidate,
        default_rule_table(),
        _measures(has_direct_conflict=False, fact_status=None, is_new=True),
    )
    assert result.decision.verdict is DecisionVerdict.AUTO_APPROVE
    assert result.decision.rule_id == 2
    candidate_id, approved = _approve_candidate(candidate)
    with as_role("acme__applier") as conn:
        assert insert_fact(
            conn, apply_candidate(approved, candidate_id=candidate_id, tenant_id="acme")
        )
    with as_role("acme__reader") as conn:
        row = one(
            conn,
            "SELECT tenant_id, scope, canonical_key, template, statement, status, "
            "support, confidence, candidate_id, lower(valid_during) "
            "FROM fact WHERE candidate_id = %s",
            (candidate_id,),
        )
    assert row[:8] == (
        "acme",
        "tenant",
        f"response({act}, {tgt})",
        "response",
        f"{act} response {tgt}",
        "trial",
        0,
        0.0,
    )
    assert str(row[8]) == candidate_id
    assert row[9] == VALID_START
