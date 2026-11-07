"""Test hợp đồng của adapter LanguageModel (task 6.1).

Cả hai backend (mô hình nhỏ trên CPU, endpoint tương thích OpenAI) qua cùng
bộ test này với cùng một adapter — đó là cổng ra của plan 6.1. Không gọi
model thật: server giả tương thích OpenAI (httpx2.MockTransport) trả phản hồi
ghi sẵn từ `tests/fixtures/contract_prompts.json` (spec dòng 213).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx2
import jsonschema
import openai
import pytest

from praxon_core.adapters.language_model import (
    LOCAL_API_KEY,
    LanguageModel,
    ModelCallError,
    OpenAICompatibleModel,
    model_from_settings,
)
from praxon_core.settings import Settings
from tests.paths import REPO_ROOT

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "contract_prompts.json"
CPU_BASE_URL = "http://localhost:8080/v1"
ENDPOINT_BASE_URL = "https://api.example.com/v1"
MODEL_ID = "Qwen/Qwen3-8B-GGUF"


def _cases() -> dict[str, dict[str, Any]]:
    """Nạp bộ câu hỏi test hợp đồng, trả dict theo id."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {case["id"]: case for case in data["cases"]}


class _FakeServer:
    """Server giả tương thích OpenAI: trả phản hồi ghi sẵn, ghi lại yêu cầu.

    Trả lỗi theo cấu hình: `fail_times` lần đầu trả 500 rồi mới thành công;
    `fail_always` luôn trả 500; `fail_status` đổi mã lỗi (401 = lỗi vĩnh viễn,
    không thử lại). `payload` (tùy chọn) thay hẳn thân phản hồi 200 — dùng
    cho ca phản hồi sai dạng.
    """

    def __init__(
        self,
        canned_text: str,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        fail_times: int = 0,
        fail_always: bool = False,
        fail_status: int = 200,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._canned_text = canned_text
        self._prompt_tokens = prompt_tokens
        self._completion_tokens = completion_tokens
        self._failures_left = fail_times
        self._fail_always = fail_always
        self._fail_status = fail_status
        self._payload = payload
        self.calls: list[httpx2.Request] = []

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        """Trả lỗi hoặc phản hồi ghi sẵn cho một yêu cầu."""
        self.calls.append(request)
        if self._fail_always or self._failures_left > 0:
            self._failures_left = max(0, self._failures_left - 1)
            return self._error(500, "lỗi server giả")
        if self._fail_status != 200:
            return self._error(self._fail_status, "lỗi server giả")
        return httpx2.Response(200, json=self._ok_payload())

    def _ok_payload(self) -> dict[str, Any]:
        """Thân phản hồi chat completion đúng dạng OpenAI."""
        if self._payload is not None:
            return self._payload
        payload: dict[str, Any] = {
            "id": "chatcmpl-gia",
            "object": "chat.completion",
            "created": 1700000000,
            "model": MODEL_ID,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": self._canned_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": self._prompt_tokens,
                "completion_tokens": self._completion_tokens,
                "total_tokens": self._prompt_tokens + self._completion_tokens,
            },
        }
        return payload

    @staticmethod
    def _error(status: int, message: str) -> httpx2.Response:
        """Thân lỗi đúng dạng OpenAI để SDK đổi thành đúng lớp ngoại lệ."""
        return httpx2.Response(
            status,
            json={"error": {"message": message, "type": "server_error", "code": None}},
        )


def _client(server: _FakeServer, *, base_url: str) -> openai.OpenAI:
    """Client OpenAI trỏ về server giả; tắt vòng thử lại của SDK."""
    return openai.OpenAI(
        base_url=base_url,
        api_key=LOCAL_API_KEY,
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(server.handler)),
    )


def _model_for_case(
    case: Mapping[str, Any], *, base_url: str = CPU_BASE_URL, max_retries: int = 2
) -> tuple[OpenAICompatibleModel, _FakeServer]:
    """Dựng adapter + server giả từ một ca trong fixture."""
    server = _FakeServer(
        str(case["canned_text"]),
        prompt_tokens=int(case["canned_prompt_tokens"]),
        completion_tokens=int(case["canned_completion_tokens"]),
        fail_times=int(case.get("fail_times", 0)),
        fail_always=bool(case.get("fail_always", False)),
    )
    model = OpenAICompatibleModel(
        _client(server, base_url=base_url),
        model=MODEL_ID,
        max_retries=max_retries,
        retry_base_delay_seconds=0.0,
    )
    return model, server


def _body(request: httpx2.Request) -> dict[str, Any]:
    """Thân JSON của một yêu cầu đã ghi lại."""
    parsed: dict[str, Any] = json.loads(request.content.decode("utf-8"))
    return parsed


