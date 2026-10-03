"""Đường dẫn dùng chung cho test. Suy từ vị trí tệp này, không từ thư mục hiện hành."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_SRC = REPO_ROOT / "packages" / "core" / "src"
PLATFORM_SRC = REPO_ROOT / "packages" / "platform" / "src"
