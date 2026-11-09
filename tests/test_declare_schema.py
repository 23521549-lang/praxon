"""Test JSON schema Declare cho đầu ra Reflector (task 6.2).

Cổng ra (plan 6.2): đầu ra luôn đúng lược đồ; mô hình không thể sinh luật
thời hạn (spec dòng 88, 176; ADR 0004 Q1a — schema chỉ cho tầng 1
`response`/`precedence`). Không gọi mô hình thật: server giả tương thích
OpenAI (httpx2.MockTransport) như test hợp đồng 6.1.
"""

from __future__ import annotations

import json
from typing import Any

import httpx2
import jsonschema
import openai
import pytest

from praxon_core.adapters.language_model import ModelCallError, OpenAICompatibleModel
from praxon_core.learning.declare_schema import (
    DECLARE_OUTPUT_SCHEMA,
    Condition,
    DeclareRule,
    ReflectorOutputError,
    parse_reflector_output,
    validate_reflector_output,
)

TIER_2 = ["succession", "init", "end", "not_response", "not_precedence"]
TEMPORAL_FIELDS = ["deadline", "within", "duration", "time_limit", "weeks", "unit"]
TEMPORAL_OPERATORS = ["<", ">", "<=", ">="]
CPU_BASE_URL = "http://localhost:8080/v1"
MODEL_ID = "Qwen/Qwen3-8B-GGUF"