def test_plain_completion_tra_text_va_token():
    model, server = _model_for_case(_cases()["plain"])
    case = _cases()["plain"]
    result = model.complete(
        str(case["prompt"]),
        temperature=float(case["temperature"]),
        seed=int(case["seed"]),
    )
    assert result.text == case["canned_text"]
    assert result.prompt_tokens == case["canned_prompt_tokens"]
    assert result.completion_tokens == case["canned_completion_tokens"]
    assert len(server.calls) == 1
    body = _body(server.calls[0])
    assert server.calls[0].url.path == "/v1/chat/completions"
    assert body["model"] == MODEL_ID
    assert body["messages"] == [{"role": "user", "content": case["prompt"]}]
    assert body["temperature"] == 0.0
    assert body["seed"] == 7
    assert "response_format" not in body


def test_schema_completion_gui_response_format_va_khop_schema():
    model, server = _model_for_case(_cases()["schema"])
    case = _cases()["schema"]
    schema = dict(case["json_schema"])
    result = model.complete(
        str(case["prompt"]),
        json_schema=schema,
        temperature=float(case["temperature"]),
        seed=int(case["seed"]),
    )
    assert result.text == case["canned_text"]
    assert len(server.calls) == 1
    body = _body(server.calls[0])
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "response", "schema": schema},
    }
    jsonschema.validate(instance=json.loads(result.text), schema=schema)


def test_schema_khong_khop_bi_tu_choi():
    # Server trả JSON sai kiểu so với schema: adapter kiểm lại ở phía host
    # và báo hỏng, không trả chữ rác cho bên gọi.
    case = _cases()["schema"]
    schema = dict(case["json_schema"])
    server = _FakeServer('{"rule": 123}', prompt_tokens=1, completion_tokens=1)
    model = OpenAICompatibleModel(
        _client(server, base_url=CPU_BASE_URL),
        model=MODEL_ID,
        max_retries=2,
        retry_base_delay_seconds=0.0,
    )
    with pytest.raises(ModelCallError):
        model.complete(str(case["prompt"]), json_schema=schema)
    assert len(server.calls) == 1


def test_text_khong_phai_json_bi_tu_choi():
    case = _cases()["schema"]
    schema = dict(case["json_schema"])
    server = _FakeServer("đây không phải JSON", prompt_tokens=1, completion_tokens=1)
    model = OpenAICompatibleModel(
        _client(server, base_url=CPU_BASE_URL),
        model=MODEL_ID,
        max_retries=2,
        retry_base_delay_seconds=0.0,
    )
    with pytest.raises(ModelCallError):
        model.complete(str(case["prompt"]), json_schema=schema)
    assert len(server.calls) == 1


def test_loi_tam_thoi_duoc_thu_lai_roi_thanh_cong():
    model, server = _model_for_case(_cases()["retry_then_ok"])
    case = _cases()["retry_then_ok"]
    result = model.complete(str(case["prompt"]), seed=int(case["seed"]))
    assert result.text == case["canned_text"]
    assert len(server.calls) == 3


def test_het_luot_thu_lai_bao_hong():
    model, server = _model_for_case(_cases()["always_fails"])
    case = _cases()["always_fails"]
    with pytest.raises(ModelCallError):
        model.complete(str(case["prompt"]), seed=int(case["seed"]))
    assert len(server.calls) == 3


def test_loi_vinh_vien_khong_thu_lai():
    # 401 là lỗi vĩnh viễn: báo hỏng ngay sau đúng một lần gọi.
    case = _cases()["plain"]
    server = _FakeServer(
        str(case["canned_text"]),
        prompt_tokens=1,
        completion_tokens=1,
        fail_status=401,
    )
    model = OpenAICompatibleModel(
        _client(server, base_url=CPU_BASE_URL),
        model=MODEL_ID,
        max_retries=2,
        retry_base_delay_seconds=0.0,
    )
    with pytest.raises(ModelCallError):
        model.complete(str(case["prompt"]))
    assert len(server.calls) == 1


def test_xac_dinh_cung_prompt_seed_tra_cung_phuc_hoi():
    model, server = _model_for_case(_cases()["determinism"])
    case = _cases()["determinism"]
    first = model.complete(str(case["prompt"]), seed=int(case["seed"]))
    second = model.complete(str(case["prompt"]), seed=int(case["seed"]))
    assert first.text == second.text == case["canned_text"]
    assert len(server.calls) == 2
    assert _body(server.calls[0])["seed"] == 42
    assert _body(server.calls[1])["seed"] == 42


def test_hai_backend_dung_chung_bo_test():
    # Cổng ra của plan 6.1: cùng một adapter + cùng bộ test hợp đồng xanh
    # cho cả hai backend, chỉ khác base_url.
    case = _cases()["plain"]
    cpu_model, cpu_server = _model_for_case(case, base_url=CPU_BASE_URL)
    endpoint_model, endpoint_server = _model_for_case(case, base_url=ENDPOINT_BASE_URL)
    cpu_result = cpu_model.complete(str(case["prompt"]), seed=int(case["seed"]))
    endpoint_result = endpoint_model.complete(str(case["prompt"]), seed=int(case["seed"]))
    assert cpu_result.text == endpoint_result.text == case["canned_text"]
    assert cpu_server.calls[0].url.host == "localhost"
    assert endpoint_server.calls[0].url.host == "api.example.com"


