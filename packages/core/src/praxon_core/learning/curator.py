"""Curator sinh Delta (task 7.2, spec: bảng vai vòng học, dòng 82).

Hàm thuần: nhận một Insight và fact hiện hành, trả danh sách Delta
(`ADD`, `CONFIRM`, `CONTRADICT`, `RETIRE`) rồi thành Candidate cho
Governor. Không gọi mô hình, không chạm cơ sở dữ liệu.

So khớp là so khớp chính xác trên `canonical_key` (spec dòng 82): Insight
mới mà chưa fact nào có khóa đó thì `ADD`; trùng khóa với fact đang giữ
(`trial` hoặc `active`) thì `CONFIRM`. Mâu thuẫn trực tiếp nhận ra qua
bảng cặp mẫu đối nghịch: Insight đối nghịch với fact `active` thì
`CONTRADICT` (xung đột cần Governor quyết); đối nghịch với fact `trial`
thì `RETIRE` (fact thử nghiệm chưa từng được xác nhận, có bằng chứng ngược
là nghỉ). Fact đã `retired` không chặn gì — Insight đối nghịch hoặc trùng
khóa với fact đã nghỉ được xem như đề xuất mới (`ADD`).

Bảng cặp mẫu đối nghịch chỉ có hai mẫu miner đang có (Response,
Precedence) và phủ định của chúng — mẫu phủ định là mẫu quan hệ phủ định
chuẩn của Declare (NotResponse, NotPrecedence), cặp phủ định của nhau
theo Di Ciccio và cộng sự, "Declarative Process Specifications"
(Response vs NotResponse là ví dụ nêu trong tài liệu). Mở rộng bảng khi
ADR 4.1 chốt từ vựng đầy đủ.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from praxon_core.learning.candidate import Candidate, FactStatus


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


#: Bảng cặp mẫu đối nghịch (chỉ Response và Precedence, mẫu miner đang có).
#: Mỗi mẫu ánh xạ tới phủ định của nó; quan hệ đối xứng. Nguồn: mẫu quan
#: hệ phủ định chuẩn của Declare (NotResponse, NotPrecedence) và quan hệ
#: "negated versions of one another" trong Di Ciccio và cộng sự.
OPPOSITE_TEMPLATES: dict[str, str] = {
    "response": "not_response",
    "not_response": "response",
    "precedence": "not_precedence",
    "not_precedence": "precedence",
}


def opposite_template(template: str) -> str | None:
    """Trả mẫu đối nghịch của `template`, hoặc None nếu chưa có trong bảng."""
    return OPPOSITE_TEMPLATES.get(template)


class InsightSource(StrEnum):
    """Insight đến từ đâu — Reflector có hai đường vào (spec dòng 76)."""

    TRACE = "trace"
    DOCUMENT = "document"


class Insight(BaseModel):
    """Một Insight: ràng buộc Declare đề xuất kèm case làm bằng chứng.

    Spec (dòng 76): đầu ra của Reflector. `scope` là phạm vi đề xuất (một
    tenant, hoặc `global`); `source` cho Governor biết Insight từ trace
    hay từ tài liệu (luật 2 dùng Wilson cho Insight từ trace).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    template: str
    activation: str
    target: str
    condition: str | None = None
    evidence_episode_ids: list[str]
    source: InsightSource
    scope: str

    @property
    def canonical_key(self) -> str:
        """Khóa canonical của ràng buộc đề xuất."""
        return canonical_key_for(self.template, self.activation, self.target, self.condition)


