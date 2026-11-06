"""Chỉ mục vị trí đầu/cuối: một lần duyệt ghi đúng vị trí đầu và cuối."""

from praxon_core.declare.index import (
    ActivityIndex,
    ActivitySpan,
    Trace,
    build_index,
    precedence_holds,
    response_holds,
)


def test_trace_rong_thi_chi_muc_rong():
    assert build_index(Trace(events=())) == {}


def test_mot_hoat_dong_thi_dau_bang_cuoi():
    assert build_index(Trace(events=("a",))) == {"a": ActivitySpan(first=0, last=0)}


def test_cac_hoat_dong_khac_nhau_thi_dau_bang_cuoi_bang_vi_tri():
    index = build_index(Trace(events=("a", "b", "c")))
    assert index == {
        "a": ActivitySpan(first=0, last=0),
        "b": ActivitySpan(first=1, last=1),
        "c": ActivitySpan(first=2, last=2),
    }


def test_hoat_dong_lap_lai_thi_dau_la_lan_dau_cuoi_la_lan_cuoi():
    index = build_index(Trace(events=("a", "b", "a", "c", "a")))
    assert index["a"] == ActivitySpan(first=0, last=4)
    assert index["b"] == ActivitySpan(first=1, last=1)
    assert index["c"] == ActivitySpan(first=3, last=3)


def test_hoat_dong_xen_ke_nhau_ghi_dung_ca_hai_dau():
    index = build_index(Trace(events=("x", "y", "x", "y", "x")))
    assert index["x"] == ActivitySpan(first=0, last=4)
    assert index["y"] == ActivitySpan(first=1, last=3)


def test_xay_chi_muc_khong_doi_trace_goc():
    trace = Trace(events=("a", "b", "a"))
    build_index(trace)
    assert trace.events == ("a", "b", "a")


def test_response_dung_khi_b_sau_lan_a_cuoi():
    index = build_index(Trace(events=("a", "b")))
    assert response_holds(index, "a", "b") is True


def test_response_dung_khi_b_xuat_hien_lai_sau_lan_a_cuoi():
    index = build_index(Trace(events=("a", "b", "a", "b")))
    assert response_holds(index, "a", "b") is True


def test_response_sai_khi_b_chi_truoc_lan_a_cuoi():
    index = build_index(Trace(events=("b", "a")))
    assert response_holds(index, "a", "b") is False


def test_response_sai_khi_b_o_giua_hai_lan_a_nhung_khong_sau_lan_cuoi():
    index = build_index(Trace(events=("a", "b", "a")))
    assert response_holds(index, "a", "b") is False


def test_response_dung_khi_a_vang():
    index = build_index(Trace(events=("b", "c")))
    assert response_holds(index, "a", "b") is True


def test_response_dung_khi_a_vang_tren_trace_rong():
    index = build_index(Trace(events=()))
    assert response_holds(index, "a", "b") is True


def test_response_sai_khi_a_co_ma_b_vang():
    index = build_index(Trace(events=("a", "c")))
    assert response_holds(index, "a", "b") is False


def test_response_dung_khi_b_sau_lan_a_cuoi_du_a_lap_nhieu_lan():
    index = build_index(Trace(events=("a", "a", "b")))
    assert response_holds(index, "a", "b") is True


def test_response_sai_khi_cung_mot_hoat_dong_va_no_xuat_hien():
    index = build_index(Trace(events=("a", "b", "a")))
    assert response_holds(index, "a", "a") is False


def test_response_dung_khi_cung_mot_hoat_dong_va_no_vang():
    index = build_index(Trace(events=("x", "y")))
    assert response_holds(index, "a", "a") is True


def test_precedence_dung_khi_lan_a_dau_truoc_lan_b_dau():
    index = build_index(Trace(events=("a", "b")))
    assert precedence_holds(index, "a", "b") is True


def test_precedence_dung_khi_a_lap_lai_sau_b_nhung_lan_dau_van_truoc():
    index = build_index(Trace(events=("a", "x", "b", "a")))
    assert precedence_holds(index, "a", "b") is True


def test_precedence_sai_khi_b_xuat_hien_truoc_a():
    index = build_index(Trace(events=("b", "a")))
    assert precedence_holds(index, "a", "b") is False


def test_precedence_sai_khi_b_lap_lai_truoc_lan_a_dau():
    index = build_index(Trace(events=("b", "b", "a")))
    assert precedence_holds(index, "a", "b") is False


def test_precedence_dung_khi_b_vang():
    index = build_index(Trace(events=("a", "c")))
    assert precedence_holds(index, "a", "b") is True


def test_precedence_dung_khi_b_vang_tren_trace_rong():
    index = build_index(Trace(events=()))
    assert precedence_holds(index, "a", "b") is True


def test_precedence_sai_khi_b_co_ma_a_vang():
    index = build_index(Trace(events=("b", "c")))
    assert precedence_holds(index, "a", "b") is False


def test_precedence_dung_khi_a_lap_nhieu_lan_nhung_lan_dau_truoc_b():
    index = build_index(Trace(events=("a", "a", "b")))
    assert precedence_holds(index, "a", "b") is True


def test_precedence_sai_khi_cung_mot_hoat_dong_va_no_xuat_hien():
    index = build_index(Trace(events=("a", "b", "a")))
    assert precedence_holds(index, "a", "a") is False


def test_precedence_dung_khi_cung_mot_hoat_dong_va_no_vang():
    index = build_index(Trace(events=("x", "y")))
    assert precedence_holds(index, "a", "a") is True


def test_chi_muc_la_dict_tu_ten_hoat_dong_sang_khoang_vi_tri():
    index: ActivityIndex = build_index(Trace(events=("a", "a")))
    assert set(index) == {"a"}
    assert index["a"].first == 0
    assert index["a"].last == 1
