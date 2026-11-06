"""Test bảy điều kiện thí nghiệm (plan con 10, task 10.2).

Khẳng định cổng ra của task: một lệnh chạy đủ bảy điều kiện trên bộ
chuẩn bán tổng hợp, in bốn chỉ số theo tenant cho cả bảy điều kiện.
"""

from __future__ import annotations

from praxon_core.eval.experiments import (
    CONDITIONS,
    CONSENSUS,
    DECLARE_ONLY,
    DOCUMENT,
    ISOLATION,
    POOLED,
    VETO,
    VOTE_K,
    VOTING,
    _tenant_data,
    condition_fact_sets,
    format_experiments_report,
    main,
    run_experiments,
)
from praxon_core.eval.metrics import VIOLATION_THRESHOLD, violation_rate
from praxon_core.eval.report import (
    SYNTHETIC_TENANT_COUNT,
    BaselineReport,
    TenantConditionRow,
)


def _report() -> BaselineReport:
    return run_experiments(seed=42, n_cases=60, n_draws=50)


def _rows_by_condition(
    report: BaselineReport,
) -> dict[str, list[TenantConditionRow]]:
    by_condition: dict[str, list[TenantConditionRow]] = {}
    for row in report.rows:
        by_condition.setdefault(row.condition, []).append(row)
    return by_condition


def test_bay_dieu_kien_theo_dung_thu_tu_spec():
    assert CONDITIONS == (
        "Chỉ Declare",
        "Cách ly",
        "Gộp chung",
        "Phân tầng bỏ phiếu",
        "Phân tầng đồng thuận",
        "Phân tầng phủ quyết",
        "Tài liệu cộng dữ liệu",
    )


def test_moi_tenant_co_du_bay_dieu_kien():
    report = _report()
    assert len(report.rows) == SYNTHETIC_TENANT_COUNT * len(CONDITIONS)
    for tenant_index in range(1, SYNTHETIC_TENANT_COUNT + 1):
        tenant_rows = [
            row for row in report.rows if row.tenant_id == f"synthetic-{tenant_index}"
        ]
        assert [row.condition for row in tenant_rows] == list(CONDITIONS)


def test_chi_declare_va_cach_ly_giong_het_giai_doan_1():
    report = _report()
    by_condition = _rows_by_condition(report)
    for declare_row, isolation_row in zip(
        by_condition[DECLARE_ONLY], by_condition[ISOLATION], strict=True
    ):
        assert declare_row.metrics == isolation_row.metrics
        assert declare_row.n_rules == isolation_row.n_rules


def test_go_p_chung_khac_chi_declare():
    report = _report()
    by_condition = _rows_by_condition(report)
    differences = [
        (declare_row, pooled_row)
        for declare_row, pooled_row in zip(
            by_condition[DECLARE_ONLY], by_condition[POOLED], strict=True
        )
        if declare_row.metrics != pooled_row.metrics
    ]
    assert differences, "gộp chung phải khác chỉ-Declare ở ít nhất một tenant"


def test_phan_tang_dong_thuan_chi_chua_luat_khong_ai_vi_pham():
    tenants = _tenant_data(seed=42, n_cases=60)
    sets = condition_fact_sets(tenants)
    for tenant in tenants:
        global_facts = [
            fact for fact in sets[CONSENSUS][tenant.tenant_id] if fact.scope == "global"
        ]
        for fact in global_facts:
            for other in tenants:
                assert violation_rate([fact], other.train_traces) <= VIOLATION_THRESHOLD


def test_phan_tang_phu_quyet_loai_luat_vi_pham():
    tenants = _tenant_data(seed=42, n_cases=60)
    sets = condition_fact_sets(tenants)
    for tenant in tenants:
        global_facts = [fact for fact in sets[VETO][tenant.tenant_id] if fact.scope == "global"]
        for fact in global_facts:
            assert violation_rate([fact], tenant.train_traces) <= VIOLATION_THRESHOLD


def test_phan_tang_bo_phieu_can_du_vote_k():
    tenants = _tenant_data(seed=42, n_cases=60)
    sets = condition_fact_sets(tenants)
    own_keys = [
        {fact.canonical_key for fact in sets[DECLARE_ONLY][tenant.tenant_id]}
        for tenant in tenants
    ]
    for tenant in tenants:
        global_keys = {
            fact.canonical_key
            for fact in sets[VOTING][tenant.tenant_id]
            if fact.scope == "global"
        }
        for key in global_keys:
            supporters = sum(1 for keys in own_keys if key in keys)
            assert supporters >= VOTE_K


def test_tai_lieu_cong_du_lieu_tap_luat_rong_va_bang_ung_vien_tot_hon():
    report = _report()
    assert "RỖNG" in report.note
    by_condition = _rows_by_condition(report)
    document_metrics = [row.metrics for row in by_condition[DOCUMENT]]
    consensus_metrics = [row.metrics for row in by_condition[CONSENSUS]]
    veto_metrics = [row.metrics for row in by_condition[VETO]]
    assert document_metrics in (consensus_metrics, veto_metrics)


def test_chay_lai_ra_dung_bao_cao_cu():
    assert _report() == _report()


def test_lenh_in_bay_dieu_kien_bon_chi_so(capsys):
    assert main(["--n-cases", "60", "--draws", "50"]) == 0
    output = capsys.readouterr().out
    for condition in CONDITIONS:
        assert condition in output
    for label in (
        "precision:",
        "recall:",
        "tỉ lệ vi phạm:",
        "negative transfer:",
    ):
        assert output.count(label) == SYNTHETIC_TENANT_COUNT * len(CONDITIONS)
    for tenant_index in range(1, SYNTHETIC_TENANT_COUNT + 1):
        assert f"Tenant synthetic-{tenant_index}" in output


def test_lenh_tu_choi_draws_khong_hop_le(capsys):
    assert main(["--draws", "0"]) == 2
    assert "số lần rút" in capsys.readouterr().err


def test_lenh_tu_choi_n_cases_khong_hop_le(capsys):
    assert main(["--n-cases", "0"]) == 2
    assert "số trace" in capsys.readouterr().err


def test_dinh_dang_bao_cao_co_ghi_chu_va_bon_chi_so():
    text = format_experiments_report(_report())
    assert "RỖNG" in text
    assert "support=0.5" in text
    assert "confidence=0.5" in text
