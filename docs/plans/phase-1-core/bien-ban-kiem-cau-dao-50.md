# Biên bản kiểm cầu dao 50% — Giai đoạn 1 (lõi học), plan con 9, task 9.7

> **Trạng thái bản này: ĐÃ DUYỆT, ngày 7/11/2026.** Đã đưa vào `docs/plans/phase-1-core/` theo task 9.7 (commit riêng trên nhánh `feat/plan9-breaker-50`, merge vào `feat/integration`).
> Người soạn: subagent (chỉ đọc + soạn thảo, không sửa repo, không commit). Ngày soạn: 7/11/2026. **Cập nhật: 7/11/2026 ~12:05** (integration lên `3c17326`, 600 test; BPIC 2019 đã có qua Drive, md5 khớp; nhát cắt 9.5 không còn sống; evidence_episode_ids đã đóng — xem mục "Cập nhật ngày 7/11/2026 ~12:05" sau phần mở đầu).
> Mức bằng chứng: **đã chạy thử** = đã chạy lệnh thật từ máy này (ghi rõ lệnh + kết quả); **đã kiểm nguồn** = đã mở file thật (ghi rõ file + dòng + ngày đọc); **giả thuyết** = suy luận, ghi rõ cách kiểm. Chỉ hai mức đầu dùng được để quyết.

## Cập nhật ngày 7/11/2026 ~12:05

Ba thay đổi kể từ bản soạn đầu (sáng 7/11), đều đã kiểm:

1. **Integration lên `3c17326`, 600 test.** Merge thêm evidence_episode_ids (commit `2d7de92`, 6 file, 290 dòng thêm, 12 test mới) — lấp khoảng trống từ 6.4 (Insight nay mang id episode thật, test round-trip tới `FactRow.source_episode_ids` đúng UUID). 10/10 cổng xanh. Tổng commit trên nhánh: 84 (trước đó 82). Con số 53/68 không đổi (evidence_episode_ids không phải task plan).
2. **BPIC 2019 đã có — nhát cắt 9.5 không còn sống.** Thuận tự tải lên Drive; file `.xes` trong cache `~/.cache/praxon/bpic2019/`, 728.558.522 byte, md5 `4eb909242351193a61e1c15b9c3cc814` khớp đúng giá trị 4TU công bố (tính lại trực tiếp bằng `md5sum`, ngày 7/11/2026 ~12:05). Phương án A đã thành hiện thực; phương án B không còn cần. Việc bắt đầu task 9.5 chưa kiểm được nhánh/worktree (xem §7 mục 5) — parent xác nhận thêm.
3. **Rủi ro #6 (evidence_episode_ids) đã đóng; rủi ro #1 (đường tải BPIC 2019) đã giải quyết bằng đường vòng Drive.** RAM vẫn thấp (~811 MB khả dụng; đã dọn đĩa theo lệnh Thuận nhưng dọn đĩa không giải phóng RAM — xem rủi ro #2).

Các kết luận chính không đổi: 53/68 (77,9%), plan file stale 27/68, tại mốc 1/11 chỉ ~15/68 (22%) — cầu dao lẽ ra đã nhảy, biên bản viết trễ 6 ngày.

## 1. Tóm tắt — kết luận trước

| Câu hỏi | Trả lời |
|---|---|
| Mốc kiểm là gì, khi nào? | Cuối tuần 4, **1/11/2026** — hết plan con 9 (plan file, dòng "Kiểm cầu dao 50%: cuối tuần 4, 1/11/2026 — hết plan con 9"). Quy tắc (roadmap dòng 33): đến 50% thời gian mà chưa xong 50% việc cốt lõi thì cầu dao nhảy: cắt phạm vi ngay, không kéo dài. |
| Biên bản này viết khi nào? | **7/11/2026 — trễ 6 ngày** so với mốc 1/11. |
| Tại mốc 1/11, xong bao nhiêu? | **~15/68 task (22%)** — plan 1 (10 task, xong 3/10) + plan 2 (5 task, code xong 17/10). **Dưới mốc 50% (34/68). Theo quy tắc, cầu dao LẼ RA ĐÃ NHẢY tại 1/11.** |
| Hôm nay (7/11), xong bao nhiêu? | **53/68 task (77,9%)** — vượt xa mốc 50%. Cầu dao không còn lý do nhảy vì số lượng, nhưng biên bản vẫn phải ghi trung thực việc mốc đã trượt tại thời điểm kiểm và việc kiểm bị trễ. (Cập nhật ~12:05: integration nay ở `3c17326`, **600 test** — con số 53/68 không đổi vì evidence_episode_ids không phải task plan.) |
| Có cần cắt gì ngay không? | **Không.** Ở 78%, không còn thiếu 50% để phải cắt. (Cập nhật ~12:05: **9.5 không còn bị chặn** — dữ liệu BPIC 2019 đã có qua Drive, md5 khớp, xem §4.2; chỉ còn 10.3 chặn bởi yếu tố ngoài (R2) và 1 phép đo thật chưa chạy được (9.1 chờ RAM). Nhát cắt đã định trước là bỏ 9.5 **không còn sống**.) Xem §4. |
| Cổng 1 (29/11) có nguy cơ gì? | Chính: plan 11 (Kaggle — chưa đọc điều khoản, chưa có tài khoản/GPU) và plan 12 (chạy phần đo — phụ thuộc plan 11) + 10.3 (R2). Xem §5. |

