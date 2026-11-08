# Spec kỹ thuật — giai đoạn 2a (BẢN NHÁP)

> **Trạng thái: BẢN NHÁP — chưa qua cổng spec.** Bản FINAL + qua cổng spec diễn ra ở tuần nghỉ 30/11–6/12/2026, khi các mục `CHƯA CÓ` đã lấp đầy (làm sớm không đổi mốc, theo đề xuất task 13.4).
>
> - Task: 13.4, plan con 13. Cổng ra lúc FINAL: spec qua cổng spec của giai đoạn 2a (plan file dòng 309).
> - Cơ sở viết: `feat/integration` ở `711f595` (ngày viết: 8/11/2026). Mọi trích dẫn code trong tài liệu này ghi kèm commit này; bước FINAL ở tuần nghỉ kiểm lại từng trích dẫn với HEAD lúc đó (đề xuất 13.4, R6).
> - Nguồn đã đọc thật: roadmap (`docs/roadmap/Lộ trình — Enterprise Agentic.md`, dòng 50, 73, 77–83, 171, 181); spec lõi (`docs/specs/phase-1-core/Spec kỹ thuật — gói core.md`, dòng 21, 52, 95–98, 140, 255–275); plan giai đoạn 1 (dòng 309); báo cáo 13.2 (`docs/reports/ket-qua-giai-doan-1.md`); AppWorld `LICENSE` (SHA `261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64`, đọc qua GitHub connector ngày 8/11/2026) và hàm sinh `README_BEFORE_SHARING.md` (`src/appworld/common/crypto.py`, `pack_bundle`, SHA `5954e97f3c0686b09ae8f14f979917e81f332327`, đọc qua GitHub connector ngày 8/11/2026).
> - Quy tắc: mục chưa có đầu vào ghi `CHƯA CÓ — chờ <task>`, không bịa số hay kết luận (tiền lệ 13.2). Mọi giả định về kết quả giai đoạn 1 viết tường minh dạng "Giả định A<n>" (§10).

## 0. Bảng phụ thuộc — mục CHƯA CÓ trong bản nháp

| Mục trong spec 2a | Trạng thái ở bản nháp | Chờ task |
|---|---|---|
| §2 Động cơ / kết quả giai đoạn 1 (baseline, F1, bốn chỉ số theo tenant × điều kiện) | CHƯA CÓ | 12.2 (đo) + 13.3 FINAL (verdict cổng 1) |
| §6 Engine phục vụ mô hình 8B trên Kaggle (vLLM hay llama-server) | CHƯA CÓ | Verdict 11.1 |
| §5.3 Tái lập: `config_hash` / `data_hash` / `code_commit` khóa của lần đo | CHƯA CÓ | Khóa thật 12.1 + 12.3 (chạy lại) |
| §2 Luật tri thức từ giai đoạn 1 (luật Wabo, trạng thái sau cổng Beta) | CHƯA CÓ | Đo 9.1 (chạy lại đang diễn ra) |
| §4.3 + §7.3 Điều khoản Claude Agent SDK + OpenAI Agents SDK | CHƯA CÓ | Đọc tuần nghỉ (hạn 6/12/2026, roadmap dòng 171) |
| §7.2 Mục License trong README chính của AppWorld | CHƯA CÓ (đã có LICENSE + điều khoản `.bundle`, xem §7.1) | Đọc tuần nghỉ |
| §9 Bảng cổng spec 2a (câu hỏi + kết quả từng vòng) | Viết ngay (theo tiền lệ 14 câu giai đoạn 1); kết quả các vòng để trống tới tuần nghỉ | — (không phụ thuộc kết quả giai đoạn 1) |

## 1. Ranh giới 2a / 2b

Giai đoạn 2 (7/12/2026–14/3/2027) chia hai nửa để cổng tool có trước khi có bất cứ thứ gì dựa vào nó (roadmap). Ranh giới, theo bảng giai đoạn của roadmap (dòng 50) và spec lõi (dòng 21):

| Nửa | Nội dung | Cổng |
|---|---|---|
| **2a — Cổng tool và điều khiển (7/12/2026–17/1/2027, 6 tuần)** | Proxy MCP có quyền chặn; tạm dừng, dừng hẳn, trần ngân sách; adapter OpenAI | Log mỗi tool call; phát lại bằng dòng lệnh | Agent thực thi trên AppWorld | Cổng 2 — 17/1/2027 (§9) |
| **2b — Học từ thực thi và giao diện tối thiểu (25/1–14/3/2027)** | Adapter Claude; giao diện tối thiểu | Duyệt/chặn thành helpful/harmful; phát lại trong giao diện | Playbook, procedural, skill | Cổng 3 (ngoài phạm vi tài liệu này) |

**Thuộc 2a, không thuộc 2b:**

- Proxy MCP thật trên giao diện `ToolGateway` (§3). Spec lõi viết "giai đoạn 2" chung cho cả phòng điều khiển; bản này vẽ ranh giới: proxy MCP là 2a, còn tầng playbook, tầng procedural, thư viện skill, induction gating là 2b (spec lõi dòng 140 giao luật playbook/procedural cho "giai đoạn 2" — roadmap giao chúng cho 2b; xem §10, Giả định A6).
- Adapter OpenAI (§4). Adapter Claude là 2b (roadmap dòng 50).
- Log mỗi tool call vào bảng `event` chỉ thêm + phát lại bằng dòng lệnh (§5). Phát lại trong giao diện là 2b.
- Agent thực thi trên AppWorld (§6). Tín hiệu helpful/harmful từ duyệt/chặn nuôi tầng playbook là 2b — 2a chỉ ghi lại quyết định, chưa dùng chúng để học.

