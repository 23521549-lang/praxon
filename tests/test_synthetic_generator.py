"""Bộ sinh bán tổng hợp (task 5.1, plan con 5).

Cổng ra: cùng seed ra cùng log; đáp án xuất ra cùng lúc với log. Đổi có
kiểm soát một số luật thứ tự theo tenant (hoán đổi hai bước kề nhau) làm
đáp án của tenant đó đổi đúng các luật của cặp bị đổi.
"""

from praxon_core.synthetic.generator import (
    ACTIVITIES,
    BASE_ORDER,
    GeneratorParams,
    generate,
    ground_truth_for,
    swap_adjacent,
)


def test_ground_truth_la_bao_dong_cua_thu_tu():
    truth = ground_truth_for(BASE_ORDER)
    assert len(truth) == 28 * 2
    assert "response(step_01, step_08)" in truth
    assert "precedence(step_04, step_05)" in truth
    assert "response(step_05, step_04)" not in truth


def test_swap_doi_dung_luat_cua_cap_bi_doi():
    swapped = swap_adjacent(BASE_ORDER, 3)
    assert swapped[3] == "step_05" and swapped[4] == "step_04"
    diff = ground_truth_for(BASE_ORDER) ^ ground_truth_for(swapped)
    assert diff == {
        "response(step_04, step_05)",
        "precedence(step_04, step_05)",
        "response(step_05, step_04)",
        "precedence(step_05, step_04)",
    }


def test_swap_ngoai_pham_vi_bao_loi():
    for index in (-1, len(BASE_ORDER) - 1, len(BASE_ORDER)):
        try:
            swap_adjacent(BASE_ORDER, index)
        except ValueError:
            pass
        else:
            raise AssertionError(f"khong bat duoc loi voi index={index}")


def test_cung_seed_ra_cung_log_va_cung_dap_an():
    params = GeneratorParams(seed=42, n_cases=300)
    first = generate(tenant_id="acme", params=params)
    second = generate(tenant_id="acme", params=params)
    assert first == second
    assert first.traces == second.traces
    assert first.ground_truth == second.ground_truth
    assert first.ground_truth == ground_truth_for(BASE_ORDER)


def test_khac_seed_ra_log_khac():
    params = GeneratorParams(seed=42, n_cases=300)
    base = generate(tenant_id="acme", params=params)
    other = generate(tenant_id="acme", params=GeneratorParams(seed=43, n_cases=300))
    assert other.traces != base.traces


def test_khac_tenant_ra_log_khac_nhung_dap_an_giong_nhau():
    params = GeneratorParams(seed=42, n_cases=300)
    first = generate(tenant_id="acme", params=params)
    second = generate(tenant_id="globex", params=params)
    assert second.traces != first.traces
    assert second.ground_truth == first.ground_truth


def test_trace_ton_trong_thu_tu_cua_tenant():
    params = GeneratorParams(seed=7, n_cases=200)
    log = generate(tenant_id="acme", params=params)
    assert len(log.traces) == 200
    for trace in log.traces:
        dedup = tuple(dict.fromkeys(trace.events))
        assert dedup == tuple(a for a in BASE_ORDER if a in dedup)
        assert len(trace.events) >= 1
        assert set(trace.events).issubset(set(ACTIVITIES))


def test_doi_thu_tu_theo_tenant_doi_dap_an():
    swapped = swap_adjacent(BASE_ORDER, 3)
    params = GeneratorParams(seed=42, n_cases=100, order=swapped)
    log = generate(tenant_id="globex", params=params)
    assert log.ground_truth == ground_truth_for(swapped)
    assert "response(step_05, step_04)" in log.ground_truth
    assert "response(step_04, step_05)" not in log.ground_truth
    base = generate(tenant_id="acme", params=GeneratorParams(seed=42, n_cases=100))
    assert log.ground_truth != base.ground_truth


def test_tham_so_sai_bao_loi():
    for bad in [
        GeneratorParams(seed=1, n_cases=-1),
        GeneratorParams(seed=1, skip_rate=1.5),
        GeneratorParams(seed=1, incomplete_rate=-0.1),
        GeneratorParams(seed=1, noise_level=2.0),
        GeneratorParams(seed=1, order=("step_01",)),
        GeneratorParams(seed=1, optional=frozenset({"khong-co"})),
    ]:
        try:
            generate(tenant_id="acme", params=bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"khong bat duoc loi voi {bad}")


def test_log_rong_khi_n_cases_bang_0():
    log = generate(tenant_id="acme", params=GeneratorParams(seed=1, n_cases=0))
    assert log.traces == ()
    assert log.ground_truth == ground_truth_for(BASE_ORDER)
