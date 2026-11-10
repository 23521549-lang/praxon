# Báo cáo cổng 1 — DRAFT (chưa trình cổng)

- **Trạng thái:** DRAFT — chưa trình cổng. Chỉ đánh FINAL khi cả sáu điều kiện ĐẠT (hoặc ĐẠT kèm mục mở đã được Thuận chấp nhận bằng văn bản).
- **Commit HEAD lúc viết:** `3c27472` (nhánh `feat/integration`, merge 12.1).
- **Ngày viết:** 7/11/2026.
- **Làm mới:** 10/11/2026 (HEAD `583274e`): C4 21→25, C5 bằng chứng run 42778699898.
- **Người viết:** Huỳnh Ngọc Thuận.
- **Bằng chứng có cấu trúc:** `bao-cao-cong-1-evidence.json` (cùng thư mục). Mọi con số trong báo cáo này đều có mặt trong file JSON đó; chạy `python -m tools.verify_gate1` để đối chiếu số trong JSON với phép đo chạy lại.
- **Kết luận cổng qua hay không:** KHÔNG có trong báo cáo này. Kết luận là của Thuận ở review cấp 3.

## Sáu điều kiện cổng — nguyên văn (plan file, dòng 12–21)

Lấy nguyên từ lộ trình, không diễn giải thêm:

1. Một lệnh chạy bảy điều kiện trên cả hai nguồn dữ liệu.
2. In bốn chỉ số theo từng tenant kèm khoảng tin cậy và bản ghi lần chạy.
3. Chạy lại ra đúng kết quả đó.
4. 25 phép tấn công bị chặn.
5. CI xanh ở mọi cổng máy.
6. Ba nền móng phòng điều khiển có test.

## Bảng tổng hợp

| # | Điều kiện | Verdict | Phép thử / con số | Commit đo | Ngày đo |
|---|---|---|---|---|---|
| C1 | Một lệnh, 7 điều kiện, 2 nguồn | CHƯA ĐỦ | Lệnh 13.1 (chưa có) | — | — |
| C2 | 4 chỉ số + CI + bản ghi lần chạy | CHƯA ĐỦ | Từ đầu ra lệnh 13.1 (chưa có) | — | — |
| C3 | Chạy lại ra đúng kết quả | CHƯA ĐỦ | Chạy lệnh 13.1 hai lần (chưa có) | — | — |
| C4 | 25 phép tấn công bị chặn | ĐẠT | 25/25 phép tấn công bị chặn (34/34 test) | 3c27472 | 7/11/2026 |
| C5 | CI xanh ở mọi cổng máy | ĐẠT | Tại chỗ 11/11 xanh; GitHub xanh (run 42778699898, success, 11m33s, 10/11; jobs cong-may + clean-machine) | 583274e | 10/11/2026 |
| C6 | Ba nền móng phòng điều khiển có test | ĐẠT | 23 test qua (7 + 9 + 7) | 3c27472 | 7/11/2026 |

## C1 — Một lệnh chạy bảy điều kiện trên cả hai nguồn dữ liệu

**Verdict: CHƯA ĐỦ.**

Phép thử: lệnh 13.1 chạy từ máy trống qua compose, thoát 0, in đủ 7 điều kiện x 2 nguồn. Lệnh này chưa có (task 13.1 chưa làm).

Bằng chứng từng phần đã có:

- 10.2 chạy bảy điều kiện bằng một lệnh trên bộ chuẩn bán tổng hợp (`python -m praxon_core.eval.experiments`, 35 hàng: 5 tenant x 7 điều kiện).
- 8.5 báo cáo trên cả hai nguồn (`python -m praxon_core.eval.report`, 20 hàng) nhưng là lệnh riêng, không phải lệnh gộp hai nguồn.

Còn thiếu: task 13.1 (viết lệnh gộp hai nguồn).

