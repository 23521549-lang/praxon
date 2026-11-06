"""Bốn chỉ số đánh giá (plan con 8, task 8.2; spec: bảng bốn chỉ số).

Bốn chỉ số luôn báo cùng nhau, theo từng tenant và từng điều kiện:

- Precision: phần fact `active` của tenant có trong tập tham chiếu của nó.
- Recall: phần tập tham chiếu của tenant có trong fact `active` của nó.
- Tỉ lệ vi phạm: phần fact `active` bị trace thật trên tập đo của tenant
  vi phạm quá 10%.
- Negative transfer: phần tỉ lệ vi phạm đến từ fact có nguồn gốc ngoài
  tenant — từ `global` hoặc từ kho gộp.

Đối chiếu fact với đáp án là so khớp chính xác trên `canonical_key` (spec,
mục Ground truth). Kiểm vi phạm trên trace dùng trực tiếp hai vị ngữ của
task 4.2 (`response_holds`, `precedence_holds`).

Mẫu số rỗng thì chỉ số là 0.0: không có fact `active` thì precision, tỉ lệ
vi phạm và negative transfer là 0; tập tham chiếu rỗng thì recall là 0;
không có trace đo thì không có bằng chứng vi phạm nên tỉ lệ vi phạm là 0.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from praxon_core.declare.index import (
    ActivityIndex,
    Trace,
    build_index,
    precedence_holds,
    response_holds,
)
from praxon_core.learning.candidate import FactStatus

VIOLATION_THRESHOLD = 0.10
"""Ngưỡng vi phạm của một fact: bị quá 10% trace đo vi phạm thì tính là vi phạm.