## 2. Số liệu — đã xong bao nhiêu phần việc cốt lõi

### 2.1. Hai nguồn đếm không khớp — plan file stale

| Nguồn | Xong / tổng | Tỉ lệ | Cách đếm |
|---|---|---|---|
| Cột "Trạng thái" trong plan file | **27 / 68** | 39,7% | Đếm trực tiếp các dòng `\| X.Y \|` có cột Trạng thái = "xong" (lệnh `grep -E "^\| [0-9]+\.[0-9]+ \|" … \| awk -F'\|' '{print $5}'`, ngày 7/11/2026). |
| Thực tế trên nhánh `feat/integration` (commit thật + file thật) | **53 / 68** | **77,9%** | Đối chiếu từng task với commit merge trên integration + file code/test có mặt (xem §2.2). |

**Chênh lệch 26 task.** Plan file stale: nhiều task đã xong + merge vẫn ghi "chưa làm". Các task stale (plan file "chưa làm" nhưng đã xong thật): 2.1–2.5, 4.2, 5.1–5.4, 6.1, 6.2, 6.4, 6.5, 7.3, 7.4, 7.5, 8.1, 8.4, 8.5, 9.1, 9.2, 9.6, 10.1, 10.2, 10.5 (26 task). Ngoài ra plan file ghi "khẩu phần 65 task" ở hai chỗ trong khi thực tế có **68 dòng task** — con số 65 cũng stale (đã biết từ trước, không thuộc phạm vi task này).

**Hệ quả:** không được dùng cột Trạng thái của plan file làm đáp án cho mốc 50%. Đáp án đúng là **53/68 (thực tế)**, và plan file cần một đợt cập nhật trạng thái nữa (đã có tiền lệ: commit `557f683` + `4fe85e3`).

### 2.2. Từng plan con — thực tế trên `feat/integration`

Nhánh `feat/integration`, HEAD `3c17326` ("Merge episode-id evidence for Reflector insights into integration", ngày 7/11/2026). Tổng **84 commit** trên nhánh. Cây sạch (`git status` trống, ngày 7/11/2026). (Cập nhật ~12:05: trước đó là `3f234c2`, 82 commit — thêm merge `3c17326` của evidence_episode_ids, commit `2d7de92`.)

