"""Lược đồ dữ liệu nạp: event = 1 dòng bất biến (task 2.1).

Ba model dưới đây là bản cài đặt bằng máy của lược đồ v1: mỗi event là một
dòng JSONL, mỗi dòng sau parse và chuẩn hoá thì bất biến (`frozen=True`).
`extra="forbid"` để trường lạ bị từ chối ngay lúc nạp thay vì bị bỏ qua im
lặng — cùng triết lý với `Settings`.

Tên `Event` đặt trong namespace `ingest` nên không lẫn với bảng `event`
(audit vòng học) trong spec.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from praxon_core.ingest.normalize import normalize_name, normalize_timestamp


class Event(BaseModel):
    """Một event trong log: 1 dòng JSONL đã chuẩn hoá, bất biến."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    variant: str = Field(min_length=1)
    activity: str = Field(min_length=1)
    occurred_at: datetime

    @field_validator("case_id", mode="before")
    @classmethod
    def _strip_case_id(cls, value: object) -> object:
        """Trim case_id trước khi check min_length."""
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("variant", "activity", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> object:
        """Chuẩn hoá tên trước khi validate kiểu."""
        if isinstance(value, str):
            return normalize_name(value)
        return value

    @field_validator("occurred_at", mode="before")
    @classmethod
    def _normalize_timestamp(cls, value: object) -> object:
        """Chuẩn hoá timestamp về UTC.

        Kiểu khác str/datetime bị từ chối tường minh: pydantic tự ép int
        thành datetime (unix timestamp) nên để lọt là sai lệch im lặng.
        """
        if isinstance(value, (str, datetime)):
            return normalize_timestamp(value)
        raise ValueError(
            "occurred_at phải là chuỗi ISO 8601 hoặc datetime, "
            f"không phải {type(value).__name__}"
        )


class Case(BaseModel):
    """Một case: các event cùng case_id, sắp theo thời điểm."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    variant: str = Field(min_length=1)
    events: tuple[Event, ...] = Field(min_length=1)


class Log(BaseModel):
    """Toàn bộ log đã lắp ráp: các case sắp theo case_id + data_hash."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cases: tuple[Case, ...]
    data_hash: str = Field(min_length=1)
