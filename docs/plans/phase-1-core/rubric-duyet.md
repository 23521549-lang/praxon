# Rubric duyệt cho quyết định thủ công (task 9.4)

> **Trạng thái: ĐÃ DUYỆT, ĐÃ KHÓA BẰNG COMMIT.**
> Task 9.4, plan con 9 (Đường vào tài liệu, rubric, hiệu chỉnh).
> Ngày duyệt nội dung: 7/11/2026.
> **Mã commit khóa rubric này là commit đầu tiên đưa file này vào repo** (nhánh
> `feat/plan9-rubric`); tra cứu bằng `git log -- docs/plans/phase-1-core/rubric-duyet.md`.
> Quyết định thủ công đầu tiên phải ghi rõ nó dùng rubric ở mã commit nào.
> Mỗi lần sửa rubric cũng commit riêng, và các quyết định sau đó dùng rubric ở mã
> commit mới. Không sửa rubric mà không commit.

## 0. Nguồn

| # | Nguồn | Nội dung dùng |
|---|---|---|
| 1 | Plan, task 9.4 (dòng 233) | "Rubric duyệt viết trước, khóa bằng commit; duyệt chéo mù một phần năm quyết định thủ công \| Rubric có mã commit trước quyết định thủ công đầu tiên; lệnh tính kappa, ngưỡng ≥ 0,61" |
| 2 | Plan, plan con 9 (dòng 219–222) | Cổng ra: "rubric khóa bằng commit trước lần duyệt đầu tiên; kappa duyệt chéo ≥ 0,61." Bất biến: "quyết định của người dùng chỉ vào hệ qua `Candidate`; … rubric viết trước." |
| 3 | Spec, dòng 49 | Bảng `candidate` có các cột `decided_by`, `rubric_clause` (người duyệt ghi). |
| 4 | Spec, dòng 99 | "Quyết định của người dùng thành Candidate. Mỗi lần duyệt, chặn hay bật sớm là một Candidate đi qua Governor với `decided_by` và `rubric_clause`, không có đường ghi tắt." |
| 5 | Spec, dòng 118 (luật 8) | "Fact đang trial \| Người duyệt chọn bật sớm, ghi điều khoản rubric \| Lên active, ghi decided_by; luật 4 vẫn gỡ nếu dữ liệu sau đó bác bỏ" |
| 6 | Spec, dòng 138 | "**Rubric viết trước, không viết sau.** Mỗi quyết định thủ công ghi điều khoản rubric vào `rubric_clause`. Không có điều khoản nào khớp nghĩa là rubric thiếu, phải sửa rubric trước khi duyệt tiếp. Một phần năm số quyết định thủ công được người thứ hai duyệt chéo." |
| 7 | Spec, dòng 241 (R9) | Rủi ro "Tự duyệt": giải pháp "Duyệt chéo mù, kappa ≥ 0,61, rubric khóa trước". Mức còn lại: Nhẹ. Dấu hiệu theo dõi: "Kappa dưới 0,61". Khi nào kiểm: Tuần 4. |
| 8 | Spec, dòng 110–125 (bảng luật Governor, luật 1–9) | Luật 1 (mâu thuẫn trực tiếp fact active → người duyệt); luật 2 (đúng lược đồ Declare; Wilson ≥ 0,7 nếu từ trace); luật 7 (điều kiện thuộc tính cần ≥ 30 case); luật 8 (bật sớm, ghi điều khoản rubric). |
| 9 | Lệnh kappa: `packages/core/src/praxon_core/eval/kappa.py` | `cohen_kappa(rater_a, rater_b)` = (Po − Pe)/(1 − Pe); `KAPPA_THRESHOLD = 0.61`; `kappa_meets_threshold(kappa)` = kappa ≥ 0,61. Nếu Pe = 1 (cả hai luôn chấm cùng một nhãn) thì kappa quy ước là 1,0. |
| 10 | Test kappa: `tests/test_kappa.py` | Nhãn dùng trong test: "approve"/"reject" và "yes"/"no". Ví dụ: đồng ý 18/20, Pe = 0,52 → kappa = 19/24 ≈ 0,79, đạt ngưỡng. Ngưỡng đúng 0,61 thì đạt, 0,60 thì không. |

## 1. Các điều khoản

> Spec và plan không liệt kê sẵn các tiêu chí rubric (không nêu số tiêu chí, tên,
> hay cách chấm). Các điều khoản C1–C5 dưới đây suy ra từ bảng luật Governor
> (spec dòng 110–125) và các bất biến, và đã được duyệt.

Mỗi quyết định thủ công (duyệt / chặn / bật sớm) được chấm theo các điều khoản sau.
Mỗi điều khoản chấm một trong ba mức: **Đạt** / **Không đạt** / **Không áp dụng**.