| Plan con | Thực tế (xong/tổng) | Plan file ghi | Bằng chứng (commit/file trên integration) |
|---|---|---|---|
| 1 — Nền móng kho và cổng máy | **10/10** | 10/10 | Commit `4609f70` (3/10/2026, plan con 1 + review). Gói `packages/core`, `packages/platform`, `tools/`, `.github/workflows/ci.yml` có mặt. Review plan file ghi "đạt". |
| 2 — Lược đồ và bất biến dữ liệu | **5/5** | 0/5 (stale) | Migration `V1__tables.sql` … `V6__promoter_read_candidate.sql` có mặt; `tests/integration/test_invariants.py` có mặt (34 hàm `def test_`, đếm tĩnh ngày 7/11/2026 — gồm 21 phép tấn công + các test bất biến thêm sau); `compose.yml` có mặt ở gốc kho. Merge `26ebc5b` (6/11/2026) đưa plan 2 vào integration; các commit DB gốc dated 17/10/2026 (`440d7d8`, `9e8e16e`, `509c313`). |
| 3 — Hồ sơ dữ liệu và phép chia | **4/4** | 4/4 | Merge `2087f81` (7/11/2026): `1b9f6d7` (3.1), `035ab22` (3.2), `4b6cec2` (3.3), `1a70cbd` (3.4). |
| 4 — Khám phá Declare | **5/5** | 4/5 (stale 4.2) | `01c0fb3` (4.1 ADR) + `b7de92c` (test từ vựng); merge `9ea5fd6` (plan4-declare-index, 4.2); merge `8241b36` (4.3/4.4/4.5). |
| 5 — Bộ sinh bán tổng hợp | **4/4** | 0/4 (stale) | Merge `364bb23` (7/11/2026): `97e136c` (5.1), `a3187a7` (5.2), `c93e767` (5.3), `61ff59f` (5.4). |
| 6 — Adapter mô hình, Reflector, F1 | **5/5** | 1/5 (stale) | `08c70d0` (6.1), `a1770b3` (6.2), 6.3 (merge `1e0bd1d`, đợt 2), `b74c563` (6.4), `20ac9fe` (6.5). |
| 7 — Vòng học | **7/7** | 4/7 (stale 7.3/7.4/7.5) | 7.1/7.2 (merge `7c51405`), 7.3/7.4/7.5 (merge `3ac7c1e`, đợt 1 — `governor.py`, `beta.py` có mặt), 7.6/7.7 (merge `eb9e2ba`), phương án P (`6d56436`), payload D+F (`c3aa2ff`). |
| 8 — Baseline và đường cong khởi động lạnh | **5/5** | 2/5 (stale 8.1/8.4/8.5) | 8.2 (`a4b75a3`), 8.3 (`880f40c`), merge `d8f9e2a` (8.1 `b09229c`, 8.4 `4f60c65`, 8.5 `f0217f2`). |
| 9 — Đường vào tài liệu, rubric, hiệu chỉnh | **5/7** | 2/7 (stale 9.1/9.2/9.6) | 9.1 (`9ebf8d0`, merge `3f234c2`), 9.2 (`2eba217`, merge `da3fdc2`), 9.3 (`496dc6a`), 9.4 (`ef13f64`, rubric khóa bằng commit), 9.6 (`0f41f3f`, merge `06216b2`). **Chưa xong: 9.5 (dữ liệu đã có qua Drive, md5 khớp — xem §4.2; việc bắt đầu task chưa kiểm được nhánh/worktree, xem §7 mục 5), 9.7 (chính biên bản này).** Ngoài plan: evidence_episode_ids (lấp khoảng trống từ 6.4) đã merge tại `3c17326` (commit `2d7de92`, 6 file, 290 dòng thêm) — không phải task plan nên không đổi tổng 53/68. |
| 10 — Bộ điều phối, bảy điều kiện, ToolGateway | **3/5** | 0/5 (stale) | 10.1 (`b527af3`), 10.2 (`331631b`), merge `b03b8b3`; 10.5 (`23b3d65`, merge `56e0958`, đợt 1 — `gateway/tool_gateway.py` có mặt). **Chưa xong: 10.3 (chặn R2), 10.4 (hoãn sau 10.1+10.3).** |
| 11 — Chạy đầy đủ trên Kaggle | **0/4** | 0/4 | Chưa làm. Chặn: điều khoản Kaggle chưa đọc, chưa có tài khoản/GPU. |
| 12 — Khóa cấu hình và chạy phần đo | **0/3** | 0/3 | Chưa làm. Chặn bởi plan 11 (và 10.x). |
| 13 — Báo cáo và demo một lệnh | **0/4** | 0/4 | Chưa làm. Chặn bởi plan 12. **13.4 (spec giai đoạn 2a) chưa tới hạn (tuần nghỉ 30/11–6/12).** |
| **Tổng** | **53/68 (77,9%)** | **27/68 (39,7%)** | |

### 2.3. Số test và cổng máy (trạng thái hiện tại)

- **600 test case lúc chạy** trên integration HEAD `3c17326` (theo kiểm độc lập của parent, `pytest --ignore=tests/perf --no-cov`, exit 0, ngày 7/11/2026). Đếm tĩnh (ngày 7/11/2026 ~12:05): **551 hàm `def test_`** trong 51 file test (`grep -rn "def test_" tests/ --include="*.py"`) — chênh 49 là do test tham số hóa (một hàm sinh nhiều ca). Hai con số nhất quán, không mâu thuẫn. (Trước đó: 588 lúc chạy / 539 tĩnh tại `3f234c2`.)
- **10/10 cổng công cụ xanh** trên kết quả merge (theo kiểm độc lập của parent, ngày 7/11/2026). Cổng CI trên GitHub chưa kiểm được từ máy này trong đợt soạn này — ghi rõ để parent kiểm bổ sung trước khi trình (xem §6, mục chưa kiểm được).
- **Không thoái cấp** được ghi nhận qua các đợt merge gần đây (số test tăng đơn điệu: 195 → 299 → 339 → 361 → 481 → 513 → 530 → 539 → 561 → 570 → 588 → 600; độ phủ giữ ≥ 95%).

## 3. Đánh giá mốc 50% — cầu dao có nhảy không?

### 3.1. Quy tắc (đã kiểm nguồn)

