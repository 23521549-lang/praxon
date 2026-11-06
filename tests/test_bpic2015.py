"""Bộ tải BPIC 2015: tải qua API figshare, kiểm md5, cache ngoài kho."""

from __future__ import annotations

import hashlib
import http.server
import json
import threading
from typing import cast

import pytest

from praxon_core.datasets import bpic2015
from praxon_core.datasets.bpic2015 import (
    BPIC2015_DATASETS,
    DownloadError,
    download_all_bpic2015,
    download_bpic2015,
    main,
)

FAKE_XES = b'<log><trace><string key="concept:name" value="c1"/></trace></log>'


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


def _article_body(
    server: _FakeFigshare,
    article_id: int,
    xes_bytes: bytes,
    *,
    md5: str | None = None,
    with_xes: bool = True,
) -> bytes:
    base = f"http://127.0.0.1:{server.server_address[1]}"
    digest = md5 or hashlib.md5(xes_bytes).hexdigest()
    files = []
    if with_xes:
        files.append(
            {
                "name": "BPIC15_1.xes",
                "size": len(xes_bytes),
                "computed_md5": digest,
                "download_url": f"{base}/files/BPIC15_1.xes",
            }
        )
    files.append(
        {
            "name": "DATA1.xml",
            "size": len(xes_bytes),
            "computed_md5": digest,
            "download_url": f"{base}/files/DATA1.xml",
        }
    )
    return json.dumps({"id": article_id, "files": files}).encode("utf-8")


def _serve_m1(
    server: _FakeFigshare,
    xes_bytes: bytes,
    *,
    md5: str | None = None,
    with_xes: bool = True,
) -> None:
    server.routes[f"/v2/articles/{BPIC2015_DATASETS[0].article_id}"] = (
        200,
        _article_body(
            server,
            BPIC2015_DATASETS[0].article_id,
            xes_bytes,
            md5=md5,
            with_xes=with_xes,
        ),
        "application/json",
    )
    server.routes["/files/BPIC15_1.xes"] = (200, xes_bytes, "application/xml")
    server.routes["/files/DATA1.xml"] = (200, xes_bytes, "application/xml")


def test_registry_nam_do_thi():
    assert [dataset.slug for dataset in BPIC2015_DATASETS] == [
        "m1",
        "m2",
        "m3",
        "m4",
        "m5",
    ]
    assert [dataset.article_id for dataset in BPIC2015_DATASETS] == [
        12709154,
        12697349,
        12718370,
        12697898,
        12713285,
    ]
    assert [dataset.expected_cases for dataset in BPIC2015_DATASETS] == [
        1199,
        832,
        1409,
        1053,
        1156,
    ]
    assert all(
        dataset.article_url.startswith("https://data.4tu.nl/articles/dataset/")
        for dataset in BPIC2015_DATASETS
    )


def test_tai_duoc_va_kiem_md5(figshare_server, tmp_path):
    _serve_m1(figshare_server, FAKE_XES)
    log = download_bpic2015(BPIC2015_DATASETS[0], tmp_path, api_base=_api_base(figshare_server))
    assert log.path.read_bytes() == FAKE_XES
    assert log.md5 == hashlib.md5(FAKE_XES).hexdigest()
    assert log.sha256 == hashlib.sha256(FAKE_XES).hexdigest()
    assert log.size_bytes == len(FAKE_XES)
    assert log.from_cache is False
    manifest = json.loads((tmp_path / "BPIC15_1.manifest.json").read_text(encoding="utf-8"))
    assert manifest["slug"] == "m1"
    assert manifest["md5"] == log.md5
    assert manifest["sha256"] == log.sha256
    assert manifest["doi"] == BPIC2015_DATASETS[0].doi


def test_khong_tai_lai_khi_cache_khop(figshare_server, tmp_path):
    _serve_m1(figshare_server, FAKE_XES)
    first = download_bpic2015(
        BPIC2015_DATASETS[0], tmp_path, api_base=_api_base(figshare_server)
    )
    second = download_bpic2015(
        BPIC2015_DATASETS[0], tmp_path, api_base=_api_base(figshare_server)
    )
    assert first.md5 == second.md5
    assert second.from_cache is True
    assert figshare_server.hits["/files/BPIC15_1.xes"] == 1


