"""Cổng Beta và cận dưới Wilson (task 7.4): số đếm biết trước."""

from __future__ import annotations

from typing import Any

import pytest

from praxon_core.learning.beta import (
    Prior,
    beta_cdf,
    beta_prob_ge,
    posterior_prob_ge,
    prior_prob_ge,
    prior_to_beta,
    wilson_lower,
)
from praxon_core.learning.candidate import Candidate, FactStatus
from praxon_core.learning.governor import decide
from praxon_core.learning.measures import Measures
from praxon_core.learning.rules import default_rule_table


def _candidate(**overrides: object) -> Candidate:
    data: dict[str, Any] = {
        "target_scope": "acme",
        "payload": {"template": "response", "a": "a", "b": "b"},
        "rationale": "đề xuất thử",
        "evidence_episode_ids": ["e1"],
        "status": "pending",
    }
    data.update(overrides)
    return Candidate(**data)


def _measures(**overrides: object) -> Measures:
    data: dict[str, Any] = {
        "has_direct_conflict": False,
        "schema_valid": True,
        "from_trace": False,
        "wilson_lower": 0.0,
        "beta_prob": 0.5,
        "is_scope_promotion": False,
        "from_global": False,
        "has_condition": False,
        "matching_cases": 0,
        "fact_status": None,
        "is_new": True,
        "human_early_activate": False,
        "has_rubric_clause": False,
    }
    data.update(overrides)
    return Measures(**data)


def test_wilson_tren_so_dem_biet_truoc():
    assert wilson_lower(10, 10) == pytest.approx(0.7224, abs=1e-4)
    assert wilson_lower(9, 10) == pytest.approx(0.5959, abs=1e-4)
    assert wilson_lower(0, 10) == pytest.approx(0.0)
    assert wilson_lower(25, 25) == pytest.approx(0.8668, abs=1e-4)
    assert wilson_lower(5, 10) == pytest.approx(0.2366, abs=1e-4)
    assert wilson_lower(1, 1) == pytest.approx(0.2065, abs=1e-4)


def test_wilson_tu_choi_so_dem_sai():
    with pytest.raises(ValueError):
        wilson_lower(0, 0)
    with pytest.raises(ValueError):
        wilson_lower(11, 10)
    with pytest.raises(ValueError):
        wilson_lower(-1, 10)
    with pytest.raises(ValueError):
        wilson_lower(5, 10, z=0.0)


def test_beta_cdf_tren_tham_so_biet_truoc():
    # Beta(a, 1): CDF = x^a.
    assert beta_cdf(0.7, 5.0, 1.0) == pytest.approx(0.7**5)
    assert beta_cdf(0.7, 9.0, 1.0) == pytest.approx(0.7**9)
    # Beta(1, 1) là đều: CDF = x.
    assert beta_cdf(0.7, 1.0, 1.0) == pytest.approx(0.7)
    # Beta(2, 2): CDF = 3x^2 - 2x^3.
    assert beta_cdf(0.7, 2.0, 2.0) == pytest.approx(0.784)
    # Beta(3, 2): CDF = 4x^3 - 3x^4.
    assert beta_cdf(0.7, 3.0, 2.0) == pytest.approx(0.6517)
    assert beta_cdf(0.0, 2.0, 2.0) == pytest.approx(0.0)
    assert beta_cdf(1.0, 2.0, 2.0) == pytest.approx(1.0)
    # Đối xứng: I_x(a, b) = 1 - I_{1-x}(b, a).
    assert beta_cdf(0.3, 2.0, 5.0) == pytest.approx(1.0 - beta_cdf(0.7, 5.0, 2.0))


def test_beta_prob_ge_tren_tham_so_biet_truoc():
    assert beta_prob_ge(5.0, 1.0, 0.7) == pytest.approx(0.83193, abs=1e-5)
    assert beta_prob_ge(9.0, 1.0, 0.7) == pytest.approx(0.95965, abs=1e-5)
    assert beta_prob_ge(1.0, 1.0, 0.7) == pytest.approx(0.3)
    assert beta_prob_ge(2.0, 2.0, 0.7) == pytest.approx(0.216)
    assert beta_prob_ge(3.0, 2.0, 0.7) == pytest.approx(0.3483, abs=1e-4)


def test_beta_tu_choi_tham_so_sai():
    with pytest.raises(ValueError):
        beta_cdf(0.5, 0.0, 1.0)
    with pytest.raises(ValueError):
        beta_cdf(0.5, 1.0, -1.0)
    with pytest.raises(ValueError):
        beta_cdf(1.5, 1.0, 1.0)
    with pytest.raises(ValueError):
        beta_cdf(-0.1, 1.0, 1.0)


