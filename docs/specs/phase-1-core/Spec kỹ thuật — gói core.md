# Spec kỹ thuật — gói core, lát cắt tháng 11/2026

Oct 3, 2026 · @ngoc han

Spec này mô tả gói **core** — phần cơ chế, giấy phép Apache 2.0 — ở mức đủ để chia plan và viết code mà không phải quay lại hỏi. Phần platform (đa tenant thương mại, hạn mức, SSO, audit export) có spec riêng, làm ở giai đoạn 3.

## Phạm vi: học đúng luật riêng, không nhiễm luật người khác

Lát cắt tháng 11 chứng minh một điều: hệ học được luật riêng của từng tổ chức và dùng được tri thức chung mà không áp sai luật của người khác — kể cả ngày đầu, khi chưa có dữ liệu — lúc đó luật chung chạy ở chế độ giám sát — ghi lại case nào sẽ vi phạm, không chặn. Hai nguồn dữ liệu trả lời hai câu hỏi khác nhau. Bộ chuẩn bán tổng hợp, sinh từ mô hình quy trình của năm đô thị BPIC 2015 nên biết trước luật nào khác ở tenant nào, trả lời câu thiết kế nào tốt hơn. BPIC 2015 thật — năm đô thị Hà Lan cùng một quy trình cấp phép xây dựng, mỗi đô thị một tenant — trả lời câu kết quả có đứng vững trên dữ liệu thật không. Generator đọc lại trace có sẵn, không gọi mô hình; chỉ Reflector gọi mô hình, với hai đường vào: trace và tài liệu quy trình. Không có agent thực thi nên LangGraph chưa vào phạm vi.

**Trong phạm vi lát cắt tháng 11:**

- Tầng episodic và tầng semantic, phạm vi tri thức tenant và `global`
- Từ vựng canonical là các mẫu Declare, khám phá Declare tự viết trong core, điều kiện trên thuộc tính phân loại
- Vòng học: Generator phát lại trace, Reflector đọc trace và tài liệu, Curator, Governor, Applier, Promoter
- Trạng thái thử cho fact và cổng thống kê Beta để lên chính thức
- Bảng luật duyệt cho tầng semantic và cho việc nâng lên `global`
- Bộ đánh giá: bộ chuẩn bán tổng hợp, bảy điều kiện thí nghiệm, bốn chỉ số kèm khoảng tin cậy, đường cong khởi động lạnh, F1 trích luật từ văn bản
- Bản ghi mỗi lần chạy, đủ để tái lập

Thiết kế giữ trong spec nhưng code ở giai đoạn 2: tầng playbook, tầng procedural, thư viện skill, induction gating, Generator gọi mô hình thật trên AppWorld, và phòng điều khiển — proxy MCP có quyền chặn, adapter cho Claude Agent SDK và runtime tương thích OpenAI, giao diện tối thiểu trên AG-UI. Hai tầng mới cần agent thực thi để có tín hiệu helpful và harmful; phát lại trace không nuôi được chúng. Thứ tự và mốc từng giai đoạn nằm ở tài liệu Lộ trình — Enterprise Agentic.

**Ngoài phạm vi, thuộc gói platform:** đa tenant thương mại, hạn mức, ba hạng gói, SSO, phân quyền ai được duyệt, xuất audit, giao diện quản trị, hạ tầng bản free.

Trong core, "tenant" chỉ là khóa phân vùng dữ liệu; `global` là phạm vi tri thức chung, không phải một tenant. BPIC 2019 không dùng làm tenant vì log chỉ có 4 mã công ty và một mã chiếm gần hết; nó chỉ dùng để kiểm điều kiện dữ liệu trên loại matching.

**Global trong sản phẩm.** Mỗi khách Pro và Enterprise chạy trên hạ tầng riêng, nên `global` chỉ có hai nguồn. Thứ nhất là gói luật của nhà cung cấp: soạn từ luật công khai như Wabo và từ dữ liệu công khai, phát hành theo phiên bản, mỗi gói một quy trình — cách dự án Sigma phát hành luật phát hiện tấn công cho các tổ chức tự vận hành. Thứ hai là tri thức chung giữa các đơn vị của cùng một khách hàng: chi nhánh, phòng ban, công ty con. Không học từ khách hàng khác; tri thức chỉ đi một chiều từ nhà cung cấp xuống. Cơ chế core không đổi: gói luật nạp vào global qua vai promoter, và mọi luật global vào trial của từng tenant.

**Global ở bản free.** Bản free là bản duy nhất chạy chung hạ tầng, nhiều người dùng trong một cơ sở dữ liệu. Vì chính sách RLS cho mọi tenant đọc hàng `global`, nếu bật nâng phạm vi ở đây thì tri thức của người dùng này lọt sang người dùng khác. Mỗi tài khoản free chỉ có một workspace nên cũng không có đơn vị nào để gộp. Do đó ở bản free, `global` chỉ gồm gói luật của nhà cung cấp và vai promoter bị tắt: cấu hình triển khai bản free không tạo thông tin đăng nhập cho promoter, và gói luật nạp bằng tài khoản triển khai của bạn trước khi mở cho người dùng. Pro và Enterprise mỗi khách một cơ sở dữ liệu riêng nên không bị ảnh hưởng.

Lát cắt coi là xong khi một lệnh duy nhất chạy hết bảy điều kiện thí nghiệm trên bộ chuẩn bán tổng hợp và trên năm đô thị BPIC 2015, in ra bốn chỉ số theo từng tenant kèm khoảng tin cậy và bản ghi lần chạy, và chạy lại lần hai cho đúng kết quả đó.

## Mô hình miền

&#91;embedded content: mô hình miền · 5 vai, 4 tầng memory, 2 bảng cắt ngang\]

Đọc theo chiều mũi tên: Generator đọc từ kho memory và sinh trajectory, ba vai tiếp theo biến nó thành quyết định, và chỉ Applier chạm vào kho. Bốn mũi tên ngang là bốn kiểu dữ liệu có cấu trúc, không phải dict thô — đó là chỗ mypy bắt được lỗi sớm nhất.