Con số 10% nằm trong định nghĩa của chỉ số trong spec (bảng bốn chỉ số),
không phải tham số hiệu chỉnh — nên nó là một hằng có tên ở đây, không phải
số chôn trong logic. So sánh là lớn hơn hẳn (`>`), đúng chữ "quá 10%" của
spec: vi phạm đúng 10% thì chưa tính.
"""


class FactScope(StrEnum):
    """Phạm vi của một fact (spec: bảng `fact`, cột `scope`)."""

    TENANT = "tenant"
    GLOBAL = "global"


@dataclass(frozen=True)
class Fact:
    """Một fact, góc nhìn tối thiểu của module eval (theo bảng `fact` của spec).

    Chỉ mang các trường bốn chỉ số cần: khóa canonical để đối chiếu với đáp
    án, mẫu + hai hoạt động để kiểm vi phạm trên trace, trạng thái để lọc
    fact `active`, phạm vi + tenant sở hữu để xác định nguồn gốc ngoài tenant.
    """

    canonical_key: str
    template: str
    activation: str
    target: str
    status: FactStatus
    scope: FactScope
    tenant_id: str


@dataclass(frozen=True)
class Metrics:
    """Bốn chỉ số của một tenant trong một điều kiện, luôn báo cùng nhau."""

    precision: float
    recall: float
    violation_rate: float
    negative_transfer: float


def _active_facts(facts: Sequence[Fact]) -> list[Fact]:
    """Chỉ lấy fact `active`; fact `trial` hay `retired` không vào chỉ số."""
    return [fact for fact in facts if fact.status is FactStatus.ACTIVE]


def _holds(fact: Fact, index: ActivityIndex) -> bool:
    """Fact có đúng trên một trace không, đọc qua chỉ mục vị trí của 4.2."""
    template = fact.template.strip().lower()
    if template == "response":
        return response_holds(index, fact.activation, fact.target)
    if template == "precedence":
        return precedence_holds(index, fact.activation, fact.target)
    raise ValueError(f"mẫu Declare không hỗ trợ: {fact.template!r}")


def _violation_fraction(fact: Fact, indexes: list[ActivityIndex]) -> float:
    """Phần trace đo vi phạm fact; không có trace đo thì là 0."""
    if not indexes:
        return 0.0
    violations = sum(1 for index in indexes if not _holds(fact, index))
    return violations / len(indexes)


def _is_external(fact: Fact, tenant_id: str) -> bool:
    """Fact có nguồn gốc ngoài tenant không: từ `global`, hoặc của tenant khác."""
    return fact.scope is FactScope.GLOBAL or fact.tenant_id != tenant_id


def _violated_facts(facts: Sequence[Fact], traces: Sequence[Trace]) -> list[Fact]:
    """Các fact `active` bị quá 10% trace đo vi phạm."""
    active = _active_facts(facts)
    indexes = [build_index(trace) for trace in traces]
    return [fact for fact in active if _violation_fraction(fact, indexes) > VIOLATION_THRESHOLD]


def precision(facts: Sequence[Fact], reference: set[str] | frozenset[str]) -> float:
    """Phần fact `active` có trong tập tham chiếu. Không có fact `active` thì 0."""
    active = _active_facts(facts)
    if not active:
        return 0.0
    correct = sum(1 for fact in active if fact.canonical_key in reference)
    return correct / len(active)


def recall(facts: Sequence[Fact], reference: set[str] | frozenset[str]) -> float:
    """Phần tập tham chiếu có trong fact `active`. Tập tham chiếu rỗng thì 0."""
    active = _active_facts(facts)
    if not reference:
        return 0.0
    active_keys = {fact.canonical_key for fact in active}
    found = sum(1 for key in reference if key in active_keys)
    return found / len(reference)


def f1_score(precision_value: float, recall_value: float) -> float:
    """Trung bình điều hòa của precision và recall (chỉ số F1).

    Dùng cho nghiệm thu bộ chuẩn 5.3: khám phá trên log do bộ sinh tạo ra
    đối chiếu với đáp án tuyệt đối của nó. Cả hai đều 0 thì không có bằng
    chứng đúng nào nên F1 là 0.
    """
    total = precision_value + recall_value
    if total == 0.0:
        return 0.0
    return 2 * precision_value * recall_value / total


def violated_flags(facts: Sequence[Fact], traces: Sequence[Trace]) -> list[bool]:
    """Từng fact `active` có bị quá 10% trace đo vi phạm không (theo thứ tự fact).

    Báo cáo baseline (8.5) cần cờ này để bootstrap khoảng tin cậy cho
    tỉ lệ vi phạm và negative transfer: tính một lần trên tập đo cố định
    rồi lấy mẫu lại các cờ, thay vì tính lại chỉ số trên mỗi lần rút.
    """
    active = _active_facts(facts)
    violated_keys = {fact.canonical_key for fact in _violated_facts(facts, traces)}
    return [fact.canonical_key in violated_keys for fact in active]


def violation_rate(facts: Sequence[Fact], traces: Sequence[Trace]) -> float:
    """Phần fact `active` bị quá 10% trace đo vi phạm. Không có fact `active` thì 0."""
    active = _active_facts(facts)
    if not active:
        return 0.0
    return len(_violated_facts(facts, traces)) / len(active)


def negative_transfer(facts: Sequence[Fact], traces: Sequence[Trace], tenant_id: str) -> float:
    """Phần tỉ lệ vi phạm đến từ fact ngoài tenant (global hoặc tenant khác)."""
    active = _active_facts(facts)
    if not active:
        return 0.0
    violated = _violated_facts(facts, traces)
    external = sum(1 for fact in violated if _is_external(fact, tenant_id))
    return external / len(active)


def compute_metrics(
    facts: Sequence[Fact],
    reference: set[str] | frozenset[str],
    traces: Sequence[Trace],
    tenant_id: str,
) -> Metrics:
    """Bốn chỉ số cùng nhau cho một tenant trong một điều kiện (spec: luôn báo cùng nhau)."""
    return Metrics(
        precision=precision(facts, reference),
        recall=recall(facts, reference),
        violation_rate=violation_rate(facts, traces),
        negative_transfer=negative_transfer(facts, traces, tenant_id),
    )
