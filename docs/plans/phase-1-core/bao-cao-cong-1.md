# Báo cáo cổng 1 — DRAFT (chưa trình cổng)

- **Trạng thái:** DRAFT — chưa trình cổng. Chỉ đánh FINAL khi cả sáu điều kiện ĐẠT (hoặc ĐẠT kèm mục mở đã được Thuận chấp nhận bằng văn bản).
- **Commit HEAD lúc viết:** `3c27472` (nhánh `feat/integration`, merge 12.1).
- **Ngày viết:** 7/11/2026.
- **Người viết:** Huỳnh Ngọc Thuận.
- **Bằng chứng có cấu trúc:** `bao-cao-cong-1-evidence.json` (cùng thư mục). Mọi con số trong báo cáo này đều có mặt trong file JSON đó; chạy `python -m tools.verify_gate1` để đối chiếu số trong JSON với phép đo chạy lại.
- **Kết luận cổng qua hay không:** KHÔNG có trong báo cáo này. Kết luận là của Thuận ở review cấp 3.

## Sáu điều kiện cổng — nguyên văn (plan file, dòng 12–21)

Lấy nguyên từ lộ trình, không diễn giải thêm:

1. Một lệnh chạy bảy điều kiện trên cả hai nguồn dữ liệu.
2. In bốn chỉ số theo từng tenant kèm khoảng tin cậy và bản ghi lần chạy.
3. Chạy lại ra đúng kết quả đó.
4. 21 phép tấn công bị chặn.
5. CI xanh ở mọi cổng máy.
6. Ba nền móng phòng điều khiển có test.

## Bảng tổng hợp

| # | Điều kiện | Verdict | Phép thử / con số | Commit đo | Ngày đo |
|---|---|---|---|---|---|
| C1 | Một lệnh, 7 điều kiện, 2 nguồn | CHƯA ĐỦ | Lệnh 13.1 (chưa có) | — | — |
| C2 | 4 chỉ số + CI + bản ghi lần chạy | CHƯA ĐỦ | Từ đầu ra lệnh 13.1 (chưa có) | — | — |
| C3 | Chạy lại ra đúng kết quả | CHƯA ĐỦ | Chạy lệnh 13.1 hai lần (chưa có) | — | — |
| C4 | 21 phép tấn công bị chặn | ĐẠT (về thực chất) + MỤC MỞ | 25/25 phép tấn công bị chặn (34/34 test) | 3c27472 | 7/11/2026 |
| C5 | CI xanh ở mọi cổng máy | CHƯA ĐẠT | Tại chỗ 11/11 xanh; GitHub ĐỎ (run 42368407153) | 3c27472 | 7/11/2026 |
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

## C4 — 21 phép tấn công bị chặn

**Verdict: ĐẠT (về thực chất) + MỤC MỞ.**

Phép thử: `python -m pytest tests/integration/test_invariants.py` — xanh: **25/25 phép tấn công bị chặn** (34/34 test trong file, gồm 25 tấn công + 1 control dương phải QUA + 8 kiểm tra cấu trúc/control). Commit đo `3c27472`, ngày 7/11/2026.

**Mục mở — lệch số 21/25:** plan (dòng 19, 30, 81, task 2.5 dòng 92) và spec (dòng 43, 204) ghi "21 phép tấn công", nhưng file test hiện có 25 phép tấn công (docstring đầu file ghi "25 phép tấn công trên 6 bất biến dữ liệu"). Báo cáo này ghi cả hai số, không lặng lẽ viết "21/21" hay "25/25". Cần Thuận quyết: cập nhật plan/spec thành 25, hay thu hẹp định nghĩa tấn công. Đây là quyết định, không phải code.

## C5 — CI xanh ở mọi cổng máy

**Verdict: CHƯA ĐẠT.**

Hai số:

- (a) Tại chỗ: 11/11 cổng máy xanh, pytest chính 718 passed + perf 1 passed (commit đo `3c27472`, ngày 7/11/2026).
- (b) GitHub: ĐỎ. 5 lần chạy gần nhất trên `feat/integration` đều `failure`. 2 lần gần nhất (run 42368407153 "Merge plan status 10.4", 11:29 UTC 7/11/2026; run 42367835583 "Merge 10.4 token budget", 11:21 UTC) đỏ vì đúng 1 test: `test_main_real_m1` (`tests/test_difference.py:159`) do thiếu tệp `/home/runner/.cache/praxon/bpic2015/BPIC15_1.xes` trên runner — thiếu dữ liệu bên thứ ba, không phải lỗi code.

Còn thiếu: sửa CI (task riêng, cần đề xuất riêng — các phương án: CI tải dữ liệu BPIC 2015 trong workflow; cache dữ liệu giữa các lần chạy; test bỏ qua khi thiếu dữ liệu — chưa chọn phương án nào) + một lần chạy CI xanh trên HEAD.

