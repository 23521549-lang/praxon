"""Chỉ mục vị trí đầu và cuối của mỗi hoạt động trong mỗi trace.

Một lần duyệt trace ghi lại, cho mỗi hoạt động, vị trí đầu tiên và vị trí
cuối cùng nó xuất hiện. Hai vị ngữ Declare của task 4.2 đọc thẳng trên chỉ
mục này, không quét lại trace:

- `Response(a, b)` đúng khi b xuất hiện sau lần a cuối cùng;
- `Precedence(a, b)` đúng khi lần a đầu tiên trước lần b đầu tiên.

Ngữ nghĩa suy từ định nghĩa hình thức trong bài báo, đúng quy tắc clean room
theo spec. Vị trí đếm từ 0.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Trace:
    """Một trace: dãy hoạt động theo thứ tự xảy ra, bất biến sau khi tạo."""

    events: tuple[str, ...]


@dataclass(frozen=True)
class ActivitySpan:
    """Vị trí đầu và cuối của một hoạt động trong một trace."""

    first: int
    last: int


ActivityIndex = dict[str, ActivitySpan]


def build_index(trace: Trace) -> ActivityIndex:
    """Duyệt một lần, ghi vị trí đầu và cuối của mỗi hoạt động trong trace."""
    index: ActivityIndex = {}
    for position, activity in enumerate(trace.events):
        span = index.get(activity)
        if span is None:
            index[activity] = ActivitySpan(first=position, last=position)
        else:
            index[activity] = ActivitySpan(first=span.first, last=position)
    return index


def response_holds(index: ActivityIndex, a: str, b: str) -> bool:
    """`Response(a, b)` đúng khi b xuất hiện sau lần a cuối cùng.

    a không xuất hiện thì ràng buộc thỏa mãn một cách hiển nhiên; a xuất hiện
    mà b không xuất hiện sau lần a cuối thì sai. a và b là cùng một hoạt động
    thì sai khi hoạt động đó xuất hiện, vì không có lần nào sau lần cuối cùng.
    """
    first_span = index.get(a)
    if first_span is None:
        return True
    second_span = index.get(b)
    if second_span is None:
        return False
    return second_span.last > first_span.last


def precedence_holds(index: ActivityIndex, a: str, b: str) -> bool:
    """`Precedence(a, b)` đúng khi lần a đầu tiên trước lần b đầu tiên.

    b không xuất hiện thì ràng buộc thỏa mãn một cách hiển nhiên; b xuất hiện
    mà a không xuất hiện trước đó thì sai. a và b là cùng một hoạt động thì
    sai khi hoạt động đó xuất hiện, vì lần đầu tiên không trước chính nó.
    """
    second_span = index.get(b)
    if second_span is None:
        return True
    first_span = index.get(a)
    if first_span is None:
        return False
    return first_span.first < second_span.first
