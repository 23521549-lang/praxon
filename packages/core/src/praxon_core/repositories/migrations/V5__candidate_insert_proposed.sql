-- V5 — BĐ3: candidate mới tạo phải ở trạng thái 'proposed' (plan con 2, task 2.4).
--
-- Bất biến BĐ3 của spec: "Curator tạo, Governor ghi quyết định." Nếu curator được
-- INSERT candidate với status='approved' thì quyết định của governor thành vô nghĩa
-- — applier/promoter (đã bị V4 chặn chỉ áp candidate approved) sẽ áp một "quyết định"
-- chưa từng qua governor.
--
-- Sửa: policy INSERT trên candidate ép status='proposed'. Chỉ governor (qua policy
-- UPDATE candidate_decide) mới chuyển được sang 'approved'/'rejected'. DEFAULT của
-- cột đã là 'proposed' nên INSERT không ghi status vẫn qua.

DROP POLICY IF EXISTS tenant_write ON candidate;

CREATE POLICY tenant_write ON candidate FOR INSERT
    WITH CHECK (
        tenant_id = split_part(current_user, '__', 1)
        AND status = 'proposed'
    );
