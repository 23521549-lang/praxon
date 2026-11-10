# So sánh lần đo 12.2 lan-3 với lần chạy lại 12.3 (lan-4)

- Lần 1 (12.2): đo 2026-11-10T13:27:20.573212+00:00, `code_commit 65e7052`, wall_time 80.0 s.
- Lần 2 (12.3): đo 2026-11-10T15:23:58.840021+00:00, `code_commit 65e7052`, wall_time 78.7 s.
- Tiêu chí: 4 giá trị chỉ số + 8 cận khoảng tin cậy bằng nhau CHÍNH XÁC cho cả 35 cặp (trừ `wall_time`/`run_id`/`measured_at`).
- Phạm vi (đề xuất 12.3 §0.3): chỉ 4 chỉ số + CI — KHÔNG so tập khóa fact (12.2 không sản xuất manifest H1) và KHÔNG so token audit (0 lần gọi model cả hai lần).

## Kiểm sáu điều kiện tái lập (spec dòng 191)

| Điều kiện | Lần 1 | Lần 2 | Kết quả |
|---|---|---|---|
| seed | 0 | 0 | ĐỦ |
| model_id + model_revision | Qwen/Qwen3-8B-GGUF@7c41481f | Qwen/Qwen3-8B-GGUF@7c41481f | ĐỦ |
| code_commit | 65e7052 | 65e7052 | ĐỦ |
| config_hash | 13e98fec | 13e98fec | ĐỦ |
| data_hash | 6564b2e2 | 6564b2e2 | ĐỦ |
| cache còn nguyên | 0 lần gọi model (tokens 0) | 0 lần gọi model (tokens 0) | ĐỦ |

Gap `code_commit`: KHÔNG CÓ — lần chạy lại ghi cùng `65e7052` với lan-3 (đúng code đã đo lan-3, không có diff tài liệu nào giữa hai lần). 6/6 điều kiện đủ.

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
- Không có cặp nào lệch. 6/6 điều kiện đủ (code_commit giống nhau, không có gap).

Ghi chú: `wall_time` (80.0 s so với 78.7 s) và `run_id` khác nhau theo thiết kế, không tính vào verdict. Hàng DB của lần chạy lại (35 hàng `run`, 35 hàng `event`) được cập nhật cột `reproducibility`/`repro_gaps` sau bước so sánh này.
