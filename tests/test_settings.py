"""Settings: nạp từ tệp, từ chối sai kiểu và khóa lạ, cho biến môi trường ghi đè."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from praxon_core.learning.coordinator import (
    compute_config_hash,
    compute_config_hash_without_budget,
)
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


def test_mac_dinh_checkpoint(tmp_path):
    # Task 10.3: mặc định checkpoint mỗi 100 case, backend local; chưa có
    # cấu hình S3 nào.
    settings = load_settings(_write(tmp_path, 'database_url = "x"\n'))
    assert settings.checkpoint_every_n_cases == 100
    assert settings.checkpoint_store == "local"
    assert settings.s3_endpoint_url is None
    assert settings.s3_bucket is None
    assert settings.s3_access_key_id is None
    assert settings.s3_secret_access_key is None


def test_ghi_de_checkpoint_qua_toml(tmp_path):
    path = _write(
        tmp_path,
        'database_url = "x"\n'
        "checkpoint_every_n_cases = 25\n"
        'checkpoint_store = "s3"\n'
        's3_endpoint_url = "https://s3.us-west-004.backblazeb2.com"\n'
        's3_bucket = "praxon-checkpoints"\n',
    )
    settings = load_settings(path)
    assert settings.checkpoint_every_n_cases == 25
    assert settings.checkpoint_store == "s3"
    assert settings.s3_endpoint_url == "https://s3.us-west-004.backblazeb2.com"
    assert settings.s3_bucket == "praxon-checkpoints"


def test_checkpoint_store_sai_gia_tri_thi_tu_choi(tmp_path):
    path = _write(
        tmp_path,
        'database_url = "x"\ncheckpoint_store = "postgres"\n',
    )
    with pytest.raises(ValidationError):
        load_settings(path)


def test_khoa_s3_chi_qua_bien_moi_truong(tmp_path, monkeypatch):
    # Khóa S3 không bao giờ nằm trong tệp TOML: chỉ biến môi trường mới
    # đưa được nó vào Settings (task 10.3, giống openai_api_key).
    monkeypatch.setenv(ENV_PREFIX + "S3_ACCESS_KEY_ID", "key-id-that")
    monkeypatch.setenv(ENV_PREFIX + "S3_SECRET_ACCESS_KEY", "khoa-bi-mat")
    monkeypatch.setenv(ENV_PREFIX + "S3_ENDPOINT_URL", "https://s3.example.com")
    monkeypatch.setenv(ENV_PREFIX + "S3_BUCKET", "praxon-checkpoints")
    monkeypatch.setenv(ENV_PREFIX + "CHECKPOINT_EVERY_N_CASES", "50")
    monkeypatch.setenv(ENV_PREFIX + "CHECKPOINT_STORE", "s3")
    path = _write(tmp_path, 'database_url = "x"\n')
    settings = load_settings(path)
    assert settings.s3_access_key_id == "key-id-that"
    assert settings.s3_secret_access_key == "khoa-bi-mat"
    assert settings.s3_endpoint_url == "https://s3.example.com"
    assert settings.s3_bucket == "praxon-checkpoints"
    assert settings.checkpoint_every_n_cases == 50
    assert settings.checkpoint_store == "s3"


def test_mac_dinh_tran_token(tmp_path):
    # Task 10.4: mặc định không đặt trần (0 = tắt), dự trữ 2048 (= ctx-size).
    settings = load_settings(_write(tmp_path, 'database_url = "x"\n'))
    assert settings.token_budget_total == 0
    assert settings.token_budget_reserve_per_call == 2048


def test_ghi_de_tran_token_qua_toml(tmp_path):
    path = _write(
        tmp_path,
        'database_url = "x"\ntoken_budget_total = 5000\ntoken_budget_reserve_per_call = 1024\n',
    )
    settings = load_settings(path)
    assert settings.token_budget_total == 5000
    assert settings.token_budget_reserve_per_call == 1024


def test_ghi_de_tran_token_qua_bien_moi_truong(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_PREFIX + "TOKEN_BUDGET_TOTAL", "5000")
    monkeypatch.setenv(ENV_PREFIX + "TOKEN_BUDGET_RESERVE_PER_CALL", "1024")
    path = _write(tmp_path, 'database_url = "x"\n')
    settings = load_settings(path)
    assert settings.token_budget_total == 5000
    assert settings.token_budget_reserve_per_call == 1024


def test_tran_token_am_thi_tu_choi(tmp_path):
    path = _write(tmp_path, 'database_url = "x"\ntoken_budget_total = -1\n')
    with pytest.raises(ValidationError):
        load_settings(path)
    path = _write(tmp_path, 'database_url = "x"\ntoken_budget_reserve_per_call = -1\n')
    with pytest.raises(ValidationError):
        load_settings(path)


def test_doi_tran_doi_config_hash_nhung_khong_doi_hash_tru_tran(tmp_path):
    settings = load_settings(_write(tmp_path, 'database_url = "x"\n'))
    nang_tran = settings.model_copy(update={"token_budget_total": 5000})
    assert compute_config_hash(nang_tran) != compute_config_hash(settings)
    assert compute_config_hash_without_budget(nang_tran) == compute_config_hash_without_budget(
        settings
    )
