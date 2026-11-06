# 0004 — Nguồn của từng mẫu Declare

Ngày: 7/11/2026 · Trạng thái: **đã chốt**, chủ dự án duyệt 7/11/2026

**Bối cảnh.** Spec dòng 225 đặt bất biến clean room cho phần khám phá Declare: "Viết từ định nghĩa hình thức trong bài báo, không mở mã nguồn pm4py; một bản quyết định kiến trúc ghi nguồn của từng mẫu; pm4py chỉ chạy như bộ đối chiếu riêng ngoài kho." Plan task 4.1 (dòng 129) là task thực hiện đúng câu đó: "Bản quyết định kiến trúc ghi nguồn của từng mẫu Declare | Tệp tồn tại ở `docs/decisions/`, mỗi mẫu trỏ một định nghĩa trong bài báo". Tới nay các task 4.2–4.5 đã xong và merge vào `feat/integration` (chỉ mục đầu/cuối, miner, perf 3,8s, đối chiếu pm4py trùng 6=6 và 69=69) nhưng bản ghi nguồn này vẫn chưa có — nghĩa là khẳng định "viết từ định nghĩa hình thức trong bài báo" hiện không kiểm được: không có chỗ nào ghi rõ "bài báo" là bài nào và định nghĩa của từng mẫu nằm ở đâu. ADR này lấp đúng chỗ trống đó. Ngoài ra, code Curator (`learning/curator.py`) ghi rõ "Mở rộng bảng khi ADR 4.1 chốt từ vựng đầy đủ" — bảng cặp mẫu đối nghịch đang chờ ADR này chốt từ vựng.

**Quyết định gì (một câu).** Chốt nguồn định nghĩa cho từng mẫu Declare mà dự án chạm tới, và chốt từ vựng canonical hai tầng của giai đoạn 1 (tầng 1: mẫu miner khám phá và eval đo được; tầng 2: mẫu chỉ ghi nguồn để diễn giải, không phát sinh fact trong giai đoạn 1).

---

## 1. Tiêu chí, viết trước khi so

| Mã | Tiêu chí | Vì sao quan trọng |
|---|---|---|
| C1 | Mỗi mẫu trong từ vựng trỏ đúng một định nghĩa trong một bài báo đã mở thật | Đây là cổng ra của task 4.1 ("mỗi mẫu trỏ một định nghĩa trong bài báo") và là bằng chứng clean room (spec dòng 225). Không có nguồn mở thật thì không tính. |
| C2 | Nguồn khớp với code đã merge (4.2–4.5) | ADR không được mâu thuẫn với miner/index/eval/pm4py đã merge; nếu mâu thuẫn thì phải nêu rõ và sửa ADR (không sửa code đã duyệt trong ADR này). |
| C3 | Từ vựng không vượt phạm vi plan con 4 | Thêm mẫu vào tầng phát sinh (miner/eval) là mở rộng plan; ADR chỉ ghi nguồn, không tự mở rộng phạm vi. |
| C4 | Định nghĩa đọc được trên trace hữu hạn | Log là trace hữu hạn; định nghĩa phải có nghĩa trên trace hữu hạn (LTLf), không phải chỉ trên hành vi vô hạn. |
| C5 | Tên mẫu không gây nhầm lẫn giữa các nguồn | Cùng một công thức mà hai bài gọi hai tên khác nhau thì phải chọn một tên canonical và ghi rõ tên kia là bí danh không dùng. |

---

## 2. Phương án đã cân nhắc

### 2.1. Điểm quyết định 1 — Nguồn chính cho định nghĩa của từng mẫu

| Phương án | C1 | C2 | C3 | C4 | C5 |
|---|---|---|---|---|---|
| **A — Leno, Dumas & Maggi 2018, Bảng 1 (+ Bảng 2 cho điều kiện dữ liệu) làm nguồn chính** | Đạt — một bảng duy nhất có đủ 12 mẫu quan hệ kèm công thức LTL + cột activation | Đạt — response/precedence trong bảng khớp miner; not_response/not_precedence khớp bảng đối nghịch của Curator | Đạt — bảng chỉ là nguồn tra cứu, không ép miner phải khám phá hết | Đạt — công thức dùng toán tử quá khứ (O, Y, S) trên trace hữu hạn | Đạt — tên mẫu trong bảng là tên chuẩn dùng trong code (`response`, `precedence`, `not_response`, `not_precedence`) |
| **B — Maggi, Bose & van der Aalst 2012 (p669.pdf) làm nguồn chính duy nhất** | Yếu — bài này chỉ định nghĩa tường minh response, precedence, responded existence, not succession; không có bảng đầy đủ (không có alternate/chain, không có init/end/succession) | Đạt — response/precedence khớp | Đạt | Yếu — công thức viết bằng LTL trên hành vi vô hạn (không nói rõ LTLf); phải tự suy ra cách đọc trên trace hữu hạn | Kém — bài này gọi công thức (a → ¬♦b) là "not succession", trong khi Leno 2018 và code gọi cùng công thức đó là "not response" (xem §5, mâu thuẫn đã phát hiện) |
| **C — Di Ciccio & Montali 2022 (Handbook, chương 4) làm nguồn chính duy nhất** | Đạt — chương có Bảng 1 (bộ mẫu lõi) + chương 3 (nền LTLf) + nguồn gốc Declare | Đạt | Đạt | Mạnh nhất — chương nói rõ Declare dùng LTLf (trace hữu hạn) | Đạt |
| **D — pm4py / Declare4Py làm nguồn định nghĩa** | **Loại — vi phạm C1/C2 và bất biến clean room.** Spec dòng 146/225: "không mở mã nguồn pm4py". pm4py chỉ là bộ đối chiếu (4.5), không phải nguồn định nghĩa. | | | | |
| **E — Grohs et al. 2023 làm nguồn định nghĩa** | **Loại — vi phạm C1.** Grohs chỉ dùng lại 5 mẫu (precedence, response, succession, init, end) từ nghiên cứu trước [19], không phải nguồn gốc của định nghĩa. Nó là nguồn cho *bộ đo* 6.5, không phải nguồn cho *định nghĩa*. | | | | |

