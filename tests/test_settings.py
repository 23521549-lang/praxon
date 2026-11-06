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


def test_mac_dinh_mo_hinh_cpu(tmp_path):
    # Task 6.1: mặc định trỏ về llama-server trên máy + Qwen3-8B-GGUF.
    settings = load_settings(_write(tmp_path, 'database_url = "x"\n'))
    assert settings.openai_base_url == "http://localhost:8080/v1"
    assert settings.cpu_model_base_url == "http://localhost:8080/v1"
    assert settings.model_id == "Qwen/Qwen3-8B-GGUF"
    assert settings.model_revision == "7c41481f57cb95916b40956ab2f0b139b296d974"
    assert settings.openai_api_key is None
    assert settings.model_max_retries == 3
    assert settings.model_retry_base_delay_seconds == 1.0


def test_ghi_de_mo_hinh_qua_toml(tmp_path):
    path = _write(
        tmp_path,
        'database_url = "x"\n'
        'openai_base_url = "https://api.example.com/v1"\n'
        'model_id = "ten-model-khac"\n'
        'model_revision = "abc123"\n'
        "model_max_retries = 1\n"
        "model_retry_base_delay_seconds = 0.5\n",
    )
    settings = load_settings(path)
    assert settings.openai_base_url == "https://api.example.com/v1"
    assert settings.model_id == "ten-model-khac"
    assert settings.model_revision == "abc123"
    assert settings.model_max_retries == 1
    assert settings.model_retry_base_delay_seconds == 0.5


def test_khoa_api_chi_qua_bien_moi_truong(tmp_path, monkeypatch):
    # Khóa API không bao giờ nằm trong tệp TOML: chỉ biến môi trường mới
    # đưa được nó vào Settings (task 6.1).
    monkeypatch.setenv(ENV_PREFIX + "OPENAI_API_KEY", "khoa-that")
    path = _write(tmp_path, 'database_url = "x"\n')
    assert load_settings(path).openai_api_key == "khoa-that"


def test_bien_moi_truong_ghi_de_so(tmp_path, monkeypatch):
    # Biến môi trường là chuỗi; Pydantic phải đổi được thành int/float.
    monkeypatch.setenv(ENV_PREFIX + "MODEL_MAX_RETRIES", "5")
    monkeypatch.setenv(ENV_PREFIX + "MODEL_RETRY_BASE_DELAY_SECONDS", "2.5")
    path = _write(tmp_path, 'database_url = "x"\n')
    settings = load_settings(path)
    assert settings.model_max_retries == 5
    assert settings.model_retry_base_delay_seconds == 2.5
