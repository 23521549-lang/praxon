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
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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

    reflector_batch_size: int = 10
    """Số trajectory mỗi lô Reflector (task 6.4, BĐ4 spec dòng 89).

    Reflector gọi mô hình một lần mỗi lô (spec dòng 76). Mặc định 10
    trajectory mỗi lô — đủ nhỏ để prompt gọn (log tổng hợp có 8 hoạt
    động mỗi trace), đủ lớn để một vòng học không gọi mô hình quá nhiều
    lần. Ghi đè trong tệp TOML hoặc biến môi trường
    `PRAXON_REFLECTOR_BATCH_SIZE` khi cần.
    """

    reflector_max_insights_per_batch: int = 20
    """Số insight tối đa mỗi lô Reflector (task 6.4, BĐ4 spec dòng 89).

    Vượt trần thì Reflector cắt ở trần, không tràn (task 6.4). Mặc định
    20 — cùng bậc với số luật miner khám phá trên một log đô thị. Trần
    tính theo từng lô, không phải toàn bộ vòng học. Ghi đè trong tệp TOML
    hoặc biến môi trường `PRAXON_REFLECTOR_MAX_INSIGHTS_PER_BATCH` khi cần.
    """

    checkpoint_every_n_cases: int = 100
    """Số case mỗi lô checkpoint (task 10.3, spec dòng 215).

    Cứ mỗi N case đã xử lý, vòng học ghi một điểm kiểm tra (fact, candidate
    đang chờ, con trỏ case, bộ nhớ đệm) vào store đã chọn. Mặc định 100
    case — đủ thưa để chi phí ghi checkpoint không đáng kể so với gọi mô
    hình, đủ dày để khi đứt chỉ chạy lại tối đa 99 case. Ghi đè trong tệp
    TOML hoặc biến môi trường `PRAXON_CHECKPOINT_EVERY_N_CASES` khi cần.
    """

    checkpoint_store: Literal["local", "s3"] = "local"
    """Backend lưu checkpoint (task 10.3, spec dòng 215).

    `"local"` ghi file JSON trên máy chạy (mặc định cho dev/test);
    `"s3"` đẩy sang object storage S3-compatible (Backblaze B2 — Thuận
    chọn ngày 7/11/2026 thay R2 trong spec). `"s3"` chỉ chạy được khi đã
    cấu hình đủ `s3_endpoint_url` + `s3_bucket` + khóa. Ghi đè trong tệp
    TOML hoặc biến môi trường `PRAXON_CHECKPOINT_STORE` khi cần.
    """

    s3_endpoint_url: str | None = None
    """URL endpoint S3-compatible cho checkpoint (task 10.3).

    Backblaze B2: `https://s3.<region>.backblazeb2.com` (lấy từ trang chi
    tiết bucket). `None` thì dùng endpoint AWS mặc định — chỉ dùng trong
    test với mock S3; B2 thật bắt buộc phải có endpoint này. Ghi đè trong
    tệp TOML hoặc biến môi trường `PRAXON_S3_ENDPOINT_URL` khi cần.
    """

    s3_bucket: str | None = None
    """Tên bucket lưu checkpoint (task 10.3).

    Bucket do Thuận tạo trong console B2 (vd `praxon-checkpoints`); store
    không tự tạo bucket. Ghi đè trong tệp TOML hoặc biến môi trường
    `PRAXON_S3_BUCKET` khi cần.
    """

    s3_access_key_id: str | None = None
    """Key ID truy cập S3 cho checkpoint (task 10.3).

    Backblaze B2: keyID của application key (KHÔNG dùng master key).
    Chỉ qua biến môi trường `PRAXON_S3_ACCESS_KEY_ID`, không bao giờ ghi
    vào tệp TOML commit lên kho — giống `openai_api_key` (task 6.1).
    """

    s3_secret_access_key: str | None = None
    """Khóa bí mật truy cập S3 cho checkpoint (task 10.3).

    Backblaze B2: applicationKey của application key (chỉ hiện một lần
    lúc tạo key). Chỉ qua biến môi trường `PRAXON_S3_SECRET_ACCESS_KEY`,
    không bao giờ ghi vào tệp TOML commit lên kho — giống `openai_api_key`
    (task 6.1). Xoay khóa không đổi `config_hash` (xem
    `coordinator.compute_config_hash`).
    """

    token_budget_total: int = Field(default=0, ge=0)
    """Trần token của một vòng học (task 10.4, spec dòng 217).

    Đếm tổng `tokens_in + tokens_out` của cả vòng; `0` nghĩa là không đặt
    trần (giữ đúng hành vi hiện tại). Trần là số cấu hình duy nhất của
    vòng — không có trần riêng cho vào/ra. Đổi trần thì đổi `config_hash`
    (trần đổi kết quả chạy nên phải đổi hash — xem
    `coordinator.compute_config_hash`). Ghi đè trong tệp TOML hoặc biến
    môi trường `PRAXON_TOKEN_BUDGET_TOTAL` khi cần.
    """

    token_budget_reserve_per_call: int = Field(default=2048, ge=0)
    """Dự trữ token cho một lần gọi mô hình (task 10.4, spec dòng 217).

    Trước mỗi lô Reflector, bộ điều phối dự trữ số lần gọi tối đa của lô
    nhân với số này; tổng đã dùng cộng dự trữ mà vượt trần thì dừng trước
    khi gọi. Mặc định 2048 = `ctx-size` của server triển khai (lệnh chạy
    9.1) — chặn trên của một lần gọi thành công (prompt + đầu ra không
    vượt cửa sổ context). Nếu server đổi `ctx-size` thì dự trữ phải đổi
    theo. Ghi đè trong tệp TOML hoặc biến môi trường
    `PRAXON_TOKEN_BUDGET_RESERVE_PER_CALL` khi cần.
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
