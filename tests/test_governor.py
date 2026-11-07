"""Governor (task 7.3): nạp bảng luật bằng Pydantic, chín luật theo thứ tự."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from praxon_core.learning.candidate import Candidate, DecisionVerdict, FactStatus
from praxon_core.learning.governor import _compare, decide
from praxon_core.learning.measures import Measures
from praxon_core.learning.rules import RuleTable, default_rule_table, load_rule_table


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


def test_bang_mac_dinh_nap_du_9_luat_va_tham_so():
    table = default_rule_table()
    assert [rule.id for rule in table.rules] == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert table.policy.confidence_threshold == 0.7
    assert table.policy.promote_probability == 0.95
    assert table.policy.retire_probability == 0.05
    assert table.policy.prior_strength_default == 2
    assert table.policy.min_matching_cases == 30


def test_tu_choi_dai_luong_la(tmp_path):
    body = (
        _POLICY
        + """
[[rules]]
id = 1
applies_to = "thử"
verdict = "needs_human"
[rules.condition]
kind = "compare"
measure = "do_tin"
op = "=="
value = true
"""
    )
    with pytest.raises(ValidationError):
        _load_table(tmp_path, body)


def test_tu_choi_phep_so_sanh_la(tmp_path):
    body = (
        _POLICY
        + """
[[rules]]
id = 1
applies_to = "thử"
verdict = "needs_human"
[rules.condition]
kind = "compare"
measure = "schema_valid"
op = "~="
value = true
"""
    )
    with pytest.raises(ValidationError):
        _load_table(tmp_path, body)


def test_tu_choi_gia_tri_sai_kieu(tmp_path):
    bad_values = [
        ("wilson_lower", '"cao"'),
        ("has_direct_conflict", "1"),
        ("matching_cases", "-1"),
        ("matching_cases", '"nhiều"'),
        ("fact_status", '"cho"'),
        ("wilson_lower", "1.5"),
        ("beta_prob", "-0.1"),
    ]
    for measure, value in bad_values:
        body = (
            _POLICY
            + f"""
[[rules]]
id = 1
applies_to = "thử"
verdict = "needs_human"
[rules.condition]
kind = "compare"
measure = "{measure}"
op = "=="
value = {value}
"""
        )
        with pytest.raises(ValidationError):
            _load_table(tmp_path, body)


def test_tu_choi_tham_chieu_chinh_sach_la(tmp_path):
    body = (
        _POLICY
        + """
[[rules]]
id = 1
applies_to = "thử"
verdict = "needs_human"
[rules.condition]
kind = "compare"
measure = "wilson_lower"
op = ">="
value = { policy = "nguong_la" }
"""
    )
    with pytest.raises(ValidationError):
        _load_table(tmp_path, body)


def test_tu_choi_luat_trung_so_hieu(tmp_path):
    body = (
        _POLICY
        + """
[[rules]]
id = 1
applies_to = "một"
verdict = "wait"
[rules.condition]
kind = "all"
children = []
[[rules]]
id = 1
applies_to = "hai"
verdict = "wait"
[rules.condition]
kind = "all"
children = []
"""
    )
    with pytest.raises(ValidationError):
        _load_table(tmp_path, body)


def test_tu_choi_bang_rong(tmp_path):
    body = "rules = []\n" + _POLICY
    with pytest.raises(ValidationError):
        _load_table(tmp_path, body)


def test_tu_choi_chinh_sach_nguoc(tmp_path):
    bad_policy = """
[policy]
confidence_threshold = 0.7
promote_probability = 0.05
retire_probability = 0.95
prior_strength_default = 4
min_matching_cases = 30
"""
    body = (
        bad_policy
        + """
[[rules]]
id = 1
applies_to = "thử"
verdict = "wait"
[rules.condition]
kind = "all"
children = []
"""
    )
    with pytest.raises(ValidationError):
        _load_table(tmp_path, body)


def test_tu_choi_phep_in_gia_tri_khong_phai_danh_sach(tmp_path):
    body = (
        _POLICY
        + """
[[rules]]
id = 1
applies_to = "thử"
verdict = "needs_human"
[rules.condition]
kind = "compare"
measure = "fact_status"
op = "in"
value = "trial"
"""
    )
    with pytest.raises(ValidationError):
        _load_table(tmp_path, body)


def test_tu_choi_so_sanh_thu_tu_tren_dai_luong_bool(tmp_path):
    body = (
        _POLICY
        + """