def _rule(
    template: str = "response",
    activation: str = "A",
    target: str = "B",
    condition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Một luật dạng dict, để sửa từng trường khi test ca sai."""
    rule: dict[str, Any] = {
        "template": template,
        "activation": activation,
        "target": target,
        "source": "De aanvraag wordt ingediend.",
    }
    if condition is not None:
        rule["condition"] = condition
    return rule


def test_dau_ra_hop_le_parse_thanh_luat():
    rules = parse_reflector_output(
        json.dumps(
            {
                "rules": [
                    _rule(),
                    _rule(
                        template="precedence",
                        condition={"attribute": "case_type", "operator": "=", "value": "X"},
                    ),
                ]
            }
        )
    )
    assert rules == [
        DeclareRule(
            template="response",
            activation="A",
            target="B",
            source="De aanvraag wordt ingediend.",
        ),
        DeclareRule(
            template="precedence",
            activation="A",
            target="B",
            source="De aanvraag wordt ingediend.",
            condition=Condition(attribute="case_type", operator="=", value="X"),
        ),
    ]
    assert rules[0].canonical_key == "response(A, B)"
    assert rules[1].canonical_key == "precedence(A, B, case_type = X)"


def test_dau_ra_rong_hop_le():
    assert parse_reflector_output(json.dumps({"rules": []})) == []


def test_condition_render_dang_chuoi():
    assert Condition(attribute="case_type", operator="=", value="X").render() == "case_type = X"
    assert (
        Condition(attribute="case_type", operator="!=", value="X").render() == "case_type != X"
    )


@pytest.mark.parametrize("template", TIER_2)
def test_mau_tang_2_bi_schema_chan(template):
    """ADR 0004 Q1a: schema chỉ cho tầng 1, tầng 2 không rời khỏi mô hình."""
    with pytest.raises(ReflectorOutputError):
        parse_reflector_output(json.dumps({"rules": [_rule(template=template)]}))


@pytest.mark.parametrize("field", TEMPORAL_FIELDS)
def test_truong_thoi_han_bi_schema_chan(field):
    """Không có chỗ cho trường thời gian: `additionalProperties: false`."""
    rule = _rule()
    rule[field] = "8 weeks"
    with pytest.raises(ReflectorOutputError):
        parse_reflector_output(json.dumps({"rules": [rule]}))


@pytest.mark.parametrize("operator", TEMPORAL_OPERATORS)
def test_dieu_kien_thoi_gian_bi_schema_chan(operator):
    """Điều kiện chỉ `=`/`!=` trên thuộc tính phân loại — không so sánh thời gian."""
    rule = _rule(condition={"attribute": "duration", "operator": operator, "value": "8 weeks"})
    with pytest.raises(ReflectorOutputError):
        parse_reflector_output(json.dumps({"rules": [rule]}))


def test_dieu_kien_them_truong_thoi_gian_bi_chan():
    rule = _rule(
        condition={
            "attribute": "case_type",
            "operator": "=",
            "value": "A",
            "unit": "weeks",
        }
    )
    with pytest.raises(ReflectorOutputError):
        parse_reflector_output(json.dumps({"rules": [rule]}))


def test_thieu_truong_bat_buoc_bi_chan():
    thieu_source = _rule()
    del thieu_source["source"]
    source_rong = _rule()
    source_rong["source"] = ""
    invalid_outputs = [
        {"rules": [_rule(template="response", activation="")]},
        {"rules": [_rule(target="")]},
        {"rules": [{"activation": "A", "target": "B"}]},
        {"rules": [{"template": "response", "target": "B"}]},
        {"rules": [{"template": "response", "activation": "A"}]},
        {"rules": [thieu_source]},
        {"rules": [source_rong]},
        {"rules": "response(A, B)"},
        {"rules": ["response(A, B)"]},
        {"rules": [], "extra": 1},
        {},
    ]
    for obj in invalid_outputs:
        with pytest.raises(ReflectorOutputError):
            parse_reflector_output(json.dumps(obj))


def test_text_khong_phai_json_bi_tu_choi():
    with pytest.raises(ReflectorOutputError):
        parse_reflector_output("đây không phải JSON")


def test_enum_mau_khop_tang_1_adr():
    """Schema chỉ cho đúng tầng 1 của ADR 0004 (Q1a)."""
    rule_schema = DECLARE_OUTPUT_SCHEMA["properties"]["rules"]["items"]
    assert rule_schema["properties"]["template"]["enum"] == ["response", "precedence"]


def test_schema_json_serializable_on_dinh():
    """Schema serialize được thành JSON xác định — khóa đệm (spec dòng 189) băm nó."""
    first = json.dumps(DECLARE_OUTPUT_SCHEMA, sort_keys=True)
    second = json.dumps(DECLARE_OUTPUT_SCHEMA, sort_keys=True)
    assert first == second
    assert len(first) > 0


def test_validate_object_da_parse():
    validate_reflector_output({"rules": [_rule()]})
    with pytest.raises(jsonschema.ValidationError):
        validate_reflector_output({"rules": [_rule(template="succession")]})


class _FakeServer:
    """Server giả tương thích OpenAI: trả phản hồi ghi sẵn, ghi lại yêu cầu."""

    def __init__(self, canned_text: str) -> None:
        self._canned_text = canned_text
        self.calls: list[httpx2.Request] = []

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        """Trả phản hồi ghi sẵn cho một yêu cầu."""
        self.calls.append(request)
        return httpx2.Response(
            200,
            json={
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
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )


def _model(canned_text: str) -> tuple[OpenAICompatibleModel, _FakeServer]:
    """Adapter trỏ về server giả; tắt vòng thử lại của SDK."""
    server = _FakeServer(canned_text)
    client = openai.OpenAI(
        base_url=CPU_BASE_URL,
        api_key="local",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(server.handler)),
    )
    model = OpenAICompatibleModel(
        client, model=MODEL_ID, max_retries=2, retry_base_delay_seconds=0.0
    )
    return model, server


def test_adapter_gui_schema_va_parse_thanh_luat():
    """Adapter gửi đúng schema này làm `response_format`, rồi parse ra luật."""
    canned = json.dumps({"rules": [_rule(), _rule(template="precedence")]})
    model, server = _model(canned)
    result = model.complete("đề xuất luật", json_schema=DECLARE_OUTPUT_SCHEMA)
    assert len(server.calls) == 1
    body = json.loads(server.calls[0].content.decode("utf-8"))
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "response", "schema": DECLARE_OUTPUT_SCHEMA},
    }
    rules = parse_reflector_output(result.text)
    assert [rule.canonical_key for rule in rules] == [
        "response(A, B)",
        "precedence(A, B)",
    ]


def test_adapter_tu_choi_luat_thoi_han():
    """Mô hình cố sinh luật thời hạn (trường `deadline`) → adapter từ chối."""
    canned_temporal = json.dumps(
        {
            "rules": [
                {
                    "template": "response",
                    "activation": "A",
                    "target": "B",
                    "source": "De aanvraag wordt ingediend.",
                    "deadline": "8 weeks",
                }
            ]
        }
    )
    model, server = _model(canned_temporal)
    with pytest.raises(ModelCallError):
        model.complete("quyết trong 8 tuần", json_schema=DECLARE_OUTPUT_SCHEMA)
    assert len(server.calls) == 1


@pytest.mark.parametrize("template", TIER_2)
def test_adapter_tu_choi_mau_tang_2(template):
    """Mô hình cố sinh mẫu tầng 2 → adapter từ chối ở phía host."""
    canned = json.dumps({"rules": [_rule(template=template)]})
    model, server = _model(canned)
    with pytest.raises(ModelCallError):
        model.complete("đề xuất luật", json_schema=DECLARE_OUTPUT_SCHEMA)
    assert len(server.calls) == 1


def test_adapter_tu_choi_dieu_kien_thoi_gian():
    """Mô hình cố nhét điều kiện thời gian vào `condition` → adapter từ chối."""
    canned = json.dumps(
        {
            "rules": [
                _rule(
                    condition={
                        "attribute": "duration",
                        "operator": "<",
                        "value": "8 weeks",
                    }
                )
            ]
        }
    )
    model, server = _model(canned)
    with pytest.raises(ModelCallError):
        model.complete("quyết trong 8 tuần", json_schema=DECLARE_OUTPUT_SCHEMA)
    assert len(server.calls) == 1


# --- Schema riêng đường tài liệu: enum 13 khái niệm Wabo (lần thử 5, 9.1) ---

TERMS_13 = [
    "aanvraag",
    "ontwerpbesluit",
    "ter inzage",
    "zienswijze",
    "besluit",
    "beschikking",
    "bezwaar",
    "beroep",
    "voorlopige voorziening",
    "verlengen",
    "buiten behandeling",
    "intrekken",
    "bekendmaking",
]


def test_document_schema_enum_chi_13_khai_niem_wabo():
    """Enum activation/target là đúng 13 `term` của bảng gắn (thứ tự bảng)."""
    from praxon_core.learning.declare_schema import document_output_schema
    from praxon_core.learning.dutch_mapping import default_dutch_mapping

    schema = document_output_schema()
    rule_schema = schema["properties"]["rules"]["items"]
    terms = [entry.term for entry in default_dutch_mapping().concept]
    assert terms == TERMS_13
    assert rule_schema["properties"]["activation"] == {"type": "string", "enum": TERMS_13}
    assert rule_schema["properties"]["target"] == {"type": "string", "enum": TERMS_13}


def test_document_schema_khac_trace_chi_o_activation_target():
    """Schema tài liệu khác schema trace chỉ ở activation/target."""
    from praxon_core.learning.declare_schema import document_output_schema

    doc_rule = document_output_schema()["properties"]["rules"]["items"]
    trace_rule = DECLARE_OUTPUT_SCHEMA["properties"]["rules"]["items"]
    for key in ("template", "source", "condition"):
        assert doc_rule["properties"][key] == trace_rule["properties"][key]
    assert doc_rule["required"] == trace_rule["required"]
    assert doc_rule["additionalProperties"] == trace_rule["additionalProperties"]


@pytest.mark.parametrize(
    "field", ["omgevingsvergunning", "2.15", "bevoegd gezag", "01_HOOFD_010", "A"]
)
def test_document_schema_tu_choi_tu_ngoai_bang(field):
    """Từ ngoài bảng (từ văn bản, số điều, tên tác nhân, mã log) bị chặn."""
    from praxon_core.learning.declare_schema import document_output_schema

    schema = document_output_schema()
    with pytest.raises(ReflectorOutputError):
        parse_reflector_output(json.dumps({"rules": [_rule(activation=field)]}), schema=schema)
    with pytest.raises(ReflectorOutputError):
        parse_reflector_output(json.dumps({"rules": [_rule(target=field)]}), schema=schema)


@pytest.mark.parametrize("term", TERMS_13)
def test_document_schema_nhan_ca_13_khai_niem(term):
    """Cả 13 khái niệm đều parse được ở cả hai vị trí."""
    from praxon_core.learning.declare_schema import document_output_schema

    schema = document_output_schema()
    rules = parse_reflector_output(
        json.dumps({"rules": [_rule(activation=term, target=term)]}), schema=schema
    )
    assert rules[0].activation == term
    assert rules[0].target == term


def test_document_schema_json_serializable_on_dinh():
    """Schema tài liệu serialize xác định và khác schema trace."""
    from praxon_core.learning.declare_schema import document_output_schema

    first = json.dumps(document_output_schema(), sort_keys=True)
    second = json.dumps(document_output_schema(), sort_keys=True)
    assert first == second
    assert first != json.dumps(DECLARE_OUTPUT_SCHEMA, sort_keys=True)


# --- Schema một luật (lần thử 6 chống liệt kê, 9.1) ---


def test_document_schema_max_rules_1_gioi_han_mang_rules():
    """`max_rules=1`: mảng `rules` có `maxItems = 1` — 1 luật parse được, 2 luật bị chặn."""
    from praxon_core.learning.declare_schema import document_output_schema

    schema = document_output_schema(max_rules=1)
    assert schema["properties"]["rules"]["maxItems"] == 1
    one = _rule(activation="aanvraag", target="besluit")
    rules = parse_reflector_output(json.dumps({"rules": [one]}), schema=schema)
    assert len(rules) == 1
    two = _rule(activation="aanvraag", target="bezwaar")
    with pytest.raises(ReflectorOutputError):
        parse_reflector_output(json.dumps({"rules": [one, two]}), schema=schema)


def test_document_schema_khong_max_rules_thi_khong_co_max_items():
    """Không truyền `max_rules` thì schema tài liệu như trước: không có `maxItems`."""
    from praxon_core.learning.declare_schema import document_output_schema

    assert "maxItems" not in document_output_schema()["properties"]["rules"]


@pytest.mark.parametrize("max_rules", [0, -1])
def test_document_schema_max_rules_khong_hop_le_thi_loi(max_rules):
    """`max_rules` phải >= 1 khi được đặt; 0 hay âm là lỗi lập trình, lộ ngay."""
    from praxon_core.learning.declare_schema import document_output_schema

    with pytest.raises(ValueError, match="max_rules phải >= 1"):
        document_output_schema(max_rules=max_rules)
