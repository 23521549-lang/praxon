"""ToolGateway: giao diện bốn quyết định và test hợp đồng với một cổng giả."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError

import pytest

from praxon_core.gateway import ToolCall, ToolDecision, ToolGateway


class FakeGateway:
    """Cổng giả: quyết định theo tên công cụ, công cụ lạ thì để luật quyết."""

    def __init__(self, decisions: Mapping[str, ToolDecision]) -> None:
        """Ghi bảng quyết định theo tên công cụ."""
        self._decisions = decisions

    def decide(self, call: ToolCall) -> ToolDecision:
        """Trả về quyết định đã ghi cho công cụ, hoặc để luật quyết."""
        return self._decisions.get(call.tool, ToolDecision.DEFER_TO_POLICY)


def _go_through_gateway(gateway: ToolGateway, call: ToolCall) -> ToolDecision:
    """Đường duy nhất một tool call đi qua: qua cổng, nhận quyết định."""
    return gateway.decide(call)


def test_bon_quyet_dinh_co_du():
    assert set(ToolDecision) == {
        ToolDecision.ALLOW,
        ToolDecision.DENY,
        ToolDecision.ASK_USER,
        ToolDecision.DEFER_TO_POLICY,
    }
    assert ToolDecision.ALLOW.value == "allow"
    assert ToolDecision.DENY.value == "deny"
    assert ToolDecision.ASK_USER.value == "ask"
    assert ToolDecision.DEFER_TO_POLICY.value == "defer"


def test_tool_call_mac_dinh_rong():
    call = ToolCall(tool="doc")
    assert call.arguments == {}
    assert call.actor is None
    assert call.run_id is None
    assert call.tenant_id is None


def test_tool_call_bat_bien():
    call = ToolCall(tool="doc")
    with pytest.raises(FrozenInstanceError):
        # Gán vào field của dataclass frozen là lỗi kiểu theo mypy, nhưng test
        # này cố tình làm vậy để khẳng định hành vi lúc chạy: phải bị chặn.
        call.tool = "khac"  # type: ignore[misc]


@pytest.mark.parametrize(
    "decision",
    [
        ToolDecision.ALLOW,
        ToolDecision.DENY,
        ToolDecision.ASK_USER,
        ToolDecision.DEFER_TO_POLICY,
    ],
)
def test_fake_tra_ve_dung_quyet_dinh(decision):
    gateway = FakeGateway({"cong_cu": decision})
    assert _go_through_gateway(gateway, ToolCall(tool="cong_cu")) is decision


def test_cong_chua_biet_thi_de_luat_quyet():
    gateway = FakeGateway({"doc": ToolDecision.ALLOW})
    assert _go_through_gateway(gateway, ToolCall(tool="la")) is ToolDecision.DEFER_TO_POLICY


def test_fake_thoa_hop_dong_tool_gateway():
    gateway: ToolGateway = FakeGateway({})
    assert _go_through_gateway(gateway, ToolCall(tool="la")) is ToolDecision.DEFER_TO_POLICY