- Roadmap dòng 33 (đã mở thật, ngày 7/11/2026): "**Khẩu phần cố định, theo Shape Up.** Mỗi giai đoạn có số tuần chốt trước. **Đến 50% thời gian mà chưa xong 50% việc cốt lõi thì cầu dao nhảy: cắt phạm vi ngay, không kéo dài.**"
- Plan file: "Kiểm cầu dao 50%: cuối tuần 4, **1/11/2026** — hết plan con 9." Mốc 50% = **34/68 task**.
- Spec dòng 239 (R7, đã mở thật): rủi ro "Phình phạm vi" — cách xử "Khẩu phần cố định, cầu dao 50%", mức Nhẹ, dấu hiệu "Chu kỳ vượt 50% khẩu phần", hạn kiểm "Liên tục".

### 3.2. Tại mốc 1/11/2026 — cầu dao LẼ RA ĐÃ NHẢY

Bằng chứng ngày commit trên `feat/integration` (lệnh `git log --format="%h %ad %s" --date=short`, ngày 7/11/2026):

- **Chỉ 8 commit dated ≤ 1/11/2026** trên nhánh integration. **74 commit dated 6–7/11/2026.** Không có commit nào dated 2–5/11.
- 8 commit trước mốc gồm: `4609f70` (3/10, plan 1) + 7 commit dated 17/10 (công việc DB plan 2: `440d7d8` Postgres+RLS, `9e8e16e` V4, `509c313` V5, `1723233` bỏ hard-code mật khẩu, `ba1b0e9` CI, `83e1295`/`ecdb044` AGENTS.md).
- Công việc đợt 1 (4.2, 7.3, 7.4, 7.5, 10.5 — merge `3ac7c1e`) dated **6/11/2026**, tức sau mốc. Mọi task commit của đợt 2 và các plan 3, 5, 6, 8, 9, 10 đều dated 6–7/11/2026.

**Trạng thái tại 1/11/2026 (tính theo công việc đã xong, dù merge sau): plan 1 (10 task) + plan 2 (5 task) = 15/68 task (22%).** Tính khắt khe hơn (chỉ tính thứ đã merge vào integration trước mốc): plan 1 = 10/68 (15%), vì plan 2 mới merge vào integration ngày 6/11 (`26ebc5b`).

**Kết luận:** tại mốc 1/11, dù tính theo cách nào (22% hay 15%), dự án cũng **dưới xa mốc 50% (34 task)**. Theo đúng quy tắc roadmap dòng 33, **cầu dao lẽ ra đã nhảy tại 1/11** — cắt phạm vi ngay, không kéo dài.

**Vì sao không nhảy lúc đó (ghi trung thực, không bào chữa):** biên bản này viết trễ 6 ngày, và không có bản ghi nào cho thấy đã có một lần kiểm cầu dao vào 1/11. Công việc sau đó dồn vào một đợt burst 6–7/11 (74 commit) và đuổi kịp. Đây là một lệch quy trình cần ghi nhận, không phải một lỗi kỹ thuật: mốc kiểm đã bị bỏ qua, không phải đã kiểm rồi cho qua.

### 3.3. Hôm nay (7/11/2026) — đã vượt mốc, không còn lý do nhảy vì số lượng

- **53/68 task (77,9%)**, vượt mốc 50% (34 task) tới 19 task.
- Các plan con 1–8 xong hoàn toàn (10+5+4+5+4+5+7+5 = 45 task). Plan 9 xong 5/7. Plan 10 xong 3/5.
- **Cầu dao không nhảy hôm nay** vì tiêu chí số lượng đã vượt. Nhưng §3.2 vẫn phải giữ trong biên bản: mốc đã trượt tại thời điểm kiểm, và việc kiểm trễ 6 ngày là một bài học quy trình (mốc kiểm cần người giữ lịch, không chờ tới khi viết biên bản mới nhớ).

## 4. Cắt gì nếu chưa đạt — đề xuất (để Thuận quyết, không tự quyết)

Không cần cắt ngay (đang ở 78%). Phần này liệt kê **thứ tự cắt đã định trước trong plan** + **nhát cắt đang "sống"** (task đã chặn sẵn), để Thuận quyết nếu phần còn lại trượt tới cổng 1.

### 4.1. Thứ tự cắt đã định trong plan (đã kiểm nguồn)

Plan file, bảng 13 plan con + mục "Thứ tự cắt khi cầu dao nhảy, theo lộ trình":

1. **Plan 6 thu về bài đo F1** (nhát cắt 1) — *đã hết hiệu lực: plan 6 xong 5/5, không còn gì để thu.*
2. **Bỏ phần điều kiện dữ liệu trên BPIC 2019 trong plan 9 (task 9.5)** (nhát cắt 2) — *đã hết hiệu lực (cập nhật ~12:05): dữ liệu BPIC 2019 đã có qua Drive, md5 khớp — xem §4.2.*
3. **Giảm số lần rút bootstrap trong plan 10** (nhát cắt 3) — *chưa cần; bootstrap hiện `Settings.bootstrap_draws = 1000`.*

