# Plan giai đoạn 1 — lõi học

Oct 3, 2026 · @ngoc thuan · **trạng thái: bản nháp, chờ chủ dự án duyệt**

Chia từ `docs/specs/phase-1-core/Spec kỹ thuật — gói core.md` (qua cổng spec lần 5, ngày 3/10/2026) và khẩu phần tám tuần trong `docs/roadmap/Lộ trình — Enterprise Agentic.md`. Chưa duyệt thì chưa được code: quy tắc 1.

**Khẩu phần:** 5/10 – 29/11/2026, tám tuần. **Cổng ra:** cổng 1 ngày 29/11/2026.
**Kiểm cầu dao 50%:** cuối tuần 4, 1/11/2026 — hết plan con 9.

## Cổng 1 phải đạt gì

Lấy nguyên từ lộ trình, không diễn giải thêm:

1. Một lệnh chạy bảy điều kiện trên cả hai nguồn dữ liệu.
2. In bốn chỉ số theo từng tenant kèm khoảng tin cậy và bản ghi lần chạy.
3. Chạy lại ra đúng kết quả đó.
4. 21 phép tấn công bị chặn.
5. CI xanh ở mọi cổng máy.
6. Ba nền móng phòng điều khiển có test.

## Mười ba plan con

Plan con là đơn vị review, tuần là khẩu phần — nên plan con chia theo khối việc và được *gắn* vào tuần, không đặt tên theo tuần.

| # | Plan con | Tuần | Cổng ra của plan con | Cắt được không |
| --- | --- | --- | --- | --- |
| 1 | Nền móng kho và cổng máy | 1 | Mọi cổng máy chạy, và mỗi cổng có một test âm chứng minh nó thật sự chặn | Không bao giờ |
| 2 | Lược đồ và bất biến dữ liệu | 1 | 21/21 phép tấn công bị chặn dưới vai ứng dụng; một tệp compose dựng cả hệ | Không bao giờ |
| 3 | Hồ sơ dữ liệu và phép chia | 1 | Một lệnh sinh bảng hồ sơ năm đô thị, chạy lại ra đúng bảng | Không bao giờ |
| 4 | Khám phá Declare | 2 | Dưới 30 giây trên log giả cỡ đô thị 1 khi không lọc trước; trùng tập luật với bản duyệt thẳng và với pm4py ngoài kho | Không bao giờ |
| 5 | Bộ sinh bán tổng hợp | 2 | Qua nghiệm thu: khám phá trên 300 trace *không* đúng tuyệt đối so với đáp án | Không bao giờ |
| 6 | Adapter mô hình, Reflector, F1 | 2 | F1 theo mẫu Declare trên 104 câu có số; hai backend qua cùng test hợp đồng | Thu về bài đo F1 |
| 7 | Vòng học: Curator, Governor, Applier, Promoter | 3 | Chạy lại Governor trên cùng candidate và cùng bảng luật ra đúng quyết định cũ | Không bao giờ |
| 8 | Baseline và đường cong khởi động lạnh | 3 | Bốn chỉ số kèm khoảng tin cậy cho điều kiện chỉ-Declare và cách ly; đường cong ở 0, 5, 10, 20, 40 trace | **Không bao giờ** |
| 9 | Đường vào tài liệu, rubric, hiệu chỉnh | 4 | Số luật trích từ Wabo và tỉ lệ bị cổng loại; rubric khóa bằng commit; kappa ≥ 0,61 | Bỏ phần BPIC 2019 |
| 10 | Bộ điều phối, bảy điều kiện, ToolGateway | 5 | Bảy điều kiện chạy hết trên bộ chuẩn bán tổng hợp bằng một lệnh; test hợp đồng ToolGateway xanh | Giảm số lần rút bootstrap |
| 11 | Chạy đầy đủ trên Kaggle | 6 | Một điều kiện chạy hết trong một phiên, đứt thì chạy tiếp từ checkpoint trên R2 | Không bao giờ |
| 12 | Khóa cấu hình và chạy phần đo | 7 | Bộ điều phối từ chối chạy phần đo khi `config_hash` khác bản đã khóa; chạy lại ra đúng kết quả | **Không bao giờ** |
| 13 | Báo cáo và demo một lệnh | 8 | Cổng 1 đủ sáu điều kiện trên | Không bao giờ |

Thứ tự cắt khi cầu dao nhảy, theo lộ trình: plan con 6 thu về bài đo F1 → bỏ phần điều kiện dữ liệu trên BPIC 2019 trong plan con 9 → giảm số lần rút bootstrap trong plan con 10.

---

## Plan con 1 — Nền móng kho và cổng máy

