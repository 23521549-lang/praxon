"""Tool lấy dữ liệu BPIC 2015 cho CI: cache, chính thức, dự phòng Drive.

Dùng máy chủ figshare giả (mẫu đã có ở tests/test_bpic2015.py) và zip dự
phòng giả trong tmp_path; không gọi mạng thật, không đọc cache thật.
"""

from __future__ import annotations

import hashlib
import http.server
import io
import json
import threading
import zipfile
from typing import Never, cast

import pytest
from tools.ci_fetch_bpic2015 import ENV_FALLBACK_URL, FetchError, FetchResult, fetch, main

from praxon_core.datasets.bpic2015 import BPIC2015_DATASETS

FAKE_XES = b'<log><trace><string key="concept:name" value="c1"/></trace></log>'
WRONG_XES = b'<log><trace><string key="concept:name" value="khac"/></trace></log>'


class _FakeFigshare(http.server.ThreadingHTTPServer):
    """Máy chủ figshare giả: giữ bảng route và đếm lượt gọi."""

    routes: dict[str, tuple[int, bytes, str]]
    hits: dict[str, int]

    def __init__(self, address: tuple[str, int]) -> None:
        super().__init__(address, _Handler)
        self.routes = {}
        self.hits = {}


class _Handler(http.server.BaseHTTPRequestHandler):
    """Trả nội dung theo bảng route của máy chủ giả."""

    def do_GET(self) -> None:
        server = cast(_FakeFigshare, self.server)
        server.hits[self.path] = server.hits.get(self.path, 0) + 1
        status, body, content_type = server.routes.get(
            self.path, (404, b"not found", "text/plain")
        )
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def figshare_server():
    """Máy chủ figshare giả trên cổng tạm, tự dọn sau test."""
    server = _FakeFigshare(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def _api_base(server: _FakeFigshare) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}/v2/articles"


def _fallback_url(server: _FakeFigshare) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}/fallback.zip"


def _article_body(server: _FakeFigshare, xes_bytes: bytes) -> bytes:
    base = f"http://127.0.0.1:{server.server_address[1]}"
    digest = hashlib.md5(xes_bytes).hexdigest()
    return json.dumps(
        {
            "id": BPIC2015_DATASETS[0].article_id,
            "files": [
                {
                    "name": "BPIC15_1.xes",
                    "size": len(xes_bytes),
                    "computed_md5": digest,
                    "download_url": f"{base}/files/BPIC15_1.xes",
                },
                {
                    "name": "DATA1.xml",
                    "size": len(xes_bytes),
                    "computed_md5": digest,
                    "download_url": f"{base}/files/DATA1.xml",
                },
            ],
        }
    ).encode("utf-8")


def _serve_m1(server: _FakeFigshare, xes_bytes: bytes) -> None:
    server.routes[f"/v2/articles/{BPIC2015_DATASETS[0].article_id}"] = (
        200,
        _article_body(server, xes_bytes),
        "application/json",
    )
    server.routes["/files/BPIC15_1.xes"] = (200, xes_bytes, "application/xml")


def _serve_fallback_zip(server: _FakeFigshare, entry_name: str, entry_bytes: bytes) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(entry_name, entry_bytes)
    server.routes["/fallback.zip"] = (200, buffer.getvalue(), "application/zip")


def test_cache_khop_thi_khong_tai(figshare_server, tmp_path):
    _serve_m1(figshare_server, FAKE_XES)
    (tmp_path / "BPIC15_1.xes").write_bytes(FAKE_XES)
    result = fetch(
        "m1", tmp_path, None, api_base=_api_base(figshare_server), retry_delay_seconds=0
    )
    assert result.source == "cache"
    assert result.path.read_bytes() == FAKE_XES
    assert result.md5 == hashlib.md5(FAKE_XES).hexdigest()
    assert figshare_server.hits.get("/files/BPIC15_1.xes", 0) == 0


def test_cache_hong_md5_thi_xoa_va_tai_lai(figshare_server, tmp_path):
    _serve_m1(figshare_server, FAKE_XES)
    (tmp_path / "BPIC15_1.xes").write_bytes(WRONG_XES)
    result = fetch(
        "m1", tmp_path, None, api_base=_api_base(figshare_server), retry_delay_seconds=0
    )
    assert result.source == "chinh-thuc"
    assert result.path.read_bytes() == FAKE_XES
    assert result.md5 == hashlib.md5(FAKE_XES).hexdigest()


def test_chinh_thuc_hong_thi_sang_du_phong(figshare_server, tmp_path):
    _serve_m1(figshare_server, FAKE_XES)
    figshare_server.routes["/files/BPIC15_1.xes"] = (
        500,
        b"loi may chu",
        "text/plain",
    )
    _serve_fallback_zip(figshare_server, "4tu/BPIC15_1.xes", FAKE_XES)
    result = fetch(
        "m1",
        tmp_path,
        _fallback_url(figshare_server),
        api_base=_api_base(figshare_server),
        retry_delay_seconds=0,
    )
    assert result.source == "du-phong"
    assert result.path.read_bytes() == FAKE_XES
    assert result.md5 == hashlib.md5(FAKE_XES).hexdigest()
    assert figshare_server.hits["/files/BPIC15_1.xes"] == 3
    assert figshare_server.hits["/fallback.zip"] == 1


