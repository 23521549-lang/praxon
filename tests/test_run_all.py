"""Test đơn vị cho bộ điều phối một lệnh (task 13.1).

Không chạm DB, không gọi model, không cần Docker: chỉ kiểm logic thuần
(chuẩn hóa hàng, so báo cáo, driver giả, băm nửa BPIC, đọc seed khóa),
proxy chèn khóa (server giả local) và wrapper `.env`.

Phép thử máy trống full (job CI clean-machine chạy thật) chưa chạy ở
task này — chờ 11.2 đo giờ (H1) + 12.2 ghi JSON (R5); xem đề xuất 13.1.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar, cast

import pytest
from tools.llm_auth_proxy import make_handler
from tools.run_phase1 import (
    _container_path,
    _lock_path_for,
    ensure_env_password,
)

from praxon_core.datasets.bpic2015 import DEFAULT_CACHE_DIR
from praxon_core.eval.run_all import (
    _bpic_half_hash,
    _mock_bpic_driver,
    _mock_bpic_rows,
    _read_lock_seed,
    compare_reports,
    normalize_row,
)

#: Nửa BPIC của data_hash (12.2 A.1, đo bằng lệnh chia — phải khớp đúng).
BPIC_HALF = "0edb706dcf2afb637a0c7b57ee9d284fc8958ee50b9594a05e3365ec5a805b92"

METRIC_NAMES = ("precision", "recall", "violation_rate", "negative_transfer")


def _metric(value: float) -> dict[str, float]:
    """Một chỉ số kèm khoảng (lower <= value <= upper)."""
    return {"value": value, "lower": value - 0.05, "upper": value + 0.05}


def _metrics_dict(value: float = 0.7) -> dict[str, dict[str, float]]:
    """Bốn chỉ số mặc định (cùng giá trị) để dựng hàng test."""
    return {name: _metric(value) for name in METRIC_NAMES}


def _nested_row(
    tenant: str = "m1",
    condition: str = "declare_only",
    source: str = "bpic2015-test-split",
    value: float = 0.7,
    metrics: dict[str, dict[str, float]] | None = None,
) -> dict[str, object]:
    """Một hàng dạng lồng `metrics` (dạng `TenantConditionRow` / 12.2 A.4).

    `metrics` cho phép dựng hàng có chỉ số lệch/khuyết để test ca lỗi mà
    không phải mutate `dict[str, object]` (mypy không cho index vào `object`).
    """
    return {
        "tenant_id": tenant,
        "condition": condition,
        "source": source,
        "n_train": 719,
        "n_measure": 240,
        "n_reference": 1200,
        "n_rules": 42,
        "metrics": metrics if metrics is not None else _metrics_dict(value),
    }


def _flat_row(
    tenant: str = "m1",
    condition: str = "declare_only",
    source: str = "bpic2015-test-split",
    value: float = 0.7,
) -> dict[str, object]:
    """Một hàng dạng trải phẳng (dạng ví dụ trong đề xuất 13.1 A.4)."""
    row: dict[str, object] = {
        "tenant_id": tenant,
        "condition": condition,
        "source": source,
        "n_train": 719,
        "n_measure": 240,
        "n_reference": 1200,
        "n_rules": 42,
    }
    for name in METRIC_NAMES:
        row[name] = _metric(value)
    return row


def _meta(**overrides: object) -> dict[str, object]:
    """Sáu trường metadata của một lần chạy + `cache_intact`."""
    meta: dict[str, object] = {
        "code_commit": "abc123",
        "config_hash": "cfg123",
        "data_hash": "6564b2e2ef6cbc7e18606ac74940931d59c5adb517572d9f943578fbfcf58783",
        "seed": 0,
        "model_id": "Qwen/Qwen3-8B-GGUF",
        "model_revision": "7c41481f57cb95916b40956ab2f0b139b296d974",
        "cache_intact": True,
    }
    meta.update(overrides)
    return meta


def _report(rows: list[dict[str, object]], **meta_overrides: object) -> dict[str, object]:
    """Một báo cáo JSON: metadata ở đỉnh + danh sách hàng."""
    report = _meta(**meta_overrides)
    report["rows"] = rows
    return report


# ---------------------------------------------------------------- normalize_row


def _metrics_of(row: dict[str, object]) -> dict[str, dict[str, float]]:
    """Lấy `metrics` của hàng đã chuẩn hóa (cast — normalize_row đã kiểm schema)."""
    return cast(dict[str, dict[str, float]], row["metrics"])


def test_normalize_row_chap_dang_long_metrics():
    row = normalize_row(_nested_row())
    assert row is not None
    assert _metrics_of(row)["precision"]["value"] == 0.7
    assert _metrics_of(row)["recall"]["lower"] == pytest.approx(0.65)
    assert row["n_train"] == 719


def test_normalize_row_chap_dang_trai_phang():
    row = normalize_row(_flat_row())
    assert row is not None
    assert _metrics_of(row)["precision"]["value"] == 0.7
    assert _metrics_of(row)["violation_rate"]["upper"] == 0.75


def test_normalize_row_hai_dang_cho_cung_ket_qua():
    assert normalize_row(_nested_row()) == normalize_row(_flat_row())


def test_normalize_row_thieu_truong_thi_none():
    row = _nested_row()
    del row["n_train"]
    assert normalize_row(row) is None


def test_normalize_row_sai_kieu_so_thi_none():
    row = _nested_row()
    row["n_train"] = "719"
    assert normalize_row(row) is None


def test_normalize_row_khong_phai_dict_thi_none():
    assert normalize_row([_nested_row()]) is None
    assert normalize_row("m1") is None


def test_normalize_row_khoang_vo_nghia_thi_none():
    bad_precision = _metrics_dict()
    bad_precision["precision"] = {"value": 0.7, "lower": 0.8, "upper": 0.75}
    assert normalize_row(_nested_row(metrics=bad_precision)) is None
    bad_recall = _metrics_dict()
    bad_recall["recall"] = {"value": 0.9, "lower": 0.8, "upper": 0.85}
    assert normalize_row(_nested_row(metrics=bad_recall)) is None


def test_normalize_row_thieu_mot_chi_so_thi_none():
    metrics = _metrics_dict()
    del metrics["recall"]
    assert normalize_row(_nested_row(metrics=metrics)) is None


def test_normalize_row_chi_so_khong_phai_dict_thi_none():
    row = _nested_row()
    row["metrics"] = {
        "precision": 0.7,
        "recall": _metric(0.7),
        "violation_rate": _metric(0.7),
        "negative_transfer": _metric(0.7),
    }
    assert normalize_row(row) is None


def test_normalize_row_gia_tri_khong_phai_so_thi_none():
    row = _nested_row()
    row["metrics"] = {
        "precision": {"value": "0.7", "lower": 0.65, "upper": 0.75},
        "recall": _metric(0.7),
        "violation_rate": _metric(0.7),
        "negative_transfer": _metric(0.7),
    }
    assert normalize_row(row) is None


# ---------------------------------------------------------------- compare_reports


def test_compare_reports_trung_nhau_thi_rong():
    rows = [_nested_row(), _nested_row(tenant="m2", condition="isolation")]
    assert compare_reports(_report(rows), _report(rows)) == []


def test_compare_reports_dang_phang_va_dang_long_trung_nhau():
    rows = [_nested_row(), _nested_row(tenant="m2", condition="isolation")]
    flat = [_flat_row(), _flat_row(tenant="m2", condition="isolation")]
    assert compare_reports(_report(rows), _report(flat)) == []


def test_compare_reports_mot_gia_tri_chi_so_lech():
    metrics = _metrics_dict(0.7)
    metrics["precision"] = {"value": 0.71, "lower": 0.7 - 0.05, "upper": 0.7 + 0.05}
    run = _report([_nested_row(value=0.7)])
    ref = _report([_nested_row(metrics=metrics)])
    gaps = compare_reports(run, ref)
    assert len(gaps) == 1
    assert "precision.value" in gaps[0]


def test_compare_reports_mot_can_khoang_lech():
    run_row = _nested_row()
    ref_metrics = _metrics_dict()
    ref_metrics["recall"] = {"value": 0.7, "lower": 0.60, "upper": 0.75}
    ref_row = _nested_row(metrics=ref_metrics)
    gaps = compare_reports(_report([run_row]), _report([ref_row]))
    assert len(gaps) == 1
    assert "recall.lower" in gaps[0]


def test_compare_reports_code_commit_lech():
    rows = [_nested_row()]
    gaps = compare_reports(_report(rows, code_commit="aaa"), _report(rows, code_commit="bbb"))
    assert gaps == ["code_commit"]


def test_compare_reports_seed_lech():
    rows = [_nested_row()]
    gaps = compare_reports(_report(rows, seed=0), _report(rows, seed=1))
    assert gaps == ["seed"]


def test_compare_reports_data_hash_lech():
    rows = [_nested_row()]
    gaps = compare_reports(_report(rows, data_hash="aaa"), _report(rows, data_hash="bbb"))
    assert gaps == ["data_hash"]


def test_compare_reports_hang_thua_va_hang_thieu():
    run = _report([_nested_row(), _nested_row(tenant="m2")])
    ref = _report([_nested_row(), _nested_row(tenant="m3")])
    gaps = compare_reports(run, ref)
    assert any("hàng thừa" in gap and "m2" in gap for gap in gaps)
    assert any("hàng thiếu" in gap and "m3" in gap for gap in gaps)


def test_compare_reports_hang_bo_chuan_khong_so():
    # Hàng bộ chuẩn (source khác) trong lần chạy không có tham chiếu: bỏ qua,
    # do phép so run1-vs-run2 của job CI kiểm — không báo "hàng thừa".
    run = _report([_nested_row(), _nested_row(source="generator", tenant="synthetic-1")])
    ref = _report([_nested_row()])
    assert compare_reports(run, ref) == []


def test_compare_reports_tham_chieu_thieu_metadata():
    rows = [_nested_row()]
    ref = _report(rows)
    del ref["code_commit"]
    gaps = compare_reports(_report(rows), ref)
    assert any("thiếu metadata" in gap for gap in gaps)


def test_compare_reports_thieu_danh_sach_hang():
    ref = _report([_nested_row()])
    run = _meta()
    gaps = compare_reports(run, ref)
    assert any("thiếu danh sách hàng" in gap for gap in gaps)


def test_compare_reports_hang_sai_schema():
    bad = _nested_row()
    del bad["n_rules"]
    gaps = compare_reports(_report([bad]), _report([_nested_row()]))
    assert any("sai schema" in gap for gap in gaps)


# ---------------------------------------------------------------- mock driver


def test_mock_bpic_rows_du_35_hang_7_dieu_kien_5_do_thi():
    rows = _mock_bpic_rows()
    assert len(rows) == 35
    tenants = sorted({str(row["tenant_id"]) for row in rows})
    assert tenants == ["m1", "m2", "m3", "m4", "m5"]
    conditions = sorted({str(row["condition"]) for row in rows})
    assert len(conditions) == 7
    assert all(row["source"] == "bpic2015-test-split" for row in rows)


def test_mock_bpic_rows_xac_dinh_chay_lai_giong_nhau():
    assert _mock_bpic_rows() == _mock_bpic_rows()


def test_mock_bpic_rows_so_case_la_so_that_cua_12_2():
    rows = _mock_bpic_rows()
    counts = {str(row["tenant_id"]): (row["n_train"], row["n_measure"]) for row in rows}
    assert counts["m1"] == (719, 240)
    assert counts["m2"] == (499, 167)
    assert counts["m3"] == (846, 282)
    assert counts["m4"] == (631, 211)
    assert counts["m5"] == (694, 232)


def test_mock_bpic_rows_chi_so_trong_khoang_va_khoang_hop_le():
    for row in _mock_bpic_rows():
        normalized = normalize_row(row)
        assert normalized is not None
        metrics = normalized["metrics"]
        assert isinstance(metrics, dict)
        for name in METRIC_NAMES:
            entry = metrics[name]
            assert isinstance(entry, dict)
            value = entry["value"]
            lower = entry["lower"]
            upper = entry["upper"]
            assert isinstance(value, float) and isinstance(lower, float)
            assert isinstance(upper, float)
            assert 0.0 <= lower <= value <= upper <= 1.0


def test_mock_bpic_driver_ghi_json_va_tra_0(tmp_path):
    report_path = tmp_path / "sau" / "bpic-driver-report.json"
    assert _mock_bpic_driver(report_path) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["code_commit"] == "mock"
    assert "MOCK" in str(report["note"])
    assert len(report["rows"]) == 35
    assert all(normalize_row(row) is not None for row in report["rows"])


def test_mock_bpic_driver_chay_lai_giong_nhau(tmp_path):
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    assert _mock_bpic_driver(path_a) == 0
    assert _mock_bpic_driver(path_b) == 0
    assert path_a.read_text(encoding="utf-8") == path_b.read_text(encoding="utf-8")


# ---------------------------------------------------------------- băm nửa BPIC + seed khóa


def test_bpic_half_hash_khop_gia_tri_cua_12_2():
    assert _bpic_half_hash(DEFAULT_CACHE_DIR) == BPIC_HALF


def test_bpic_half_hash_thieu_file_thi_loi(tmp_path):
    with pytest.raises(FileNotFoundError):
        _bpic_half_hash(tmp_path)


def test_read_lock_seed_doc_dung_seed(tmp_path):
    lock = tmp_path / "phan-do.lock.toml"
    lock.write_text('seed = 42\nlocked_config_hash = "abc"\n', encoding="utf-8")
    assert _read_lock_seed(lock) == 42


def test_read_lock_seed_thieu_file_thi_value_error(tmp_path):
    with pytest.raises(ValueError):
        _read_lock_seed(tmp_path / "khong-co.lock.toml")


def test_read_lock_seed_thieu_seed_thi_value_error(tmp_path):
    lock = tmp_path / "phan-do.lock.toml"
    lock.write_text('locked_config_hash = "abc"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        _read_lock_seed(lock)


def test_read_lock_seed_seed_khong_phai_so_thi_value_error(tmp_path):
    lock = tmp_path / "phan-do.lock.toml"
    lock.write_text('seed = "42"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        _read_lock_seed(lock)


# ---------------------------------------------------------------- proxy chèn khóa


class _RecordingUpstream(BaseHTTPRequestHandler):
    """Server mô hình giả: ghi lại header Authorization rồi trả JSON cố định."""

    requests: ClassVar[list[dict[str, str]]] = []
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _handle(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length > 0 else b""
        _RecordingUpstream.requests.append(
            {
                "authorization": self.headers.get("Authorization") or "",
                "body": body.decode("utf-8", "replace"),
            }
        )
        payload = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # Tên phương thức bắt buộc của BaseHTTPRequestHandler (xem proxy).
    do_GET = _handle  # noqa: N815
    do_POST = _handle  # noqa: N815


def _serve(handler: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, int]:
    """Chạy một HTTP server trên cổng tạm (luồng nền), trả (server, cổng)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, int(server.server_address[1])