def test_tien_nghiem_thanh_beta():
    assert prior_to_beta(Prior(canonical_key="k", confidence=1.0, strength=8.0), 4.0) == (
        9.0,
        1.0,
    )
    assert prior_to_beta(Prior(canonical_key="k", confidence=0.5, strength=None), 4.0) == (
        3.0,
        3.0,
    )
    assert prior_to_beta(Prior(canonical_key="k", confidence=0.0, strength=4.0), 4.0) == (
        1.0,
        5.0,
    )
    with pytest.raises(ValueError):
        prior_to_beta(Prior(canonical_key="k", confidence=0.5), 0.0)


def test_hau_nghiem_tu_tien_nghiem_mot_minh():
    # Độ tin 1,0 độ mạnh 8: tiên nghiệm một mình đã ≥ 0,95 (bị từ chối ở 7.5).
    prior_manh = Prior(canonical_key="k", confidence=1.0, strength=8.0)
    assert prior_prob_ge(prior_manh, 0.7, strength_default=4.0) == pytest.approx(
        0.95965, abs=1e-5
    )
    # Độ tin 1,0 độ mạnh mặc định 4: tiên nghiệm một mình dưới 0,95.
    prior_mac_dinh = Prior(canonical_key="k", confidence=1.0, strength=None)
    assert prior_prob_ge(prior_mac_dinh, 0.7, strength_default=4.0) == pytest.approx(
        0.83193, abs=1e-5
    )


def test_tien_nghiem_tu_choi_nguong_sai():
    prior = Prior(canonical_key="k", confidence=0.5, strength=4.0)
    with pytest.raises(ValueError):
        prior_prob_ge(prior, 1.5, strength_default=4.0)


def test_hau_nghiem_tu_choi_so_dem_sai():
    prior = Prior(canonical_key="k", confidence=0.5, strength=4.0)
    with pytest.raises(ValueError):
        posterior_prob_ge(prior, 1, 0, 0.7, strength_default=4.0)
    with pytest.raises(ValueError):
        posterior_prob_ge(prior, 0, 10, 1.5, strength_default=4.0)


def test_luat_2_tu_wilson_10_tren_10():
    table = default_rule_table()
    result = decide(
        _candidate(),
        table,
        _measures(from_trace=True, wilson_lower=wilson_lower(10, 10)),
    )
    assert result.decision.rule_id == 2
    assert result.decision.verdict.value == "auto_approve"
    assert result.decision.target_status == FactStatus.TRIAL


def test_luat_2_tu_choi_khi_wilson_9_tren_10():
    table = default_rule_table()
    result = decide(
        _candidate(),
        table,
        _measures(from_trace=True, wilson_lower=wilson_lower(9, 10)),
    )
    assert result.decision.rule_id == 9
    assert result.decision.verdict.value == "wait"


def test_luat_3_tu_hau_nghiem_beta():
    table = default_rule_table()
    prior = Prior(canonical_key="k", confidence=0.8, strength=4.0)
    prob = posterior_prob_ge(prior, 20, 20, 0.7, strength_default=4.0)
    assert prob >= 0.95
    result = decide(
        _candidate(),
        table,
        _measures(is_new=False, fact_status=FactStatus.TRIAL, beta_prob=prob),
    )
    assert result.decision.rule_id == 3
    assert result.decision.verdict.value == "auto_approve"
    assert result.decision.target_status == FactStatus.ACTIVE


def test_luat_4_tu_hau_nghiem_beta():
    table = default_rule_table()
    prior = Prior(canonical_key="k", confidence=0.2, strength=4.0)
    prob = posterior_prob_ge(prior, 0, 20, 0.7, strength_default=4.0)
    assert prob < 0.05
    result = decide(
        _candidate(),
        table,
        _measures(is_new=False, fact_status=FactStatus.ACTIVE, beta_prob=prob),
    )
    assert result.decision.rule_id == 4
    assert result.decision.verdict.value == "auto_approve"
    assert result.decision.target_status == FactStatus.RETIRED


def test_luat_7_du_lieu_thoa_dieu_kien_it_hon_30_case():
    table = default_rule_table()
    result = decide(
        _candidate(),
        table,
        _measures(
            from_trace=True,
            wilson_lower=wilson_lower(10, 10),
            has_condition=True,
            matching_cases=10,
        ),
    )
    assert result.decision.rule_id == 7
    assert result.decision.verdict.value == "reject"


def test_luat_2_du_lieu_thoa_dieu_kien_du_30_case():
    table = default_rule_table()
    result = decide(
        _candidate(),
        table,
        _measures(
            from_trace=True,
            wilson_lower=wilson_lower(10, 10),
            has_condition=True,
            matching_cases=30,
        ),
    )
    assert result.decision.rule_id == 2
    assert result.decision.target_status == FactStatus.TRIAL