**Phương án sống sót:** A, B, C (B và C yếu hơn A ở C1/C4/C5). **Bị loại:** D (phá bất biến clean room), E (không phải nguồn gốc định nghĩa).

### 2.2. Điểm quyết định 2 — Phạm vi từ vựng giai đoạn 1

| Phương án | C1 | C2 | C3 |
|---|---|---|---|
| **A — Hai tầng (đề xuất): tầng 1 = response, precedence (miner + eval + đối chiếu pm4py); tầng 2 = succession, init, end, not_response, not_precedence (chỉ ghi nguồn để diễn giải, không phát sinh fact trong giai đoạn 1); tầng 3 = các mẫu còn lại trong Bảng 1 của Leno 2018 (hoãn)** | Đạt — mọi mẫu dự án chạm tới đều có nguồn (§4) | Đạt — khớp đúng code đã merge (miner chỉ 2 mẫu; eval từ chối mẫu khác bằng ValueError; Curator chỉ có 2 cặp đối nghịch) | Đạt — không mở rộng miner/eval |
| **B — Một tầng phẳng: cả 7 mẫu (response, precedence, succession, init, end, not_response, not_precedence) đều "trong từ vựng"** | Đạt | **Kém — mâu thuẫn code:** eval (`eval/metrics.py`) báo `ValueError` với fact mẫu `succession` (test `test_mau_khong_ho_tro_thi_bao_loi` khẳng định điều đó); miner không khám phá succession/init/end; đối chiếu pm4py chỉ cho phép `{"response", "precedence"}`. Chọn B thì phải sửa code (thêm 5 mẫu vào miner + eval) — đó là mở rộng plan con 4, không phải việc của ADR này. | Kém — vượt phạm vi plan con 4 |
| **C — Tối thiểu: chỉ response + precedence là "trong từ vựng", còn lại là "ngoài"** | **Kém — không đạt cổng ra 4.1:** code và bài đo 6.5 đã chạm tới succession/init/end (bộ 104 câu dùng 5 mẫu) và not_response/not_precedence (bảng đối nghịch của Curator); nếu xếp chúng là "ngoài" thì ADR không ghi nguồn cho chúng, cổng ra "mỗi mẫu trỏ một định nghĩa" không đạt. | Đạt | Đạt |

**Phương án sống sót:** A, C (C yếu hơn A ở C1). **Bị loại:** B (mâu thuẫn code đã merge + vượt phạm vi plan).

### 2.3. Điểm quyết định 3 — Cách đọc định nghĩa: LTL hay LTLf (trace hữu hạn)

| Phương án | C4 | Ghi chú |
|---|---|---|
| **A — Đọc theo LTLf (trace hữu hạn), theo Di Ciccio & Montali 2022 §3 (đề xuất)** | Đạt — chương nói rõ Declare dùng LTLf vì "every process instance is expected to complete in a finite number of steps"; miner dùng chỉ mục đầu/cuối trên trace hữu hạn, khớp đúng cách đọc này | Công thức Leno 2018 (Bảng 1) dùng toán tử quá khứ (O, Y, S) vốn chỉ có nghĩa trên trace hữu hạn có điểm bắt đầu |
| **B — Đọc theo LTL (hành vi vô hạn) như Maggi 2012 viết** | Yếu — công thức (a → ♦b) trên hành vi vô hạn cho phép b xảy ra "ở đâu đó trong tương lai vô hạn", không khớp miner (miner kiểm b sau lần a cuối *trong cùng trace*); phải tự thêm quy ước "trong cùng trace" | Không có nguồn nào trong dự án nói rõ cách đọc này |

**Phương án sống sót:** A, B (B yếu hơn). Chọn A.

---

## 3. Quyết định

1. **Nguồn chính cho định nghĩa:** **Leno, Dumas & Maggi 2018, Bảng 1** (12 mẫu quan hệ: công thức LTL + cột activation) cho mọi mẫu quan hệ; **Bảng 2** của cùng bài cho dạng điều kiện dữ liệu MP-Declare (điều kiện kích hoạt ϕa + điều kiện tương quan ϕc). **Nguồn phụ:** Maggi, Bose & van der Aalst 2012 (CAiSE 2012) cho response/precedence và cho tên gọi của chỉ số support/confidence; **Di Ciccio & Montali 2022** (Handbook, chương 4) cho cách đọc LTLf + nguồn gốc Declare + cặp mẫu phủ định; **Grohs et al. 2023 §4.1** cho định nghĩa của succession/init/end (5 mẫu của bộ đo 6.5).
2. **Từ vựng giai đoạn 1 — hai tầng (phương án A, §2.2):**
   - **Tầng 1 (canonical, phát sinh được):** `response`, `precedence`. Miner (4.3) khám phá, eval (8.2) đo, pm4py đối chiếu (4.5) — chỉ hai mẫu này.
   - **Tầng 2 (canonical, chỉ ghi nguồn để diễn giải — không phát sinh fact trong giai đoạn 1):** `succession`, `init`, `end` (để diễn giải F1 theo từng mẫu của bài đo 6.5) và `not_response`, `not_precedence` (để Curator nhận ra mâu thuẫn trực tiếp qua bảng đối nghịch; không phải mẫu miner khám phá).
   - **Tầng 3 (hoãn — trong danh mục Leno 2018 Bảng 1 nhưng ngoài giai đoạn 1):** `responded existence`, `alternate response`, `chain response`, `alternate precedence`, `chain precedence`, `not responded existence`, `not chain response`, `not chain precedence`, các mẫu existence/choice khác, và điều kiện thời gian kiểu MP-Declare (spec dòng 176: "vào danh sách để sau").
   - **Điều kiện dữ liệu (MP-Declare):** chỉ điều kiện trên thuộc tính phân loại (spec dòng 144, 176); dạng điều kiện theo Leno 2018 Bảng 2 (điều kiện kích hoạt + điều kiện tương quan).