def test_giao_dien_language_model():
    # Adapter cài đặt giao diện LanguageModel: bên gọi chỉ cần giao diện.
    model, _server = _model_for_case(_cases()["plain"])
    language_model: LanguageModel = model
    result = language_model.complete("xin chào")
    assert result.text == _cases()["plain"]["canned_text"]


def test_factory_cpu_dung_khoa_gia():
    # Factory nối đúng backend CPU: khóa giả "local", host localhost,
    # model từ Settings — kiểm đầu-cuối qua server giả.
    case = _cases()["plain"]
    server = _FakeServer(
        str(case["canned_text"]),
        prompt_tokens=int(case["canned_prompt_tokens"]),
        completion_tokens=int(case["canned_completion_tokens"]),
    )
    settings = Settings(database_url="postgresql://localhost/praxon")
    model = model_from_settings(
        settings,
        backend="cpu",
        http_client=httpx2.Client(transport=httpx2.MockTransport(server.handler)),
    )
    result = model.complete(str(case["prompt"]))
    assert result.text == case["canned_text"]
    assert model.model == MODEL_ID
    request = server.calls[0]
    assert request.url.host == "localhost"
    assert request.headers["authorization"] == "Bearer " + LOCAL_API_KEY


def test_factory_endpoint_can_khoa():
    settings = Settings(database_url="postgresql://localhost/praxon")
    with pytest.raises(ValueError):
        model_from_settings(settings, backend="endpoint")
    case = _cases()["plain"]
    server = _FakeServer(
        str(case["canned_text"]),
        prompt_tokens=int(case["canned_prompt_tokens"]),
        completion_tokens=int(case["canned_completion_tokens"]),
    )
    keyed = Settings(
        database_url="x",
        openai_base_url=ENDPOINT_BASE_URL,
        openai_api_key="khoa-that",
    )
    model = model_from_settings(
        keyed,
        backend="endpoint",
        http_client=httpx2.Client(transport=httpx2.MockTransport(server.handler)),
    )
    result = model.complete(str(case["prompt"]))
    assert result.text == case["canned_text"]
    assert model.model == MODEL_ID
    request = server.calls[0]
    assert request.url.host == "api.example.com"
    assert request.headers["authorization"] == "Bearer khoa-that"


def test_factory_tat_vong_thu_lai_cua_sdk():
    # SDK có vòng thử lại riêng (mặc định 2 lần); factory phải tắt nó để
    # vòng thử lại của adapter là vòng duy nhất — chứng minh: adapter đặt
    # max_retries=0, server luôn lỗi, fake chỉ thấy đúng một lần gọi.
    server = _FakeServer("x", fail_always=True)
    settings = Settings(database_url="x", model_max_retries=0)
    model = model_from_settings(
        settings,
        backend="cpu",
        http_client=httpx2.Client(transport=httpx2.MockTransport(server.handler)),
    )
    with pytest.raises(ModelCallError):
        model.complete("xin chào")
    assert len(server.calls) == 1


def test_factory_truyen_timeout_tu_settings():
    # Factory phải truyền timeout từ Settings vào client SDK — mặc định
    # 1800 giây (task 9.1: tường mặc định 600 giây giết đoạn Wabo dài
    # sinh ~690 giây). Chứng minh bằng timeout của client đã dựng;
    # giá trị khác trong Settings phải chảy tới đúng client đó.
    settings = Settings(database_url="<redacted>")
    model = model_from_settings(settings, backend="cpu")
    assert model._client.timeout == 1800.0
    settings = Settings(database_url="<redacted>", model_timeout_seconds=42.0)
    model = model_from_settings(settings, backend="cpu")
    assert model._client.timeout == 42.0


def test_phan_hoi_rong_bi_tu_choi():
    # Server trả 200 nhưng không có lựa chọn nào: sai hợp đồng, báo hỏng.
    server = _FakeServer(
        "",
        payload={
            "id": "chatcmpl-gia",
            "object": "chat.completion",
            "created": 1700000000,
            "model": MODEL_ID,
            "choices": [],
        },
    )
    model = OpenAICompatibleModel(
        _client(server, base_url=CPU_BASE_URL),
        model=MODEL_ID,
        max_retries=0,
        retry_base_delay_seconds=0.0,
    )
    with pytest.raises(ModelCallError):
        model.complete("xin chào")


def test_usage_thieu_tra_none():
    # Server không trả usage: số token là None, không đoán số.
    server = _FakeServer(
        "xin chào",
        payload={
            "id": "chatcmpl-gia",
            "object": "chat.completion",
            "created": 1700000000,
            "model": MODEL_ID,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "xin chào"},
                    "finish_reason": "stop",
                }
            ],
        },
    )
    model = OpenAICompatibleModel(
        _client(server, base_url=CPU_BASE_URL),
        model=MODEL_ID,
        max_retries=0,
        retry_base_delay_seconds=0.0,
    )
    result = model.complete("xin chào")
    assert result.text == "xin chào"
    assert result.prompt_tokens is None
    assert result.completion_tokens is None
