-- V7 — Bảng `run` thêm trạng thái `budget_exceeded` (plan con 10, task 10.4).
--
-- Lý do: spec dòng 217 bắt vòng học chạm trần token thì đóng `run` ở trạng
-- thái `budget_exceeded`. V1 chỉ cho ba giá trị (`running`, `succeeded`,
-- `failed`) nên cần mở CHECK thêm giá trị thứ tư. Không migration dữ liệu:
-- mọi hàng cũ chỉ mang ba giá trị cũ nên vẫn thỏa CHECK mới.
--
-- Tên constraint: V1 đặt CHECK không tên nên Postgres sinh tên
-- `run_status_check` (đã xác nhận bằng `SELECT conname,
-- pg_get_constraintdef(oid) FROM pg_constraint WHERE
-- conrelid = 'run'::regclass AND contype = 'c'` trên DB đã áp V1–V6,
-- ngày 7/11/2026).

ALTER TABLE run DROP CONSTRAINT run_status_check;
ALTER TABLE run ADD CONSTRAINT run_status_check CHECK (status IN ('running', 'succeeded', 'failed', 'budget_exceeded'));
