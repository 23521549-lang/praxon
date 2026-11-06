"""Hợp đồng payload chung Curator → Applier (sửa khoảng trống D+F).

Test thuần (không cần DB): payload Curator tạo phải khớp `FactPayload`
(0 lỗi — trước đây là 6 lỗi), fail-fast ngay lúc tạo, validator nhất quán
bắt lệch khóa/mẫu, payload JSON-safe cho JSONB, và chuỗi Curator → Governor
→ Applier chạy thông tới `build_fact_row` (đường tenant, thuần — đường ghi
xuống DB kiểm ở test integration).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from praxon_core.learning.applier import build_fact_close, build_fact_row
from praxon_core.learning.candidate import DecisionVerdict, FactStatus
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
from praxon_core.learning.payload import FactPayload, statement_for
from praxon_core.learning.rules import default_rule_table

#: Thời điểm hiệu lực cố định cho test (xác định — không dùng giờ thật).
VALID_START = datetime(2030, 1, 1, tzinfo=UTC)
#: Một episode id hợp lệ dạng UUID (build_fact_row parse evidence thành UUID).
EPISODE_ID = "11111111-1111-1111-1111-111111111111"


def _insight(
    template: str = "response",
    scope: str = "acme",
    condition: str | None = None,
) -> Insight:
    return Insight(
        template=template,
        activation="A",
        target="B",
        condition=condition,
        evidence_episode_ids=[EPISODE_ID],
        source=InsightSource.TRACE,
        scope=scope,
    )


def _fact(
    key: str,
    status: FactStatus = FactStatus.ACTIVE,
    fact_id: str = "f1",
) -> FactRead:
    return FactRead(
        id=fact_id,
        scope="acme",
        canonical_key=key,
        template="response",
        activation="A",
        target="B",
        condition=None,
        status=status,
    )


def _measures_auto_approve() -> Measures:
    """Số đo để luật 2 (ràng buộc mới) auto_approve."""
    return Measures(
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


def test_to_candidate_tao_payload_khop_fact_payload():
    """Test 1 (§10): payload Curator tạo khớp FactPayload, 0 lỗi."""
    candidate = to_candidate(curate(_insight(), [])[0], valid_start=VALID_START)
    FactPayload.model_validate(candidate.payload)
    assert candidate.payload["statement"] == "A response B"
    assert candidate.payload["valid_start"] == "2030-01-01T00:00:00Z"
    assert candidate.payload["kind"] == "add"
    assert candidate.payload["fact_id"] is None
    assert "fact_canonical_key" not in candidate.payload
    assert "fact_status" not in candidate.payload


def test_to_candidate_fail_fast_thieu_valid_start():
    """Test 2 (§10, fail-fast): thiếu valid_start thì lỗi ngay lúc tạo."""
    delta = curate(_insight(), [])[0]
    with pytest.raises(TypeError, match="valid_start"):
        # Cố ý gọi thiếu đối số bắt buộc để kiểm fail-fast — mypy báo
        # đúng (call-arg), bỏ qua có chủ đích ở dòng này.
        to_candidate(delta)  # type: ignore[call-arg]


def test_to_candidate_contradict_khoa_khop_mau():
    """Test 3 (§10): CONTRADICT mang khóa MỚI (đối nghịch) — sửa lỗi §2."""
    fact = _fact("response(A, B)", FactStatus.ACTIVE)
    candidate = to_candidate(
        curate(_insight(template="not_response"), [fact])[0], valid_start=VALID_START
    )
    assert candidate.payload["canonical_key"] == "not_response(A, B)"
    assert candidate.payload["template"] == "not_response"
    assert candidate.payload["statement"] == "A not_response B"
    assert candidate.payload["kind"] == "contradict"
    assert candidate.payload["fact_id"] == "f1"
    FactPayload.model_validate(candidate.payload)


def test_payload_lech_khoa_mau_bi_bat():
    """Test 4 (§10, fail-fast): validator nhất quán bắt lệch khóa/mẫu."""
    with pytest.raises(ValidationError, match="khong khop"):
        FactPayload(
            canonical_key="response(A, B)",
            template="not_response",
            statement="A not_response B",
            activation="A",
            target="B",
            valid_start=VALID_START,
        )


def test_payload_json_safe_cho_jsonb():
    """Test 7 (§10): payload lưu được xuống JSONB (valid_start là chuỗi ISO)."""
    candidate = to_candidate(curate(_insight(), [])[0], valid_start=VALID_START)
    dumped = json.dumps(candidate.payload)
    assert isinstance(candidate.payload["valid_start"], str)
    assert json.loads(dumped)["valid_start"] == "2030-01-01T00:00:00Z"


def test_statement_cho_moi_mau():
    """Test 8 (§10): định dạng statement (Q1) cho mọi mẫu x có/không điều kiện."""
    assert statement_for("response", "A", "B", None) == "A response B"
    assert statement_for("not_response", "A", "B", None) == "A not_response B"
    assert statement_for("precedence", "A", "B", None) == "A precedence B"
    assert statement_for("not_precedence", "A", "B", None) == "A not_precedence B"
    assert statement_for("response", "A", "B", "loai = 'x'") == "A response B when loai = 'x'"
    assert (
        statement_for("not_response", "A", "B", "loai = 'x'")
        == "A not_response B when loai = 'x'"
    )


def test_chuoi_curator_governor_applier_thong_thuan():
    """Chuỗi Curator → Governor → Applier chạy thông (đường tenant, thuần).

    Bản thuần của test nối §10 test 6: kiểm tới `build_fact_row` (không ghi
    DB — đường ghi xuống DB kiểm ở test integration). Đổi status sang
    'approved' bằng `model_copy` (mô phỏng bước đổi status qua V5 ở DB).
    """
    deltas = curate(_insight(), [])
    assert [d.kind for d in deltas] == [DeltaKind.ADD]
    candidate = to_candidate(deltas[0], valid_start=VALID_START)
    result = decide(candidate, default_rule_table(), _measures_auto_approve())
    assert result.decision.verdict is DecisionVerdict.AUTO_APPROVE
    assert result.decision.rule_id == 2
    approved = result.candidate.model_copy(update={"status": "approved"})
    row = build_fact_row(
        approved,
        candidate_id="00000000-0000-0000-0000-000000000001",
        tenant_id="acme",
    )
    assert row.tenant_id == "acme"
    assert row.canonical_key == "response(A, B)"
    assert row.statement == "A response B"
    assert row.valid_start == VALID_START
    assert row.source_episode_ids == (UUID(EPISODE_ID),)


def test_build_fact_row_tu_choi_retire_va_confirm():
    """RETIRE/CONFIRM không tạo FactRow mới (task P): từ chối, ADD thì nhận."""
    deltas = curate(
        _insight(template="not_response"), [_fact("response(A, B)", FactStatus.TRIAL)]
    )
    assert len(deltas) == 1 and deltas[0].kind == DeltaKind.RETIRE
    retire = to_candidate(deltas[0], valid_start=VALID_START).model_copy(
        update={"status": "approved"}
    )
    with pytest.raises(ValueError, match="RETIRE"):
        build_fact_row(
            retire, candidate_id="00000000-0000-0000-0000-000000000001", tenant_id="global"
        )
    deltas = curate(_insight(), [_fact("response(A, B)", FactStatus.ACTIVE)])
    assert len(deltas) == 1 and deltas[0].kind == DeltaKind.CONFIRM
    confirm = to_candidate(deltas[0], valid_start=VALID_START).model_copy(
        update={"status": "approved"}
    )
    with pytest.raises(ValueError, match="CONFIRM"):
        build_fact_row(
            confirm, candidate_id="00000000-0000-0000-0000-000000000002", tenant_id="global"
        )
    deltas = curate(_insight(), [])
    assert len(deltas) == 1 and deltas[0].kind == DeltaKind.ADD
    add = to_candidate(deltas[0], valid_start=VALID_START).model_copy(
        update={"status": "approved"}
    )
    row = build_fact_row(
        add, candidate_id="00000000-0000-0000-0000-000000000003", tenant_id="global"
    )
    assert row.canonical_key == "response(A, B)"


def test_build_fact_close_chi_nhan_retire_va_contradict():
    """build_fact_close chỉ nhận RETIRE/CONTRADICT + cần fact_id + cần đã duyệt."""
    deltas = curate(
        _insight(template="not_response"), [_fact("response(A, B)", FactStatus.TRIAL)]
    )
    retire = to_candidate(deltas[0], valid_start=VALID_START).model_copy(
        update={"status": "approved"}
    )
    close = build_fact_close(retire, retired_at=datetime(2030, 6, 1, tzinfo=UTC))
    assert close.fact_id == "f1"
    assert close.retired_at == datetime(2030, 6, 1, tzinfo=UTC)
    deltas = curate(_insight(), [])
    add = to_candidate(deltas[0], valid_start=VALID_START).model_copy(
        update={"status": "approved"}
    )
    with pytest.raises(ValueError, match="RETIRE/CONTRADICT"):
        build_fact_close(add, retired_at=datetime(2030, 6, 1, tzinfo=UTC))
    with pytest.raises(ValueError, match="đã duyệt"):
        build_fact_close(
            retire.model_copy(update={"status": "proposed"}),
            retired_at=datetime(2030, 6, 1, tzinfo=UTC),
        )


def test_factpayload_tu_choi_khoa_la():
    """FactPayload từ chối khóa lạ (extra=forbid) — hợp đồng D+F không nới."""
    payload = {
        "canonical_key": "response(A, B)",
        "template": "response",
        "statement": "A response B",
        "valid_start": "2030-01-01T00:00:00+00:00",
        "fact_canonical_key": "response(A, B)",
    }
    with pytest.raises(ValidationError):
        FactPayload.model_validate(payload)
    assert FactPayload.model_validate(
        {k: v for k, v in payload.items() if k != "fact_canonical_key"}
    )
