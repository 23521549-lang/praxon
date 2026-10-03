"""Test âm cho cổng trùng tên thư viện chuẩn — lý do ở docs/decisions/0003."""

from __future__ import annotations

import pytest
from tools.check_no_stdlib_shadowing import offending, top_level_packages


@pytest.mark.parametrize("name", ["platform", "json", "os", "types"])
def test_bat_ten_trung_thu_vien_chuan(name):
    assert offending([name]) == [name]


def test_cho_qua_ten_rieng():
    assert offending(["praxon_core", "praxon_platform"]) == []


def test_goi_that_hien_dang_sach():
    found = top_level_packages()
    assert set(found) == {"praxon_core", "praxon_platform"}
    assert offending(found) == []
