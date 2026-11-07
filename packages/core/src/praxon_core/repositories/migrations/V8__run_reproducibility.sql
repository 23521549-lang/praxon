-- V8 — Bảng `run` thêm verdict tái lập (plan con 12, task 12.3).
--
-- Lý do: spec dòng 191 bắt thiếu một điều kiện tái lập thì `run` ghi
-- "không tái lập được", nhưng bảng `run` (V1) không có cột nào để ghi
-- (docstring `RunRow` đã hứa nhưng không có chỗ ghi — xem E5 trong đề
-- xuất 12.3). Thêm hai cột: `reproducibility` (NULL = không phải lần
-- chạy lại / chưa kiểm; 'reproducible' / 'not_reproducible') và
-- `repro_gaps` (tên gap nối bằng dấu phẩy, rỗng khi không có gap).
-- Không sửa cột cũ, không đổi CHECK `status` (V1/V7 giữ nguyên).
-- Bất biến `repro_gaps` khác rỗng ⟺ `reproducibility =
-- 'not_reproducible'` ép bằng code + test, không ép bằng CHECK phức
-- tạp trong DB.

ALTER TABLE run ADD COLUMN reproducibility text
    CHECK (reproducibility IS NULL OR reproducibility IN ('reproducible', 'not_reproducible'));
ALTER TABLE run ADD COLUMN repro_gaps text NOT NULL DEFAULT '';
