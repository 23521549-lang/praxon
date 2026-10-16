"""Chuẩn hoá giá trị thô trước khi validate: tên và timestamp.

Hai hàm dưới đây là hàm thuần — không I/O, không đọc cấu hình — nên test
đơn vị không cần fixture. Mọi đường vào `Event` đều đi qua hai hàm này
(via `field_validator`), nên không có đường vòng lọt chuẩn hoá.
"""

from __future__ import annotations

from datetime import UTC, datetime


def normalize_name(name: str) -> str:
    """Chuẩn hoá tên: casefold + trim + gộp mọi whitespace thành một space.

    `casefold()` thay vì `lower()`: Python docs ghi casefold "more
    aggressive … intended to remove all case distinctions" — ví dụ 'ß'
    thành 'ss' trong khi `lower()` để nguyên. `" ".join(s.split())` làm
    trim + gộp khoảng trắng trong một bước, không cần regex.
    """
    return " ".join(name.casefold().split())


def normalize_timestamp(value: str | datetime) -> datetime:
    """Parse ISO 8601, bắt buộc có múi giờ, đổi về UTC.

    Nhận cả chuỗi và object datetime (dựng trực tiếp bằng code) — cả hai
    đều bắt buộc có tzinfo. Timestamp naive (không múi giờ) bị từ chối:
    giá trị naive là dữ liệu mơ hồ, không phải dữ liệu thiếu — ngầm hiểu
    là UTC thì sai lệch số liệu mà không để lại vết.
    """
    parsed = value if isinstance(value, datetime) else _parse_iso(value)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp thiếu múi giờ: {value!r}")
    return parsed.astimezone(UTC)


def _parse_iso(value: str) -> datetime:
    """Parse ISO 8601, bọc lỗi thành ValueError có thông điệp rõ."""
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"timestamp không đúng ISO 8601: {value!r}") from exc
