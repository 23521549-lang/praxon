"""Backend checkpoint trên filesystem (task 10.3).

Backend mặc định cho dev/test: mỗi checkpoint là một file JSON dưới thư mục
gốc. Khóa checkpoint là đường dẫn tương đối dưới root, nên `list_keys` chỉ
là liệt kê file.
"""

from __future__ import annotations

from pathlib import Path


class LocalCheckpointStore:
    """CheckpointStore lưu mỗi checkpoint thành một file JSON dưới `root`.

    `put` ghi nguyên tử (ghi file tạm rồi đổi tên) nên checkpoint đang ghi
    dở vì đứt giữa chừng không bao giờ thành file `.json` đọc được: lần
    đọc sau chỉ thấy checkpoint cũ nguyên vẹn hoặc checkpoint mới đầy đủ,
    không bao giờ thấy file dở. Khóa trèo ra ngoài root (`..`, đường dẫn
    tuyệt đối) thì từ chối.
    """

    def __init__(self, root: Path) -> None:
        """`root` là thư mục gốc chứa mọi checkpoint (tự tạo khi ghi)."""
        self._root = root

    def _path_for(self, key: str) -> Path:
        """Đường dẫn file cho `key`; khóa trèo ra ngoài root thì từ chối."""
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root.resolve()):
            raise ValueError(f"khóa checkpoint {key!r} trèo ra ngoài thư mục gốc")
        return path

    def put(self, key: str, data: bytes) -> None:
        """Ghi `data` vào `key` (ghi đè nếu khóa đã có)."""
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def get(self, key: str) -> bytes | None:
        """Đọc bytes tại `key`; khóa chưa có thì `None`."""
        path = self._path_for(key)
        if not path.is_file():
            return None
        return path.read_bytes()

    def list_keys(self, prefix: str) -> list[str]:
        """Mọi khóa bắt đầu bằng `prefix`, sắp xếp tăng dần."""
        if not self._root.is_dir():
            return []
        root = self._root.resolve()
        return sorted(
            str(path.relative_to(root))
            for path in root.rglob("*.json")
            if path.is_file() and str(path.relative_to(root)).startswith(prefix)
        )
