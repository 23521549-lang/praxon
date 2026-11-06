"""Hợp đồng payload chung giữa Curator và Applier (sửa khoảng trống D+F).

Một model dùng chung mà cả Curator (lúc tạo Candidate) và Applier (lúc áp)
đều dùng — thay vì mỗi bên tự định nghĩa payload bằng dict thô. Theo nguyên
tắc spec dòng 37: dữ liệu giữa các vai phải là kiểu có cấu trúc, không phải
dict thô — "đó là chỗ mypy bắt được lỗi sớm nhất". Curator tạo payload bằng
chính model này nên thiếu trường bắt buộc bị mypy báo ngay lúc viết code và
bị Pydantic từ chối ngay lúc tạo (fail-fast), không đợi tới lúc áp mới lỗi.

`FactPayload` giữ `extra="forbid"`: khóa lạ bị từ chối ngay. Hai trường
`kind` + `fact_id` KHÔNG phải trường fact — chúng là tín hiệu để Applier
quyết hành động (task P, ngữ nghĩa RETIRE/CONTRADICT): ADD thì INSERT fact
mới; RETIRE thì đóng fact cũ; CONTRADICT thì đóng cũ + thêm mới mang khóa
đối nghịch; CONFIRM thì không INSERT. Không có hai trường này, Applier
không phân biệt được loại Delta. `fact_canonical_key` + `fact_status` đã bỏ
(thừa: khóa fact cũ luôn bằng `canonical_key` của Delta; trạng thái fact
hiện hành đã có ở Measures/DB).

`statement` suy bằng `statement_for` (Q1): tên mẫu nguyên văn, không câu tự
nhiên. `valid_start` do coordinator truyền vào (Q2) — hàm thuần không tự
lấy giờ; với Insight từ tài liệu, khi đường tài liệu có metadata văn bản thì
coordinator truyền khoảng hiệu lực văn bản theo spec dòng 56.
"""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from praxon_core.learning.candidate import FactStatus


def canonical_key_for(
    template: str, activation: str, target: str, condition: str | None
) -> str:
    """Ghép khóa canonical từ mẫu Declare, hai hoạt động và điều kiện.

    Định dạng theo ví dụ trong spec (dòng 54):
    `precedence(Record Goods Receipt, Record Invoice Receipt)`. Có điều
    kiện thì điều kiện là đối số thứ ba — mở rộng tự nhiên của ví dụ, do
    spec không định dạng riêng cho điều kiện. Mọi nơi trong gói learning
    dùng chung hàm này để khóa không lệch nhau.
    """
    if condition is None:
        return f"{template}({activation}, {target})"
    return f"{template}({activation}, {target}, {condition})"


def statement_for(template: str, activation: str, target: str, condition: str | None) -> str:
    """Suy câu ràng buộc dạng đọc được từ mẫu, hai hoạt động và điều kiện.

    Định dạng (Q1, đã duyệt): `f"{activation} {template} {target}"`, có
    điều kiện thì thêm `" when {condition}"`. Mẫu phủ định dùng tên mẫu
    nguyên văn (vd `"A not_response B"`) — nhất quán với `canonical_key`
    (cũng dùng tên mẫu nguyên văn), cơ học, không bịa bảng ánh xạ mẫu →
    cụm từ tự nhiên. Khớp bằng chứng duy nhất trong repo: test Applier
    dùng `"a response b"` cho template `"response"`.
    """
    base = f"{activation} {template} {target}"
    if condition is None:
        return base
    return f"{base} when {condition}"


class FactPayload(BaseModel):
    """Nội dung fact trong `payload` của candidate (Curator ghi, Applier đọc).

    Khóa này là hợp đồng giữa Curator (7.2) và Applier: Curator đặt các trường
    fact vào payload của candidate; Applier đọc đúng các trường này để ghi fact.
    `extra="forbid"` để một khóa lạ bị từ chối ngay. `source_episode_ids` của
    fact lấy từ `evidence_episode_ids` của candidate, không nằm trong payload.

    `kind` + `fact_id` không phải trường fact: `kind` là loại Delta
    (`"add"`/`"confirm"`/`"contradict"`/`"retire"`) để Applier quyết hành
    động; `fact_id` là id fact hiện hành bị tác động (None với ADD), để
    Applier biết đóng fact nào khi áp RETIRE/CONTRADICT (task P). Cả hai
    đều `None` được — payload của fact mới (ADD) không có fact bị tác động.
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
    kind: str | None = None
    fact_id: str | None = None

    @model_validator(mode="after")
    def _check_canonical_key_matches_template(self) -> Self:
        """Khóa canonical phải khớp mẫu + hai hoạt động + điều kiện.

        Bắt lỗi lệch khóa/mẫu ngay lúc tạo (vd payload CONTRADICT mang
        `canonical_key="response(A, B)"` nhưng `template="not_response"` —
        khóa suy từ mẫu phải là `"not_response(A, B)"`). Chỉ kiểm khi đủ
        dữ liệu để suy khóa (activation + target đều khác None); khi một
        trong hai là None thì bỏ qua (không đủ dữ liệu để suy khóa).
        """
        if self.activation is not None and self.target is not None:
            expected = canonical_key_for(
                self.template, self.activation, self.target, self.condition
            )
            if self.canonical_key != expected:
                raise ValueError(
                    f"canonical_key {self.canonical_key!r} khong khop template "
                    f"{self.template!r} -> {expected!r}"
                )
        return self
