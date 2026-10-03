"""Cổng: `praxon-core` không phụ thuộc thư viện AGPL, GPL hay không khai giấy phép.

Chấm trong một môi trường **chỉ có core**, không chấm môi trường phát triển.
Phép thử ngày 3/10/2026 cho thấy vì sao: chạy pip-licenses trên môi trường phát
triển bắt được PyGObject, python-apt, launchpadlib và ba gói LGPL khác — toàn
bộ là gói của hệ điều hành, không phải phụ thuộc của dự án. Một cổng báo nhầm
sáu dòng ngay lần chạy đầu thì sẽ bị tắt, không bị sửa. Câu cần trả lời là
*core một mình kéo theo những gì*, nên phải hỏi trên môi trường đó.

Gọi pip-licenses **trần**, không qua ống dẫn: một ống dẫn trả mã thoát của lệnh
cuối, nên `pip-licenses | grep` nuốt mất lỗi của pip-licenses và cổng xanh
trong khi nó chưa chạy được.

Khớp một phần theo từ khóa, vì mỗi gói khai một kiểu: "GNU Affero General
Public License v3", "AGPLv3+", "GPL-3.0-only" đều phải bắt được. Hệ quả cố ý:
"LGPL" cũng khớp từ khóa GPL. Đó là báo nhầm có chủ đích — LGPL trong sản phẩm
phân phối cho khách là việc cần người quyết, không phải việc để một danh sách
ngoại lệ âm thầm cho qua. Nên cổng này không có đường ngoại lệ.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

from tools.core_env import core_only_env

# Phải có cả dạng viết tắt và dạng viết đủ chữ. Test âm ngày 3/10/2026 chứng
# minh vì sao: "GNU Affero General Public License v3" KHÔNG chứa chuỗi "gpl",
# nên một cổng chỉ khớp viết tắt sẽ cho qua đúng giấy phép nguy hiểm nhất.
# Spec viết "khớp từ khóa AGPL, GPL và UNKNOWN"; dòng dưới rộng hơn đúng một
# từ khóa, và chỉ theo chiều chặt hơn.
FORBIDDEN_KEYWORDS = ("agpl", "gpl", "general public license", "unknown")


def offending(rows: Iterable[dict[str, str]]) -> list[tuple[str, str]]:
    """Trả về các gói mang giấy phép không dùng được, dạng (tên, giấy phép)."""
    problems: list[tuple[str, str]] = []
    for row in rows:
        license_text = (row.get("License") or "").lower()
        if any(keyword in license_text for keyword in FORBIDDEN_KEYWORDS):
            problems.append((row.get("Name", "?"), row.get("License", "?")))
    return sorted(problems)


def licenses_in(python: Path) -> list[dict[str, str]]:
    """Đọc giấy phép của mọi gói trong môi trường mà `python` trỏ tới."""
    done = subprocess.run(
        ["python3", "-m", "piplicenses", "--format=json", "--python", str(python)],
        capture_output=True,
        text=True,
        check=True,
    )
    parsed: list[dict[str, str]] = json.loads(done.stdout)
    return parsed


def main() -> int:
    """Chạy cổng, trả mã thoát cho dòng lệnh."""
    with core_only_env() as python:
        rows = licenses_in(python)
    problems = offending(rows)
    if problems:
        print("Phụ thuộc của praxon-core mang giấy phép không dùng được:", file=sys.stderr)
        for name, license_text in problems:
            print(f"  {name}: {license_text}", file=sys.stderr)
        return 1
    print(f"Cổng giấy phép đạt: {len(rows)} gói trong cây phụ thuộc của core, sạch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