[[rules]]
id = 1
applies_to = "thử"
verdict = "needs_human"
[rules.condition]
kind = "compare"
measure = "has_direct_conflict"
op = ">"
value = true
"""
    )
    with pytest.raises(ValidationError):
        _load_table(tmp_path, body)


def test_nap_bang_khong_phai_dict_bi_tu_choi():
    from praxon_core.learning.rules import RuleTable

    with pytest.raises(ValidationError):
        RuleTable.model_validate("chuỗi")
    with pytest.raises(ValidationError):
        RuleTable.model_validate({"policy": "không phải dict", "rules": []})


def test_tu_choi_dieu_kien_dang_chuoi_khong_co_eval(tmp_path):
    body = (
        _POLICY
        + """
[[rules]]
id = 1
applies_to = "thử"
verdict = "needs_human"
condition = "wilson_lower >= 0.7"
"""
    )
    with pytest.raises(ValidationError):
        _load_table(tmp_path, body)
    body = (
        _POLICY
        + """
[[rules]]
id = 1
applies_to = "thử"
verdict = "needs_human"
[rules.condition]
kind = "eval"
measure = "schema_valid"
op = "=="
value = true
"""
    )
    with pytest.raises(ValidationError):
        _load_table(tmp_path, body)


def test_tu_choi_khoa_la_trong_bang(tmp_path):
    body = (
        _POLICY
        + """
[[rules]]
id = 1
applies_to = "thử"
verdict = "needs_human"
ghi_chu = "thừa"
[rules.condition]
kind = "all"
children = []
"""
    )
    with pytest.raises(ValidationError):
        _load_table(tmp_path, body)


def test_luat_1_mau_thuan_truc_tiep_can_nguoi_duyet():
    table = default_rule_table()
    result = decide(_candidate(), table, _measures(has_direct_conflict=True))
    assert result.decision.verdict is DecisionVerdict.NEEDS_HUMAN
    assert result.decision.rule_id == 1
    assert result.decision.target_status is None


def test_luat_2_rang_buoc_moi_tu_tai_lieu_vao_trial():
    table = default_rule_table()
    result = decide(_candidate(), table, _measures())
    assert result.decision.verdict is DecisionVerdict.AUTO_APPROVE
    assert result.decision.target_status is FactStatus.TRIAL
    assert result.decision.rule_id == 2


def test_luat_2_tu_trace_wilson_du_vao_trial():
    table = default_rule_table()
    result = decide(_candidate(), table, _measures(from_trace=True, wilson_lower=0.8))
    assert result.decision.rule_id == 2
    assert result.decision.target_status is FactStatus.TRIAL


def test_luat_2_tu_trace_wilson_thieu_cho_them_du_lieu():
    table = default_rule_table()
    result = decide(_candidate(), table, _measures(from_trace=True, wilson_lower=0.6))
    assert result.decision.rule_id == 9
    assert result.decision.verdict is DecisionVerdict.WAIT


def test_luat_2_rang_buoc_co_dieu_kien_du_case_vao_trial():
    table = default_rule_table()
    result = decide(
        _candidate(),
        table,
        _measures(has_condition=True, matching_cases=50),
    )
    assert result.decision.rule_id == 2
    assert result.decision.target_status is FactStatus.TRIAL


def test_luat_7_rang_buoc_co_dieu_kien_thieu_case_bi_loai():
    table = default_rule_table()
    result = decide(
        _candidate(),
        table,
        _measures(has_condition=True, matching_cases=10),
    )
    assert result.decision.rule_id == 7
    assert result.decision.verdict is DecisionVerdict.REJECT


def test_luat_3_trial_du_chac_len_active():
    table = default_rule_table()
    result = decide(
        _candidate(),
        table,
        _measures(is_new=False, fact_status=FactStatus.TRIAL, beta_prob=0.97),
    )
    assert result.decision.rule_id == 3
    assert result.decision.verdict is DecisionVerdict.AUTO_APPROVE
    assert result.decision.target_status is FactStatus.ACTIVE


def test_luat_4_trial_thieu_chac_bi_retired():
    table = default_rule_table()
    result = decide(
        _candidate(),
        table,
        _measures(is_new=False, fact_status=FactStatus.TRIAL, beta_prob=0.02),
    )
    assert result.decision.rule_id == 4
    assert result.decision.target_status is FactStatus.RETIRED
    result = decide(
        _candidate(),
        table,
        _measures(is_new=False, fact_status=FactStatus.ACTIVE, beta_prob=0.02),
    )
    assert result.decision.rule_id == 4


def test_luat_5_nang_global_can_nguoi_duyet():
    table = default_rule_table()
    result = decide(
        _candidate(),
        table,
        _measures(is_new=False, fact_status=FactStatus.TRIAL, is_scope_promotion=True),
    )
    assert result.decision.rule_id == 5
    assert result.decision.verdict is DecisionVerdict.NEEDS_HUMAN


def test_luat_6_fact_global_vao_trial_tenant():
    table = default_rule_table()
    result = decide(
        _candidate(),
        table,
        _measures(schema_valid=False, from_global=True),
    )
    assert result.decision.rule_id == 6
    assert result.decision.target_status is FactStatus.TRIAL


def test_luat_8_bat_som_len_active():
    table = default_rule_table()
    result = decide(
        _candidate(decided_by="nguoi-duyet", rubric_clause="R-1"),
        table,
        _measures(
            is_new=False,
            fact_status=FactStatus.TRIAL,
            human_early_activate=True,
            has_rubric_clause=True,
        ),
    )
    assert result.decision.rule_id == 8
    assert result.decision.target_status is FactStatus.ACTIVE


def test_luat_8_thieu_dieu_khoan_rubric_cho_them_du_lieu():
    table = default_rule_table()
    result = decide(
        _candidate(),
        table,
        _measures(
            is_new=False,
            fact_status=FactStatus.TRIAL,
            human_early_activate=True,
            has_rubric_clause=False,
        ),
    )
    assert result.decision.rule_id == 9
    assert result.decision.verdict is DecisionVerdict.WAIT


def test_luat_9_con_lai_cho_them_du_lieu():
    table = default_rule_table()
    result = decide(
        _candidate(),
        table,
        _measures(is_new=False, fact_status=FactStatus.TRIAL, beta_prob=0.5),
    )
    assert result.decision.rule_id == 9
    assert result.decision.verdict is DecisionVerdict.WAIT


def test_khong_luat_nao_khop_can_nguoi_duyet(tmp_path):
    body = (
        _POLICY
        + """
