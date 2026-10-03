"""Settings: nạp từ tệp, từ chối sai kiểu và khóa lạ, cho biến môi trường ghi đè."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from praxon_core.settings import ENV_PREFIX, Settings, load_settings


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "praxon.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_nap_duoc_cau_hinh_hop_le(tmp_path):
    path = _write(tmp_path, 'database_url = "postgresql://localhost/praxon"\n')
    assert load_settings(path).database_url == "postgresql://localhost/praxon"


def test_tu_choi_sai_kieu(tmp_path):
    path = _write(tmp_path, "database_url = 5432\n")
    with pytest.raises(ValidationError):
        load_settings(path)


def test_tu_choi_khoa_la(tmp_path):
    # Một khóa viết sai phải bị từ chối, không được bỏ qua im lặng rồi hệ chạy
    # với giá trị mặc định mà không ai biết.
    path = _write(tmp_path, 'database_url = "x"\ndatabse_url = "y"\n')
    with pytest.raises(ValidationError):
        load_settings(path)


def test_thieu_khoa_bat_buoc(tmp_path):
    with pytest.raises(ValidationError):
        load_settings(_write(tmp_path, "\n"))


def test_bien_moi_truong_ghi_de(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_PREFIX + "DATABASE_URL", "postgresql://ghi-de/praxon")
    path = _write(tmp_path, 'database_url = "postgresql://trong-tep/praxon"\n')
    assert load_settings(path).database_url == "postgresql://ghi-de/praxon"


def test_settings_khong_sua_duoc():
    # Điều kiện tái lập đòi config_hash không đổi trong suốt một lần chạy.
    settings = Settings(database_url="postgresql://localhost/praxon")
    with pytest.raises(ValidationError):
        settings.database_url = "postgresql://khac/praxon"