Thứ tự cắt toàn dự án (roadmap dòng ~193, đã mở thật): (1) giai đoạn nghiên cứu 4 tuần sang danh sách để sau; (2) SSO và xuất audit đầy đủ sang sau phát hành; (3) tầng procedural và skill sang sau phát hành; (4) adapter Claude chỉ còn chạy trên sự kiện ghi sẵn. **Không bao giờ cắt:** baseline và tái lập, cách ly tenant, cổng tool, log chỉ thêm, rà pháp lý trước khi bán.

### 4.2. Nhát cắt 9.5 (BPIC 2019) — ĐÃ HẾT HIỆU LỰC (cập nhật ~12:05)

- **Tình trạng mới:** **phương án A đã thành hiện thực.** Thuận đã tự tải BPIC 2019 lên Drive (thư mục `1W644SKasF107ECcBpIZGQURNfoWJpJ-G`, file `BPI_Challenge_2019.zip`, 16.898.402 byte); file `.xes` đã có trong cache `~/.cache/praxon/bpic2019/BPI_Challenge_2019.xes`, **728.558.522 byte, md5 `4eb909242351193a61e1c15b9c3cc814` — khớp đúng giá trị 4TU công bố** (tính lại bằng `md5sum` trực tiếp trên file, ngày 7/11/2026 ~12:05; md5 của file zip là `67bfa5ebb06032730a6ed2bc7488eeb2`). Nguồn gốc: 4TU, DOI `10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1`, CC BY 4.0. Đường tải ndownloader vẫn chết (HTTP 504, 12 lần liên tiếp tới 10:56) nhưng **không còn chặn 9.5** — dữ liệu đã có bằng đường vòng Drive, đúng như phương án A đã nêu.
- **Phương án B (cắt 9.5 ngay) không còn cần nữa** — nhát cắt này đã hết hiệu lực cùng với việc dữ liệu đã về. Không còn đề xuất cắt nào đang sống trong biên bản này.
- **Việc bắt đầu task 9.5 — chưa kiểm được (ghi rõ):** kiểm ngày 7/11/2026 ~12:05 — không thấy nhánh `feat/plan9-bpic2019` (local hay remote) và không thấy worktree nào cho 9.5 (`git branch -a`, `git worktree list`, `git ls-remote` đều trống). Parent cho biết task đã được spawn — có thể luồng mới spawn chưa tạo nhánh, hoặc chưa spawn xong. **Không khẳng định 9.5 đang chạy.** Parent xác nhận thêm trước khi trình biên bản (xem §7 mục 5).
- **Ảnh hưởng nếu (giả sử) cắt:** không còn áp dụng — ghi lại để đối chiếu: mất phần kiểm điều kiện thuộc tính phân loại trên loại matching (4 loại `Item Category`); phần tối thiểu 30 case của 9.6 hoãn theo; cổng 1 không đòi BPIC 2019 nên cắt cũng không ảnh hưởng cổng 1.

### 4.3. Các nhát cắt khác — chưa cần, chỉ ghi để theo dõi

| Nhát cắt | Khi nào dùng | Ảnh hưởng |
|---|---|---|
| Giảm số lần rút bootstrap (plan 10) | Nếu plan 11 chậm vì mỗi lần chạy tốn thời gian rút bootstrap | Khoảng tin cậy rộng hơn; không đổi đáp án. Chưa cần vì plan 10 mới tới 10.2. |
| Hoãn 10.3 (checkpoint R2) nếu R2 không có | Nếu tới tuần 6 vẫn chưa có bucket/credentials R2 | Plan 11 mất khả năng chạy tiếp từ checkpoint (phép thử đứt phiên 11.3 không làm được); cổng 1 không đòi R2 trực tiếp nhưng plan 11 đòi. |
| Hoãn 10.4 (trần token) | Đã hoãn theo plan (sau 10.1+10.3); cần migration thêm trạng thái `budget_exceeded` | Không chặn cổng 1 nếu chạy đo không chạm trần; rủi ro là chạy Kaggle không có trần. |

## 5. Rủi ro còn mở (chưa xử lý — trạng thái từng cái)

