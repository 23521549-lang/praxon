"""Bộ nhớ đệm phản hồi mô hình (task 6.3).

Khóa đệm gồm băm của prompt, `model_revision`, tham số giải mã và băm JSON
schema đầu ra — mọi thứ ảnh hưởng tới kết quả đều phải nằm trong khóa, nếu
không thì đổi schema mà vẫn đọc nhầm kết quả cũ (spec, mục chạy lại).

Cache là một component thuần quấn quanh một callable chung `call(prompt)`:
nó không định nghĩa giao diện `LanguageModel` (việc của task 6.1), không gọi
mô hình, và không import SDK mô hình nào. Task 6.1 sau đó nối adapter thật
qua nó bằng một lớp mỏng.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any

__all__ = ["ResponseCache", "cache_key"]


def _sha256_text(text: str) -> str:
    """SHA-256 hex của một chuỗi UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_json(value: Mapping[str, Any]) -> str:
    """SHA-256 hex của một giá trị JSON, chuẩn hóa thứ tự khóa trước khi băm."""
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256_text(canonical)


def cache_key(
    prompt: str,
    model_revision: str,
    decode_params: Mapping[str, Any],
    json_schema: Mapping[str, Any],
) -> str:
    """Khóa đệm: SHA-256 của (băm prompt, `model_revision`, tham số giải mã, băm schema).

    Thứ tự khóa trong `decode_params` và `json_schema` không ảnh hưởng tới
    khóa (chuẩn hóa trước khi băm), nhưng đổi bất cứ thành phần nào — kể cả
    chỉ đổi schema — thì khóa đổi, nên không bao giờ đọc nhầm kết quả cũ.
    """
    key_doc = {
        "prompt_sha256": _sha256_text(prompt),
        "model_revision": model_revision,
        "decode_params_sha256": _sha256_json(decode_params),
        "json_schema_sha256": _sha256_json(json_schema),
    }
    return _sha256_text(
        json.dumps(key_doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )


class ResponseCache:
    """Bộ nhớ đệm phản hồi mô hình trong bộ nhớ, khóa theo `cache_key`.

    Một cache có thể phục vụ nhiều `model_revision` khác nhau: khóa phân biệt
    chúng, nên mục của revision này không bao giờ trả cho revision khác.
    Lần gọi lỗi không lưu vào đệm — lần sau gọi lại như chưa từng gọi.
    """

    def __init__(self) -> None:
        """Đệm rỗng."""
        self._entries: dict[str, str] = {}

    def get_or_call(
        self,
        prompt: str,
        *,
        model_revision: str,
        decode_params: Mapping[str, Any],
        json_schema: Mapping[str, Any],
        call: Callable[[str], str],
    ) -> str:
        """Trả phản hồi từ đệm nếu khóa đã có; nếu không thì gọi `call(prompt)`, lưu rồi trả."""
        key = cache_key(prompt, model_revision, decode_params, json_schema)
        if key in self._entries:
            return self._entries[key]
        response = call(prompt)
        self._entries[key] = response
        return response

    def __len__(self) -> int:
        """Số mục đang lưu trong đệm."""
        return len(self._entries)

    def clear(self) -> None:
        """Xóa toàn bộ mục trong đệm."""
        self._entries.clear()