**Tuần:** 1 · **Mục tiêu:** mọi cổng máy trong `CLAUDE.md` chạy và chặn được merge, *trước* khi có dòng mã nghiệp vụ nào.
**Cổng ra:** CI xanh, và mỗi cổng có một test âm — một vi phạm cố ý làm cổng đó trả mã khác 0 — chứng minh cổng không phải trang trí.
**Bất biến chạm tới:** `core` không import `platform`; một mã nguồn không hai nhánh; hạn mức là dữ liệu không hard-code.
**Phụ thuộc:** không.
**Thứ tự cắt:** không cắt gì. Spec nói độ phủ áp *từ commit đầu tiên*, nên plan con này đi trước mọi plan con khác.

| # | Task | Cổng ra kiểm bằng máy | Trạng thái | Review |
| --- | --- | --- | --- | --- |
| 1.1 | Cấu trúc gói `core/` và `platform/`, `pyproject.toml`, khóa phiên bản phụ thuộc | `pip install -e .` xong; `python -c "import core"` mã thoát 0 | chưa làm | chưa review |
| 1.2 | Bốn hợp đồng import-linter: core ⇸ platform, SDK mô hình chỉ trong `adapters`, driver cơ sở dữ liệu chỉ trong `repositories`, client MCP và SDK agent chỉ trong `gateway` và `adapters`; bắt buộc `include_external_packages = True` | `lint-imports` mã thoát 0; thêm tạm một import vi phạm từng hợp đồng → mã thoát khác 0, bốn lần | chưa làm | chưa review |
| 1.3 | mypy strict, ruff, ruff format | `mypy --strict core` 0 lỗi; `ruff check` và `ruff format --check` 0 lỗi | chưa làm | chưa review |
| 1.4 | pip-licenses chạy trần, không qua ống dẫn; khớp một phần theo từ khóa AGPL, GPL, UNKNOWN | Mã thoát 0 trên bộ phụ thuộc hiện tại; thêm tạm một gói AGPL → mã thoát khác 0 | chưa làm | chưa review |
| 1.5 | Cổng độ phủ 85% trên `core` | `pytest --cov=core --cov-fail-under=85` xanh | chưa làm | chưa review |
| 1.6 | Module settings có kiểu, nạp từ một tệp; bước CI tìm `os.environ` và `getenv` ngoài module đó | Test nạp cấu hình sai kiểu bị từ chối; script grep mã thoát 0, và khác 0 khi đặt tạm một `getenv` ngoài settings | chưa làm | chưa review |
| 1.7 | Bước CI chặn `.xes`, `.csv`, `.gz` trong kho ngoài thư mục fixture | Script mã thoát 0; thêm tạm một tệp `.xes` ngoài fixture → mã thoát khác 0 | chưa làm | chưa review |

**Review plan con 1** — ngày: · người review: · kết luận:

---

## Plan con 2 — Lược đồ và bất biến dữ liệu

**Tuần:** 1 · **Mục tiêu:** sáu bất biến dữ liệu của spec do cơ sở dữ liệu chặn, không do mã nhớ phải chặn.
**Cổng ra:** 21/21 phép tấn công bị chặn, chạy dưới đúng vai ứng dụng — không bao giờ dưới tài khoản quản trị.
**Bất biến chạm tới:** `episode` và `event` chỉ thêm; chỉ `applier` và `promoter` ghi tri thức; chỉ `promoter` ghi `global`; không hai fact cùng khóa cùng hiệu lực; áp candidate lũy đẳng.
**Phụ thuộc:** plan con 1.
**Thứ tự cắt:** không cắt gì.

| # | Task | Cổng ra kiểm bằng máy | Trạng thái | Review |
| --- | --- | --- | --- | --- |
| 2.1 | `docker compose` dựng Postgres 16 kèm pgvector | `docker compose up -d` rồi `SELECT 1` qua vai ứng dụng, mã thoát 0 từ máy trống | chưa làm | chưa review |
| 2.2 | Migration các bảng `episode`, `fact`, `candidate`, `run`, `event`; các vai `ingestor`, `applier`, `promoter`, `reader` | Migration chạy từ cơ sở dữ liệu trống; chạy lần hai là lũy đẳng, không lỗi | chưa làm | chưa review |
| 2.3 | RLS `ENABLE` và `FORCE` trên mọi bảng có dữ liệu tenant; policy cho tenant đọc hàng của mình cộng hàng `global`; chưa đặt tenant thì 0 hàng | Test: đọc chéo tenant ra 0 hàng; chưa đặt tenant ra 0 hàng; truy vấn `pg_roles` xác nhận không vai nào superuser hay `BYPASSRLS` | chưa làm | chưa review |
| 2.4 | Quyền chỉ thêm trên `episode` và `event`; exclusion constraint trên `(scope, canonical_key, valid_during, known_during)`; unique trên `candidate_id` | Test: UPDATE và DELETE bị từ chối trên hai bảng; thêm fact trùng khóa trùng hiệu lực bị từ chối; áp lại cùng candidate không tạo hàng thứ hai | chưa làm | chưa review |
| 2.5 | Bộ 21 phép tấn công thành test tích hợp | `pytest tests/integration/test_invariants.py` xanh, 21/21 bị chặn | chưa làm | chưa review |

