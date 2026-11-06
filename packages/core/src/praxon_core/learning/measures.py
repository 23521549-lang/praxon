"""Danh sách đại lượng cho trước của Governor (spec: điều kiện chỉ lấy từ đây).

Mọi đại lượng đều đếm được trên dữ liệu — không đại lượng nào hỏi ý kiến mô
hình. Governor chỉ đọc số đo; việc đếm thuộc về phía gọi (Curator / bộ điều
phối), không thuộc task này. Mỗi đại lượng ghi rõ luật nào dùng nó.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from praxon_core.learning.candidate import FactStatus


class MeasureName(StrEnum):
    """Tên các đại lượng Governor được phép dùng trong điều kiện."""

    HAS_DIRECT_CONFLICT = "has_direct_conflict"
    SCHEMA_VALID = "schema_valid"
    FROM_TRACE = "from_trace"
    WILSON_LOWER = "wilson_lower"
    BETA_PROB = "beta_prob"
    IS_SCOPE_PROMOTION = "is_scope_promotion"
    FROM_GLOBAL = "from_global"
    HAS_CONDITION = "has_condition"
    MATCHING_CASES = "matching_cases"
    FACT_STATUS = "fact_status"
    IS_NEW = "is_new"
    HUMAN_EARLY_ACTIVATE = "human_early_activate"
    HAS_RUBRIC_CLAUSE = "has_rubric_clause"


class Measures(BaseModel):
    """Toàn bộ số đo Governor cần để đánh giá một candidate.

    `is_new` phân biệt ràng buộc mới (luật 2, 6, 7) với fact đang có (luật 3,
    4, 8); `fact_status` là trạng thái của fact đang có, None khi chưa có.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    has_direct_conflict: bool
    schema_valid: bool
    from_trace: bool
    wilson_lower: float = Field(ge=0.0, le=1.0)
    beta_prob: float = Field(ge=0.0, le=1.0)
    is_scope_promotion: bool
    from_global: bool
    has_condition: bool
    matching_cases: int = Field(ge=0)
    fact_status: FactStatus | None = None
    is_new: bool
    human_early_activate: bool
    has_rubric_clause: bool


def measures_to_dict(measures: Measures) -> dict[str, bool | float | int | str | None]:
    """Ghi toàn bộ số đo lúc đánh giá, để chạy lại ra đúng quyết định cũ."""
    dumped: dict[str, bool | float | int | str | None] = measures.model_dump()
    return dumped
