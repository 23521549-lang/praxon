"""Test âm cho cổng dữ liệu bên thứ ba."""

from __future__ import annotations

import pytest
from tools.check_thirdparty_data import offending, tracked_files


@pytest.mark.parametrize(
    "path",
    ["data/bpic2015_1.xes", "docs/bang.csv", "log.gz", "packages/core/src/x.csv"],
)
def test_bat_du_lieu_trong_kho(path):
    assert offending([path]) == [path]


@pytest.mark.parametrize("path", ["tests/fixtures/log_nho.xes", "tests/fixtures/sub/bang.csv"])
def test_cho_phep_fixture_cua_test(path):
    assert offending([path]) == []


def test_khong_bat_tep_khac():
    assert offending(["README.md", "pyproject.toml", "CLAUDE.md"]) == []


def test_kho_that_hien_dang_sach():
    assert offending(tracked_files()) == []
