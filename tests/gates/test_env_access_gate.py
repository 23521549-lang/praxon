"""Test âm cho cổng biến môi trường: nó phải đỏ khi có vi phạm thật."""

from __future__ import annotations

from tools.check_env_access import offending, scan

MODULE_KHAC = "praxon_core/vi_du.py"
MODULE_SETTINGS = "praxon_core/settings.py"


def test_bat_os_environ_ngoai_settings():
    hits = offending("import os\nX = os.environ['A']\n", MODULE_KHAC)
    assert hits and hits[0][1] == "os.environ"


def test_bat_os_getenv_ngoai_settings():
    hits = offending("import os\nX = os.getenv('A')\n", MODULE_KHAC)
    assert hits and hits[0][1] == "os.getenv"


def test_bat_from_os_import():
    hits = offending("from os import getenv\nX = getenv('A')\n", MODULE_KHAC)
    assert hits and "from os import getenv" in hits[0][1]


def test_cho_phep_trong_settings():
    assert offending("import os\nX = os.environ['A']\n", MODULE_SETTINGS) == []


def test_khong_bao_nham_tren_chu_thich_va_chuoi():
    # Đây là lý do cổng dùng phân tích cú pháp chứ không khớp chuỗi: một cổng
    # báo nhầm thì sớm muộn bị tắt.
    source = '# os.environ là đường cấm\nDOC = "dùng os.getenv ở đây là sai"\n'
    assert offending(source, MODULE_KHAC) == []


def test_ma_nguon_that_hien_dang_sach():
    assert scan(("packages/core/src", "packages/platform/src")) == []