**Không bao giờ cắt (roadmap, thứ tự cắt toàn dự án):** baseline và tái lập, cách ly tenant, cổng tool, log chỉ thêm, rà pháp lý trước khi bán. Thứ tự cắt của riêng 2a — xem §8.3.

## 2. Động cơ / kết quả giai đoạn 1

**CHƯA CÓ — chờ 12.2 (đo) + 13.3 FINAL (verdict cổng 1).**

Mục này, khi lấp đầy ở tuần nghỉ, ghi: baseline của bảy điều kiện trên cả hai nguồn dữ liệu (bốn chỉ số kèm khoảng tin cậy theo tenant × điều kiện), F1 trích luật từ văn bản, và verdict cổng 1 (sáu điều kiện). Nguồn duy nhất: báo cáo 13.2 (`docs/reports/ket-qua-giai-doan-1.md`, sinh bằng lệnh `python -m tools.generate_phase1_report`) và báo cáo cổng 1 (13.3 FINAL). Không chép tay số từ bất cứ nguồn nào khác.

**CHƯA CÓ — chờ đo 9.1 (chạy lại đang diễn ra): luật tri thức từ giai đoạn 1 (luật Wabo, trạng thái sau cổng Beta).** Luật Wabo là đầu vào cho agent 2a ở chỗ: agent thực thi trên AppWorld không dùng luật Wabo làm ground truth (AppWorld chấm bằng unit test kiểm thay đổi DB, §6), nhưng luật là bằng chứng rằng pipeline học luật từ văn bản đã chạy hết — mục này ghi trạng thái của luật sau cổng Beta để 2a biết xuất phát điểm nào của tri thức đã học, không phải để agent dùng luật làm đáp án.

## 3. Kiến trúc proxy MCP có quyền chặn trên giao diện `ToolGateway`

### 3.1 Giao diện `ToolGateway` — nền móng đã có từ giai đoạn 1

Spec lõi (dòng 95–98) đặt nền móng: "Giao diện `ToolGateway` trong core. Mọi tool call sau này phải đi qua một cổng duy nhất, trả về một trong bốn quyết định: cho, chặn, hỏi người, để luật quyết — cùng bốn giá trị hook `PreToolUse` của Claude Code dùng. Lát cắt chỉ khai báo giao diện và test hợp đồng với một cổng giả; proxy MCP thật làm ở giai đoạn 2a."

Trích dẫn code tại `feat/integration` ở `711f595` (`packages/core/src/praxon_core/gateway/tool_gateway.py`):

- `ToolDecision` (StrEnum) có đúng bốn giá trị: `ALLOW = "allow"`, `DENY = "deny"`, `ASK_USER = "ask"`, `DEFER_TO_POLICY = "defer"`.
- `ToolCall` (frozen dataclass): `tool: str`, `arguments: Mapping[str, object]`, `actor: str | None`, `run_id: str | None`, `tenant_id: str | None`. Cổng giả trong test hợp đồng không cần ba trường ngữ cảnh; cổng thật ở 2a điền đầy đủ để ghi bảng `event` (§5).
- `ToolGateway` (Protocol): một phương thức `decide(call: ToolCall) -> ToolDecision`. Bên gọi đưa một `ToolCall` vào và nhận về đúng một `ToolDecision`; quyết định đó là thứ bên gọi phải tuân theo — không có đường vòng qua cổng.
- Hợp đồng import-linter `client-tool-chi-trong-gateway-va-adapters`: import client MCP hay SDK agent chỉ được phép trong `gateway` và `adapters` (docstring của `tool_gateway.py`). Core không import client nào.

**Bất biến (giữ từ giai đoạn 1, kiểm bằng cổng 2):** mọi tool call đi qua đúng một cổng này. Agent cố gọi tool không qua cổng thì thất bại — có test (tiêu chí cổng 2, roadmap dòng 89–91).

### 3.2 Proxy MCP — API của AppWorld bọc thành tool MCP nằm sau proxy

Roadmap (dòng 84–88): "`ToolGateway` thành proxy MCP. API của AppWorld bọc thành tool MCP nằm sau proxy. Mỗi call nhận một trong bốn quyết định: cho, chặn, hỏi người, để luật quyết — cùng bốn giá trị mà hook `PreToolUse` của Claude Code dùng, nên adapter sau này khớp thẳng."

- Mỗi API của AppWorld (§6: 457 API) bọc thành một tool MCP; tool MCP không gọi thẳng API — lời gọi đi qua proxy, proxy hỏi `ToolGateway.decide()` rồi mới cho qua hoặc chặn.
- Proxy là thành phần duy nhất biết cả hai phía: phía trước là agent (qua adapter, §4), phía sau là API AppWorld. Proxy không chứa luật nghiệp vụ của AppWorld; nó chỉ thực thi quyết định của cổng.
- Một tool call chỉ được thực thi khi quyết định là `ALLOW` (hoặc `ASK_USER` đã được người duyệt, §3.3). Quyết định `DENY` và `DEFER_TO_POLICY` (khi luật quyết là chặn) không bao giờ tới được API.

### 3.3 Ngữ nghĩa bốn quyết định