**Review plan con 2** — ngày: · người review: · kết luận:

---

## Plan con 3 — Hồ sơ dữ liệu và phép chia

**Tuần:** 1 · **Mục tiêu:** biết dữ liệu thật trông thế nào trước khi xây bất cứ thứ gì lên nó. Spec chỉ định đây là **task đầu tiên của plan**, không lồng vào giữa.
**Cổng ra:** một lệnh sinh bảng hồ sơ năm đô thị từ log tải lúc chạy, chạy lại ra đúng bảng đó.
**Bất biến chạm tới:** dữ liệu bên thứ ba không nằm trong kho; tham số chia vào `data_hash`.
**Phụ thuộc:** plan con 1 (bước CI chặn dữ liệu phải có trước khi tải log về máy).
**Rủi ro trả lời ở đây:** R2 mức khác biệt giữa năm đô thị, R4 thuộc tính phân loại nào có thật, R14 phân phối theo thời gian, R15 số hoạt động còn lại sau lọc.
**Điểm quyết định đã chốt trong spec:** năm đô thị khác nhau ít **không** phải lý do dừng, mà là một kết quả cần báo cáo. Chỉ dừng và quay về spec nếu log hỏng hoặc thiếu trường bắt buộc.

| # | Task | Cổng ra kiểm bằng máy | Trạng thái | Review |
| --- | --- | --- | --- | --- |
| 3.1 | Bộ tải log BPIC 2015 từ nguồn gốc, kiểm băm, không đóng gói vào kho | Lệnh tải xong, băm khớp giá trị đã ghi; bước CI chặn dữ liệu vẫn mã thoát 0 | chưa làm | chưa review |
| 3.2 | Bảng hồ sơ: số case, số sự kiện, số loại hoạt động, phân phối theo thời gian, danh sách thuộc tính phân loại có mặt | Lệnh in bảng; số case khớp 1.199 / 832 / 1.409 / 1.053 / 1.156 — đối chiếu bài báo số 1 của BPIC 2015 | chưa làm | chưa review |
| 3.3 | Chia theo thời điểm bắt đầu case 60/20/20; `data_hash` băm tệp log, tham số chia, danh sách tenant | Test: không case nào nằm ở hai phần; mọi case ở phần học bắt đầu trước mọi case ở phần đo; đổi tham số chia thì `data_hash` đổi | chưa làm | chưa review |
| 3.4 | Báo cáo mức khác biệt giữa năm đô thị và số hoạt động còn lại sau lọc | Báo cáo sinh bằng lệnh, có số; nếu log hỏng hoặc thiếu trường thì dừng và quay về spec | chưa làm | chưa review |

**Luồng song song, hạn tuần 1:** chủ dự án đọc điều khoản Kaggle trước khi dùng tài khoản thứ hai.

**Review plan con 3** — ngày: · người review: · kết luận:

---

## Plan con 4 — Khám phá Declare

**Tuần:** 2 · **Mục tiêu:** nền tri thức tự viết clean room, đủ nhanh để chạy hàng nghìn lần trong đánh giá.
**Cổng ra:** log giả cỡ đô thị 1, không lọc trước, dưới 30 giây trên CPU; cùng tập luật với bản duyệt thẳng trên một lát nhỏ; trùng pm4py trên môi trường đối chiếu ngoài kho.
**Bất biến chạm tới:** clean room — viết từ định nghĩa hình thức trong bài báo, không mở mã pm4py; pm4py không nằm trong phụ thuộc của `core`.
**Phụ thuộc:** plan con 1, plan con 3 (cần log thật để biết số hoạt động).

| # | Task | Cổng ra kiểm bằng máy | Trạng thái | Review |
| --- | --- | --- | --- | --- |
| 4.1 | Bản quyết định kiến trúc ghi nguồn của từng mẫu Declare | Tệp tồn tại ở `docs/decisions/`, mỗi mẫu trỏ một định nghĩa trong bài báo | chưa làm | chưa review |
| 4.2 | Chỉ mục vị trí đầu và cuối của mỗi hoạt động trong mỗi trace | Unit test ngữ nghĩa: `Response(a,b)` đúng khi b sau lần a cuối; `Precedence(a,b)` đúng khi a đầu trước b đầu | chưa làm | chưa review |
| 4.3 | Lọc trước theo `support × confidence` | Test: tập luật sau lọc trùng tập luật khi không lọc, trên một lát nhỏ | chưa làm | chưa review |
| 4.4 | Test hiệu năng trong CI | `pytest tests/perf` dưới 30 giây trên log giả cỡ đô thị 1, không lọc trước | chưa làm | chưa review |
| 4.5 | Môi trường đối chiếu pm4py, ngoài kho, không vào phụ thuộc `core` | Script đối chiếu cho kết quả trùng khớp; `pip-licenses` của `core` vẫn mã thoát 0 | chưa làm | chưa review |

