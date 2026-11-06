"""Bảng luật của Governor: tệp cấu hình, kiểm bằng Pydantic lúc nạp.

Điều kiện chỉ là cây so sánh trên danh sách đại lượng cho trước — không có
`eval`, không có tên lạ. Mọi con số chính sách nằm ở mục `[policy]` của tệp;
các luật tham chiếu chúng bằng `{ policy = "<tên>" }` để không trùng lặp.
"""

from __future__ import annotations

import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal, TypeGuard

from pydantic import BaseModel, ConfigDict, Field, model_validator

from praxon_core.learning.beta import Prior, check_prior_invariant
from praxon_core.learning.candidate import DecisionVerdict, FactStatus
from praxon_core.learning.measures import MeasureName

DEFAULT_RULE_TABLE_FILENAME = "default_rule_table.toml"


class ComparisonOp(StrEnum):
    """Phép so sánh được phép trong điều kiện của bảng luật."""

    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    IN = "in"
    NOT_IN = "not_in"


class Comparison(BaseModel):
    """Một phép so sánh: đại lượng, phép so sánh, giá trị.

    Kiểu của giá trị được kiểm lại trong `_check_value` (kể cả phân biệt
    bool với int — bool là lớp con của int trong Python), để một giá trị
    sai kiểu trong tệp bị từ chối thay vì bị ép kiểu im lặng.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["compare"] = "compare"
    measure: MeasureName
    op: ComparisonOp
    value: bool | float | int | str | list[bool | float | int | str]

    @model_validator(mode="after")
    def _check_value_matches_measure(self) -> Comparison:
        _check_value(self.measure, self.op, self.value)
        return self


class AllCondition(BaseModel):
    """Tất cả điều kiện con đều đúng."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["all"] = "all"
    children: list[Condition]


class AnyCondition(BaseModel):
    """Ít nhất một điều kiện con đúng."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["any"] = "any"
    children: list[Condition]


class NotCondition(BaseModel):
    """Phủ định một điều kiện."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["not"] = "not"
    child: Condition


Condition = Annotated[
    Comparison | AllCondition | AnyCondition | NotCondition,
    Field(discriminator="kind"),
]

# Kiểu giá trị mỗi đại lượng nhận: bool, float (chấp nhận int), int, str,
# hoặc fact_status (str nhưng phải là một trong ba trạng thái của fact).
_MEASURE_VALUE_KINDS: dict[MeasureName, str] = {
    MeasureName.HAS_DIRECT_CONFLICT: "bool",
    MeasureName.SCHEMA_VALID: "bool",
    MeasureName.FROM_TRACE: "bool",
    MeasureName.WILSON_LOWER: "float",
    MeasureName.BETA_PROB: "float",
    MeasureName.IS_SCOPE_PROMOTION: "bool",
    MeasureName.FROM_GLOBAL: "bool",
    MeasureName.HAS_CONDITION: "bool",
    MeasureName.MATCHING_CASES: "int",
    MeasureName.FACT_STATUS: "fact_status",
    MeasureName.IS_NEW: "bool",
    MeasureName.HUMAN_EARLY_ACTIVATE: "bool",
    MeasureName.HAS_RUBRIC_CLAUSE: "bool",
}


def _is_number(value: object) -> TypeGuard[int | float]:
    """Số (int/float) nhưng không phải bool — bool là lớp con của int."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_scalar(kind: str, value: object) -> None:
    """Kiểm một giá trị vô hướng khớp kiểu của đại lượng."""
    if kind == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"đại lượng bool cần giá trị bool, nhận {value!r}")
    elif kind == "float":
        if not _is_number(value):
            raise ValueError(f"đại lượng float cần giá trị số, nhận {value!r}")
        number = float(value)
        if not 0.0 <= number <= 1.0:
            raise ValueError(f"đại lượng float trong [0, 1], nhận {value!r}")
    elif kind == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"đại lượng int cần giá trị int, nhận {value!r}")
        if value < 0:
            raise ValueError(f"số case không âm, nhận {value!r}")
    elif kind == "fact_status":
        if not isinstance(value, str) or value not in {s.value for s in FactStatus}:
            raise ValueError(f"fact_status phải là trial/active/retired, nhận {value!r}")
    else:  # pragma: no cover - mọi đại lượng đều có kiểu trong bảng trên.
        raise ValueError(f"kiểu đại lượng lạ: {kind}")


def _check_value(
    measure: MeasureName,
    op: ComparisonOp,
    value: bool | float | int | str | list[bool | float | int | str],
) -> None:
    """Kiểm giá trị so sánh khớp kiểu của đại lượng."""
    kind = _MEASURE_VALUE_KINDS[measure]
    if kind == "bool" and op in (
        ComparisonOp.LT,
        ComparisonOp.LE,
        ComparisonOp.GT,
        ComparisonOp.GE,
    ):
        raise ValueError(f"phép {op.value} không dùng cho đại lượng bool")
    if op in (ComparisonOp.IN, ComparisonOp.NOT_IN):
        if not isinstance(value, list) or not value:
            raise ValueError(f"phép {op.value} cần danh sách giá trị không rỗng")
        for item in value:
            _check_scalar(kind, item)
        return
    _check_scalar(kind, value)


class Rule(BaseModel):
    """Một luật trong bảng: điều kiện khớp thì quyết định thắng.

    `prior` là tiên nghiệm khai trong gói luật (độ tin + độ mạnh); None
    nghĩa là dùng độ mạnh mặc định của chính sách.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: int = Field(gt=0)
    applies_to: str
    condition: Condition
    verdict: DecisionVerdict
    target_status: FactStatus | None = None
    prior: Prior | None = None


