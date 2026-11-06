"""Tham số bộ sinh từ log thật (task 5.2, plan con 5).

Cổng ra: tham số bộ sinh nằm trong khoảng đo được từ log thật. Khoảng đo
(từ `praxon_core.synthetic.generator`, đo ngày 7/11/2026 bằng parser XES
của plan 3 trên cả 5 đô thị): số case 832-1.409, tỉ lệ bỏ 0,042-0,900,
tỉ lệ case dở dang 0,062-0,203, mức nhiễu 0,295-0,418.

Ngoài cổng khoảng, test thống kê tách riêng từng cơ chế (chỉ bật một tham
số, tắt hai tham số còn lại) để chứng minh bộ sinh thật sự tôn trọng tham
số của nó, không chỉ khai báo đúng khoảng.
"""

from praxon_core.declare.index import Trace
from praxon_core.synthetic.generator import (
    BASE_ORDER,
    DEFAULT_OPTIONAL,
    MEASURED_CASE_COUNT_RANGE,
    MEASURED_INCOMPLETE_RATE_RANGE,
    MEASURED_NOISE_RATE_RANGE,
    MEASURED_SKIP_RATE_RANGE,
    GeneratorParams,
    generate,
)

# Dung sai thống kê cho test tách cơ chế (n = 5.000 case, sai số chuẩn
# ~0,005-0,007 nên ±0,05 là hơn 7 sigma — không flaky).
TOLERANCE = 0.05
N_STAT = 5_000


def _missing_rate(traces: tuple[Trace, ...], activity: str) -> float:
    """Tỉ lệ trace không chứa một hoạt động."""
    return sum(1 for trace in traces if activity not in trace.events) / len(traces)


def _repeat_rate(traces: tuple[Trace, ...]) -> float:
    """Tỉ lệ trace có một hoạt động lặp lại."""
    return sum(1 for trace in traces if len(set(trace.events)) < len(trace.events)) / len(
        traces
    )


def test_tham_so_mac_dinh_nam_trong_khoang_do_duoc():
    params = GeneratorParams(seed=1)
    case_low, case_high = MEASURED_CASE_COUNT_RANGE
    assert case_low <= params.n_cases <= case_high
    skip_low, skip_high = MEASURED_SKIP_RATE_RANGE
    assert skip_low <= params.skip_rate <= skip_high
    incomplete_low, incomplete_high = MEASURED_INCOMPLETE_RATE_RANGE
    assert incomplete_low <= params.incomplete_rate <= incomplete_high
    noise_low, noise_high = MEASURED_NOISE_RATE_RANGE
    assert noise_low <= params.noise_level <= noise_high


def test_bo_buoc_ton_trong_skip_rate():
    params = GeneratorParams(
        seed=11, n_cases=N_STAT, skip_rate=0.6, incomplete_rate=0.0, noise_level=0.0
    )
    log = generate(tenant_id="acme", params=params)
    for activity in DEFAULT_OPTIONAL:
        assert abs(_missing_rate(log.traces, activity) - 0.6) <= TOLERANCE
    for activity in BASE_ORDER:
        if activity not in DEFAULT_OPTIONAL:
            assert _missing_rate(log.traces, activity) == 0.0


def test_case_do_dang_ton_trong_incomplete_rate():
    params = GeneratorParams(
        seed=12, n_cases=N_STAT, skip_rate=0.0, incomplete_rate=0.12, noise_level=0.0
    )
    log = generate(tenant_id="acme", params=params)
    # step_08 là bước cuối bắt buộc: chỉ cắt ngắn mới làm mất nó.
    assert abs(_missing_rate(log.traces, "step_08") - 0.12) <= TOLERANCE


def test_nhieu_ton_trong_noise_level():
    params = GeneratorParams(
        seed=13, n_cases=N_STAT, skip_rate=0.0, incomplete_rate=0.0, noise_level=0.35
    )
    log = generate(tenant_id="acme", params=params)
    assert abs(_repeat_rate(log.traces) - 0.35) <= TOLERANCE


def test_log_mac_dinh_co_thong_ke_trong_khoang_do_duoc():
    log = generate(tenant_id="acme", params=GeneratorParams(seed=14, n_cases=N_STAT))
    noise_low, noise_high = MEASURED_NOISE_RATE_RANGE
    assert noise_low <= _repeat_rate(log.traces) <= noise_high
    incomplete_low, incomplete_high = MEASURED_INCOMPLETE_RATE_RANGE
    assert incomplete_low <= _missing_rate(log.traces, "step_08") <= incomplete_high
    skip_low, skip_high = MEASURED_SKIP_RATE_RANGE
    for activity in DEFAULT_OPTIONAL:
        assert skip_low <= _missing_rate(log.traces, activity) <= skip_high