| # | Rủi ro / phát hiện | Trạng thái | Ảnh hưởng nếu không xử lý |
|---|---|---|---|
| 1 | **Đường tải BPIC 2019 chết (HTTP 504 ×12)** | **Đã giải quyết bằng đường vòng (Drive) — cập nhật ~12:05.** Dữ liệu đã có trong cache, md5 khớp đúng giá trị 4TU công bố (tính lại trực tiếp, ngày 7/11/2026). Đường ndownloader vẫn 504 nhưng không còn chặn 9.5. | Không còn ảnh hưởng — 9.5 chỉ còn chờ bắt đầu task (chưa kiểm được nhánh, xem §7 mục 5). |
| 2 | **Đo thật 9.1 chưa chạy được — RAM** | Mở. Máy ảo chỉ còn ~811 MB RAM khả dụng (kiểm `free -m` ngày 7/11/2026 ~12:05; dao động 521–1.424 MB trong ngày), model Qwen3-8B cần ~6,5 GB. Đường dữ liệu thật đã chạy tới sát mô hình (52 đoạn, 5.649 trace nạp đủ) nhưng **số luật trích được / bị cổng Beta loại chưa biết**. Đã dọn đĩa theo lệnh Thuận (xóa `4tu-extract`, `4tu.zip`, `praxon-df-fresh`, `.venv` 25 worktree đã merge — chỉ giữ venv integration; đĩa 12G → 9,5G đã dùng) — **dọn đĩa không giải phóng RAM** (RAM vẫn ~829 MB sau khi dọn; ~5,3 GB RAM bị dùng ở tầng khác, không thuộc về process nào nhìn thấy được). | Điều kiện 7 (tài liệu cộng dữ liệu) chưa có số thật; 10.2 đang chạy với tập luật tài liệu rỗng. Cần chạy lại lệnh khi máy có ≥6,5 GB trống (~30 phút) — hoặc chạy model trên máy khác (Thuận cho biết có 250 đô cloud Docker có thể chạy model — hướng dẫn/chạy đang được chuẩn bị riêng, ngoài phạm vi biên bản này). |
| 3 | **10.3 cần R2 bucket/credentials** | Mở. Không có gì trong settings; Thuận chưa cung cấp. | Plan 11 (chạy tiếp từ checkpoint) + 10.4 đều chặn sau 10.3. |
| 4 | **Plan 11 chặn bởi Kaggle** | Mở. Điều khoản Kaggle chưa đọc (luồng song song tuần 1, chưa có kết quả trong repo), chưa có tài khoản/GPU. | Plan 11 → 12 → 13 đều chặn sau nó; cổng 1 (29/11) phụ thuộc chuỗi này. Đây là **rủi ro lớn nhất cho cổng 1**. |
| 5 | **target_scope** (Curator đặt tên tenant, DB chỉ nhận `'tenant'`/`'global'`) | Mở, chờ Thuận quyết. Coordinator 10.1 hiện fail-fast (ValueError) khi gặp tên tenant thay vì lặng lẽ map sai. | Đường tenant chưa chạy end-to-end qua DB (chỉ đường global được test DB); cần một task riêng ánh xạ `'global'`/`'tenant'` khi Thuận quyết. |
| 6 | **evidence_episode_ids rỗng** (Trajectory chỉ mang `case_id`, không mang id episode) | **Đã đóng — cập nhật ~12:05.** Đã merge tại `3c17326` (commit `2d7de92`, 6 file, 290 dòng thêm, 12 test mới): `EpisodeRow` thêm `id: UUID`, `Trajectory` thêm `episode_ids`, `replay()` điền, Reflector gắn id episode của trajectory thể hiện mẫu (mỗi trajectory tối đa 2 id; luật không trajectory nào thể hiện thì evidence rỗng, không bịa); test round-trip tới `FactRow.source_episode_ids` đúng UUID. 600 test qua, 10/10 cổng xanh. | Không còn ảnh hưởng. Lưu ý còn lại (thấp): luật suy biến activation == target (vd `precedence(A,A)`) không gắn evidence — ngoài phạm vi, hành vi khóa bởi code. |
| 7 | **Độ mạnh tiên nghiệm 2,0 vs 4,0** | Mở, chờ Thuận duyệt riêng. Hiệu chỉnh 9.6 đo được 2,0 tốt nhất (lên nhanh nhất, biên bất biến lớn nhất, 0 lỗi) nhưng mặc định vẫn giữ 4,0 — luồng cố tình không tự đổi vì là quyết định chính sách. | Không chặn gì (4,0 vẫn an toàn, đã đo 0 lỗi); chỉ là chưa áp dụng khuyến nghị đo được. |
| 8 | **F1 0,7153 vs GPT-4 0,7946 (R5)** | Mở, theo dõi. Model 8B kém GPT-4 0,08 ở Overall — thấp hơn nhưng không "thấp xa" theo R5; vượt GPT-4 ở init (0,95 vs 0,90) và end (0,92 vs 0,29). | Cần theo dõi ở Reflector: bao nhiêu luật bị cổng loại. Không chặn merge 6.5. |
| 9 | **Rubric row-10 wording** ("approve"/"reject" vs "approve"/"reject" và "yes"/"no") | Mở, đã hỏi Thuận 7/11 ~01:52, chưa có trả lời. | Chỉ là chi tiết mô tả; không đổi quy tắc/ngưỡng. Nếu sửa sau, cần commit riêng theo luật khóa-bằng-commit của rubric. |
| 10 | **Plan file stale** (27/68 "xong" trong khi thực tế 53/68) | Mở. Đã có tiền lệ cập nhật (`557f683` + `4fe85e3`) nhưng sau đó lại stale vì các đợt merge 6–7/11. | Mốc kiểm sau sẽ sai nếu dùng cột Trạng thái làm đáp án. Cần một đợt cập nhật trạng thái nữa (đề xuất riêng, không tự sửa trong biên bản này). |
| 11 | **Môi trường: VM thay mới + Postgres tắt** | Mở, tái diễn. Lần gần nhất: Postgres tắt sau khi VM thay mới; đã khôi phục (`pg_ctlcluster start` + đặt lại `trust` cho TCP localhost + tạo lại DB `praxon`). | Mỗi lần VM thay mới, cổng DB đỏ giả (không phải lỗi code) cho tới khi khôi phục môi trường. Cần quy trình khôi phục ghi sẵn, không chẩn đoán lại từ đầu mỗi lần. |
| 12 | **Kiểm cầu dao trễ 6 ngày (biên bản này)** | Ghi nhận tại §3.2. | Mốc kiểm sau (cổng 1, 29/11) cần người giữ lịch; không để tới khi viết biên bản mới nhớ. |

