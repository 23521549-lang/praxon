"""Test âm cho phép thử ranh giới.

Dùng chính interpreter phát triển làm ca âm: ở đây `praxon_platform` **có** cài,
nên cổng phải báo vi phạm. Nếu nó im lặng thì cổng không kiểm gì. Cách này
không phải dựng venv nên chạy nhanh, mà vẫn chứng minh được nửa quan trọng.
"""

from __future__ import annotations

import sys
from pathlib import Path

from tools.check_core_standalone import problems_in


def test_bat_duoc_platform_co_mat():
    found = problems_in(Path(sys.executable))
    assert any("praxon_platform có mặt" in line for line in found)


def test_khong_bao_nham_ve_core():
    # core import được ở môi trường phát triển, nên không được có dòng nào về nó.
    found = problems_in(Path(sys.executable))
    assert not any("praxon_core không import được" in line for line in found)