| Quyết định | Ý nghĩa | Hành vi của proxy | Ghi log |
|---|---|---|---|
| `ALLOW` (cho) | Cổng cho phép | Thực thi tool call, trả kết quả về cho agent | Một dòng `event`: quyết định, ai quyết, lý do (§5) |
| `DENY` (chặn) | Cổng từ chối | Không thực thi; trả về cho agent một từ chối (không phải kết quả tool) | Một dòng `event` kèm lý do chặn |
| `ASK_USER` (hỏi người) | Cần người duyệt trước khi thực thi | Dừng lần chạy, trả về trạng thái chạy tiếp được sau khi duyệt (cơ chế dừng chờ duyệt có sẵn của OpenAI Agents SDK, §4); quyết định duyệt/chặn của người dùng thành một Candidate đi qua Governor với `decided_by` và `rubric_clause` (nền móng thứ ba, spec lõi dòng 95–98) | Hai dòng `event`: dòng hỏi (quyết định `ASK_USER`) và dòng quyết định của người |
| `DEFER_TO_POLICY` (để luật quyết) | Cổng nhường quyết định cho một luật | Luật đánh giá lời gọi (tên tool, băm đối số, actor, tenant) và trả về cho/chặn; luật không phải là mô hình — nó là phép tính trên số đếm và điều kiện đã khai báo, cùng họ với cổng Beta và Wilson của giai đoạn 1 | Một dòng `event` ghi luật nào đã quyết và kết quả |

**Câu hỏi cho review tuần nghỉ (chưa quyết trong bản nháp):** luật ở `DEFER_TO_POLICY` lấy từ đâu trong 2a — luật viết tay cho từng tool AppWorld, hay luật học từ log duyệt/chặn của 2a rồi mới có ở 2b? Bản nháp không tự chọn; tuần nghỉ quyết trước khi viết plan 2a.

### 3.4 Tạm dừng / dừng hẳn / trần ngân sách

Roadmap (dòng 88): "Nút tạm dừng, dừng hẳn, trần ngân sách là lệnh đi qua cùng cổng, có trong log."

- Ba nút là lệnh, không phải cờ lẻ: mỗi nút là một lời gọi đi qua cùng cổng `ToolGateway` và được ghi vào bảng `event` như mọi hành động khác (actor là người ra lệnh, action là `pause` / `stop` / `set_budget_ceiling`).
- **Tạm dừng:** dừng lần chạy ở biên tool call gần nhất; trạng thái chạy tiếp được (cùng cơ chế dừng chờ duyệt của §3.3); chạy tiếp không gọi lại các tool call đã xong.
- **Dừng hẳn:** kết thúc lần chạy; checkpoint tại biên đã hoàn thành gần nhất (tiền lệ 10.3: checkpoint mỗi N case, resume từ checkpoint); lần chạy ghi trạng thái dừng hẳn, không ghi là thất bại.
- **Trần ngân sách:** cơ chế chốt theo tiền lệ 10.4 (giai đoạn 1): trần là một cài đặt; khi chạm trần, checkpoint tại biên đã hoàn thành, ghi sự kiện, dừng lần chạy; chỉ chạy tiếp được bằng cách nâng trần (hoặc tắt trần) — không tự động chạy tiếp. Giá trị số của trần do plan 2a đặt, không phải spec này; spec chỉ quy định cơ chế chốt và đường chạy tiếp.

## 4. Adapter OpenAI — runtime tương thích OpenAI

### 4.1 Adapter A

Roadmap (dòng 86): "Adapter A: runtime tương thích OpenAI. OpenAI Agents SDK đã có sẵn cơ chế dừng chờ duyệt: tool đánh dấu cần duyệt thì lần chạy dừng, trả về trạng thái chạy tiếp được sau khi duyệt."

- Adapter OpenAI là thành phần duy nhất trong 2a biết OpenAI Agents SDK. Nó dịch giữa hai phía: phía agent (lời gọi mô hình qua endpoint tương thích OpenAI, §6) và phía proxy MCP (§3.2). Adapter không chứa luật chặn — mọi quyết định chặn đều do `ToolGateway` trả về; adapter chỉ thực thi cơ chế dừng/chạy tiếp.
- Khi một tool call nhận quyết định `ASK_USER`, adapter dùng đúng cơ chế dừng chờ duyệt của SDK: lần chạy dừng, trả về trạng thái chạy tiếp được sau khi duyệt; khi người duyệt xong, lần chạy tiếp tục từ đúng điểm dừng (không gọi lại các tool call đã xong).
- Model phục vụ qua endpoint tương thích OpenAI (§6) — adapter không gọi thẳng model vendor nào khác.

### 4.2 Core chỉ biết `ToolGateway`

Roadmap (rủi ro, dòng 181): "Điều khoản SDK cấm nhúng vào sản phẩm thương mại | Chưa biết | Đọc trước 2a; core chỉ biết `ToolGateway`, nên bỏ một adapter không ảnh hưởng phần còn lại."

- Core không import OpenAI Agents SDK, không import client MCP, không biết tên adapter nào. Hợp đồng import-linter `client-tool-chi-trong-gateway-va-adapters` (§3.1) chặn import client ngoài `gateway` và `adapters` — kiểm bằng máy, không bằng kỷ luật.
- Hệ quả thiết kế: bỏ adapter OpenAI (vì điều khoản, vì giá, vì SDK đổi phiên bản) thì proxy + core + log vẫn chạy; adapter thay thế chỉ cần nói được giao thức của proxy. Câu hỏi 17 của cổng spec (§9) kiểm hệ quả này.

### 4.3 Điều khoản SDK

**CHƯA CÓ — chờ đọc tuần nghỉ (hạn 6/12/2026, roadmap dòng 171).**

