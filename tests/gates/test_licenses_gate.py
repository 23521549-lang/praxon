"""Test âm cho cổng giấy phép phụ thuộc."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from tools.check_licenses import licenses_in, offending


@pytest.mark.parametrize(
    "license_text",
    [
        "GNU Affero General Public License v3",
        "AGPLv3+",
        "GPL-3.0-only",
        "UNKNOWN",
        "gnu general public license",
    ],
)
def test_bat_giay_phep_khong_dung_duoc(license_text):
    assert offending([{"Name": "x", "License": license_text}]) == [("x", license_text)]


@pytest.mark.parametrize("license_text", ["MIT", "Apache Software License", "BSD-3-Clause"])
def test_cho_qua_giay_phep_dung_duoc(license_text):
    assert offending([{"Name": "x", "License": license_text}]) == []


def test_lgpl_cung_bi_bat():
    # Báo nhầm có chủ đích: LGPL khớp từ khóa GPL. Một thư viện LGPL trong sản
    # phẩm phân phối cho khách là việc cần người quyết, không phải việc để một
    # danh sách ngoại lệ âm thầm cho qua.
    assert offending([{"Name": "x", "License": "LGPLv2.1"}]) == [("x", "LGPLv2.1")]


def test_thieu_truong_license_bi_coi_la_khong_khai():
    assert offending([{"Name": "x"}]) == []


def test_pip_licenses_chay_duoc_that():
    # Cổng gọi pip-licenses trần, không qua ống dẫn — nếu nó không chạy được
    # thì phải lộ ra ở đây, không phải xanh giả.
    assert len(licenses_in(Path(sys.executable))) > 0
