"""Bộ sinh bán tổng hợp (plan con 5, task 5.1; spec: Bộ chuẩn bán tổng hợp).

Mô hình quy trình: một dãy 8 bước theo thứ tự (`BASE_ORDER`). Mỗi tenant
có một thứ tự riêng, đổi có kiểm soát từ thứ tự gốc bằng cách hoán đổi hai
bước kề nhau (`swap_adjacent`) — luật thứ tự nào khác ở tenant nào biết
trước, nên có ground truth tuyệt đối.

Ground truth của một tenant là bao đóng của thứ tự của nó: với mọi cặp
bước (x, y) mà x đứng trước y, hai luật `response(x, y)` và
`precedence(x, y)` đều thuộc đáp án (spec, mục Ground truth: đáp án là luật
đã cài vào bộ sinh; đối chiếu bằng khớp chính xác trên `canonical_key`).
Với 8 bước, đáp án có 28 cặp x 2 mẫu = 56 luật.

Sinh trace (hàm thuần, chỉ dùng `random.Random` gieo từ seed + tenant):
- Bước tùy chọn (`optional`) bị bỏ qua với xác suất `skip_rate`, độc lập
  từng bước từng case.
- Case dở dang: với xác suất `incomplete_rate`, cắt ngắn trace tại một vị
  trí ngẫu nhiên (giữ lại ít nhất một sự kiện).
- Nhiễu: với xác suất `noise_level`, nhân đôi một sự kiện ngẫu nhiên ngay
  sau lần xuất hiện của nó (bước đó xảy ra hai lần liên tiếp). Bản sao đặt
  kề lần gốc nên trace vẫn tôn trọng thứ tự quy trình — nhiễu chỉ tạo hoạt
  động lặp lại (đúng proxy đã đo trong log thật), không phá luật thứ tự.

Cùng seed + cùng tenant ra cùng log (xác định); khác tenant hoặc khác seed
ra log khác. Đáp án xuất ra cùng lúc với log (`generate` trả cả hai).

Tham số mặc định lấy từ log thật BPIC 2015 (đo ngày 7/11/2026 bằng parser
XES của plan 3, trên cả 5 đô thị; task 5.2 kiểm bằng test rằng các tham số
này nằm trong khoảng đo được):
- `n_cases = 1.199` (số case đô thị 1; khoảng đo được 832-1.409);
- `skip_rate = 0,6` (gần trung vị tỉ lệ bỏ của bước tùy chọn, khoảng
  0,042-0,900);
- `incomplete_rate = 0,12` (tỉ lệ case không có `endDate` toàn bộ 664/5.649
  ≈ 0,118; khoảng theo đô thị 0,062-0,203);
- `noise_level = 0,35` (tỉ lệ trace có hoạt động lặp lại toàn bộ
  1.965/5.649 ≈ 0,348; khoảng theo đô thị 0,295-0,418).
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from praxon_core.declare.index import Trace

ACTIVITIES: tuple[str, ...] = (
    "step_01",
    "step_02",
    "step_03",
    "step_04",
    "step_05",
    "step_06",
    "step_07",
    "step_08",
)
"""Tám bước của quy trình (cùng cỡ với bộ sinh tám hoạt động của đợt 2)."""

BASE_ORDER: tuple[str, ...] = ACTIVITIES
"""Thứ tự gốc của quy trình: tám bước theo thứ tự."""

DEFAULT_OPTIONAL: frozenset[str] = frozenset({"step_03", "step_05", "step_07"})
"""Ba bước tùy chọn mặc định (3/8 bước, cùng bậc với tỉ lệ bước tùy chọn
trong log thật: 83-117 trên 356-410 loại hoạt động là tùy chọn)."""

# --- Khoảng đo được từ log thật BPIC 2015 (task 5.2) ---
# Đo ngày 7/11/2026 bằng parser XES của plan 3 (`datasets/xes.py`) trên cả
# 5 đô thị (tổng 5.649 case, 264.628 sự kiện). Mỗi khoảng là [nhỏ nhất,
# lớn nhất] theo đô thị. Định nghĩa đo (chốt trước khi đo, xem ghi chú
# từng hằng):
MEASURED_CASE_COUNT_RANGE: tuple[int, int] = (832, 1_409)
"""Khoảng số case theo đô thị (M2 832; M3 1.409). Tổng 5.649 case."""

MEASURED_SKIP_RATE_RANGE: tuple[float, float] = (0.042, 0.900)
"""Khoảng tỉ lệ bỏ của bước tùy chọn: với mỗi hoạt động xuất hiện ở
10-99% số case, tỉ lệ bỏ = 1 - (số case chứa hoạt động / tổng số case).
Nhỏ nhất 0,042 (M3), lớn nhất 0,900 (M5); trung vị theo đô thị 0,602-0,671.
"""

MEASURED_INCOMPLETE_RATE_RANGE: tuple[float, float] = (0.062, 0.203)
"""Khoảng tỉ lệ case dở dang: số trace không có thuộc tính `endDate` /
tổng số case (đo từ `Trace.attributes`). Nhỏ nhất 0,062 (M5), lớn nhất
0,203 (M1); gộp 5 đô thị 664/5.649 ≈ 0,118. Đối chiếu: `caseStatus` = 'O'
(mở) cho 0,057-0,452 — khoảng rộng hơn và ý nghĩa 'O'/'G' không có trong
log nên không dùng làm định nghĩa chính.
"""

MEASURED_NOISE_RATE_RANGE: tuple[float, float] = (0.295, 0.418)
"""Khoảng mức nhiễu: tỉ lệ trace có một hoạt động lặp lại (>= 2 lần).
Nhỏ nhất 0,295 (M4), lớn nhất 0,418 (M5); gộp 5 đô thị 1.965/5.649
≈ 0,348. Định nghĩa này khớp cơ chế nhiễu của bộ sinh (nhân đôi một sự
kiện tạo hoạt động lặp lại). Định nghĩa thay thế đã loại: tỉ lệ event có
`lifecycle:transition` = "incomplete"/"withdraw" — đo được 0,0000 ở cả 5
đô thị (mọi event đều "complete") nên không có tín hiệu, không dùng được.
"""


@dataclass(frozen=True)
class GeneratorParams:
    """Tham số bộ sinh của một tenant (đóng băng, hash được).

    `order` phải là một hoán vị của `ACTIVITIES` (chỉ đổi thứ tự, không đổi
    tập bước — đổi có kiểm soát). `optional` phải là tập con của `order`.
    Ba tỉ lệ nằm trong [0, 1].
    """

    seed: int
    n_cases: int = 1_199
    order: tuple[str, ...] = BASE_ORDER
    optional: frozenset[str] = DEFAULT_OPTIONAL
    skip_rate: float = 0.6
    incomplete_rate: float = 0.12
    noise_level: float = 0.35


@dataclass(frozen=True)
class GeneratedLog:
    """Kết quả sinh của một tenant: log kèm đáp án tuyệt đối của nó.

    `ground_truth` là tập khóa canonical của các luật đã cài vào bộ sinh
    cho tenant này — xuất ra cùng lúc với log, để khám phá đối chiếu.
    """

    tenant_id: str
    traces: tuple[Trace, ...]
    ground_truth: frozenset[str]


def ground_truth_for(order: tuple[str, ...]) -> frozenset[str]:
    """Bao đóng luật thứ tự của một thứ tự: mọi cặp (x trước y) cho hai luật.

    `response(x, y)` và `precedence(x, y)` với x đứng trước y trong thứ tự.
    """
    truth: set[str] = set()
    for position, first in enumerate(order):
        for second in order[position + 1 :]:
            truth.add(f"response({first}, {second})")
            truth.add(f"precedence({first}, {second})")
    return frozenset(truth)


def swap_adjacent(order: tuple[str, ...], index: int) -> tuple[str, ...]:
    """Đổi chỗ hai bước kề nhau tại vị trí `index` (đổi có kiểm soát).

    Trả thứ tự mới, không sửa thứ tự cũ. `index` phải nằm trong
    [0, len(order) - 2].
    """
    if not 0 <= index < len(order) - 1:
        raise ValueError(f"index phải nằm trong [0, {len(order) - 2}], nhận {index}")
    items = list(order)
    items[index], items[index + 1] = items[index + 1], items[index]
    return tuple(items)


def _validate_params(params: GeneratorParams) -> None:
    """Tham số sai thì lộ ra ngay (ValueError), không sinh log sai lặng lẽ."""
    if params.n_cases < 0:
        raise ValueError(f"n_cases phải >= 0, nhận {params.n_cases}")
    if sorted(params.order) != sorted(ACTIVITIES):
        raise ValueError("order phải là một hoán vị của ACTIVITIES")
    if not params.optional.issubset(params.order):
        raise ValueError("optional phải là tập con của order")
    for name, rate in (
        ("skip_rate", params.skip_rate),
        ("incomplete_rate", params.incomplete_rate),
        ("noise_level", params.noise_level),
    ):
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"{name} phải nằm trong [0, 1], nhận {rate}")


def _derive_seed(seed: int, tenant_id: str) -> int:
    """Gieo RNG từ (seed, tenant_id): ổn định qua mọi lần chạy và máy.

    Dùng SHA-256 của chuỗi canonical, không dùng `hash()` của Python (nó
    ngẫu nhiên theo tiến trình). Cùng seed + cùng tenant cho cùng dòng
    ngẫu nhiên; khác tenant cho dòng khác dù cùng seed.
    """
    digest = hashlib.sha256(f"{seed}:{tenant_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _generate_trace(rng: random.Random, params: GeneratorParams) -> Trace:
    """Sinh một trace: bỏ bước tùy chọn, có thể cắt ngắn, có thể nhân đôi."""
    events = [
        activity
        for activity in params.order
        if activity not in params.optional or rng.random() >= params.skip_rate
    ]
    if rng.random() < params.incomplete_rate and len(events) >= 2:
        events = events[: rng.randint(1, len(events) - 1)]
    if rng.random() < params.noise_level and events:
        position = rng.randrange(len(events))
        events.insert(position + 1, events[position])
    return Trace(tuple(events))


def generate(*, tenant_id: str, params: GeneratorParams) -> GeneratedLog:
    """Sinh log của một tenant kèm đáp án tuyệt đối của nó.

    Hàm thuần: cùng seed + cùng tenant + cùng tham số ra cùng log và cùng
    đáp án. Không đọc tệp, không gọi mô hình, không chạm cơ sở dữ liệu.
    """
    _validate_params(params)
    rng = random.Random(_derive_seed(params.seed, tenant_id))
    traces = tuple(_generate_trace(rng, params) for _ in range(params.n_cases))
    return GeneratedLog(
        tenant_id=tenant_id, traces=traces, ground_truth=ground_truth_for(params.order)
    )
