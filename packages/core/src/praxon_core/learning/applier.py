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

Ngữ nghĩa áp theo loại Delta (task P): ADD thì INSERT fact mới; RETIRE
thì đóng fact cũ (`build_fact_close` + `close_fact`, không tạo hàng mới);
CONTRADICT thì đóng fact cũ + thêm fact mới mang khóa đối nghịch, trong
một giao dịch; CONFIRM thì không INSERT. `build_fact_row` từ chối
RETIRE/CONFIRM (chúng không tạo fact mới); `build_fact_close` chỉ nhận
RETIRE/CONTRADICT. Coordinator nối các bước lại trong một transaction.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from praxon_core.learning.candidate import Candidate
from praxon_core.learning.payload import FactPayload
from praxon_core.repositories.facts import FactClose, FactRow


def build_fact_close(candidate: Candidate, *, retired_at: datetime) -> FactClose:
    """Xây lệnh đóng fact cũ từ candidate RETIRE/CONTRADICT đã duyệt (thuần).

    Đọc `kind` + `fact_id` từ payload (hợp đồng D+F): RETIRE/CONTRADICT
    đều tác động lên một fact hiện có. Từ chối candidate chưa duyệt (BĐ3,
    như `build_fact_row`), từ chối loại Delta khác RETIRE/CONTRADICT và
    từ chối khi thiếu `fact_id` — Applier không biết đóng fact nào.

    `retired_at` (thời điểm fact nghỉ) do coordinator truyền vào — thời
    điểm duyệt/áp; hàm thuần không tự lấy giờ (giữ tính xác định).
    Người gọi ghi lệnh này qua `repositories.facts.close_fact` bằng kết
    nối dưới đúng vai ứng dụng.
    """
    if candidate.status != "approved":
        raise ValueError(
            f"chỉ áp candidate đã duyệt (candidate đang ở trạng thái {candidate.status!r})"
        )
    payload = FactPayload.model_validate(candidate.payload)
    if payload.kind not in ("retire", "contradict"):
        raise ValueError(
            f"chỉ đóng fact cũ cho RETIRE/CONTRADICT (candidate mang kind {payload.kind!r})"
        )
    if payload.fact_id is None:
        raise ValueError(
            f"không đóng được fact cũ: payload thiếu fact_id (kind {payload.kind!r})"
        )
    return FactClose(fact_id=payload.fact_id, retired_at=retired_at)


def build_fact_row(candidate: Candidate, *, candidate_id: str, tenant_id: str) -> FactRow:
    """Xây hàng fact từ candidate đã duyệt (thuần, không chạm DB).

    Từ chối candidate chưa có quyết định (status khác 'approved') — BĐ3 còn
    được V4 chặn ở tầng DB, nhưng từ chối sớm ở đây cho lỗi rõ ràng. Scope lấy
    từ candidate.target_scope; tenant_id của fact là tenant của candidate.

    Chỉ nhận ADD và CONTRADICT (phần thêm fact mới mang khóa đối nghịch):
    RETIRE/CONFIRM không tạo fact mới — RETIRE chỉ đóng fact cũ (dùng
    `build_fact_close` + `close_fact`), CONFIRM thì fact đã có sẵn. Tạo
    FactRow mới cho hai loại này là sai ngữ nghĩa và vi phạm BĐ5 (INSERT
    cùng khóa trong khi fact cũ còn "known" bị exclusion chặn).
    """
    if candidate.status != "approved":
        raise ValueError(
            f"chỉ áp candidate đã duyệt (candidate {candidate_id} đang ở trạng thái "
            f"{candidate.status!r})"
        )
    payload = FactPayload.model_validate(candidate.payload)
    if payload.kind in ("retire", "confirm"):
        raise ValueError(
            f"không tạo FactRow mới cho {payload.kind.upper()} (candidate "
            f"{candidate_id}): RETIRE chỉ đóng fact cũ, CONFIRM thì fact "
            "đã có sẵn"
        )
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
