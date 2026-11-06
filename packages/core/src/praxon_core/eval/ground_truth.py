"""Ground truth cho đánh giá (plan con 8, task 8.1; spec: mục Ground truth).

Đáp án không bao giờ được sinh bằng chính một điều kiện đang được so:

- Bộ chuẩn bán tổng hợp: đáp án là luật đã cài vào bộ sinh
  (`GeneratedLog.ground_truth`, xuất ra cùng lúc với log).
- BPIC 2015: đáp án là kết quả khám phá Declare trên phần ĐO của tenant
  — không phải phần học — với ngưỡng support và confidence cố định,
  dùng chung cho cả bảy điều kiện thí nghiệm (spec, bảng bảy điều kiện:
  Chỉ Declare, Cách ly, Gộp chung, Phân tầng bỏ phiếu, Phân tầng đồng
  thuận, Phân tầng phủ quyết, Tài liệu cộng dữ liệu).

Ngưỡng cố định: support 0,5, confidence 0,5 — cùng cặp ngưỡng báo cáo
khác biệt 3.4 và nghiệm thu bộ chuẩn 5.3 đã dùng trên log thật, nên đáp
án dùng đúng ngưỡng dự án đã đo với. Spec không cho số Declare cụ thể
(báo cáo 3.4 đã ghi rõ); 0,7 / 0,95 / 0,05 là của cổng Beta, không dùng
ở đây. Ngưỡng là HẰNG của module, không phải tham số: hàm xây đáp án
không nhận ngưỡng hay điều kiện — đổi điều kiện không thể đổi đáp án,
vì đáp án không biết điều kiện là gì.

Đối chiếu fact với đáp án là so khớp chính xác trên `canonical_key`
(spec, mục Ground truth). `GroundTruth` mang cả nguồn gốc (provenance)
để test kiểm được đáp án đến từ đâu: `generator` hay
`bpic2015-test-split`, kèm ngưỡng đã dùng.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from praxon_core.declare.index import Trace
from praxon_core.declare.miner import Rule, discover
from praxon_core.eval.metrics import Fact, FactScope
from praxon_core.learning.candidate import FactStatus
from praxon_core.synthetic.generator import GeneratedLog

GROUND_TRUTH_SUPPORT = 0.5
"""Ngưỡng support cố định cho đáp án BPIC 2015 (dùng chung bảy điều kiện).

Cùng ngưỡng báo cáo 3.4 và nghiệm thu 5.3 đã dùng; xem docstring module.
"""

GROUND_TRUTH_CONFIDENCE = 0.5
"""Ngưỡng confidence cố định cho đáp án BPIC 2015 (dùng chung bảy điều kiện)."""

GENERATOR_SOURCE = "generator"
"""Nguồn gốc đáp án bộ chuẩn: luật đã cài vào bộ sinh."""

BPIC_TEST_SPLIT_SOURCE = "bpic2015-test-split"
"""Nguồn gốc đáp án BPIC 2015: khám phá trên phần đo (không phải phần học)."""


@dataclass(frozen=True)
class GroundTruth:
    """Đáp án tham chiếu của một tenant, kèm nguồn gốc để kiểm.

    `reference` là tập khóa canonical. `source` cho biết đáp án đến từ
    bộ sinh hay từ khám phá trên phần đo — test 8.1 kiểm nguồn gốc này
    để chắc không điều kiện nào được chấm bằng đáp án sinh từ chính nó.
    `support`/`confidence` ghi ngưỡng đã dùng (luôn là hai hằng cố định
    của module với đáp án BPIC; 0 với đáp án bộ sinh vì bộ sinh không
    dùng ngưỡng khám phá).
    """

    tenant_id: str
    reference: frozenset[str]
    source: str
    support: float = 0.0
    confidence: float = 0.0


def ground_truth_from_generator(log: GeneratedLog) -> GroundTruth:
    """Đáp án bộ chuẩn: luật đã cài vào bộ sinh, xuất cùng log."""
    return GroundTruth(
        tenant_id=log.tenant_id,
        reference=log.ground_truth,
        source=GENERATOR_SOURCE,
    )


def ground_truth_from_test_traces(traces: Sequence[Trace], *, tenant_id: str) -> GroundTruth:
    """Đáp án BPIC 2015: khám phá trên phần đo với ngưỡng cố định.

    Chỉ nhận trace của phần đo — người gọi chịu trách nhiệm đưa đúng
    phần đo (lệnh báo cáo 8.5 tách phần đo bằng `datasets/split.py`).
    Hàm không nhận ngưỡng hay điều kiện: ngưỡng lấy từ hai hằng cố định
    của module, nên đáp án giống nhau cho mọi điều kiện.
    """
    rules = discover(
        traces,
        support=GROUND_TRUTH_SUPPORT,
        confidence=GROUND_TRUTH_CONFIDENCE,
    )
    return GroundTruth(
        tenant_id=tenant_id,
        reference=frozenset(rule.canonical_key for rule in rules),
        source=BPIC_TEST_SPLIT_SOURCE,
        support=GROUND_TRUTH_SUPPORT,
        confidence=GROUND_TRUTH_CONFIDENCE,
    )


def facts_from_rules(
    rules: frozenset[Rule] | Sequence[Rule],
    tenant_id: str,
    *,
    status: FactStatus = FactStatus.ACTIVE,
    scope: FactScope = FactScope.TENANT,
) -> list[Fact]:
    """Luật khám phá thành fact để đối chiếu bằng bốn chỉ số.

    Với cả hai mẫu, `activation`/`target` là hai hoạt động theo thứ tự
    trong khóa canonical (`response(x, y)`: x kích hoạt; `precedence(x, y)`:
    x phải đứng trước y) — đúng ngữ nghĩa `_holds` của eval. Mặc định
    fact `active` thuộc tenant (đường cong 8.4 và báo cáo 8.5 dùng mặc
    định này; điểm 0 của đường cong truyền `status=TRIAL` rồi chấm ở
    chế độ giám sát — xem `cold_start.py`).
    Trả fact theo thứ tự khóa canonical (đã sắp xếp): `discover` trả
    frozenset nên thứ tự lặp của nó thay đổi theo tiến trình (băm chuỗi
    ngẫu nhiên) — sắp xếp ở đây để mọi phép đo dùng fact (kể cả
    bootstrap lấy mẫu lại theo chỉ số) cho đúng kết quả khi chạy lại.
    """
    return sorted(
        (
            Fact(
                canonical_key=rule.canonical_key,
                template=rule.template,
                activation=rule.first,
                target=rule.second,
                status=status,
                scope=scope,
                tenant_id=tenant_id,
            )
            for rule in rules
        ),
        key=lambda fact: fact.canonical_key,
    )
