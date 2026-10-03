"""Cổng: phiên bản công cụ đang chạy khớp với requirements-dev.txt.

Phép thử ngày 3/10/2026: `mypy` trên PATH báo 1.20.2 còn `python3 -m mypy` báo
2.4.0; `ruff` trên PATH báo 0.15.20 còn `python3 -m ruff` báo 0.16.10. Nghĩa là
ghim phiên bản trong requirements-dev.txt **không có tác dụng gì** nếu lệnh gọi
chạm vào một binary khác đang nằm trên PATH. Khi đó "xanh ở máy tôi" không nói
gì về CI, và hai bên có thể khác nhau hàng năm phiên bản mà không ai thấy.

Cổng này đọc phiên bản thật của gói đã cài qua metadata, so với bản ghim, và đỏ
khi lệch. Nó không sửa được việc ai đó gọi sai binary — việc đó do CI và tài
liệu quy định gọi qua `python3 -m` — nhưng nó bảo đảm môi trường đang chạy đúng
là môi trường đã ghim.
"""

from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path

REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements-dev.txt"


def pinned(text: str) -> dict[str, str]:
    """Đọc các dòng `tên==phiên bản`, bỏ chú thích và dòng trống."""
    found: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "==" not in stripped:
            continue
        name, version = stripped.split("==", 1)
        found[name.strip()] = version.strip()
    return found


def mismatches(expected: dict[str, str]) -> list[str]:
    """Trả về mô tả từng chỗ lệch giữa bản ghim và gói đã cài."""
    problems: list[str] = []
    for name, want in sorted(expected.items()):
        try:
            got = metadata.version(name)
        except metadata.PackageNotFoundError:
            problems.append(f"{name}: ghim {want}, chưa cài")
            continue
        if got != want:
            problems.append(f"{name}: ghim {want}, đang cài {got}")
    return problems


def main() -> int:
    """Chạy cổng, trả mã thoát cho dòng lệnh."""
    problems = mismatches(pinned(REQUIREMENTS.read_text(encoding="utf-8")))
    if problems:
        print("Phiên bản công cụ lệch bản ghim:", file=sys.stderr)
        for line in problems:
            print(f"  {line}", file=sys.stderr)
        print(
            "Chạy: python3 -m pip install -r requirements-dev.txt — và gọi công cụ "
            "bằng `python3 -m <tên>`, không bằng binary trên PATH.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