**Review plan con 4** — ngày: · người review: · kết luận:

---

## Plan con 5 — Bộ sinh bán tổng hợp

**Tuần:** 2 · **Mục tiêu:** bộ chuẩn có đáp án tuyệt đối và số tenant tùy ý, đủ khó để phân biệt được các thiết kế.
**Cổng ra nghiệm thu:** bộ sinh có bước tùy chọn với tỉ lệ bỏ qua lấy từ log thật, và khám phá trên 300 trace **không** đúng tuyệt đối so với đáp án. Bộ chuẩn mà phương pháp nào cũng đạt trần thì không phân biệt được gì.
**Phụ thuộc:** plan con 3 (mức nhiễu, tỉ lệ case dở dang, số case lấy từ log thật), plan con 4 (khám phá mô hình quy trình của từng đô thị).

| # | Task | Cổng ra kiểm bằng máy | Trạng thái | Review |
| --- | --- | --- | --- | --- |
| 5.1 | Bộ sinh nhận seed và tham số riêng; đổi có kiểm soát một số luật thứ tự theo tenant | Cùng seed ra cùng log; đáp án xuất ra cùng lúc với log | chưa làm | chưa review |
| 5.2 | Tham số nhiễu, tỉ lệ bỏ bước, số case lấy từ bảng hồ sơ của plan con 3 | Test: tham số bộ sinh nằm trong khoảng đo được từ log thật | chưa làm | chưa review |
| 5.3 | Nghiệm thu bộ chuẩn | Test: khám phá trên 300 trace cho F1 dưới 1,00 so với đáp án | chưa làm | chưa review |
| 5.4 | `data_hash` gồm seed và tham số bộ sinh | Đổi một tham số bộ sinh thì `data_hash` đổi | chưa làm | chưa review |

**Review plan con 5** — ngày: · người review: · kết luận:

---

## Plan con 6 — Adapter mô hình, Reflector, F1 trích luật

**Tuần:** 2 · **Mục tiêu:** vai duy nhất gọi mô hình chạy được, có số đo riêng cho chất lượng trích luật từ văn bản.
**Cổng ra:** F1 theo từng mẫu Declare trên bộ 104 câu, có số để so với 0,79 mà GPT-4 đạt; hai backend qua cùng bộ test hợp đồng.
**Bất biến chạm tới:** mọi lệnh gọi mô hình qua một adapter `LanguageModel`; bộ 104 câu tải lúc đo, không vào kho; khóa đệm phải gồm mọi thứ ảnh hưởng kết quả.
**Phụ thuộc:** plan con 1, plan con 4 (schema Declare).
**Thứ tự cắt:** đây là chỗ cắt đầu tiên nếu cầu dao nhảy — điều kiện thứ bảy thu về đúng bài đo F1 này.

| # | Task | Cổng ra kiểm bằng máy | Trạng thái | Review |
| --- | --- | --- | --- | --- |
| 6.1 | Giao diện `LanguageModel` cộng hai backend: mô hình nhỏ trên CPU, endpoint tương thích OpenAI | Cùng bộ test hợp đồng xanh cho cả hai backend; `lint-imports` xác nhận SDK chỉ nằm trong `adapters` | chưa làm | chưa review |
| 6.2 | Giải mã có ràng buộc theo JSON schema Declare; schema chỉ cho các mẫu trong từ vựng | Test: đầu ra luôn đúng lược đồ; mô hình không thể sinh luật thời hạn | chưa làm | chưa review |
| 6.3 | Bộ nhớ đệm phản hồi, khóa gồm băm prompt, `model_revision`, tham số giải mã, băm JSON schema | Test: đổi schema thì đệm không trả kết quả cũ; cùng đầu vào thì không gọi mô hình lần hai | chưa làm | chưa review |
| 6.4 | Reflector theo lô, có trần số insight mỗi lô, hai đường vào là trace và tài liệu | Test: vượt trần thì cắt, không tràn; lỗi gọi mô hình thì thử lại có giãn cách rồi đánh dấu cả lô thất bại, không nuốt lỗi | chưa làm | chưa review |
| 6.5 | Bài đo F1 trên bộ 104 câu, tải lúc đo | Lệnh in F1 theo từng mẫu Declare; bước CI chặn dữ liệu vẫn mã thoát 0 | chưa làm | chưa review |