def _stop(server: ThreadingHTTPServer) -> None:
    server.shutdown()
    server.server_close()


def test_proxy_chen_khoa_that_vao_upstream(capsys):
    api_key = "khoa-mot-lan-13-1"
    _RecordingUpstream.requests.clear()
    upstream, upstream_port = _serve(_RecordingUpstream)
    proxy, proxy_port = _serve(make_handler(f"http://127.0.0.1:{upstream_port}", api_key))
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{proxy_port}/v1/chat/completions",
            data=b'{"model": "qwen"}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            assert response.status == 200
            assert response.read() == b'{"ok": true}'
    finally:
        _stop(proxy)
        _stop(upstream)
    assert len(_RecordingUpstream.requests) == 1
    seen = _RecordingUpstream.requests[0]
    assert seen["authorization"] == f"Bearer {api_key}"
    assert seen["body"] == '{"model": "qwen"}'
    # Khóa không bao giờ xuất hiện trong log của proxy (stderr).
    captured = capsys.readouterr()
    assert api_key not in captured.err


def test_proxy_gui_nguyen_ma_loi_cua_upstream():
    # Upstream trả 401 thì proxy trả nguyên 401 (không biến thành 502).
    class _Unauthorized(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: object) -> None:
            pass

        def do_GET(self) -> None:
            payload = b'{"error": "invalid api key"}'
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    upstream, upstream_port = _serve(_Unauthorized)
    proxy, proxy_port = _serve(make_handler(f"http://127.0.0.1:{upstream_port}", "k"))
    try:
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(f"http://127.0.0.1:{proxy_port}/v1/models", timeout=10)
        assert excinfo.value.code == 401
    finally:
        _stop(proxy)
        _stop(upstream)


