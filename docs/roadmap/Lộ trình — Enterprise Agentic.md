# Lộ trình — Enterprise Agentic

Oct 3, 2026 · @ngoc han

## Tóm tắt

**Đích đến ngày 27/6/2027:** một nền tảng mà doanh nghiệp giao việc cho đội agent theo vai, nhìn thấy và điều khiển được từng hành động của chúng, còn hệ thống tự học cách doanh nghiệp đó vận hành — từ log quy trình và từ chính những lần giám đốc duyệt hay chặn. Bản Free chạy trên hạ tầng 0 đồng của bạn; Pro và Enterprise khách tự vận hành, tự lo LLM.

Lộ trình gồm 38 tuần, từ 5/10/2026 đến 27/6/2027, chia sáu giai đoạn và năm cổng. Mỗi giai đoạn có khẩu phần cố định: chậm thì cắt phạm vi theo thứ tự đã định, không dời mốc.

Lộ trình này thay cho hình "lộ trình 9 tháng · 4 giai đoạn" trong tài liệu đề xuất: hình đó vẽ trước khi có spec, chưa có phòng điều khiển, và đánh số giai đoạn khác spec.

## Sản phẩm cuối cùng

Ba lớp, một cổng: mọi tool call của mọi agent đi qua `ToolGateway`, nên cùng một chỗ vừa cho giám đốc thấy và chặn, vừa ghi log cho vòng học.

&#91;embedded content: kiến trúc sản phẩm cuối cùng · 3 lớp, 1 cổng tool\]

Log đi từ cổng vào bộ nhớ rồi vào vòng học; mỗi lần duyệt hay chặn là một Candidate cho Governor. Core không import platform và không phụ thuộc AG-UI.

