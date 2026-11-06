"""Test hiệu năng khám phá Declare (task 4.4).

Cổng ra (plan, task 4.4): ``pytest tests/perf`` dưới 30 giây trên log giả
cỡ đô thị 1 (M1), không lọc trước. M1 theo spec (dòng 172 và 148): 1.199
case, 356-410 loại hoạt động, 44-60 nghìn sự kiện.

Chạy cổng này với ``--no-cov``: đo coverage làm chậm vòng lặp trong của
miner (gấp ~4 lần CPU) nên thời gian đo không còn phản ánh tốc độ thật, và
ngưỡng coverage 85% là cổng của toàn bộ test suite — một lát con
(tests/perf) vốn chỉ bao phủ ~15% mã nên không áp được.
"""

import time

from praxon_core.declare.miner import discover
from tests.synthetic_log import M1_CASES, M1_SEED, m1_log

PERF_LIMIT_SECONDS = 30.0
SUPPORT = 0.5
CONFIDENCE = 0.5


def test_discover_m1_khong_loc_duoi_30_giay():
    traces = m1_log(seed=M1_SEED)
    assert len(traces) == M1_CASES
    distinct = {event for trace in traces for event in trace.events}
    assert 356 <= len(distinct) <= 410
    total_events = sum(len(trace.events) for trace in traces)
    assert 44_000 <= total_events <= 60_000
    start = time.perf_counter()
    rules = discover(traces, support=SUPPORT, confidence=CONFIDENCE, pre_filter=False)
    elapsed = time.perf_counter() - start
    assert elapsed < PERF_LIMIT_SECONDS
    assert rules