def test_cache_hong_md5_thi_tai_lai(figshare_server, tmp_path):
    _serve_m1(figshare_server, FAKE_XES)
    (tmp_path / "BPIC15_1.xes").write_bytes(b"du lieu cu hong")
    log = download_bpic2015(BPIC2015_DATASETS[0], tmp_path, api_base=_api_base(figshare_server))
    assert log.path.read_bytes() == FAKE_XES
    assert log.from_cache is False


def test_md5_sai_thi_bao_loi_va_khong_de_file(figshare_server, tmp_path):
    _serve_m1(figshare_server, b"noi dung khac", md5="0" * 32)
    with pytest.raises(DownloadError):
        download_bpic2015(BPIC2015_DATASETS[0], tmp_path, api_base=_api_base(figshare_server))
    assert not (tmp_path / "BPIC15_1.xes").exists()
    assert not (tmp_path / "BPIC15_1.xes.tmp").exists()


def test_khong_co_tep_xes_thi_bao_loi(figshare_server, tmp_path):
    _serve_m1(figshare_server, FAKE_XES, with_xes=False)
    with pytest.raises(DownloadError):
        download_bpic2015(BPIC2015_DATASETS[0], tmp_path, api_base=_api_base(figshare_server))


def test_api_loi_http_thi_bao_loi(figshare_server, tmp_path):
    figshare_server.routes[f"/v2/articles/{BPIC2015_DATASETS[0].article_id}"] = (
        500,
        b"loi may chu",
        "text/plain",
    )
    with pytest.raises(DownloadError):
        download_bpic2015(BPIC2015_DATASETS[0], tmp_path, api_base=_api_base(figshare_server))


def test_tai_ca_nam_do_thi(figshare_server, tmp_path):
    base = f"http://127.0.0.1:{figshare_server.server_address[1]}"
    for dataset in BPIC2015_DATASETS:
        body = json.dumps(
            {
                "id": dataset.article_id,
                "files": [
                    {
                        "name": dataset.xes_filename,
                        "size": len(FAKE_XES),
                        "computed_md5": hashlib.md5(FAKE_XES).hexdigest(),
                        "download_url": f"{base}/files/{dataset.xes_filename}",
                    }
                ],
            }
        ).encode("utf-8")
        figshare_server.routes[f"/v2/articles/{dataset.article_id}"] = (
            200,
            body,
            "application/json",
        )
        figshare_server.routes[f"/files/{dataset.xes_filename}"] = (
            200,
            FAKE_XES,
            "application/xml",
        )
    logs = download_all_bpic2015(tmp_path, api_base=_api_base(figshare_server))
    assert [log.dataset.slug for log in logs] == ["m1", "m2", "m3", "m4", "m5"]
    assert all(log.path.read_bytes() == FAKE_XES for log in logs)


def test_main_in_bang_va_tra_0(figshare_server, tmp_path, capsys, monkeypatch):
    _serve_m1(figshare_server, FAKE_XES)
    monkeypatch.setattr(bpic2015, "FIGSHARE_API_URL", _api_base(figshare_server))
    assert main(["--dataset", "m1", "--cache-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "m1: BPIC15_1.xes" in out
    assert hashlib.md5(FAKE_XES).hexdigest() in out


def test_main_bao_loi_khi_api_sap(figshare_server, tmp_path, monkeypatch):
    figshare_server.routes[f"/v2/articles/{BPIC2015_DATASETS[0].article_id}"] = (
        500,
        b"loi may chu",
        "text/plain",
    )
    monkeypatch.setattr(bpic2015, "FIGSHARE_API_URL", _api_base(figshare_server))
    assert main(["--dataset", "m1", "--cache-dir", str(tmp_path)]) == 1
    assert not (tmp_path / "BPIC15_1.xes").exists()