Nguồn luật điều kiện 7: chưa có đo thật lúc viết DRAFT này — đo thật 9.1 đang chạy trong sandbox Docker (kiểm lần cuối 19:00 ngày 7/11/2026: 1 tiến trình `wabo_rules` sống, log còn trống vì báo cáo chỉ in cuối; sandbox dừng ~20:13). Không suy ra số luật từ lần chạy code cũ.

## C2 — In bốn chỉ số theo từng tenant kèm khoảng tin cậy và bản ghi lần chạy

**Verdict: CHƯA ĐỦ.**

Phép thử: từ đầu ra lệnh 13.1 — bốn chỉ số x từng tenant (5 tenant x 2 nguồn x 2 điều kiện = 20 hàng), mỗi chỉ số kèm CI 95%; bản ghi lần chạy có mặt (hàng `run` đủ sáu trường tái lập). Lệnh 13.1 chưa có.

Bằng chứng từng phần đã có:

- 8.5 in bốn chỉ số kèm CI 95% theo tenant (20 hàng: (5 tổng hợp + 5 BPIC) x 2 điều kiện).
- 10.1 ghi `run` đủ sáu trường tái lập.

Còn thiếu: task 13.1 (in qua lệnh gộp, không phải qua lệnh 8.5 riêng).

## C3 — Chạy lại ra đúng kết quả đó

**Verdict: CHƯA ĐỦ.**

Phép thử: chạy lệnh 13.1 hai lần, so đầu ra (bằng nhau tuyệt đối hoặc đẳng thức đã định nghĩa); `reproducibility_gaps` rỗng. Lệnh 13.1 chưa có.

Bằng chứng từng phần đã có:

- Hàm `reproducibility_gaps` (`learning/coordinator.py` dòng 187) + `is_reproducible` (dòng 221) đã tồn tại.
- Lỗi tái lập do thứ tự `frozenset` trong 8.5 đã tìm + sửa (sắp xếp fact theo khóa + test hồi quy).

Còn thiếu: task 13.1 (chạy hai lần) + task 12.3 (kiểm tái lập phía phần đo).

## C4 — 25 phép tấn công bị chặn

**Verdict: ĐẠT.**

Phép thử: `python -m pytest tests/integration/test_invariants.py` — xanh: **25/25 phép tấn công bị chặn** (34/34 test trong file, gồm 25 tấn công + 1 control dương phải QUA + 8 kiểm tra cấu trúc/control). Commit đo `3c27472`, ngày 7/11/2026.

**Đã giải quyết — lệch số 21/25:** commit `8429321` (7/11 12:26 UTC) đã cập nhật plan (dòng 19, 30, 81, task 2.5 dòng 92) và spec (dòng 204) thành 25 phép tấn công; câu "21/21" còn lại ở spec dòng 43 là bản ghi lịch sử ngày 3/10/2026 (lúc đó bộ test có 21 phép), không phải yêu cầu hiện tại. Không còn mục mở cho C4.

## C5 — CI xanh ở mọi cổng máy

**Verdict: ĐẠT.**

Hai số:

- (a) Tại chỗ: 11/11 cổng máy xanh, pytest chính 718 passed + perf 1 passed (commit đo `3c27472`, ngày 7/11/2026).
- (b) GitHub: xanh. Lần chạy gần nhất trên `feat/integration` là run 42778699898 (success, 11m33s, 10/11/2026; jobs cong-may + clean-machine đều success; HEAD `583274e`). Hai lần chạy đỏ cũ (run 42368407153 và 42367835583, đỏ vì 1 test `test_main_real_m1` thiếu tệp BPIC 2015 trên runner) đã được sửa bằng các commit lấy dữ liệu BPIC trong CI (`6fb8a1f`, `264f7eb`, `e44e020`).

Không còn thiếu cho C5.

Lưu ý: đánh giá "1 chưa kiểm (trạng thái GitHub CI)" trong biên bản cầu dao §6 nay đã cũ — CI đã kiểm và đã xanh (run 42778699898, success, 11m33s, 10/11), không còn "chưa kiểm".

