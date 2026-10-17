-- V2 — Vai nhóm và phân quyền tối thiểu (plan con 2, task 2.2/2.4).
--
-- Mô hình hai tầng:
--   * Vai nhóm NOLOGIN (`g_ingestor`, …) giữ toàn bộ grant. Grant định nghĩa một lần.
--   * Vai login theo tenant dạng `<slug>__<chức-năng>` (vd `acme__reader`) kế thừa từ
--     vai nhóm tương ứng. Tenant là dữ liệu runtime nên vai login được tạo bởi
--     `tools/db_migrate.py --provision-tenant`, KHÔNG tạo trong migration này.
--   * Ngoại lệ duy nhất: `promoter` là vai login toàn cục (không thuộc tenant nào),
--     vì chỉ promoter được ghi `global` (BĐ4).
--
-- 7 vai suy ra trực tiếp từ cột "Ai được ghi" của spec (task 2.2 ghi 4 vai nhưng
-- thiếu người ghi run/event và thiếu phân biệt Curator/Governor trên candidate):
--   ingestor:    episode SELECT+INSERT (chỉ thêm, BĐ1)
--   curator:     candidate SELECT+INSERT (tạo đề xuất), SELECT episode/fact (evidence)
--   governor:    candidate SELECT+UPDATE (ghi quyết định)
--   applier:     fact SELECT+INSERT+UPDATE(2 cột) trong phạm vi tenant (BĐ3)
--   promoter:    như applier, thêm phạm vi global (BĐ4)
--   coordinator: run/event SELECT+INSERT (chỉ thêm, BĐ1)
--   reader:      SELECT mọi bảng (chịu RLS, BĐ2)
--
-- Không vai ứng dụng nào là superuser hay có BYPASSRLS (kiểm bằng test ở task 2.5).

-- Vai là đối tượng cấp cluster (không theo database) nên khối tạo vai dưới đây
-- tự kiểm tra tồn tại: chạy migration trên database thứ hai của cùng cluster
-- không được lỗi.
DO $$
DECLARE
    r text;
BEGIN
    FOREACH r IN ARRAY ARRAY[
        'g_ingestor', 'g_curator', 'g_governor', 'g_applier',
        'g_promoter', 'g_coordinator', 'g_reader'
    ]
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN', r);
        END IF;
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'promoter') THEN
        CREATE ROLE promoter LOGIN PASSWORD 'promoter-dev-only' IN ROLE g_promoter;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public
    TO g_ingestor, g_curator, g_governor, g_applier, g_promoter, g_coordinator, g_reader;

-- episode: chỉ thêm (BĐ1). Không UPDATE/DELETE cho bất kỳ vai nào.
GRANT SELECT, INSERT ON episode TO g_ingestor;

-- event/run: chỉ thêm (BĐ1).
GRANT SELECT, INSERT ON event TO g_coordinator;
GRANT SELECT, INSERT ON run TO g_coordinator;

-- candidate: curator tạo, governor ghi quyết định; applier/promoter đọc để áp.
GRANT SELECT, INSERT ON candidate TO g_curator;
GRANT SELECT, UPDATE ON candidate TO g_governor;
GRANT SELECT ON candidate TO g_applier, g_promoter;

-- fact: applier/promoter. UPDATE giới hạn đúng 2 cột phục vụ thao tác "đóng fact cũ"
-- khi thay thế (BĐ5): thu hẹp known_during + chuyển status. Sửa confidence/statement
-- hay bất kỳ cột nào khác đều bị từ chối ở tầng quyền — không cần tin code.
GRANT SELECT, INSERT ON fact TO g_applier;
GRANT UPDATE (known_during, status) ON fact TO g_applier;
GRANT SELECT, INSERT ON fact TO g_promoter;
GRANT UPDATE (known_during, status) ON fact TO g_promoter;

-- reader: chỉ đọc, mọi hàng đi qua RLS (BĐ2).
GRANT SELECT ON episode, event, run, candidate, fact TO g_reader;

-- promoter đọc episode/event/run: RLS vẫn lọc 0 hàng tenant (vai này không có
-- phần tenant trong tên) — grant này để test "chưa đặt tenant thì 0 hàng" đúng
-- nghĩa "0 hàng" chứ không phải "báo lỗi thiếu quyền", và để promoter đọc được
-- context khi cần. Không mở thêm hàng nào: policy tenant_isolation đã chặn.
GRANT SELECT ON episode, event, run TO g_promoter;

-- Không có GRANT DELETE trên bất kỳ bảng nào cho bất kỳ vai ứng dụng nào.
-- Không GRANT UPDATE trên episode/event/run: chỉ thêm là tuyệt đối ở tầng quyền.