Điều khoản Claude Agent SDK và OpenAI Agents SDK chưa đọc; mục này chỉ lấp đầy sau khi đọc, và phải trả lời đúng một câu hỏi: điều khoản có cấm nhúng adapter vào sản phẩm thương mại không? Nếu cấm, §4.2 đã có đường lui (bỏ adapter, core không ảnh hưởng) — nhưng quyết định bỏ hay giữ adapter nào là việc của plan 2a, không phải của spec này.

## 5. Log mỗi tool call vào bảng `event` chỉ thêm + phát lại bằng dòng lệnh

### 5.1 Bảng `event` — nền móng đã có từ giai đoạn 1

Spec lõi (dòng 95–98) đặt nền móng: "Bảng `event` chỉ thêm. Mỗi hành động có ai làm, làm gì, quyết định gì, ai quyết, vì sao, thuộc run nào. Ở lát cắt này bảng ghi lần gọi vai và quyết định của Governor; từ giai đoạn 2 ghi thêm từng tool call."

Trích dẫn code tại `feat/integration` ở `711f595` (`packages/core/src/praxon_core/repositories/migrations/V1__tables.sql`, bảng `event`, chú thích "Cắt ngang: nhật ký quyết định và tool call. Chỉ thêm (BĐ1)"):

| Cột | Ý nghĩa |
|---|---|
| `event_id` | Khóa chính (uuid, mặc định `gen_random_uuid()`) |
| `run_id` | Thuộc run nào (tham chiếu bảng `run`) |
| `tenant_id` | Của tenant nào (NOT NULL) |
| `actor` | Ai làm (NOT NULL) |
| `action` | Làm gì (NOT NULL) |
| `target` | Đối tượng tác động |
| `decision` | Quyết định gì |
| `decided_by` | Ai quyết |
| `reason` | Vì sao |
| `payload_hash` | Băm tải trọng (NOT NULL) |
| `occurred_at` | Thời điểm (mặc định `now()`) |

Bảng chỉ thêm: không có lệnh cập nhật hay xóa dòng `event` trong code; bất biến BĐ1 của giai đoạn 1. Lệnh tạm dừng / dừng hẳn / trần ngân sách (§3.4) cũng ghi vào đây như mọi hành động khác.

### 5.2 Mỗi tool call ghi gì

Roadmap (dòng 89): "Log mỗi tool call: ai gọi, tham số đã băm, quyết định, ai quyết, lý do."

- Một tool call = một dòng `event`: `actor` là agent (hoặc người, với quyết định duyệt), `action` là tên tool, `target` là tên tool hoặc tài nguyên tác động, `decision` là một trong bốn giá trị của `ToolDecision`, `decided_by` là cổng / luật / người, `reason` là lý do, `payload_hash` là băm của đối số (đối số không ghi dạng plaintext vào log — xem §7.2 về quy tắc không tái phân phối dữ liệu task ở dạng plaintext).
- Quyết định `ASK_USER` ghi hai dòng: dòng hỏi và dòng quyết định của người (§3.3).

### 5.3 Phát lại bằng dòng lệnh

Roadmap (dòng 89): "Phát lại một phiên từ log bằng dòng lệnh." Tiêu chí cổng 2: "phát lại từ log ra đúng phiên".

- Lệnh phát lại nhận một `run_id`, đọc các dòng `event` của run đó theo `occurred_at`, và tái hiện phiên. Ngữ nghĩa phát lại mặc định của spec này là **phát lại quyết định**: chạy lại agent từ cùng đầu vào và cùng seed, đối chiếu từng quyết định của cổng với quyết định đã ghi trong log; phiên phát lại "đúng" khi mọi quyết định trùng khớp. Ngữ nghĩa này không cần thêm cột vào bảng `event` và khớp với việc log chỉ ghi băm đối số (§5.2).
- **Câu hỏi cho review tuần nghỉ (chưa quyết trong bản nháp):** có cần ngữ nghĩa phát lại thứ hai — **phát lại lời gọi** (gọi lại đúng các tool call đã ghi, không chạy lại agent) — không? Ngữ nghĩa này cần đối số đầy đủ, mà log hiện chỉ có băm; muốn có nó phải thêm cột lưu đối số vào `event` (migration mới) và cân nhắc đối số có thể chứa dữ liệu nhạy cảm. Bản nháp không tự chọn; tuần nghỉ quyết trước khi viết plan 2a.
- **CHƯA CÓ — chờ khóa thật 12.1 + 12.3 (chạy lại): tái lập của lần đo — `config_hash` / `data_hash` / `code_commit` khóa.** Phát lại 2a tái lập được phiên khi và chỉ khi ba giá trị khóa của lần đo giai đoạn 1 đã có; hiện cả ba đều CHƯA CÓ. Cơ chế tái lập của giai đoạn 1 (lệnh một lần `python -m tools.run_phase1`, mã thoát 0/1/2/3/4 — `tools/run_phase1.py` tại `711f595`) là tiền lệ cho lệnh phát lại 2a: một lệnh, mã thoát nói rõ kết quả.

## 6. Agent thực thi trên AppWorld

Roadmap (dòng 79–83): "Môi trường là AppWorld: 9 ứng dụng thường ngày, 457 API, 750 task, chấm bằng unit test kiểm thay đổi trong cơ sở dữ liệu — nên thành công đo bằng máy, không nhờ mô hình chấm."