def test_proxy_upstream_chet_thi_tra_502():
    # Không có server nào nghe ở cổng upstream: proxy trả 502, không treo.
    proxy, proxy_port = _serve(make_handler("http://127.0.0.1:1", "k"))
    try:
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(f"http://127.0.0.1:{proxy_port}/v1/models", timeout=10)
        assert excinfo.value.code == 502
    finally:
        _stop(proxy)


# ---------------------------------------------------------------- wrapper run_phase1


def test_ensure_env_password_tao_moi_khi_chua_co(tmp_path):
    env_path = tmp_path / ".env"
    password = ensure_env_password(env_path)
    assert len(password) >= 32
    assert env_path.read_text(encoding="utf-8") == f"POSTGRES_PASSWORD={password}\n"
    # Gọi lại: không sinh lại, trả đúng mật khẩu đã có.
    assert ensure_env_password(env_path) == password


def test_ensure_env_password_giu_nguyen_gia_tri_da_co(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("POSTGRES_PASSWORD=mat-khau-cu\nOTHER=x\n", encoding="utf-8")
    assert ensure_env_password(env_path) == "mat-khau-cu"
    assert env_path.read_text(encoding="utf-8") == ("POSTGRES_PASSWORD=mat-khau-cu\nOTHER=x\n")


def test_ensure_env_password_thay_dong_rong_tai_cho_giu_dong_khac(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("OTHER=x\nPOSTGRES_PASSWORD=\nTAIL=y\n", encoding="utf-8")
    password = ensure_env_password(env_path)
    lines = env_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "OTHER=x"
    assert lines[1] == f"POSTGRES_PASSWORD={password}"
    assert lines[2] == "TAIL=y"


def test_ensure_env_password_them_vao_cuoi_khi_thieu_key(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("OTHER=x\n", encoding="utf-8")
    password = ensure_env_password(env_path)
    assert env_path.read_text(encoding="utf-8") == (f"OTHER=x\nPOSTGRES_PASSWORD={password}\n")


def test_container_path_trong_repo_thanh_duong_dan_app(tmp_path):
    root = tmp_path
    assert _container_path(root, root / "configs" / "phan-do.toml") == (
        "/app/configs/phan-do.toml"
    )
    assert _container_path(root, Path("configs/phan-do.toml")) == ("/app/configs/phan-do.toml")


def test_container_path_ngoai_repo_thi_value_error(tmp_path):
    with pytest.raises(ValueError):
        _container_path(tmp_path / "repo", Path("/etc/phan-do.toml"))


def test_lock_path_for_doi_stem():
    assert _lock_path_for(Path("configs/phan-do.toml")) == Path("configs/phan-do.lock.toml")
