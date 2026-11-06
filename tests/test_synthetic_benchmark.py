"""Nghiệm thu bộ chuẩn (task 5.3, plan con 5).

Cổng ra: khám phá trên 300 trace do bộ sinh tạo ra cho F1 dưới 1,00 so
với đáp án tuyệt đối mà bộ sinh phát ra cùng log. Một bộ chuẩn mà mọi
phương pháp đều đạt trần thì không phân biệt được thiết kế nào — nên
F1 phải dưới 1,00.

Ngưỡng khám phá: support 0,5, confidence 0,5 (cùng ngưỡng báo cáo khác
biệt 3.4 dùng trên log thật). Độ khó là tham số mặc định của bộ sinh
(đo từ log thật, task 5.2): skip 0,6, incomplete 0,12, noise 0,35.

F1 đo được ngày 7/11/2026 (seed 42, 300 trace, tenant mặc định):
precision 1,0, recall 20/56, F1 ≈ 0,5263 — dưới 1,00 với biên độ lớn,
không cần tăng độ khó. Vì sao: trong 56 luật đáp án, 36 luật chạm một
bước tùy chọn — với skip 0,6, confidence của chúng chỉ ≈ 0,4, dưới
ngưỡng 0,5 nên bộ khám phá bỏ qua; chỉ 20 luật giữa 5 bước bắt buộc
(10 cặp x 2 mẫu) qua ngưỡng. Precision 1,0: bộ khám phá không bịa luật
ngoài đáp án, vì trace tôn trọng thứ tự tenant và nhiễu chỉ nhân đôi
sự kiện kề nhau. Cùng F1 đo được trên tenant đổi thứ tự (hoán đổi
step_04/step_05) và ổn định qua các seed 1, 7, 42, 20261003 (đã đo
trước khi viết test).
"""

from praxon_core.declare.miner import discover
from praxon_core.eval.ground_truth import facts_from_rules
from praxon_core.eval.metrics import f1_score, precision, recall
from praxon_core.synthetic.generator import (
    BASE_ORDER,
    DEFAULT_OPTIONAL,
    GeneratorParams,
    generate,
    swap_adjacent,
)

# Cỡ mẫu nghiệm thu theo task 5.3; ngưỡng khám phá như báo cáo 3.4.
N_BENCHMARK = 300
SUPPORT = 0.5
CONFIDENCE = 0.5
SEED = 42


def _measure_f1(*, tenant_id: str, params: GeneratorParams) -> tuple[float, float, float]:
    """Khám phá trên log do bộ sinh tạo, trả (precision, recall, F1)."""
    log = generate(tenant_id=tenant_id, params=params)
    rules = discover(log.traces, support=SUPPORT, confidence=CONFIDENCE)
    facts = facts_from_rules(rules, tenant_id)
    precision_value = precision(facts, log.ground_truth)
    recall_value = recall(facts, log.ground_truth)
    return precision_value, recall_value, f1_score(precision_value, recall_value)


def test_kham_pha_tren_300_trace_cho_f1_duoi_1():
    precision_value, recall_value, f1_value = _measure_f1(
        tenant_id="acme", params=GeneratorParams(seed=SEED, n_cases=N_BENCHMARK)
    )
    assert precision_value == 1.0
    assert recall_value == 20 / 56
    assert f1_value < 1.00
    assert abs(f1_value - 0.5263157894736842) < 1e-12


def test_chi_luat_giua_buoc_bat_buoc_qua_nguong():
    log = generate(tenant_id="acme", params=GeneratorParams(seed=SEED, n_cases=N_BENCHMARK))
    rules = discover(log.traces, support=SUPPORT, confidence=CONFIDENCE)
    keys = {rule.canonical_key for rule in rules}
    mandatory = [a for a in BASE_ORDER if a not in DEFAULT_OPTIONAL]
    expected = set()
    for position, first in enumerate(mandatory):
        for second in mandatory[position + 1 :]:
            expected.add(f"response({first}, {second})")
            expected.add(f"precedence({first}, {second})")
    assert keys == expected


def test_tenant_doi_thu_tu_cung_cho_f1_duoi_1():
    swapped = swap_adjacent(BASE_ORDER, 3)
    _, _, f1_value = _measure_f1(
        tenant_id="globex",
        params=GeneratorParams(seed=SEED, n_cases=N_BENCHMARK, order=swapped),
    )
    assert f1_value < 1.00