- **Môi trường:** AppWorld — 9 ứng dụng thường ngày, 457 API, 750 task. Agent gọi API qua tool MCP sau proxy (§3.2); mọi tool call đi qua cổng.
- **Cách chấm:** unit test kiểm thay đổi trong cơ sở dữ liệu. Thành công đo bằng máy, không nhờ mô hình chấm — cùng nguyên tắc với giai đoạn 1 (ground truth không qua mô hình, spec lõi cổng câu 5).
- **Mô hình:** agent chạy với mô hình mở 8B trên Kaggle qua endpoint tương thích OpenAI — 0 đồng (roadmap dòng 85). "Generator thôi phát lại trace, bắt đầu gọi mô hình thật."
- **Engine phục vụ mô hình 8B trên Kaggle (vLLM hay llama-server): CHƯA CÓ — chờ verdict 11.1.**
- **Tỉ lệ thành công của agent chưa học trên AppWorld (baseline): CHƯA CÓ — đo trong 2a, là một tiêu chí cổng 2** ("tỉ lệ thành công của agent chưa học trên AppWorld được ghi lại làm baseline", roadmap dòng 89–91). Baseline này chưa có số vì agent chưa chạy lần nào; không ước lượng trước.
- **Một lệnh chạy bảy điều kiện của giai đoạn 1** (`python -m tools.run_phase1`, task 13.1) là tiền lệ cho lệnh chạy 2a, nhưng lệnh chạy 2a là việc của plan 2a, không phải của spec này.

## 7. Giấy phép AppWorld và quy tắc không tái phân phối plaintext

### 7.1 Hai khẳng định đã kiểm nguồn (ngày 8/11/2026)

**Khẳng định 1 — LICENSE là Apache License 2.0.** File `LICENSE` tại nhánh `main` của repo `StonyBrookNLP/appworld`, đọc trực tiếp qua GitHub connector ngày 8/11/2026. Toàn văn là Apache License, Version 2.0, January 2004. SHA của file: `261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64`.

**Khẳng định 2 — điều khoản `.bundle` (phần protected).** File `README_BEFORE_SHARING.md` không tồn tại dưới dạng file tĩnh trong repo công khai (nó là artifact riêng tư, sinh ra lúc phát hành — xem `.private.gitignore` của repo). Nội dung của nó được sinh bởi hàm `pack_bundle` trong `src/appworld/common/crypto.py` (đọc trực tiếp qua GitHub connector ngày 8/11/2026, SHA file `5954e97f3c0686b09ae8f14f979917e81f332327`), trích đúng chỗ:

> `# License`
>
> `The contents of this folder are part of the protected portion of AppWorld, released as an encrypted .bundle file under the Apache 2.0 license with the additional requirement that any public redistribution of it (or of its derivatives) must also be done in an encrypted format.`
>
> `Visit https://github.com/stonybrooknlp/appworld for more information.`

Dịch nghĩa giữ nguyên điều kiện: phần protected (code/dữ liệu task/app/API trong file `.bundle` mã hóa) phát hành dưới Apache 2.0 kèm yêu cầu thêm — mọi lần tái phân phối công khai phần đó (hoặc phái sinh của nó) cũng phải ở dạng mã hóa.

**Quy tắc cứng rút ra cho 2a (ghi ngay từ bản nháp):** không tái phân phối công khai dữ liệu task, API, hay đáp án AppWorld ở dạng plaintext — không đăng code/dữ liệu trích từ `.bundle` lên mạng, không đưa vào tài liệu công khai, không để lọt vào log plaintext. Log tool call (§5.2) chỉ ghi băm đối số, không ghi đối số dạng plaintext — quy tắc này khớp với điều khoản `.bundle`.

**Lưu ý kiểm chứng (8/11/2026, ghi lại để tuần nghỉ đối chiếu):** câu "huấn luyện mô hình và phục vụ đầu ra không tính là tái phân phối" KHÔNG có trong nội dung `README_BEFORE_SHARING.md` được sinh bởi `pack_bundle` (trích đúng chỗ ở trên). Câu đó thuộc mục License trong README chính của AppWorld — mục này chưa đọc (xem §7.2). Bản nháp không khẳng định câu đó cho tới khi mục đó được đọc trực tiếp ở tuần nghỉ.

### 7.2 Mục License trong README chính của AppWorld

**CHƯA CÓ — chờ đọc tuần nghỉ.** Mục này, khi đọc, phải trả lời: (a) câu "huấn luyện mô hình và phục vụ đầu ra không tính là tái phân phối" có đúng nguyên văn trong mục này không; (b) mục này có điều kiện nào khác ngoài hai khẳng định ở §7.1 không.

### 7.3 Điều khoản SDK

**CHƯA CÓ — chờ đọc tuần nghỉ (hạn 6/12/2026).** Xem §4.3.

## 8. Rủi ro của 2a + thứ tự cắt

### 8.1 Bảng rủi ro

