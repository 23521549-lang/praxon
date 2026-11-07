"""Test hợp đồng của proxy chèn khóa (task 9.1/13.1): timeout chuyển tiếp.

Proxy phải truyền timeout vào `urlopen` — mặc định 1800 giây, khớp tường
của client SDK (đo 9.1 hỏng EXIT:2 vì tường cũ 600 giây ở cả hai bên);
cờ `--timeout` ghi đè. Không gọi server thật: `urlopen` bị thay bằng
bản ghi giả, chỉ ghi lại tham số; proxy vẫn chạy thật trên cổng tạm.
"""

from __future__ import annotations

import http.client
import threading
import urllib.request
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Literal

import pytest
from tools.llm_auth_proxy import ENV_VAR, main, make_handler


def _serve(handler: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, int]:
    """Chạy một HTTP server trên cổng tạm (luồng nền), trả (server, cổng)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, int(server.server_address[1])


def _stop(server: ThreadingHTTPServer) -> None:
    server.shutdown()
    server.server_close()


class _FakeUpstreamResponse:
    """Phản hồi giả của upstream: đủ cho proxy đọc trọn rồi trả về."""

    def __init__(self) -> None:
        self.status = 200
        self.headers = Message()

    def read(self) -> bytes:
        return b'{"ok": true}'

    def __enter__(self) -> _FakeUpstreamResponse:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        return False


class _UrlopenRecorder:
    """`urlopen` giả: ghi lại (url, timeout), chuyển tiếp gọi tới proxy.

    Gọi tới cổng proxy thì gọi `urlopen` thật (proxy phải chạy thật);
    gọi tới upstream thì trả phản hồi giả (không có server thật).
    """

    def __init__(self, proxy_port: int) -> None:
        self.calls: list[tuple[str, float | None]] = []
        self._proxy_port = proxy_port
        self._real = urllib.request.urlopen

    def __call__(
        self, url: str | urllib.request.Request, *, timeout: float | None = None
    ) -> _FakeUpstreamResponse | http.client.HTTPResponse:
        target = url.full_url if isinstance(url, urllib.request.Request) else url
        self.calls.append((target, timeout))
        if f":{self._proxy_port}/" in target:
            # `urlopen` thật trả `addinfourl` (con của HTTPResponse);
            # typeshed gõ nó là Any nên khẳng định kiểu tại đây.
            response = self._real(url, timeout=timeout)
            assert isinstance(response, http.client.HTTPResponse)
            return response
        return _FakeUpstreamResponse()


def _upstream_timeouts(recorder: _UrlopenRecorder) -> list[float | None]:
    """Timeout của các lần gọi tới upstream (không tính gọi tới proxy)."""
    return [timeout for url, timeout in recorder.calls if ":9/" in url]


def test_proxy_truyen_timeout_mac_dinh_1800(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy, proxy_port = _serve(make_handler("http://127.0.0.1:9", "k"))
    recorder = _UrlopenRecorder(proxy_port)
    monkeypatch.setattr(urllib.request, "urlopen", recorder)
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{proxy_port}/v1/models", method="GET"
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            assert response.status == 200
            assert response.read() == b'{"ok": true}'
    finally:
        _stop(proxy)
    assert _upstream_timeouts(recorder) == [1800.0]


def test_proxy_truyen_timeout_tuy_chon(monkeypatch: pytest.MonkeyPatch) -> None:
    proxy, proxy_port = _serve(make_handler("http://127.0.0.1:9", "k", timeout=42.0))
    recorder = _UrlopenRecorder(proxy_port)
    monkeypatch.setattr(urllib.request, "urlopen", recorder)
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{proxy_port}/v1/models", method="GET"
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            assert response.status == 200
    finally:
        _stop(proxy)
    assert _upstream_timeouts(recorder) == [42.0]


def test_cli_timeout_duoc_truyen_vao_make_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, float] = {}

    def _fake_make_handler(
        upstream: str, api_key: str, *, timeout: float
    ) -> type[BaseHTTPRequestHandler]:
        seen["timeout"] = timeout
        return BaseHTTPRequestHandler

    class _DummyServer:
        """Server giả: `main` chỉ cần dựng + `serve_forever`, không chạy thật."""

        def __init__(self, address: object, handler: object) -> None:
            pass

        def serve_forever(self) -> None:
            pass

    monkeypatch.setattr("tools.llm_auth_proxy.make_handler", _fake_make_handler)
    monkeypatch.setattr("tools.llm_auth_proxy.ThreadingHTTPServer", _DummyServer)
    monkeypatch.setenv(ENV_VAR, "k")
    assert main(["--upstream", "http://127.0.0.1:9", "--timeout", "42"]) == 0
    assert seen["timeout"] == 42.0
    assert main(["--upstream", "http://127.0.0.1:9"]) == 0
    assert seen["timeout"] == 1800.0
