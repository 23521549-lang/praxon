"""Chuẩn hoá: tên (casefold + trim + gộp whitespace) và timestamp về UTC."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from praxon_core.ingest.normalize import normalize_name, normalize_timestamp


def test_approve_thuong_va_hoa_la_mot():
    # Đúng test trong task 2.4 của plan.
    assert normalize_name("Approve ") == normalize_name("APPROVE")


def test_trim_va_gop_khoang_trang():
    assert normalize_name("  ghi\tsổ\nkế  ") == "ghi sổ kế"


def test_casefold_manh_hon_lower():
    # 'ß' đã là chữ thường nên lower() để nguyên; casefold() ra 'ss'.
    # Dùng lower() sẽ để lọt hai tên thực ra là một.
    assert normalize_name("straße") == normalize_name("STRASSE")
    assert "ß".lower() != "ß".casefold()


def test_timestamp_co_offset_ve_utc():
    assert normalize_timestamp("2015-06-01T10:00:00+07:00") == datetime(
        2015, 6, 1, 3, 0, tzinfo=UTC
    )


def test_timestamp_hau_to_z():
    assert normalize_timestamp("2015-06-01T03:00:00Z") == datetime(2015, 6, 1, 3, 0, tzinfo=UTC)


def test_timestamp_naive_bi_tu_choi():
    # Giá trị naive là dữ liệu mơ hồ — ngầm hiểu là UTC thì sai lệch số liệu
    # mà không để lại vết.
    with pytest.raises(ValueError):
        normalize_timestamp("2015-06-01T10:00:00")


def test_timestamp_sai_dinh_dang_bi_tu_choi():
    with pytest.raises(ValueError):
        normalize_timestamp("ngay mai")


def test_nhan_truc_tiep_object_datetime():
    dt = datetime(2015, 6, 1, 10, 0, tzinfo=UTC)
    assert normalize_timestamp(dt) == dt
    with pytest.raises(ValueError):
        normalize_timestamp(datetime(2015, 6, 1, 10, 0))
