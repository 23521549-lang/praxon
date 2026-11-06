"""Đọc log XES bằng streaming (task 3.2, plan con 3).

XES là XML: một `<log>` chứa nhiều `<trace>` (case), mỗi trace chứa
nhiều `<event>`. Tệp BPIC 2015 ~40MB/log nên đọc bằng `iterparse` và
xóa từng trace sau khi xử lý — không nạp cả cây vào bộ nhớ.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def _local_name(tag: str) -> str:
    """Tên thẻ không có namespace (vd `{...}trace` → `trace`)."""
    return tag.rsplit("}", 1)[-1]


def _parse_value(element: ET.Element) -> str | None:
    """Giá trị của một thuộc tính XES (`string`/`date`/`int`/…)."""
    if _local_name(element.tag) in ("string", "date", "int", "float", "boolean"):
        return element.get("value")
    return None


def _parse_attributes(element: ET.Element) -> dict[str, str]:
    """Thuộc tính trực tiếp của một `<trace>`/`<event>` (không lồng nhau)."""
    attrs: dict[str, str] = {}
    for child in element:
        value = _parse_value(child)
        if value is not None:
            key = child.get("key", "")
            if key:
                attrs[key] = value
    return attrs


def _parse_timestamp(raw: str | None) -> datetime | None:
    """Đọc ISO 8601 có múi giờ; sai định dạng thì bỏ qua (None)."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


@dataclass(frozen=True)
class Event:
    """Một sự kiện trong trace: hoạt động + thời điểm + thuộc tính."""

    activity: str
    timestamp: datetime | None
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Trace:
    """Một case: định danh, thời điểm bắt đầu, danh sách sự kiện."""

    case_id: str
    start: datetime | None
    events: tuple[Event, ...] = ()
    attributes: dict[str, str] = field(default_factory=dict)


def iter_traces(path: Path) -> Iterator[Trace]:
    """Yield từng trace trong một tệp XES (streaming, tiết kiệm bộ nhớ)."""
    context = ET.iterparse(path, events=("end",))
    for _, elem in context:
        if _local_name(elem.tag) != "trace":
            continue
        trace_attrs = _parse_attributes(elem)
        case_id = trace_attrs.get("concept:name", "")
        start = _parse_timestamp(trace_attrs.get("startDate"))
        events: list[Event] = []
        for event_elem in elem:
            if _local_name(event_elem.tag) != "event":
                continue
            event_attrs = _parse_attributes(event_elem)
            activity = event_attrs.get("concept:name", "")
            timestamp = _parse_timestamp(event_attrs.get("time:timestamp"))
            events.append(Event(activity, timestamp, event_attrs))
        if start is None and events:
            start = events[0].timestamp
        yield Trace(case_id, start, tuple(events), trace_attrs)
        elem.clear()