[[rules]]
id = 1
applies_to = "chỉ khi xung đột"
verdict = "needs_human"
[rules.condition]
kind = "compare"
measure = "has_direct_conflict"
op = "=="
value = true
"""
    )
    table = _load_table(tmp_path, body)
    result = decide(_candidate(), table, _measures())
    assert result.decision.verdict is DecisionVerdict.NEEDS_HUMAN
    assert result.decision.rule_id is None
    assert result.candidate.rule_id is None


def test_ghi_rule_id_va_metrics_vao_candidate():
    table = default_rule_table()
    measures = _measures(from_trace=True, wilson_lower=0.8)
    result = decide(_candidate(), table, measures)
    assert result.candidate.rule_id == 2
    metrics = result.candidate.metrics_at_decision
    assert metrics is not None
    assert metrics["wilson_lower"] == 0.8
    assert metrics["from_trace"] is True
    assert len(metrics) == 13


def test_chay_lai_ra_dung_quyet_dinh_cu():
    table = default_rule_table()
    candidate = _candidate()
    measures = _measures(is_new=False, fact_status=FactStatus.TRIAL, beta_prob=0.97)
    first = decide(candidate, table, measures)
    second = decide(candidate, table, measures)
    assert first == second
    assert candidate.rule_id is None
    assert candidate.metrics_at_decision is None


def test_toan_tu_day_du_le_gt_khac_not_in_not(tmp_path):
    body = (
        _POLICY
        + """
[[rules]]
id = 1
applies_to = "đủ toán tử"
verdict = "wait"
[rules.condition]
kind = "all"
[[rules.condition.children]]
kind = "compare"
measure = "matching_cases"
op = "<="
value = 30
[[rules.condition.children]]
kind = "compare"
measure = "matching_cases"
op = ">"
value = 5
[[rules.condition.children]]
kind = "compare"
measure = "fact_status"
op = "!="
value = "retired"
[[rules.condition.children]]
kind = "compare"
measure = "fact_status"
op = "not_in"
value = ["retired"]
[[rules.condition.children]]
kind = "not"
[rules.condition.children.child]
kind = "compare"
measure = "has_direct_conflict"
op = "=="
value = true
"""
    )
    table = _load_table(tmp_path, body)
    result = decide(
        _candidate(),
        table,
        _measures(is_new=False, fact_status=FactStatus.TRIAL, matching_cases=10),
    )
    assert result.decision.rule_id == 1


def test_so_sanh_thu_tu_tren_fact_status_none_bao_loi():
    from praxon_core.learning.rules import ComparisonOp

    with pytest.raises(ValueError):
        _compare(None, ComparisonOp.GT, "active")
    assert _compare("trial", ComparisonOp.GT, "active") is True
    assert _compare("active", ComparisonOp.LT, "trial") is True
    assert _compare("trial", ComparisonOp.LE, "trial") is True
    assert _compare("trial", ComparisonOp.GE, "trial") is True
    with pytest.raises(ValueError):
        _compare("trial", ComparisonOp.GT, 0.5)


def test_luat_dau_khop_thang_luat_sau_khong_duoc_xet():
    table = default_rule_table()
    result = decide(
        _candidate(),
        table,
        _measures(has_direct_conflict=True, is_scope_promotion=True),
    )
    assert result.decision.rule_id == 1
