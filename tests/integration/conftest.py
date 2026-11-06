"""Fixture Postgres cho test tích hợp plan con 2.

DB lấy từ ``PRAXON_TEST_DATABASE_URL`` (mặc định: DB dev của compose.yml). Dùng biến
riêng thay vì ``PRAXON_DATABASE_URL`` để không làm nhiễu test settings (test đó kiểm
hành vi ghi đè env của Settings).

Phân vai rõ ràng: dựng schema/cấp vai/reset dữ liệu dùng tài khoản quản trị
(setup, một lần); mọi phép tấn công chạy dưới đúng vai ứng dụng qua ``as_role``
— fail ngay nếu vai là superuser. Đúng cổng ra của plan con 2: "chạy dưới đúng
vai ứng dụng — không bao giờ dưới tài khoản quản trị".
"""

from __future__ import annotations

import os
import secrets
import urllib.parse
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from psycopg import Connection, OperationalError, connect

from praxon_core.repositories import migrate as migrations

ADMIN_DSN = os.environ.get(
    "PRAXON_TEST_DATABASE_URL",
    "postgresql://postgres@localhost:5432/praxon",
)
TENANTS = ("acme", "globex")
#: Mật khẩu sinh ngẫu nhiên mỗi phiên test — không hard-code trong repo.
TENANT_PASSWORD = secrets.token_urlsafe(16)
#: Mật khẩu vai `promoter` sinh ngẫu nhiên mỗi phiên; fixture đặt qua tài khoản
#: quản trị vì V2 tạo vai này NOLOGIN (không hard-code mật khẩu trong migration).
PROMOTER_PASSWORD = secrets.token_urlsafe(16)


def _dsn_for(user: str, password: str) -> str:
    parts = urllib.parse.urlsplit(ADMIN_DSN)
    host = parts.hostname or "localhost"
    port = parts.port or 5432
    netloc = f"{user}:{urllib.parse.quote(password)}@{host}:{port}"
    return urllib.parse.urlunsplit((parts.scheme, netloc, parts.path, "", ""))


@contextmanager
def as_role(role: str) -> Iterator[Connection[Any]]:
    """Kết nối dưới một vai ứng dụng; fail ngay nếu vai là superuser."""
    password = PROMOTER_PASSWORD if role == "promoter" else TENANT_PASSWORD
    with connect(_dsn_for(role, password)) as conn:
        row = conn.execute(
            "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
        ).fetchone()
        assert row is not None and not row[0], f"vai {role} không được là superuser"
        yield conn


def one(conn: Connection[Any], query: str, params: tuple[Any, ...] = ()) -> tuple[Any, ...]:
    """SELECT một hàng; fail rõ ràng thay vì unpack None."""
    row = conn.execute(query, params).fetchone()
    assert row is not None
    return tuple(row)


def _reset_data() -> None:
    with connect(ADMIN_DSN) as conn:
        conn.execute("TRUNCATE event, run, candidate, fact, episode")


def _seed() -> None:
    """Dữ liệu mẫu: mỗi tenant một bộ episode/fact/candidate/event/run + 1 fact global."""
    with as_role("acme__ingestor") as conn:
        conn.execute(
            "INSERT INTO episode (tenant_id, case_id, occurred_at) "
            "VALUES ('acme', 'seed-acme-1', now())"
        )
    with as_role("globex__ingestor") as conn:
        conn.execute(
            "INSERT INTO episode (tenant_id, case_id, occurred_at) "
            "VALUES ('globex', 'seed-globex-1', now())"
        )
    with as_role("acme__coordinator") as conn:
        conn.execute(
            "INSERT INTO run (tenant_id, seed, model_id, code_commit, config_hash, data_hash) "
            "VALUES ('acme', 1, 'seed-model', 'seed-commit', 'seed-config', 'seed-data')"
        )
        conn.execute(
            "INSERT INTO event (tenant_id, actor, action, payload_hash) "
            "VALUES ('acme', 'seed', 'seed-action', 'seed-hash')"
        )
    with as_role("globex__coordinator") as conn:
        conn.execute(
            "INSERT INTO run (tenant_id, seed, model_id, code_commit, config_hash, data_hash) "
            "VALUES ('globex', 1, 'seed-model', 'seed-commit', 'seed-config', 'seed-data')"
        )
        conn.execute(
            "INSERT INTO event (tenant_id, actor, action, payload_hash) "
            "VALUES ('globex', 'seed', 'seed-action', 'seed-hash')"
        )
    with as_role("acme__curator") as conn:
        conn.execute(
            "INSERT INTO candidate (tenant_id, target_scope) VALUES ('acme', 'tenant')"
        )
    with as_role("globex__curator") as conn:
        conn.execute(
            "INSERT INTO candidate (tenant_id, target_scope) VALUES ('globex', 'tenant')"
        )
    with as_role("acme__applier") as conn:
        conn.execute(
            "INSERT INTO fact (tenant_id, scope, canonical_key, template, statement, "
            "valid_during) "
            "VALUES ('acme', 'tenant', 'seed-fact-acme', 'seed-template', 'seed', "
            "tstzrange('2020-01-01', '2025-01-01', '[)'))"
        )
    with as_role("globex__applier") as conn:
        conn.execute(
            "INSERT INTO fact (tenant_id, scope, canonical_key, template, statement, "
            "valid_during) "
            "VALUES ('globex', 'tenant', 'seed-fact-globex', 'seed-template', 'seed', "
            "tstzrange('2020-01-01', '2025-01-01', '[)'))"
        )
    with as_role("promoter") as conn:
        conn.execute(
            "INSERT INTO fact (tenant_id, scope, canonical_key, template, statement, "
            "valid_during) "
            "VALUES ('global', 'global', 'seed-fact-global', 'seed-template', 'seed', "
            "tstzrange('2020-01-01', '2030-01-01', '[)'))"
        )


@pytest.fixture(scope="session")
def pg() -> Iterator[None]:
    """Dựng schema + vai + dữ liệu mẫu một lần cho cả session test."""
    try:
        applied = migrations.apply(ADMIN_DSN)
    except OperationalError as exc:
        pytest.fail(
            "không nối được Postgres cho test tích hợp — "
            "chạy `docker compose up -d` trước (xem compose.yml). "
            f"Chi tiết: {exc}",
            pytrace=False,
        )
    for tenant in TENANTS:
        migrations.provision_tenant(ADMIN_DSN, tenant, TENANT_PASSWORD)
    # Vai promoter tạo NOLOGIN trong V2: đặt mật khẩu ngẫu nhiên qua admin để
    # test kết nối được. Mật khẩu không hard-code ở bất cứ đâu trong repo.
    migrations.set_role_password(ADMIN_DSN, "promoter", PROMOTER_PASSWORD)
    _reset_data()
    _seed()
    names = ", ".join(f"V{m.version}" for m in applied) or "không có (schema đã mới nhất)"
    print(f"\n[migration đã áp trong lần chạy này: {names}]")
    yield
