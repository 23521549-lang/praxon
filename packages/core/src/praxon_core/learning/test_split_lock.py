"""Đọc hai file khóa phần đo (task 12.1, spec dòng 152).

Hàm thuần: nạp TOML cấu hình, tính `config_hash`, đối chiếu với
`locked_config_hash` trong bản ghi khóa. Lệch nhau hoặc thiếu file thì
từ chối ngay, chưa chạy gì (fail-closed). Không đọc biến môi trường,
không gọi git, không chạm coordinator: driver chạy đo (12.2) gọi hàm
này rồi mới dựng `LearningRound` với `on_test_split=True`.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from praxon_core.learning.coordinator import compute_config_hash
from praxon_core.settings import Settings, load_settings


def load_locked_config(config_path: Path, lock_path: Path) -> tuple[Settings, str]:
    """Nạp cấu hình đo đã khóa; trả `(settings, locked_config_hash)`.

    `locked_config_hash` là hash đã khóa bằng commit trước khi chạm phần
    đo lần đầu. Bản ghi khóa thiếu, không đọc được, thiếu khóa hash, hoặc
    hash tính từ TOML khác hash trong bản ghi thì raise `ValueError`
    trước khi trả gì: driver không có gì để chạy đo.
    """
    try:
        lock_raw = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"không đọc được bản ghi khóa {lock_path}: {exc}") from exc
    locked = lock_raw.get("locked_config_hash")
    if not isinstance(locked, str) or not locked:
        raise ValueError(
            f"bản ghi khóa {lock_path} thiếu locked_config_hash: không chạy đo không khóa"
        )
    try:
        settings = load_settings(config_path)
    except OSError as exc:
        raise ValueError(f"không đọc được cấu hình đo {config_path}: {exc}") from exc
    config_hash = compute_config_hash(settings)
    if config_hash != locked:
        raise ValueError(
            "cấu hình đo khác khóa phần đo "
            f"(config_hash {config_hash[:12]}... khác khóa {locked[:12]}...): "
            "không được chạy trên phần đo"
        )
    return settings, locked
