"""Khoảng tin cậy bootstrap: cùng seed ra cùng khoảng, số lần rút trong cấu hình."""

from collections.abc import Sequence

import pytest

from praxon_core.declare.index import Trace
from praxon_core.eval.bootstrap import bootstrap_confidence_interval
from praxon_core.eval.metrics import Fact, FactScope, violation_rate
from praxon_core.learning.candidate import FactStatus
from praxon_core.settings import Settings, load_settings


def _mean(cases: Sequence[float]) -> float:
    return sum(cases) / len(cases)


def _so_muoi() -> list[float]:
    return [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]


def test_cung_seed_ra_cung_khoang():
    lower_a, upper_a = bootstrap_confidence_interval(_mean, _so_muoi(), n_draws=200, seed=42)
    lower_b, upper_b = bootstrap_confidence_interval(_mean, _so_muoi(), n_draws=200, seed=42)
    assert (lower_a, upper_a) == (lower_b, upper_b)


def test_khoang_nam_trong_mien_gia_tri_cua_chi_so():
    lower, upper = bootstrap_confidence_interval(_mean, _so_muoi(), n_draws=200, seed=7)
    assert 1.0 <= lower <= upper <= 10.0


def test_so_lan_rut_dung_so_lan_goi_chi_so():
    calls: list[int] = []

    def metric(cases: Sequence[float]) -> float:
        calls.append(1)
        return _mean(cases)

    bootstrap_confidence_interval(metric, _so_muoi(), n_draws=50, seed=1)
    assert len(calls) == 50
    bootstrap_confidence_interval(metric, _so_muoi(), n_draws=200, seed=1)
    assert len(calls) == 250


def test_so_lan_rut_khong_duong_thi_bao_loi():
    with pytest.raises(ValueError):
        bootstrap_confidence_interval(_mean, _so_muoi(), n_draws=0, seed=1)


def test_khong_co_case_thi_bao_loi():
    with pytest.raises(ValueError):
        bootstrap_confidence_interval(_mean, [], n_draws=10, seed=1)


def test_do_tin_cay_ngoai_khoang_thi_bao_loi():
    with pytest.raises(ValueError):
        bootstrap_confidence_interval(_mean, _so_muoi(), n_draws=10, seed=1, confidence=1.0)
    with pytest.raises(ValueError):
        bootstrap_confidence_interval(_mean, _so_muoi(), n_draws=10, seed=1, confidence=0.0)


def test_so_lan_rut_nam_trong_cau_hinh(tmp_path):
    path = tmp_path / "praxon.toml"
    path.write_text(
        'database_url = "postgresql://localhost/praxon"\nbootstrap_draws = 50\n',
        encoding="utf-8",
    )
    assert load_settings(path).bootstrap_draws == 50


def test_so_lan_rut_mac_dinh_khi_khong_ghi_trong_cau_hinh(tmp_path):
    path = tmp_path / "praxon.toml"
    path.write_text('database_url = "postgresql://localhost/praxon"\n', encoding="utf-8")
    assert load_settings(path).bootstrap_draws == 1000
    assert Settings(database_url="postgresql://localhost/praxon").bootstrap_draws == 1000


def test_bootstrap_tren_ti_le_vi_pham_cua_8_2():
    """Dùng hàm chỉ số của 8.2 làm metric cho bootstrap: cùng seed ra cùng khoảng."""
    facts = [
        Fact(
            canonical_key="response(a, b)",
            template="response",
            activation="a",
            target="b",
            status=FactStatus.ACTIVE,
            scope=FactScope.TENANT,
            tenant_id="acme",
        ),
        Fact(
            canonical_key="response(c, d)",
            template="response",
            activation="c",
            target="d",
            status=FactStatus.ACTIVE,
            scope=FactScope.TENANT,
            tenant_id="acme",
        ),
    ]
    traces = [
        Trace(events=("b", "a")),
        Trace(events=("a",)),
        Trace(events=("a", "b", "c", "d")),
        Trace(events=("a", "b", "c", "d")),
        Trace(events=("a", "b", "c", "d")),
    ]

    def metric(sampled: Sequence[Trace]) -> float:
        return violation_rate(facts, sampled)

    lower_a, upper_a = bootstrap_confidence_interval(metric, traces, n_draws=100, seed=7)
    lower_b, upper_b = bootstrap_confidence_interval(metric, traces, n_draws=100, seed=7)
    assert (lower_a, upper_a) == (lower_b, upper_b)
    assert 0.0 <= lower_a <= upper_a <= 1.0
