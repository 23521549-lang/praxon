"""JSON schema Declare cho đầu ra của Reflector (task 6.2, spec dòng 88, 176).

Spec bất biến 3 (dòng 88): "Đầu ra của Reflector luôn đúng lược đồ. Giải
mã có ràng buộc loại lỗi cú pháp; đúng cú pháp chưa có nghĩa là đúng luật,
đó là việc của Governor và của phép đo." Spec dòng 176: "JSON schema của
Reflector chỉ cho các mẫu trong từ vựng, nên mô hình không thể sinh luật
thời hạn."

Từ vựng (ADR 0004, Q1a — đã chốt): schema chỉ cho tầng 1 (`response`,
`precedence`). Tầng 2 (`succession`, `init`, `end`, `not_response`,
`not_precedence`) chỉ ghi nguồn để diễn giải, không phát sinh fact — nên
schema KHÔNG cho mô hình sinh chúng (chặn ở schema, không phải ở cổng vào
kho: luật tầng 2 không bao giờ rời khỏi mô hình). Muốn nâng tầng thì sửa
ADR trước, rồi mới sửa schema này (có test bắt).

Luật thời hạn bị chặn theo cấu trúc, không phải bằng danh sách cấm:
mọi object đều `additionalProperties: false` (không có chỗ cho trường
`deadline`/`within`/`duration`/`time_limit` hay bất kỳ trường thời gian
nào), và `condition` là object có cấu trúc với phép so sánh chỉ `=`/`!=`
trên thuộc tính phân loại — không có phép so sánh thời gian, không có
trường đơn vị/khoảng thời gian. Điều kiện dạng chuỗi tự do sẽ cho mô hình
nhét "within 8 weeks" vào, nên điều kiện KHÔNG phải chuỗi tự do.

Cách dùng: Reflector (6.4) truyền `DECLARE_OUTPUT_SCHEMA` cho adapter
(`LanguageModel.complete(..., json_schema=...)`) — adapter gửi
`response_format` cho server (giải mã có ràng buộc) VÀ kiểm lại ở phía
host bằng `jsonschema` — rồi gọi `parse_reflector_output` để lấy danh
sách `DeclareRule` có kiểu. Khóa đệm (spec dòng 189) băm schema này, nên
đổi schema là đổi khóa đệm.

Không có `maxItems` cho `rules`: trần số insight mỗi lô là tham số cấu
hình của Reflector (bất biến 4, task 6.4), không phải hằng của schema —
hard-code nó ở đây là hard-code số chính sách.

Mỗi luật phải kèm `source`: trích dẫn nguyên văn (một câu hoặc một phần
câu) trong đoạn mà luật đó lấy từ đó, là lần thử 2 chống liệt kê từ vựng
(9.1, 2026-11-09). Schema bắt buộc trường này (`minLength: 1`) nên mô
hình thiếu trích dẫn thì cả lô sai lược đồ; đường tài liệu còn lọc cơ
học sau parse, bỏ luật có trích dẫn không khớp đoạn (xem Reflector).

Đường tài liệu có schema riêng (`document_output_schema`, lần thử 5,
9.1, 2026-11-09): `activation`/`target` là enum 13 khái niệm Wabo
(`term` của bảng gắn, không phải tên hoạt động log) — llama-server
chuyển schema thành GBNF và ép giải mã, nên mô hình không thể sinh từ
ngoài bảng (`omgevingsvergunning`, `2.15`, `bevoegd gezag`) ở hai vị
trí này. Đường trace giữ nguyên `DECLARE_OUTPUT_SCHEMA` (mã log tự do).
Chế độ một luật (lần thử 6, 9.1) truyền `max_rules=1` cho
`document_output_schema`: mảng `rules` bị giới hạn bằng `maxItems` nên
mô hình không thể sinh luật thứ hai — `max_rules` là tham số của bên
gọi, không phải hằng chính sách hard-code (trần insight mỗi lô vẫn là
tham số cấu hình của Reflector, xem trên).
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

import jsonschema

from praxon_core.learning.dutch_mapping import (
    DutchMappingTable,
    default_dutch_mapping,
)
from praxon_core.learning.payload import canonical_key_for

__all__ = [
    "CONDITION_OPERATORS",
    "DECLARE_OUTPUT_SCHEMA",
    "DECLARE_RULE_SCHEMA",
    "TIER_1_TEMPLATES",
    "Condition",
    "DeclareRule",
    "ReflectorOutputError",
    "document_output_schema",
    "document_rule_schema",
    "parse_reflector_output",
    "validate_reflector_output",
]

#: Mẫu Declare tầng 1 (ADR 0004, Q1a): chỉ hai mẫu này được Reflector sinh.
#: Tầng 2 bị chặn ở schema (xem docstring module).
TIER_1_TEMPLATES: tuple[str, ...] = ("response", "precedence")

#: Phép so sánh cho điều kiện trên thuộc tính phân loại (spec dòng 144,
#: 176): chỉ bằng/khác — không có phép so sánh thời gian.
CONDITION_OPERATORS: tuple[str, ...] = ("=", "!=")

#: JSON Schema cho một luật Declare. Viết thẳng (không `$ref`) để bộ
#: chuyển schema → GBNF của llama-server hiểu được chắc chắn.
DECLARE_RULE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "template": {"type": "string", "enum": list(TIER_1_TEMPLATES)},
        "activation": {"type": "string", "minLength": 1},
        "target": {"type": "string", "minLength": 1},
        "source": {"type": "string", "minLength": 1},
        "condition": {
            "type": "object",
            "properties": {
                "attribute": {"type": "string", "minLength": 1},
                "operator": {"type": "string", "enum": list(CONDITION_OPERATORS)},
                "value": {"type": "string", "minLength": 1},
            },
            "required": ["attribute", "operator", "value"],
            "additionalProperties": False,
        },
    },
    "required": ["template", "activation", "target", "source"],
    "additionalProperties": False,
}

#: JSON Schema cho toàn bộ đầu ra của Reflector: một object chứa danh sách
#: luật. Gốc phải là object vì `response_format` kiểu JSON schema của OpenAI
#: đòi vậy. Không đổi dict này tại chỗ — khóa đệm (spec dòng 189) băm nó.
DECLARE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"rules": {"type": "array", "items": DECLARE_RULE_SCHEMA}},
    "required": ["rules"],
    "additionalProperties": False,
}


def document_rule_schema(mapping: DutchMappingTable) -> dict[str, Any]:
    """Trả schema một luật cho đường tài liệu: chỉ 13 khái niệm Wabo.

    Giống `DECLARE_RULE_SCHEMA` nhưng `activation`/`target` là enum các
    `term` của bảng gắn (lần thử 5 chống liệt kê, 9.1, 2026-11-09) —
    llama-server chuyển schema thành GBNF và ép giải mã nên mô hình
    không thể sinh từ ngoài bảng ở hai vị trí này. Enum là `term`
    (khái niệm Wabo), KHÔNG phải `dutch_name` của hoạt động log: mô hình
    viết khái niệm, `resolve_activity` gắn khái niệm đó sang mã canonical.
    """
    schema = copy.deepcopy(DECLARE_RULE_SCHEMA)
    terms = [entry.term for entry in mapping.concept]
    schema["properties"]["activation"] = {"type": "string", "enum": terms}
    schema["properties"]["target"] = {"type": "string", "enum": terms}
    return schema


def document_output_schema(
    mapping: DutchMappingTable | None = None,
    *,
    max_rules: int | None = None,
) -> dict[str, Any]:
    """Trả schema đầu ra cho đường tài liệu: luật theo `document_rule_schema`.

    `mapping` không truyền thì dùng bảng gắn mặc định (tệp TOML cạnh
    `dutch_mapping.py`). Mỗi lần gọi dựng dict mới — khóa đệm băm nội
    dung nên dict mới với cùng nội dung cho cùng khóa. `max_rules`
    giới hạn số luật trong mảng `rules` bằng `maxItems` (chế độ một
    luật của lần thử 6 chống liệt kê, 9.1: `max_rules=1` — llama-server
    chuyển thành GBNF nên mô hình không thể sinh luật thứ hai; không
    truyền thì không giới hạn, như trước).
    """
    if max_rules is not None and max_rules < 1:
        raise ValueError(f"max_rules phải >= 1 khi được đặt, nhận {max_rules}")
    table = mapping if mapping is not None else default_dutch_mapping()
    rules_schema: dict[str, Any] = {
        "type": "array",
        "items": document_rule_schema(table),
    }
    if max_rules is not None:
        rules_schema["maxItems"] = max_rules
    return {
        "type": "object",
        "properties": {"rules": rules_schema},
        "required": ["rules"],
        "additionalProperties": False,
    }


class ReflectorOutputError(ValueError):
    """Đầu ra của Reflector không parse được JSON hoặc không khớp schema.

    Bên gọi (Reflector, 6.4) bắt lỗi này để đánh dấu cả lô thất bại, không
    dùng luật nửa vời.
    """


@dataclass(frozen=True)
class Condition:
    """Điều kiện trên thuộc tính phân loại (MP-Declare, spec dòng 144).

    Chỉ bằng/khác trên giá trị phân loại — không có thời gian. `render`
    ra dạng chuỗi mà `Insight`/`FactPayload` đang dùng (`condition:
    str | None`), để một luật có điều kiện ghép đúng `canonical_key`
    bằng `canonical_key_for`.
    """

    attribute: str
    operator: str
    value: str

    def render(self) -> str:
        """Dạng chuỗi của điều kiện, vd `case_type = A`."""
        return f"{self.attribute} {self.operator} {self.value}"


@dataclass(frozen=True)
class DeclareRule:
    """Một luật Declare mà Reflector đề xuất (đã đúng lược đồ).

    Đây là hình dạng đầu ra của mô hình — chưa phải `Insight`: mô hình
    không biết case làm bằng chứng hay phạm vi, hai thứ đó Reflector (6.4)
    gắn thêm khi xây Insight. `source` là trích dẫn nguyên văn trong đoạn
    mà luật lấy từ đó (một câu hoặc một phần câu).
    """

    template: str
    activation: str
    target: str
    source: str
    condition: Condition | None = None

    @property
    def condition_string(self) -> str | None:
        """Điều kiện dạng chuỗi (`None` khi luật không có điều kiện)."""
        if self.condition is None:
            return None
        return self.condition.render()

    @property
    def canonical_key(self) -> str:
        """Khóa canonical của luật (cùng hàm `payload` dùng)."""
        return canonical_key_for(
            self.template, self.activation, self.target, self.condition_string
        )


def validate_reflector_output(obj: object, *, schema: dict[str, Any] | None = None) -> None:
    """Kiểm một object đã parse có khớp schema đầu ra của Reflector không.

    Sai thì `jsonschema.ValidationError` — bên gọi đổi thành
    `ReflectorOutputError` nếu muốn một loại lỗi duy nhất. `schema`
    không truyền thì dùng schema chung của đường trace; đường tài liệu
    truyền `document_output_schema()`.
    """
    jsonschema.validate(
        instance=obj, schema=schema if schema is not None else DECLARE_OUTPUT_SCHEMA
    )


def parse_reflector_output(
    text: str, *, schema: dict[str, Any] | None = None
) -> list[DeclareRule]:
    """Parse text phản hồi của mô hình thành danh sách luật Declare.

    Text phải là JSON khớp schema đầu ra (`DECLARE_OUTPUT_SCHEMA` mặc
    định; đường tài liệu truyền `document_output_schema()`); sai (không
    parse được JSON, sai lược đồ) thì `ReflectorOutputError` — không trả
    luật nửa vời.
    """
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReflectorOutputError(f"đầu ra Reflector không parse được JSON: {exc}") from exc
    try:
        validate_reflector_output(parsed, schema=schema)
    except jsonschema.ValidationError as exc:
        raise ReflectorOutputError(
            f"đầu ra Reflector không khớp JSON schema: {exc.message}"
        ) from exc
    rules: list[DeclareRule] = []
    for raw in parsed["rules"]:
        condition = None
        raw_condition = raw.get("condition")
        if raw_condition is not None:
            condition = Condition(
                attribute=str(raw_condition["attribute"]),
                operator=str(raw_condition["operator"]),
                value=str(raw_condition["value"]),
            )
        rules.append(
            DeclareRule(
                template=str(raw["template"]),
                activation=str(raw["activation"]),
                target=str(raw["target"]),
                source=str(raw["source"]),
                condition=condition,
            )
        )
    return rules