3. **Cách đọc:** mọi định nghĩa đọc theo **LTLf (trace hữu hạn)** (Di Ciccio & Montali 2022 §3). Công thức Maggi 2012 (viết bằng LTL) được hiểu với cùng nghĩa trên trace hữu hạn.
4. **Tên canonical:** dùng tên của Leno 2018 Bảng 1. Riêng công thức (a → ¬♦b) gọi là **`not_response`** (khớp code + Leno 2018); tên "not succession" mà Maggi 2012 dùng cho cùng công thức này được ghi là **bí danh không dùng** (xem §5).

## 4. Bảng nguồn của từng mẫu (cổng ra của task 4.1)

Ký hiệu LTL: G = luôn luôn, F (♦) = rồi sẽ có lúc, O = đã có lúc trong quá khứ, X = vị trí kế tiếp, Y = vị trí trước đó, U = cho tới khi, S = kể từ khi. Activation = hoạt động mà sự xuất hiện của nó kích hoạt ràng buộc (theo Bảng 1 của Leno 2018).

### 4.1. Tầng 1 — miner khám phá, eval đo

| Mẫu | Định nghĩa (LTL) | Activation → Target | Nguồn chính (bài báo + chỗ trích) |
|---|---|---|---|
| `response` | G(A → FB) — "A xảy ra thì B sẽ xảy ra sau" | A → B | Leno, Dumas & Maggi 2018, Bảng 1: "response G(A → FB) A". Nguồn phụ: Maggi, Bose & van der Aalst 2012, §2: "the response constraint can be formalized as (a → ♦b)"; Grohs et al. 2023 §4.1: "Response(A,B) (formal as A -$>$ B) means that B must follow whenever A occurs" (dạng đầy đủ trong Bảng 2 của Grohs: "provide laundry service -$>$ F(bill)"). |
| `precedence` | G(B → OA) — "B chỉ xảy ra khi A đã xảy ra trước" | B → A | Leno, Dumas & Maggi 2018, Bảng 1: "precedence G(B → OA) B". Nguồn phụ: Maggi, Bose & van der Aalst 2012, §2: "precedence (formally: (¬b U a) ∨ ¬♦b)" (dạng tương đương, toán tử tương lai — bản trích PDF ghi "(¬b_t a) ∨ (¬b)", trong đó vế thứ hai là trường hợp B không bao giờ xảy ra thì thỏa mãn một cách hiển nhiên); Grohs et al. 2023 §4.1: "Precedence(A, B) (formal as NOT(B) U A) means that activity B should only occur after activity A" (dạng rút gọn khi B có xảy ra). |

### 4.2. Tầng 2 — chỉ ghi nguồn để diễn giải (không phát sinh fact trong giai đoạn 1)

| Mẫu | Định nghĩa (LTL) | Activation | Nguồn chính (bài báo + chỗ trích) |
|---|---|---|---|
| `succession` | Response(A,B) ∧ Precedence(A,B) — hợp của hai mẫu trên | A và B (cả hai — mỗi lần A xuất hiện đòi B sau đó; mỗi lần B xuất hiện đòi A trước đó) | Grohs et al. 2023 §4.1: "Succession(A,B) is the combination of Precedence(A,B) and Response(A,B)". (Leno 2018 Bảng 1 không liệt kê `succession` riêng; Maggi 2012 nhắc tới succession như ràng buộc mạnh hơn response trong §2.2 về vacuity.) |
| `init` | START → A — "mọi case đều bắt đầu bằng A" (mẫu một ngôi: chỉ một hoạt động) | A | Grohs et al. 2023 §4.1: "Init(A) (formal as START -$>$ A) prescribes that all process instances must start with A". Nguồn phụ: Di Ciccio & Montali 2022, Ví dụ 1: "To specify that c is the initial task, we write Init(c)". |
| `end` | END → A — "mọi case đều kết thúc bằng A" (mẫu một ngôi: chỉ một hoạt động) | A | Grohs et al. 2023 §4.1: "End(A) (formal as END -$>$ A) indicates that they must end with A". |
| `not_response` | G(A → ¬FB) — "A xảy ra thì B không xảy ra sau đó" | A → B | Leno, Dumas & Maggi 2018, Bảng 1: "not response G(A → ¬FB) A". Nguồn phụ: Di Ciccio & Montali 2022, Ví dụ 1: "After the admission has been notified, the candidate will not receive a rejection any longer – NotResponse(y, n)". **Bí danh không dùng:** Maggi 2012 gọi cùng công thức này là "not succession" (xem §5). |
| `not_precedence` | G(B → ¬OA) — "B xảy ra mà A chưa từng xảy ra trước đó" | B → A | Leno, Dumas & Maggi 2018, Bảng 1: "not precedence G(B → ¬OA) B". |

### 4.3. Điều kiện dữ liệu (MP-Declare) — dạng điều kiện, không phải mẫu riêng

| Hạng mục | Định nghĩa | Nguồn |
|---|---|---|
| Điều kiện kích hoạt + điều kiện tương quan trên thuộc tính phân loại | Mỗi mẫu quan hệ mang thêm điều kiện kích hoạt ϕa(x) (trên payload của activation) và điều kiện tương quan ϕc(x, y) (liên hệ payload của activation và target); ngữ nghĩa MFOTL trong Bảng 2, ví dụ response: G(∀x.((A ∧ ϕa(x)) → FI (B ∧ ∃y.ϕc(x, y)))) | Leno, Dumas & Maggi 2018, Bảng 2 + §2.3: "we illustrate a multi-perspective version of Declare (MPDeclare) introduced in [5]. This semantics is expressed in Metric First-Order Linear Temporal Logic (MFOTL)". Giai đoạn 1 chỉ dùng điều kiện trên thuộc tính phân loại (spec dòng 144, 176); điều kiện thời gian hoãn (spec dòng 176). |

### 4.4. Tầng 3 — hoãn (trong danh mục, ngoài giai đoạn 1)

