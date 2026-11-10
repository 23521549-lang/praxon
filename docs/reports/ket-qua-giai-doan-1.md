# Báo cáo kết quả giai đoạn 1

Sinh bằng lệnh: `python -m tools.generate_phase1_report` — mọi số trong báo cáo này đều do một lệnh sinh ra (xem bảng ánh xạ trong đề xuất 13.2); mục chưa có đầu vào ghi `CHƯA CÓ`, không bịa số.

## 1. Ảnh chụp đầu vào

- Commit `feat/integration` lúc sinh: `583274e5fbd5f6f120f5d23c050f460f1e321efc`
- Ngày sinh (UTC+7): 2026-11-10
- Khóa cấu hình 12.1: commit `8a34d67e121c2b8005fc680c8fb1f996c31bdda0`
- `config_hash` (khóa đo): `13e98fec4a6088cf30b63c1efea594460193be605efaf957eb5d548d4a225f20`
- `data_hash` (BPIC 2015, cả năm đô thị): `0edb706dcf2afb637a0c7b57ee9d284fc8958ee50b9594a05e3365ec5a805b92`
- Seed: 42 (bộ chuẩn bán tổng hợp + đo F1 6.5 + hiệu chỉnh 9.6)
- Model: Qwen/Qwen3-8B-GGUF (revision `7c41481f57cb95916b40956ab2f0b139b296d974`) — mặc định Settings, mẫu dùng ở 6.5/9.1
- Trường Settings (20): bootstrap_draws, checkpoint_every_n_cases, checkpoint_store, cpu_model_base_url, database_url, model_id, model_max_retries, model_retry_base_delay_seconds, model_revision, model_timeout_seconds, openai_api_key, openai_base_url, reflector_batch_size, reflector_max_insights_per_batch, s3_access_key_id, s3_bucket, s3_endpoint_url, s3_secret_access_key, token_budget_reserve_per_call, token_budget_total
- Đầu vào đã dùng:
  - `bpic2019.txt` (sha256 `467878a2d3a225b819ff487d67a34addde5af56ebc98458833b0a1140472d3c6`)
  - `calibration-beta.txt` (sha256 `112d6b2dddccb67f388dca731c4cc788297ae4809647e42feb6359610ce84409`)
  - `cold-start.txt` (sha256 `67f925cc4bacf779628165769b6a5a55920a25bb3491c1df15cce7b92990c0fe`)
  - `profile-bpic2015.txt` (sha256 `50884559d573a882b569ae59c3ae37201428dafd923928daf0bb1e10fcc4132b`)
  - `split-bpic2015.txt` (sha256 `48ebe81eef7e4248bc11573417daba89d689a1bc02d96442fd14d7385289d448`)
- Đầu vào còn thiếu:
  - B1.3 F1 tổng micro (6.5) — chờ đo lại 6.5 (cần llama-server chạy)
  - B1.4 F1 theo mẫu (6.5) — chờ đo lại 6.5 (cần llama-server chạy)
  - B1.5 F1 bộ sinh 5.3 (độ khó) — chờ lệnh sinh chưa xác nhận
  - B2.1 Wabo: trích được / không gắn được / cổng Beta loại / token — chờ 9.1 đo thật
  - B2.2 Bốn chỉ số theo tenant x điều kiện kèm CI 95% — chờ 13.1 (lệnh) + 12.2 (lần chạy đo)
  - B2.3 Tái lập: chạy lại lần hai ra đúng kết quả lần đầu hay không — chờ 12.3
  - B2.4 Phép thử đứt phiên: verdict 4 lần chạy — chờ 11.3 (lần chạy Kaggle chờ 11.1 + 11.2)

## 2. Dữ liệu

| Đô thị | case | sự kiện | loại hoạt động |
| --- | --- | --- | --- |
| 1 | 1.199 | 52.217 | 398 |
| 2 | 832 | 44.354 | 410 |
| 3 | 1.409 | 59.681 | 383 |
| 4 | 1.053 | 47.293 | 356 |
| 5 | 1.156 | 59.083 | 389 |

Nguồn: `python -m praxon_core.datasets.profile`

| Đô thị | tổng case | học | hiệu chỉnh | đo |
| --- | --- | --- | --- | --- |
| 1 | 1.199 | 719 | 240 | 240 |
| 2 | 832 | 499 | 166 | 167 |
| 3 | 1.409 | 846 | 281 | 282 |
| 4 | 1.053 | 631 | 211 | 211 |
| 5 | 1.156 | 694 | 230 | 232 |

Nguồn: `python -m praxon_core.datasets.split`