| # | Rủi ro | Mức | Cách giữ | Dấu hiệu theo dõi | Hạn kiểm |
|---|---|---|---|---|---|
| R1 | Giai đoạn 2 phình to: 2a gánh cả proxy MCP, adapter OpenAI, AppWorld, log/phát lại trong 6 tuần | Trung bình | Đã tách 2a và 2b, mỗi nửa có cổng và cầu dao 50% riêng (roadmap); bản nháp vẽ ranh giới §1 để không lấn sang 2b | Giữa 2a chưa chặn được một tool call | Cổng 2 — 17/1/2027 |
| R2 | Điều khoản SDK cấm nhúng vào sản phẩm thương mại | Chưa biết | Đọc trước 2a (§4.3, hạn 6/12/2026); core chỉ biết `ToolGateway`, bỏ một adapter không ảnh hưởng phần còn lại (§4.2) | Điều khoản có hạn chế | 6/12/2026 |
| R3 | Giấy phép AppWorld: mục License trong README chính chưa đọc; câu "huấn luyện/phục vụ không tính là tái phân phối" chưa kiểm trên nguồn gốc | Nhẹ | Chỉ khẳng định hai điều đã kiểm nguồn (§7.1); quy tắc không tái phân phối plaintext ghi cứng từ bản nháp; mục README đọc ở tuần nghỉ (§7.2) | Mục README có điều kiện khác với §7.1 | 6/12/2026 |
| R4 | Lẫn phạm vi 2a/2b: spec lõi viết "giai đoạn 2" chung (playbook/procedural/skill) | Nhẹ | Ranh giới rõ ở §1; đoạn nào cần nội dung 2b để viết tiếp thì đánh dấu là câu hỏi cho review tuần nghỉ, không tự lấn sang | Một mục nháp cần nội dung 2b mới viết được | Review bản nháp (trước tuần nghỉ) |
| R5 | "Cổng spec của giai đoạn 2a" chưa được định nghĩa trong repo | Nhẹ | §9 định nghĩa cổng theo tiền lệ giai đoạn 1 (bảng câu hỏi review trong chính tài liệu, chạy theo vòng); bảng cổng có mặt trong bản nháp từ ngày đầu | Lúc duyệt, chủ dự án hỏi "cổng đo bằng gì?" | Lúc duyệt đề xuất 13.4 |
| R6 | Nháp sớm neo quyết định vào giả định về kết quả giai đoạn 1 (vd. mặc định engine là vLLM) | Nhẹ | Mọi giả định viết tường minh ở §10 dạng "Giả định A<n>", không trình bày giả định như sự thật; mục engine để CHƯA CÓ tới verdict 11.1 | Verdict 11.1 về | Khi verdict 11.1 về |
| R7 | Nháp trích code đang đổi (giao diện `ToolGateway`, bảng `event`, lệnh 13.1) rồi code đổi làm trích dẫn sai | Nhẹ | Mọi trích dẫn ghi kèm commit `711f595`; bước FINAL tuần nghỉ kiểm lại từng trích dẫn với HEAD lúc đó | Một commit đổi file được trích dẫn | Tuần nghỉ 30/11–6/12 |
| R8 | Chạy adapter Claude tốn tiền, ngân sách 0 đồng | Trung bình | Không thuộc 2a (adapter Claude là 2b); 2a tự chạy bằng mô hình mở trên Kaggle (§6); adapter Claude test bằng sự kiện ghi sẵn, chạy thật bằng khóa của khách (roadmap) | Demo cần hai hãng mà không có khóa | Cổng 2 — 17/1/2027 |
| R9 | Hết hạn mức GPU giữa giai đoạn | Nhẹ | Backend CPU cho phát triển, bộ đệm phản hồi, checkpoint (tiền lệ 10.3/10.4); quota Kaggle 30 giờ/tuần | Hết hạn mức trước khi xong một điều kiện | Trong 2a |
| R10 | Phát lại cần đối số đầy đủ nhưng log chỉ ghi băm (§5.3) | Nhẹ | Ngữ nghĩa phát lại mặc định là phát lại quyết định (không cần thêm cột); ngữ nghĩa phát lại lời gọi là câu hỏi cho review tuần nghỉ | Review tuần nghỉ chọn ngữ nghĩa phát lại lời gọi | Tuần nghỉ 30/11–6/12 |

### 8.2 Cầu dao 50%

Mỗi nửa giai đoạn 2 có cầu dao 50% riêng (roadmap): giữa 2a, nếu chưa chặn được một tool call thì cầu dao nhảy — dừng lại, chia lại plan 2a, không cố chạy tiếp. Dấu hiệu nhảy cầu dao là R1 (giữa 2a chưa chặn được một tool call).

### 8.3 Thứ tự cắt của 2a

Thứ tự cắt toàn dự án (roadmap): (1) giai đoạn nghiên cứu sang danh sách để sau; (2) SSO và xuất audit đầy đủ sang sau phát hành; (3) tầng procedural và skill sang sau phát hành; (4) adapter Claude chỉ còn chạy trên sự kiện ghi sẵn. Không bao giờ cắt: baseline và tái lập, cách ly tenant, cổng tool, log chỉ thêm, rà pháp lý trước khi bán.

Áp cho 2a: cắt theo đúng thứ tự trên, trong đó mục (3) và (4) vốn đã thuộc 2b nên không nằm trong phạm vi cắt của 2a; mục (1) và (2) cắt trước khi động vào bất cứ thứ gì của 2a. **Trong nội bộ 2a, không cắt:** cổng tool (§3), log chỉ thêm (§5), rà pháp lý (§7). Thứ tự cắt chi tiết trong nội bộ 2a (vd. giảm số task AppWorld đo baseline trước hay giảm phạm vi phát lại trước) là câu hỏi cho plan 2a, không phải spec này — plan 2a viết sau khi cổng spec 2a qua.

## 9. Cổng spec 2a — bảng câu hỏi review (theo tiền lệ giai đoạn 1)

Tiền lệ: cổng duyệt spec giai đoạn 1 (spec lõi dòng 255–275) là một bảng review trong tài liệu, do người chạy theo vòng — không phải một tool máy. Lần chạy thứ năm, ngày 3/10/2026, qua với 14 câu, tất cả Đạt, chạy 5 vòng; 17 rủi ro R1–R17 đều ở mức nhẹ, mỗi cái có dấu hiệu theo dõi và hạn kiểm. Cổng spec 2a theo đúng mẫu đó: bảng câu hỏi dưới đây, chạy theo vòng tới khi không còn rủi ro trung bình/nặng và mọi câu Đạt.