## 6. Triển vọng cổng 1 (29/11/2026) — còn thiếu gì

Cổng 1 đòi sáu điều kiện (plan file, mục "Cổng 1 phải đạt gì"):

| # | Điều kiện cổng 1 | Trạng thái hôm nay (7/11) | Còn thiếu |
|---|---|---|---|
| 1 | Một lệnh chạy bảy điều kiện trên cả hai nguồn dữ liệu | **Một phần.** 10.2 chạy bảy điều kiện bằng một lệnh trên bộ chuẩn bán tổng hợp; 8.5 chạy báo cáo trên cả hai nguồn (tổng hợp + 5 đô thị BPIC 2015) nhưng chưa gộp thành một lệnh duy nhất. | Lệnh 13.1 (gộp hai nguồn vào một lệnh). |
| 2 | In bốn chỉ số theo từng tenant kèm khoảng tin cậy và bản ghi lần chạy | **Có.** 8.5 in bốn chỉ số + CI 95% theo tenant; 10.1 ghi `run` đủ sáu trường tái lập. | Gộp vào lệnh 13.1. |
| 3 | Chạy lại ra đúng kết quả đó | **Có (đã kiểm trên từng phần).** 10.1/10.2/8.5 đều có test tái lập; 8.5 từng sửa lỗi thứ tự `frozenset` làm CI đổi giữa hai lần chạy (đã sửa bằng sắp xếp theo khóa). | Kiểm tái lập trên lệnh 13.1 đầy đủ. |
| 4 | 21 phép tấn công bị chặn | **Có.** Plan 2 xong; `test_invariants.py` có 34 hàm test (gồm 21 phép tấn công + test bất biến thêm sau). | Không. |
| 5 | CI xanh ở mọi cổng máy | **Có trên máy này; chưa kiểm trên GitHub trong đợt soạn này.** 10/10 cổng công cụ + 600 test xanh trên integration HEAD `3c17326` (kiểm độc lập của parent, 7/11/2026). | Parent kiểm trạng thái CI GitHub trước khi trình biên bản (mục chưa kiểm được, xem dưới). |
| 6 | Ba nền móng phòng điều khiển có test | **Có.** Bảng `event` (7.7), `ToolGateway` (10.5), quyết định người dùng thành `Candidate` (9.3) — cả ba có test. | Không. |

**Chuỗi việc còn lại tới cổng 1:** 10.3 (R2) → 10.4 (trần token) → 11.1–11.4 (Kaggle) → 12.1–12.3 (khóa cấu hình + chạy phần đo + kiểm tái lập) → 13.1–13.3 (lệnh + báo cáo + báo cáo cổng 1). Tuần còn lại: tuần 5 (2–8/11, đang chạy), 6, 7, 8 (tới 29/11). Nút thắt là **plan 11 (Kaggle)** và **10.3 (R2)** — cả hai đều phụ thuộc yếu tố ngoài (điều khoản/tài khoản/GPU; bucket/credentials), không phải code.

## 7. Chỗ chưa kiểm được (ghi rõ, không ước đoán)