class FactRead(BaseModel):
    """Một fact hiện hành, đọc tối thiểu để Curator so khớp.

    Chỉ gồm các trường Curator dùng: khóa canonical (so khớp), mẫu +
    hai hoạt động + điều kiện (tính khóa đối nghịch), trạng thái (phân
    biệt `CONTRADICT` với `RETIRE`), phạm vi và id (đưa vào Candidate).
    Không gồm support/confidence/khoảng hiệu lực — Curator không dùng.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    scope: str
    canonical_key: str
    template: str
    activation: str
    target: str
    condition: str | None = None
    status: FactStatus


class DeltaKind(StrEnum):
    """Bốn loại Delta của Curator (spec dòng 77)."""

    ADD = "add"
    CONFIRM = "confirm"
    CONTRADICT = "contradict"
    RETIRE = "retire"


class Delta(BaseModel):
    """Một Delta: một thay đổi đề xuất lên một fact (hoặc thêm fact mới).

    `canonical_key` là khóa của fact bị tác động (với `ADD` là khóa của
    ràng buộc mới). `fact` là fact hiện hành bị tác động, None với `ADD`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: DeltaKind
    canonical_key: str
    insight: Insight
    fact: FactRead | None = None
    rationale: str


def curate(insight: Insight, facts: list[FactRead]) -> list[Delta]:
    """So một Insight với fact hiện hành, sinh Delta.

    Chỉ xét fact cùng phạm vi với Insight. Thông thường trả đúng một Delta;
    trường hợp bệnh (tập fact chứa cả khóa lẫn khóa đối nghịch) trả hai
    Delta để Governor xử lý — Curator không tự ý bỏ qua mâu thuẫn.
    """
    scoped = [fact for fact in facts if fact.scope == insight.scope]
    deltas: list[Delta] = []
    for fact in scoped:
        if fact.canonical_key != insight.canonical_key:
            continue
        if fact.status is FactStatus.RETIRED:
            continue
        deltas.append(
            Delta(
                kind=DeltaKind.CONFIRM,
                canonical_key=fact.canonical_key,
                insight=insight,
                fact=fact,
                rationale=(
                    f"Insight trùng khóa với fact {fact.id} "
                    f"({fact.status.value}), xác nhận fact này"
                ),
            )
        )
    opposite = opposite_template(insight.template)
    if opposite is not None:
        opposite_key = canonical_key_for(
            opposite, insight.activation, insight.target, insight.condition
        )
        for fact in scoped:
            if fact.canonical_key != opposite_key:
                continue
            if fact.status is FactStatus.RETIRED:
                continue
            if fact.status is FactStatus.TRIAL:
                deltas.append(
                    Delta(
                        kind=DeltaKind.RETIRE,
                        canonical_key=fact.canonical_key,
                        insight=insight,
                        fact=fact,
                        rationale=(
                            f"Insight đối nghịch trực tiếp với fact {fact.id} "
                            f"đang ở trạng thái trial, nghỉ fact này"
                        ),
                    )
                )
            else:
                deltas.append(
                    Delta(
                        kind=DeltaKind.CONTRADICT,
                        canonical_key=fact.canonical_key,
                        insight=insight,
                        fact=fact,
                        rationale=(
                            f"Insight đối nghịch trực tiếp với fact {fact.id} "
                            f"đang ở trạng thái active, xung đột cần quyết"
                        ),
                    )
                )
    if not deltas:
        deltas.append(
            Delta(
                kind=DeltaKind.ADD,
                canonical_key=insight.canonical_key,
                insight=insight,
                fact=None,
                rationale="Insight mới, chưa có fact nào cùng khóa hay đối nghịch",
            )
        )
    return deltas


def to_candidate(delta: Delta) -> Candidate:
    """Một Delta thành Candidate cho Governor (spec dòng 77).

    `target_scope` lấy từ phạm vi của Insight; `payload` mang đủ thông tin
    để Applier hành động (loại delta, khóa, ràng buộc đề xuất, fact bị tác
    động nếu có); `status` ban đầu là `pending`.
    """
    insight = delta.insight
    fact = delta.fact
    return Candidate(
        target_scope=insight.scope,
        payload={
            "kind": delta.kind.value,
            "canonical_key": delta.canonical_key,
            "template": insight.template,
            "activation": insight.activation,
            "target": insight.target,
            "condition": insight.condition,
            "fact_id": fact.id if fact is not None else None,
            "fact_canonical_key": fact.canonical_key if fact is not None else None,
            "fact_status": fact.status.value if fact is not None else None,
        },
        rationale=delta.rationale,
        evidence_episode_ids=list(insight.evidence_episode_ids),
        status="pending",
    )