**Review plan con 6** — ngày: · người review: · kết luận:

---

## Plan con 7 — Vòng học: Curator, Governor, Applier, Promoter

**Tuần:** 3 · **Mục tiêu:** vòng học đi hết từ trace đến fact đã ghi, mọi quyết định giải thích được và chạy lại được.
**Cổng ra:** chạy lại Governor trên cùng candidate và cùng bảng luật ra đúng quyết định cũ, kèm số hiệu luật đã khớp và giá trị các đại lượng lúc đánh giá.
**Bất biến chạm tới:** mỗi vai là hàm thuần, không vai nào gọi vai khác; chỉ delta, không viết lại toàn bộ tập fact; tiên nghiệm một mình không bao giờ đưa luật lên chính thức.
**Phụ thuộc:** plan con 2, 4, 6.

| # | Task | Cổng ra kiểm bằng máy | Trạng thái | Review |
| --- | --- | --- | --- | --- |
| 7.1 | Generator phát lại trace từ `episode`, không gọi mô hình | Test: không lệnh gọi mô hình nào phát sinh; `Trajectory` là kiểu có khai báo, mypy strict pass | chưa làm | chưa review |
| 7.2 | Curator sinh `Delta` bốn loại `ADD`, `CONFIRM`, `CONTRADICT`, `RETIRE`; bảng cặp mẫu đối nghịch | Test: so khớp chính xác trên `canonical_key`; mâu thuẫn trực tiếp bị nhận ra; không gọi mô hình | chưa làm | chưa review |
| 7.3 | Governor: bảng nạp bằng Pydantic, chín luật theo thứ tự, luật đầu khớp thì thắng, không luật nào khớp thì cần người duyệt | Test: không có `eval`; điều kiện chỉ lấy từ danh sách đại lượng cho trước; chạy lại ra đúng quyết định cũ | chưa làm | chưa review |
| 7.4 | Cổng Beta và cận dưới Wilson; ghi `rule_id` và `metrics_at_decision` vào `candidate` | Unit test trên số đếm biết trước cho từng luật 2, 3, 4, 7 | chưa làm | chưa review |
| 7.5 | Bất biến tiên nghiệm, kiểm theo từng luật lúc nạp gói | Unit test: gói có luật độ tin 1,0 với độ mạnh 8 **bị từ chối**; độ mạnh mặc định 4 được nhận | chưa làm | chưa review |
| 7.6 | Applier và Promoter, chỉ áp candidate đã có quyết định, lũy đẳng | Test: ghi qua vai khác bị cơ sở dữ liệu chặn; áp lại cùng candidate không làm gì | chưa làm | chưa review |
| 7.7 | Bảng `event` ghi mỗi lần gọi vai và mỗi quyết định của Governor | Test: `event` từ chối UPDATE và DELETE; mỗi hàng có `run_id`, `tenant_id`, `actor`, `decision`, `decided_by` | chưa làm | chưa review |

**Review plan con 7** — ngày: · người review: · kết luận:

---

## Plan con 8 — Baseline và đường cong khởi động lạnh

**Tuần:** 3 · **Mục tiêu:** cái thước đo. Không có số này thì không đi tiếp — lộ trình ghi đúng chữ đó.
**Cổng ra:** bốn chỉ số theo từng tenant kèm khoảng tin cậy 95% cho điều kiện chỉ-Declare và điều kiện cách ly; đường cong khởi động lạnh ở 0, 5, 10, 20, 40 trace, điểm 0 ghi rõ là đo trên luật `trial` ở chế độ giám sát.
**Bất biến chạm tới:** ground truth không đi qua mô hình; đáp án trên dữ liệu thật lấy từ **phần đo**, không từ phần học; bốn chỉ số luôn báo cùng nhau.
**Phụ thuộc:** plan con 3, 4, 5, 7.
**Thứ tự cắt:** **không bao giờ cắt.**

| # | Task | Cổng ra kiểm bằng máy | Trạng thái | Review |
| --- | --- | --- | --- | --- |
| 8.1 | Ground truth: bộ chuẩn lấy đáp án từ bộ sinh; BPIC 2015 lấy từ khám phá trên phần đo với ngưỡng cố định dùng chung cho cả bảy điều kiện | Test: không điều kiện nào được chấm bằng đáp án sinh từ chính nó; đổi điều kiện không đổi đáp án | chưa làm | chưa review |
| 8.2 | Bốn chỉ số: precision, recall, tỉ lệ vi phạm, negative transfer | Test trên tenant giả có đáp án biết trước; mỗi chỉ số có một ca ra khác 0 | chưa làm | chưa review |
| 8.3 | Khoảng tin cậy 95% bằng bootstrap trên case | Test: cùng seed ra cùng khoảng; số lần rút nằm trong cấu hình, không hard-code | chưa làm | chưa review |
| 8.4 | Đường cong khởi động lạnh ở 0, 5, 10, 20, 40 trace | Lệnh in đường cong; điểm 0 có nhãn ghi rõ đo trên luật `trial` chế độ giám sát | chưa làm | chưa review |
| 8.5 | Báo cáo baseline chỉ-Declare và cách ly | Báo cáo sinh bằng lệnh, bốn chỉ số theo tenant kèm khoảng tin cậy | chưa làm | chưa review |