class Policy(BaseModel):
    """Tham số chính sách của Governor (spec: nằm trong tệp cấu hình).

    Không có giá trị mặc định ở đây: tệp cấu hình phải khai đủ, để con số
    chỉ tồn tại ở một chỗ duy nhất là tệp đó.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    confidence_threshold: float = Field(gt=0.0, lt=1.0)
    promote_probability: float = Field(gt=0.0, lt=1.0)
    retire_probability: float = Field(gt=0.0, lt=1.0)
    prior_strength_default: float = Field(gt=0.0)
    min_matching_cases: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_order(self) -> Policy:
        if self.retire_probability >= self.promote_probability:
            raise ValueError(
                "retire_probability phải nhỏ hơn promote_probability, "
                f"nhận {self.retire_probability} và {self.promote_probability}"
            )
        return self


def _resolve_condition_refs(condition: object, policy: dict[str, Any]) -> object:
    """Thay mỗi `{ policy = "<tên>" }` bằng giá trị trong mục [policy]."""
    if not isinstance(condition, dict):
        return condition
    kind = condition.get("kind")
    if kind == "compare":
        value = condition.get("value")
        if isinstance(value, dict) and set(value) == {"policy"}:
            name = value["policy"]
            if not isinstance(name, str) or name not in policy:
                raise ValueError(f"tham chiếu chính sách lạ: {name!r}")
            return {**condition, "value": policy[name]}
        return condition
    if kind in ("all", "any"):
        children = condition.get("children", [])
        resolved = [
            _resolve_condition_refs(child, policy) if isinstance(child, dict) else child
            for child in children
        ]
        return {**condition, "children": resolved}
    if kind == "not":
        child = condition.get("child")
        return {**condition, "child": _resolve_condition_refs(child, policy)}
    return condition


class RuleTable(BaseModel):
    """Bảng luật đã nạp: tham số chính sách + các luật theo thứ tự."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy: Policy
    rules: list[Rule]

    @model_validator(mode="before")
    @classmethod
    def _resolve_policy_refs(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        policy = data.get("policy")
        rules = data.get("rules")
        if not isinstance(policy, dict) or not isinstance(rules, list):
            return data
        resolved = [
            {**rule, "condition": _resolve_condition_refs(rule.get("condition"), policy)}
            if isinstance(rule, dict)
            else rule
            for rule in rules
        ]
        return {**data, "rules": resolved}

    @model_validator(mode="after")
    def _check_rules(self) -> RuleTable:
        if not self.rules:
            raise ValueError("bảng luật rỗng")
        ids = [rule.id for rule in self.rules]
        if len(set(ids)) != len(ids):
            raise ValueError(f"số hiệu luật trùng: {ids}")
        priors = [
            Prior(canonical_key="mặc định", confidence=1.0, strength=None),
            *(rule.prior for rule in self.rules if rule.prior is not None),
        ]
        check_prior_invariant(
            priors,
            confidence_threshold=self.policy.confidence_threshold,
            promote_probability=self.policy.promote_probability,
            prior_strength_default=self.policy.prior_strength_default,
        )
        return self


def load_rule_table(path: Path) -> RuleTable:
    """Nạp bảng luật từ tệp TOML, kiểm bằng Pydantic lúc nạp."""
    raw: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
    return RuleTable.model_validate(raw)


def default_rule_table() -> RuleTable:
    """Bảng luật mặc định — chín luật trong spec giai đoạn 1."""
    path = Path(__file__).with_name(DEFAULT_RULE_TABLE_FILENAME)
    return load_rule_table(path)