Các mẫu sau có nguồn trong cùng Bảng 1 của Leno 2018 (công thức LTL + activation) nhưng **không** thuộc từ vựng giai đoạn 1, nên ADR chỉ ghi tên + nguồn, không định nghĩa chi tiết ở đây: `responded existence` (G(A → (OB ∨ FB))), `alternate response` (G(A → X(¬A U B))), `chain response` (G(A → XB)), `alternate precedence` (G(B → Y(¬B S A))), `chain precedence` (G(B → YA)), `not responded existence` (G(A → ¬(OB ∨ FB))), `not chain response` (G(A → ¬XB)), `not chain precedence` (G(B → ¬YA)). Muốn đưa mẫu nào vào tầng 1/2 thì sửa ADR này trước (ghi rõ lý do + cập nhật miner/eval/Curator tương ứng), không tự thêm vào code.

### 4.5. Chỉ số support / confidence (định nghĩa đi kèm miner)

| Hạng mục | Định nghĩa trong dự án | Nguồn |
|---|---|---|
| `support` | Tỉ lệ case mà luật được kích hoạt và thỏa mãn | Maggi, Bose & van der Aalst 2012 §4: "considering only the ones that are relevant (based on the event log) according to (the combination of) simple metrics, such as Confidence and Support"; định nghĩa chính xác theo docstring `declare/miner.py` ("support: tỉ lệ case tối thiểu mà luật được kích hoạt và thỏa mãn"). |
| `confidence` | Tỉ lệ trong các case đã kích hoạt mà luật thỏa mãn | Cùng nguồn trên; docstring `declare/miner.py` ("confidence: tỉ lệ tối thiểu trong các case đã kích hoạt mà luật thỏa mãn"). |
| Lọc trước `support × confidence` | Hoạt động xuất hiện ở ít hơn `support × confidence` phần case bị bỏ trước, vì không thể thuộc luật nào qua được cả hai ngưỡng | Spec dòng 148; docstring `declare/miner.py` chứng minh ngưỡng lọc là an toàn ("support × confidence <= support"). |

---

## 5. Mâu thuẫn / khoảng trống đã phát hiện (không giấu)

