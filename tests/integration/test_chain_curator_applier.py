"""Chuỗi Curator → Governor → Applier trên DB thật (sửa khoảng trống D+F).

§10 test 6: Insight → curate → to_candidate → decide (luật 2 auto_approve)
→ ghi candidate xuống DB qua curator/governor → promote_candidate →
insert_fact qua promoter → đọc lại fact. Đường global (Insight
scope="global") — toàn bộ chuỗi chạy thông tới DB, chứng minh khoảng trống
payload đã đóng. Đường tenant qua apply_candidate + INSERT candidate bị
chặn bởi lệch tên scope (to_candidate đặt target_scope = tên tenant, DB
chỉ nhận 'tenant'/'global') — khoảng trống riêng, task riêng; đường tenant
kiểm tới build_fact_row ở test thuần (tests/test_payload.py).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from praxon_core.learning.applier import promote_candidate
from praxon_core.learning.candidate import DecisionVerdict
from praxon_core.learning.curator import (
    DeltaKind,
    Insight,
    InsightSource,
    curate,
    to_candidate,
)
from praxon_core.learning.governor import decide
from praxon_core.learning.measures import Measures
from praxon_core.learning.payload import FactPayload
from praxon_core.learning.rules import default_rule_table
from praxon_core.repositories.facts import insert_fact

from .conftest import as_role, one

#: Thời điểm hiệu lực cố định cho test (xác định — không dùng giờ thật).
VALID_START = datetime(2030, 1, 1, tzinfo=UTC)
#: Một episode id hợp lệ dạng UUID (build_fact_row parse evidence thành UUID).
EPISODE_ID = "22222222-2222-2222-2222-222222222222"


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