def test_md5_chinh_thuc_sai_thi_thoat_1_va_khong_de_tep(figshare_server, tmp_path):
    _serve_m1(figshare_server, FAKE_XES)
    figshare_server.routes["/files/BPIC15_1.xes"] = (200, WRONG_XES, "application/xml")
    with pytest.raises(FetchError) as exc_info:
        fetch(
            "m1",
            tmp_path,
            None,
            api_base=_api_base(figshare_server),
            retry_delay_seconds=0,
        )
    assert "chinh-thuc" in str(exc_info.value)
    assert not (tmp_path / "BPIC15_1.xes").exists()
    assert list(tmp_path.iterdir()) == []


def test_md5_du_phong_sai_thi_thoat_1_va_khong_de_tep(figshare_server, tmp_path):
    _serve_m1(figshare_server, FAKE_XES)
    figshare_server.routes["/files/BPIC15_1.xes"] = (
        500,
        b"loi may chu",
        "text/plain",
    )
    _serve_fallback_zip(figshare_server, "4tu/BPIC15_1.xes", WRONG_XES)
    with pytest.raises(FetchError) as exc_info:
        fetch(
            "m1",
            tmp_path,
            _fallback_url(figshare_server),
            api_base=_api_base(figshare_server),
            retry_delay_seconds=0,
        )
    assert "dự phòng" in str(exc_info.value)
    assert not (tmp_path / "BPIC15_1.xes").exists()
    assert list(tmp_path.iterdir()) == []


def test_zip_du_phong_thieu_entry_thi_thoat_1(figshare_server, tmp_path):
    _serve_m1(figshare_server, FAKE_XES)
    figshare_server.routes["/files/BPIC15_1.xes"] = (
        500,
        b"loi may chu",
        "text/plain",
    )
    _serve_fallback_zip(figshare_server, "4tu/khac.xes", FAKE_XES)
    with pytest.raises(FetchError) as exc_info:
        fetch(
            "m1",
            tmp_path,
            _fallback_url(figshare_server),
            api_base=_api_base(figshare_server),
            retry_delay_seconds=0,
        )
    assert "dự phòng" in str(exc_info.value)
    assert not (tmp_path / "BPIC15_1.xes").exists()


def test_thieu_ca_hai_nguon_thi_thoat_1_phan_biet_loi(figshare_server, tmp_path, capsys):
    _serve_m1(figshare_server, FAKE_XES)
    figshare_server.routes["/files/BPIC15_1.xes"] = (
        500,
        b"loi may chu",
        "text/plain",
    )
    with pytest.raises(FetchError) as exc_info:
        fetch(
            "m1",
            tmp_path,
            None,
            api_base=_api_base(figshare_server),
            retry_delay_seconds=0,
        )
    errors = exc_info.value.errors
    assert any(error.startswith("chinh-thuc") for error in errors)
    assert not (tmp_path / "BPIC15_1.xes").exists()
    captured = capsys.readouterr()
    assert "không có URL dự phòng" in captured.err


def test_dataset_la_thi_bao_loi(tmp_path):
    with pytest.raises(ValueError, match="không có trong registry"):
        fetch("m9", tmp_path, None, retry_delay_seconds=0)


def test_main_tra_0_khi_fetch_thanh_cong(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        "tools.ci_fetch_bpic2015.fetch",
        lambda *args, **kwargs: FetchResult(
            source="cache", path=tmp_path / "BPIC15_1.xes", md5="abc"
        ),
    )
    assert main(["--dataset", "m1", "--cache-dir", str(tmp_path)]) == 0
    assert "cache" in capsys.readouterr().out


def test_main_tra_1_khi_fetch_that_bai(monkeypatch, tmp_path, capsys):
    def _fail(*args: object, **kwargs: object) -> Never:
        raise FetchError(["chinh-thuc lần 1: lỗi", "dự phòng: lỗi"])

    monkeypatch.setattr("tools.ci_fetch_bpic2015.fetch", _fail)
    assert main(["--dataset", "m1", "--cache-dir", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert "chinh-thuc lần 1" in captured.err
    assert "dự phòng" in captured.err


def test_main_uu_tien_tham_so_hon_bien_moi_truong(monkeypatch, tmp_path):
    seen: dict[str, object] = {}

    def _capture(*args: object, **kwargs: object) -> FetchResult:
        seen["fallback_url"] = kwargs.get("fallback_url")
        return FetchResult(source="cache", path=tmp_path / "BPIC15_1.xes", md5="abc")

    monkeypatch.setattr("tools.ci_fetch_bpic2015.fetch", _capture)
    monkeypatch.setenv(ENV_FALLBACK_URL, "https://example.invalid/env.zip")
    assert (
        main(
            [
                "--dataset",
                "m1",
                "--cache-dir",
                str(tmp_path),
                "--fallback-url",
                "https://example.invalid/tham-so.zip",
            ]
        )
        == 0
    )
    assert seen["fallback_url"] == "https://example.invalid/tham-so.zip"


def test_main_lay_url_du_phong_tu_bien_moi_truong(monkeypatch, tmp_path):
    seen: dict[str, object] = {}

    def _capture(*args: object, **kwargs: object) -> FetchResult:
        seen["fallback_url"] = kwargs.get("fallback_url")
        return FetchResult(source="cache", path=tmp_path / "BPIC15_1.xes", md5="abc")

    monkeypatch.setattr("tools.ci_fetch_bpic2015.fetch", _capture)
    monkeypatch.setenv(ENV_FALLBACK_URL, "https://example.invalid/env.zip")
    assert main(["--dataset", "m1", "--cache-dir", str(tmp_path)]) == 0
    assert seen["fallback_url"] == "https://example.invalid/env.zip"


def test_main_dataset_la_thi_thoat_2(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        main(["--dataset", "m9", "--cache-dir", str(tmp_path)])
    assert exc_info.value.code == 2
