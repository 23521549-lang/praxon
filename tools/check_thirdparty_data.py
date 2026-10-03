"""Cổng: không có dữ liệu bên thứ ba nào nằm trong kho.

Bất biến của dự án: log BPIC và bộ 104 câu tải lúc chạy, không đóng gói vào
kho. Lý do là giấy phép — kho có thể mở nguồn, dữ liệu thì không chắc được
phép phân phối lại.

Hỏi `git ls-files` chứ không quét đĩa, vì "trong kho" nghĩa là đã được theo
dõi. Tải về để chạy thì vẫn được, đúng như bất biến nói; commit mới là vi phạm.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable

FORBIDDEN_SUFFIXES = (".xes", ".csv", ".gz")
ALLOWED_PREFIXES = ("tests/fixtures/",)


def offending(tracked: Iterable[str]) -> list[str]:
    """Trả về các tệp dữ liệu bị theo dõi ngoài thư mục fixture."""
    return sorted(
        path
        for path in tracked
        if path.endswith(FORBIDDEN_SUFFIXES) and not path.startswith(ALLOWED_PREFIXES)
    )


def tracked_files() -> list[str]:
    """Danh sách tệp đang được git theo dõi."""
    done = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, check=True)
    return [p for p in done.stdout.split("\0") if p]


def main() -> int:
    """Chạy cổng, trả mã thoát cho dòng lệnh."""
    problems = offending(tracked_files())
    if problems:
        print("Dữ liệu bên thứ ba bị theo dõi trong kho:", file=sys.stderr)
        for path in problems:
            print(f"  {path}", file=sys.stderr)
        print(
            f"Bỏ theo dõi và tải lúc chạy. Fixture của test đặt dưới {ALLOWED_PREFIXES[0]}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