| # | Chưa kiểm được | Cách kiểm |
|---|---|---|
| 1 | Trạng thái CI trên GitHub (điều kiện 5 của cổng 1) — chỉ biết cổng xanh trên máy này. | Mở Actions của repo `23521549-lang/praxon`, nhánh `feat/integration`, xem lần chạy gần nhất. |
| 2 | Số task "xong" theo định nghĩa review cấp 3 (Thuận review ở cổng giai đoạn) — cột Review trong plan file vẫn "chưa review" ở mọi task trừ plan 1. Con số 53/68 là "code xong + merge + cổng xanh", chưa phải "đã qua review cấp 3". | Thuận review ở cổng giai đoạn (cấp 3) — ngoài phạm vi biên bản này. |
| 3 | Liệu plan 2 có đủ 5/5 theo đúng cổng ra từng task (đặc biệt 2.1 docker compose chạy từ máy trống) — chỉ kiểm được file `compose.yml` có mặt + migration + test có mặt; chưa chạy `docker compose up` vì Docker không cài trên máy này. | Chạy `docker compose up -d` rồi `SELECT 1` qua vai ứng dụng từ máy có Docker. |
| 4 | Số luật Wabo trích được / bị cổng Beta loại (9.1 đo thật) — xem rủi ro #2 (§5). | Chạy lệnh 9.1 khi máy có ≥6,5 GB RAM trống. |
| 5 | Task 9.5 đã bắt đầu chưa (nhánh/worktree) — kiểm ngày 7/11/2026 ~12:05 không thấy nhánh `feat/plan9-bpic2019` hay worktree nào (dữ liệu thì đã có, md5 khớp). | Parent xác nhận: `git branch -a` / `git worktree list` / `git ls-remote origin feat/plan9-bpic2019`. |

## Phụ lục — nguồn của từng con số chính

| Con số | Nguồn |
|---|---|
| 68 dòng task; 27 "xong" theo plan file; 41 "chưa làm" | Plan file `docs/plans/phase-1-core/Plan giai đoạn 1 — lõi học.md`, đếm trực tiếp bằng `grep` + `awk` cột Trạng thái, ngày 7/11/2026. |
| 53/68 thực tế | Đối chiếu từng task với commit merge + file trên `feat/integration` HEAD `3c17326` (bảng §2.2). |
| 8 commit ≤ 1/11; 74 commit 6–7/11; 84 commit tổng | `git log --format="%h %ad %s" --date=short` trên worktree `~/workspace/praxon-wt/integration`, ngày 7/11/2026 ~12:05 (trước đó 82 tại `3f234c2`; +2: merge `3c17326` + commit `2d7de92`). |
| 15/68 (22%) tại 1/11 | Plan 1 (10 task, commit `4609f70` 3/10) + plan 2 (5 task, commit DB dated 17/10: `440d7d8`, `9e8e16e`, `509c313`). |
| 600 test case; 10/10 cổng xanh | Kiểm độc lập của parent trên integration HEAD `3c17326`, ngày 7/11/2026 (ghi trong `~/MEMORY.md`). |
| 551 hàm `def test_`; 51 file test | Đếm tĩnh `grep -rn "def test_" tests/ --include="*.py"`, ngày 7/11/2026 ~12:05. |
| 34 hàm test trong `test_invariants.py` | Đếm tĩnh `grep -c "def test_" tests/integration/test_invariants.py`, ngày 7/11/2026. |
| F1 0,7153 vs GPT-4 0,7946 | Task 6.5, commit `20ac9fe` (đo trên bộ 104 câu, seed 42, temperature=0, 0 lần gọi hỏng). |
| BPIC 2019: 728.558.522 byte, md5 `4eb909242351193a61e1c15b9c3cc814` (khớp đúng) | `md5sum` trực tiếp trên `~/.cache/praxon/bpic2019/BPI_Challenge_2019.xes`, ngày 7/11/2026 ~12:05; file zip `BPI_Challenge_2019.zip` 16.898.402 byte, md5 `67bfa5ebb06032730a6ed2bc7488eeb2`; nguồn gốc `~/workspace/praxon-wabo-bpic2019-sources.md` (§3). Đường ndownloader vẫn 504 (×12 tới 10:56) nhưng không còn chặn 9.5. |
| RAM ~811 MB khả dụng (dao động 521–1.424 MB); model cần ~6,5 GB | `free -m` ngày 7/11/2026 ~12:05 + báo cáo task 9.1 (commit `9ebf8d0`). |
| evidence_episode_ids đã đóng: commit `2d7de92`, merge `3c17326` | `git log` + `git show --stat` trên worktree integration, ngày 7/11/2026 ~12:05 (6 file, 290 dòng thêm, 33 dòng xóa, 12 test mới). |
| Quy tắc cầu dao; thứ tự cắt | Roadmap `docs/roadmap/Lộ trình — Enterprise Agentic.md` dòng 33, 65, 71, ~193; plan file bảng 13 plan con. |
| Cổng 1 sáu điều kiện | Plan file, mục "Cổng 1 phải đạt gì"; roadmap dòng 71. |
