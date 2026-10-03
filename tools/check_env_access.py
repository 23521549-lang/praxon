"""Cổng: `os.environ` và `os.getenv` chỉ được dùng trong module settings.

Dùng phân tích cú pháp chứ không khớp chuỗi, vì khớp chuỗi báo nhầm trên chú
thích và trên chuỗi ký tự — và một cổng báo nhầm thì sớm muộn bị ai đó tắt.

Chỉ quét mã nguồn của các gói, không quét `tools/` và `tests/`: đó là phần
được phát hành, và là phần mà một biến môi trường lẩn vào sẽ thành lỗi lúc
chạy ở máy khách.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable
from pathlib import Path

ALLOWED_MODULES = frozenset({"praxon_core/settings.py"})
PACKAGE_SOURCES = ("packages/core/src", "packages/platform/src")
FORBIDDEN_ATTRIBUTES = frozenset({"environ", "getenv", "environb", "putenv"})


class Finding(ast.NodeVisitor):
    """Thu các chỗ đọc biến môi trường trong một cây cú pháp."""

    def __init__(self) -> None:
        """Khởi tạo danh sách vi phạm rỗng."""
        self.hits: list[tuple[int, str]] = []

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Bắt dạng `os.environ` và `os.getenv`."""
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and node.attr in FORBIDDEN_ATTRIBUTES
        ):
            self.hits.append((node.lineno, f"os.{node.attr}"))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Bắt dạng `from os import getenv`."""
        if node.module == "os":
            for alias in node.names:
                if alias.name in FORBIDDEN_ATTRIBUTES:
                    self.hits.append((node.lineno, f"from os import {alias.name}"))
        self.generic_visit(node)


def offending(source: str, relative_name: str) -> list[tuple[int, str]]:
    """Trả về các vi phạm trong một tệp, rỗng nếu tệp được phép hoặc sạch."""
    if relative_name in ALLOWED_MODULES:
        return []
    finder = Finding()
    finder.visit(ast.parse(source))
    return finder.hits


def scan(roots: Iterable[str]) -> list[str]:
    """Quét mã nguồn các gói, trả về mô tả từng vi phạm."""
    problems: list[str] = []
    for root in roots:
        base = Path(root)
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            relative = path.relative_to(base).as_posix()
            for lineno, what in offending(path.read_text(encoding="utf-8"), relative):
                problems.append(f"{path}:{lineno}: {what}")
    return problems


def main() -> int:
    """Chạy cổng, trả mã thoát cho dòng lệnh."""
    problems = scan(PACKAGE_SOURCES)
    if problems:
        print("Đọc biến môi trường ngoài module settings:", file=sys.stderr)
        for line in problems:
            print(f"  {line}", file=sys.stderr)
        print(
            "Chuyển giá trị đó thành một trường của Settings và nạp từ tệp cấu hình.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
