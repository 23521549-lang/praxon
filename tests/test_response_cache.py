"""Bộ nhớ đệm phản hồi (task 6.3): khóa gồm prompt, revision, params, schema."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from praxon_core.adapters.cache import ResponseCache, cache_key

PARAMS = {"temperature": 0.0, "max_tokens": 10}
SCHEMA = {"type": "object", "properties": {"rule": {"type": "string"}}}
REVISION = "model-1.0"


class FakeModel:
    """Mô hình giả: đếm số lần gọi, trả phản hồi khác nhau mỗi lần gọi."""

    def __init__(self) -> None:
        """Chưa gọi lần nào."""
        self.calls: int = 0
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        """Đếm một lần gọi rồi trả phản hồi khác nhau mỗi lần gọi."""
        self.calls += 1
        self.prompts.append(prompt)
        return f"response-{self.calls}"


def _call(
    cache: ResponseCache,
    model: FakeModel,
    prompt: str = "prompt",
    revision: str = REVISION,
    params: Mapping[str, Any] = PARAMS,
    schema: Mapping[str, Any] = SCHEMA,
) -> str:
    """Gọi đệm với các giá trị mặc định của task 6.3."""
    return cache.get_or_call(
        prompt,
        model_revision=revision,
        decode_params=params,
        json_schema=schema,
        call=model,
    )


def test_same_input_calls_model_once():
    cache = ResponseCache()
    model = FakeModel()
    first = _call(cache, model)
    second = _call(cache, model)
    assert model.calls == 1
    assert first == second == "response-1"


def test_schema_change_calls_model_again():
    cache = ResponseCache()
    model = FakeModel()
    first = _call(cache, model)
    other_schema = {"type": "object", "properties": {"other": {"type": "string"}}}
    second = _call(cache, model, schema=other_schema)
    assert model.calls == 2
    assert first == "response-1"
    assert second == "response-2"


def test_prompt_change_calls_model_again():
    cache = ResponseCache()
    model = FakeModel()
    _call(cache, model, prompt="prompt-a")
    _call(cache, model, prompt="prompt-b")
    assert model.calls == 2


def test_revision_change_calls_model_again():
    cache = ResponseCache()
    model = FakeModel()
    _call(cache, model, revision="model-1.0")
    _call(cache, model, revision="model-2.0")
    assert model.calls == 2


def test_params_change_calls_model_again():
    cache = ResponseCache()
    model = FakeModel()
    _call(cache, model, params={"temperature": 0.0, "max_tokens": 10})
    _call(cache, model, params={"temperature": 0.7, "max_tokens": 10})
    assert model.calls == 2


def test_params_key_order_does_not_matter():
    cache = ResponseCache()
    model = FakeModel()
    _call(cache, model, params={"temperature": 0.0, "max_tokens": 10})
    _call(cache, model, params={"max_tokens": 10, "temperature": 0.0})
    assert model.calls == 1


def test_schema_key_order_does_not_matter():
    cache = ResponseCache()
    model = FakeModel()
    _call(cache, model, schema={"type": "object", "properties": {"a": {"type": "string"}}})
    _call(cache, model, schema={"properties": {"a": {"type": "string"}}, "type": "object"})
    assert model.calls == 1


def test_cache_key_deterministic_and_sensitive():
    base = cache_key("prompt", REVISION, PARAMS, SCHEMA)
    assert cache_key("prompt", REVISION, PARAMS, SCHEMA) == base
    assert cache_key("other", REVISION, PARAMS, SCHEMA) != base
    assert cache_key("prompt", "model-2.0", PARAMS, SCHEMA) != base
    assert cache_key("prompt", REVISION, {"temperature": 0.7}, SCHEMA) != base
    assert cache_key("prompt", REVISION, PARAMS, {"type": "string"}) != base


def test_caches_are_independent():
    first_cache = ResponseCache()
    second_cache = ResponseCache()
    model = FakeModel()
    _call(first_cache, model)
    _call(second_cache, model)
    assert model.calls == 2
    assert len(first_cache) == 1
    assert len(second_cache) == 1


def test_failed_call_is_not_cached():
    cache = ResponseCache()
    attempts = {"count": 0}

    def flaky(prompt: str) -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("model down")
        return "ok"

    with pytest.raises(RuntimeError, match="model down"):
        cache.get_or_call(
            "prompt",
            model_revision=REVISION,
            decode_params=PARAMS,
            json_schema=SCHEMA,
            call=flaky,
        )
    assert len(cache) == 0
    assert (
        cache.get_or_call(
            "prompt",
            model_revision=REVISION,
            decode_params=PARAMS,
            json_schema=SCHEMA,
            call=flaky,
        )
        == "ok"
    )
    assert attempts["count"] == 2
    assert len(cache) == 1


def test_len_and_clear():
    cache = ResponseCache()
    model = FakeModel()
    assert len(cache) == 0
    _call(cache, model, prompt="a")
    _call(cache, model, prompt="b")
    assert len(cache) == 2
    cache.clear()
    assert len(cache) == 0
    _call(cache, model, prompt="a")
    assert model.calls == 3


def test_non_serializable_params_raise():
    cache = ResponseCache()
    model = FakeModel()
    with pytest.raises(TypeError):
        _call(cache, model, params={"temperature": {0.0}})
    assert model.calls == 0
