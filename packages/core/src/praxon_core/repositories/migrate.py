"""Runner migration SQL có version cho Postgres (plan con 2, task 2.2).

Mỗi migration là một file ``V<n>__<mo_ta>.sql`` đặt cạnh module này (đóng gói kèm
wheel qua package-data). Runner áp đúng một lần theo thứ tự version, mỗi file
trong một transaction riêng; bảng ``schema_migrations`` ghi version đã áp nên
chạy lần hai bỏ qua — đạt lũy đẳng ở mức runner, đúng cổng ra của task 2.2.

``psycopg`` chỉ import trong hàm (deferred): môi trường core-only không có driver
vẫn ``import praxon_core`` được, giữ cổng standalone xanh. Thiếu driver thì báo
lỗi nêu rõ tên gói cần cài thay vì một ImportError khó hiểu.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from psycopg import Connection

VERSION_PATTERN = re.compile(r"^V(\d+)__[A-Za-z0-9_]+\.sql$")
MIGRATIONS_TABLE = "schema_migrations"

#: Chức năng của vai DB, cũng là hậu tố trong tên vai login `<slug>__<chức-năng>`.
FUNCTIONS = (
    "ingestor",
    "curator",
    "governor",
    "applier",
    "promoter",
    "coordinator",
    "reader",
)

#: Chức năng được tạo theo từng tenant. `promoter` là vai toàn cục duy nhất
#: (tạo trong V2), không tạo theo tenant.
TENANT_FUNCTIONS = tuple(f for f in FUNCTIONS if f != "promoter")

_TENANT_SLUG_PATTERN = re.compile(r"^[a-z0-9-]{1,63}$")
_RESERVED_SLUGS = frozenset({"promoter", "public", *FUNCTIONS})


@dataclass(frozen=True)
class Migration:
    """Một migration: version, tên file, nội dung SQL."""

    version: int
    name: str
    sql: str


def discover() -> list[Migration]:
    """Liệt kê migrations theo thứ tự version; version trùng thì lỗi ngay."""
    found: list[Migration] = []
    # Tên package SQL viết tường minh: __package__ ở đây là `repositories`,
    # còn file SQL nằm trong subpackage `repositories.migrations`.
    package_files = resources.files("praxon_core.repositories.migrations")
    for entry in package_files.iterdir():
        match = VERSION_PATTERN.match(entry.name)
        if match is None:
            continue
        found.append(
            Migration(
                version=int(match.group(1)),
                name=entry.name,
                sql=entry.read_text(encoding="utf-8"),
            )
        )
    found.sort(key=lambda item: item.version)
    if not found:
        raise ValueError("không tìm thấy file migration nào (kiểm tra package-data)")
    versions = [item.version for item in found]
    if len(set(versions)) != len(versions):
        raise ValueError("migration version bị trùng nhau")
    return found


def _connect(dsn: str) -> Connection[Any]:
    """Mở kết nối; thiếu driver thì báo lỗi nêu rõ gói cần cài."""
    try:
        from psycopg import connect
    except ImportError as exc:
        raise RuntimeError(
            "thiếu driver Postgres: cài 'psycopg' và 'psycopg-binary'"
            " (xem requirements-dev.txt)"
        ) from exc
    return connect(dsn)


def _applied_versions(conn: Connection[Any]) -> set[int]:
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} ("
        "version integer PRIMARY KEY, "
        "applied_at timestamptz NOT NULL DEFAULT now())"
    )
    rows = conn.execute(f"SELECT version FROM {MIGRATIONS_TABLE}").fetchall()
    return {row[0] for row in rows}


def apply(dsn: str, *, plan_only: bool = False) -> list[Migration]:
    """Áp migrations còn thiếu theo thứ tự version.

    Mỗi migration chạy trong một transaction riêng. ``plan_only=True`` thì chỉ
    trả về danh sách sẽ chạy mà không chạy thật (dùng cho ``--plan``).
    Trả về danh sách migrations đã áp (hoặc sẽ áp ở chế độ plan).
    """
    with _connect(dsn) as conn:
        pending = [m for m in discover() if m.version not in _applied_versions(conn)]
        if plan_only:
            return pending
        for migration in pending:
            with conn.transaction():
                conn.execute(migration.sql)
                conn.execute(
                    f"INSERT INTO {MIGRATIONS_TABLE} (version) VALUES (%s)",
                    (migration.version,),
                )
        return pending


def _set_role_password(conn: Connection[Any], role: str, password: str) -> None:
    """Đặt mật khẩu cho một vai (dùng Literal vì ALTER ROLE không tham số hóa được)."""
    try:
        from psycopg.sql import SQL, Identifier, Literal
    except ImportError as exc:
        raise RuntimeError(
            "thiếu driver Postgres: cài 'psycopg' và 'psycopg-binary'"
            " (xem requirements-dev.txt)"
        ) from exc
    conn.execute(
        SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(Identifier(role), Literal(password))
    )


def set_role_password(dsn: str, role: str, password: str) -> None:
    """Đặt mật khẩu cho một vai DB đã tồn tại (cần quyền quản trị).

    Dùng cho vai `promoter` (tạo NOLOGIN trong V2, chưa có mật khẩu) lúc
    provision/test. Mật khẩu không bao giờ hard-code trong migration.
    """
    with _connect(dsn) as conn:
        _set_role_password(conn, role, password)


def provision_tenant(dsn: str, slug: str, password: str) -> list[str]:
    """Tạo 6 vai login ``<slug>__<chức-năng>`` kế thừa vai nhóm tương ứng.

    Slug chỉ gồm chữ thường, số, gạch ngang; không được trùng tên vai hệ thống.
    Idempotent: vai đã tồn tại thì chỉ cập nhật mật khẩu (để mật khẩu truyền vào
    luôn hiệu lực), không lỗi; chỉ vai mới tạo mới được trả về.
    """
    if not _TENANT_SLUG_PATTERN.match(slug) or slug in _RESERVED_SLUGS:
        raise ValueError(f"slug tenant không hợp lệ: {slug!r}")
    try:
        from psycopg.sql import SQL, Identifier, Literal
    except ImportError as exc:
        raise RuntimeError(
            "thiếu driver Postgres: cài 'psycopg' và 'psycopg-binary'"
            " (xem requirements-dev.txt)"
        ) from exc
    created: list[str] = []
    with _connect(dsn) as conn:
        for function in TENANT_FUNCTIONS:
            role = f"{slug}__{function}"
            exists = conn.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)
            ).fetchone()
            # CREATE/ALTER ROLE là utility statement, không tham số hóa được password:
            # nhúng bằng Literal (đã quote đúng), không nối chuỗi thô.
            if exists is None:
                conn.execute(
                    SQL("CREATE ROLE {} LOGIN PASSWORD {} IN ROLE {}").format(
                        Identifier(role), Literal(password), Identifier(f"g_{function}")
                    )
                )
                created.append(role)
            else:
                conn.execute(
                    SQL("ALTER ROLE {} WITH PASSWORD {}").format(
                        Identifier(role), Literal(password)
                    )
                )
    return created