| Mã | Điều khoản | Mô tả (người duyệt kiểm gì) | Nguồn |
|---|---|---|---|
| C1 | Đúng lược đồ Declare | Ràng buộc theo đúng mẫu Declare (template hợp lệ; hai hoạt động có trong log; điều kiện — nếu có — đúng kiểu MP-Declare). Lược đồ sai thì không duyệt. | Spec luật 2 (dòng 112): "Đúng lược đồ Declare" |
| C2 | Không mâu thuẫn trực tiếp với fact `active` cùng tenant | Ràng buộc không mâu thuẫn trực tiếp với một fact đang `active` của cùng tenant. Nếu mâu thuẫn trực tiếp thì đây chính là trường hợp luật 1 đưa cho người duyệt — người duyệt phải quyết rõ (chặn ràng buộc mới, hoặc ghi rõ lý do nếu vẫn duyệt). | Spec luật 1 (dòng 111): "Mâu thuẫn trực tiếp một fact `active` cùng tenant → Người duyệt" |
| C3 | Bằng chứng đủ mạnh | Bằng chứng ủng hộ ràng buộc: nếu ràng buộc từ trace thì cận dưới Wilson của độ tin ≥ 0,7 trên trace của chính tenant; nếu từ tài liệu (Wabo) thì nguồn tài liệu rõ ràng và đúng thời kỳ log. Bằng chứng yếu thì chưa duyệt (chờ thêm dữ liệu). | Spec luật 2 (dòng 112): "nếu từ trace thì cận dưới Wilson của độ tin ≥ 0,7 trên trace của chính tenant" |
| C4 | Đủ case cho điều kiện thuộc tính | Chỉ áp dụng khi ràng buộc có điều kiện thuộc tính (ví dụ loại matching). Phần dữ liệu thỏa điều kiện phải có ít nhất 30 case. Dưới 30 case thì loại (không duyệt). Không có điều kiện thuộc tính thì ghi "Không áp dụng". | Spec luật 7 (dòng 117): "Phần dữ liệu thỏa điều kiện có ít nhất 30 case … dưới 30 case thì loại" |
| C5 | Phản ánh quy trình thật, không phải nhiễu | Ràng buộc phản ánh một quy tắc nghiệp vụ/quy trình thật (có ý nghĩa trong bối cảnh đô thị), không phải artefact của dữ liệu hay nhiễu. Đây là phần phán đoán của người duyệt — lý do cần duyệt thủ công thay vì chỉ dựa vào cổng thống kê. **Điều khoản phán đoán, không có ngưỡng số.** | Suy từ vai trò duyệt thủ công (spec dòng 99, 138). |

### Cách ghi `rubric_clause`

- Mỗi quyết định thủ công ghi **mã điều khoản chính** (ví dụ `C3`) vào trường
  `rubric_clause` của Candidate, kèm ghi chú ngắn nếu cần (ví dụ
  `C3: Wilson 0,82 trên 214 trace`). Nếu nhiều điều khoản cùng quyết định, ghi
  điều khoản chính và nhắc các điều khoản còn lại trong ghi chú. (Lý do:
  `rubric_clause` là một chuỗi duy nhất trong bảng `candidate` — spec dòng 49;
  code 9.3 chỉ yêu cầu nó không rỗng.)
- **Quy tắc rubric thiếu (spec dòng 138):** nếu không có điều khoản nào khớp với
  quyết định (tức rubric không bao quát trường hợp này) thì **rubric thiếu — phải
  sửa rubric trước khi duyệt tiếp**. Không được duyệt mà không ghi được điều
  khoản. Sửa rubric xong phải commit lại (xem §3) rồi mới duyệt tiếp.

### Quy tắc ra quyết định

| Quyết định | Điều kiện |
|---|---|
| **Duyệt** (approve) | Mọi điều khoản áp dụng đều **Đạt**. |
| **Chặn** (reject) | Có ít nhất một điều khoản **Không đạt**. Ghi mã điều khoản không đạt vào `rubric_clause`. |
| **Bật sớm** (early activate, luật 8) | Fact đang `trial`, mọi điều khoản áp dụng đều **Đạt**, và người duyệt phán đoán nên bật sớm (không chờ cổng Beta). Ghi điều khoản rubric vào `rubric_clause` và ghi `decided_by`. Lưu ý: luật 4 vẫn gỡ nếu dữ liệu sau đó bác bỏ (spec dòng 118). |

## 2. Duyệt chéo mù một phần năm quyết định thủ công

### 2.1. Lấy mẫu

- **Tỉ lệ:** một phần năm (1/5) số quyết định thủ công được duyệt chéo (spec dòng
  138; plan 9.4 dòng 233).
- **Cách lấy mẫu:** lấy ngẫu nhiên 1/5 trong số các quyết định thủ công đã làm,
  không chọn theo cảm tính. Ghi rõ danh sách các quyết định được chọn (mã
  candidate) để đối chiếu.
- **Cỡ mẫu tối thiểu:** chỉ tính kappa khi mẫu duyệt chéo đạt ít nhất
  **20 quyết định** (tức khoảng 100 quyết định thủ công). Dưới 20 thì kappa chưa
  đủ tin — ghi rõ là "chưa đủ mẫu" và tiếp tục lấy mẫu. (Lý do: test kappa dùng
  ví dụ 20 quyết định; kappa trên mẫu quá nhỏ không ổn định. Spec không nêu cỡ
  mẫu tối thiểu — đây là quyết định đã duyệt.)