**Điểm quyết định đã chốt trong spec:** nếu ở 0, 5 và 10 trace điều kiện tài liệu cộng dữ liệu không hơn chỉ-Declare, phần LLM của lát cắt thu về bài đo trích luật từ văn bản, và tuyên bố của dự án đổi theo. Đây là một kết quả, không phải thất bại.

**Review plan con 8** — ngày: · người review: · kết luận:

---

## Plan con 9 — Đường vào tài liệu, rubric, hiệu chỉnh

**Tuần:** 4 · **Mục tiêu:** đường vào thứ hai của Reflector chạy được, việc duyệt thủ công kiểm lại được, tham số hiệu chỉnh đúng chỗ.
**Cổng ra:** số luật thứ tự trích được từ Wabo và tỉ lệ bị cổng loại; rubric khóa bằng commit trước lần duyệt đầu tiên; kappa duyệt chéo ≥ 0,61.
**Bất biến chạm tới:** luật từ tài liệu cũng đi qua `Candidate` và vào `trial`; quyết định của người dùng chỉ vào hệ qua `Candidate`; tham số chỉ chỉnh trên phần hiệu chỉnh; rubric viết trước.
**Phụ thuộc:** plan con 6, 7, 8.
**Thứ tự cắt:** bỏ phần điều kiện dữ liệu trên BPIC 2019 (task 9.5) là nhát cắt thứ hai của giai đoạn.
**Cuối plan con này là kiểm cầu dao 50% — 1/11/2026.**

| # | Task | Cổng ra kiểm bằng máy | Trạng thái | Review |
| --- | --- | --- | --- | --- |
| 9.1 | Trích luật thứ tự từ Wabo vào `global`, kế thừa `valid_during` của văn bản | Lệnh in số luật trích được và số bị cổng Beta loại; test: fact từ Wabo mang khoảng hiệu lực của Wabo | chưa làm | chưa review |
| 9.2 | Gắn khái niệm tiếng Hà Lan với tên hoạt động trong log, là một bước có kiểm | Test: bảng gắn nạp được, gắn sai thì luật bị cổng loại chứ không áp sai | chưa làm | chưa review |
| 9.3 | Quyết định của người dùng thành `Candidate` kèm `decided_by` và `rubric_clause` | Test: không có đường ghi tắt nào vòng qua `Candidate`; thiếu `rubric_clause` thì từ chối | chưa làm | chưa review |
| 9.4 | Rubric duyệt viết trước, khóa bằng commit; duyệt chéo mù một phần năm quyết định thủ công | Rubric có mã commit trước quyết định thủ công đầu tiên; lệnh tính kappa, ngưỡng ≥ 0,61 | chưa làm | chưa review |
| 9.5 | Kiểm điều kiện thuộc tính phân loại trên loại matching của BPIC 2019 | Lệnh in số case trong phần thỏa điều kiện; dưới 30 case thì loại theo luật 7 | chưa làm | chưa review |
| 9.6 | Hiệu chỉnh 0,7; 0,95; 0,05; độ mạnh tiên nghiệm; phần tối thiểu 30 case — chỉ trên phần hiệu chỉnh | Test: bộ điều phối từ chối hiệu chỉnh trên phần đo; độ mạnh tiên nghiệm thử ít nhất ba giá trị, tất cả trong vùng bất biến cho phép | chưa làm | chưa review |
| 9.7 | Biên bản kiểm cầu dao 50% | Văn bản ở `docs/plans/phase-1-core/`: đã xong bao nhiêu phần việc cốt lõi, cắt gì nếu chưa đạt | chưa làm | chưa review |

**Review plan con 9** — ngày: · người review: · kết luận:

---

## Plan con 10 — Bộ điều phối, bảy điều kiện, ToolGateway

**Tuần:** 5 · **Mục tiêu:** một lệnh chạy hết bảy điều kiện, và nền móng phòng điều khiển có mặt đúng lúc còn rẻ.
**Cổng ra:** bảy điều kiện chạy hết trên bộ chuẩn bán tổng hợp bằng một lệnh; test hợp đồng `ToolGateway` xanh với một cổng giả.
**Bất biến chạm tới:** bộ điều phối mỏng, không vai nào gọi vai khác; mọi tool call qua `ToolGateway`; trần token kiểm **trước** khi gọi.
**Phụ thuộc:** plan con 7, 8, 9.
**Thứ tự cắt:** giảm số lần rút bootstrap là nhát cắt thứ ba.