## Lược đồ dữ liệu: bất biến nằm trong cơ sở dữ liệu, không nằm trong trí nhớ

Mượn mô hình song thời gian của Graphiti — mỗi fact mang khoảng thời gian nó đúng trong thực tế và khoảng thời gian hệ thống tin nó đúng, mâu thuẫn thì đóng fact cũ chứ không ghi đè ([Zep](https://blog.getzep.com/beyond-static-knowledge-graphs/)) — nhưng lưu trên Postgres, không dùng graph database, để core dựng được bằng một tệp compose và chạy được trong notebook Kaggle.

Toàn bộ thiết kế dưới đây đã chạy thử trên Postgres 16 ngày 3/10/2026 và qua 21/21 phép tấn công; bộ test đó là test tích hợp đầu tiên của dự án.

| Bảng | Tầng | Trường chính | Ai được ghi |
| --- | --- | --- | --- |
| `episode` | Episodic | `tenant_id`, `case_id`, `payload`, `occurred_at`, `ingested_at` | Chỉ `ingestor`, chỉ thêm |
| `fact` | Semantic | `scope`, `canonical_key`, `template`, `activation`, `target`, `condition`, `statement`, `status`, `support`, `confidence`, `valid_during`, `known_during`, `source_episode_ids`, `candidate_id` | `applier` vào scope của tenant hiện hành; `promoter` vào `global` |
| `candidate` | Cắt ngang | `target_scope`, `payload`, `rationale`, `evidence_episode_ids`, `rule_id`, `metrics_at_decision`, `status`, `decided_by`, `rubric_clause` | Curator tạo, Governor ghi quyết định |
| `run` | Cắt ngang | `seed`, `model_id`, `model_revision`, `code_commit`, `config_hash`, `data_hash`, `tokens_in`, `tokens_out`, `wall_time`, `status` | Bộ điều phối |
| event | Cắt ngang | event\_id, run\_id, tenant\_id, actor, action, target, decision, decided\_by, reason, payload\_hash, occurred\_at | Bộ điều phối và ToolGateway, chỉ thêm |
| `skill`, `playbook_bullet` | Procedural, playbook | Như bản thiết kế trước | Giai đoạn 2 |

`status` của fact có ba giá trị: `trial` (chỉ quan sát, không áp), `active`, `retired`. `canonical_key` ghép từ mẫu Declare, hai hoạt động và điều kiện, ví dụ `precedence(Record Goods Receipt, Record Invoice Receipt)`.

Fact sinh từ tài liệu kế thừa khoảng hiệu lực của chính văn bản. Luật Wabo có hiệu lực suốt thời kỳ của BPIC 2015, nên fact trích từ Wabo mang `valid_during` của Wabo. Văn bản thay thế nó — Omgevingswet, từ 2024 — là một tài liệu khác với khoảng hiệu lực khác, không ghi đè lên fact cũ.

Sáu bất biến, mỗi cái có một cơ chế máy chặn:

1. **`episode` và `event` chỉ thêm.** Vai ghi của mỗi bảng chỉ có quyền INSERT và SELECT; không vai nào có UPDATE hay DELETE trên hai bảng này.
2. **Không đọc chéo tenant.** Row-Level Security bật cả `ENABLE` lẫn `FORCE` trên mọi bảng có dữ liệu tenant. Tenant đọc được hàng của mình cộng hàng `global`; chưa đặt tenant thì ra 0 hàng.
3. **Hai đường ghi tách bạch.** `episode` là đầu vào, nạp qua `ingestor`. Tri thức chỉ ghi qua `applier` và `promoter`, và cả hai chỉ áp `candidate` đã có quyết định.
4. **Chỉ `promoter` ghi được `global`.** Chính sách RLS dựa vào tên vai cơ sở dữ liệu, không dựa vào biến phiên — phép thử đã chứng minh biến phiên thì code nào cũng tự bật được.
5. **Không hai fact cùng khóa cùng hiệu lực.** `valid_during` và `known_during` kiểu `tstzrange`, kèm exclusion constraint trên `(scope, canonical_key, valid_during, known_during)`. Thay thế phải đóng fact cũ rồi mới thêm fact mới, trong một giao dịch.
6. **Áp candidate là lũy đẳng.** `candidate_id` là ràng buộc duy nhất trên `fact`; áp lại là không làm gì.

Không vai nào của ứng dụng là superuser hay có `BYPASSRLS`, vì cả hai bỏ qua RLS kể cả khi bật `FORCE`. Core không dùng hàm `SECURITY DEFINER`.

## Hợp đồng vòng học: một vai gọi mô hình, hai vai được ghi

Ba vai của ACE giữ nguyên; thêm Governor để quyết, Applier và Promoter để ghi. Điểm mượn quan trọng nhất từ ACE: Curator chỉ sinh delta, còn việc gộp delta do logic xác định đảm nhiệm, không dùng mô hình ([ACE](https://arxiv.org/abs/2510.04618)).

| Vai | Đầu vào | Đầu ra | Gọi mô hình |
| --- | --- | --- | --- |
| Generator | Một lô case từ `episode` của một tenant | `Trajectory`: trình tự hoạt động thật kèm thuộc tính case | Không, phát lại trace |
| Reflector | Lô trajectory hoặc tài liệu quy trình của tenant, cùng fact hiện hành của tenant và của `global` | `Insight`: ràng buộc Declare đề xuất, kèm case làm bằng chứng | Có, một lần mỗi lô, giải mã có ràng buộc theo JSON schema Declare |
| Curator | Insight, fact hiện hành | `Delta`: `ADD`, `CONFIRM`, `CONTRADICT`, `RETIRE` — thành `Candidate` | Không ở lát cắt này |
| Governor | Candidate, bảng luật, số đo trên `episode` | `Decision`: tự duyệt, cần người duyệt, từ chối, chờ thêm dữ liệu | Không, thuần luật |
| Applier | Candidate đã duyệt cho một tenant | Ghi `fact` vào scope của tenant đó | Không |
| Promoter | Candidate nâng lên `global` đã duyệt | Ghi `fact` vào `global` | Không |

Ở lát cắt này Curator không cần mô hình: dạng canonical làm cho việc so một insight với fact hiện có là phép so khớp chính xác trên `canonical_key`, cộng một bảng cặp mẫu đối nghịch để nhận ra mâu thuẫn trực tiếp.

Sáu bất biến của vòng học:

1. **Chỉ Applier và Promoter được ghi tri thức**, và cả hai chỉ áp candidate đã có quyết định. Cơ sở dữ liệu chặn mọi vai khác.
2. **Không bao giờ viết lại toàn bộ tập fact.** Mọi thay đổi là delta trên từng fact có khóa canonical.
3. **Đầu ra của Reflector luôn đúng lược đồ.** Giải mã có ràng buộc loại lỗi cú pháp; đúng cú pháp chưa có nghĩa là đúng luật, đó là việc của Governor và của phép đo.
4. **Reflector chạy theo lô, có trần đầu ra.** Kích thước lô và số insight tối đa mỗi lô là tham số cấu hình.
5. **Cùng seed, cùng đầu vào, cùng phiên bản mô hình thì ra cùng kết quả**, nhờ bộ nhớ đệm phản hồi.
6. **Mỗi vai là một hàm thuần trên kiểu dữ liệu có cấu trúc của nó.** Không vai nào gọi vai khác; bộ điều phối mỏng nối lại, và sau này thay bằng LangGraph mà không đụng vào các vai.

## Nền móng cho phòng điều khiển: ba thứ làm ngay vì sửa sau thì đắt

Lát cắt tháng 11 chưa có agent thực thi và chưa có giao diện, nhưng đặt sẵn ba nền móng để giai đoạn 2 không phải viết lại lớp tool và không mất log cũ. Cả ba đều nhỏ, không đụng thí nghiệm.

1. **Giao diện `ToolGateway` trong core.** Mọi tool call sau này phải đi qua một cổng duy nhất, trả về một trong bốn quyết định: cho, chặn, hỏi người, để luật quyết — cùng bốn giá trị hook `PreToolUse` của Claude Code dùng. Lát cắt chỉ khai báo giao diện và test hợp đồng với một cổng giả; proxy MCP thật làm ở giai đoạn 2a.
2. **Bảng `event` chỉ thêm.** Mỗi hành động có ai làm, làm gì, quyết định gì, ai quyết, vì sao, thuộc run nào. Ở lát cắt này bảng ghi lần gọi vai và quyết định của Governor; từ giai đoạn 2 ghi thêm từng tool call. Log có cấu trúc hiện có được ghi vào đây, không chỉ ra file.
3. **Quyết định của người dùng thành Candidate.** Mỗi lần duyệt, chặn hay bật sớm là một Candidate đi qua Governor với `decided_by` và `rubric_clause`, không có đường ghi tắt. Đây là nguồn tín hiệu helpful và harmful cho tầng playbook ở giai đoạn 2b.

Core không phụ thuộc AG-UI hay SDK của hãng nào: adapter AG-UI nằm trong platform, adapter agent nằm sau `ToolGateway`. Chuẩn đổi thì chỉ sửa adapter.

## Chính sách cổng duyệt: luật nào khớp đầu tiên thì thắng

Governor nạp một bảng luật có thứ tự, duyệt từ trên xuống, luật đầu tiên khớp thì thắng, không luật nào khớp thì cần người duyệt. Bảng luật là một tệp cấu hình, kiểm bằng Pydantic lúc nạp: điều kiện chỉ được chọn từ danh sách đại lượng và phép so sánh cho trước, không có `eval`. Mọi đại lượng đều đếm được trên `episode` — không điều kiện nào hỏi ý kiến mô hình.

Đã cân nhắc Cedar và OPA. Cedar trả lời câu *ai được làm gì trên tài nguyên nào* và mạnh nhất ở đó; OPA cần thêm một tiến trình chạy riêng. Câu hỏi của Governor là *một thay đổi có đủ bằng chứng chưa*, nên giữ bảng luật nhỏ tự viết. Câu "ai được duyệt" thuộc platform ở giai đoạn 3, và Cedar là ứng viên cho việc đó.

| # | Áp cho | Điều kiện | Quyết định |
| --- | --- | --- | --- |
| 1 | Fact của tenant | Mâu thuẫn trực tiếp một fact `active` cùng tenant | Người duyệt |
| 2 | Ràng buộc mới, từ trace hoặc từ tài liệu | Đúng lược đồ Declare; nếu từ trace thì cận dưới Wilson của độ tin ≥ 0,7 trên trace của chính tenant | Thêm ở trạng thái `trial` |
| 3 | Fact đang `trial` | Xác suất hậu nghiệm Beta để độ tin ≥ 0,7 đạt ≥ 0,95 | Lên `active` |
| 4 | Fact đang `trial` hoặc `active` | Xác suất hậu nghiệm Beta để độ tin ≥ 0,7 rơi dưới 0,05 | `retired`, kèm lý do |
| 5 | Nâng lên `global` | Qua cổng nâng phạm vi, xem dưới | Người duyệt |
| 6 | Fact `global` áp cho một tenant | Luôn luôn | Vào `trial` của tenant đó, tiên nghiệm Beta lấy từ độ tin của luật trong global: độ tin khai trong gói luật, hoặc độ tin trên các đơn vị khác của cùng khách hàng |
| 7 | Ràng buộc có điều kiện thuộc tính | Phần dữ liệu thỏa điều kiện có ít nhất 30 case | Đi tiếp theo luật 2; dưới 30 case thì loại |
| 8 | Fact đang trial | Người duyệt chọn bật sớm, ghi điều khoản rubric | Lên active, ghi decided\_by; luật 4 vẫn gỡ nếu dữ liệu sau đó bác bỏ |
| 9 | Còn lại | — | Chờ thêm dữ liệu |

**Cổng Beta, nói đơn giản.** Mỗi luật ở `trial` có một ước lượng độ tin kèm độ chắc chắn. Ước lượng khởi đầu từ tiên nghiệm — độ tin của luật trong global nếu luật đến từ global, ngược lại là phẳng — với độ mạnh tương đương 4 case. Mỗi trace của tenant cập nhật ước lượng. Luật lên chính thức khi gần như chắc rằng độ tin trên 0,7, và bị gỡ khi gần như chắc rằng không. Không có số trace tối thiểu cố định: luật rõ ràng lên nhanh, luật mập mờ chờ lâu hơn.

Mô phỏng ngày 3/10 trên log có 15% trace nhiễu cho thấy cách này đạt 100% luật đúng, nhanh nhất trong bốn cách đã thử, không áp sai luật nào — kể cả với tenant thiểu số có 40% case làm theo số đông. Ngưỡng cố định trước đây kẹt ở 87%.

**Tiên nghiệm một mình không bao giờ đưa luật lên chính thức.** Độ mạnh tiên nghiệm quá cao thì luật trong gói thành chính thức trước khi tenant có trace nào, kể cả luật sai: mô phỏng 2.000 tenant cho thấy ở độ mạnh 20, luật sai được áp ngay từ đầu và chỉ bị gỡ sau 15 đến 78 trace. Trần an toàn phụ thuộc độ tin khai trong gói: dưới 10,3 ở độ tin 0,95, nhưng chỉ dưới 7,4 ở độ tin 1,0. Vì vậy bất biến kiểm theo từng luật lúc nạp gói: xác suất hậu nghiệm tính từ tiên nghiệm một mình phải dưới ngưỡng 0,95, không thì từ chối nạp cả gói. Độ mạnh mặc định 4 an toàn với mọi độ tin.

**Cổng nâng phạm vi.** Bỏ phiếu đơn thuần — đủ k tenant cùng học được thì nâng — đã bị phép thử bác bỏ: khi các tenant đa số giống nhau, luật của nhóm đa số lọt vào `global` và áp sai cho tenant thiểu số. Hai phương án sống sót, chọn sau khi chạy bộ chuẩn bán tổng hợp và BPIC 2015:

- **Đồng thuận:** chỉ nâng luật không bị dữ liệu của tenant nào vi phạm. `global` nhỏ nhưng an toàn.
- **Phủ quyết:** nâng luật của số đông, mỗi tenant tự loại luật mà dữ liệu của chính nó vi phạm. `global` lớn hơn, cho tenant mới nhiều gợi ý hơn.

Ở dữ liệu mô phỏng hai phương án hòa nhau. Với doanh nghiệp vừa cài và chưa có dữ liệu thì cả hai đều áp sai, nên luật 6 là bắt buộc dù chọn phương án nào.

Các tham số 0,7; 0,95; 0,05; độ mạnh tiên nghiệm 4 và phần tối thiểu 30 case lấy từ mô phỏng, nằm trong tệp cấu hình chính sách và hiệu chỉnh trên phần hiệu chỉnh của BPIC 2015 ở tuần 4. Độ mạnh tiên nghiệm hiệu chỉnh trên ít nhất ba giá trị, và chỉ trong vùng bất biến tiên nghiệm cho phép.

**Mỗi quyết định phải giải thích được.** Governor ghi vào `candidate` số hiệu luật đã khớp và giá trị các đại lượng lúc đánh giá. Chạy lại Governor trên cùng candidate và cùng bảng luật phải ra đúng quyết định cũ.

**Rubric viết trước, không viết sau.** Mỗi quyết định thủ công ghi điều khoản rubric vào `rubric_clause`. Không có điều khoản nào khớp nghĩa là rubric thiếu, phải sửa rubric trước khi duyệt tiếp. Một phần năm số quyết định thủ công được người thứ hai duyệt chéo.

**Giai đoạn 2** thêm luật cho tầng playbook và procedural, giữ nguyên thiết kế đã có: sửa bullet đang `active` luôn cần người duyệt; bullet mới vào `trial` và lên `active` khi helpful trừ harmful ≥ 2; skill qua induction gating — lặp trên ít nhất 5 case, tỉ lệ thành công ≥ 0,9, có ít nhất một postcondition kiểm được bằng code.

## Hợp đồng đánh giá: bảy điều kiện, bốn chỉ số, ground truth không qua mô hình

**Từ vựng canonical là Declare.** Declare là ngôn ngữ ràng buộc khai báo của ngành process mining, với các mẫu như Response(a,b) — a xảy ra thì b sẽ xảy ra sau — và Precedence(a,b) — b chỉ xảy ra khi a đã xảy ra trước ([van der Aalst](https://www.vdaalst.com/publications/p669.pdf)). Luật phụ thuộc thuộc tính case, như loại matching trong BPIC 2019, dùng điều kiện kiểu MP-Declare ([Dumas](https://kodu.ut.ee/~dumas/pubs/bpm2018datarules.pdf)).

**Khám phá Declare tự viết trong core, không dùng pm4py.** pm4py theo giấy phép AGPL-3.0; Declare4Py không khai báo giấy phép và phụ thuộc pm4py. Core tự viết từ định nghĩa trong bài báo, không chép mã của hai thư viện đó. pm4py chỉ chạy trong một môi trường đối chiếu riêng, không nằm trong phụ thuộc của core, để kiểm bản tự viết: phép thử ngày 3/10 cho kết quả trùng khớp 10/10 lần.

**Khám phá theo chỉ mục vị trí.** Mỗi log BPIC 2015 có 356 đến 410 loại hoạt động, tức khoảng 158 nghìn cặp mỗi lần khám phá; duyệt thẳng mất khoảng 6 phút mỗi lần, trong khi đánh giá cần hàng nghìn lần. Hoạt động xuất hiện ít hơn support × confidence phần case bị bỏ trước, vì không thể thuộc luật nào. Với mỗi trace lưu vị trí đầu và cuối của mỗi hoạt động: Response(a,b) đúng khi b xuất hiện sau lần a cuối cùng, Precedence(a,b) đúng khi lần a đầu tiên trước lần b đầu tiên. Ngữ nghĩa này suy từ định nghĩa hình thức, đúng quy tắc clean room. Phép thử ngày 3/10 trên log giả cỡ đô thị 1: 9,5 giây khi không lọc trước, cùng tập luật với bản duyệt thẳng.

**Ground truth.** Đáp án không bao giờ được sinh bằng chính một điều kiện đang được so. Trên bộ chuẩn bán tổng hợp, đáp án là luật đã cài vào bộ sinh. Trên BPIC 2015, đáp án là kết quả khám phá Declare trên phần đo của tenant — không phải phần học — với ngưỡng support và confidence cố định, dùng chung cho cả bảy điều kiện. Phép thử ngày 3/10 cho thấy đáp án lấy từ phần học chấm điều kiện chỉ-Declare hoàn hảo trong khi sai thật là 3–4%. Đáp án từ phần đo có nhiễu riêng nên số tuyệt đối hơi bi quan, như nhau cho mọi điều kiện: báo cáo so sánh bằng chênh lệch. Đối chiếu fact với đáp án là so khớp chính xác trên `canonical_key`.

**Phép chia.** Mỗi đô thị chia theo thời điểm bắt đầu case: 60% học, 20% hiệu chỉnh, 20% đo — chia ngẫu nhiên thì tương lai lọt vào tập học, và phép thử cho thấy nó báo vi phạm bằng một nửa thực tế khi quy trình đổi giữa chừng. Mọi tham số chỉ chỉnh trên phần hiệu chỉnh hoặc trên bộ chuẩn bán tổng hợp. Trước lần đầu chạm phần đo, cấu hình khóa bằng commit; bộ điều phối từ chối chạy trên phần đo nếu `config_hash` khác bản đã khóa. Phần đo chạy một lần cho kết quả công bố.

**Bảy điều kiện thí nghiệm**, chạy trên bộ chuẩn bán tổng hợp và trên năm đô thị của BPIC 2015, cùng phép chia:

| Điều kiện | Cách tổ chức tri thức | Vai trò trong thí nghiệm |
| --- | --- | --- |
| Chỉ Declare | Khám phá Declare trên trace của tenant, không mô hình ngôn ngữ | Baseline bắt buộc, so ở cùng số trace trên đường cong khởi động lạnh: nếu LLM không thắng điều kiện này ở 0, 5 và 10 trace, phần LLM không có lý do tồn tại |
| Cách ly | Mỗi tenant tự học, không có `global` | Cận an toàn, tốc độ học chậm nhất |
| Gộp chung | Một kho chung cho mọi tenant | Cách làm ngây thơ; ở mô phỏng nó mất luật hoặc áp sai tùy ngưỡng |
| Phân tầng bỏ phiếu | `global` nâng khi đủ k tenant | Ablation: thiết kế đã bị bác bỏ, giữ lại để chứng minh vì sao |
| Phân tầng đồng thuận | `global` chỉ chứa luật không tenant nào vi phạm | Ứng viên |
| Phân tầng phủ quyết | `global` của số đông, mỗi tenant tự loại luật mà dữ liệu của nó vi phạm | Ứng viên |
| Tài liệu cộng dữ liệu | Ứng viên tốt hơn trong hai cái trên, cộng luật LLM trích từ luật Wabo vào `global`, vào `trial` của từng tenant ngay ngày đầu | Đo đúng giá trị riêng của LLM: rút ngắn đường cong khởi động lạnh bao nhiêu |

**Bài đo riêng cho việc trích luật từ văn bản.** F1 theo từng mẫu Declare trên bộ 104 câu mô tả quy trình đã dùng trong nghiên cứu trước, nơi GPT-4 đạt 0,79 ([arXiv 2307.09923](https://arxiv.org/pdf/2307.09923)). Con số này cho biết mô hình 8B của dự án kém GPT-4 bao xa, và từ đó tính được bao nhiêu luật từ tài liệu sẽ bị cổng loại. Bộ 104 câu chỉ tải về lúc đo, không đóng gói vào kho của dự án, vì kho gốc không có tệp giấy phép.

**Bộ chuẩn bán tổng hợp.** Khám phá mô hình quy trình của từng đô thị BPIC 2015, rồi sinh nhiều tenant giả bằng cách đổi có kiểm soát một số luật thứ tự. Mức nhiễu, tỉ lệ case dở dang và số case lấy từ log thật, không tự đặt. Biết trước luật nào khác ở tenant nào nên có ground truth tuyệt đối, và rút được nhiều bộ chuẩn độc lập để tính khoảng tin cậy với số tenant tùy ý. Phép thử ngày 3/10 với 12 lần rút mỗi ô: ở 5 tenant, khoảng tin cậy của chênh lệch giữa gộp chung và phân tầng vẫn loại trừ 0 xa. Bộ sinh nhận seed và tham số riêng, cả hai vào `data_hash`.

**Nghiệm thu bộ chuẩn.** Bộ sinh phải có bước tùy chọn với tỉ lệ bỏ qua lấy từ log thật, và khám phá trên 300 trace không được đúng tuyệt đối so với đáp án. Bộ chuẩn mà phương pháp nào cũng đạt trần thì không phân biệt được gì — bộ sinh tám hoạt động thứ tự cố định dùng ở đợt 2 đã đúng tuyệt đối từ 10 trace.

**BPIC 2015 thật.** Năm log có 1.199, 832, 1.409, 1.053 và 1.156 case, từ 44 đến 60 nghìn sự kiện mỗi log, đã kiểm trên nguồn gốc. Khoảng tin cậy 95% tính bằng bootstrap trên case. Log tải từ nguồn gốc lúc chạy, không đóng gói vào kho.

**Tài liệu cho điều kiện thứ bảy.** Luật Wabo — luật cấp phép môi trường Hà Lan có hiệu lực suốt thời kỳ của BPIC 2015 — là tài liệu của phạm vi global, giống nhau cho cả năm đô thị. Không tự viết tài liệu cho từng đô thị, vì viết dựa trên log là nhét đáp án vào đề. Gắn khái niệm trong văn bản tiếng Hà Lan với tên hoạt động trong log là một bước có kiểm: gắn sai thì luật sai, và cổng Beta loại luật sai — nên gắn sai chỉ tốn công, không làm hệ áp sai.

**Giới hạn đã biết.** Phần lớn luật trong Wabo là luật thời hạn, như quyết trong 8 tuần. Từ vựng hiện chỉ có điều kiện trên thuộc tính phân loại, nên từ Wabo chỉ trích luật thứ tự, như công bố dự thảo trước quyết định cuối. JSON schema của Reflector chỉ cho các mẫu trong từ vựng, nên mô hình không thể sinh luật thời hạn. Điều kiện thời gian kiểu MP-Declare vào danh sách để sau.

**Bốn chỉ số, theo từng tenant và từng điều kiện**, luôn báo cùng nhau, mỗi chỉ số kèm khoảng tin cậy 95%. Không bao giờ báo tỉ lệ vi phạm một mình: phép thử ngày 3/10 cho thấy gộp chung hỏng chủ yếu bằng cách lặng lẽ mất luật — recall kém 4 đến 11 điểm trong khi tỉ lệ vi phạm chỉ kém 0,2 đến 1 điểm.

| Chỉ số | Định nghĩa | Bắt được gì |
| --- | --- | --- |
| Precision | Phần fact `active` của tenant có trong tập tham chiếu của nó | Học sai |
| Recall | Phần tập tham chiếu của tenant có trong fact `active` của nó | Mất tri thức, như gộp chung ở ngưỡng cao |
| Tỉ lệ vi phạm | Phần fact `active` bị trace thật trên tập đo của tenant vi phạm quá 10% | Hậu quả thật của việc áp luật |
| Negative transfer | Phần tỉ lệ vi phạm đến từ fact có nguồn gốc ngoài tenant — từ `global` hoặc từ kho gộp | Nỗi lo chính của khách hàng |

Thêm một đường cong khởi động lạnh: cho trace của một tenant mới đến dần, đo bốn chỉ số ở 0, 5, 10, 20, 40 trace. Ở 0 trace chưa luật nào active, nên điểm này đo trên luật trial ở chế độ giám sát và ghi rõ như vậy. Đường cong này trả lời câu khách hàng sẽ hỏi trước tiên: bản basic vừa cài thì làm được gì, và bao lâu thì khớp với doanh nghiệp.

**Chạy lại phải ra đúng kết quả cũ.** Bộ nhớ đệm phản hồi lưu mọi lần gọi mô hình. Khóa đệm gồm băm của prompt, `model_revision`, tham số giải mã và băm JSON schema đầu ra — mọi thứ ảnh hưởng tới kết quả đều phải nằm trong khóa, nếu không thì đổi schema mà vẫn đọc nhầm kết quả cũ.

**Điều kiện tái lập, phải đúng cả sáu:** cùng `seed`, cùng `model_id` và `model_revision`, cùng `code_commit`, cùng `config_hash`, cùng `data_hash`, và bộ nhớ đệm còn nguyên. Thiếu một thì `run` ghi *không tái lập được*, không im lặng cho qua. `data_hash` băm cả tệp log, tham số chia, danh sách tenant, và seed cùng tham số của bộ sinh bán tổng hợp.

## Yêu cầu phi chức năng: quy ước nào không kiểm được bằng máy thì không tính

Mọi mục dưới đây đều có một cách kiểm tự động đi kèm.

| Yêu cầu | Cách thực hiện | Cách kiểm |
| --- | --- | --- |
| Ranh giới gói | `core` không bao giờ import `platform` | import-linter trong CI, mã thoát khác 0 thì chặn merge |
| Gọi mô hình | Chỉ qua một adapter với giao diện `LanguageModel` | import-linter cấm SDK mô hình ngoài thư mục adapter; bắt buộc `include_external_packages = True`, thiếu dòng này luật về thư viện bên ngoài không chạy |
| Truy cập dữ liệu | Chỉ qua module repository | import-linter cấm driver cơ sở dữ liệu ngoài `repositories` |
| Giấy phép phụ thuộc | Core không phụ thuộc thư viện AGPL hay không có giấy phép | pip-licenses trong CI, khớp một phần theo từ khóa AGPL, GPL và UNKNOWN vì mỗi gói khai một kiểu; chạy trần, không qua ống dẫn, vì ống dẫn nuốt mã thoát |
| Cách ly tenant | RLS trong cơ sở dữ liệu | Bộ test tích hợp chạy dưới đúng vai ứng dụng, không bao giờ dưới tài khoản quản trị |
| Bất biến dữ liệu | Quyền theo vai, exclusion constraint, ràng buộc duy nhất | Cùng bộ test tích hợp: 21 phép tấn công phải bị chặn |
| Kiểu dữ liệu | Chú thích kiểu đầy đủ; `Trajectory`, `Insight`, `Delta`, `Candidate`, `Decision` là kiểu có khai báo | mypy strict trên `core` |
| Cấu hình | Một đối tượng settings có kiểu, nạp từ một tệp | Bước CI tìm os.environ và getenv ngoài module settings; import-linter không chặn được thuộc tính nên không dùng nó cho việc này |
| Định dạng và lint | ruff, ruff format | CI gate |
| Gói luật | Tiên nghiệm một mình không đưa luật nào lên chính thức, kiểm theo độ tin của từng luật | Validator Pydantic từ chối nạp gói; unit test: gói có luật độ tin 1,0 với độ mạnh 8 phải bị từ chối |
| Dữ liệu bên thứ ba | Log BPIC và bộ 104 câu tải lúc chạy, không nằm trong kho | Bước CI chặn tệp .xes, .csv và .gz trong kho ngoài thư mục fixture của test |
| Hiệu năng khám phá | Lọc trước theo support × confidence, chỉ mục vị trí đầu và cuối | Test CI: log giả cỡ đô thị 1, không lọc trước, dưới 30 giây trên CPU; cùng tập luật với bản duyệt thẳng trên lát nhỏ |
| Phần đo khóa | Cấu hình khóa bằng commit trước khi chạm phần đo | Test tích hợp: bộ điều phối từ chối run trên phần đo khi config\_hash khác bản đã khóa |
| Cổng tool | Mọi tool call đi qua ToolGateway; quyết định của người dùng chỉ vào qua Candidate | import-linter cấm client MCP và SDK agent ngoài thư mục gateway và adapter; test hợp đồng với cổng giả; test bảng event từ chối UPDATE và DELETE |
| Độ phủ | Unit test cho từng vai với phản hồi mô hình ghi sẵn; một test đầu cuối trên tenant giả | Ngưỡng 85% trên `core`, áp từ commit đầu tiên |

**Chạy tiếp được sau khi đứt.** Mỗi N case ghi điểm kiểm tra gồm fact, candidate đang chờ, con trỏ case và bộ nhớ đệm phản hồi, rồi đẩy sang R2. Checkpoint không bao giờ chỉ nằm trên Kaggle. Khởi động lại thì chạy tiếp từ con trỏ.

**Trần token kiểm trước khi gọi.** Chạm trần thì ghi điểm kiểm tra, đóng `run` với trạng thái `budget_exceeded`, thoát với mã lỗi rõ ràng.

**Lỗi không được nuốt.** Gọi mô hình hỏng thì thử lại có giãn cách; hết lượt thì đánh dấu cả lô thất bại trong `run` và dừng.

**Log có cấu trúc, một sự kiện cho mỗi lần gọi vai**, mang `run_id`, `tenant_id`, danh sách `candidate_id`, số token vào và ra. Định dạng cố định từ đầu vì đây là nguồn cho phần audit về sau.

**Hai backend sau một adapter `LanguageModel`.** Vòng phát triển hằng ngày chạy một mô hình nhỏ trên CPU, không tiêu hạn mức GPU nào; Kaggle chỉ cho những lần chạy đầy đủ. Hai backend phải qua cùng bộ test hợp đồng của adapter.

**Clean room cho phần khám phá Declare.** Viết từ định nghĩa hình thức trong bài báo, không mở mã nguồn pm4py; một bản quyết định kiến trúc ghi nguồn của từng mẫu; pm4py chỉ chạy như bộ đối chiếu riêng ngoài kho.

## Rủi ro còn lại: cả mười bảy ở mức nhẹ

Cả mười bảy rủi ro đã có giải pháp được duyệt ngày 3/10: R1 đến R9 ở đợt 1, R10 đến R12 ở đợt 2, R13 đến R17 ở đợt 3 — đợt này tìm ra năm rủi ro mà cổng lần 4 bỏ sót, trong đó R13 ở mức nặng. Phần lớn giải pháp có bằng chứng chạy thử. Sau khi vá, không còn rủi ro nào ở mức trung bình hay nặng: phần còn lại không làm sai kết luận của dự án, có dấu hiệu theo dõi rõ, và có sẵn hướng xử lý khi dấu hiệu xuất hiện.

| # | Rủi ro | Giải pháp đã duyệt | Mức còn lại | Dấu hiệu theo dõi | Khi nào kiểm |
| --- | --- | --- | --- | --- | --- |
| R1 | LLM không thêm giá trị | Đường vào từ tài liệu; điều kiện chỉ-Declare làm baseline | Nhẹ — cả hai kết quả đều có kế hoạch, sản phẩm vẫn chạy bằng khám phá Declare | Điều kiện 7 không rút ngắn đường cong khởi động lạnh | Tuần 3 |
| R2 | Dữ liệu không đủ khác biệt | BPIC 2015; kết luận chính dựa vào bộ chuẩn bán tổng hợp | Nhẹ — khác biệt ít là một kết quả, không làm sai kết luận | Bảng hồ sơ năm đô thị | Tuần 1 |
| R3 | Ngưỡng sai trên log thật | Cổng thống kê Beta | Nhẹ — đã thử trên log nhiễu 15% | Luật trial kẹt quá 80 trace; hiệu chỉnh ba độ mạnh tiên nghiệm | Tuần 4 |
| R4 | Điều kiện dữ liệu khó | Chỉ thuộc tính phân loại, phần ≥ 30 case, cận dưới Wilson | Nhẹ | Thuộc tính phân loại nào có trong BPIC 2015; số luật có điều kiện tăng vọt | Tuần 1 |
| R5 | Mô hình sai nghĩa | Mọi ràng buộc qua cổng Beta trên dữ liệu | Nhẹ — sai nghĩa tốn chi phí, không làm hệ áp sai | F1 trên 104 câu thấp xa 0,79 | Tuần 2 |
| R6 | Giấy phép | Clean room, CI chặn giấy phép, dữ liệu bên thứ ba không nằm trong kho | Nhẹ | CI giấy phép báo đỏ; hỏi người có chuyên môn trước bản thương mại đầu tiên | Trước giai đoạn 4 |
| R7 | Phình phạm vi | Khẩu phần cố định, cầu dao 50% | Nhẹ | Chu kỳ vượt 50% khẩu phần | Liên tục |
| R8 | Hạn mức GPU | Backend CPU cho phát triển, bộ đệm phản hồi, checkpoint lên R2, đo token trước khi chạy | Nhẹ | Hết hạn mức trước khi xong một điều kiện; bạn đọc điều khoản Kaggle | Tuần 2 |
| R9 | Tự duyệt | Duyệt chéo mù, kappa ≥ 0,61, rubric khóa trước | Nhẹ | Kappa dưới 0,61 | Tuần 4 |
| R10 | BPIC 2015 không kèm tài liệu quy trình | Luật Wabo làm tài liệu global, đúng thời kỳ log; F1 riêng trên 104 câu | Nhẹ — gắn sai bị cổng loại, xấu nhất là kết quả âm vẫn công bố được | Tỉ lệ luật từ Wabo bị cổng loại | Tuần 2 |
| R11 | Năm tenant yếu về thống kê | Bộ chuẩn bán tổng hợp cho số tenant tùy ý; bootstrap trên case cho BPIC 2015 | Nhẹ — kết luận không còn đặt lên một lần rút | Khoảng tin cậy chứa 0; tham số bộ sinh lệch log thật | Tuần 3 |
| R12 | Tiên nghiệm là dòng chảy tri thức giữa tenant, mà khách tự chạy hạ tầng | Global = gói luật nhà cung cấp + đơn vị cùng khách hàng; bất biến tiên nghiệm kiểm lúc nạp | Nhẹ — không còn lời hứa cần dữ liệu khách khác | Luật trong gói bị tenant gỡ nhiều | Trước giai đoạn 3 |
| R13 | Đáp án trên dữ liệu thật sinh bằng chính điều kiện chỉ-Declare | Đáp án từ phần đo, chung cho mọi điều kiện; so LLM ở cùng số trace; bộ chuẩn phải đủ khó | Nhẹ — số tuyệt đối hơi bi quan như nhau cho mọi điều kiện; so bằng chênh lệch | Bộ chuẩn không qua nghiệm thu; một điều kiện đạt 1,00 trên dữ liệu thật | Tuần 3 |
| R14 | Chỉnh tham số trên dữ liệu dùng để đo; chia ngẫu nhiên | Chia theo thời gian 60/20/20; cấu hình khóa bằng commit trước khi chạm phần đo | Nhẹ — còn lại là quy trình đổi ngay trong phần đo | Phân phối theo thời gian trong bảng hồ sơ | Tuần 1 |
| R15 | Khám phá quá chậm trên log 356–410 hoạt động | Lọc trước, chỉ mục vị trí, test hiệu năng trong CI | Nhẹ — xấu nhất 9,5 giây mỗi lần | Số hoạt động còn lại sau lọc trên log thật; test CI quá 30 giây | Tuần 1 |
| R16 | Lời hứa ngày đầu mâu thuẫn bất biến tiên nghiệm | Ngày đầu chạy giám sát; người duyệt bật sớm có rubric (luật 8) | Nhẹ — bật sớm sai có vết, dữ liệu gỡ được | Luật bật sớm bị luật 4 gỡ | Tuần 4 |
| R17 | Luật thời hạn trong Wabo không diễn đạt được | Giới hạn đã biết; schema Reflector chặn; vào danh sách để sau | Nhẹ — điều kiện thứ bảy ít luật hơn, đã nằm trong tình huống xấu nhất của R10 | Số luật thứ tự trích được từ Wabo | Tuần 2 |

Lý do, bằng chứng chạy thử và cách đánh giá mức còn lại của từng giải pháp nằm ở tab Giải pháp rủi ro; các quyết định đã được đưa vào các mục tương ứng của spec này.

**Thứ cố tình không tối ưu ở lát cắt này:** chất lượng truy hồi, mô hình embedding, tốc độ truy vấn, giao diện. Làm cho đúng trước, làm cho nhanh sau — nhưng chỉ khi ranh giới module đã đúng.

## Cổng duyệt spec: lần chạy thứ năm, ngày 3/10 — qua, sang bước plan

Cổng chạy lại sau khi áp đợt 3 (G8 đến G11). Cổng lần 4 đã báo không còn rủi ro nặng, nhưng đọc lại từ đầu tìm thấy R13 ở mức nặng — một lỗi mà mười hai câu cũ không hỏi tới. Câu 13 thêm vào để hỏi đúng loại lỗi đó.

| # | Câu hỏi | Kết quả |
| --- | --- | --- |
| 1 | Có gì của platform lọt vào core? | Đạt |
| 2 | Có đường ghi tri thức nào vòng qua candidate? | Đạt — luật từ tài liệu cũng đi qua candidate và vào `trial` |
| 3 | Có vai nào gọi thẳng vai khác? | Đạt |
| 4 | Mọi điều kiện luật đều đo bằng số? | Đạt — cổng Beta và Wilson đều là phép tính trên số đếm |
| 5 | Ground truth có đi qua mô hình? | Đạt |
| 6 | Có nguồn ngẫu nhiên ngoài seed? | Đạt — bộ sinh bán tổng hợp nhận seed, seed vào data\_hash |
| 7 | Mục phi chức năng nào CI không kiểm được? | Đạt |
| 8 | Rủi ro nào chưa có hạn kiểm? | Đạt — R1 đến R17 đều có |
| 9 | Mỗi chỉ số có cách nào ra khác 0? | Đạt |
| 10 | Phụ thuộc nào mang giấy phép không dùng được? | Đạt |
| 11 | **Mỗi dữ kiện về dữ liệu đã được kiểm trên nguồn gốc, hay chỉ dựa vào mô tả và trí nhớ?** | Đạt — số case năm đô thị đã kiểm trên nguồn gốc; tài liệu cho điều kiện thứ bảy là luật Wabo; mức khác biệt về luật chưa kiểm được nhưng kết luận không còn dựa vào nó, và nó là task đầu tiên của plan |
| 12 | Còn rủi ro nào ở mức trung bình hoặc nặng? | Đạt — cả mười bảy rủi ro đều ở mức nhẹ, mỗi cái có dấu hiệu theo dõi và hạn kiểm |
| 13 | Có điều kiện nào được chấm bằng đáp án sinh từ chính nó, hoặc tham số nào chỉnh trên dữ liệu dùng để đo? | Đạt — đáp án từ phần đo hoặc từ bộ sinh; tham số chỉ chỉnh trên phần hiệu chỉnh; phần đo khóa bằng config\_hash |
| 14 | Có đường nào gọi tool hoặc ghi quyết định của người dùng mà vòng qua ToolGateway, Candidate hay bảng event? | Đạt — import-linter chặn client tool ngoài gateway; quyết định chỉ vào qua Candidate; event chỉ thêm |

Cổng qua đủ mười bốn câu; câu 14 thêm ngày 3/10 khi gộp phòng điều khiển vào dự án. Bảng hồ sơ năm đô thị vẫn là task đầu tiên của plan, không lồng vào giữa; nó cũng trả lời phần chưa kiểm của R14 và R15.

**Sang bước plan với ba điểm quyết định:**

1. Tuần 1, bảng hồ sơ năm đô thị: năm đô thị khác nhau ít không phải lý do dừng mà là một kết quả cần báo cáo. Chỉ dừng và quay lại spec nếu log hỏng hoặc thiếu trường bắt buộc.
2. Tuần 2, luật Wabo cho điều kiện thứ bảy: nếu cổng loại gần hết luật trích từ văn bản, điều kiện đó báo kết quả âm và vẫn công bố, giữ bài đo F1 riêng — không tự viết tài liệu từ log.
3. Tuần 3, baseline: nếu ở 0, 5 và 10 trace điều kiện tài liệu cộng dữ liệu không hơn chỉ-Declare, phần LLM của lát cắt thu về bài đo trích luật từ văn bản, và tuyên bố của dự án đổi theo.
