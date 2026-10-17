"""Test runner migration: khám phá, lũy đẳng, slug, và báo lỗi thiếu driver."""

from __future__ import annotations

import sys

import pytest

from praxon_core.repositories import migrate as migrations

from .conftest import ADMIN_DSN, TENANT_PASSWORD, _dsn_for


def test_discover_thay_3_migration_theo_thu_tu() -> None:
    found = migrations.discover()
    assert [m.version for m in found] == [1, 2, 3, 4, 5]
    assert [m.name for m in found] == [
        "V1__tables.sql",
        "V2__roles.sql",
        "V3__rls.sql",
        "V4__fact_candidate_approved.sql",
        "V5__candidate_insert_proposed.sql",
    ]
    assert all(m.sql.strip() for m in found)


@pytest.mark.parametrize(
    "slug",
    ["", "ACME", "acme__x", "promoter", "public", "ingestor", "a" * 64, "ac me"],
)
def test_provision_tenant_tu_choi_slug_khong_hop_le(slug: str) -> None:
    with pytest.raises(ValueError, match="slug tenant không hợp lệ"):
        migrations.provision_tenant("postgresql://localhost:5432/x", slug, "pw")


def test_provision_tenant_tu_choi_slug_qua_dai() -> None:
    # Slug 51 ký tự + "__coordinator" (11) = 64 > 63: tên vai Postgres không chứa nổi.
    with pytest.raises(ValueError, match="quá dài"):
        migrations.provision_tenant("postgresql://localhost:5432/x", "a" * 51, "pw")
    # Slug 50 ký tự là giới hạn vừa đủ: qua được validation (thử kết nối DB giả
    # để chứng minh không bị từ chối ở bước kiểm slug).
    try:
        migrations.provision_tenant("postgresql://localhost:5432/x", "a" * 50, "pw")
    except ValueError as exc:
        pytest.fail(f"slug 50 ký tự không được bị từ chối validation: {exc}")
    except Exception:
        pass  # Lỗi kết nối là đúng — validation đã qua.


def test_thieu_driver_bao_loi_ro_rang(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "psycopg", None)
    monkeypatch.setitem(sys.modules, "psycopg.sql", None)
    with pytest.raises(RuntimeError, match="psycopg"):
        migrations.apply("postgresql://localhost:5432/x")
    with pytest.raises(RuntimeError, match="psycopg"):
        migrations.provision_tenant("postgresql://localhost:5432/x", "acme", "pw")


def test_apply_luy_dang(pg: None) -> None:
    # pg fixture đã áp hết: chạy lại phải trả về rỗng, không lỗi.
    assert migrations.apply(ADMIN_DSN) == []
    assert migrations.apply(ADMIN_DSN, plan_only=True) == []


def test_provision_tenant_luy_dang(pg: None) -> None:
    assert migrations.provision_tenant(ADMIN_DSN, "acme", TENANT_PASSWORD) == []
    assert migrations.provision_tenant(ADMIN_DSN, "globex", TENANT_PASSWORD) == []


def test_provision_tenant_cap_nhat_mat_khau(pg: None) -> None:
    """Provision lại với mật khẩu mới phải cập nhật mật khẩu (không chỉ bỏ qua)."""
    import secrets

    from psycopg import connect

    new_password = secrets.token_urlsafe(16)
    assert migrations.provision_tenant(ADMIN_DSN, "acme", new_password) == []
    # Kết nối được bằng mật khẩu mới — chứng tỏ ALTER ROLE đã chạy.
    with connect(_dsn_for("acme__ingestor", new_password)):
        pass
    # Trả lại mật khẩu của phiên test để các test sau không gãy.
    assert migrations.provision_tenant(ADMIN_DSN, "acme", TENANT_PASSWORD) == []