| # | Vấn đề | Mức | Cách giải quyết trong ADR này |
|---|---|---|---|
| 1 | **Curator cho `succession` đi qua nhưng eval từ chối nó.** `learning/curator.py` không kiểm từ vựng: insight mẫu `succession` → delta `ADD` với khóa `succession(A, B)` (test `test_template_khong_co_doi_nghich_thi_bo_qua_bang_doi_nghich` khẳng định điều đó). Nếu fact đó được duyệt và ghi, `eval/metrics.py` sẽ báo `ValueError` ("mẫu Declare không hỗ trợ") khi đo (test `test_mau_khong_ho_tro_thi_bao_loi` khẳng định điều đó). | Trung bình (tiềm ẩn — chưa kích hoạt được trong giai đoạn 1 vì chưa có nguồn insight nào sinh ra `succession`: miner chỉ sinh response/precedence; Reflector 6.2 chưa làm) | ADR xếp `succession` vào **tầng 2 (không phát sinh fact)** và ghi rõ: JSON schema của Reflector (6.2) chỉ cho các mẫu tầng 1 (spec dòng 176: "JSON schema của Reflector chỉ cho các mẫu trong từ vựng" — ở đây "từ vựng" được hiểu là tầng 1). Nếu sau này muốn Reflector sinh `succession`/`init`/`end` thì phải thêm hỗ trợ vào eval (và miner nếu cần) trước, rồi mới sửa ADR nâng tầng. |
| 2 | **Tên "not succession" gây nhầm.** Maggi 2012 gọi công thức (a → ¬♦b) là "not succession" (Bảng ở §2 + §5: discovery tìm "precedence, response and not succession"), trong khi Leno 2018 Bảng 1 và code gọi cùng công thức đó là "not response". "Not succession" theo nghĩa đen phải là phủ định của succession (¬Response ∨ ¬Precedence), không phải (a → ¬♦b). | Thấp (đã ghi rõ) | ADR chọn tên canonical là **`not_response`** (khớp Leno 2018 + code + pm4py) và ghi "not succession" là bí danh **không dùng**. Không thêm mẫu `not_succession` vào code. |
| 3 | **Spec/plan không nêu tên `succession`/`init`/`end`/`not_response`/`not_precedence`.** Spec chỉ nêu tên Response và Precedence (dòng 144); plan con 4 cũng chỉ nêu hai mẫu đó. Nhưng bộ đo 6.5 dùng 5 mẫu và Curator dùng 2 mẫu phủ định. | Thấp (ADR này lấp) | ADR ghi nguồn cho cả 7 mẫu (§4.1–4.2). Không cần sửa spec/plan cho việc này (ADR là nơi ghi nguồn theo đúng yêu cầu của spec dòng 225); nếu Thuận muốn spec nêu đủ 7 tên thì đó là một sửa spec riêng, cần duyệt riêng. |
| 4 | **Plan 4.1 nói "trong bài báo" (số ít) nhưng từ vựng cần nhiều bài.** Một bài duy nhất không đủ: Leno 2018 có đủ 12 mẫu quan hệ nhưng không có succession/init/end; Grohs 2023 có 5 mẫu nhưng không phải nguồn gốc; Di Ciccio & Montali 2022 có đủ nhưng Bảng 1 của chương khó trích chính xác từng dòng (một phần là hình). | Thấp (đã ghi rõ cách hiểu) | ADR hiểu "bài báo" ở đây là **bài báo chính cho từng mẫu** (§4 ghi rõ bài + bảng/mục cho từng mẫu), với Leno 2018 Bảng 1 là nguồn chính cho mọi mẫu quan hệ. Nếu Thuận muốn chỉ một bài duy nhất thì phải chấp nhận mất succession/init/end (phương án B, §2.1) — ADR không khuyến nghị. |
| 5 | **Bảng đối nghịch của Curator đang chờ ADR này.** `learning/curator.py` ghi "Mở rộng bảng khi ADR 4.1 chốt từ vựng đầy đủ". | Thấp (ADR này trả lời) | Với từ vựng hai tầng, bảng đối nghịch **giữ nguyên** (response ↔ not_response, precedence ↔ not_precedence) — không mở rộng trong giai đoạn 1, vì tầng 2 không phát sinh fact. Nếu sau này nâng `succession` lên tầng 1 thì bảng cần thêm cặp succession ↔ not_succession — nhưng "not_succession" chưa có định nghĩa thống nhất (xem #2), nên việc nâng tầng này phải giải quyết tên gọi trước. |

---

## 6. Vì sao (chọn phương án A ở cả ba điểm quyết định)

- **Nguồn chính là Leno 2018 Bảng 1** vì đó là bảng duy nhất (trong các nguồn đã mở thật) có đủ ba thứ cùng một chỗ cho mỗi mẫu quan hệ: công thức LTL, cột activation, và (ở Bảng 2) dạng điều kiện dữ liệu MP-Declare. Maggi 2012 là bài spec đã trích cho Response/Precedence nhưng không có bảng đầy đủ; Di Ciccio & Montali 2022 đầy đủ nhất về lý thuyết nhưng Bảng 1 của chương khó trích chính xác từng dòng. Dùng Leno 2018 làm nguồn chính, hai bài kia làm nguồn phụ, là cách duy nhất đạt C1 cho mọi mẫu mà không phải tự suy ra định nghĩa.
- **Từ vựng hai tầng** vì đó là cách duy nhất vừa đạt cổng ra 4.1 (ghi nguồn cho mọi mẫu dự án chạm tới) vừa không mâu thuẫn code đã merge và không vượt phạm vi plan con 4. Tầng 1 = đúng những gì miner/eval/pm4py đã làm; tầng 2 = những gì bài đo 6.5 và Curator đã chạm tới nhưng chưa phát sinh fact. Phương án B (một tầng phẳng) đòi sửa miner + eval — đó là việc của plan, không phải của ADR. Phương án C (chỉ 2 mẫu) thì ADR không ghi nguồn cho succession/init/end/not_response/not_precedence — cổng ra 4.1 không đạt.
- **Đọc theo LTLf** vì log là trace hữu hạn và miner kiểm trên trace hữu hạn; Di Ciccio & Montali 2022 §3 nói rõ đây là cách đọc đúng của Declare. Đọc theo LTL vô hạn (Maggi 2012) sẽ cho phép b xảy ra "ở đâu đó trong tương lai vô hạn", không khớp miner.

## 7. Hệ quả

- **Được:** khẳng định "viết từ định nghĩa hình thức trong bài báo" (spec dòng 225) trở thành kiểm được — mỗi mẫu có đúng một nguồn (bài + bảng/mục + trích dẫn) trong §4. Bảng đối nghịch của Curator có căn cứ để **giữ nguyên** (không mở rộng). JSON schema của Reflector (6.2) có căn cứ để **chỉ cho tầng 1** (response, precedence). Bài đo 6.5 có căn cứ để diễn giải F1 của cả 5 mẫu (định nghĩa ở §4.2).
- **Mất:** không có gì mất — ADR không sửa code, không đổi hành vi. Miner/eval/Curator/pm4py giữ nguyên.
- **Khó đổi về sau:** thấp — thêm mẫu vào tầng 1/2 chỉ là sửa ADR này + cập nhật miner/eval/Curator tương ứng (có test bắt). Đổi nguồn chính (ví dụ sang Di Ciccio & Montali 2022) chỉ là sửa §4, không ràng buộc code.
- **Hệ quả lên plan:** không đổi task nào. Task 4.1 chuyển trạng thái "chưa làm" → "xong" khi tệp này được duyệt + đưa vào repo (cổng ra của task là tệp tồn tại ở `docs/decisions/`). Không thêm task mới; việc "thêm test khẳng định từ vựng khớp ADR" (xem "Cách kiểm bằng máy") là một task mới nếu Thuận muốn — ADR này không tự thêm.

## 8. Bằng chứng

| # | Khẳng định | Mức | Chi tiết |
|---|---|---|---|
| 1 | Maggi, Bose & van der Aalst 2012: response = (a → ♦b); precedence = (¬b U a) ∨ (¬b); responded existence = (♦a → ♦b); not succession = (a → ¬(♦b)) | **Đã kiểm nguồn** (7/11/2026) | Mở thật https://www.vdaalst.com/publications/p669.pdf (bản PDF, 776 dòng trích): §2 "the response constraint can be formalized as (a → ♦b)"; "precedence (formally: (¬b_t a) ∨ (¬b))"; bảng ở §2: "response (a → ♦b) If a occurs then b follows … precedence (¬b t a) ∨ (¬b) If b occurs then a precedes … not succession (a → ¬(♦b)) If a occurs then b does not follow"; §5: discovery tìm "precedence, response and not succession". Nơi xuất bản đã kiểm qua TU/e Research Portal: CAiSE 2012, LNCS 7328, tr. 270–285, DOI 10.1007/978-3-642-31095-9_18. |
| 2 | Leno, Dumas & Maggi 2018, Bảng 1: 12 mẫu quan hệ kèm công thức LTL + cột activation (response G(A → FB); precedence G(B → OA); not response G(A → ¬FB); not precedence G(B → ¬OA); …) | **Đã kiểm nguồn** (7/11/2026) | Mở thật https://kodu.ut.ee/~dumas/pubs/bpm2018datarules.pdf (BPM 2018): "Table 1: Semantics for Declare templates" — "responded existence G(A → (OB ∨ FB)) A; response G(A → FB) A; alternate response G(A → X(¬AUB)) A; chain response G(A → XB) A; precedence G(B → OA) B; alternate precedence G(B → Y(¬BSA)) B; chain precedence G(B → YA) B; not responded existence G(A → ¬(OB ∨ FB)) A; not response G(A → ¬FB) A; not precedence G(B → ¬OA) B; not chain response G(A → ¬XB) A; not chain precedence G(B → ¬YA) B". |
| 3 | Leno, Dumas & Maggi 2018, Bảng 2: ngữ nghĩa MP-Declare (MFOTL) với điều kiện kích hoạt ϕa và điều kiện tương quan ϕc cho cùng 12 mẫu | **Đã kiểm nguồn** (7/11/2026) | Cùng tệp trên: "Table 2: Semantics for Multi-Perspective Declare constraints" + §2.3: "we illustrate a multi-perspective version of Declare (MPDeclare) introduced in [5]. This semantics is expressed in Metric First-Order Linear Temporal Logic (MFOTL)". |
| 4 | Di Ciccio & Montali 2022: Declare dùng LTLf (trace hữu hạn); Bảng 1 là bộ mẫu lõi; Init(c) = c là task đầu tiên; NotResponse(y, n) là mẫu quan hệ phủ định | **Đã kiểm nguồn** (7/11/2026) | Mở thật https://link.springer.com/chapter/10.1007/978-3-031-08848-3_4 (Process Mining Handbook, LNBIP 448, tr. 108–152, open access): §3 "Focusing on finite traces reflects the intuition that every process instance is expected to complete in a finite number of steps"; §2 "Table 1 shows a set of Declare constraints we use throughout this chapter"; Ví dụ 1: "To specify that c is the initial task, we write Init(c)"; "After the admission has been notified, the candidate will not receive a rejection any longer – NotResponse(y, n)". |
| 5 | Grohs et al. 2023 §4.1: 5 mẫu — Precedence(A,B) = NOT(B) U A; Response(A,B) = A → F(B); Succession = hợp của Precedence + Response; Init(A) = START → A; End(A) = END → A | **Đã kiểm nguồn** (7/11/2026) | Mở thật https://arxiv.org/html/2307.09923v1: "It uses the common declarative modeling language Declare, which is based on constraint templates grounded in Linear Temporal Logic (LTL) [4]. By applying rule-based NLP techniques to sentences, the approach in [19] generates declarative constraints for five LTL templates: precedence, response, succession, initialization (init), and end. Precedence(A, B) (formal as NOT(B) U A) means that activity B should only occur after activity A. Response(A,B) (formal as A -$>$ B) means that B must follow whenever A occurs. Succession(A,B) is the combination of Precedence(A,B) and Response(A,B). Init(A) (formal as START -$>$ A) prescribes that all process instances must start with A and End(A) (formal as END -$>$ A) indicates that they must end with A." |
| 6 | Miner chỉ khám phá response + precedence; eval chỉ đo response + precedence (mẫu khác → ValueError); đối chiếu pm4py chỉ cho phép {"response", "precedence"} | **Đã chạy thử** (7/11/2026) | Đọc code trên nhánh `feat/integration` (eb9e2ba): `declare/miner.py` (Rule + `discover()` chỉ response/precedence); `declare/index.py` (`response_holds`, `precedence_holds`); `eval/metrics.py` dòng 88–93 (chỉ hai nhánh `if template == "response"` / `"precedence"`, còn lại `raise ValueError`); `tools/cross_check_pm4py.py` dòng 86 (`allowed_templates={"response", "precedence"}`); `tests/test_metrics.py` (`test_mau_khong_ho_tro_thi_bao_loi`: fact mẫu `succession` → `ValueError`). |
| 7 | Bảng đối nghịch của Curator chỉ có 2 cặp (response ↔ not_response, precedence ↔ not_precedence); `succession` không có đối nghịch; insight `succession` vẫn thành delta ADD | **Đã chạy thử** (7/11/2026) | Đọc code trên `feat/integration`: `learning/curator.py` dòng 52–58 (`OPPOSITE_TEMPLATES` 4 mục) + docstring dòng 19–21 ("Mở rộng bảng khi ADR 4.1 chốt từ vựng đầy đủ"); `tests/test_curator.py` (`test_bang_doi_nghich_chi_co_response_va_precedence`: `opposite_template("succession") is None`; `test_template_khong_co_doi_nghich_thi_bo_qua_bang_doi_nghich`: insight `succession` → `ADD`, khóa `succession(A, B)`). |
| 8 | Spec chỉ nêu tên Response và Precedence (dòng 144); plan con 4 cũng chỉ nêu hai mẫu đó; spec dòng 225 đòi ADR ghi nguồn từng mẫu; spec dòng 176 giới hạn JSON schema của Reflector theo từ vựng và hoãn điều kiện thời gian | **Đã kiểm nguồn** (7/11/2026) | Đọc nguyên văn: spec `docs/specs/phase-1-core/Spec kỹ thuật — gói core.md` dòng 144, 146, 176, 225; plan `docs/plans/phase-1-core/Plan giai đoạn 1 — lõi học.md` dòng 120–135 (plan con 4, task 4.1 dòng 129). Lệnh `grep -i "succession\|not_response\|not_precedence"` trên cả hai tệp trả 0 kết quả — khẳng định spec/plan chưa từng nêu tên các mẫu này. |
| 9 | Repo đã có 3 ADR (0001, 0002, 0003) ở `docs/decisions/` với định dạng: tiêu đề + ngày/trạng thái + Bối cảnh + Tiêu chí + Các phương án + Quyết định + Hệ quả + Bằng chứng + Cách kiểm bằng máy | **Đã kiểm nguồn** (7/11/2026) | Đọc cả 3 tệp trong `docs/decisions/` (0001-cach-chia-plan-giai-doan-1.md, 0002-pham-vi-test-am-cho-cong-may.md, 0003-cach-dat-hai-goi-core-va-platform.md). ADR này theo đúng định dạng đó. |
| 10 | Từ vựng canonical là Declare; khóa canonical dạng `mẫu(hoạt động, hoạt động)`; từ vựng hiện chỉ có điều kiện trên thuộc tính phân loại | **Đã kiểm nguồn** (7/11/2026) | Spec dòng 54 (`canonical_key` ví dụ `precedence(Record Goods Receipt, Record Invoice Receipt)`), dòng 144 ("Từ vựng canonical là Declare"), dòng 176 ("Từ vựng hiện chỉ có điều kiện trên thuộc tính phân loại"). |
| 11 | Công thức precedence dạng (¬b U a) ∨ ¬♦b tương đương G(B → OA) trên trace hữu hạn | **Giả thuyết** | Hai dạng đều xuất hiện trong nguồn đã mở (Maggi 2012 dạng tương lai; Leno 2018 dạng quá khứ), nhưng bản thân tương đương này không được trích nguyên văn từ bài báo nào trong lần soát này. Cách kiểm: chứng minh bằng bảng chân lý trên trace hữu hạn (mọi trace hữu hạn thỏa dạng này thì thỏa dạng kia) — một kiểm tra tay, ghi lại khi làm. Không dùng khẳng định này để quyết (chỉ ghi chú tương đương để tiện tra cứu). |

## 9. Rủi ro mới sinh ra

| # | Rủi ro | Mức | Đã loop giảm thế nào | Dấu hiệu theo dõi | Hạn kiểm |
|---|---|---|---|---|---|
| 1 | Công thức LTL trong §4 bị chép sai (sai một ký tự là sai ngữ nghĩa) | **Thấp** | Mọi công thức đều trích nguyên văn từ nguồn đã mở thật (§8 #1–5, ghi rõ bảng/mục + trích đúng chỗ); mỗi hàng ghi rõ nguồn chính + nguồn phụ để đối chiếu chéo. | Người review đối chiếu một hàng với bài báo và thấy khác. | Lúc duyệt nội dung (trước khi đưa vào repo) — Thuận hoặc người review kiểm ngẫu nhiên 2–3 hàng với bài gốc. |
| 2 | Từ vựng tầng 1 (chỉ response/precedence) làm Reflector (6.2) không sinh được succession/init/end, hạn chế những gì LLM trích được từ tài liệu | **Thấp** | ADR ghi nguồn cho cả 5 mẫu (§4.2) nên việc nâng tầng sau này chỉ là sửa ADR + thêm hỗ trợ eval/miner — không phải tìm lại nguồn. Bài đo 6.5 vẫn đo đủ 5 mẫu để biết mô hình kém GPT-4 bao xa. | Task 6.2 cần một mẫu ngoài tầng 1. | Lúc thiết kế 6.2 (JSON schema của Reflector). |
| 3 | Tên "not succession" gây nhầm (Maggi 2012) — ai đó thêm mẫu `not_succession` vào code | **Thấp** | ADR ghi rõ "not succession" là bí danh **không dùng** (§3.4, §5 #2) và chỉ dùng `not_response`. | `grep -rn "not_succession"` trong repo trả kết quả khác 0. | Mỗi lần review plan con (cấp 2) + khi có task chạm Curator/miner. |
| 4 | Code trôi khỏi ADR (thêm mẫu mới vào miner/eval/Curator mà không cập nhật ADR) | **Thấp** | "Cách kiểm bằng máy" dưới đây đề xuất test khẳng định tập mẫu của miner/eval/bảng đối nghịch khớp đúng tầng trong ADR; cho tới khi test đó có, rủi ro còn lại là trôi không ai phát hiện — giảm bằng cách ghi rõ trong ADR này rằng thêm mẫu = sửa ADR trước. | Một mẫu mới xuất hiện trong code mà §4 không có hàng tương ứng. | Mỗi lần review cấp 2 của plan con 4/7/8; khi test khẳng định từ vựng được thêm thì cổng máy bắt luôn. |
| 5 | Cách đọc LTLf vs LTL gây khác biệt ở mẫu mới (ví dụ mẫu dùng "luôn luôn" ở cuối trace) | **Thấp** | ADR chốt cách đọc LTLf (§3.3) và ghi rõ công thức Maggi 2012 được hiểu theo nghĩa đó; với 2 mẫu tầng 1, hai cách đọc cho cùng kết quả trên trace hữu hạn (miner đã kiểm bằng test + đối chiếu pm4py). | Thêm mẫu mới mà LTL và LTLf cho kết quả khác nhau trên trace hữu hạn. | Khi thêm mẫu mới vào tầng 1/2 — kiểm định nghĩa LTLf của mẫu đó trước khi thêm. |

**Kết luận rủi ro:** không còn rủi ro trung bình/nặng. Mọi rủi ro còn lại đều thấp và có cách giảm cụ thể như bảng trên.

## 10. Chạm vào đâu và rút lui thế nào

**Khi Thuận duyệt nội dung, bước đưa vào repo sẽ chạm:**

| File | Thay đổi | Vì sao chọn vị trí này |
|---|---|---|
| MỚI `docs/decisions/0004-nguon-cua-tung-mau-declare.md` | Toàn bộ nội dung đã duyệt (trạng thái **đã chốt**, duyệt 7/11/2026). | Plan task 4.1 (dòng 129) đòi tệp ở `docs/decisions/`; 3 ADR trước (0001–0003) đều ở đó, cùng định dạng; số 0004 là số tiếp theo trong thư mục này. |
| SỬA `docs/plans/phase-1-core/Plan giai đoạn 1 — lõi học.md` (chỉ ô trạng thái của task 4.1) | Dòng 129: trạng thái "chưa làm" → "xong" (cột Review giữ "chưa review" cho tới khi Thuận review cấp 3). | Cổng ra của task 4.1 là tệp tồn tại ở `docs/decisions/`; khi tệp đã có thì trạng thái task đổi theo. (Việc cập nhật cột trạng thái của plan file đang có một đề xuất riêng chờ duyệt — nếu đề xuất đó được duyệt trước thì dòng 129 đổi cùng đợt đó; không sửa hai lần.) |
| KHÔNG SỬA code | Miner/index/eval/Curator/pm4py giữ nguyên (ADR này khớp với code đã merge, không đòi sửa code). | ADR chỉ ghi nguồn + chốt từ vựng; mọi thay đổi code (nếu có) là task riêng, duyệt riêng. |

**Lưu ý về số 0004:** trong `~/workspace/your_files/praxon-r18/` có một tệp khác cũng mang số 0004 (`0004-nguon-tai-log-bpic-2015.md`, về nguồn tải log BPIC 2015, R18). Tệp đó nằm **ngoài repo** (thư mục tệp của Thuận, không phải `docs/decisions/`), nên không xung đột số trong repo. Nếu Thuận muốn tránh nhầm lẫn thì có thể đổi tên tệp R18 đó sau — không phải việc của ADR này.

**Rút lui:** ADR là tài liệu mới, không sửa hành vi hiện có. Rút lui = xóa tệp `docs/decisions/0004-*.md` + trả ô trạng thái task 4.1 về "chưa làm" (revert commit đưa ADR vào repo). Repo trở về trạng thái trước 4.1 (không có bản ghi nguồn), không mất test/cổng/bất biến nào. Không cần backup riêng vì đây là nhánh mới + commit riêng (theo quy trình).

**Cách kiểm bằng máy.** (a) Cổng ra của task 4.1: tệp tồn tại ở `docs/decisions/` (kiểm bằng `ls docs/decisions/0004-*.md`). (b) Mỗi mẫu trong từ vựng (§4.1–4.2) có một hàng nguồn trong tệp — kiểm bằng cách đọc §4 (7 mẫu + dạng điều kiện MP-Declare). (c) Đề xuất thêm (không bắt buộc cho task 4.1, là task mới nếu Thuận muốn): một test khẳng định tập mẫu của miner (`discover` chỉ sinh `response`/`precedence`), tập mẫu eval chấp nhận (chỉ 2 mẫu, còn lại `ValueError`), và bảng đối nghịch của Curator (chỉ 2 cặp) khớp đúng tầng trong ADR — test đỏ nếu code thêm mẫu mà ADR chưa cập nhật.

---

## Nguồn (đầy đủ, để tra cứu)

- Maggi, F. M., Bose, R. P. J. C., & van der Aalst, W. M. P. (2012). Efficient Discovery of Understandable Declarative Process Models from Event Logs. CAiSE 2012, LNCS 7328, tr. 270–285. DOI: 10.1007/978-3-642-31095-9_18. URL (link spec đã dùng): https://www.vdaalst.com/publications/p669.pdf — đã mở thật 7/11/2026.
- Leno, V., Dumas, M., & Maggi, F. M. (2018). Correlating Activation and Target Conditions in Data-Aware Declarative Process Discovery. BPM 2018. URL: https://kodu.ut.ee/~dumas/pubs/bpm2018datarules.pdf — đã mở thật 7/11/2026.
- Di Ciccio, C., & Montali, M. (2022). Declarative Process Specifications: Reasoning, Discovery, Monitoring. Trong W. M. P. van der Aalst & J. Carmona (chủ biên), Process Mining Handbook, LNBIP 448, tr. 108–152. Springer (open access). URL: https://link.springer.com/chapter/10.1007/978-3-031-08848-3_4 — đã mở thật 7/11/2026.
- Grohs, M., Abb, L., Elsayed, N., & Rehse, J.-R. (2023). Large Language Models can accomplish Business Process Management Tasks. arXiv:2307.09923. URL: https://arxiv.org/html/2307.09923v1 — đã mở thật 7/11/2026 (§4.1–4.2).

---

## Điểm đã quyết kèm ADR (đã chốt 7/11/2026 — tất cả chọn phương án (a))

| # | Điểm cần quyết | Các lựa chọn | Khuyến nghị (đã duyệt) |
|---|---|---|---|
| Q1 | JSON schema của Reflector (6.2) có được sinh mẫu tầng 2 (`succession`/`init`/`end`) không? | (a) Chỉ tầng 1 (response, precedence) — ADR hiện tại viết theo hướng này; (b) Cả 5 mẫu — thì phải thêm hỗ trợ eval (và miner nếu cần) trước, rồi sửa ADR nâng tầng. | (a) — vì eval hiện từ chối `succession` bằng ValueError; chọn (b) là mở rộng plan, cần task mới. |
| Q2 | Chốt từ vựng hai tầng (§3.2) hay chỉ một tầng phẳng? | (a) Hai tầng (đề xuất); (b) Một tầng phẳng 7 mẫu — đòi sửa miner + eval (mở rộng plan con 4); (c) Tối thiểu 2 mẫu — thì ADR không ghi nguồn cho succession/init/end/not_response/not_precedence, cổng ra 4.1 không đạt. | (a). |
| Q3 | Chấp nhận cách hiểu "bài báo" = bài báo chính cho từng mẫu (Leno 2018 Bảng 1 làm nguồn chính) hay bắt buộc một bài duy nhất? | (a) Nhiều bài, mỗi mẫu một nguồn chính (đề xuất); (b) Một bài duy nhất — thì mất succession/init/end (phương án B, §2.1). | (a). |
| Q4 | Tên canonical cho công thức (a → ¬♦b): `not_response` hay `not_succession`? | (a) `not_response` (đề xuất — khớp Leno 2018 + code + pm4py); (b) `not_succession` (theo Maggi 2012 — thì phải đổi tên trong code Curator + test, và tên này dễ nhầm với phủ định của succession). | (a). |
| Q5 | Số hiệu + tên tệp ADR trong repo: `docs/decisions/0004-nguon-cua-tung-mau-declare.md` có được không? | (a) Giữ 0004 (đề xuất — số tiếp theo trong `docs/decisions/`); (b) Đổi số/tên khác (ghi rõ số muốn dùng). Lưu ý: tệp R18 ngoài repo cũng mang số 0004 nhưng không xung đột (xem §10). | (a). |
| Q6 | Có thêm test khẳng định từ vựng khớp ADR ("Cách kiểm bằng máy" (c)) không? | (a) Thêm (đề xuất — một task mới, nhỏ, bắt trôi từ vựng); (b) Không thêm — thì rủi ro #4 chỉ giảm bằng review tay. | (a) — nhưng là task mới, duyệt riêng, không gộp vào việc đưa ADR này vào repo. |
