"""Generator (task 7.1): phát lại trace từ episode, không gọi mô hình."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from praxon_core.learning.generator import EpisodeRow, Trajectory, replay


def _dt(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def _row(
    case_id: str,
    activity: str,
    occurred: str,
    tenant: str = "acme",
    attributes: dict[str, Any] | None = None,
    episode_id: UUID | None = None,
) -> EpisodeRow:
    return EpisodeRow(
        id=episode_id if episode_id is not None else uuid4(),
        tenant_id=tenant,
        case_id=case_id,
        payload={
            "activity": activity,
            "case_attributes": attributes if attributes is not None else {},
        },
        occurred_at=_dt(occurred),
        ingested_at=_dt("2026-11-06T00:00:00"),
    )


def test_lo_rong_thi_tra_ve_rong():
    assert replay("acme", []) == []


def test_mot_case_xep_theo_thoi_gian():
    rows = [
        _row("c1", "B", "2026-11-01T10:02:00", episode_id=UUID(int=2)),
        _row("c1", "A", "2026-11-01T10:00:00", episode_id=UUID(int=1)),
        _row("c1", "C", "2026-11-01T10:05:00", episode_id=UUID(int=3)),
    ]
    result = replay("acme", rows)
    assert result == [
        Trajectory(
            tenant_id="acme",
            case_id="c1",
            activities=("A", "B", "C"),
            attributes={},
            episode_ids=(UUID(int=1), UUID(int=2), UUID(int=3)),
        )
    ]


def test_episode_ids_khop_thu_tu_thoi_gian_cua_activities():
    """episode_ids theo đúng thứ tự thời gian, khớp từng vị trí của activities."""
    rows = [
        _row("c1", "C", "2026-11-01T10:05:00", episode_id=UUID(int=30)),
        _row("c1", "A", "2026-11-01T10:00:00", episode_id=UUID(int=10)),
        _row("c1", "B", "2026-11-01T10:02:00", episode_id=UUID(int=20)),
    ]
    result = replay("acme", rows)
    assert len(result) == 1
    assert result[0].activities == ("A", "B", "C")
    assert result[0].episode_ids == (UUID(int=10), UUID(int=20), UUID(int=30))
    assert len(result[0].episode_ids) == len(result[0].activities)


def test_nhieu_case_xen_ke_nhom_dung_case():
    rows = [
        _row("c1", "A", "2026-11-01T10:00:00"),
        _row("c2", "X", "2026-11-01T10:01:00"),
        _row("c1", "B", "2026-11-01T10:02:00"),
        _row("c2", "Y", "2026-11-01T10:03:00"),
    ]
    result = replay("acme", rows)
    assert [t.case_id for t in result] == ["c1", "c2"]
    assert result[0].activities == ("A", "B")
    assert result[1].activities == ("X", "Y")


def test_cung_thoi_diem_giu_nguyen_thu_tu_dau_vao():
    rows = [
        _row("c1", "A", "2026-11-01T10:00:00"),
        _row("c1", "B", "2026-11-01T10:00:00"),
        _row("c1", "C", "2026-11-01T10:00:00"),
    ]
    assert replay("acme", rows)[0].activities == ("A", "B", "C")


def test_thuoc_tinh_case_lay_tu_hang_som_nhat():
    rows = [
        _row("c1", "B", "2026-11-01T10:02:00", attributes={"loai": "xay-dung"}),
        _row("c1", "A", "2026-11-01T10:00:00", attributes={"loai": "xay-dung"}),
    ]
    result = replay("acme", rows)
    assert result[0].attributes == {"loai": "xay-dung"}


def test_vang_case_attributes_thi_mac_dinh_rong():
    row = EpisodeRow(
        id=UUID(int=1),
        tenant_id="acme",
        case_id="c1",
        payload={"activity": "A"},
        occurred_at=_dt("2026-11-01T10:00:00"),
        ingested_at=_dt("2026-11-06T00:00:00"),
    )
    assert replay("acme", [row])[0].attributes == {}


def test_hang_khac_tenant_thi_tu_choi():
    rows = [
        _row("c1", "A", "2026-11-01T10:00:00"),
        _row("c2", "X", "2026-11-01T10:01:00", tenant="globex"),
    ]
    with pytest.raises(ValueError, match="không phải acme"):
        replay("acme", rows)


def test_payload_thieu_activity_thi_tu_choi():
    row = EpisodeRow(
        id=UUID(int=1),
        tenant_id="acme",
        case_id="c1",
        payload={},
        occurred_at=_dt("2026-11-01T10:00:00"),
        ingested_at=_dt("2026-11-06T00:00:00"),
    )
    with pytest.raises(ValueError, match="thiếu 'activity'"):
        replay("acme", [row])


def test_payload_activity_khong_phai_chuoi_thi_tu_choi():
    row = EpisodeRow(
        id=UUID(int=1),
        tenant_id="acme",
        case_id="c1",
        payload={"activity": 42},
        occurred_at=_dt("2026-11-01T10:00:00"),
        ingested_at=_dt("2026-11-06T00:00:00"),
    )
    with pytest.raises(ValueError, match="thiếu 'activity'"):
        replay("acme", [row])


def test_payload_case_attributes_khong_phai_dict_thi_tu_choi():
    row = EpisodeRow(
        id=UUID(int=1),
        tenant_id="acme",
        case_id="c1",
        payload={"activity": "A", "case_attributes": "xay-dung"},
        occurred_at=_dt("2026-11-01T10:00:00"),
        ingested_at=_dt("2026-11-06T00:00:00"),
    )
    with pytest.raises(ValueError, match="phải là dict"):
        replay("acme", [row])


def test_cung_dau_vao_ra_dung_ket_qua_cu():
    rows = [
        _row("c1", "B", "2026-11-01T10:02:00"),
        _row("c1", "A", "2026-11-01T10:00:00"),
    ]
    assert replay("acme", rows) == replay("acme", rows)


def test_khong_import_bat_cu_module_mo_hinh_nao():
    source = (
        Path(__file__).parent.parent
        / "packages"
        / "core"
        / "src"
        / "praxon_core"
        / "learning"
        / "generator.py"
    ).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not {
        name
        for name in imported
        if name.startswith("praxon_core.adapters") or name in {"openai", "anthropic"}
    }
