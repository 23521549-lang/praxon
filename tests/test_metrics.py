"""Bốn chỉ số: tenant giả có đáp án biết trước, mỗi chỉ số có ca ra khác 0."""

import pytest

from praxon_core.declare.index import Trace
from praxon_core.eval.metrics import (
    Fact,
    FactScope,
    Metrics,
    compute_metrics,
    f1_score,
    negative_transfer,
    precision,
    recall,
    violation_rate,
)
from praxon_core.learning.candidate import FactStatus

TENANT = "acme"


def _fact(
    key: str,
    template: str,
    a: str,
    b: str,
    scope: FactScope,
    tenant: str,
    status: FactStatus = FactStatus.ACTIVE,
) -> Fact:
    return Fact(
        canonical_key=key,
        template=template,
        activation=a,
        target=b,
        status=status,
        scope=scope,
        tenant_id=tenant,
    )


def _bo_bon_fact() -> list[Fact]:
    """Bốn fact active của tenant acme; ba cái trong đáp án, một cái học sai."""
    return [
        _fact("response(a, b)", "response", "a", "b", FactScope.TENANT, TENANT),
        _fact("precedence(c, d)", "precedence", "c", "d", FactScope.TENANT, TENANT),
        _fact("response(e, f)", "response", "e", "f", FactScope.GLOBAL, "global"),
        _fact("response(x, y)", "response", "x", "y", FactScope.TENANT, TENANT),
    ]


def _dap_an() -> set[str]:
    return {
        "response(a, b)",
        "precedence(c, d)",
        "response(e, f)",
        "precedence(g, h)",
    }


def _muoi_trace() -> list[Trace]:
    """10 trace đo.

    Trace 1-2 vi phạm response(e, f); trace 3 vi phạm precedence(c, d);
    trace 4-10 không vi phạm fact nào.
    """
    return [
        Trace(events=("f", "e")),
        Trace(events=("e",)),
        Trace(events=("d", "c")),
        Trace(events=("a", "b", "c", "d", "e", "f", "x", "y")),
        Trace(events=("a", "b", "c", "d", "e", "f", "x", "y")),
        Trace(events=("a", "b", "c", "d", "e", "f", "x", "y")),
        Trace(events=("a", "b", "c", "d", "e", "f", "x", "y")),
        Trace(events=("a", "b", "c", "d", "e", "f", "x", "y")),
        Trace(events=("a", "b", "c", "d", "e", "f", "x", "y")),
        Trace(events=("a", "b", "c", "d", "e", "f", "x", "y")),
    ]


def test_precision_ba_tren_bon_fact_active_co_trong_dap_an():
    assert precision(_bo_bon_fact(), _dap_an()) == pytest.approx(0.75)


def test_recall_ba_tren_bon_dap_an_co_trong_fact_active():
    assert recall(_bo_bon_fact(), _dap_an()) == pytest.approx(0.75)


def test_ti_le_vi_pham_mot_tren_bon_fact_active():
    assert violation_rate(_bo_bon_fact(), _muoi_trace()) == pytest.approx(0.25)


def test_negative_transfer_mot_tren_bon_vi_pham_tu_global():
    assert negative_transfer(_bo_bon_fact(), _muoi_trace(), TENANT) == pytest.approx(0.25)


def test_bon_chi_so_bao_cung_nhau():
    result = compute_metrics(_bo_bon_fact(), _dap_an(), _muoi_trace(), TENANT)
    assert result.precision == pytest.approx(0.75)
    assert result.recall == pytest.approx(0.75)
    assert result.violation_rate == pytest.approx(0.25)
    assert result.negative_transfer == pytest.approx(0.25)


