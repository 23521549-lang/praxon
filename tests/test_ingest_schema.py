"""Schema: model frozen, từ chối trường lạ, thiếu trường và case_id rỗng."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from praxon_core.ingest.schema import Event


def _base() -> dict[str, str]:
    """Một event hợp lệ dạng dict thô."""
    return {
        "case_id": "c1",
        "variant": "standard",
        "activity": "approve",
        "occurred_at": "2015-06-01T10:00:00+07:00",
    }


def test_event_hop_le_va_timestamp_ve_utc():
    e = Event.model_validate(_base())
    assert e.case_id == "c1"
    assert e.activity == "approve"
    assert e.occurred_at.isoformat() == "2015-06-01T03:00:00+00:00"


def test_event_bat_bien_frozen():
    # Event là "1 dòng bất biến": đọc xong không ai sửa được.
    e = Event.model_validate(_base())
    with pytest.raises(ValidationError):
        e.activity = "khac"


def test_tu_choi_truong_la():
    # Trường lạ phải bị từ chối ngay lúc nạp, không được bỏ qua im lặng.
    with pytest.raises(ValidationError):
        Event.model_validate({**_base(), "resource": "nguoi_dung"})


def test_tu_choi_thieu_truong_bat_buoc():
    with pytest.raises(ValidationError):
        Event.model_validate({"case_id": "c1"})


def test_case_id_rong_sau_trim_bi_tu_choi():
    with pytest.raises(ValidationError):
        Event.model_validate({**_base(), "case_id": "   "})


def test_truong_khong_phai_chuoi_bi_tu_choi():
    # Validator chỉ chuẩn hoá chuỗi; kiểu sai thì pydantic từ chối.
    with pytest.raises(ValidationError):
        Event.model_validate({**_base(), "case_id": 123})
    with pytest.raises(ValidationError):
        Event.model_validate({**_base(), "activity": 123})


def test_occurred_at_kieu_la_bi_tu_choi_tuong_minh():
    # Bẫy đã kiểm ngày 16/10/2026: pydantic tự ép int thành datetime (unix
    # timestamp) nên validator phải từ chối tường minh, không để lọt.
    with pytest.raises(ValidationError):
        Event.model_validate({**_base(), "occurred_at": 123})
