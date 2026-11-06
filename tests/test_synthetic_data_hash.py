"""`data_hash` gồm seed và tham số bộ sinh (task 5.4, plan con 5).

Cổng ra: đổi một tham số bộ sinh thì `data_hash` đổi. Cùng đầu vào ra
cùng băm (xác định, 64 ký tự hex SHA-256).

`compute_data_hash` băm seed + toàn bộ tham số của `GeneratorParams` +
tenant — tenant nằm trong băm vì log sinh ra phụ thuộc vào tenant (dòng
ngẫu nhiên gieo từ seed + tenant). Quy tắc gộp hai nửa (F-10) ghi trong
docstring của hàm: coordinator (10.1) băm nối tiếp nửa BPIC (3.3) trước,
nửa bộ sinh sau, theo thứ tự cố định.
"""

import dataclasses

from praxon_core.synthetic.generator import (
    BASE_ORDER,
    GeneratorParams,
    compute_data_hash,
    swap_adjacent,
)


def _base_hash() -> str:
    return compute_data_hash(tenant_id="acme", params=GeneratorParams(seed=42))


def test_cung_dau_vao_ra_cung_bam():
    first = _base_hash()
    second = compute_data_hash(tenant_id="acme", params=GeneratorParams(seed=42))
    assert first == second
    assert len(first) == 64
    assert all(c in "0123456789abcdef" for c in first)


def test_doi_seed_thi_bam_doi():
    changed = compute_data_hash(tenant_id="acme", params=GeneratorParams(seed=43))
    assert changed != _base_hash()


def test_doi_tung_tham_so_bo_sinh_thi_bam_doi():
    base = _base_hash()
    variants = [
        GeneratorParams(seed=42, n_cases=301),
        GeneratorParams(seed=42, order=swap_adjacent(BASE_ORDER, 3)),
        GeneratorParams(seed=42, optional=frozenset({"step_03", "step_05"})),
        GeneratorParams(seed=42, skip_rate=0.61),
        GeneratorParams(seed=42, incomplete_rate=0.13),
        GeneratorParams(seed=42, noise_level=0.36),
    ]
    for variant in variants:
        changed = compute_data_hash(tenant_id="acme", params=variant)
        assert changed != base


def test_doi_tenant_thi_bam_doi():
    changed = compute_data_hash(tenant_id="globex", params=GeneratorParams(seed=42))
    assert changed != _base_hash()


def test_doi_mot_tham_so_bang_replace_thi_bam_doi():
    base_params = GeneratorParams(seed=42)
    base = compute_data_hash(tenant_id="acme", params=base_params)
    replaced = dataclasses.replace(base_params, noise_level=0.40)
    assert compute_data_hash(tenant_id="acme", params=replaced) != base
