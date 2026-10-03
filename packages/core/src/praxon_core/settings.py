"""Cấu hình có kiểu, nạp từ một tệp.

Đây là module DUY NHẤT trong `praxon_core` được phép đọc biến môi trường. Lý do:
rải `os.environ` khắp mã nghiệp vụ thì không ai biết hệ cần những biến nào, và
một biến thiếu chỉ lộ ra lúc chạy. Cổng `tools/check_env_access.py` canh điều
đó bằng cách phân tích cú pháp, không bằng khớp chuỗi.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

ENV_PREFIX = "PRAXON_"


class Settings(BaseModel):
    """Toàn bộ cấu hình của một lần chạy.

    `extra="forbid"` để một khóa viết sai trong tệp cấu hình bị từ chối ngay
    lúc nạp, thay vì bị bỏ qua im lặng rồi hệ chạy với giá trị mặc định.
    `frozen=True` để không vai nào sửa được cấu hình giữa lần chạy — điều kiện
    tái lập đòi `config_hash` không đổi trong suốt một `run`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    database_url: str


def load_settings(path: Path) -> Settings:
    """Nạp cấu hình từ một tệp TOML, cho biến môi trường ghi đè từng khóa."""
    raw: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
    return Settings.model_validate(_apply_env_overrides(raw))


def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    merged = dict(raw)
    for field in Settings.model_fields:
        value = os.environ.get(ENV_PREFIX + field.upper())
        if value is not None:
            merged[field] = value
    return merged