14 câu của giai đoạn 1 chuyển thể sang 2a, cộng 4 câu riêng 2a (câu 15–18). **Kết quả các vòng để trống tới tuần nghỉ** — bản nháp không tự chấm Đạt.

| # | Câu hỏi | Kết quả |
|---|---|---|
| 1 | Có gì của platform lọt vào core? (Adapter và client MCP/SDK chỉ ở platform; core chỉ biết `ToolGateway`.) | — |
| 2 | Có đường ghi quyết định nào vòng qua Candidate hay bảng `event`? | — |
| 3 | Có agent/adapter nào gọi thẳng API AppWorld mà không qua proxy? | — |
| 4 | Mọi luật ở `DEFER_TO_POLICY` đều là phép tính trên số đếm/điều kiện khai báo, không phải phán đoán của mô hình? | — |
| 5 | Chấm AppWorld có đi qua mô hình? (Phải là unit test kiểm thay đổi DB.) | — |
| 6 | Có nguồn ngẫu nhiên ngoài seed? (Seed của lần chạy agent có vào bản ghi không?) | — |
| 7 | Mục phi chức năng nào CI không kiểm được? | — |
| 8 | Rủi ro nào chưa có hạn kiểm? | — |
| 9 | Mỗi tiêu chí cổng 2 có cách đo bằng máy, không nhờ mô hình chấm? | — |
| 10 | Phụ thuộc nào mang giấy phép không dùng được? (AppWorld + điều khoản SDK.) | — |
| 11 | **Mỗi dữ kiện về AppWorld (9 ứng dụng, 457 API, 750 task, cách chấm) đã được kiểm trên nguồn gốc, hay chỉ dựa vào mô tả và trí nhớ?** | — |
| 12 | Còn rủi ro nào ở mức trung bình hoặc nặng? | — |
| 13 | Có tham số nào của agent (prompt, luật) chỉnh trên chính task AppWorld dùng để đo baseline? | — |
| 14 | Có đường nào gọi tool hoặc ghi quyết định của người dùng mà vòng qua ToolGateway, Candidate hay bảng event? | — |
| 15 | Có tool AppWorld nào không bọc thành tool MCP nằm sau proxy không? | — |
| 16 | Có đường nào tái phân phối phần protected của AppWorld ở dạng plaintext không? (Dữ liệu task/API không rời khỏi máy ở dạng plaintext; log chỉ ghi băm đối số.) | — |
| 17 | Adapter nào bỏ đi cũng không ảnh hưởng core không? (Bỏ adapter OpenAI, proxy + core + log vẫn chạy?) | — |
| 18 | Phát lại từ log có ra đúng phiên không? (Tiêu chí cổng 2.) | — |

**Tiêu chí cổng 2 — 17/1/2027 (roadmap):** Agent cố gọi tool không qua cổng thì thất bại (có test); chặn được một call giữa chừng; dừng hẳn và trần ngân sách hoạt động; phát lại từ log ra đúng phiên; tỉ lệ thành công của agent chưa học trên AppWorld được ghi lại làm baseline.

## 10. Giả định về kết quả giai đoạn 1 (viết tường minh, không trình bày như sự thật)

- **Giả định A1:** Engine phục vụ mô hình 8B trên Kaggle là vLLM. (Nguồn: task 11.1 — phương án B đang chạy: sửa lỗi `-lcuda` rồi chạy lại engine (1) vLLM+GGUF; nếu verdict là llama-server, §6 viết lại.)
- **Giả định A2:** Kết quả giai đoạn 1 tồn tại và cổng 1 qua (bảy điều kiện chạy hết, bốn chỉ số có số, chạy lại ra đúng kết quả). (Nguồn: task 12.2 + 13.3 FINAL; nếu tới tuần nghỉ mà một mục CHƯA CÓ vẫn mở, bản FINAL lùi sang đầu giai đoạn 2a (trước 7/12), không cắt cổng — đề xuất 13.4, Phụ lục B.)
- **Giả định A3:** Khóa thật 12.1 tồn tại với `config_hash` / `data_hash` / `code_commit` (nguồn: task 12.1 + 12.3; §5.3 viết lại khi khóa xong).
- **Giả định A4:** Luật Wabo có trạng thái sau cổng Beta (nguồn: task 9.1, đang chạy lại; §2 viết lại).
- **Giả định A5:** Điều khoản SDK cho phép nhúng adapter vào sản phẩm (nguồn: đọc tuần nghỉ; nếu cấm, core chỉ biết `ToolGateway` nên bỏ adapter đó, phần còn lại không ảnh hưởng — roadmap đã lường, §4.2).
- **Giả định A6:** Ranh giới 2a/2b như §1 (nguồn: roadmap dòng 50; spec lõi dòng 140 viết "giai đoạn 2" chung — nếu review tuần nghỉ đổi ranh giới, §1 + §3–§6 viết lại).

## Phụ lục A — Bảng phụ thuộc (bản chính; §0 tóm tắt bảng này)

