"""Quyết định của người dùng thành Candidate (plan con 9, task 9.3).

Cổng ra: không có đường ghi tắt nào vòng qua `Candidate`; thiếu
`rubric_clause` thì từ chối. Phần "không đường vòng" ở tầng DB do V4/V5 chặn
(đã kiểm ở test_invariants.py, BĐ3); ở đây kiểm hàm chuyển đổi thuần: mọi
quyết định của người dùng chỉ vào vòng học qua `human_decision_to_candidate`,
luôn ở status 'proposed' kèm `decided_by` + `rubric_clause`.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from praxon_core.learning.human_decision import human_decision_to_candidate


def _payload() -> dict[str, Any]:
    return {
        "canonical_key": "response(A, B)",
        "template": "response",
        "statement": "A response B",
        "valid_start": "2030-01-01T00:00:00+00:00",
    }


def test_quyet_dinh_thanh_candidate_co_decided_by_va_rubric_clause():
    candidate = human_decision_to_candidate(
        target_scope="tenant",
        payload=_payload(),
        rationale="người dùng duyệt",
        decided_by="nguoi-duyet",
        rubric_clause="rubric 3.2",
        evidence_episode_ids=["e1", "e2"],
    )
    assert candidate.target_scope == "tenant"
    assert candidate.payload == _payload()
    assert candidate.rationale == "người dùng duyệt"
    assert candidate.evidence_episode_ids == ["e1", "e2"]
    assert candidate.decided_by == "nguoi-duyet"
    assert candidate.rubric_clause == "rubric 3.2"
    # Người dùng ghi căn cứ quyết định chứ không tự đóng dấu duyệt: luôn ở
    # 'proposed', chưa có rule_id — chỉ Governor mới đổi status qua V5.
    assert candidate.status == "proposed"
    assert candidate.rule_id is None


def test_quyet_dinh_global_thanh_candidate():
    candidate = human_decision_to_candidate(
        target_scope="global",
        payload=_payload(),
        rationale="người dùng duyệt global",
        decided_by="nguoi-duyet",
        rubric_clause="rubric 3.2",
    )
    assert candidate.target_scope == "global"
    assert candidate.evidence_episode_ids == []


def test_thieu_rubric_clause_bi_tu_choi():
    for rubric_clause in (None, "", "   "):
        with pytest.raises(ValueError):
            human_decision_to_candidate(
                target_scope="tenant",
                payload=_payload(),
                rationale="người dùng duyệt",
                decided_by="nguoi-duyet",
                rubric_clause=rubric_clause,
            )


def test_thieu_decided_by_bi_tu_choi():
    for decided_by in (None, "", "   "):
        with pytest.raises(ValueError):
            human_decision_to_candidate(
                target_scope="tenant",
                payload=_payload(),
                rationale="người dùng duyệt",
                decided_by=decided_by,
                rubric_clause="rubric 3.2",
            )


def test_target_scope_la_bi_tu_choi():
    with pytest.raises(ValueError):
        human_decision_to_candidate(
            target_scope="acme",
            payload=_payload(),
            rationale="người dùng duyệt",
            decided_by="nguoi-duyet",
            rubric_clause="rubric 3.2",
        )


def test_payload_sai_bi_tu_choi_ngay_luc_tao():
    """Payload không khớp FactPayload thì lỗi ngay lúc tạo (fail-fast, F).

    Trước đây hàm này chuyền payload do caller cung cấp mà không kiểm, nên
    lỗi chỉ lộ ở lúc áp. Nay validate theo FactPayload trước khi tạo
    Candidate: thiếu `valid_start` thì từ chối ngay.
    """
    with pytest.raises(ValidationError):
        human_decision_to_candidate(
            target_scope="tenant",
            payload={"canonical_key": "k", "template": "t", "statement": "s"},
            rationale="người dùng duyệt",
            decided_by="nguoi-duyet",
            rubric_clause="rubric 3.2",
        )


def test_payload_khoa_la_bi_tu_choi_ngay_luc_tao():
    """Khóa lạ trong payload vẫn bị `extra="forbid"` từ chối ngay lúc tạo."""
    payload = _payload()
    payload["kind2"] = "x"
    with pytest.raises(ValidationError):
        human_decision_to_candidate(
            target_scope="tenant",
            payload=payload,
            rationale="người dùng duyệt",
            decided_by="nguoi-duyet",
            rubric_clause="rubric 3.2",
        )
