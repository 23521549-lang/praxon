"""Bất biến tiên nghiệm (task 7.5): kiểm theo từng luật lúc nạp gói."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from praxon_core.learning.beta import (
    Prior,
    PriorInvariantError,
    check_prior_invariant,
)
from praxon_core.learning.rules import RuleTable, default_rule_table, load_rule_table


def _load_table(tmp_path: Path, body: str) -> RuleTable:
    path = tmp_path / "bang.toml"
    path.write_text(body, encoding="utf-8")
    return load_rule_table(path)


_POLICY = """
[policy]
confidence_threshold = 0.7
promote_probability = 0.95
retire_probability = 0.05
prior_strength_default = 4
min_matching_cases = 30
"""

_RULE = """
[[rules]]
id = 1
applies_to = "thử"
verdict = "wait"
[rules.condition]
kind = "all"
children = []
"""


def test_goi_co_luat_do_tin_1_do_manh_8_bi_tu_choi():
    priors = [Prior(canonical_key="luật 1", confidence=1.0, strength=8.0)]
    with pytest.raises(PriorInvariantError, match="luật 1"):
        check_prior_invariant(
            priors,
            confidence_threshold=0.7,
            promote_probability=0.95,
            prior_strength_default=4.0,
        )


def test_do_manh_mac_dinh_4_duoc_nhan():
    priors = [Prior(canonical_key="luật 1", confidence=1.0, strength=None)]
    check_prior_invariant(
        priors,
        confidence_threshold=0.7,
        promote_probability=0.95,
        prior_strength_default=4.0,
    )


def test_tran_an_toan_theo_do_tin():
    # Spec: trần dưới 10,3 ở độ tin 0,95; dưới 7,4 ở độ tin 1,0.
    check_prior_invariant(
        [Prior(canonical_key="a", confidence=0.95, strength=8.0)],
        confidence_threshold=0.7,
        promote_probability=0.95,
        prior_strength_default=4.0,
    )
    check_prior_invariant(
        [Prior(canonical_key="a", confidence=0.95, strength=10.0)],
        confidence_threshold=0.7,
        promote_probability=0.95,
        prior_strength_default=4.0,
    )
    with pytest.raises(PriorInvariantError):
        check_prior_invariant(
            [Prior(canonical_key="a", confidence=0.95, strength=11.0)],
            confidence_threshold=0.7,
            promote_probability=0.95,
            prior_strength_default=4.0,
        )
    check_prior_invariant(
        [Prior(canonical_key="a", confidence=1.0, strength=7.0)],
        confidence_threshold=0.7,
        promote_probability=0.95,
        prior_strength_default=4.0,
    )
    with pytest.raises(PriorInvariantError):
        check_prior_invariant(
            [Prior(canonical_key="a", confidence=1.0, strength=8.0)],
            confidence_threshold=0.7,
            promote_probability=0.95,
            prior_strength_default=4.0,
        )


def test_mot_luat_xau_tu_choi_ca_goi_va_neu_ten():
    priors = [
        Prior(canonical_key="luật tốt", confidence=0.5, strength=4.0),
        Prior(canonical_key="luật xấu", confidence=1.0, strength=8.0),
        Prior(canonical_key="luật tốt 2", confidence=0.8, strength=4.0),
    ]
    with pytest.raises(PriorInvariantError) as exc:
        check_prior_invariant(
            priors,
            confidence_threshold=0.7,
            promote_probability=0.95,
            prior_strength_default=4.0,
        )
    assert "luật xấu" in str(exc.value)
    assert "luật tốt" not in str(exc.value)


def test_goi_toan_luat_tot_duoc_nhan():
    priors = [
        Prior(canonical_key="luật 1", confidence=1.0, strength=4.0),
        Prior(canonical_key="luật 2", confidence=0.95, strength=10.0),
    ]
    check_prior_invariant(
        priors,
        confidence_threshold=0.7,
        promote_probability=0.95,
        prior_strength_default=4.0,
    )


def test_nap_bang_mac_dinh_duoc_nhan():
    table = default_rule_table()
    assert len(table.rules) == 9


def test_nap_bang_do_manh_mac_dinh_20_bi_tu_choi(tmp_path):
    body = _POLICY.replace("prior_strength_default = 4", "prior_strength_default = 20")
    body += _RULE
    with pytest.raises(ValidationError, match="bất biến tiên nghiệm"):
        _load_table(tmp_path, body)


def test_nap_bang_co_luat_do_tin_1_do_manh_8_bi_tu_choi(tmp_path):
    body = (
        _POLICY
        + _RULE
        + """
[rules.prior]
canonical_key = "luật 1"
confidence = 1.0
strength = 8
"""
    )
    with pytest.raises(ValidationError, match="luật 1"):
        _load_table(tmp_path, body)


def test_nap_bang_co_luat_do_tin_1_do_manh_4_duoc_nhan(tmp_path):
    body = (
        _POLICY
        + _RULE
        + """
[rules.prior]
canonical_key = "luật 1"
confidence = 1.0
strength = 4
"""
    )
    table = _load_table(tmp_path, body)
    assert table.rules[0].prior is not None
    assert table.rules[0].prior.confidence == 1.0
