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
    bootstrap_draws: int = 1000
    """Số lần rút của bootstrap (task 8.3).

    Mặc định 1000 lần — đủ ổn định cho khoảng tin cậy 95%. Ghi đè trong tệp
    TOML khi cần; bộ điều phối đọc giá trị này, không có số lần rút nào
    hard-code trong hàm bootstrap.
    """

    openai_base_url: str = "http://localhost:8080/v1"
    """URL của backend endpoint tương thích OpenAI (task 6.1).

    Mặc định là llama-server chạy trên máy (backend CPU). Backend endpoint
    dùng URL do Thuận cung cấp, ghi vào tệp TOML của môi trường chạy hoặc
    biến môi trường `PRAXON_OPENAI_BASE_URL` — không commit URL thật vào kho.
    """

    cpu_model_base_url: str = "http://localhost:8080/v1"
    """URL của backend mô hình nhỏ chạy trên CPU (task 6.1).

    Mặc định là llama-server trên máy, phục vụ Qwen3-8B-GGUF. Ghi đè trong
    tệp TOML hoặc biến môi trường `PRAXON_CPU_MODEL_BASE_URL` khi server
    chạy ở cổng khác.
    """

    model_id: str = "Qwen/Qwen3-8B-GGUF"
    """Định danh mô hình đang chạy (task 6.1).

    Backend CPU: kho GGUF trên Hugging Face. Backend endpoint: tên model ở
    endpoint đó, do Thuận cung cấp. `model_id` đi vào `run` và khóa cache
    (spec dòng 189, 191), nên đổi model mà không đổi trường này là mất tái lập.
    """

    model_revision: str = "7c41481f57cb95916b40956ab2f0b139b296d974"
    """Revision của mô hình, ghim bằng commit hash trên Hugging Face (task 6.1).

    Commit HEAD của kho `Qwen/Qwen3-8B-GGUF` lúc làm task 6.1 (kiểm ngày
    7/11/2026; tệp `Qwen3-8B-Q4_K_M.gguf` trong commit này có blob
    `d4ee8ae7f4de3a5046b1a29776a3f011ba28017e`, 5.027.783.488 byte).
    Không ghi `Q4_K_M` — đó là nhãn quantization, không phải revision.
    `model_revision` đi vào `run` và khóa cache (spec dòng 189, 191).
    """

    openai_api_key: str | None = None
    """Khóa API cho backend endpoint tương thích OpenAI (task 6.1).

    Chỉ qua biến môi trường `PRAXON_OPENAI_API_KEY`, không bao giờ ghi vào
    tệp TOML commit lên kho. Backend CPU (llama-server trên máy) không yêu
    cầu xác thực nên dùng khóa giả `"local"` (xem `LOCAL_API_KEY` trong
    `adapters.language_model`); backend endpoint dùng khóa thật do Thuận cấp.
    """

    model_max_retries: int = 3
    """Số lần thử lại sau lần gọi mô hình đầu tiên hỏng (task 6.1, spec dòng 219).

    Mặc định 3 lần thử lại (tổng cộng tối đa 4 lần gọi). Chỉ thử lại lỗi tạm
    thời (mất kết nối, timeout, 429, lỗi 5xx); lỗi vĩnh viễn (sai khóa, sai
    yêu cầu) không thử lại. Ghi đè trong tệp TOML hoặc biến môi trường
    `PRAXON_MODEL_MAX_RETRIES` khi cần.
    """

    model_retry_base_delay_seconds: float = 1.0
    """Độ trễ cơ sở (giây) giữa các lần thử lại gọi mô hình (task 6.1, spec dòng 219).

    Lần thử lại thứ n chờ `model_retry_base_delay_seconds * 2 ** n` giây
    (giãn cách theo cấp số nhân). Mặc định 1,0 giây. Ghi đè trong tệp TOML
    hoặc biến môi trường `PRAXON_MODEL_RETRY_BASE_DELAY_SECONDS` khi cần;
    test hợp đồng truyền 0,0 để không chờ thật.
    """


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
