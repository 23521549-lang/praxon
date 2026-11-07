"""Ghi hàng `run` (plan con 10, task 10.1; spec: bảng `run`).

Bảng `run` đã có từ migration V1 (`repositories/migrations/V1__tables.sql`):
seed, model_id, model_revision, code_commit, config_hash, data_hash,
tokens_in, tokens_out, wall_time, status. V2 cấp cho vai coordinator
quyền INSERT (chỉ thêm, không sửa — BĐ1); V3 bật RLS và chỉ cho
coordinator của đúng tenant đó ghi. V7 thêm giá trị `budget_exceeded`
cho `status` (task 10.4, spec dòng 217). V8 thêm hai cột verdict tái lập
`reproducibility`/`repro_gaps` (task 12.3, spec dòng 191). Task 10.1
KHÔNG cần migration mới: chỉ thêm lớp ghi theo đúng mẫu
`repositories/facts.py` và `repositories/events.py` — một kiểu hàng
thuần + một hàm INSERT, dùng `psycopg`, và chỉ module này được import
driver DB cho bảng `run`.
"""

from __future__ import annotations

from dataclasses import dataclass

from psycopg import Connection


@dataclass(frozen=True)
class RunRow:
    """Một hàng của bảng `run`: điều kiện tái lập của một lần chạy.

    Sáu trường điều kiện tái lập (spec, dòng 191) là `seed`, `model_id`,
    `model_revision`, `code_commit`, `config_hash`, `data_hash` — thiếu
    một trường là lần chạy đó ghi "không tái lập được", không bao giờ
    lặng lẽ cho qua. `tokens_in`/`tokens_out` là token vào ra của mô
    hình trong lần chạy; `wall_time` là thời gian tường của lần chạy
    (giây); `status` là `running` khi bắt đầu, `succeeded`/`failed`
    khi kết thúc (V1 chỉ cho ba giá trị này; V7 thêm `budget_exceeded`
    cho vòng học chạm trần token — task 10.4).

    Verdict tái lập (task 12.3, spec dòng 191, V8): `reproducibility`
    là NULL khi không phải lần chạy lại (lần chạy thường không có
    verdict), `'reproducible'` khi lần chạy lại đủ sáu điều kiện,
    `'not_reproducible'` khi lần chạy lại thiếu điều kiện; `repro_gaps`
    là tên gap nối bằng dấu phẩy, rỗng khi không có gap. Bất biến:
    `repro_gaps` khác rỗng ⟺ `reproducibility == 'not_reproducible'`.
    """

    tenant_id: str
    seed: int
    model_id: str
    model_revision: str
    code_commit: str
    config_hash: str
    data_hash: str
    tokens_in: int = 0
    tokens_out: int = 0
    wall_time: float = 0.0
    status: str = "running"
    reproducibility: str | None = None
    repro_gaps: str = ""


def insert_run(conn: Connection, run: RunRow) -> str:
    """Ghi một hàng `run`, trả về id (uuid do DB sinh).

    Người gọi chạy dưới vai `<tenant>__coordinator` (V2/V3): cùng tenant
    với `run.tenant_id` thì ghi được; khác tenant thì RLS chặn. Hàm
    không tự commit — người gọi giữ giao dịch (ghi `run` cùng các
    event/fact của nó rồi commit một lần).
    """
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO run (tenant_id, seed, model_id, model_revision, "
            "code_commit, config_hash, data_hash, tokens_in, tokens_out, "
            "wall_time, status, reproducibility, repro_gaps) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id",
            (
                run.tenant_id,
                run.seed,
                run.model_id,
                run.model_revision,
                run.code_commit,
                run.config_hash,
                run.data_hash,
                run.tokens_in,
                run.tokens_out,
                run.wall_time,
                run.status,
                run.reproducibility,
                run.repro_gaps,
            ),
        )
        row = cur.fetchone()
        assert row is not None
        return str(row[0])
