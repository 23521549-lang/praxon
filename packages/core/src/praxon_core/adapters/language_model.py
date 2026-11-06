"""Giao diện `LanguageModel` + một adapter tương thích OpenAI (task 6.1).

Spec (dòng 200, 223): mọi lệnh gọi mô hình đi qua một adapter duy nhất với
giao diện `LanguageModel`; hai backend — mô hình nhỏ trên CPU (llama-server,
Qwen3-8B-GGUF) và endpoint tương thích OpenAI — cùng cài đặt giao diện này và
qua cùng bộ test hợp đồng. SDK `openai` chỉ được import trong thư mục này
(hợp đồng import-linter `sdk-mo-hinh-chi-trong-adapters`).

Thử lại (spec dòng 219): gọi mô hình hỏng thì thử lại có giãn cách; hết lượt
thì báo hỏng bằng `ModelCallError` — bên gọi đánh dấu cả lô thất bại trong
`run` rồi dừng, không nuốt lỗi. Chỉ lỗi tạm thời (mất kết nối, timeout, 429,
lỗi 5xx) mới được thử lại; lỗi vĩnh viễn (sai khóa, sai yêu cầu) báo hỏng ngay.
Vòng thử lại của adapter là vòng duy nhất: client SDK được dựng với
`max_retries=0` để hai vòng không nhân nhau.

JSON schema (rủi ro #3 của đề xuất 6.1): khi `complete` nhận `json_schema`,
adapter gửi `response_format` cho server (llama-server chuyển schema thành
GBNF và ép giải mã) VÀ kiểm lại object đã parse ở phía host bằng `jsonschema`
— vì llama-server bỏ qua lặng lẽ tính năng schema nó không hỗ trợ. Phản hồi
không parse được JSON hoặc không khớp schema thì báo hỏng, không trả chữ rác.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx2
import jsonschema
import openai

from praxon_core.settings import Settings

__all__ = [
    "CompletionResult",
    "LanguageModel",
    "ModelCallError",
    "OpenAICompatibleModel",
    "model_from_settings",
]

# Khóa giả cho backend CPU: llama-server trên máy không yêu cầu xác thực.
# Đây không phải credential — chỉ là chuỗi giữ chỗ để SDK chấp nhận gọi.
LOCAL_API_KEY = "local"

# Tên cố định cho `response_format` kiểu JSON schema (OpenAI yêu cầu có tên).
JSON_SCHEMA_RESPONSE_NAME = "response"

# Lỗi tạm thời: được thử lại có giãn cách. Mọi lỗi API khác (sai khóa, sai yêu
# cầu, không tìm thấy model) là vĩnh viễn — báo hỏng ngay, không thử lại.
_RETRYABLE_ERRORS: tuple[type[openai.APIError], ...] = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.InternalServerError,
)


@dataclass(frozen=True)
class CompletionResult:
    """Kết quả một lần gọi mô hình.

    `text` là nội dung phản hồi (chuỗi gốc, không chuẩn hóa lại). Hai số token
    là `None` khi server không trả `usage` (llama-server thường trả, nhưng
    không bắt buộc).
    """

    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ModelCallError(RuntimeError):
    """Gọi mô hình hỏng sau khi đã thử lại hết lượt, hoặc phản hồi sai hợp đồng.

    Bên gọi bắt lỗi này để đánh dấu cả lô thất bại trong `run` rồi dừng
    (spec dòng 219) — không nuốt lỗi, không trả phản hồi giả.
    """


class LanguageModel(Protocol):
    """Giao diện duy nhất mọi lệnh gọi mô hình phải đi qua (spec dòng 200, 223).

    Hai backend (mô hình nhỏ trên CPU, endpoint tương thích OpenAI) cùng cài
    đặt giao diện này và qua cùng bộ test hợp đồng của adapter.
    """

    def complete(
        self,
        prompt: str,
        *,
        json_schema: Mapping[str, Any] | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        """Hoàn thành một prompt, trả text + số token đếm được.

        `json_schema` (tùy chọn) ép đầu ra theo JSON schema: adapter gửi
        `response_format` cho server và kiểm lại object đã parse ở phía host.
        `temperature=0` + `seed` cố định để xác định (spec dòng 191).
        """


class OpenAICompatibleModel:
    """Một adapter tương thích OpenAI, phục vụ cả hai backend của task 6.1.

    Nhận một client `openai.OpenAI` đã dựng sẵn (bên gọi chịu trách nhiệm
    dựng client với `base_url`/`api_key` đúng backend — xem
    `model_from_settings`). Client SDK phải có `max_retries=0`: vòng thử lại
    của adapter là vòng duy nhất, để số lần gọi thật đúng
    `max_retries + 1` và test đếm được.
    """

    def __init__(
        self,
        client: openai.OpenAI,
        *,
        model: str,
        max_retries: int,
        retry_base_delay_seconds: float,
    ) -> None:
        """Giữ client và tham số; không gọi mạng lúc dựng."""
        self._client = client
        self._model = model
        self._max_retries = max_retries
        self._retry_base_delay_seconds = retry_base_delay_seconds

    @property
    def model(self) -> str:
        """Tên model mà adapter gọi (đi vào thân yêu cầu và khóa cache)."""
        return self._model

    def complete(
        self,
        prompt: str,
        *,
        json_schema: Mapping[str, Any] | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
        max_tokens: int | None = None,
    ) -> CompletionResult:
        """Hoàn thành một prompt, thử lại lỗi tạm thời có giãn cách."""
        response = self._create_with_retries(
            prompt,
            json_schema=json_schema,
            temperature=temperature,
            seed=seed,
            max_tokens=max_tokens,
        )
        text = self._text_of(response)
        if json_schema is not None:
            self._validate_against_schema(text, json_schema)
        usage = response.usage
        return CompletionResult(
            text=text,
            prompt_tokens=usage.prompt_tokens if usage is not None else None,
            completion_tokens=usage.completion_tokens if usage is not None else None,
        )

    def _create_with_retries(
        self,
        prompt: str,
        *,
        json_schema: Mapping[str, Any] | None,
        temperature: float,
        seed: int | None,
        max_tokens: int | None,
    ) -> openai.types.chat.ChatCompletion:
        """Gọi chat completions, thử lại lỗi tạm thời rồi mới báo hỏng."""
        request = self._request_body(
            prompt,
            json_schema=json_schema,
            temperature=temperature,
            seed=seed,
            max_tokens=max_tokens,
        )
        attempts = 0
        while True:
            try:
                response: openai.types.chat.ChatCompletion = (
                    self._client.chat.completions.create(**request)
                )
                return response
            except _RETRYABLE_ERRORS as exc:
                attempts += 1
                if attempts > self._max_retries:
                    raise ModelCallError(
                        f"gọi mô hình hỏng sau {attempts} lần thử: {exc}"
                    ) from exc
                time.sleep(self._retry_base_delay_seconds * (2 ** (attempts - 1)))
            except openai.APIError as exc:
                raise ModelCallError(f"gọi mô hình hỏng (không thử lại): {exc}") from exc

    def _request_body(
        self,
        prompt: str,
        *,
        json_schema: Mapping[str, Any] | None,
        temperature: float,
        seed: int | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        """Thân yêu cầu chat completions; chỉ đưa tham số nào được đặt."""
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if seed is not None:
            body["seed"] = seed
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if json_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": JSON_SCHEMA_RESPONSE_NAME,
                    "schema": dict(json_schema),
                },
            }
        return body

    @staticmethod
    def _text_of(response: openai.types.chat.ChatCompletion) -> str:
        """Lấy text của lựa chọn đầu tiên; phản hồi rỗng là sai hợp đồng."""
        if not response.choices:
            raise ModelCallError("phản hồi mô hình không có lựa chọn nào")
        content = response.choices[0].message.content
        if content is None:
            raise ModelCallError("phản hồi mô hình không có nội dung text")
        return content

    @staticmethod
    def _validate_against_schema(text: str, json_schema: Mapping[str, Any]) -> None:
        """Kiểm lại phản hồi ở phía host: phải parse được JSON và khớp schema."""
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ModelCallError(f"phản hồi không parse được JSON: {exc}") from exc
        try:
            jsonschema.validate(instance=parsed, schema=dict(json_schema))
        except jsonschema.ValidationError as exc:
            raise ModelCallError(f"phản hồi không khớp JSON schema: {exc.message}") from exc


def model_from_settings(
    settings: Settings,
    *,
    backend: Literal["cpu", "endpoint"],
    http_client: httpx2.Client | None = None,
) -> OpenAICompatibleModel:
    """Dựng adapter từ Settings, theo backend đã chọn (task 6.1).

    Backend `"cpu"`: llama-server trên máy (`cpu_model_base_url`,
    `model_id`), khóa giả `"local"` vì server không yêu cầu xác thực.
    Backend `"endpoint"`: URL + model + khóa thật từ Settings
    (`openai_base_url`, `model_id`, `openai_api_key` qua biến môi trường
    `PRAXON_OPENAI_API_KEY`); thiếu khóa thì báo lỗi ngay, không gọi.
    `http_client` (tùy chọn) chèn transport HTTP — dùng cho test hợp đồng
    (server giả) và cho proxy; lúc chạy thật để `None` để SDK tự dựng.
    """
    if backend == "cpu":
        base_url = settings.cpu_model_base_url
        api_key: str | None = LOCAL_API_KEY
    else:
        base_url = settings.openai_base_url
        api_key = settings.openai_api_key
        if api_key is None:
            raise ValueError(
                "backend endpoint cần khóa API: đặt biến môi trường PRAXON_OPENAI_API_KEY"
            )
    client = openai.OpenAI(
        base_url=base_url, api_key=api_key, max_retries=0, http_client=http_client
    )
    return OpenAICompatibleModel(
        client,
        model=settings.model_id,
        max_retries=settings.model_max_retries,
        retry_base_delay_seconds=settings.model_retry_base_delay_seconds,
    )