### 2.2. Chấm mù (blind)

- **Người chấm chéo:** một người thứ hai, khác người đã ra quyết định gốc (spec
  dòng 138: "người thứ hai duyệt chéo"). Người cụ thể được quyết khi làm duyệt
  chéo.
- **Mù nghĩa là:** người chấm chéo **không được thấy** quyết định gốc (duyệt/chặn/
  bật sớm) và không được thấy `rubric_clause` của người thứ nhất. Người chấm chéo
  chỉ nhận: candidate (payload, rationale, evidence_episode_ids) + rubric này, rồi
  tự ra quyết định theo rubric.
- **Nhãn chấm:** mỗi quyết định chéo ghi một nhãn trong hai nhãn: `duyệt` hoặc
  `chặn`. (Bật sớm được gộp vào `duyệt` ở bước chấm chéo — vì chấm chéo chỉ đo
  đồng thuận về đúng/sai của ràng buộc, không đo thời điểm bật.)
  - Nhãn dùng trong lệnh kappa là chuỗi; test kappa dùng "approve"/"reject" và
    "yes"/"no" (xem `tests/test_kappa.py`). Khi chạy lệnh, dùng một bộ nhãn
    trong ba bộ: `duyệt`/`chặn` (tiếng Việt), `approve`/`reject` (tiếng Anh),
    hoặc `yes`/`no` — chỉ cần hai người dùng cùng một bộ nhãn.

### 2.3. Tính kappa và ngưỡng

- **Lệnh:** dùng lệnh đã xong ở task 9.4 (phần lệnh): `cohen_kappa(rater_a, rater_b)`
  trong `packages/core/src/praxon_core/eval/kappa.py`, với `rater_a` = dãy nhãn của
  người duyệt gốc trên các quyết định được chọn, `rater_b` = dãy nhãn của người
  chấm chéo trên cùng các quyết định đó (cùng thứ tự).
- **Ngưỡng đạt:** kappa ≥ 0,61 (`KAPPA_THRESHOLD = 0.61`;
  `kappa_meets_threshold(kappa)` trả True khi ≥ 0,61). Kappa đúng 0,61 thì đạt;
  0,60 thì không (đã có test khẳng định — xem `tests/test_kappa.py`).
- **Trường hợp đặc biệt (đã có trong code):** nếu cả hai người luôn chấm cùng một
  nhãn duy nhất (Pe = 1) thì kappa quy ước là 1,0 (đồng thuận tuyệt đối).
- **Khi kappa < 0,61 (không đạt):** theo dấu hiệu theo dõi của R9 (spec dòng 241:
  "Kappa dưới 0,61"), phải dừng và xem lại — một trong các nguyên nhân: rubric
  chưa rõ (hai người hiểu khác nhau), rubric thiếu điều khoản, hoặc mẫu chưa đủ.
  Loop theo quy trình: tìm nguyên nhân (ở rubric → sửa rubric; ở quy trình chấm
  → sửa quy trình), sửa xong thì chấm chéo lại trên mẫu mới. Không được bỏ qua
  ngưỡng (không hạ chuẩn để cho qua).

## 3. Quy tắc khóa rubric bằng commit

- **Rubric viết trước, không viết sau (spec dòng 138; plan con 9 dòng 222).**
  Rubric phải có mã commit **trước** quyết định thủ công đầu tiên (plan 9.4 dòng
  233: "Rubric có mã commit trước quyết định thủ công đầu tiên").
- **Trình tự:**
  1. Viết rubric (file này).
  2. Commit rubric vào repo (một commit riêng, một dòng, tiếng Anh, conventional
     commits, dưới danh nghĩa Thuận).
  3. Ghi lại mã commit của rubric.
  4. Chỉ sau đó mới làm quyết định thủ công đầu tiên. Quyết định thủ công đầu tiên
     phải ghi rõ nó dùng rubric ở mã commit nào (để đối chiếu).
- **Sửa rubric sau khi đã duyệt (spec dòng 138):** nếu rubric thiếu (không có điều
  khoản nào khớp) thì sửa rubric **trước khi duyệt tiếp**. Mỗi lần sửa rubric cũng
  commit riêng, và các quyết định sau đó dùng rubric ở mã commit mới. Không sửa
  rubric mà không commit.
- **Vị trí file rubric:** `docs/plans/phase-1-core/rubric-duyet.md` (cùng thư mục
  với plan giai đoạn 1) để dễ đối chiếu với plan con 9.

## 4. Cổng ra của task 9.4 (đối chiếu plan)

| Cổng ra (plan dòng 233) | Trạng thái |
|---|---|
| Rubric có mã commit trước quyết định thủ công đầu tiên | **Xong** — file này, khóa bằng commit đầu tiên đưa file vào repo (xem đầu file). |
| Lệnh tính kappa, ngưỡng ≥ 0,61 | **Xong** — `eval/kappa.py` + `tests/test_kappa.py` (8 test), đã merge vào `feat/integration`. |
| Task 9.4 "xong" | **Xong** — cả hai phần (lệnh kappa + rubric) đều xong. |
