-- V6 — Vai `promoter` được đọc bảng `candidate` (plan con 7, task 7.6).
--
-- Lý do: trigger V4 (`fact_check_candidate_approved`) kiểm candidate đã duyệt
-- chạy với quyền người gọi (spec cấm SECURITY DEFINER), nên khi Promoter ghi
-- fact global kèm `candidate_id`, trigger phải SELECT được candidate đó.
-- V3 chỉ cho tenant đọc candidate của đúng tenant mình; vai `promoter` không
-- có tenant nên thấy 0 hàng → trigger báo "candidate không tồn tại" và đường
-- ghi global của Promoter bị chặn.
--
-- Sửa: policy SELECT riêng cho `promoter`. V2 đã GRANT SELECT ON candidate cho
-- nhóm `g_promoter` (chủ ý: "applier/promoter đọc để áp") nên chỉ thiếu policy
-- RLS này. Chỉ đọc (không INSERT/UPDATE/DELETE); không đổi policy của tenant
-- nên BĐ2 giữ nguyên — không tenant nào đọc được dữ liệu tenant khác.

CREATE POLICY promoter_read_candidate ON candidate FOR SELECT
    USING (current_user = 'promoter');
