"""Test âm cho bốn hợp đồng import-linter.

Chạy trên cây mã **thật** và tệp `.importlinter` **thật**, không trên bản sao:
mục đích là chứng minh cấu hình đang dùng có chặn, nên kiểm một bản sao của nó
thì không chứng minh được gì.

Mỗi phép thử đặt một tệp dò vào thư mục cần thử, chạy `lint-imports`, rồi xóa
tệp ở khối `finally`. Tên tệp bắt đầu bằng `_gate_probe_` và `.gitignore` chặn
mẫu đó, nên một tệp sót lại vì tiến trình bị giết cũng không thể lọt vào commit.

Kiểm cả hai nửa của mỗi hợp đồng "chỉ ở một chỗ": import bị cấm đặt ngoài thư
mục được phép thì đỏ, cùng import đó đặt trong thư mục được phép thì xanh. Nửa
thứ hai là thứ chứng minh allowlist viết đúng.
"""

from __future__ import annotations

import subprocess
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from tests.paths import CORE_SRC, REPO_ROOT

CORE_PACKAGE = CORE_SRC / "praxon_core"


@contextmanager
def probe(subpackage: str, body: str) -> Iterator[None]:
    directory = CORE_PACKAGE / subpackage if subpackage else CORE_PACKAGE
    path: Path = directory / f"_gate_probe_{uuid.uuid4().hex}.py"
    path.write_text(body, encoding="utf-8")
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def lint_imports_exit_code() -> int:
    return subprocess.run(
        ["lint-imports", "--config", ".importlinter"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    ).returncode


def test_cay_ma_that_hien_dang_xanh():
    assert lint_imports_exit_code() == 0


def test_bat_core_import_platform():
    with probe("", "import praxon_platform\n"):
        assert lint_imports_exit_code() != 0


@pytest.mark.parametrize(
    ("subpackage", "body"),
    [
        ("repositories", "import openai\n"),
        ("gateway", "import anthropic\n"),
    ],
)
def test_bat_sdk_mo_hinh_ngoai_adapters(subpackage, body):
    with probe(subpackage, body):
        assert lint_imports_exit_code() != 0


def test_cho_phep_sdk_mo_hinh_trong_adapters():
    with probe("adapters", "import openai\n"):
        assert lint_imports_exit_code() == 0


@pytest.mark.parametrize("subpackage", ["adapters", "gateway"])
def test_bat_driver_db_ngoai_repositories(subpackage):
    with probe(subpackage, "import psycopg\n"):
        assert lint_imports_exit_code() != 0


def test_cho_phep_driver_db_trong_repositories():
    with probe("repositories", "import psycopg\n"):
        assert lint_imports_exit_code() == 0


def test_bat_client_tool_ngoai_gateway_va_adapters():
    with probe("repositories", "import mcp\n"):
        assert lint_imports_exit_code() != 0


@pytest.mark.parametrize("subpackage", ["gateway", "adapters"])
def test_cho_phep_client_tool_trong_gateway_va_adapters(subpackage):
    with probe(subpackage, "import mcp\n"):
        assert lint_imports_exit_code() == 0
