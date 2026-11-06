"""Log giả có seed, cỡ đô thị 1 (M1) của BPIC 2015.

Dùng chung cho task 4.3/4.4/4.5: cùng một log giả cho lọc trước, test hiệu
năng, và đối chiếu pm4py. Cỡ M1 theo spec (dòng 172 và 148): 1.199 case,
356-410 loại hoạt động, 44-60 nghìn sự kiện.

Mỗi trace có một "xương sống" 8 hoạt động xuất hiện theo thứ tự trong mọi
trace, nên luôn có luật Response/Precedence thật để khám phá (không phải
log nhiễu thuần túy). Phần còn lại là hoạt động nhiễu rút từ pool 372 loại
(trừ xương sống) với trọng số theo tầng tần suất — vài hoạt động thường gặp,
đa số hiếm — như log thật.
"""

from __future__ import annotations

import random

from praxon_core.declare.index import Trace

# Cỡ M1 (spec, dòng 172 và 148).
M1_CASES = 1_199
M1_ACTIVITIES = 380
M1_MIN_TRACE_LEN = 30
M1_MAX_TRACE_LEN = 50
M1_SEED = 20261003

# Xương sống: 8 hoạt động, theo thứ tự, trong mọi trace.
SKELETON = (
    "core_00",
    "core_01",
    "core_02",
    "core_03",
    "core_04",
    "core_05",
    "core_06",
    "core_07",
)

# Pool nhiễu: 372 loại (8 xương sống + 372 = 380 loại, trong khoảng 356-410).
_NOISE_POOL_SIZE = 372
# Tầng tần suất: 20 hoạt động thường gặp, 100 trung bình, 252 hiếm.
_NOISE_WEIGHTS = [20.0] * 20 + [5.0] * 100 + [1.0] * 252


def _noise_pool() -> tuple[list[str], list[float]]:
    """Pool hoạt động nhiễu (372 loại) kèm trọng số theo tầng tần suất."""
    pool = [f"act_{i:03d}" for i in range(_NOISE_POOL_SIZE)]
    return pool, _NOISE_WEIGHTS


def generate_log(
    *,
    n_traces: int,
    seed: int,
    min_trace_len: int = M1_MIN_TRACE_LEN,
    max_trace_len: int = M1_MAX_TRACE_LEN,
) -> list[Trace]:
    """Sinh log giả có seed: xương sống + hoạt động nhiễu theo tầng tần suất.

    Mỗi trace: 8 hoạt động xương sống giữ nguyên thứ tự, xen kẽ hoạt động
    nhiễu rút từ pool 372 loại (trừ xương sống) với trọng số theo tầng.
    Cùng seed cho cùng log — chạy lại cho đúng kết quả.
    """
    rng = random.Random(seed)
    pool, weights = _noise_pool()
    traces: list[Trace] = []
    for _ in range(n_traces):
        length = rng.randint(min_trace_len, max_trace_len)
        n_noise = length - len(SKELETON)
        noise = rng.choices(pool, weights=weights, k=n_noise)
        events: list[str] = list(SKELETON)
        for activity in noise:
            events.insert(rng.randrange(len(events) + 1), activity)
        traces.append(Trace(events=tuple(events)))
    return traces


def m1_log(*, seed: int = M1_SEED) -> list[Trace]:
    """Log giả cỡ đô thị 1 (M1): 1.199 case, 380 loại, 44-60k sự kiện."""
    return generate_log(n_traces=M1_CASES, seed=seed)