## C6 — Ba nền móng phòng điều khiển có test

**Verdict: ĐẠT.**

Chạy ba file test, tất cả qua (tổng 23 test, commit đo `3c27472`, ngày 7/11/2026):

- Bảng `event`: 7 test (`tests/integration/test_event_log.py`).
- `ToolGateway`: 9 trường hợp chạy, từ 6 hàm test (1 hàm tham số hóa 4 quyết định: ALLOW, DENY, ASK_USER, DEFER_TO_POLICY) (`tests/test_tool_gateway.py`).
- Quyết định người dùng thành `Candidate`: 7 test (`tests/test_human_decision.py`).

Không còn gì — chỉ cần chạy lại để ghi số vào báo cáo FINAL.

## Còn thiếu để đóng cổng (theo thứ tự)

1. **11.1–11.4 rồi 12.1–12.3** — chuỗi đã chạy (11.1 smoke test qua trình duyệt, 12.1/11.3 đang triển khai phần code); xong thì có dữ liệu đo + khóa cấu hình cho 13.1.
2. **13.1** — viết lệnh gộp hai nguồn; chạy lệnh đó (C1/C2) và chạy hai lần (C3).
3. **13.2** — báo cáo kết quả; 13.3 trích số của 13.2 (không tính lại).
4. **13.3 bước FINAL** — điền số thật vào JSON + Markdown, chạy `verify_gate1.py` (thoát 0), đánh FINAL, trình ở cổng giai đoạn để Thuận kết luận.
5. **13.4** (spec giai đoạn 2a) không nằm trong chuỗi đóng cổng 1 — làm song song, tuần nghỉ 30/11–6/12, không chặn FINAL.

## Mục mở cần Thuận quyết

- Không có mục mở nào khác lúc viết DRAFT này.

## Phụ lục

### Lệnh chạy lại từng con số

- C4: `python -m pytest tests/integration/test_invariants.py`
- C6: `python -m pytest tests/integration/test_event_log.py tests/test_tool_gateway.py tests/test_human_decision.py`
- C5-local: 11 cổng máy — `python -m tools.check_tool_versions`, `python -m ruff check .`, `python -m ruff format --check .`, `python -m mypy`, `lint-imports --config .importlinter`, `python -m tools.check_env_access`, `python -m tools.check_thirdparty_data`, `python -m tools.check_no_stdlib_shadowing`, `python -m tools.check_licenses`, `python -m tools.check_core_standalone`, `python -m pytest --ignore=tests/perf` + `python -m pytest tests/perf --no-cov`.
- Kiểm toàn bộ JSON: `python -m tools.verify_gate1` (thoát 0 khi khớp, 1 khi lệch).

### Log CI liên quan (E6)

Lần chạy gần nhất `42778699898` (10/11/2026, HEAD `583274e`): success, 11m33s, jobs cong-may + clean-machine đều success.

Run đỏ cũ `42368407153` (và `42367835583` trước đó) đã được sửa xong bằng các commit lấy dữ liệu BPIC trong CI (`6fb8a1f`, `264f7eb`, `e44e020`); log lỗi cũ (`test_main_real_m1` thiếu tệp `/home/runner/.cache/praxon/bpic2015/BPIC15_1.xes` trên runner) không còn xảy ra.

### Đo thật 9.1

Chưa có đo thật lúc viết DRAFT này. Lần chạy lại trong sandbox Docker đang chạy (kiểm lần cuối 19:00 ngày 7/11/2026: 1 tiến trình `wabo_rules` sống, log còn trống vì báo cáo chỉ in cuối; sandbox dừng ~20:13 ngày 7/11/2026). Nếu đo xong trước khi viết FINAL thì số luật trích/bị loại vào mục C1; nếu chưa xong thì báo cáo FINAL ghi rõ "chưa có đo thật".
