-- V4 — BĐ3: fact chỉ được ghi từ candidate đã có quyết định (plan con 2, task 2.4).
--
-- Bất biến BĐ3 của spec: "Tri thức chỉ ghi qua applier và promoter, và cả hai
-- chỉ áp candidate đã có quyết định." V1–V3 đã chặn "ai được ghi" (quyền + RLS);
-- migration này chặn "ghi từ cái gì":
--
--   1. Khóa ngoại: candidate_id phải trỏ tới candidate có thật.
--   2. Trigger: candidate được áp phải đang ở trạng thái 'approved'.
--
-- candidate_id NULL được cho qua: fact không nhất thiết sinh từ candidate
-- (ví dụ dữ liệu seed). Ràng buộc chỉ áp khi fact khai nguồn từ một candidate.
--
-- Hàm trigger chạy với quyền của người gọi (KHÔNG SECURITY DEFINER — spec cấm),
-- nên phép đọc bảng candidate trong hàm vẫn chịu RLS: applier chỉ thấy được
-- candidate của đúng tenant mình, thử áp candidate của tenant khác bị chặn ở đây.

ALTER TABLE fact
    ADD CONSTRAINT fact_candidate_fk
    FOREIGN KEY (candidate_id) REFERENCES candidate (id);

CREATE OR REPLACE FUNCTION fact_check_candidate_approved()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    candidate_status text;
BEGIN
    IF NEW.candidate_id IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT status INTO candidate_status
    FROM candidate
    WHERE id = NEW.candidate_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'fact: candidate % không tồn tại', NEW.candidate_id;
    END IF;
    IF candidate_status IS DISTINCT FROM 'approved' THEN
        RAISE EXCEPTION
            'fact: chỉ được áp candidate đã duyệt (candidate % đang ở trạng thái %)',
            NEW.candidate_id, candidate_status;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER fact_candidate_approved
    BEFORE INSERT OR UPDATE OF candidate_id ON fact
    FOR EACH ROW
    EXECUTE FUNCTION fact_check_candidate_approved();
