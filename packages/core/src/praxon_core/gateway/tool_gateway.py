"""Giao diện `ToolGateway` — cổng duy nhất mọi tool call phải đi qua.

Spec (mục "Nền móng cho phòng điều khiển"): một tool call đi qua cổng này và
nhận về một trong bốn quyết định — cho, chặn, hỏi người, để luật quyết — cùng
bốn giá trị hook `PreToolUse` của Claude Code dùng. Lát cắt này chỉ khai báo
giao diện và test hợp đồng với một cổng giả; proxy MCP thật làm ở giai đoạn 2a.

Không import client MCP hay SDK agent ở đây: hợp đồng import-linter
`client-tool-chi-trong-gateway-va-adapters` cho phép các import đó chỉ trong
`gateway` và `adapters`, nhưng giao diện tự nó không cần chúng.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ToolDecision(StrEnum):
    """Một trong bốn quyết định của `ToolGateway` cho một tool call."""

    ALLOW = "allow"
    DENY = "deny"
    ASK_USER = "ask"
    DEFER_TO_POLICY = "defer"


@dataclass(frozen=True)
class ToolCall:
    """Một tool call đưa qua `ToolGateway` để xin quyết định.

    `tool` là tên công cụ, `arguments` là đối số của nó. Ba trường còn lại là
    ngữ cảnh để cổng ghi log và để luật quyết: ai gọi, thuộc run nào, của
    tenant nào. Tất cả đều tùy chọn vì cổng giả trong test hợp đồng không cần
    chúng; cổng thật ở giai đoạn 2a sẽ điền đầy đủ để ghi bảng `event`.
    """

    tool: str
    arguments: Mapping[str, object] = field(default_factory=dict)
    actor: str | None = None
    run_id: str | None = None
    tenant_id: str | None = None


class ToolGateway(Protocol):
    """Cổng duy nhất mọi tool call phải đi qua.

    Bên gọi đưa một `ToolCall` vào và nhận về đúng một `ToolDecision`; quyết
    định đó là thứ bên gọi phải tuân theo — không có đường vòng qua cổng.
    """

    def decide(self, call: ToolCall) -> ToolDecision:
        """Trả về một trong bốn quyết định cho một tool call."""
