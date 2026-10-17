"""CLI migration Postgres cho phát triển/CI (plan con 2, task 2.2).

Đọc DSN từ ``--dsn`` hoặc biến môi trường ``PRAXON_DATABASE_URL``. Toàn bộ logic
nằm ở ``praxon_core.repositories.migrate``; file này chỉ là lớp CLI mỏng và
không import driver DB trực tiếp (đúng tinh thần hợp đồng import-linter
"driver DB chỉ trong repositories").

Ví dụ::

    python -m tools.db_migrate --plan
    python -m tools.db_migrate
    python -m tools.db_migrate --provision-tenant acme --provision-tenant globex
"""

from __future__ import annotations

import argparse
import os
import secrets

ENV_VAR = "PRAXON_DATABASE_URL"


def _resolve_dsn(explicit: str | None) -> str:
    dsn = explicit or os.environ.get(ENV_VAR)
    if not dsn:
        raise SystemExit(
            f"thiếu DSN: truyền --dsn hoặc đặt biến môi trường {ENV_VAR}, ví dụ "
            "postgresql://postgres@localhost:5432/praxon (mật khẩu lấy từ .env)"
        )
    return dsn


def main() -> int:
    """Chạy CLI, trả mã thoát."""
    parser = argparse.ArgumentParser(description="Áp migration Postgres của praxon.")
    parser.add_argument("--dsn", default=None, help=f"DSN Postgres (mặc định: ${ENV_VAR}).")
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Chỉ in migrations sẽ chạy, không chạy thật.",
    )
    parser.add_argument(
        "--provision-tenant",
        action="append",
        default=[],
        metavar="SLUG",
        help="Tạo vai login cho tenant (dùng được nhiều lần).",
    )
    parser.add_argument(
        "--tenant-password",
        default=None,
        help="Mật khẩu cho vai tenant mới; mặc định sinh ngẫu nhiên và in ra.",
    )
    parser.add_argument(
        "--promoter-password",
        nargs="?",
        const="",
        default=None,
        metavar="MẬT_KHẨU",
        help=(
            "Đặt mật khẩu cho vai login toàn cục 'promoter' (tạo NOLOGIN trong V2, "
            "chưa có mật khẩu). Không cho giá trị thì sinh ngẫu nhiên và in ra."
        ),
    )
    args = parser.parse_args()

    from praxon_core.repositories import migrate as migrations

    dsn = _resolve_dsn(args.dsn)

    if args.plan:
        pending = migrations.apply(dsn, plan_only=True)
        if not pending:
            print("không có migration nào chờ chạy.")
        for migration in pending:
            print(f"V{migration.version} {migration.name}")
        return 0

    applied = migrations.apply(dsn)
    for migration in applied:
        print(f"đã áp: V{migration.version} {migration.name}")
    if not applied:
        print("schema đã ở bản mới nhất.")

    for slug in args.provision_tenant:
        password = args.tenant_password or secrets.token_urlsafe(16)
        created = migrations.provision_tenant(dsn, slug, password)
        if created:
            print(f"tenant {slug}: đã tạo {len(created)} vai (mật khẩu: {password})")
        else:
            print(f"tenant {slug}: vai đã tồn tại, không tạo thêm.")

    if args.promoter_password is not None:
        promoter_password = args.promoter_password or secrets.token_urlsafe(16)
        migrations.set_role_password(dsn, "promoter", promoter_password)
        print(f"vai promoter: đã đặt mật khẩu (mật khẩu: {promoter_password})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