def test_fact_vi_pham_dung_muoi_phan_tram_thi_chua_tinh():
    """precedence(c, d) vi phạm đúng 1/10 trace thì chưa quá 10% nên không tính."""
    facts = [_fact("precedence(c, d)", "precedence", "c", "d", FactScope.TENANT, TENANT)]
    traces = [Trace(events=("d", "c"))] + [Trace(events=("c", "d")) for _ in range(9)]
    assert violation_rate(facts, traces) == pytest.approx(0.0)


def test_fact_vi_pham_vuot_muoi_phan_tram_thi_tinh():
    facts = [_fact("response(e, f)", "response", "e", "f", FactScope.GLOBAL, "global")]
    traces = [Trace(events=("f", "e")), Trace(events=("e",))] + [
        Trace(events=("e", "f")) for _ in range(8)
    ]
    assert violation_rate(facts, traces) == pytest.approx(1.0)
    assert negative_transfer(facts, traces, TENANT) == pytest.approx(1.0)


def test_fact_cua_tenant_khac_bi_vi_pham_thi_tinh_vao_negative_transfer():
    """Fact scope tenant nhưng của tenant khác (kho gộp) cũng là nguồn ngoài."""
    facts = [_fact("response(a, b)", "response", "a", "b", FactScope.TENANT, "globex")]
    traces = [Trace(events=("b", "a"))]
    assert violation_rate(facts, traces) == pytest.approx(1.0)
    assert negative_transfer(facts, traces, TENANT) == pytest.approx(1.0)
    assert negative_transfer(facts, traces, "globex") == pytest.approx(0.0)


def test_fact_trial_va_retired_khong_vao_chi_so():
    facts = [
        *_bo_bon_fact(),
        _fact(
            "response(q, r)",
            "response",
            "q",
            "r",
            FactScope.TENANT,
            TENANT,
            status=FactStatus.TRIAL,
        ),
        _fact(
            "response(s, t)",
            "response",
            "s",
            "t",
            FactScope.TENANT,
            TENANT,
            status=FactStatus.RETIRED,
        ),
    ]
    assert precision(facts, _dap_an()) == pytest.approx(0.75)
    assert recall(facts, _dap_an()) == pytest.approx(0.75)
    assert violation_rate(facts, _muoi_trace()) == pytest.approx(0.25)


def test_khong_co_fact_active_thi_bon_chi_so_bang_khong():
    facts = [
        _fact(
            "response(a, b)",
            "response",
            "a",
            "b",
            FactScope.TENANT,
            TENANT,
            status=FactStatus.TRIAL,
        )
    ]
    assert precision(facts, _dap_an()) == 0.0
    assert recall(facts, _dap_an()) == 0.0
    assert violation_rate(facts, _muoi_trace()) == 0.0
    assert negative_transfer(facts, _muoi_trace(), TENANT) == 0.0
    assert compute_metrics(facts, _dap_an(), _muoi_trace(), TENANT) == Metrics(
        precision=0.0, recall=0.0, violation_rate=0.0, negative_transfer=0.0
    )


def test_dap_an_rong_thi_recall_bang_khong():
    assert recall(_bo_bon_fact(), set()) == 0.0


def test_khong_co_trace_do_thi_ti_le_vi_pham_bang_khong():
    assert violation_rate(_bo_bon_fact(), []) == 0.0
    assert negative_transfer(_bo_bon_fact(), [], TENANT) == 0.0


def test_mau_khong_ho_tro_thi_bao_loi():
    facts = [_fact("response(a, b)", "succession", "a", "b", FactScope.TENANT, TENANT)]
    with pytest.raises(ValueError):
        violation_rate(facts, _muoi_trace())


def test_f1_la_trung_binh_dieu_hoa_cua_precision_va_recall():
    assert f1_score(1.0, 1.0) == 1.0
    assert f1_score(1.0, 0.0) == 0.0
    assert f1_score(0.0, 0.0) == 0.0
    assert abs(f1_score(1.0, 20 / 56) - 0.5263157894736842) < 1e-12
    assert abs(f1_score(0.5, 0.5) - 0.5) < 1e-12
