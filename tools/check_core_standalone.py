"""Cổng: phép thử ranh giới — `praxon-core` cài và chạy được một mình.

Spec đặt phép thử này thành điều kiện để ranh giới hai gói là thật, không phải
quy ước: *"chạy trọn thí nghiệm BPIC 2015 chỉ bằng gói core với một tệp cấu
hình và một mô hình chạy cục bộ — chạy được thì ranh giới là thật."*

Ở lát cắt này thí nghiệm chưa có, nên cổng kiểm phần kiểm được ngay: trong môi
trường chỉ có core, `praxon_core` phải import được và `praxon_platform` phải
không có. Khi thí nghiệm có thật thì thêm một bước chạy nó ở cùng môi trường.

Đây là thứ import-linter một mình không chứng minh được: import-linter đọc mã
nguồn, cổng này đọc **gói đã cài**. Nếu `praxon-core` vô tình khai
`praxon-platform` là phụ thuộc thì import-linter vẫn xanh, còn cổng này đỏ.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.core_env import core_only_env


def problems_in(python: Path) -> list[str]:
    """Trả về danh sách lý do thất bại trong một môi trường, rỗng nếu đạt."""
    found: list[str] = []
    core = subprocess.run(
        [str(python), "-c", "import praxon_core"],
        capture_output=True,
        text=True,
        check=False,
    )
    if core.returncode != 0:
        found.append(f"praxon_core không import được: {core.stderr.strip()[-400:]}")

    platform_pkg = subprocess.run(
        [str(python), "-c", "import praxon_platform"],
        capture_output=True,
        text=True,
        check=False,
    )
    if platform_pkg.returncode == 0:
        found.append(
            "praxon_platform có mặt trong môi trường chỉ cài praxon-core — core "
            "đang kéo theo platform, chiều phụ thuộc đã bị mở ngược"
        )
    return found


def main() -> int:
    """Chạy cổng, trả mã thoát cho dòng lệnh."""
    with core_only_env() as python:
        found = problems_in(python)
    if found:
        print("Phép thử ranh giới thất bại:", file=sys.stderr)
        for line in found:
            print(f"  {line}", file=sys.stderr)
        return 1
    print("Phép thử ranh giới đạt: praxon-core cài và chạy một mình, không kéo platform.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