| Chuẩn | Dùng cho | Nằm ở đâu |
| --- | --- | --- |
| [MCP](https://modelcontextprotocol.io/specification/2025-11-25/basic/index.md) | Agent gọi tool | `ToolGateway` trong core |
| [AG-UI](https://docs.ag-ui.com/introduction) | Agent nói chuyện với giao diện | Adapter trong platform |
| [Claude Code hooks](https://code.claude.com/docs/en/hooks) | Chặn và duyệt từng tool call của Claude | Adapter agent, giai đoạn 2b |
| [OpenAI Agents SDK](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals) | Dừng chờ duyệt, chạy tiếp | Adapter agent, giai đoạn 2a |
| Declare | Từ vựng luật quy trình | Core |

## Nguyên tắc lập lộ trình

Mốc cố định, phạm vi co giãn: đây là cách duy nhất một người làm kịp 38 tuần mà không để nợ kỹ thuật.

1. **Khẩu phần cố định, theo Shape Up.** Mỗi giai đoạn có số tuần chốt trước. Đến 50% thời gian mà chưa xong 50% việc cốt lõi thì cầu dao nhảy: cắt phạm vi ngay, không kéo dài.
2. **Tuần nghỉ giữa các giai đoạn.** Không viết tính năng mới: sửa lỗi, trả nợ kỹ thuật vừa phát sinh, review chéo, lập plan giai đoạn sau.
3. **Cổng cuối mỗi giai đoạn đo bằng số hoặc bằng phép thử máy chạy được.** Không đạt thì giai đoạn sau chỉ được làm phần không phụ thuộc vào nó.
4. **Quy trình mỗi giai đoạn: spec, rồi plan, rồi code.** Spec qua cổng 13 câu, plan chia thành plan con và task, mỗi task có review. Sai ở bước nào thì quay lại bước đó.
5. **Nền móng làm sớm nếu rẻ bây giờ mà đắt về sau.** Giao diện `ToolGateway`, bảng sự kiện chỉ thêm, quyết định của người dùng thành Candidate — cả ba vào giai đoạn 1 dù chưa có agent thực thi.
6. **Core không phụ thuộc vào chuẩn giao diện.** AG-UI, MCP nằm sau adapter; chuẩn đổi thì chỉ sửa adapter.
7. **Thứ tự cắt khi chậm đã định trước** (mục Rủi ro của lộ trình). Không quyết định cắt gì vào lúc đang gấp.

## Toàn cảnh

Năm cổng rơi vào 29/11/2026, 17/1, 14/3, 30/5 và 27/6/2027; giai đoạn nghiên cứu (viền đứt) là phần bị cắt đầu tiên nếu chậm.

&#91;embedded content: lộ trình 38 tuần · 6 giai đoạn, 5 cổng\]

| Giai đoạn | (b) Điều khiển | (c) Lưu vết và bàn bạc | Cơ chế học |
| --- | --- | --- | --- |
| 1 | Khai báo `ToolGateway` | Bảng sự kiện chỉ thêm; quyết định người dùng thành Candidate | Episodic, semantic, sáu vai |
| 2a | Proxy MCP có quyền chặn; tạm dừng, dừng hẳn, trần ngân sách; adapter OpenAI | Log mỗi tool call; phát lại bằng dòng lệnh | Agent thực thi trên AppWorld |
| 2b | Adapter Claude; giao diện tối thiểu | Duyệt/chặn thành helpful/harmful; phát lại trong giao diện | Playbook, procedural, skill |
| Nghiên cứu | — | Chính sách cuộc họp, thí nghiệm có baseline | — |
| 3 | Phân vai duyệt, phòng điều khiển đầy đủ | Xuất audit; bản Free phát lại phiên | Đa tenant, hạn mức |
| 4 | — | — | Chạy thử trên log doanh nghiệp thật |

## Giai đoạn 1 — Lõi học (5/10 – 29/11/2026, 8 tuần)

Chứng minh hệ học đúng luật riêng của từng tổ chức mà không nhiễm luật người khác, và đặt sẵn ba nền móng cho phòng điều khiển. Phạm vi đúng như spec đã qua cổng lần 5; chưa có agent thực thi, chưa có giao diện.

| Tuần | Việc chính | Ra được gì |
| --- | --- | --- |
| 1 · 5–11/10 | Repo và CI đủ cổng (giấy phép, import-linter, mypy strict, ruff, độ phủ); lược đồ Postgres với 21 phép tấn công, thêm bảng sự kiện chỉ thêm; bảng hồ sơ năm đô thị; chia thời gian 60/20/20; đọc điều khoản Kaggle | Luật dừng tuần 1: chỉ dừng nếu log hỏng |
| 2 · 12–18/10 | Khám phá Declare theo chỉ mục, test hiệu năng, đối chiếu pm4py ngoài kho; bộ sinh bán tổng hợp qua nghiệm thu; Reflector trên backend CPU; F1 trên 104 câu | Bài đo F1, bộ chuẩn đủ khó |
| 3 · 19–25/10 | Curator, Governor (9 luật, cổng Beta, Wilson), Applier, Promoter; baseline chỉ-Declare và đường cong khởi động lạnh | Baseline — không có số này thì không đi tiếp |
| 4 · 26/10–1/11 | Trích luật từ Wabo; quyết định của người dùng thành Candidate có rubric; hiệu chỉnh tham số trên phần hiệu chỉnh; khóa rubric, bắt đầu duyệt chéo mù | **Kiểm cầu dao 50%** cuối tuần này |
| 5 · 2–8/11 | Bộ điều phối; bảy điều kiện trên bộ chuẩn bán tổng hợp; checkpoint lên R2; bộ nhớ đệm phản hồi; khai báo `ToolGateway` kèm test hợp đồng | Kết luận về thiết kế |
| 6 · 9–15/11 | Chạy đầy đủ trên Kaggle; sửa lỗi từ bảy điều kiện | Số liệu trên phần hiệu chỉnh |
| 7 · 16–22/11 | Khóa cấu hình bằng commit; chạy phần đo BPIC 2015 một lần; chạy lại để kiểm tái lập | Kết quả công bố được |
| 8 · 23–29/11 | Báo cáo kết quả, bản demo chạy một lệnh; tuần đệm | Cổng 1 |

**Cổng 1 — 29/11/2026.** Một lệnh chạy bảy điều kiện trên cả hai nguồn dữ liệu, in bốn chỉ số kèm khoảng tin cậy và bản ghi lần chạy, chạy lại ra đúng kết quả đó; 21 phép tấn công bị chặn; CI xanh; ba nền móng có test.

**Tuần nghỉ 30/11 – 6/12:** trả nợ kỹ thuật, viết spec giai đoạn 2a và cho qua cổng spec.

**Cắt khi chậm, theo thứ tự:** điều kiện 7 thu về bài đo F1 → bỏ phần điều kiện dữ liệu trên BPIC 2019 → giảm số lần rút bootstrap. Không bao giờ cắt: baseline, tái lập, các cổng CI.

## Giai đoạn 2 — Agent thực thi và phòng điều khiển (7/12/2026 – 14/3/2027)

Agent bắt đầu làm việc thật, mọi tool call đi qua một cổng có quyền chặn, và mỗi lần duyệt hay chặn trở thành tín hiệu học. Chia hai nửa để cổng tool có trước khi có bất cứ thứ gì dựa vào nó.

Môi trường là [AppWorld](https://alphaxiv.org/benchmarks/allen-institute-for-ai/appworld): 9 ứng dụng thường ngày, 457 API, 750 task, chấm bằng unit test kiểm thay đổi trong cơ sở dữ liệu — nên thành công đo bằng máy, không nhờ mô hình chấm. Giấy phép của AppWorld chưa kiểm, phải đọc trong tuần nghỉ trước 2a.

### 2a — Cổng tool và điều khiển (7/12/2026 – 17/1/2027, 6 tuần)

- **Agent chạy trên AppWorld** với mô hình mở 8B trên Kaggle qua endpoint tương thích OpenAI — 0 đồng. Generator thôi phát lại trace, bắt đầu gọi mô hình thật.
- **`ToolGateway` thành proxy MCP.** API của AppWorld bọc thành tool MCP nằm sau proxy. Mỗi call nhận một trong bốn quyết định: cho, chặn, hỏi người, để luật quyết — cùng bốn giá trị mà hook `PreToolUse` của Claude Code dùng, nên adapter sau này khớp thẳng.
- **Adapter A: runtime tương thích OpenAI.** OpenAI Agents SDK đã có sẵn cơ chế dừng chờ duyệt: tool đánh dấu cần duyệt thì lần chạy dừng, trả về trạng thái chạy tiếp được sau khi duyệt.
- **Nút tạm dừng, dừng hẳn, trần ngân sách** là lệnh đi qua cùng cổng, có trong log.
- **Log mỗi tool call:** ai gọi, tham số đã băm, quyết định, ai quyết, lý do. Phát lại một phiên từ log bằng dòng lệnh.

**Cổng 2 — 17/1/2027.** Agent cố gọi tool không qua cổng thì thất bại (có test); chặn được một call giữa chừng; dừng hẳn và trần ngân sách hoạt động; phát lại từ log ra đúng phiên; tỉ lệ thành công của agent chưa học trên AppWorld được ghi lại làm baseline.

**Tuần nghỉ 18 – 24/1/2027.**

### 2b — Học từ thực thi và giao diện tối thiểu (25/1 – 14/3/2027, 6 tuần làm việc + tuần Tết)

Mùng 1 Tết Đinh Mùi là thứ Bảy 6/2/2027; tuần 8 – 14/2 nghỉ, không tính vào khẩu phần.

- **Tầng playbook:** mỗi bullet có bộ đếm helpful và harmful theo cách của ACE. Nguồn đếm: kết quả unit test của AppWorld và quyết định duyệt hay chặn của người dùng. Bullet mới vào trial, lên active khi helpful trừ harmful ≥ 2.
- **Tầng procedural và skill:** induction gating — lặp trên ít nhất 5 case, tỉ lệ thành công ≥ 0,9, có ít nhất một điều kiện sau kiểm được bằng code.
- **Adapter B: Claude Code qua Claude Agent SDK.** Hook `PreToolUse` và `PermissionRequest` chuyển mọi call về cổng. Test bằng sự kiện hook ghi sẵn; chạy thật cần khóa Anthropic trả phí, nên chỉ chạy khi có khóa của khách hoặc có ngân sách.
- **Giao diện tối thiểu:** adapter trong platform chuyển log sang sự kiện AG-UI (giấy phép MIT); dựng bằng component có sẵn. Bốn thứ: dòng thời gian lượt nói, panel tool call từng agent, nút duyệt/chặn/tạm dừng/dừng hẳn, đồng hồ token. Chấp nhận xấu.
- **Phát lại phiên trong giao diện** — đây là nền của chế độ xem thử bản Free.

**Cổng 3 — 14/3/2027.** Agent có học so với baseline cổng 2 trên phần task giữ riêng, báo kèm khoảng tin cậy; mức chốt đặt sau khi có baseline, không đặt trước. Demo: hai runtime cùng một task, thấy tool call lúc nó xảy ra, chặn một call, dừng một agent, thấy chi phí chạy.

**Tuần nghỉ 15 – 21/3/2027.**

**Cắt khi chậm, theo thứ tự:** adapter Claude chỉ chạy trên sự kiện ghi sẵn → tầng procedural và skill sang danh sách để sau → giao diện chỉ còn phát lại, chưa điều khiển trực tiếp. Không bao giờ cắt: cổng tool, log, tầng playbook.

## Giai đoạn nghiên cứu — Điều phối cuộc họp nhiều agent (22/3 – 18/4/2027, 4 tuần)

Trả lời bằng số: một "cuộc họp" nhiều agent có vai, có người phản biện và điều kiện dừng có làm tốt hơn một agent làm một mình không. Đây là giai đoạn bị cắt đầu tiên nếu chậm.

**Vì sao phải làm như một thí nghiệm, không coi là hiển nhiên.** Nghiên cứu MAST của Berkeley (NeurIPS 2025) phân tích bảy framework nhiều agent trên hơn 200 task và kết luận mức cải thiện so với một agent thường rất nhỏ. Họ tìm ra 14 kiểu lỗi trong ba nhóm: đặc tả nhiệm vụ, lệch nhau giữa các agent, và thiếu kiểm tra kết quả ([arXiv 2503.13657](https://arxiv.org/abs/2503.13657v2)).

**Bốn điều kiện, cùng tập task giữ riêng của AppWorld, cùng trần token:**

| Điều kiện | Cách làm | Vai trò |
| --- | --- | --- |
| Một agent | Agent có học từ giai đoạn 2 | Baseline |
| Một agent tự kiểm | Cùng agent, lấy nhiều mẫu rồi chọn | Baseline mạnh, cùng số token |
| Họp lần lượt | Nhiều vai, nói theo vòng | Cách làm ngây thơ |
| Họp có điều phối | Người điều phối chọn ai nói, một vai phản biện, dừng khi kiểm tra kết quả đạt | Đề xuất, nhắm vào ba nhóm lỗi của MAST |

Chỉ số: tỉ lệ thành công theo unit test, số token, số lần người dùng phải can thiệp, và phân loại lỗi theo MAST. Mọi cuộc họp đi qua cùng cổng tool và cùng log, nên phát lại được.

**Ra được gì.** Bản nháp bài báo (tùy chọn, như đã chốt). Nếu họp có điều phối không hơn một agent tự kiểm, sản phẩm mặc định dùng một agent, cuộc họp chỉ còn là tùy chọn — đó là một kết quả, không phải thất bại.

**Nếu bị cắt:** cả giai đoạn sang danh sách để sau, giai đoạn 3 bắt đầu sớm 4 tuần và có thêm đệm.

## Giai đoạn 3 — Platform (19/4 – 30/5/2027, 6 tuần)

Biến cơ chế đã chứng minh thành thứ doanh nghiệp dám đưa vào quy trình thật: ai được duyệt gì, hạn mức, dấu vết xuất ra được, và cách cài. Toàn bộ nằm trong gói platform (BSL 1.1); core không import platform.

| Phần | Việc | Gói dùng |
| --- | --- | --- |
| Đa tenant | Khách → đơn vị → tenant; mỗi khách Pro/Enterprise một cơ sở dữ liệu; bản Free chung cơ sở dữ liệu, promoter tắt | Cả ba |
| Hạn mức | Trần token theo khóa LLM của khách, giới hạn bản Free (1 workspace, 3 agent, 10 skill) | Cả ba |
| Phân vai duyệt | Ai được duyệt luật nào, bật sớm luật nào, chặn tool nào — viết bằng Cedar, như spec đã chọn | Pro, Enterprise |
| Phòng điều khiển đầy đủ | Nhiều phiên, lọc theo agent và vai, lịch sử quyết định, rollback luật | Pro, Enterprise |
| Xuất audit | Xuất log quyết định và tool call theo khoảng thời gian | Enterprise |
| SSO, RBAC | Đăng nhập qua nhà cung cấp danh tính của khách | Enterprise |
| Triển khai | Bản Free lên hạ tầng 0 đồng bằng Terraform và compose; image + license key cho Pro/Enterprise | Cả ba |

**Cổng 4 — 30/5/2027.** Bản Free chạy công khai với chế độ xem thử phát lại phiên ghi sẵn; image Pro cài được từ máy trống bằng một lệnh compose (có test trong CI); license key hết hạn thì tính năng trả phí tắt; mọi chính sách Cedar có test; phép tấn công chéo tenant trên bản Free bị chặn.

**Cắt khi chậm, theo thứ tự:** SSO sang sau phát hành (chỉ Enterprise cần) → xuất audit chỉ CSV → phòng điều khiển giữ bản tối thiểu của 2b. Không bao giờ cắt: cách ly tenant, phân vai duyệt, license key.

## Giai đoạn 4 — Phát hành thương mại (31/5 – 27/6/2027, 4 tuần)

Phát hành cả hai bản từ một mã nguồn, có người chuyên môn rà pháp lý trước, và chạy thử với doanh nghiệp thật.

- **Rà pháp lý:** giấy phép BSL 1.1 và Apache 2.0; điều khoản nhúng Claude Agent SDK và OpenAI Agents SDK vào sản phẩm thương mại; điều khoản dữ liệu BPIC, AppWorld; nghĩa vụ theo Luật Bảo vệ dữ liệu cá nhân 2025 cho bản Free, nơi bạn giữ dữ liệu người dùng.
- **Đóng gói hai bản** từ một mã nguồn, không tách nhánh; tài liệu cài đặt và quản trị.
- **Chạy thử Pro** với 1–2 doanh nghiệp đã phỏng vấn, ở chế độ giám sát trên log của chính họ: luật chỉ báo, không chặn.
- **Mở bản Free** cho người dùng.
- **Tuần cuối là đệm**, không xếp việc.

**Cổng 5 — 27/6/2027.** Bản Free mở công khai; image Pro và Enterprise có license key; báo cáo chạy thử có số liệu từ log thật; mọi mục rà pháp lý đã có kết luận.

**Cắt khi chậm:** chạy thử thu về một doanh nghiệp hoặc một bộ log công khai khác. Không bao giờ cắt: rà pháp lý trước khi bán.

## Các luồng chạy song song

Bốn luồng không tốn khẩu phần code nhưng có hạn riêng; trễ hạn thì chặn giai đoạn sau.

| Luồng | Việc | Hạn |
| --- | --- | --- |
| GPU | Đọc điều khoản Kaggle trước khi dùng tài khoản thứ hai; thứ tự dùng Kaggle → Colab → Lightning AI; checkpoint luôn trên R2 | Tuần 1 giai đoạn 1 |
| Pháp lý | Giấy phép AppWorld; điều khoản Claude Agent SDK và OpenAI Agents SDK | Tuần nghỉ trước 2a (6/12/2026) |
| Pháp lý | Rà BSL 1.1, dữ liệu người dùng bản Free theo Luật Bảo vệ dữ liệu cá nhân 2025 | Trước giai đoạn 4 |
| Thị trường | Phỏng vấn 5–10 doanh nghiệp nhóm Pro: quy trình hay sai luật, dữ liệu nằm đâu, có chạy được Docker không, mức giá | Trước cổng 3 (14/3/2027) |
| Thị trường | Chọn 1–2 doanh nghiệp chạy thử, xin log có hợp đồng | Trước cổng 4 (30/5/2027) |
| Duyệt chéo | Người thứ hai duyệt mù 1/5 quyết định thủ công, kappa ≥ 0,61 | Liên tục từ tuần 4 |

Phỏng vấn không tốn GPU và có thể làm vào tuần nghỉ. Kết quả phỏng vấn có thể đổi thứ tự ưu tiên của giai đoạn 3, nhưng không đổi mốc.

## Rủi ro của lộ trình và cách cắt khi chậm

Rủi ro lớn nhất là giai đoạn 2 phình to: nó gánh cả playbook, procedural, AppWorld, cổng tool, hai adapter và giao diện trong 12 tuần làm việc.

| Rủi ro | Mức | Cách giữ | Dấu hiệu |
| --- | --- | --- | --- |
| Giai đoạn 2 phình to | Trung bình | Tách 2a và 2b, mỗi nửa có cổng và cầu dao 50% riêng; thứ tự cắt đã định | Giữa 2a chưa chặn được một tool call |
| Chạy adapter Claude tốn tiền, ngân sách 0 đồng | Trung bình | Tự chạy bằng mô hình mở trên Kaggle; adapter Claude test bằng sự kiện ghi sẵn, chạy thật bằng khóa của khách | Demo cần hai hãng mà không có khóa |
| Điều khoản SDK cấm nhúng vào sản phẩm thương mại | Chưa biết | Đọc trước 2a; core chỉ biết `ToolGateway`, nên bỏ một adapter không ảnh hưởng phần còn lại | Điều khoản có hạn chế |
| AG-UI đổi phiên bản | Nhẹ | Chỉ adapter trong platform phụ thuộc AG-UI | Phiên bản mới phá tương thích |
| Họp nhiều agent không hơn một agent | Nhẹ | Là một kết quả; sản phẩm mặc định một agent | Điều kiện họp có điều phối thua tự kiểm |
| Hết hạn mức GPU giữa giai đoạn | Nhẹ | Backend CPU cho phát triển, bộ đệm phản hồi, checkpoint R2 | Hết hạn mức trước khi xong một điều kiện |
| Không tìm được doanh nghiệp chạy thử | Trung bình | Phỏng vấn từ giai đoạn 1; dự phòng bằng một bộ log công khai khác | Trước cổng 3 chưa có ai đồng ý |

**Thứ tự cắt toàn dự án**, khi cầu dao của một giai đoạn nhảy mà cắt trong giai đoạn đó vẫn không đủ:

1. Giai đoạn nghiên cứu (4 tuần) sang danh sách để sau.
2. SSO và xuất audit đầy đủ sang sau phát hành.
3. Tầng procedural và skill sang sau phát hành.
4. Adapter Claude chỉ còn chạy trên sự kiện ghi sẵn.

Không bao giờ cắt: baseline và tái lập, cách ly tenant, cổng tool, log chỉ thêm, rà pháp lý trước khi bán.

## Nguồn

Các trang đã mở và đọc ngày 3/10/2026.

- [AG-UI — tổng quan giao thức](https://docs.ag-ui.com/introduction) và [kho mã AG-UI, giấy phép MIT](https://github.com/ag-ui-protocol/ag-ui)
- [Đặc tả MCP 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/index.md)
- [Claude Code — hooks, PreToolUse và PermissionRequest](https://code.claude.com/docs/en/hooks)
- [OpenAI Agents SDK — guardrails và duyệt của người](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals)
- [AppWorld — 9 ứng dụng, 457 API, 750 task](https://alphaxiv.org/benchmarks/allen-institute-for-ai/appworld)
- [Why Do Multi-Agent LLM Systems Fail? (MAST)](https://arxiv.org/abs/2503.13657v2)
- [Tết Âm lịch 2027 — Thư viện Pháp luật](https://thuvienphapluat.vn/hoi-dap-phap-luat/tet-am-lich-2027-la-ngay-may-duong-lich-138050948.html)
- [Luật Bảo vệ dữ liệu cá nhân 2025, số 91/2025/QH15](https://thuvienphapluat.vn/van-ban/Bo-may-hanh-chinh/Luat-Bao-ve-du-lieu-ca-nhan-2025-so-91-2025-QH15-625628.aspx)
- [BPIC 2015, bài báo số 1 — số case và loại hoạt động](https://www.win.tue.nl/bpi/2015/bpic2015_paper_1.pdf)

Phạm vi giai đoạn 1 và các cổng lấy từ tab spec của tài liệu "Spec kỹ thuật — gói core"; mô hình gói và hạ tầng lấy từ tài liệu đề xuất.
