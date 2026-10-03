"""Dựng một môi trường Python trống chỉ có `praxon-core` và phụ thuộc của nó.

Hai cổng dùng chung nó: phép thử ranh giới và cổng giấy phép. Cả hai hỏi cùng
một câu — *core một mình kéo theo những gì* — nên chúng phải hỏi trên cùng một
môi trường, không phải trên môi trường phát triển vốn có đủ thứ khác.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import venv
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

CORE_PACKAGE_DIR = Path(__file__).resolve().parent.parent / "packages" / "core"


class CoreEnvError(RuntimeError):
    """Không dựng được môi trường chỉ có core."""


def _python_in(env_dir: Path) -> Path:
    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    return env_dir / bin_dir / "python"


@contextmanager
def core_only_env() -> Iterator[Path]:
    """Cho ra đường dẫn interpreter của một môi trường chỉ cài praxon-core."""
    with tempfile.TemporaryDirectory() as tmp:
        env_dir = Path(tmp) / "env"
        venv.create(env_dir, with_pip=True, clear=True)
        python = _python_in(env_dir)
        done = subprocess.run(
            [str(python), "-m", "pip", "install", "--quiet", str(CORE_PACKAGE_DIR)],
            capture_output=True,
            text=True,
            check=False,
        )
        if done.returncode != 0:
            raise CoreEnvError(f"cài praxon-core thất bại: {done.stderr.strip()[-400:]}")
        yield python
