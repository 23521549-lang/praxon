"""Lệnh tính kappa: Cohen's kappa trên nhãn của hai người duyệt, ngưỡng 0,61."""

import pytest

from praxon_core.eval.kappa import KAPPA_THRESHOLD, cohen_kappa, kappa_meets_threshold


def test_dong_y_o_muc_ngau_nhien_thi_kappa_bang_khong():
    """Hai người đồng ý 2/4, đúng bằng kỳ vọng ngẫu nhiên → kappa = 0."""
    assert cohen_kappa(["yes", "yes", "no", "no"], ["yes", "no", "yes", "no"]) == pytest.approx(
        0.0
    )


def test_dong_y_tuyet_doi_thi_kappa_bang_mot():
    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == pytest.approx(1.0)


def test_kappa_nua_thi_chua_dat_nguong():
    """Po = 0,75, Pe = 0,5 → kappa = 0,5, dưới ngưỡng 0,61."""
    first = ["yes", "yes", "yes", "no", "no", "no", "yes", "no"]
    second = ["yes", "yes", "no", "no", "no", "yes", "yes", "no"]
    kappa = cohen_kappa(first, second)
    assert kappa == pytest.approx(0.5)
    assert kappa_meets_threshold(kappa) is False


def test_duyet_cheo_20_quyet_dinh_dat_nguong():
    """Đồng ý 18/20, Pe = 0,52 → kappa = 19/24 ≈ 0,79, đạt ngưỡng."""
    first = ["approve"] * 11 + ["reject"] * 7 + ["approve", "reject"]
    second = ["approve"] * 11 + ["reject"] * 7 + ["reject", "approve"]
    kappa = cohen_kappa(first, second)
    assert kappa == pytest.approx(19 / 24)
    assert kappa_meets_threshold(kappa) is True


def test_ca_hai_luon_cham_cung_mot_nhan_thi_kappa_bang_mot():
    """Pe = 1 (chỉ một nhãn được dùng) thì kappa quy ước là 1.0."""
    assert cohen_kappa(["yes"] * 5, ["yes"] * 5) == pytest.approx(1.0)


def test_nguong_dung_0_61_thi_dat_sai_thi_khong():
    assert pytest.approx(0.61) == KAPPA_THRESHOLD
    assert kappa_meets_threshold(0.61) is True
    assert kappa_meets_threshold(0.60) is False
    assert kappa_meets_threshold(1.0) is True


def test_khong_co_nhan_thi_bao_loi():
    with pytest.raises(ValueError):
        cohen_kappa([], [])


def test_hai_day_khac_do_dai_thi_bao_loi():
    with pytest.raises(ValueError):
        cohen_kappa(["a", "b"], ["a"])
