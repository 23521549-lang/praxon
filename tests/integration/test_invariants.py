"""25 phép tấn công trên 6 bất biến dữ liệu (plan con 2, task 2.5).

Mỗi test là một phép tấn công độc lập, chạy dưới đúng vai ứng dụng (xem `as_role`
trong conftest — fail ngay nếu vai là superuser). "Bị chặn" nghĩa là một trong:
- ``InsufficientPrivilege`` (42501): thiếu quyền ở tầng GRANT hoặc vi phạm RLS,
- ``UniqueViolation`` (23505): trùng ``candidate_id``,
- ``ExclusionViolation`` (23P01): trùng khóa + khoảng hiệu lực,
- 0 hàng: đọc chéo tenant (RLS lọc).

Cuối file là kiểm tra cấu trúc (RLS bật+ép, không superuser/BYPASSRLS, không hàm
SECURITY DEFINER) và các control dương (đảm bảo policy không chặn nhầm).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from psycopg import Connection
from psycopg.errors import (
    ExclusionViolation,
    InsufficientPrivilege,
    RaiseException,
    UniqueViolation,
)

from .conftest import as_role, one


def _unique_key(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _insert_fact_sql() -> str:
    return (
        "INSERT INTO fact (tenant_id, scope, canonical_key, template, statement, valid_during) "
        "VALUES (%s, %s, %s, 't', 's', %s)"
    )


# --- BĐ1: episode và event chỉ thêm -------------------------------------------


def test_bd1_ingestor_khong_update_duoc_episode(pg: None) -> None:
    with as_role("acme__ingestor") as conn, pytest.raises(InsufficientPrivilege):
        conn.execute("UPDATE episode SET case_id = 'x' WHERE tenant_id = 'acme'")


def test_bd1_ingestor_khong_delete_duoc_episode(pg: None) -> None:
    with as_role("acme__ingestor") as conn, pytest.raises(InsufficientPrivilege):
        conn.execute("DELETE FROM episode WHERE tenant_id = 'acme'")


def test_bd1_coordinator_khong_update_duoc_event(pg: None) -> None:
    with as_role("acme__coordinator") as conn, pytest.raises(InsufficientPrivilege):
        conn.execute("UPDATE event SET action = 'x' WHERE tenant_id = 'acme'")


def test_bd1_coordinator_khong_delete_duoc_event(pg: None) -> None:
    with as_role("acme__coordinator") as conn, pytest.raises(InsufficientPrivilege):
        conn.execute("DELETE FROM event WHERE tenant_id = 'acme'")


# --- BĐ2: không đọc chéo tenant ------------------------------------------------


def test_bd2_acme_khong_doc_duoc_episode_cua_globex(pg: None) -> None:
    with as_role("acme__reader") as conn:
        (count,) = one(conn, "SELECT count(*) FROM episode WHERE tenant_id = 'globex'")
        assert count == 0


def test_bd2_acme_khong_doc_duoc_fact_cua_globex(pg: None) -> None:
    with as_role("acme__reader") as conn:
        (count,) = one(conn, "SELECT count(*) FROM fact WHERE tenant_id = 'globex'")
        assert count == 0


def test_bd2_acme_khong_doc_duoc_candidate_cua_globex(pg: None) -> None:
    with as_role("acme__reader") as conn:
        (count,) = one(conn, "SELECT count(*) FROM candidate WHERE tenant_id = 'globex'")
        assert count == 0


def test_bd2_acme_khong_doc_duoc_event_cua_globex(pg: None) -> None:
    with as_role("acme__reader") as conn:
        (count,) = one(conn, "SELECT count(*) FROM event WHERE tenant_id = 'globex'")
        assert count == 0


def test_bd2_acme_khong_doc_duoc_run_cua_globex(pg: None) -> None:
    with as_role("acme__reader") as conn:
        (count,) = one(conn, "SELECT count(*) FROM run WHERE tenant_id = 'globex'")
        assert count == 0


# --- BĐ3: hai đường ghi tách bạch ------------------------------------------------


def test_bd3_ingestor_khong_insert_duoc_fact(pg: None) -> None:
    with as_role("acme__ingestor") as conn, pytest.raises(InsufficientPrivilege):
        conn.execute(
            _insert_fact_sql(),
            ("acme", "tenant", _unique_key("bd3"), "[2020-01-01,2021-01-01)"),
        )


def test_bd3_curator_khong_insert_duoc_fact(pg: None) -> None:
    # Phân tách đặc quyền: curator chỉ tạo candidate, không ghi fact trực tiếp.
    with as_role("acme__curator") as conn, pytest.raises(InsufficientPrivilege):
        conn.execute(
            _insert_fact_sql(),
            ("acme", "tenant", _unique_key("bd3"), "[2020-01-01,2021-01-01)"),
        )


def test_bd3_reader_khong_insert_duoc_episode(pg: None) -> None:
    with as_role("acme__reader") as conn, pytest.raises(InsufficientPrivilege):
        conn.execute(
            "INSERT INTO episode (tenant_id, case_id, occurred_at) "
            "VALUES ('acme', 'attack', now())"
        )


def test_bd3_governor_khong_insert_duoc_fact(pg: None) -> None:
    with as_role("acme__governor") as conn, pytest.raises(InsufficientPrivilege):
        conn.execute(
            _insert_fact_sql(),
            ("acme", "tenant", _unique_key("bd3"), "[2020-01-01,2021-01-01)"),
        )


def test_bd3_coordinator_khong_insert_duoc_fact(pg: None) -> None:
    with as_role("acme__coordinator") as conn, pytest.raises(InsufficientPrivilege):
        conn.execute(
            _insert_fact_sql(),
            ("acme", "tenant", _unique_key("bd3"), "[2020-01-01,2021-01-01)"),
        )


def test_bd3_khong_ap_duoc_candidate_chua_duyet(pg: None) -> None:
    # Candidate ở trạng thái 'proposed' (chưa có quyết định) thì applier không áp được.
    candidate_id = str(uuid.uuid4())
    with as_role("acme__curator") as conn:
        conn.execute(
            "INSERT INTO candidate (id, tenant_id, target_scope) VALUES (%s, 'acme', 'tenant')",
            (candidate_id,),
        )
    with as_role("acme__applier") as conn, pytest.raises(RaiseException):
        _apply_candidate(conn, "acme", candidate_id, _unique_key("bd3"))


def test_bd3_khong_ap_duoc_candidate_khong_ton_tai(pg: None) -> None:
    # candidate_id trỏ tới candidate không có thật: trigger chặn trước khóa ngoại.
    with as_role("acme__applier") as conn, pytest.raises(RaiseException):
        _apply_candidate(conn, "acme", str(uuid.uuid4()), _unique_key("bd3"))


def test_bd3_khong_ap_duoc_candidate_cua_tenant_khac(pg: None) -> None:
    # Candidate đã duyệt nhưng của tenant khác: RLS trong trigger không thấy → chặn.
    candidate_id = str(uuid.uuid4())
    with as_role("globex__curator") as conn:
        conn.execute(
            "INSERT INTO candidate (id, tenant_id, target_scope) "
            "VALUES (%s, 'globex', 'tenant')",
            (candidate_id,),
        )
    with as_role("globex__governor") as conn:
        conn.execute("UPDATE candidate SET status = 'approved' WHERE id = %s", (candidate_id,))
    with as_role("acme__applier") as conn, pytest.raises(RaiseException):
        _apply_candidate(conn, "acme", candidate_id, _unique_key("bd3"))


def test_bd3_curator_khong_tu_duyet_duoc_candidate(pg: None) -> None:
    # Curator INSERT thẳng status='approved' để qua mặt governor: policy chặn.
    with as_role("acme__curator") as conn, pytest.raises(InsufficientPrivilege):
        conn.execute(
            "INSERT INTO candidate (id, tenant_id, target_scope, status) "
            "VALUES (%s, 'acme', 'tenant', 'approved')",
            (str(uuid.uuid4()),),
        )


# --- BĐ4: chỉ promoter ghi global -------------------------------------------------


def test_bd4_applier_khong_ghi_duoc_global(pg: None) -> None:
    with as_role("acme__applier") as conn, pytest.raises(InsufficientPrivilege):
        conn.execute(
            _insert_fact_sql(),
            ("global", "global", _unique_key("bd4"), "[2020-01-01,2030-01-01)"),
        )


def test_bd4_curator_khong_ghi_duoc_global(pg: None) -> None:
    with as_role("acme__curator") as conn, pytest.raises(InsufficientPrivilege):
        conn.execute(
            _insert_fact_sql(),
            ("global", "global", _unique_key("bd4"), "[2020-01-01,2030-01-01)"),
        )


def test_bd4_khong_mao_danh_duoc_vai_promoter(pg: None) -> None:
    # current_user không đổi được bằng SET khi không phải thành viên của vai đó.
    with as_role("acme__reader") as conn, pytest.raises(InsufficientPrivilege):
        conn.execute("SET ROLE promoter")


# --- BĐ5: không hai fact cùng khóa cùng hiệu lực -----------------------------------


def test_bd5_trung_khoa_giao_valid_during_bi_chan(pg: None) -> None:
    key = _unique_key("bd5")
    with as_role("acme__applier") as conn:
        conn.execute(
            _insert_fact_sql(),
            ("acme", "tenant", key, "[2020-01-01,2025-01-01)"),
        )
        with pytest.raises(ExclusionViolation):
            conn.execute(
                _insert_fact_sql(),
                ("acme", "tenant", key, "[2023-01-01,2028-01-01)"),
            )


def test_bd5_trung_khoa_trung_known_during_bi_chan(pg: None) -> None:
    key = _unique_key("bd5")
    with as_role("acme__applier") as conn:
        conn.execute(
            _insert_fact_sql(),
            ("acme", "tenant", key, "[2020-01-01,2025-01-01)"),
        )
        with pytest.raises(ExclusionViolation):
            conn.execute(
                _insert_fact_sql(),
                ("acme", "tenant", key, "[2020-01-01,2025-01-01)"),
            )


def test_bd5_khoa_giong_nhau_nhung_valid_during_ke_nhau_thi_qua(pg: None) -> None:
    # Control dương: khoảng kề nhau không giao nhau thì được thêm (thay thế nối tiếp).
    key = _unique_key("bd5")
    with as_role("acme__applier") as conn:
        conn.execute(
            _insert_fact_sql(),
            ("acme", "tenant", key, "[2020-01-01,2025-01-01)"),
        )
        conn.execute(
            _insert_fact_sql(),
            ("acme", "tenant", key, "[2025-01-01,2030-01-01)"),
        )
        (count,) = one(conn, "SELECT count(*) FROM fact WHERE canonical_key = %s", (key,))
        assert count == 2


# --- BĐ6: áp candidate lũy đẳng -----------------------------------------------------


def _apply_candidate(conn: Connection[Any], tenant: str, candidate_id: str, key: str) -> None:
    conn.execute(
        "INSERT INTO fact (tenant_id, scope, canonical_key, template, statement, "
        "valid_during, candidate_id) "
        "VALUES (%s, 'tenant', %s, 't', 's', tstzrange('2030-01-01','2035-01-01','[)'), %s)",
        (tenant, key, candidate_id),
    )


def test_bd6_ap_lai_cung_candidate_bi_chan(pg: None) -> None:
    candidate_id = str(uuid.uuid4())
    key = _unique_key("bd6")
    with as_role("acme__curator") as conn:
        one(
            conn,
            "INSERT INTO candidate (id, tenant_id, target_scope) "
            "VALUES (%s, 'acme', 'tenant') RETURNING id",
            (candidate_id,),
        )
    with as_role("acme__governor") as conn:
        conn.execute("UPDATE candidate SET status = 'approved' WHERE id = %s", (candidate_id,))
    with as_role("acme__applier") as conn:
        _apply_candidate(conn, "acme", candidate_id, key)
        with pytest.raises(UniqueViolation):
            _apply_candidate(conn, "acme", candidate_id, _unique_key("bd6"))


def test_bd6_ap_lai_bang_on_conflict_khong_tao_hang_moi(pg: None) -> None:
    candidate_id = str(uuid.uuid4())
    key = _unique_key("bd6")
    with as_role("acme__curator") as conn:
        one(
            conn,
            "INSERT INTO candidate (id, tenant_id, target_scope) "
            "VALUES (%s, 'acme', 'tenant') RETURNING id",
            (candidate_id,),
        )
    with as_role("acme__governor") as conn:
        conn.execute("UPDATE candidate SET status = 'approved' WHERE id = %s", (candidate_id,))
    with as_role("acme__applier") as conn:
        _apply_candidate(conn, "acme", candidate_id, key)
        (before,) = one(conn, "SELECT count(*) FROM fact")
        cursor = conn.execute(
            "INSERT INTO fact (tenant_id, scope, canonical_key, template, statement, "
            "valid_during, candidate_id) "
            "VALUES ('acme', 'tenant', %s, 't', 's', "
            "tstzrange('2030-01-01','2035-01-01','[)'), %s) "
            "ON CONFLICT (candidate_id) DO NOTHING",
            (_unique_key("bd6"), candidate_id),
        )
        assert cursor.rowcount == 0
        (after,) = one(conn, "SELECT count(*) FROM fact")
        assert after == before


# --- Kiểm tra cấu trúc (ngoài 21 phép tấn công) --------------------------------------


def test_rls_enable_va_force_tren_ca_5_bang(pg: None) -> None:
    with as_role("acme__reader") as conn:
        rows = conn.execute(
            "SELECT relname FROM pg_class "
            "WHERE relname IN ('episode','event','run','candidate','fact') "
            "AND relrowsecurity AND relforcerowsecurity"
        ).fetchall()
        assert {row[0] for row in rows} == {"episode", "event", "run", "candidate", "fact"}


def test_vai_ung_dung_khong_superuser_khong_bypassrls(pg: None) -> None:
    with as_role("acme__reader") as conn:
        rows = conn.execute(
            "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles "
            "WHERE rolname LIKE '%\\_\\_%' ESCAPE '\\' "
            "OR rolname = 'promoter' OR rolname LIKE 'g\\_%' ESCAPE '\\'"
        ).fetchall()
        assert rows, "không tìm thấy vai ứng dụng nào để kiểm"
        for name, is_super, bypass in rows:
            assert not is_super, f"{name} không được là superuser"
            assert not bypass, f"{name} không được có BYPASSRLS"


def test_khong_ham_security_definer(pg: None) -> None:
    with as_role("acme__reader") as conn:
        (count,) = one(
            conn,
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'public' AND p.prosecdef",
        )
        assert count == 0


# --- Control dương: policy không chặn nhầm -------------------------------------------


def test_tenant_doc_duoc_hang_cua_minh_va_global(pg: None) -> None:
    with as_role("acme__reader") as conn:
        (n_ep,) = one(conn, "SELECT count(*) FROM episode")
        assert n_ep >= 1
        keys = {row[0] for row in conn.execute("SELECT canonical_key FROM fact").fetchall()}
        assert "seed-fact-acme" in keys
        assert "seed-fact-global" in keys
        assert "seed-fact-globex" not in keys


def test_chua_dat_tenant_thi_0_hang(pg: None) -> None:
    # Vai promoter không có phần tenant trong tên → split_part ra 'promoter', khớp 0 hàng.
    with as_role("promoter") as conn:
        (n_ep,) = one(conn, "SELECT count(*) FROM episode")
        assert n_ep == 0
        (n_global,) = one(conn, "SELECT count(*) FROM fact WHERE scope = 'global'")
        assert n_global >= 1


def test_promoter_ghi_global_duoc(pg: None) -> None:
    key = _unique_key("global-ok")
    with as_role("promoter") as conn:
        conn.execute(
            _insert_fact_sql(),
            ("global", "global", key, "[2020-01-01,2030-01-01)"),
        )
        (count,) = one(conn, "SELECT count(*) FROM fact WHERE canonical_key = %s", (key,))
        assert count == 1


def test_applier_chi_update_duoc_2_cot_dong_fact(pg: None) -> None:
    # Grant theo cột (điểm D đã duyệt): đóng fact được, sửa nội dung thì bị chặn.
    key = _unique_key("close")
    with as_role("acme__applier") as conn:
        conn.execute(
            _insert_fact_sql(),
            ("acme", "tenant", key, "[2020-01-01,2021-01-01)"),
        )
        conn.execute(
            "UPDATE fact SET known_during = tstzrange(lower(known_during), now(), '[)'), "
            "status = 'retired' WHERE canonical_key = %s",
            (key,),
        )
        (status,) = one(conn, "SELECT status FROM fact WHERE canonical_key = %s", (key,))
        assert status == "retired"
        with pytest.raises(InsufficientPrivilege):
            conn.execute("UPDATE fact SET confidence = 0.99 WHERE canonical_key = %s", (key,))


def test_thay_the_fact_trong_mot_giao_dich(pg: None) -> None:
    # Đóng fact cũ + thêm fact mới không giao nhau: exclusion cho qua.
    key = _unique_key("replace")
    with as_role("acme__applier") as conn:
        conn.execute(
            _insert_fact_sql(),
            ("acme", "tenant", key, "[2020-01-01,2030-01-01)"),
        )
        conn.execute(
            "UPDATE fact SET known_during = tstzrange(lower(known_during), now(), '[)'), "
            "status = 'retired' WHERE canonical_key = %s",
            (key,),
        )
        conn.execute(
            _insert_fact_sql(),
            ("acme", "tenant", key, "[2020-01-01,2030-01-01)"),
        )
        (count,) = one(conn, "SELECT count(*) FROM fact WHERE canonical_key = %s", (key,))
        assert count == 2
