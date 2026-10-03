"""Test âm cho cổng phiên bản công cụ."""

from __future__ import annotations

from tools.check_tool_versions import REQUIREMENTS, mismatches, pinned


def test_doc_duoc_ban_ghim():
    found = pinned("# chú thích\n\nruff==0.16.10\nmypy==2.4.0\n")
    assert found == {"ruff": "0.16.10", "mypy": "2.4.0"}


def test_bo_qua_dong_khong_ghim():
    assert pinned("ruff>=0.1\n-e .\n") == {}


def test_bat_phien_ban_lech():
    assert mismatches({"ruff": "0.0.1"}) == ["ruff: ghim 0.0.1, đang cài 0.16.10"]


def test_bat_goi_chua_cai():
    assert mismatches({"khong-ton-tai-goi-nay": "1.0"}) == [
        "khong-ton-tai-goi-nay: ghim 1.0, chưa cài"
    ]


def test_moi_truong_that_khop_ban_ghim():
    assert mismatches(pinned(REQUIREMENTS.read_text(encoding="utf-8"))) == []