| # | Task | Cổng ra kiểm bằng máy | Trạng thái | Review |
| --- | --- | --- | --- | --- |
| 10.1 | Bộ điều phối mỏng nối sáu vai; ghi `run` với seed, `model_id`, `model_revision`, `code_commit`, `config_hash`, `data_hash`, token vào ra | Test: mỗi vai vẫn là hàm thuần; `run` có đủ sáu trường điều kiện tái lập | chưa làm | chưa review |
| 10.2 | Bảy điều kiện thí nghiệm chạy bằng một lệnh trên bộ chuẩn bán tổng hợp | Lệnh in bốn chỉ số theo tenant cho cả bảy điều kiện | chưa làm | chưa review |
| 10.3 | Checkpoint mỗi N case gồm fact, candidate chờ, con trỏ case, bộ nhớ đệm; đẩy sang R2 | Test: cắt giữa lần chạy rồi khởi động lại, chạy tiếp từ con trỏ, kết quả không đổi | chưa làm | chưa review |
| 10.4 | Trần token kiểm trước khi gọi; chạm trần thì ghi checkpoint, đóng `run` trạng thái `budget_exceeded`, thoát mã lỗi rõ | Test: không lệnh gọi nào vượt trần được phát ra | chưa làm | chưa review |
| 10.5 | Khai báo giao diện `ToolGateway` bốn quyết định: cho, chặn, hỏi người, để luật quyết | Test hợp đồng với cổng giả xanh; `lint-imports` xác nhận client tool chỉ trong `gateway` và `adapters` | chưa làm | chưa review |

**Review plan con 10** — ngày: · người review: · kết luận:

---

## Plan con 11 — Chạy đầy đủ trên Kaggle

**Tuần:** 6 · **Mục tiêu:** bảy điều kiện chạy hết trên hạ tầng thật, số liệu trên phần hiệu chỉnh.
**Cổng ra:** một điều kiện chạy hết trong một phiên 12 giờ; cắt phiên rồi chạy tiếp từ checkpoint trên R2 cho đúng kết quả.
**Bất biến chạm tới:** checkpoint không bao giờ chỉ nằm trên Kaggle.
**Phụ thuộc:** plan con 10. **Phụ thuộc ngoài:** chủ dự án đã đọc điều khoản Kaggle ở tuần 1.

| # | Task | Cổng ra kiểm bằng máy | Trạng thái | Review |
| --- | --- | --- | --- | --- |
| 11.1 | Notebook Kaggle dựng `core` bằng một tệp compose hoặc tương đương, vLLM phục vụ mô hình mở 8B | Notebook chạy từ đầu, in phiên bản mô hình và `model_revision` | chưa làm | chưa review |
| 11.2 | Chạy bảy điều kiện trên bộ chuẩn và trên phần hiệu chỉnh của năm đô thị | Bản ghi `run` cho từng lần chạy, không lần nào trạng thái `budget_exceeded` ngoài dự kiến | chưa làm | chưa review |
| 11.3 | Phép thử đứt phiên | Dừng phiên giữa chừng, phiên sau nạp checkpoint từ R2 và ra đúng kết quả | chưa làm | chưa review |
| 11.4 | Sửa lỗi phát hiện từ bảy điều kiện | Mọi lỗi sửa xong có test hồi quy; CI xanh | chưa làm | chưa review |

**Review plan con 11** — ngày: · người review: · kết luận:

---

## Plan con 12 — Khóa cấu hình và chạy phần đo

**Tuần:** 7 · **Mục tiêu:** kết quả công bố được, chạy một lần, chạy lại ra đúng nó.
**Cổng ra:** bộ điều phối **từ chối** chạy phần đo khi `config_hash` khác bản đã khóa; chạy lại lần hai cho đúng kết quả lần đầu.
**Bất biến chạm tới:** phần đo chạy một lần; thiếu một trong sáu điều kiện tái lập thì `run` ghi *không tái lập được*, không im lặng cho qua.
**Phụ thuộc:** plan con 11.
**Thứ tự cắt:** **không bao giờ cắt.**

| # | Task | Cổng ra kiểm bằng máy | Trạng thái | Review |
| --- | --- | --- | --- | --- |
| 12.1 | Khóa cấu hình bằng commit trước khi chạm phần đo | Test tích hợp: `config_hash` khác bản đã khóa thì bộ điều phối từ chối chạy phần đo | chưa làm | chưa review |
| 12.2 | Chạy phần đo BPIC 2015 một lần, bảy điều kiện, năm đô thị | Bốn chỉ số theo tenant kèm khoảng tin cậy; bản ghi `run` đầy đủ | chưa làm | chưa review |
| 12.3 | Chạy lại để kiểm tái lập | Kết quả trùng lần đầu; thiếu một điều kiện tái lập thì `run` ghi *không tái lập được* | chưa làm | chưa review |

