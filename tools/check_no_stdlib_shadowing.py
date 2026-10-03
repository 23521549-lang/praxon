"""Cổng: không gói nào ở cấp cao nhất trùng tên một module của thư viện chuẩn.

Lý do nằm ở bản quyết định kiến trúc 0003: một gói tên `platform` đè module
`platform` của thư viện chuẩn khi `src/` nằm đầu `sys.path`, và `platform.
python_version()` báo AttributeError. Nó đè *tùy cách gọi* — hỏng ở pytest, chạy
được khi cài — nên không có cổng thì nó quay lại lúc nào không biết.
"""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_SOURCES = ("packages/core/src", "packages/platform/src")


def offending(names: list[str]) -> list[str]:
    """Trả về các tên gói trùng với module của thư viện chuẩn."""
    return sorted(set(names) & set(sys.stdlib_module_names))


def top_level_packages() -> list[str]:
    """Tên các gói cấp cao nhất trong mã nguồn hai distribution."""
    found: list[str] = []
    for root in PACKAGE_SOURCES:
        base = Path(root)
        if base.is_dir():
            found += [p.name for p in base.iterdir() if (p / "__init__.py").is_file()]
    return found


def main() -> int:
    """Chạy cổng, trả mã thoát cho dòng lệnh."""
    problems = offending(top_level_packages())
    if problems:
        print("Gói cấp cao nhất trùng tên module thư viện chuẩn:", file=sys.stderr)
        for name in problems:
            print(f"  {name} — xem docs/decisions/0003", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