- Tổng case: 251.734 (trong năm 2018: 251.268; ngoài năm: 466; thiếu Item Category: 0; không có thời điểm bắt đầu: 0)

| Loại matching | case (2018) | luật | quyết định |
| --- | --- | --- | --- |
| 2-way match | 891 | luật 2 | auto_approve |
| 3-way match, invoice after GR | 15.131 | luật 2 | auto_approve |
| 3-way match, invoice before GR | 220.752 | luật 2 | auto_approve |
| Consignment | 14.494 | luật 2 | auto_approve |
- Hiệu chỉnh min_matching_cases=30: cả 4 loại đều đủ ngưỡng (nhỏ nhất '2-way match': 891 case, gấp 29,7 lần) — ngưỡng được giữ nguyên.

Nguồn: `python -m praxon_core.learning.bpic2019`

F1 bộ sinh (độ khó, 5.3): CHƯA CÓ — chờ lệnh sinh chưa xác nhận

## 3. Trích luật từ văn bản (F1, 6.5)

CHƯA CÓ — chờ chạy lại lệnh đo `python -m tools.measure_f1_text_to_ltl` (cần llama-server chạy; lần đo 6.5 đã xong nhưng đầu ra lệnh chưa lưu thành file, không chép số từ báo cáo review)

## 4. Luật Wabo (9.1)

CHƯA CÓ — chờ 9.1 đo thật

## 5. Hiệu chỉnh cổng Beta (9.6)

| Độ mạnh | trung vị trace để đẩy | biên bất biến | lên sai | gỡ sai | lên |
| --- | --- | --- | --- | --- | --- |
| 2,0 | 13,0 | 0,2930 | 0 | 0 | 20 |
| 4,0 | 16,0 | 0,1181 | 0 | 0 | 20 |
| 6,0 | 20,0 | 0,0324 | 0 | 0 | 20 |
Chọn: 2,0.

- Độ mạnh đã áp: 2,0 (`prior_strength_default = 2` trong `learning/default_rule_table.toml`, merge `ed677db`).
- `min_matching_cases = 30` (giữ nguyên theo 9.5 — nhỏ nhất 891 case, gấp 29,7 lần ngưỡng).

Nguồn: `python -m praxon_core.learning.calibration`

## 6. Bốn chỉ số (12.2 qua lệnh 13.1)

CHƯA CÓ — chờ 13.1 (lệnh) + 12.2 (lần chạy đo)

## 7. Đường cong khởi động lạnh (8.4)

| trace | luật | precision | recall | vi phạm | neg.transfer | chế độ |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 0 | 0,000 | 0,000 | 0,000 | 0,000 | trial (giám sát) |
| 5 | 20 | 1,000 | 0,357 | 0,050 | 0,000 | active |
| 10 | 20 | 1,000 | 0,357 | 0,050 | 0,000 | active |
| 20 | 20 | 1,000 | 0,357 | 0,050 | 0,000 | active |
| 40 | 20 | 1,000 | 0,357 | 0,050 | 0,000 | active |

Nguồn: `python -m praxon_core.eval.cold_start`

## 8. Tái lập (12.3)

CHƯA CÓ — chờ 12.3

## 9. Phép thử đứt phiên (11.3)

CHƯA CÓ — chờ 11.3 (lần chạy Kaggle chờ 11.1 + 11.2)

## 10. Caveat + câu hỏi mở

- Luật Wabo (9.1) khi đo xong sẽ mang `status="active"` (không phải `trial`) và bằng chứng đo trên toàn bộ trace gộp, kể cả phần đo — hai quyết định đã ghi trong docstring của `learning/wabo_rules.py` để review; nếu Thuận muốn `trial` thì đổi một dòng.
- F1 succession: chưa có đầu vào đo — khi có đầu ra F1 sẽ ghi rõ số ca của mẫu succession (mẫu nhỏ thì không kết luận).
- Đáp án BPIC 2015 lấy từ phần đo nên có nhiễu riêng — số tuyệt đối hơi bi quan; báo cáo này so các điều kiện bằng chênh lệch, không so số tuyệt đối.
- Plan file từng stale 26 task (review đợt 2, §3.3) — số task trong báo cáo này đếm từ commit merge, không lấy từ cột Trạng thái của plan file.
- Hai mục còn mở từ review đợt 2 đã xong: rubric dòng 10 (merge `150ec6d`) và target_scope (merge `6c12991`); rubric §2.2 (merge `b76796b`), spec prose 4→2 (merge `1ab9269`), target_scope option B (merge `ac1f210`).
- Plan file ghi "65 task" nhưng đếm được 68 dòng task — số "65" là số lỗi thời.