**Review plan con 12** — ngày: · người review: · kết luận:

---

## Plan con 13 — Báo cáo và demo một lệnh

**Tuần:** 8, có đệm · **Mục tiêu:** cổng 1.
**Cổng ra:** đủ sáu điều kiện của cổng 1.
**Phụ thuộc:** plan con 12.

| # | Task | Cổng ra kiểm bằng máy | Trạng thái | Review |
| --- | --- | --- | --- | --- |
| 13.1 | Một lệnh chạy bảy điều kiện trên cả hai nguồn dữ liệu, in bốn chỉ số và bản ghi lần chạy | Lệnh chạy từ máy trống qua compose; chạy lại ra đúng kết quả | chưa làm | chưa review |
| 13.2 | Báo cáo kết quả giai đoạn 1 | Mọi số trong báo cáo sinh được bằng lệnh, không chép tay | chưa làm | chưa review |
| 13.3 | Báo cáo cổng 1 | Sáu điều kiện cổng, mỗi điều kiện một phép thử hoặc một con số | chưa làm | chưa review |
| 13.4 | Spec giai đoạn 2a cho tuần nghỉ 30/11 – 6/12 | Spec qua cổng spec của giai đoạn 2a | chưa làm | chưa review |

**Review plan con 13** — ngày: · người review: · kết luận:

---

## Tự review theo cổng plan — 3/10/2026

Chạy bảy câu của `docs/process/Quy trình làm việc — spec, plan, code.md` trên chính plan này, theo quy tắc 6.

| # | Câu hỏi | Kết quả |
| --- | --- | --- |
| 1 | Mỗi task có cổng ra kiểm được bằng máy chưa? | Đạt — 65 task trên 13 plan con, mỗi task một lệnh hoặc một test. Task 3.4, 9.7, 13.2 và 13.3 ra văn bản, nhưng điều kiện là văn bản đó *sinh bằng lệnh*, không chép tay |
| 2 | Task nào chạm bất biến nào, bất biến đó có test chưa? | Đạt — mỗi plan con liệt kê bất biến chạm tới; plan con 1 và 2 dựng test cho bất biến trước khi có mã nghiệp vụ |
| 3 | Thứ tự task có chỗ nào phải làm lại vì phụ thuộc ngược không? | Đạt — mỗi plan con ghi phụ thuộc; plan con 3 đi sau plan con 1 vì cần bước CI chặn dữ liệu trước khi tải log về máy |
| 4 | Nền móng nào rẻ bây giờ mà đắt về sau, đã nằm đủ sớm chưa? | Đạt — ba nền móng phòng điều khiển: bảng `event` ở task 7.7, `ToolGateway` ở 10.5, quyết định người dùng thành `Candidate` ở 9.3 |
| 5 | Task nào phụ thuộc hạn mức GPU, giấy phép hay người thứ ba? Có đường đi khi nó trượt không? | Đạt — plan con 11 phụ thuộc Kaggle, có backend CPU và bộ nhớ đệm làm đường đi; task 9.4 phụ thuộc người duyệt chéo, hạn liên tục từ tuần 4; giấy phép AppWorld thuộc tuần nghỉ trước 2a, ngoài plan này |
| 6 | Việc cốt lõi chiếm bao nhiêu phần khẩu phần? Mốc 50% rơi vào task nào? | Đạt — mốc 50% là cuối plan con 9, task 9.7 là biên bản kiểm |
| 7 | Thứ tự cắt khi chậm đã viết ra trước chưa? | Đạt — ba nhát cắt ghi ở bảng mười ba plan con và ở từng plan con liên quan |

**Chỗ tôi tự thấy yếu và đã sửa trước khi gửi:** bản nháp đầu đặt plan con 3 ở vị trí đầu tiên theo đúng chữ của spec, nhưng như vậy thì log được tải về máy trước khi bước CI chặn dữ liệu tồn tại — một đường để lọt `.xes` vào kho. Đã đổi: plan con 1 đi trước, plan con 3 vẫn là *task đầu tiên về dữ liệu* và vẫn không lồng vào giữa như spec yêu cầu.

**Chỗ còn là giả thuyết, chưa có bằng chứng:** khẩu phần từng plan con trong một tuần. Lộ trình chốt tám tuần và việc chính mỗi tuần, nhưng chưa ai đo một task như 2.5 hay 7.4 mất bao lâu. Cách kiểm: hết tuần 1, so số task đã xong với số task đã xếp, rồi chỉnh khẩu phần tuần 2 trở đi trước khi cầu dao kịp nhảy.