| Mục trong spec 2a | Trạng thái ở bản nháp | Chờ task |
|---|---|---|
| §2 Động cơ / kết quả giai đoạn 1 (baseline, F1, bốn chỉ số theo tenant × điều kiện) | CHƯA CÓ | 12.2 (đo) + 13.3 FINAL (verdict cổng 1) |
| §6 Engine phục vụ mô hình 8B trên Kaggle (vLLM hay llama-server) | CHƯA CÓ | Verdict 11.1 |
| §5.3 Tái lập: `config_hash` / `data_hash` / `code_commit` khóa của lần đo | CHƯA CÓ | Khóa thật 12.1 + 12.3 (chạy lại) |
| §2 Luật tri thức từ giai đoạn 1 (luật Wabo, trạng thái sau cổng Beta) | CHƯA CÓ | Đo 9.1 (chạy lại đang diễn ra) |
| §4.3 + §7.3 Điều khoản Claude Agent SDK + OpenAI Agents SDK | CHƯA CÓ | Đọc tuần nghỉ (hạn 6/12/2026, roadmap dòng 171) |
| §7.2 Mục License trong README chính của AppWorld | CHƯA CÓ (đã có LICENSE + điều khoản `.bundle`, xem §7.1) | Đọc tuần nghỉ |
| §9 Bảng cổng spec 2a (câu hỏi + kết quả từng vòng) | Viết ngay (theo tiền lệ 14 câu giai đoạn 1); kết quả các vòng để trống tới tuần nghỉ | — (không phụ thuộc kết quả giai đoạn 1) |

## Phụ lục B — Nguồn đã kiểm (bằng chứng của bản nháp)

| # | Khẳng định | Mức | Bằng chứng |
|---|---|---|---|
| 1 | Nội dung 2a/2b, mốc 2a (7/12/2026–17/1/2027), cổng 2, AppWorld (9 ứng dụng, 457 API, 750 task, chấm unit test DB), rủi ro phình to + điều khoản SDK, thứ tự cắt | Đã kiểm nguồn | Roadmap dòng 50, 73, 77–83, 171, 181, đọc 8/11/2026 |
| 2 | Ba nền móng (ToolGateway 4 quyết định, bảng event chỉ thêm, Candidate); luật playbook/procedural + induction gating; cổng spec 14 câu, 5 vòng, ngày 3/10/2026 | Đã kiểm nguồn | Spec lõi dòng 21, 52, 95–98, 140, 255–275, đọc 8/11/2026 |
| 3 | Task 13.4: "Spec giai đoạn 2a cho tuần nghỉ 30/11 – 6/12", cổng ra "Spec qua cổng spec của giai đoạn 2a", trạng thái "chưa làm" | Đã kiểm nguồn | Plan file dòng 309, đọc 8/11/2026 |
| 4 | Tiền lệ CHƯA CÓ: mục chưa có đầu vào ghi `CHƯA CÓ`, không bịa số | Đã kiểm nguồn | Báo cáo 13.2 dòng 3, đọc 8/11/2026 |
| 5 | `ToolGateway`: `ToolDecision` 4 giá trị, `ToolCall` 5 trường, `decide()`; hợp đồng import-linter `client-tool-chi-trong-gateway-va-adapters` | Đã kiểm nguồn | `packages/core/src/praxon_core/gateway/tool_gateway.py` tại `711f595`, đọc 8/11/2026 |
| 6 | Bảng `event`: 11 cột, chỉ thêm (BĐ1); `payload_hash` NOT NULL | Đã kiểm nguồn | `packages/core/src/praxon_core/repositories/migrations/V1__tables.sql` tại `711f595`, đọc 8/11/2026 |
| 7 | Một lệnh chạy bảy điều kiện: `python -m tools.run_phase1`, mã thoát 0/1/2/3/4 | Đã kiểm nguồn | `tools/run_phase1.py` tại `711f595`, đọc 8/11/2026 |
| 8 | AppWorld LICENSE là Apache 2.0 | Đã kiểm nguồn | `StonyBrookNLP/appworld` `LICENSE` tại `main`, SHA `261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64`, đọc qua GitHub connector 8/11/2026 |
| 9 | Điều khoản `.bundle`: phần protected dưới Apache 2.0 + yêu cầu tái phân phối công khai cũng phải mã hóa | Đã kiểm nguồn | `StonyBrookNLP/appworld` `src/appworld/common/crypto.py`, hàm `pack_bundle` (sinh `README_BEFORE_SHARING.md`), SHA file `5954e97f3c0686b09ae8f14f979917e81f332327`, đọc qua GitHub connector 8/11/2026. Lưu ý: file `README_BEFORE_SHARING.md` không tồn tại dạng tĩnh trong repo công khai (artifact riêng tư, sinh lúc phát hành) — nội dung trích ở §7.1 là nội dung hàm sinh ra |
| 10 | Verdict 11.1, đo 12.2, chạy lại 12.3, 13.3 FINAL, khóa thật 12.1, đo 9.1 đều chưa có kết quả | Đã kiểm nguồn | Plan: 62/68 task "xong", 6 "chưa làm" gồm đúng 11.1, 11.4, 12.2, 12.3, 13.3, 13.4 (`feat/integration` ở `711f595`, 8/11/2026); 9.1 đang chạy lại, 11.1 đang chạy phương án B |
| 11 | Tuần nghỉ đủ chỗ để FINAL + qua cổng spec | Giả thuyết | Chưa đo: khẩu phần tuần nghỉ chưa ai ước lượng. Cách kiểm: lúc lập kế hoạch tuần nghỉ (trước 30/11), đối chiếu danh sách mục CHƯA CÓ còn mở với số ngày nghỉ; nếu không đủ, bản FINAL lùi sang đầu giai đoạn 2a (trước 7/12) chứ không cắt cổng |
