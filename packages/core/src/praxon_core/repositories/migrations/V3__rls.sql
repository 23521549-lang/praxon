-- V3 — Row-Level Security: ENABLE + FORCE và policy (plan con 2, task 2.3).
--
-- Nguyên tắc duy nhất: tenant suy từ TÊN VAI cơ sở dữ liệu, không từ biến phiên.
-- Vai login có dạng `<slug>__<chức-năng>` (vd `acme__reader`); tenant của session là
-- `split_part(current_user, '__', 1)`. Muốn đổi tenant phải đăng nhập lại bằng vai
-- khác — không có đường `SET` như biến phiên (lý do ở bất biến BĐ4 của spec:
-- "biến phiên thì code nào cũng tự bật được", áp dụng đồng đều cho BĐ2).
--
-- Vai `promoter` không có phần tenant: `split_part('promoter','__',1) = 'promoter'`
-- nên nó thấy 0 hàng tenant — đó cũng là phép thử "chưa đặt tenant thì 0 hàng".
--
-- Policy viết theo từng lệnh (không dùng FOR ALL): lệnh nào không có policy thì
-- bị từ chối mặc định (fail-closed), kể cả khi ai đó vô tình GRANT thêm về sau.
-- Không có policy DELETE trên bất kỳ bảng nào: xóa hàng là không bao giờ được.

ALTER TABLE episode   ENABLE ROW LEVEL SECURITY;
ALTER TABLE episode   FORCE ROW LEVEL SECURITY;
ALTER TABLE event     ENABLE ROW LEVEL SECURITY;
ALTER TABLE event     FORCE ROW LEVEL SECURITY;
ALTER TABLE run       ENABLE ROW LEVEL SECURITY;
ALTER TABLE run       FORCE ROW LEVEL SECURITY;
ALTER TABLE candidate ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate FORCE ROW LEVEL SECURITY;
ALTER TABLE fact      ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact      FORCE ROW LEVEL SECURITY;

-- BĐ2: cách ly tenant cho 4 bảng không có scope.
CREATE POLICY tenant_read ON episode FOR SELECT
    USING (tenant_id = split_part(current_user, '__', 1));
CREATE POLICY tenant_write ON episode FOR INSERT
    WITH CHECK (tenant_id = split_part(current_user, '__', 1));

CREATE POLICY tenant_read ON event FOR SELECT
    USING (tenant_id = split_part(current_user, '__', 1));
CREATE POLICY tenant_write ON event FOR INSERT
    WITH CHECK (tenant_id = split_part(current_user, '__', 1));

CREATE POLICY tenant_read ON run FOR SELECT
    USING (tenant_id = split_part(current_user, '__', 1));
CREATE POLICY tenant_write ON run FOR INSERT
    WITH CHECK (tenant_id = split_part(current_user, '__', 1));

CREATE POLICY tenant_read ON candidate FOR SELECT
    USING (tenant_id = split_part(current_user, '__', 1));
CREATE POLICY tenant_write ON candidate FOR INSERT
    WITH CHECK (tenant_id = split_part(current_user, '__', 1));
-- Governor ghi quyết định lên candidate của đúng tenant mình.
CREATE POLICY candidate_decide ON candidate FOR UPDATE
    USING (tenant_id = split_part(current_user, '__', 1))
    WITH CHECK (tenant_id = split_part(current_user, '__', 1));

-- BĐ2: tenant đọc hàng của mình cộng hàng global.
-- Vai promoter (không có tenant) chỉ đọc được hàng global ở đây. Đây là chủ ý:
-- credential `promoter` là "ngòi ghi global"; component Promoter khi cần đọc dữ
-- liệu tenant thì dùng credential reader/applier tương ứng (mỗi thao tác một
-- credential tối thiểu) — chi tiết luồng promote thuộc plan con 7.
CREATE POLICY fact_read ON fact FOR SELECT
    USING (scope = 'global' OR tenant_id = split_part(current_user, '__', 1));

-- BĐ3 + BĐ4: tenant ghi qua applier của đúng tenant mình; global CHỈ promoter.
-- Khóa global theo tên vai DB (`current_user = 'promoter'`), không theo biến phiên.
-- Quy ước (xem V1): fact global mang tenant_id = 'global'.
CREATE POLICY fact_insert ON fact FOR INSERT
    WITH CHECK (
        (scope = 'global' AND tenant_id = 'global' AND current_user = 'promoter')
        OR (scope <> 'global' AND tenant_id = split_part(current_user, '__', 1))
    );

-- BĐ5: đóng fact cũ khi thay thế. Vai nào được UPDATE cột nào do GRANT ở V2 quyết
-- (chỉ known_during, status); policy ở đây chỉ giới hạn hàng được chạm.
CREATE POLICY fact_close ON fact FOR UPDATE
    USING (tenant_id = split_part(current_user, '__', 1)
           OR (scope = 'global' AND current_user = 'promoter'))
    WITH CHECK (tenant_id = split_part(current_user, '__', 1)
                OR (scope = 'global' AND current_user = 'promoter'));
