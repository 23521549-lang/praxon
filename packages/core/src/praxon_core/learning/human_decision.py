"""Quyết định của người dùng thành Candidate (plan con 9, task 9.3).

Đây là đường DUY NHẤT đưa quyết định của người dùng vào vòng học: duyệt,
chặn hay bật sớm đều thành một `Candidate` kèm `decided_by` (ai quyết) và
`rubric_clause` (điều nào của rubric làm căn cứ). Không có đường ghi tắt nào
vòng qua `Candidate`: ở tầng DB, V4 chỉ cho áp candidate đã 'approved' và V5
chỉ cho governor đổi status — một quyết định không đi qua đây thì không bao
giờ thành tri thức. Hàm này thuần, không chạm DB.

Loại quyết định (duyệt/chặn/bật sớm) KHÔNG nằm trong Candidate: nó là ngữ
cảnh của coordinator khi gọi hàm này (Governor luật 8 đọc hai đại lượng
`human_early_activate` + `has_rubric_clause` từ số đo, không đọc Candidate).
"""

from __future__ import annotations

from typing import Any

from praxon_core.learning.candidate import Candidate
from praxon_core.learning.payload import FactPayload

_TARGET_SCOPES = ("tenant", "global")


def human_decision_to_candidate(
    *,
    target_scope: str,
    payload: dict[str, Any],
    rationale: str,
    decided_by: str | None,
    rubric_clause: str | None,
    evidence_episode_ids: list[str] | None = None,
) -> Candidate:
    """Chuyển quyết định của người dùng thành Candidate (thuần).

    Candidate luôn ở status 'proposed': người dùng ghi căn cứ quyết định chứ
    không tự đóng dấu duyệt — chỉ Governor mới đổi status qua V5. Từ chối
    khi thiếu `decided_by` hay `rubric_clause` (rỗng, chỉ khoảng trắng, hay
    None) và khi `target_scope` không phải 'tenant' hay 'global'. Payload
    phải khớp hợp đồng chung `FactPayload` (validate ngay lúc tạo — fail-fast,
    không đợi tới lúc áp mới lỗi); người gọi xây payload bằng `FactPayload`
    (như Curator) để không bao giờ đưa payload sai vào đây.
    """
    if decided_by is None or not decided_by.strip():
        raise ValueError("quyết định của người dùng thiếu decided_by (ai quyết)")
    if rubric_clause is None or not rubric_clause.strip():
        raise ValueError("quyết định của người dùng thiếu rubric_clause (điều nào của rubric)")
    if target_scope not in _TARGET_SCOPES:
        raise ValueError(f"target_scope lạ: {target_scope!r}")
    FactPayload.model_validate(payload)
    return Candidate(
        target_scope=target_scope,
        payload=payload,
        rationale=rationale,
        evidence_episode_ids=list(evidence_episode_ids or []),
        status="proposed",
        decided_by=decided_by,
        rubric_clause=rubric_clause,
    )
