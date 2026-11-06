"""Applier và Promoter (plan con 7, task 7.6; spec: hợp đồng vòng học).

Chỉ applier/promoter ghi tri thức, và cả hai chỉ áp candidate đã có quyết
định (BĐ3). Cơ sở dữ liệu chặn phần còn lại: V4 (candidate phải 'approved'),
V3 (applier chỉ ghi scope tenant của mình, promoter mới ghi 'global').
Áp candidate là lũy đẳng (BĐ6): áp lại cùng candidate không làm gì.

Mỗi vai là một hàm thuần trên kiểu dữ liệu có cấu trúc; không vai nào gọi vai
khác, và không hàm nào ở đây chạm DB hay import driver DB (hợp đồng
driver-db-chi-trong-repositories — import-linter soi cả import trong khối
TYPE_CHECKING nên learning không được nhắc tới psycopg dưới bất kỳ hình thức
nào). Mỗi hàm vai xây một `FactRow`; người gọi ghi hàng đó qua
`repositories.facts.insert_fact` bằng kết nối dưới đúng vai ứng dụng
(`<tenant>__applier` cho tenant, `promoter` cho global). Quyền + RLS +
trigger V4 chặn ở tầng DB khi ghi qua vai sai.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from praxon_core.learning.candidate import Candidate, FactStatus
from praxon_core.repositories.facts import FactRow


class FactPayload(BaseModel):
    """Nội dung fact trong `payload` của candidate (Curator ghi, Applier đọc).

    Khóa này là hợp đồng giữa Curator (7.2) và Applier: Curator đặt các trường
    fact vào payload của candidate; Applier đọc đúng các trường này để ghi fact.
    `extra="forbid"` để một khóa lạ bị từ chối ngay. `source_episode_ids` của
    fact lấy từ `evidence_episode_ids` của candidate, không nằm trong payload.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_key: str
    template: str
    statement: str
    status: FactStatus = FactStatus.TRIAL
    activation: str | None = None
    target: str | None = None
    condition: str | None = None
    support: int = Field(default=0, ge=0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    valid_start: datetime
    valid_end: datetime | None = None


def build_fact_row(candidate: Candidate, *, candidate_id: str, tenant_id: str) -> FactRow:
    """Xây hàng fact từ candidate đã duyệt (thuần, không chạm DB).

    Từ chối candidate chưa có quyết định (status khác 'approved') — BĐ3 còn
    được V4 chặn ở tầng DB, nhưng từ chối sớm ở đây cho lỗi rõ ràng. Scope lấy
    từ candidate.target_scope; tenant_id của fact là tenant của candidate.
    """
    if candidate.status != "approved":
        raise ValueError(
            f"chỉ áp candidate đã duyệt (candidate {candidate_id} đang ở trạng thái "
            f"{candidate.status!r})"
        )
    payload = FactPayload.model_validate(candidate.payload)
    return FactRow(
        tenant_id=tenant_id,
        scope=candidate.target_scope,
        canonical_key=payload.canonical_key,
        template=payload.template,
        statement=payload.statement,
        status=payload.status.value,
        support=payload.support,
        confidence=payload.confidence,
        valid_start=payload.valid_start,
        valid_end=payload.valid_end,
        activation=payload.activation,
        target=payload.target,
        condition=payload.condition,
        source_episode_ids=tuple(UUID(e) for e in candidate.evidence_episode_ids),
        candidate_id=candidate_id,
    )


def apply_candidate(candidate: Candidate, *, candidate_id: str, tenant_id: str) -> FactRow:
    """Xây hàng fact cho vai applier từ candidate đã duyệt (thuần, không ghi DB).

    Chỉ nhận candidate nhắm tới scope tenant; người gọi ghi hàng trả về qua
    `repositories.facts.insert_fact` bằng kết nối dưới vai `<tenant>__applier`.
    `insert_fact` trả True nếu ghi hàng mới, False nếu candidate đã áp trước
    đó (lũy đẳng, BĐ6). Ghi qua vai khác thì cơ sở dữ liệu chặn (quyền + RLS).
    """
    if candidate.target_scope != "tenant":
        raise ValueError(
            f"applier chỉ áp candidate vào scope tenant (candidate {candidate_id} "
            f"nhắm tới {candidate.target_scope!r})"
        )
    return build_fact_row(candidate, candidate_id=candidate_id, tenant_id=tenant_id)


def promote_candidate(candidate: Candidate, *, candidate_id: str) -> FactRow:
    """Xây hàng fact global cho vai promoter từ candidate đã duyệt (thuần).

    Chỉ nhận candidate nhắm tới scope global; người gọi ghi hàng trả về qua
    `repositories.facts.insert_fact` bằng kết nối dưới vai `promoter`. Fact
    global mang tenant_id = 'global' (quy ước V1).
    """
    if candidate.target_scope != "global":
        raise ValueError(
            f"promoter chỉ nâng candidate lên scope global (candidate {candidate_id} "
            f"nhắm tới {candidate.target_scope!r})"
        )
    return build_fact_row(candidate, candidate_id=candidate_id, tenant_id="global")
