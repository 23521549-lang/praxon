"""Một lệnh chạy bảy điều kiện trên cả hai nguồn (task 13.1, spec dòng 31).

Người dùng chỉ gõ `python -m tools.run_phase1`: wrapper đảm bảo `.env`
có `POSTGRES_PASSWORD` (sinh ngẫu nhiên nếu chưa có, KHÔNG ghi đè giá trị
đã có), sinh khóa API một lần cho model service, tính `code_commit`, rồi
chạy `docker compose run --rm eval` và trả nguyên mã thoát của service
`eval` (0/1/2/3/4 — xem `praxon_core.eval.run_all`).

Khóa `PRAXON_LLM_API_KEY` chỉ sống trong tiến trình con (env), không ghi
vào file nào. Mật khẩu Postgres ghi vào `.env` (file đã gitignore) vì
`compose.yml` bắt bằng `:?` — không có mật khẩu thì compose không chạy.
"""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path

ENV_FILENAME = ".env"
PASSWORD_KEY = "POSTGRES_PASSWORD"
LLM_KEY_ENV = "PRAXON_LLM_API_KEY"
CODE_COMMIT_ENV = "PRAXON_CODE_COMMIT"
OUT_ENV = "PRAXON_PHASE1_OUT"
DEFAULT_CONFIG = Path("configs/phan-do.toml")
DEFAULT_OUT = Path("out")


def _repo_root() -> Path:
    """Gốc kho: thư mục cha của `tools/`."""
    return Path(__file__).resolve().parent.parent


def _password_present(env_path: Path) -> bool:
    """`.env` đã có `POSTGRES_PASSWORD` khác rỗng chưa."""
    if not env_path.is_file():
        return False
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(PASSWORD_KEY + "="):
            return stripped.split("=", 1)[1].strip() != ""
    return False


def ensure_env_password(env_path: Path) -> str:
    """Đảm bảo `.env` có mật khẩu; trả mật khẩu (mới sinh hoặc đã có).

    Chỉ thêm khi key chưa có hoặc rỗng — không bao giờ ghi đè giá trị đã
    có (Postgres từ chối đổi mật khẩu trên data dir đã có — xem 13.1 R8).
    Mật khẩu sinh bằng `secrets` (URL-safe, không ký tự phá vỡ `.env`).
    """
    if _password_present(env_path):
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(PASSWORD_KEY + "="):
                return stripped.split("=", 1)[1].strip()
        raise RuntimeError("không đọc được mật khẩu đã có trong .env")
    password = secrets.token_urlsafe(32)
    lines: list[str] = []
    replaced = False
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(PASSWORD_KEY + "="):
                if not replaced:
                    lines.append(f"{PASSWORD_KEY}={password}")
                    replaced = True
                # Dòng trùng thì bỏ (chỉ giữ một dòng mật khẩu).
                continue
            lines.append(line)
    if not replaced:
        lines.append(f"{PASSWORD_KEY}={password}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return password


def _git_head(root: Path) -> str:
    """`code_commit` lúc chạy; rỗng khi git không chạy được (run_all tự rơi về "unknown")."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    commit = result.stdout.strip()
    return commit if result.returncode == 0 else ""


def _container_path(root: Path, path: Path) -> str:
    """Đường dẫn repo-tương đối thành đường dẫn trong container (`/app/...`).

    Config nằm trong repo nên image đã COPY nó; đường dẫn ngoài repo thì
    container không thấy được nên báo lỗi rõ thay vì chạy với file sai.
    """
    candidate = path if path.is_absolute() else root / path
    try:
        relative = candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"cấu hình {path} nằm ngoài repo — container không đọc được") from exc
    return "/app/" + relative.as_posix()


def _lock_path_for(config: Path) -> Path:
    """Bản ghi khóa đi kèm TOML cấu hình (cùng stem + `.lock`)."""
    return config.with_name(config.stem + ".lock.toml")


def main(argv: list[str] | None = None) -> int:
    """Lệnh `python -m tools.run_phase1 [--config] [--out] [--smoke]`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="tệp TOML cấu hình khóa (mặc định %(default)s)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="thư mục host nhận báo cáo JSON (mặc định %(default)s)",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="lát cắt nhỏ: bỏ qua trích Wabo, bộ chuẩn rút gọn, driver BPIC giả",
    )
    args = parser.parse_args(argv)
    root = _repo_root()
    ensure_env_password(root / ENV_FILENAME)
    out_host = args.out if args.out.is_absolute() else root / args.out
    out_host.mkdir(parents=True, exist_ok=True)
    try:
        config_container = _container_path(root, args.config)
        lock_container = _container_path(root, _lock_path_for(args.config))
    except ValueError as exc:
        print(f"lỗi tham số: {exc}", file=sys.stderr)
        return 2
    env = dict(os.environ)
    env[LLM_KEY_ENV] = secrets.token_urlsafe(32)
    env[CODE_COMMIT_ENV] = _git_head(root)
    env[OUT_ENV] = str(out_host)
    command = [
        "docker",
        "compose",
        "run",
        "--rm",
        "eval",
        "--config",
        config_container,
        "--lock",
        lock_container,
        "--out",
        "/out",
        "--code-commit",
        env[CODE_COMMIT_ENV],
    ]
    if args.smoke:
        command.append("--smoke")
    try:
        result = subprocess.run(command, cwd=root, env=env, check=False)
    except FileNotFoundError:
        print(
            "không chạy được docker compose: chưa cài Docker hoặc `docker` "
            "không có trên PATH (máy trống cần Docker để chạy lệnh này)",
            file=sys.stderr,
        )
        return 2
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
