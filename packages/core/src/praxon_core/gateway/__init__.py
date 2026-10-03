"""Nơi DUY NHẤT trong praxon_core được import client MCP hoặc SDK agent.

`ToolGateway` sống ở đây: mọi tool call của mọi agent đi qua một cổng, nên chỉ
một chỗ vừa chặn được vừa ghi log cho vòng học. Hợp đồng
`client-tool-chi-trong-gateway-va-adapters` canh điều đó.
"""
