"""Kiểu Candidate và Decision của vòng học (spec: bảng candidate, dòng 49).

Governor là hàm thuần: nhận Candidate + bảng luật + số đo, trả Decision kèm
bản sao Candidate đã ghi `rule_id` và `metrics_at_decision`. Không gọi vai
khác, không chạm cơ sở dữ liệu.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class DecisionVerdict(StrEnum):
    """Bốn giá trị Decision trong spec (mục vòng học, bảng vai)."""

    AUTO_APPROVE = "auto_approve"
    NEEDS_HUMAN = "needs_human"
    REJECT = "reject"
    WAIT = "wait"


class FactStatus(StrEnum):
    """Ba giá trị status của fact (spec: `trial`, `active`, `retired`)."""

    TRIAL = "trial"
    ACTIVE = "active"
    RETIRED = "retired"


class Candidate(BaseModel):
    """Một đề xuất thay đổi tri thức, đúng các cột trong spec (dòng 49).

    Curator tạo; Governor chỉ ghi `rule_id` và `metrics_at_decision`.
    `decided_by` và `rubric_clause` do người duyệt ghi (luật 8); Governor
    không tự đặt chúng.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_scope: str
    payload: dict[str, Any]
    rationale: str
    evidence_episode_ids: list[str]
    rule_id: int | None = None
    metrics_at_decision: dict[str, bool | float | int | str | None] | None = None
    status: str
    decided_by: str | None = None
    rubric_clause: str | None = None


class Decision(BaseModel):
    """Quyết định của Governor cho một candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: DecisionVerdict
    target_status: FactStatus | None = None
    rule_id: int | None = None
    reason: str


class GovernorResult(BaseModel):
    """Kết quả một lần đánh giá: quyết định + bản sao candidate đã ghi."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Decision
    candidate: Candidate
