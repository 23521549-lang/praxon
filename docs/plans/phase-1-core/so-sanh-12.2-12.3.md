# So sánh lần đo 12.2 với lần chạy lại 12.3

- Lần 1 (12.2): đo 2026-11-10T07:43:49.881175+00:00, `code_commit 7cc8fcb`, wall_time 80.4 s.
- Lần 2 (12.3): đo 2026-11-10T09:00:50.745713+00:00, `code_commit 583274e`, wall_time 78.3 s.
- Tiêu chí: 4 giá trị chỉ số + 8 cận khoảng tin cậy bằng nhau CHÍNH XÁC cho cả 35 cặp (trừ `wall_time`/`run_id`/`measured_at`).
- Phạm vi (đề xuất 12.3 §0.3): chỉ 4 chỉ số + CI — KHÔNG so tập khóa fact (12.2 không sản xuất manifest H1) và KHÔNG so token audit (0 lần gọi model cả hai lần).

## Kiểm sáu điều kiện tái lập (spec dòng 191)

| Điều kiện | Lần 1 | Lần 2 | Kết quả |
|---|---|---|---|
| seed | 0 | 0 | ĐỦ |
| model_id + model_revision | Qwen/Qwen3-8B-GGUF@7c41481f | Qwen/Qwen3-8B-GGUF@7c41481f | ĐỦ |
| code_commit | 7cc8fcb | 583274e | GAP (đăng ký trước) |
| config_hash | 13e98fec | 13e98fec | ĐỦ |
| data_hash | 6564b2e2 | 6564b2e2 | ĐỦ |
| cache còn nguyên | 0 lần gọi model (tokens 0) | 0 lần gọi model (tokens 0) | ĐỦ |

Gap `code_commit`: lần chạy lại ghi `583274e`, lần đầu ghi `7cc8fcb`. Theo quy tắc đăng ký trước (đề xuất 12.3 §0.2.2), gap này được tính là "chỉ khác tài liệu": diff `7cc8fcb..583274e` đã kiểm — đúng 2 file (file JSON báo cáo mới + 1 dòng trạng thái trong plan), 0 thay đổi code. Verdict vẫn là `reproducible` nếu 4 chỉ số trùng chính xác VÀ 5 điều kiện còn lại đủ.

## Bảng từng cặp (35 cặp)

| Tenant | Điều kiện | 4 chỉ số + 8 cận CI |
|---|---|---|
| m1 | Chỉ Declare | TRÙNG |
| m1 | Cách ly | TRÙNG |
| m1 | Gộp chung | TRÙNG |
| m1 | Phân tầng bỏ phiếu | TRÙNG |
| m1 | Phân tầng phủ quyết | TRÙNG |
| m1 | Phân tầng đồng thuận | TRÙNG |
| m1 | Tài liệu cộng dữ liệu | TRÙNG |
| m2 | Chỉ Declare | TRÙNG |
| m2 | Cách ly | TRÙNG |
| m2 | Gộp chung | TRÙNG |
| m2 | Phân tầng bỏ phiếu | TRÙNG |
| m2 | Phân tầng phủ quyết | TRÙNG |
| m2 | Phân tầng đồng thuận | TRÙNG |
| m2 | Tài liệu cộng dữ liệu | TRÙNG |
| m3 | Chỉ Declare | TRÙNG |
| m3 | Cách ly | TRÙNG |
| m3 | Gộp chung | TRÙNG |
| m3 | Phân tầng bỏ phiếu | TRÙNG |
| m3 | Phân tầng phủ quyết | TRÙNG |
| m3 | Phân tầng đồng thuận | TRÙNG |
| m3 | Tài liệu cộng dữ liệu | TRÙNG |
| m4 | Chỉ Declare | TRÙNG |
| m4 | Cách ly | TRÙNG |
| m4 | Gộp chung | TRÙNG |
| m4 | Phân tầng bỏ phiếu | TRÙNG |
| m4 | Phân tầng phủ quyết | TRÙNG |
| m4 | Phân tầng đồng thuận | TRÙNG |
| m4 | Tài liệu cộng dữ liệu | TRÙNG |
| m5 | Chỉ Declare | TRÙNG |
| m5 | Cách ly | TRÙNG |
| m5 | Gộp chung | TRÙNG |
| m5 | Phân tầng bỏ phiếu | TRÙNG |
| m5 | Phân tầng phủ quyết | TRÙNG |
| m5 | Phân tầng đồng thuận | TRÙNG |
| m5 | Tài liệu cộng dữ liệu | TRÙNG |

## Verdict: `reproducible` — TÁI LẬP ĐƯỢC

- Số cặp trùng chính xác: **35/35**.
- Không có cặp nào lệch. 5/6 điều kiện đủ + gap `code_commit` đã đăng ký trước là "chỉ khác tài liệu".

Ghi chú: `wall_time` (80,4 s so với 78,3 s) và `run_id` khác nhau theo thiết kế, không tính vào verdict. Hàng DB của lần chạy lại (35 hàng `run`, 35 hàng `event`) được cập nhật cột `reproducibility`/`repro_gaps` sau bước so sánh này.
