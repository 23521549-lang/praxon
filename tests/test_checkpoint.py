"""Checkpoint (task 10.3): format có version, khóa theo số case, đọc mới nhất."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws
from pydantic import ValidationError

from praxon_core.adapters.local_store import LocalCheckpointStore
from praxon_core.adapters.s3_store import S3CheckpointStore
from praxon_core.learning.candidate import (
    Candidate,
    Decision,
    DecisionVerdict,
    GovernorResult,
)
from praxon_core.learning.checkpoint import (
    CHECKPOINT_VERSION,
    Checkpoint,
    CheckpointStore,
    checkpoint_key,
    checkpoint_prefix,
    read_checkpoint,
    read_latest_checkpoint,
    write_checkpoint,
)
from praxon_core.learning.curator import Insight, InsightSource
from praxon_core.learning.generator import Trajectory
from praxon_core.repositories.events import EventRow
from praxon_core.repositories.facts import FactClose, FactRow

EPISODE_ID = "22222222-2222-2222-2222-222222222222"
FACT_ID = "33333333-3333-3333-3333-333333333333"
CONFIG_HASH = "c" * 64
DATA_HASH = "d" * 64


class MemoryStore:
    """Store giả trong bộ nhớ, đúng Protocol `CheckpointStore`."""

    def __init__(self) -> None:
        """Store rỗng."""
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        """Ghi `data` vào `key` trong dict."""
        self.objects[key] = data

    def get(self, key: str) -> bytes | None:
        """Đọc bytes tại `key`; chưa có thì `None`."""
        return self.objects.get(key)

    def list_keys(self, prefix: str) -> list[str]:
        """Mọi khóa bắt đầu bằng `prefix`, sắp xếp tăng dần."""
        return sorted(key for key in self.objects if key.startswith(prefix))


def _sample_checkpoint(*, cases_done: tuple[str, ...] = ("c1", "c2")) -> Checkpoint:
    return Checkpoint(
        tenant_id="acme",
        seed=42,
        model_id="Qwen/Qwen3-8B-GGUF",
        model_revision="7c41481f57cb95916b40956ab2f0b139b296d974",
        config_hash=CONFIG_HASH,
        data_hash=DATA_HASH,
        cases_done=cases_done,
        trajectories=(
            Trajectory(
                tenant_id="acme",
                case_id="c1",
                activities=("A", "B"),
                attributes={},
                episode_ids=(UUID(EPISODE_ID),),
            ),
        ),
        insights=(
            Insight(
                template="response",
                activation="A",
                target="B",
                condition=None,
                evidence_episode_ids=[EPISODE_ID],
                source=InsightSource.TRACE,
                scope="global",
            ),
        ),
        decisions=(
            GovernorResult(
                decision=Decision(
                    verdict=DecisionVerdict.AUTO_APPROVE, rule_id=2, reason="duyet"
                ),
                candidate=Candidate(
                    target_scope="global",
                    payload={"kind": "ADD"},
                    rationale="r",
                    evidence_episode_ids=[EPISODE_ID],
                    status="approved",
                ),
            ),
        ),
        candidate_ids=("candidate-0",),
        fact_rows=(
            FactRow(
                tenant_id="global",
                scope="global",
                canonical_key="response(A, B)",
                template="response",
                statement="s",
                status="trial",
                support=3,
                confidence=0.9,
                valid_start=datetime(2030, 1, 1, tzinfo=UTC),
                valid_end=None,
                candidate_id="candidate-0",
            ),
        ),
        fact_closes=(
            FactClose(
                fact_id=FACT_ID,
                retired_at=datetime(2030, 2, 1, tzinfo=UTC),
            ),
        ),
        events=(
            EventRow(
                tenant_id="acme",
                actor="generator",
                action="replay",
                payload_hash="a" * 64,
            ),
        ),
        cache_entries={"khoa-1": "phan-hoi-1"},
        tokens_in=10,
        tokens_out=20,
    )


def _prefix() -> str:
    return checkpoint_prefix(
        tenant_id="acme", seed=42, config_hash=CONFIG_HASH, data_hash=DATA_HASH
    )


def test_checkpoint_mac_dinh_version_1_va_rong():
    checkpoint = Checkpoint(
        tenant_id="acme",
        seed=42,
        model_id="m",
        model_revision="r",
        config_hash=CONFIG_HASH,
        data_hash=DATA_HASH,
    )
    assert checkpoint.version == CHECKPOINT_VERSION == 1
    assert checkpoint.cases_done == ()
    assert checkpoint.decisions == ()
    assert checkpoint.fact_rows == ()
    assert checkpoint.cache_entries == {}
    assert (checkpoint.tokens_in, checkpoint.tokens_out) == (0, 0)


def test_checkpoint_tu_choi_truong_la():
    with pytest.raises(ValidationError):
        Checkpoint.model_validate(
            {
                "tenant_id": "acme",
                "seed": 42,
                "model_id": "m",
                "model_revision": "r",
                "config_hash": CONFIG_HASH,
                "data_hash": DATA_HASH,
                "truong_la": 1,
            }
        )


def test_checkpoint_prefix_chua_tenant_seed_va_hash():
    prefix = _prefix()
    assert prefix.startswith("checkpoints/acme/42-")
    assert CONFIG_HASH[:12] in prefix
    assert DATA_HASH[:12] in prefix


def test_checkpoint_key_ma_so_case_thanh_6_chu_so():
    assert checkpoint_key("checkpoints/acme/42-cc-dd", 2) == (
        "checkpoints/acme/42-cc-dd/000002.json"
    )
    assert checkpoint_key("checkpoints/acme/42-cc-dd", 100) == (
        "checkpoints/acme/42-cc-dd/000100.json"
    )


def test_write_read_round_trip_giu_nguyen_moi_thanh_phan():
    store = MemoryStore()
    checkpoint = _sample_checkpoint()
    key = write_checkpoint(store, checkpoint, _prefix())
    assert key == _prefix() + "/000002.json"
    assert read_checkpoint(store, key) == checkpoint


def test_read_khoa_thieu_thi_tu_choi():
    store = MemoryStore()
    with pytest.raises(ValueError, match="không có checkpoint"):
        read_checkpoint(store, "checkpoints/acme/42-cc-dd/000001.json")


def test_read_version_la_thi_tu_choi():
    store: CheckpointStore = MemoryStore()
    key = _prefix() + "/000001.json"
    document = _sample_checkpoint(cases_done=("c1",)).model_dump(mode="json")
    document["version"] = 99
    store.put(key, json.dumps(document).encode("utf-8"))
    with pytest.raises(ValueError, match="version 99"):
        read_checkpoint(store, key)


def test_read_json_hong_thi_tu_choi():
    store: CheckpointStore = MemoryStore()
    key = _prefix() + "/000001.json"
    store.put(key, b"khong-phai-json")
    with pytest.raises(ValueError, match="không phải JSON hợp lệ"):
        read_checkpoint(store, key)


def test_read_khong_phai_object_thi_tu_choi():
    store: CheckpointStore = MemoryStore()
    key = _prefix() + "/000001.json"
    store.put(key, b"[1, 2]")
    with pytest.raises(ValueError, match="phải là một object JSON"):
        read_checkpoint(store, key)


def test_read_latest_chon_so_case_lon_nhat():
    store = MemoryStore()
    prefix = _prefix()
    write_checkpoint(store, _sample_checkpoint(cases_done=("c1",)), prefix)
    latest_key = write_checkpoint(
        store, _sample_checkpoint(cases_done=("c1", "c2", "c3")), prefix
    )
    write_checkpoint(store, _sample_checkpoint(cases_done=("c1", "c2")), prefix)
    latest = read_latest_checkpoint(store, prefix)
    assert latest is not None
    assert latest.cases_done == ("c1", "c2", "c3")
    assert read_checkpoint(store, latest_key) == latest


def test_read_latest_khong_co_thi_none():
    store = MemoryStore()
    assert read_latest_checkpoint(store, _prefix()) is None


def test_read_latest_bo_qua_khoa_la_trong_cung_thu_muc():
    store: CheckpointStore = MemoryStore()
    prefix = _prefix()
    write_checkpoint(store, _sample_checkpoint(cases_done=("c1",)), prefix)
    store.put(prefix + "/ghi-chu.txt", b"file la khong phai checkpoint")
    store.put(prefix + "/checkpoint-cu.json", b"ten khong dung dang so case")
    latest = read_latest_checkpoint(store, prefix)
    assert latest is not None
    assert latest.cases_done == ("c1",)


def test_read_latest_checkpoint_moi_nhat_hong_thi_bao_loi():
    # Checkpoint mới nhất mà hỏng thì phải báo lỗi to, không được lặng lẽ
    # lùi về checkpoint cũ hơn (lùi lùi thì chạy lại case đã xong, có thể
    # quyết lại candidate đã quyết — sai lặng còn tệ hơn dừng lại).
    store: CheckpointStore = MemoryStore()
    prefix = _prefix()
    write_checkpoint(store, _sample_checkpoint(cases_done=("c1",)), prefix)
    store.put(prefix + "/000002.json", b"khong-phai-json")
    with pytest.raises(ValueError, match="không phải JSON hợp lệ"):
        read_latest_checkpoint(store, prefix)


# --- Backend local filesystem ---


def test_local_store_put_get_round_trip(tmp_path):
    store = LocalCheckpointStore(tmp_path / "ckp")
    store.put("checkpoints/acme/42-cc-dd/000002.json", b'{"a": 1}')
    assert store.get("checkpoints/acme/42-cc-dd/000002.json") == b'{"a": 1}'


def test_local_store_get_thieu_thi_none(tmp_path):
    store = LocalCheckpointStore(tmp_path / "ckp")
    assert store.get("checkpoints/acme/42-cc-dd/000001.json") is None


def test_local_store_put_ghi_de(tmp_path):
    store = LocalCheckpointStore(tmp_path / "ckp")
    key = "checkpoints/acme/42-cc-dd/000001.json"
    store.put(key, b"cu")
    store.put(key, b"moi")
    assert store.get(key) == b"moi"


def test_local_store_list_keys_loc_theo_prefix_va_sap_xep(tmp_path):
    store = LocalCheckpointStore(tmp_path / "ckp")
    store.put("checkpoints/acme/42-cc-dd/000002.json", b"2")
    store.put("checkpoints/acme/42-cc-dd/000001.json", b"1")
    store.put("checkpoints/acme/43-ee-ff/000001.json", b"khac")
    store.put("checkpoints/globex/42-cc-dd/000001.json", b"khac")
    assert store.list_keys("checkpoints/acme/42-cc-dd") == [
        "checkpoints/acme/42-cc-dd/000001.json",
        "checkpoints/acme/42-cc-dd/000002.json",
    ]
    assert store.list_keys("checkpoints/acme") == [
        "checkpoints/acme/42-cc-dd/000001.json",
        "checkpoints/acme/42-cc-dd/000002.json",
        "checkpoints/acme/43-ee-ff/000001.json",
    ]
    assert store.list_keys("checkpoints/khong-co") == []


def test_local_store_khoa_treo_ra_ngoai_root_thi_tu_choi(tmp_path):
    store = LocalCheckpointStore(tmp_path / "ckp")
    with pytest.raises(ValueError, match="trèo ra ngoài"):
        store.put("../thoat.json", b"x")
    with pytest.raises(ValueError, match="trèo ra ngoài"):
        store.get("/etc/passwd")


def test_local_store_ghi_doc_checkpoint_dang_day_du(tmp_path):
    # Format + store local đi chung: ghi checkpoint rồi đọc lại giống hệt.
    store = LocalCheckpointStore(tmp_path / "ckp")
    prefix = _prefix()
    checkpoint = _sample_checkpoint()
    key = write_checkpoint(store, checkpoint, prefix)
    assert read_checkpoint(store, key) == checkpoint
    assert read_latest_checkpoint(store, prefix) == checkpoint
    assert (tmp_path / "ckp" / key).is_file()


# --- Backend S3-compatible (mock S3, chưa cần B2 thật) ---


@pytest.fixture
def s3_store():
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(
            Bucket="praxon-checkpoints-test"
        )
        yield S3CheckpointStore(
            bucket="praxon-checkpoints-test",
            endpoint_url=None,
            access_key_id="test",
            secret_access_key="test",
        )


def test_s3_store_put_get_round_trip(s3_store):
    s3_store.put("checkpoints/acme/42-cc-dd/000002.json", b'{"a": 1}')
    assert s3_store.get("checkpoints/acme/42-cc-dd/000002.json") == b'{"a": 1}'


def test_s3_store_get_thieu_thi_none(s3_store):
    assert s3_store.get("checkpoints/acme/42-cc-dd/000001.json") is None


def test_s3_store_list_keys_loc_theo_prefix_va_sap_xep(s3_store):
    s3_store.put("checkpoints/acme/42-cc-dd/000002.json", b"2")
    s3_store.put("checkpoints/acme/42-cc-dd/000001.json", b"1")
    s3_store.put("checkpoints/acme/43-ee-ff/000001.json", b"khac")
    assert s3_store.list_keys("checkpoints/acme/42-cc-dd") == [
        "checkpoints/acme/42-cc-dd/000001.json",
        "checkpoints/acme/42-cc-dd/000002.json",
    ]
    assert s3_store.list_keys("checkpoints/khong-co") == []


def test_s3_store_bucket_chua_co_thi_bao_loi_ro():
    with mock_aws():
        store = S3CheckpointStore(
            bucket="bucket-chua-tao",
            endpoint_url=None,
            access_key_id="test",
            secret_access_key="test",
        )
        with pytest.raises(ClientError, match="NoSuchBucket"):
            store.put("checkpoints/acme/42-cc-dd/000001.json", b"x")


def test_s3_store_ghi_doc_checkpoint_dang_day_du(s3_store):
    # Format + store S3 đi chung qua mock: ghi checkpoint rồi đọc lại
    # giống hệt; lần push B2 thật kiểm riêng khi có credentials.
    prefix = _prefix()
    checkpoint = _sample_checkpoint()
    key = write_checkpoint(s3_store, checkpoint, prefix)
    assert read_checkpoint(s3_store, key) == checkpoint
    assert read_latest_checkpoint(s3_store, prefix) == checkpoint
