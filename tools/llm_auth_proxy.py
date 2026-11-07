"""Proxy chèn khóa API cho server mô hình (task 13.1, service `llm-proxy`).

Vấn đề: backend `"cpu"` của `praxon_core.adapters.language_model` luôn gửi
khóa giả cố định `"local"` (`LOCAL_API_KEY`) — nó không bao giờ đọc
`settings.openai_api_key`. Server llama.cpp trong compose chạy với
`--api-key` (khóa một lần qua env) nên gọi thẳng sẽ 401. Proxy này đứng
giữa: nhận yêu cầu từ service `eval`, chèn `Authorization: Bearer` bằng
khóa thật từ biến môi trường `PRAXON_LLM_API_KEY`, chuyển tiếp tới server
mô hình, trả nguyên trạng thái + thân phản hồi về.

Mẫu này đã chứng minh ở đo 9.1 (proxy shim trong sandbox Docker). Chỉ dùng
thư viện chuẩn — không cần SDK, không cần phụ thuộc nào khác. Client mô
hình không dùng streaming (`chat.completions.create` không truyền
`stream=True`) nên proxy đọc trọn phản hồi rồi trả về (không cần chuyển
tiếp theo khối).

Khóa KHÔNG BAO GIỜ ghi vào log hay in ra: log chỉ ghi phương thức, đường
dẫn và mã trạng thái. Thiếu khóa thì thoát 2 ngay, chưa nhận yêu cầu nào.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ENV_VAR = "PRAXON_LLM_API_KEY"

#: Header không chuyển tiếp (do hop gây nhiễu hoặc do urllib tự đặt).
_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-connection",
        "transfer-encoding",
        "upgrade",
        "content-length",
        "host",
        "authorization",
    }
)


def _forward_headers(incoming: Message[str, str]) -> dict[str, str]:
    """Lọc header yêu cầu: bỏ hop-by-hop + Host + Authorization cũ."""
    forwarded: dict[str, str] = {}
    for name, value in incoming.items():
        if name.lower() in _HOP_HEADERS:
            continue
        forwarded[name] = value
    return forwarded


def _filter_response_headers(headers: Message[str, str]) -> list[tuple[str, str]]:
    """Lọc header phản hồi: bỏ hop-by-hop, giữ còn lại."""
    return [
        (name, value) for name, value in headers.items() if name.lower() not in _HOP_HEADERS
    ]


def make_handler(
    upstream: str, api_key: str, *, timeout: float = 1800.0
) -> type[BaseHTTPRequestHandler]:
    """Dựng lớp handler chuyển tiếp tới `upstream` với khóa đã cho.

    `timeout` là giới hạn chờ (giây) của một lần chuyển tiếp tới server
    mô hình — mặc định 1800 giây, khớp tường timeout của client SDK
    (task 9.1: đoạn Wabo dài sinh ~690 giây, tường cũ 600 giây làm
    mọi lần gọi chết đúng tường). Không đổi tường này mà không đổi
    cả hai bên: lệch nhau thì tường thấp hơn vẫn giết lần gọi.
    """

    class ProxyHandler(BaseHTTPRequestHandler):
        """Chuyển tiếp một yêu cầu, chèn khóa, trả nguyên phản hồi."""

        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: object) -> None:
            """Chỉ ghi phương thức + đường dẫn + trạng thái, không ghi khóa."""
            sys.stderr.write(f"{self.address_string()} {format % args}\n")

        def _forward(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length > 0 else None
            url = upstream.rstrip("/") + self.path
            headers = _forward_headers(self.headers)
            headers["Authorization"] = f"Bearer {api_key}"
            request = urllib.request.Request(
                url, data=body, headers=headers, method=self.command
            )
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    payload = response.read()
                    self.send_response(response.status)
                    for name, value in _filter_response_headers(response.headers):
                        self.send_header(name, value)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
            except urllib.error.HTTPError as exc:
                payload = exc.read()
                self.send_response(exc.code)
                for name, value in _filter_response_headers(exc.headers):
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except urllib.error.URLError as exc:
                message = f"proxy: không tới được server mô hình: {exc}".encode()
                self.send_response(502)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(message)))
                self.end_headers()
                self.wfile.write(message)

        # Tên phương thức bắt buộc của BaseHTTPRequestHandler (không phải
        # biến mixedCase do code đặt — ruff N815 không áp cho tên API này).
        do_GET = _forward  # noqa: N815
        do_POST = _forward  # noqa: N815
        do_PUT = _forward  # noqa: N815
        do_PATCH = _forward  # noqa: N815
        do_DELETE = _forward  # noqa: N815

    return ProxyHandler


def main(argv: list[str] | None = None) -> int:
    """Chạy proxy: `python -m tools.llm_auth_proxy --upstream URL --port N`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--upstream",
        required=True,
        help="URL gốc của server mô hình (vd http://model:8000)",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="host lắng nghe (mặc định %(default)s)"
    )
    parser.add_argument(
        "--port", type=int, default=8081, help="cổng lắng nghe (mặc định %(default)s)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=1800.0,
        help="timeout (giây) của một lần chuyển tiếp tới server mô hình "
        "(mặc định %(default)s, khớp tường của client SDK)",
    )
    args = parser.parse_args(argv)
    api_key = os.environ.get(ENV_VAR)
    if not api_key:
        print(
            f"thiếu khóa API: đặt biến môi trường {ENV_VAR}",
            file=sys.stderr,
        )
        return 2
    handler = make_handler(args.upstream, api_key, timeout=args.timeout)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        f"llm-auth-proxy: nghe {args.host}:{args.port}, chuyển tiếp tới {args.upstream}",
        file=sys.stderr,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
