"""Khám phá Declare: lọc trước theo support x confidence rồi kiểm từng cặp.

Bộ khám phá chạy trên chỉ mục vị trí đầu/cuối của task 4.2
(`build_index`, `response_holds`, `precedence_holds`). Hai ngưỡng là tham
số, không hard-code:

- ``support``: tỉ lệ case tối thiểu mà luật được kích hoạt và thỏa mãn;
- ``confidence``: tỉ lệ tối thiểu trong các case đã kích hoạt mà luật thỏa mãn.

Lọc trước (spec, dòng 148): hoạt động xuất hiện ở ít hơn
``support x confidence`` phần case bị bỏ trước, vì không thể thuộc luật nào
qua được cả hai ngưỡng — với định nghĩa support/confidence ở trên, một luật
qua ngưỡng đòi cả hai hoạt động của nó xuất hiện ở ít nhất ``support`` phần
case, mà ``support x confidence <= support`` nên ngưỡng lọc là an toàn.

``discover_brute_force`` là bản duyệt thẳng làm tham chiếu: không lọc, quét
trực tiếp sự kiện từng trace cho từng cặp, không dùng chỉ mục. Hai tập luật
phải trùng nhau trên cùng dữ liệu; test 4.3 kiểm đúng điều đó.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from praxon_core.declare.index import (
    Trace,
    build_index,
    precedence_holds,
    response_holds,
)


@dataclass(frozen=True)
class Rule:
    """Một luật Declare đã qua ngưỡng support và confidence.

    ``first`` và ``second`` là hai hoạt động theo thứ tự trong khóa canonical
    (ví dụ ``precedence(a, b)`` nghĩa là a phải xảy ra trước b). Đối với
    ``response``, hoạt động kích hoạt là ``first``; đối với ``precedence``,
    hoạt động kích hoạt là ``second``.
    """

    template: str
    first: str
    second: str
    support: float
    confidence: float

    @property
    def canonical_key(self) -> str:
        """Khóa canonical theo spec: ``mẫu(hoạt động thứ nhất, hoạt động thứ hai)``."""
        return f"{self.template}({self.first}, {self.second})"


def _validate_thresholds(support: float, confidence: float) -> None:
    """Hai ngưỡng phải nằm trong [0, 1]."""
    if not 0.0 <= support <= 1.0:
        raise ValueError(f"support phải nằm trong [0, 1], nhận {support}")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"confidence phải nằm trong [0, 1], nhận {confidence}")


def _passes(
    satisfied: int, activated: int, total: int, support: float, confidence: float
) -> bool:
    """Luật qua ngưỡng khi cả support và confidence đều đạt.

    support = số case kích hoạt và thỏa mãn / tổng số case;
    confidence = số case kích hoạt và thỏa mãn / số case đã kích hoạt.
    Không case nào kích hoạt thì luật không có bằng chứng nên không qua.
    """
    if activated == 0:
        return False
    return satisfied / total >= support and satisfied / activated >= confidence


def frequent_activities(traces: Sequence[Trace], *, min_frequency: float) -> frozenset[str]:
    """Hoạt động xuất hiện ở ít nhất ``min_frequency`` phần case.

    Tần suất của một hoạt động là tỉ lệ case chứa nó (mỗi case tính một lần
    dù hoạt động lặp lại trong case đó).
    """
    total = len(traces)
    if total == 0:
        return frozenset()
    counts: Counter[str] = Counter()
    for trace in traces:
        for activity in set(trace.events):
            counts[activity] += 1
    return frozenset(
        activity for activity, count in counts.items() if count / total >= min_frequency
    )


def discover(
    traces: Sequence[Trace],
    *,
    support: float,
    confidence: float,
    pre_filter: bool = True,
) -> frozenset[Rule]:
    """Khám phá luật Declare trên các trace, có lọc trước theo support x confidence.

    Lọc trước (mặc định bật): chỉ giữ hoạt động xuất hiện ở ít nhất
    ``support x confidence`` phần case. Đặt ``pre_filter=False`` để khám phá
    không lọc (cổng ra 4.4 yêu cầu chạy không lọc dưới 30 giây).

    Đếm gộp theo trace: mỗi trace duyệt một lần, cập nhật số case thỏa mãn
    cho từng cặp hoạt động cùng xuất hiện trong trace đó — thay vì quét lại
    toàn bộ trace cho từng cặp — nên vẫn nhanh khi không lọc.
    """
    _validate_thresholds(support, confidence)
    total = len(traces)
    if total == 0:
        return frozenset()
    indexes = [build_index(trace) for trace in traces]
    counts: Counter[str] = Counter()
    for index in indexes:
        for activity in index:
            counts[activity] += 1
    if pre_filter:
        kept = {
            activity
            for activity, count in counts.items()
            if count / total >= support * confidence
        }
    else:
        kept = set(counts)
    satisfied: Counter[tuple[str, str, str]] = Counter()
    for index in indexes:
        present = [activity for activity in index if activity in kept]
        for first in present:
            for second in present:
                if first == second:
                    continue
                if response_holds(index, first, second):
                    satisfied[("response", first, second)] += 1
                if precedence_holds(index, first, second):
                    satisfied[("precedence", first, second)] += 1
    rules: set[Rule] = set()
    for first in kept:
        for second in kept:
            if first == second:
                continue
            activated = counts[first]
            hit = satisfied[("response", first, second)]
            if _passes(hit, activated, total, support, confidence):
                rules.add(Rule("response", first, second, hit / total, hit / activated))
            activated = counts[second]
            hit = satisfied[("precedence", first, second)]
            if _passes(hit, activated, total, support, confidence):
                rules.add(Rule("precedence", first, second, hit / total, hit / activated))
    return frozenset(rules)


def _brute_counts(
    traces: Sequence[Trace], first: str, second: str, template: str
) -> tuple[int, int]:
    """Đếm (kích hoạt và thỏa mãn, đã kích hoạt) bằng cách quét trực tiếp sự kiện.

    Tham chiếu độc lập với chỉ mục: ``response`` kích hoạt khi ``first`` xuất
    hiện, thỏa mãn khi ``second`` xuất hiện sau lần ``first`` cuối cùng;
    ``precedence`` kích hoạt khi ``second`` xuất hiện, thỏa mãn khi ``first``
    xuất hiện trước lần ``second`` đầu tiên.
    """
    satisfied = 0
    activated = 0
    for trace in traces:
        events = trace.events
        if template == "response":
            if first not in events:
                continue
            activated += 1
            last_first = max(i for i, event in enumerate(events) if event == first)
            if any(event == second for event in events[last_first + 1 :]):
                satisfied += 1
        else:
            if second not in events:
                continue
            activated += 1
            first_second = min(i for i, event in enumerate(events) if event == second)
            if any(event == first for event in events[:first_second]):
                satisfied += 1
    return satisfied, activated


def discover_brute_force(
    traces: Sequence[Trace], *, support: float, confidence: float
) -> frozenset[Rule]:
    """Tham chiếu duyệt thẳng: không lọc, quét trực tiếp từng trace cho từng cặp.

    Chỉ dùng cho lát nhỏ trong test — chậm hơn bộ khám phá chính nhiều lần vì
    quét lại toàn bộ trace cho từng cặp. Hai tập luật phải trùng nhau.
    """
    _validate_thresholds(support, confidence)
    total = len(traces)
    if total == 0:
        return frozenset()
    activities: set[str] = set()
    for trace in traces:
        activities.update(trace.events)
    rules: set[Rule] = set()
    for first in activities:
        for second in activities:
            if first == second:
                continue
            hit, activated = _brute_counts(traces, first, second, "response")
            if _passes(hit, activated, total, support, confidence):
                rules.add(Rule("response", first, second, hit / total, hit / activated))
            hit, activated = _brute_counts(traces, first, second, "precedence")
            if _passes(hit, activated, total, support, confidence):
                rules.add(Rule("precedence", first, second, hit / total, hit / activated))
    return frozenset(rules)
