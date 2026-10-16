"""Nạp event log từ JSONL thành lược đồ bất biến (plan con 2).

Bất biến của package: mọi event sau parse đều frozen, mọi timestamp đều ở
UTC, mọi tên đã chuẩn hoá, một case_id chỉ gắn một variant. Chi tiết từng
bất biến ở module tương ứng.
"""

from praxon_core.ingest.jsonl import JsonlError, ParsedLine, ParseStats, parse_jsonl
from praxon_core.ingest.log import (
    DuplicateCaseError,
    build_log,
    canonical_hash,
    load_log,
)
from praxon_core.ingest.normalize import normalize_name, normalize_timestamp
from praxon_core.ingest.schema import Case, Event, Log

__all__ = [
    "Case",
    "DuplicateCaseError",
    "Event",
    "JsonlError",
    "Log",
    "ParseStats",
    "ParsedLine",
    "build_log",
    "canonical_hash",
    "load_log",
    "normalize_name",
    "normalize_timestamp",
    "parse_jsonl",
]