Lưu ý: đánh giá "1 chưa kiểm (trạng thái GitHub CI)" trong biên bản cầu dao §6 nay đã cũ — CI đã kiểm và đang ĐỎ, không còn "chưa kiểm".

## C6 — Ba nền móng phòng điều khiển có test

**Verdict: ĐẠT.**

Chạy ba file test, tất cả qua (tổng 23 test, commit đo `3c27472`, ngày 7/11/2026):

- Bảng `event`: 7 test (`tests/integration/test_event_log.py`).
- `ToolGateway`: 9 trường hợp chạy, từ 6 hàm test (1 hàm tham số hóa 4 quyết định: ALLOW, DENY, ASK_USER, DEFER_TO_POLICY) (`tests/test_tool_gateway.py`).
- Quyết định người dùng thành `Candidate`: 7 test (`tests/test_human_decision.py`).

Không còn gì — chỉ cần chạy lại để ghi số vào báo cáo FINAL.

## Còn thiếu để đóng cổng (theo thứ tự)

1. **Sửa CI (C5)** — task riêng, đề xuất riêng (chọn 1 trong 3 phương án ở mục C5); xong thì một lần chạy CI xanh trên HEAD. Không chờ 13.1.
2. **Thuận quyết số 21/25 (C4)** — một quyết định, không phải code; ghi vào báo cáo (và, nếu Thuận đồng ý đổi số, sửa plan/spec bằng đề xuất riêng).
3. **11.1–11.4 rồi 12.1–12.3** — chuỗi đã chạy (11.1 smoke test qua trình duyệt, 12.1/11.3 đang triển khai phần code); xong thì có dữ liệu đo + khóa cấu hình cho 13.1.
4. **13.1** — viết lệnh gộp hai nguồn; chạy lệnh đó (C1/C2) và chạy hai lần (C3).
5. **13.2** — báo cáo kết quả; 13.3 trích số của 13.2 (không tính lại).
6. **13.3 bước FINAL** — điền số thật vào JSON + Markdown, chạy `verify_gate1.py` (thoát 0), đánh FINAL, trình ở cổng giai đoạn để Thuận kết luận.
7. **13.4** (spec giai đoạn 2a) không nằm trong chuỗi đóng cổng 1 — làm song song, tuần nghỉ 30/11–6/12, không chặn FINAL.

## Mục mở cần Thuận quyết

- **Số 21/25 (C4):** plan/spec ghi 21, file test có 25 — cập nhật số thành 25 hay thu hẹp định nghĩa tấn công?
- Không có mục mở nào khác lúc viết DRAFT này.

## Phụ lục

### Lệnh chạy lại từng con số

- C4: `python -m pytest tests/integration/test_invariants.py`
- C6: `python -m pytest tests/integration/test_event_log.py tests/test_tool_gateway.py tests/test_human_decision.py`
- C5-local: 11 cổng máy — `python -m tools.check_tool_versions`, `python -m ruff check .`, `python -m ruff format --check .`, `python -m mypy`, `lint-imports --config .importlinter`, `python -m tools.check_env_access`, `python -m tools.check_thirdparty_data`, `python -m tools.check_no_stdlib_shadowing`, `python -m tools.check_licenses`, `python -m tools.check_core_standalone`, `python -m pytest --ignore=tests/perf` + `python -m pytest tests/perf --no-cov`.
- Kiểm toàn bộ JSON: `python -m tools.verify_gate1` (thoát 0 khi khớp, 1 khi lệch).

### Log CI liên quan (E6)

Lần chạy gần nhất `42368407153` ("Merge plan status 10.4 into integration", 11:29 UTC 7/11/2026), job "Test và độ phủ":

```
_________________________ test_main_real_m1 _________________________
    def test_main_real_m1(capsys):
>       assert main(["--dataset", "m1", "--support", "0.5", "--confidence", "0.5"]) == 0
E       AssertionError: assert 1 == 0
tests/test_difference.py:159: AssertionError
----------------------------- Captured stderr call -----------------------------
thiếu tệp: /home/runner/.cache/praxon/bpic2015/BPIC15_1.xes
```

Lần trước đó `42367835583` ("Merge 10.4 token budget into integration", 11:21 UTC): cùng test, cùng lỗi, cùng tệp thiếu (`FAILED tests/test_difference.py::test_main_real_m1`). Cả hai lần chỉ có đúng 1 test đỏ trong toàn bộ suite.

### Đo thật 9.1

Chưa có đo thật lúc viết DRAFT này. Lần chạy lại trong sandbox Docker đang chạy (kiểm lần cuối 19:00 ngày 7/11/2026: 1 tiến trình `wabo_rules` sống, log còn trống vì báo cáo chỉ in cuối; sandbox dừng ~20:13 ngày 7/11/2026). Nếu đo xong trước khi viết FINAL thì số luật trích/bị loại vào mục C1; nếu chưa xong thì báo cáo FINAL ghi rõ "chưa có đo thật".
