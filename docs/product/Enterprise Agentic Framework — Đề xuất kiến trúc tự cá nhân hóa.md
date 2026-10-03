# Enterprise Agentic Framework — Đề xuất kiến trúc tự cá nhân hóa

Oct 2, 2026 · @ngoc han

Đã duyệt toàn bộ ngày 2/10/2026: xây bản free làm nền kỹ thuật, với khóa luận và bài báo là mục tiêu tự đặt, rồi phát triển lên bản Pro và Enterprise, hoàn thành trước tháng 7/2027. Điểm khác biệt không nằm ở việc xây thêm một framework agent — chỗ đó đã chật. Nó nằm ở lớp *tự cá nhân hóa*: cơ chế để một bản cài đặt gốc tự học quy trình, từ vựng và ràng buộc của từng doanh nghiệp trong lúc vận hành.

**Bổ sung 3/10/2026: gộp ý tưởng phòng điều khiển.** Doanh nghiệp giao việc cho đội agent theo vai, nhìn thấy và điều khiển được từng hành động của chúng, còn hệ thống tự học cách doanh nghiệp đó vận hành — từ log quy trình và từ chính những lần giám đốc duyệt hay chặn. Mô hình gói, giấy phép và mốc tháng 7/2027 giữ nguyên.

## Khoảng trống thật nằm ở ai làm việc thích nghi

Mọi nền tảng lớn đều đã có "cải tiến liên tục", nhưng người cải tiến là con người, không phải hệ thống. Copilot Studio cho maker chấm điểm phản hồi bằng thumbs up/down và xem dashboard đánh giá, rồi maker tự sửa prompt và topic ([Microsoft](https://www.microsoft.com/en-us/microsoft-copilot/blog/?p=7230)). Vòng lặp đó phụ thuộc vào một đội vận hành biết agent đang sai ở đâu — thứ mà doanh nghiệp vừa và nhỏ ở Việt Nam gần như không có.

Thị trường đã chật ở lớp orchestration. Agentforce đạt 540 triệu USD ARR với 18.500 khách hàng doanh nghiệp đầu 2026; Gartner dự báo 40% ứng dụng doanh nghiệp sẽ có agent chuyên biệt vào cuối 2026 ([tech-insider](https://tech-insider.org/agentic-ai-enterprise-2026-market-analysis/), [MarkTechPost](https://www.marktechpost.com/2026/05/19/best-enterprise-level-agentic-ai-platforms-for-2026/)). Xây thêm một framework điều phối agent nữa là cạnh tranh trực diện với Google, Microsoft, Salesforce, UiPath — không nên.

Lớp còn trống là *cá nhân hóa tự động*: hệ thống tự quan sát cách doanh nghiệp làm việc, tự rút ra quy tắc, và tự đề xuất thay đổi hành vi của chính nó. Nghiên cứu 2025–2026 đã chứng minh điều này khả thi mà không cần huấn luyện lại mô hình. ACE (Stanford/SambaNova/Berkeley) coi context như một "playbook tiến hóa", cập nhật từng mục nhỏ thay vì viết lại toàn bộ, tăng trung bình 10,6% trên benchmark agentic, 8,6% trên benchmark tài chính, và giảm trung bình 86,9% độ trễ thích nghi ([arXiv 2510.04618](https://arxiv.org/pdf/2510.04618), [InfoQ](https://infoq.com/news/2025/10/agentic-context-eng)).

Ba lý do khiến đây là chỗ đứng hợp lý:

- **Chuẩn đã chín, nên không phải xây lại hạ tầng kết nối.** MCP và A2A đều đã về dưới Agentic AI Foundation của Linux Foundation; A2A ra bản v1.0 tháng 3/2026 và có hơn 150 tổ chức hỗ trợ ([Linux Foundation](https://www.hpcwire.com/off-the-wire/linux-foundation-a2a-protocol-marks-one-year-with-broad-enterprise-and-cloud-adoption/)).
- **Memory đã thành hạ tầng mua sẵn.** Mem0, Zep/Graphiti và Letta đã giải quyết phần lưu trữ và truy hồi ([so sánh](https://www.agenticwire.news/article/mem0-zep-letta-agent-memory)). Phần chưa ai làm tốt là *quản trị* cái được ghi vào đó.
- **Chính các bài so sánh nền tảng cũng chỉ ra chỗ hở này.** Lời khuyên lặp lại là đánh giá governance của harness — quyền ghi có giới hạn, audit, rollback — *trước khi* chọn nhà cung cấp memory ([puppyone](https://www.puppyone.ai/blog/best-ai-agent-memory-platforms)).

## Không nền tảng nào tự thay đổi hành vi của chính nó

Trong 12 nền tảng khảo sát, cột "ai quyết định thay đổi" luôn là con người. Đó là ranh giới để định vị đề xuất này.

| Nền tảng | Lớp | Cách thích nghi với doanh nghiệp | Ai quyết định thay đổi |
| --- | --- | --- | --- |
| [Agentforce](https://tech-insider.org/agentic-ai-enterprise-2026-market-analysis/) | Orchestration, neo vào CRM | Grounding vào dữ liệu Salesforce, cấu hình topic/action | Admin, consultant |
| [Copilot Studio](https://www.microsoft.com/en-us/microsoft-copilot/blog/?p=7230) | Orchestration, neo vào M365 | Thumbs up/down, bộ đánh giá, maker sửa prompt | Maker |
| [Gemini Enterprise](https://www.marktechpost.com/2026/05/19/best-enterprise-level-agentic-ai-platforms-for-2026/) | Orchestration đa mô hình | Kết nối hệ thống qua MCP, cấu hình agent | Platform engineer |
| [ServiceNow](https://www.marktechpost.com/2026/05/19/best-enterprise-level-agentic-ai-platforms-for-2026/) | Agent nội bộ IT/HR | Workflow có sẵn theo module | Process owner |
| [UiPath](https://agentic-ai.readthedocs.io/en/latest/AgentPlatforms/enterprise-platforms-2026/) | RPA phủ lớp agentic | Ghi lại thao tác, dựng automation | RPA developer |
| [watsonx Orchestrate](https://agentic-ai.readthedocs.io/en/latest/AgentPlatforms/enterprise-platforms-2026/) | Orchestration cho ngành quản chế | Blueprint theo ngành, marketplace agent | Consultant |
| [LangGraph](https://www.marktechpost.com/2026/05/19/best-enterprise-level-agentic-ai-platforms-for-2026/) | Thư viện xây agent | Lập trình graph, state tự quản | Kỹ sư |
| [CrewAI](https://agentic-ai.readthedocs.io/en/latest/AgentPlatforms/enterprise-platforms-2026/) | Thư viện multi-agent | Định nghĩa vai trò và nhiệm vụ bằng code | Kỹ sư |
| [Letta](https://www.agenticwire.news/article/mem0-zep-letta-agent-memory) | Runtime có memory phân tầng | Agent tự sửa core memory qua tool call | Agent, trong phạm vi runtime |
| [Mem0](https://mem0.ai/compare/mem0-vs-zep) | Lớp memory cắm ngoài | Trích xuất và truy hồi fact tự động | Hệ thống, không có cổng duyệt |
| [Zep / Graphiti](https://www.developersdigest.tech/blog/best-ai-agent-memory-providers-2026) | Knowledge graph theo thời gian | Fact có cửa sổ hiệu lực, ABAC, retention | Hệ thống + policy admin |
| [ACE](https://arxiv.org/pdf/2510.04618) | Nghiên cứu, context tiến hóa | Generator → Reflector → Curator, cập nhật delta | Hệ thống, chưa có lớp quản trị |

Ba điều rút ra để tái sử dụng thay vì xây lại:

- **Letta và ACE đã có cơ chế tự sửa, nhưng thiếu quản trị.** Letta cho agent tự ghi vào core memory; ACE cho agent tự biên tập playbook. Cả hai đều không có khái niệm "ai được duyệt thay đổi này" — đúng thứ doanh nghiệp bắt buộc phải có.
- **Zep có đúng nguyên thủy quản trị cần dùng.** Cửa sổ hiệu lực của fact, kiểm soát truy cập theo thuộc tính, chính sách lưu trữ và audit. Spec mượn mô hình song thời gian của nó nhưng cài trên Postgres, để một tệp compose dựng được cả hệ và chạy được trong notebook Kaggle.
- **Phần orchestration không tự xây.** LangGraph (Apache 2.0) đã là lớp chạy agent được triển khai trên Vertex AI, Bedrock và Azure Foundry. Lát cắt đầu dùng một bộ điều phối mỏng; mỗi vai là một hàm thuần nên sau này thay bằng LangGraph mà không sửa vai nào.

## Lõi đề xuất: bốn tầng memory, mỗi tầng một cổng duyệt khác nhau

Cá nhân hóa không phải một tính năng mà là bốn loại ghi nhớ khác nhau, với mức rủi ro khác nhau — nên phải có cổng duyệt khác nhau. Đây là điểm mà Letta, Mem0 và ACE đều để trống.

Phân loại memory trong khảo sát học thuật gồm working, episodic, semantic và procedural; câu hỏi khó là *chính sách chuyển tầng*: khi nào một bản ghi trải nghiệm được nâng lên thành quy tắc ([arXiv 2603.07670](https://arxiv.org/pdf/2603.07670)). Đề xuất của tôi là trả lời câu hỏi đó bằng một cổng duyệt tương ứng với thiệt hại nếu ghi sai.

| Tầng | Nội dung | Ví dụ trong doanh nghiệp | Cổng duyệt đề xuất |
| --- | --- | --- | --- |
| Episodic | Nhật ký phiên làm việc và trace tool call | Agent đã xử lý đơn hoàn hàng #1042 ngày 12/09 | Ghi tự động, bất biến, chỉ hết hạn theo retention |
| Semantic | Fact và từ vựng của doanh nghiệp | "Đơn trên 50 triệu cần trưởng phòng duyệt" | Vào trạng thái thử, lên chính thức qua cổng thống kê Beta; gắn cửa sổ hiệu lực |
| Procedural | Quy trình thực thi được, có tham số | Playbook 6 bước xử lý khiếu nại giao hàng trễ | Người duyệt bắt buộc, có version và đường rút lui |
| Playbook hành vi | Quy tắc định hướng cách agent hành xử | "Khách hàng doanh nghiệp luôn trả lời bằng giọng trang trọng" | Delta update, review định kỳ |

**Vì sao procedural phải có người duyệt.** Skill là bộ nhớ *thực thi được*: một skill sai không cho một câu trả lời sai, nó tạo ra hành vi sai mọi lần được gọi, rồi agent lại ghép skill mới lên trên nó ([Nakrani](https://alpeshnakrani.com/books/memory-systems/procedural-memory-and-skill-libraries/)). Vì vậy procedural memory cần thứ mà các tầng khác không cần: test, version và đường khai tử.

**Cơ chế sinh skill lấy từ Voyager, nhưng có chốt chặn.** Voyager (NVIDIA + Caltech) cho agent GPT-4 đóng băng tự sinh code cho mỗi nhiệm vụ mới, lưu chương trình thành công vào thư viện skill đánh chỉ mục bằng mô tả ngôn ngữ tự nhiên; agent khám phá được 63 vật phẩm, gấp 3,3 lần baseline, mà không huấn luyện lại ([khảo sát](https://arxiv.org/pdf/2512.16301)). Chốt chặn cần thêm là *induction gating*: một chuỗi tool call chỉ được nâng thành skill khi vượt ngưỡng tỉ lệ thành công trên số lần lặp tối thiểu ([JumpCloud](https://jumpcloud.com/it-index/what-is-procedural-memory-skill-induction)).

**Cách cập nhật playbook lấy từ ACE.** Hai lỗi phải tránh là *brevity bias* (tối ưu về prompt ngắn, chung chung) và *context collapse* (viết lại nhiều lần làm mất chi tiết quan trọng). ACE chống lại bằng cách coi context là tập "bullet" có metadata, cập nhật từng delta cục bộ thay vì viết lại toàn bộ, kèm cơ chế grow-and-refine gộp hoặc cắt các mục trùng theo độ tương đồng ngữ nghĩa ([InfoQ](https://infoq.com/news/2025/10/agentic-context-eng)).

**Một bộ ba agent chạy vòng học, không phải một model.** ACE tách ba vai: Generator thực thi nhiệm vụ bằng playbook hiện tại, Reflector rút bài học từ kết quả, Curator quyết định ghi gì vào context ([arXiv 2510.04618](https://arxiv.org/pdf/2510.04618)). Đề xuất này giữ nguyên ba vai đó và thêm vai thứ tư — **Governor** — là nơi áp chính sách và chặn thay đổi vượt quyền.

**Rủi ro đã có tên trong nghiên cứu.** Memory tiến hóa có nhánh nghiên cứu riêng về quản trị, với các khung như SSGM (Stability and Safety Governed Memory) và các khảo sát về tấn công, phòng thủ trên vòng đời memory ([arXiv 2603.11768](https://arxiv.org/pdf/2603.11768)). Nghĩa là phần quản trị không phải tôi tự nghĩ ra — đã có nền để dựa vào.

## Kiến trúc: chỉ một lớp là của mình

&#91;embedded content: kiến trúc 5 lớp · phần cần xây là lớp giữa\]

Bốn lớp còn lại đều mượn thành phần hoặc thiết kế đã có. Phạm vi phải xây mới chỉ là lớp cá nhân hóa và nền quản trị dưới nó. Vì khách tự chạy hạ tầng, mọi thành phần phải tự host được, nên cả ba hạng dùng chung Postgres kèm pgvector: mượn mô hình song thời gian của Graphiti chứ không dùng graph database, không dùng Zep Cloud hay Mem0 managed. Mọi tool call của agent đi qua `ToolGateway` — xem mục Phòng điều khiển.

## Vòng đời: từ bản basic đến bản đã thích nghi

&#91;embedded content: vòng đời cá nhân hóa · 7 bước, 1 điểm rẽ\]

Luật mới vào trạng thái thử: chỉ giám sát, không áp. Governor cho lên chính thức khi cổng thống kê Beta đạt trên dữ liệu của chính doanh nghiệp; luật chưa đạt không bị xóa mà chờ thêm dữ liệu. Người duyệt bắt buộc khi luật mâu thuẫn luật đang áp, khi nâng lên tri thức chung, và khi muốn bật sớm một luật — bật sớm phải ghi điều khoản rubric. Không có ngoại lệ bỏ qua cổng.

## Phòng điều khiển: ý tưởng thứ hai, gộp vào thay vì tách dự án

Ý tưởng thứ hai là một môi trường nơi nhiều agent của nhiều hãng cùng bàn bạc và làm việc theo vai, còn người dùng đóng vai giám đốc: ra lệnh, theo dõi, can thiệp. Thị trường đã đông ở phần *xem*; hai phần còn trống là nơi dự án đặt sức:

- **(b) Điều khiển hai chiều trong lúc chạy:** chặn một tool call, đổi hướng, dừng hẳn một agent, rút ngân sách.
- **(c) Bàn bạc có cấu trúc và lưu vết:** ai quyết gì, dựa trên bằng chứng nào, phát lại được cả phiên.

**Vì sao gộp.** Phòng điều khiển cho cơ chế học hai thứ còn thiếu: agent thực thi có người giám sát, và phản hồi trực tiếp của con người — mỗi lần chặn là tín hiệu harmful, mỗi lần duyệt là helpful cho tầng playbook. Ngược lại, cơ chế học cho phòng điều khiển chiều sâu mà một dashboard không có: duyệt hay chặn đều đi vào vòng học qua cổng thống kê và rubric. Tách thành hai dự án thì cả hai không kịp mốc.

**Những điều phải chấp nhận.** Agent của các hãng không nói chuyện trực tiếp với nhau; chúng cùng đọc và ghi qua một kênh trung gian. Muốn thấy mọi tool call thì mọi agent phải đi qua một cổng tool duy nhất. Và họp nhiều agent chưa chắc hơn một agent: nghiên cứu MAST trên bảy framework thấy mức cải thiện thường rất nhỏ ([arXiv 2503.13657](https://arxiv.org/abs/2503.13657v2)), nên phần này làm như thí nghiệm có baseline.

**Chuẩn dùng:** MCP cho tool, AG-UI (MIT) cho giao diện, hooks của Claude Code và cơ chế duyệt của OpenAI Agents SDK cho adapter. Core không phụ thuộc chuẩn giao diện nào.

## Lộ trình

Cập nhật 3/10/2026: lộ trình đầy đủ nằm ở Lộ trình — Enterprise Agentic. Lộ trình bốn giai đoạn trước đây vẽ trước khi có spec và chưa có phòng điều khiển; nó được thay bằng sáu giai đoạn, năm cổng, 38 tuần.

| Giai đoạn | Thời gian | Cổng ra |
| --- | --- | --- |
| 1 · Lõi học | 5/10 – 29/11/2026 | Một lệnh chạy bảy điều kiện, tái lập được; ba nền móng phòng điều khiển có test |
| 2a · Cổng tool | 7/12/2026 – 17/1/2027 | Mọi tool call qua proxy MCP; chặn, dừng, trần ngân sách chạy; baseline AppWorld |
| 2b · Học từ thực thi | 25/1 – 14/3/2027, nghỉ Tết 8–14/2 | Agent có học so với baseline; demo hai runtime trong giao diện tối thiểu |
| Nghiên cứu | 22/3 – 18/4/2027 | Không có cổng; bị cắt đầu tiên nếu chậm |
| 3 · Platform | 19/4 – 30/5/2027 | Bản Free chạy công khai; image Pro cài được bằng một lệnh |
| 4 · Phát hành | 31/5 – 27/6/2027 | Rà pháp lý xong; chạy thử trên log doanh nghiệp thật |

Giai đoạn 1 và 2 là phạm vi khóa luận và bài báo tự đặt; giai đoạn 3 và 4 là phần sản phẩm. Giai đoạn 4 đóng gói cả hai bản từ một mã nguồn, không tách nhánh. Mốc cố định, phạm vi co giãn: chậm thì cắt theo thứ tự đã định trong lộ trình, không dời mốc.

## Khóa luận làm nền cho sản phẩm: đồng ý thứ tự, nhưng cắt phạm vi khác

Thứ tự bạn đề xuất đúng. Pro và Enterprise khác Free ở cấu hình và tính năng quản trị, không khác ở cơ chế, nên xây Free trước rồi mở dần là cách duy nhất không phải viết lại. Quy tắc một mã nguồn ở mục trên đã ép đúng thứ tự đó.

Chỗ tôi không đồng ý là lấy *bản free* làm đối tượng nghiên cứu. Bản free là một cách đóng gói — hạn mức, gói, chống lạm dụng — và không có gì trong đó công bố được. Đối tượng nghiên cứu phải là **cơ chế**: lớp cá nhân hóa bốn tầng memory với cổng duyệt phân theo mức thiệt hại nếu ghi sai. Bản free là bản cài tham chiếu của cơ chế đó, không phải bản thân đóng góp.

Cách cắt này giữ cho hai mục tiêu không giẫm chân nhau:

| Thành phần | Khóa luận và bài báo | Sản phẩm |
| --- | --- | --- |
| Cơ chế bốn tầng memory kèm cổng duyệt | Đóng góp chính | Lõi dùng chung cả ba hạng |
| Đo trên benchmark agent công khai | Bằng chứng chính, reviewer kiểm lại được | Không dùng để bán |
| Đo độ khớp với một doanh nghiệp cụ thể | Phụ lục, một ca nghiên cứu | Bằng chứng bán hàng chính |
| Hạn mức, gói, chống lạm dụng | Không đưa vào | Có |
| SSO, RBAC, xuất audit | Không đưa vào | Chỉ Enterprise |

Hai điều về quyền và giấy phép — một đã rõ, một còn phải tính:

- **Sở hữu trí tuệ: đã sạch.** Dự án không nộp cho trường và không nằm trong khuôn khổ đề tài được giao, nên toàn bộ kết quả là của bạn và giấy phép BSL 1.1 chốt được ngay. Giữ sạch thì giữ cho hết: không dùng mã, dữ liệu hay tài nguyên nào của trường trong kho này, và không nộp chính dự án này làm bài tập môn học — đó là hai đường duy nhất khiến quyền sở hữu trở nên tranh cãi về sau.
- **Mâu thuẫn giữa công bố và nguồn đóng.** BSL 1.1 không phải open source theo định nghĩa OSI, và nhiều nơi nộp bài yêu cầu artifact mở để tái lập kết quả. Nghĩa là nếu sau này gửi bài ở nơi yêu cầu artifact mở để tái lập kết quả, một kho BSL có thể không được chấp nhận. Chưa cần xử ngay, nhưng phải giữ cho việc tách sau này rẻ.

Không phải tách hai kho ngay hôm nay. Một kho, hai gói, ranh giới rõ là đủ:

| Thành phần | Gói | Vì sao |
| --- | --- | --- |
| Bốn tầng memory và chính sách chuyển tầng | core, Apache 2.0 | Là cơ chế, tức là phần đóng góp |
| Vòng Generator, Reflector, Curator; delta update; grow-and-refine | core, Apache 2.0 | Lõi thuật toán |
| Induction gating và mô hình phân quyền duyệt theo mức rủi ro | core, Apache 2.0 | Mô hình chính sách là phần nghiên cứu, khác với phần cài đặt nó |
| Bộ đánh giá: BPIC 2015, bộ chuẩn bán tổng hợp, bốn chỉ số | core, Apache 2.0 | Chính là artifact của bài báo |
| Đa tenant, hạn mức, ba hạng gói | platform, BSL 1.1 | Đóng gói thương mại |
| Cài đặt vai trò, SSO, RBAC, xuất audit | platform, BSL 1.1 | Đây mới là thứ bán được |
| Giao diện quản trị, kịch bản triển khai, hạ tầng | platform, BSL 1.1 | Vận hành |

**Một quy tắc duy nhất giữ cho tách được:** platform được import core, core không bao giờ import platform. Phép thử là chạy trọn thí nghiệm BPIC 2015 chỉ bằng gói core với một tệp cấu hình và một mô hình chạy cục bộ — chạy được thì ranh giới là thật. Giữ đúng chiều phụ thuộc này thì khi nào cần hai kho thật, việc tách chỉ là một lệnh cắt lịch sử; để lẫn vào nhau thì phải viết lại.

Một lợi ích ít người tính tới: khóa luận ép bạn làm đúng thứ sản phẩm cần mà hay bị bỏ qua — một baseline đo được và một tập đánh giá cố định. Đó chính là cổng ra của giai đoạn 1, và không có nó thì về sau không chứng minh được với khách rằng agent có học thật hay không. Xuất bản giờ là việc sau: hoàn thành dự án trước tháng 7/2027 đã, còn thời gian thì viết bài. Phần đánh giá vẫn phải làm đúng ngay từ đầu vì nó là bằng chứng bán hàng; thứ có thể để sau chỉ là công viết bài và các thủ tục dành cho phản biện.

## Dữ liệu đánh giá: log công khai thật cộng bộ chuẩn bán tổng hợp

Không có doanh nghiệp thật không chặn gì cả. Dữ liệu chính là **BPI Challenge 2015**: log cấp phép xây dựng thật của năm đô thị Hà Lan, cùng một quy trình, mỗi đô thị một tenant — 1.199, 832, 1.409, 1.053 và 1.156 case, 356 đến 410 loại hoạt động mỗi log ([BPIC 2015, bài số 1](https://www.win.tue.nl/bpi/2015/bpic2015_paper_1.pdf)). Bản trước của mục này chọn BPIC 2019 vì ban tổ chức mô tả 60 công ty con, nhưng log chỉ có 4 mã công ty và một mã chiếm gần hết, nên không dựng được thí nghiệm nhiều tenant; BPIC 2019 chỉ còn dùng để kiểm điều kiện dữ liệu trên loại matching.

Năm đô thị chưa đủ để kết luận thiết kế nào tốt hơn, nên đi kèm một **bộ chuẩn bán tổng hợp**: khám phá mô hình quy trình của từng đô thị thật, rồi sinh nhiều tenant giả bằng cách đổi có kiểm soát một số luật thứ tự, với mức nhiễu và tỉ lệ bỏ bước lấy từ log thật. Bộ chuẩn biết trước đáp án nên trả lời câu "thiết kế nào tốt hơn"; BPIC 2015 thật trả lời câu "kết quả có đứng vững trên dữ liệu thật không". Tài liệu cho điều kiện học từ văn bản là luật Wabo, có hiệu lực đúng thời kỳ của log.

| Bộ dữ liệu | Nội dung | Chứng minh được gì |
| --- | --- | --- |
| BPI Challenge 2015 | 5 đô thị, cùng quy trình cấp phép, 832 đến 1.409 case mỗi nơi | Cá nhân hóa đứng vững trên log thật |
| Bộ chuẩn bán tổng hợp | Sinh từ mô hình quy trình của BPIC 2015, đáp án biết trước, số tenant tùy ý | Thiết kế nào tốt hơn, có khoảng tin cậy |
| AppWorld | 9 ứng dụng, 457 API, 750 task, chấm bằng unit test | Agent thực thi và tầng playbook, giai đoạn 2; so trực tiếp với ACE |
| τ-bench | Agent phải bám chính sách của miền khi làm việc với người dùng mô phỏng | Agent có tuân quy tắc doanh nghiệp hay không |
| [CRMArena-Pro](https://arxiv.org/pdf/2505.18878) | 29.101 bản ghi trên 25 đối tượng Salesforce, cả B2B và B2C | Độ rộng nghiệp vụ, có baseline đã công bố |
| WorkArena++ | Tác vụ trên nền ServiceNow | Agent thao tác trên hệ doanh nghiệp thật |

**Cách biến BPIC 2015 thành bộ đánh giá.** Mỗi đô thị là một tenant. Chia theo thời điểm bắt đầu case: 60% học, 20% hiệu chỉnh, 20% đo; tham số chỉ chỉnh trên phần hiệu chỉnh, phần đo chạy một lần. Đáp án trên dữ liệu thật là luật khám phá trên phần đo, dùng chung cho mọi điều kiện — không điều kiện nào được chấm bằng chính nó.

Bốn chỉ số luôn báo cùng nhau và kèm khoảng tin cậy — precision, recall, tỉ lệ vi phạm, negative transfer — để trả lời hai câu, và câu thứ hai mới là câu quan trọng:

1. **Có rút đúng quy tắc riêng không.** Mỗi đô thị làm cùng thủ tục cấp phép theo lối riêng; agent học đúng luật của tenant mình phục vụ hay không.
2. **Có nhầm sang quy tắc của tenant khác không.** Đây là phép đo mà chưa nơi nào làm cho bài toán này, và nó đúng là nỗi sợ của doanh nghiệp khi mua một khung dùng chung: *negative transfer*. Chứng minh được là không nhầm, bạn có đóng góp riêng cho bài báo và có luận điểm bán hàng mạnh nhất.

**Giới hạn phải nói thẳng.** Log sự kiện không có hội thoại và không có tool call, nên nó chỉ chứng minh được tầng episodic và semantic. Tầng playbook, procedural và phần agent thực thi đo trên AppWorld ở giai đoạn 2.

**Bạn tự duyệt skill thì phải xử lý xung đột lợi ích.** Người duyệt cũng là tác giả hệ thống, lại chỉ có một người, nên không có độ đồng thuận giữa người đánh giá. Ba cách xử, làm đủ cả ba:

- **Giữ việc bạn duyệt ra khỏi đường đo chính.** Đáp án của bộ chuẩn là luật đã cài vào bộ sinh, đáp án của BPIC 2015 là luật khám phá trên phần đo, nên các phép đo chạy hoàn toàn tự động, không qua tay bạn.
- **Viết rubric duyệt thành văn bản trước khi chạy.** Mỗi lần duyệt ghi lại quyết định kèm điều khoản rubric tương ứng. Khi đó việc duyệt kiểm lại được, thay vì là cảm tính của một người.
- **Nhờ duyệt chéo một mẫu ngẫu nhiên.** Thầy hướng dẫn hoặc một bạn cùng lớp duyệt mù khoảng một phần năm số quyết định thủ công; độ đồng thuận kappa phải từ 0,61. Rubric khóa bằng commit trước khi duyệt.

Dù làm đủ ba, vẫn phải ghi câu này vào phần hạn chế: việc duyệt do một người thực hiện, và người đó là tác giả.

**Nút thắt thật là chi phí chạy thí nghiệm, không phải chi phí hạ tầng.** Reflector đọc trace theo lô, còn đường cong khởi động lạnh, bảy điều kiện, năm đô thị cộng bootstrap cần rất nhiều lần chạy. Hạn mức miễn phí của Groq là 200K token mỗi ngày, không đủ. Bạn không có GPU riêng, nên cách đi là dùng hạn mức miễn phí cho khéo:

- **Kaggle là lựa chọn đúng.** 30 giờ GPU mỗi tuần, hai card T4 cộng lại 32 GB VRAM, mỗi phiên tối đa 12 giờ, 20 GB lưu trữ bền, cần xác minh số điện thoại, không cần thẻ ([gpuperhour](https://gpuperhour.com/blog/free-cloud-gpus-and-credits), [GMI](https://www.gmicloud.ai/en/blog/best-free-gpu-cloud-options-for-ai-startups-and-researchers)). Đủ chạy mô hình mở cỡ 8B ở fp16, hoặc cỡ lớn hơn ở dạng lượng tử hóa, phục vụ bằng vLLM.
- **Ưu tiên một tài khoản Kaggle.** Mỗi tài khoản cần một số điện thoại thật để bật GPU; dùng nhiều tài khoản để nhân hạn mức có thể vi phạm điều khoản, nên phải đọc điều khoản Kaggle trước khi dùng tài khoản thứ hai. Đã chốt cách làm: Kaggle, Colab và Lightning AI trước — Colab thêm 15 đến 30 giờ mỗi tuần, Lightning AI 80 giờ mỗi tháng — chỉ đụng tới hai tài khoản Kaggle còn lại nếu thực sự thiếu giờ và điều khoản cho phép. Checkpoint luôn nằm trên R2, để nếu tài khoản bị khóa thì mất giờ GPU chứ không mất kết quả.
- **Reflector không cần mô hình mạnh.** ACE đo được rằng đổi Reflector sang mô hình nhỏ hơn vẫn cho +5,9 thay vì +7,6 trên FiNER. Phần lớn giá trị nằm ở cơ chế, không ở kích thước mô hình.

**Mẹo cắt chi phí lớn nhất: ở giai đoạn 1 không chạy agent, chỉ phát lại trace có sẵn.** Log đã chứa trình tự hoạt động thật, nên Generator không gọi LLM; chỉ Reflector gọi. Cộng thêm bộ nhớ đệm phản hồi, gộp nhiều case vào một lần gọi, và vòng phát triển hằng ngày chạy mô hình nhỏ trên CPU — Kaggle chỉ dành cho lần chạy đầy đủ.

**Phiên 12 giờ không làm mất việc nếu có điểm kiểm tra.** Sau mỗi N case, ghi fact, candidate đang chờ, con trỏ case và bộ nhớ đệm phản hồi rồi đẩy sang R2; phiên sau nạp lại và chạy tiếp. Thiếu bước này thì mỗi lần hết phiên là mất sạch, và đó là lý do phổ biến nhất khiến thí nghiệm trên hạ tầng miễn phí không bao giờ xong.

## Ba hạng gói: thứ bán được là quản trị, không phải vòng học

Vòng học nên cho không ở bản free, vì đó là thứ phải thấy mới tin. Thứ khóa lại là những gì khiến một doanh nghiệp dám đưa nó vào quy trình thật: cổng duyệt theo vai, đường rút lui, xuất audit. Các nền tảng agent đang đóng gói đúng theo trục này — để "an toàn ở mức một người dùng" trong bản free và tính tiền cho "an toàn ở mức tổ chức" ([Gravitee](https://gravitee.io/corpus/gen-942/financial-economics/freemium-models.html)).

| Hạng mục | Free | Pro | Enterprise |
| --- | --- | --- | --- |
| Ai bỏ hạ tầng | Bạn, trên hạ tầng 0 đồng | Khách tự chạy | Khách tự chạy, có dự phòng |
| LLM | Bắt buộc khóa của khách; chế độ xem thử chạy trên trace ghi sẵn, không gọi LLM | Khách bắt buộc tự lo | Khách tự lo, qua gateway riêng |
| Dữ liệu | Không dành cho dữ liệu thật, nói rõ trong điều khoản | Nằm trong hạ tầng khách | Không rời hạ tầng khách, có DPA |
| Quy mô | 1 workspace, 3 agent, 10 skill đã duyệt | Không giới hạn kỹ thuật | Không giới hạn, nhiều môi trường |
| Tầng memory | Episodic giữ 7 ngày, semantic và playbook rút gọn | Đủ bốn tầng | Đủ bốn tầng, thêm ontology riêng theo ngành |
| Vòng học | Chạy theo lịch tuần | Chạy liên tục | Chạy liên tục, ngưỡng tùy chỉnh |
| Quản trị | Log cơ bản, một người duyệt tất cả | Version, rollback, phân vai duyệt | SSO, RBAC, xuất audit, chính sách tùy biến |
| Hỗ trợ | Cộng đồng | Email | Theo hợp đồng |
| Giấy phép | Core Apache 2.0; platform BSL 1.1, không dùng cho mục đích thương mại | Giấy phép thương mại theo chỗ ngồi | Giấy phép thương mại theo hợp đồng |

**Khách hàng mục tiêu** — giả thuyết ngày 3/10/2026, chưa kiểm chứng trên thị trường.

| Gói | Ai | Dấu hiệu nhận ra |
| --- | --- | --- |
| Free | Cá nhân, nhóm nghiên cứu, sinh viên, doanh nghiệp muốn thử trước khi mua | Không dùng dữ liệu thật; tự mang khóa LLM |
| Pro | Doanh nghiệp vừa và nhỏ có quy trình rõ, nhiều phòng ban hoặc chi nhánh, không có đội AI riêng — ví dụ phân phối và bán lẻ chạy ERP, logistics, dịch vụ kế toán, BPO và chăm sóc khách hàng | Có dữ liệu sự kiện từ ERP, CRM hoặc hệ thống ticket; quy trình lặp lại có luật thứ tự; có ít nhất một người IT chạy được Docker và Postgres |
| Enterprise | Tổ chức lớn hoặc ngành bị quản lý chặt: ngân hàng, bảo hiểm, y tế, khối nhà nước | Cần dự phòng, SSO, xuất audit, hợp đồng và DPA riêng |

Pro và Enterprise đều tự vận hành hạ tầng và tự lo LLM; hai gói khác nhau ở dự phòng, quản trị và hợp đồng, không khác ở chỗ ai giữ dữ liệu. Bạn giao image cùng license key, không giao repo; phần platform theo BSL 1.1 nên được bảo vệ bằng giấy phép và hợp đồng, không bằng việc giấu mã. Bước kiểm chứng: phỏng vấn 5 đến 10 doanh nghiệp nhóm Pro về quy trình hay sai luật, nơi dữ liệu đang nằm và mức giá chấp nhận được, song song với giai đoạn 1.

Ba điều ràng buộc kèm theo bảng này:

- **Một mã nguồn, không hai nhánh.** Bản free phải là một tệp cấu hình cộng một lớp kiểm tra giấy phép, không bao giờ là một nhánh riêng. Đây là chỗ dễ sinh nợ kỹ thuật nhất: hai nhánh thì mọi sửa lỗi phải làm hai lần, và sau nửa năm bản free trở thành phiên bản chết.
- **Giới hạn là dữ liệu, không phải mã.** Mỗi hạn mức trong bảng là một bản ghi trong bảng cấu hình gói, đọc lúc chạy. Hard-code một con số nào vào mã nghĩa là mỗi lần đổi chính sách giá phải phát hành lại phần mềm.
- **Chỉ bản free có chi phí biến đổi của bạn.** Pro và Enterprise chạy trên hạ tầng và token của khách nên chi phí biên gần bằng không. Vì vậy toàn bộ phần chống lạm dụng chỉ cần áp cho bản free — nhưng ở đó phải chặt.

## Hạ tầng 0 đồng: trần không do bạn đặt

Giới hạn bản free không phải lựa chọn sản phẩm của bạn, mà là hạn mức của nhà cung cấp. Và hạn mức đó thay đổi: Oracle cắt Always Free từ 4 OCPU/24 GB xuống 2 OCPU/12 GB vào tháng 6/2026, không thông báo trước, buộc người dùng thu nhỏ máy trước 18/8/2026 nếu không muốn bị chấm dứt ([fullmetalbrackets](https://fullmetalbrackets.com/blog/oci-free-tier-breakdown), [SnapDeploy](https://snapdeploy.dev/blog/free-cloud-deployment-platforms-2026-comparison)).

| Lớp | Lựa chọn | Hạn mức | Điều phải biết |
| --- | --- | --- | --- |
| Máy chủ | Oracle Cloud Always Free, ARM Ampere A1 | 2 OCPU, 12 GB RAM, 200 GB đĩa | Free tier duy nhất còn đủ sức chạy thật; cần thẻ, hết chỗ theo vùng, máy nhàn rỗi có thể bị thu hồi |
| Băng thông ra | Oracle | 10 TB mỗi tháng | Rộng nhất trong các hyperscaler |
| Lưu trữ tệp | Cloudflare R2 | Egress không giới hạn | Dung lượng vẫn tính tiền theo GB |
| Cạnh và định tuyến | Cloudflare Workers | 100.000 request mỗi ngày, 10 ms CPU mỗi request | Không chạy được vòng lặp agent, chỉ hợp làm cổng vào |
| Cơ sở dữ liệu | Postgres kèm pgvector, chạy ngay trên VM Oracle | Theo 200 GB đĩa | Neon 0,5 GB và Supabase 500 MB đều tự ngủ khi nhàn rỗi, không hợp cho dịch vụ chạy liên tục |
| LLM miễn phí | Groq | 30 request/phút, 1.000 request/ngày, 200K token/ngày | Trần token chặn trước trần request trên tác vụ ngữ cảnh dài |
| LLM miễn phí | OpenRouter | 20 request/phút, 50 request/ngày; 1.000/ngày sau khi từng nạp 10 USD | Dung lượng quản ở mức toàn cục, mở thêm tài khoản không nhân lên được |
| LLM miễn phí | Gemini Flash | Miễn phí, hạn mức công bố qua AI Studio | Nội dung ở bậc free được dùng để cải thiện sản phẩm Google |

**Gemini bậc free bị loại khỏi vai trò mặc định.** Google đánh dấu nội dung bậc free là dữ liệu dùng để cải thiện sản phẩm của họ ([continuumcode](https://continuumcode.ai/guides/free-llm-api/)). Một khung agentic doanh nghiệp không thể đặt đó làm đường mặc định. Với ngân sách 0 đồng thì không chỉ Gemini bị loại, mà mọi chế độ dùng khóa của bạn đều bị loại: bạn không có đồng nào để chịu chi phí biến đổi. Bản free vì vậy bắt buộc khóa của khách, và phần "xem thử trong năm phút đầu" làm bằng một workspace dựng sẵn phát lại trace đã ghi — người ta thấy đúng vòng học chạy thế nào mà không có một lệnh gọi LLM nào phát sinh.

**Trần thật của bản free là token, không phải request.** 200K token mỗi ngày nghe nhiều, nhưng Reflector đọc trọn trace để rút bài học, nên một vòng học tiêu gấp nhiều lần một lượt chạy agent. Hạn mức bản free vì vậy phải tính theo *số vòng học mỗi tuần*, không theo số câu hỏi mỗi ngày.

**Quy tắc bắt buộc: dựng lại được trong một ngày.** Oracle đã đổi hạn mức mà không báo; phải coi hạ tầng free là thứ có thể biến mất. Toàn bộ hạ tầng viết bằng Terraform hoặc tương đương, ảnh chụp hằng đêm đẩy sang R2, và không dùng dịch vụ quản lý đặc thù của bất kỳ nhà cung cấp nào. Quy tắc này còn phục vụ mục đích thứ hai: cùng một tệp compose chạy được trên máy khách ở bản thương mại, nên bạn chỉ phải bảo trì một kịch bản triển khai.

**Thẻ ảo không dùng được cho Oracle.** Oracle nói thẳng là không nhận thẻ ảo, thẻ trả trước hay thẻ dùng một lần khi xác minh thanh toán; phải là thẻ tín dụng thật, và thẻ ghi nợ chỉ đôi khi qua được ([dev.to](https://dev.to/ashish-codejourney/getting-a-free-oracle-cloud-vps-from-india-the-full-guide-and-the-rupay-wall-nobody-warns-you-4p5o), [itnext](https://itnext.io/why-creating-an-oci-free-tier-account-is-so-hard-and-what-you-can-do-instead-7a06b83ec576)). Vài điều kiện phụ cũng hay làm hỏng đăng ký: không được dùng VPN, địa chỉ phải khớp đúng địa chỉ thanh toán của thẻ, và email tạm bị từ chối tự động. Ngay cả khi qua được, máy ARM thường báo hết dung lượng theo vùng.

**Tất cả phương án, xếp theo yêu cầu về thẻ.**

| Nền tảng | Miễn phí được gì | Thẻ | Dùng vào việc gì |
| --- | --- | --- | --- |
| Oracle Cloud Always Free | 2 OCPU ARM, 12 GB RAM, 200 GB đĩa, 10 TB băng thông ra | Thẻ tín dụng thật; từ chối thẻ ảo, trả trước, dùng một lần | Tốt nhất: cả bản free chạy trên một máy |
| Google Cloud | 1 máy e2-micro (1 vCPU, 1 GB RAM, 30 GB) ở vùng Mỹ vĩnh viễn; Cloud Run 2 triệu request mỗi tháng | Cần thẻ, có giữ tạm một khoản nhỏ; thẻ ảo đôi khi lọt | Dự phòng; 1 GB RAM chỉ đủ phần cổng vào |
| Azure | App Service F1 vĩnh viễn: 60 phút CPU mỗi ngày, 1 GB RAM, không SLA | Cần thẻ; thẻ ảo đôi khi lọt | Chỉ đủ demo, 60 phút CPU mỗi ngày quá chặt |
| AWS | Tín dụng 100–200 USD trong 6 tháng rồi tài khoản free đóng; Lambda vẫn miễn phí | Cần thẻ | Không nên: hết 6 tháng là mất, rơi đúng giữa khóa luận |
| Fly.io | Không còn hạn mức miễn phí cho người mới | Cần thẻ | Không dùng |
| Render | Gói free chạy được container, ngủ khi nhàn rỗi | Không cần thẻ | Phương án không thẻ tốt nhất cho phần chạy agent |
| Railway | Gói free chạy container | Không cần thẻ | Dự phòng cho Render |
| Koyeb | Nay chỉ còn Postgres: 0,25 vCPU, 1 GB RAM, 1 GB đĩa, 5 giờ chạy mỗi tháng | Không cần thẻ | Đã teo, không dựa vào |
| Cloudflare Workers, Pages, R2 | 100.000 request mỗi ngày, 10 ms CPU, egress R2 không giới hạn | Không cần thẻ | Cổng vào, tệp tĩnh, lưu trữ |
| Neon hoặc Supabase | Postgres 0,5 GB hoặc 500 MB, ngủ khi nhàn rỗi | Không cần thẻ | Cơ sở dữ liệu khi không có máy Oracle |

**Trả lời thẳng về thẻ ảo.** Với Oracle thì không, họ ghi rõ không nhận thẻ ảo, trả trước hay dùng một lần. Với AWS, Azure và Google thì có người qua được bằng thẻ ảo hoặc trả trước, nhưng kết quả tùy ngân hàng phát hành và tùy lần kiểm tra, không có gì bảo đảm. Rủi ro thật không nằm ở lúc đăng ký mà ở sau đó: nhà cung cấp kiểm tra lại phương thức thanh toán theo chu kỳ, và một tài khoản bị khóa giữa kỳ làm khóa luận thì mất cả hạ tầng lẫn dữ liệu. Đừng lấy thẻ ảo làm phương án chính, kể cả khi nó lọt.

**Hai kịch bản để chốt.** Mượn được thẻ tín dụng thật thì chọn Oracle và chạy mọi thứ trên một máy. Không mượn được thì Render chạy container, Neon làm Postgres, Cloudflare làm cổng vào và lưu trữ — bản free sẽ ngủ khi nhàn rỗi, chấp nhận được vì chế độ xem thử chỉ phát lại trace, không gọi LLM nên độ trễ khởi động không ảnh hưởng. Cả hai kịch bản đều viết bằng Terraform và compose để chuyển qua lại trong một ngày.

## Chính sách giới hạn bản free: chặn ở tám tầng, không ở một

Công thức free tier kiểu SaaS không sống nổi với sản phẩm AI. Suốt hai thập kỷ, chiến lược free tier dựa trên giả định chi phí biên mỗi người dùng nhỏ đến mức làm tròn được; với sản phẩm mà mỗi tương tác đều tính vào thời gian GPU thì giả định đó sai, và áp dụng nó tạo ra lỗ tăng dần ngay lập tức. Chính các nhà cung cấp inference cũng đã đóng bậc free của họ đầu 2026 ([Tian Pan](https://tianpan.co/blog/2026/04/23/free-tier-abuse-economics-ai-bots)).

Nguyên tắc là chặn ở nhiều mức cùng lúc — người dùng, agent, ứng dụng, nhóm, model, công cụ, tài khoản thanh toán — chứ không dựa vào một hạn ngạch request duy nhất ([Gravitee](https://www.gravitee.io/corpus/gen-2199/revenue-management/freemium-api-strategies.html)).

| Tầng chặn | Giới hạn đề xuất | Chặn được gì |
| --- | --- | --- |
| Tạo tài khoản | Xác minh email tên miền doanh nghiệp, một workspace mỗi tên miền | Mở hàng loạt tài khoản để lách hạn mức |
| Phạm vi | 1 workspace, 3 agent, 10 skill đã duyệt, 1 quy trình mẫu | Dùng bản free làm hệ thống thật |
| Lượt chạy | 20 lượt agent mỗi ngày, 200 mỗi tháng | Tải đều đặn kéo dài |
| Vòng học | 1 vòng mỗi tuần, tối đa 20 ứng viên mỗi vòng | Khoản tốn token lớn nhất của cả hệ |
| Memory | Episodic 7 ngày, 200 fact semantic, 50 bullet playbook | Chi phí lưu trữ và chi phí nạp context phình dần |
| Token | Bắt buộc khóa của khách; không có đường nào tiêu token của bạn | Ngân sách 0 đồng không chịu nổi bất kỳ chi phí biến đổi nào |
| Chi tiêu | Trần cứng bằng 0: mọi đường có thể sinh hóa đơn đều tắt mặc định | Kiểu lạm dụng mà bạn chưa lường trước |
| Ưu tiên | Job bản free vào hàng đợi trễ, nhường bản trả tiền | Bản free làm chậm khách trả tiền |

Bốn quy tắc kỹ thuật đi kèm, để chính sách này không thành nợ về sau:

- **Mỗi request ra ngoài phải quy về đúng một tenant key.** Khi đó khóa một tenant vi phạm là một thao tác thu hồi khóa, không phải một lần triển khai lại, và không ảnh hưởng tenant khác ([dev.to](https://dev.to/xenoncross2718/nodejs-free-tier-abuse-protection-per-tenant-api-keys-and-account-quota-backstops-17d6)).
- **Kiểm hạn mức trước khi tiêu, không phải sau.** Gọi LLM rồi mới đếm là đã mất tiền rồi mới biết.
- **Chặn ở cổng vào, không rải trong mã nghiệp vụ.** Mọi lưu lượng LLM, MCP và A2A đi qua một lớp gateway duy nhất mang sẵn xác thực, chính sách và đo đếm. Rải logic hạn mức khắp nơi là dạng nợ kỹ thuật khó gỡ nhất ở sản phẩm loại này.
- **Chặn việc tạo tài khoản, không chỉ chặn việc dùng.** Phần lớn lạm dụng đến từ mẫu tạo tài khoản hàng loạt, nên điểm chặn hiệu quả nhất nằm ở lúc đăng ký.

Một điểm nhỏ nhưng đáng làm: thông báo "đã hết hạn mức" là đúng về vận hành nhưng yếu về thương mại. Màn hình chạm hạn mức nên nói rõ agent đang học được gì mà bản free không cho chạy tiếp, vì đó đúng là lúc giá trị sản phẩm dễ thấy nhất.

Hai chỉ số cần theo từ ngày đầu: chi phí token trên mỗi lượt đăng ký free, và tỉ lệ chuyển đổi chia theo mức tiêu thụ hạn mức. Chỉ số thứ hai cho biết hạn mức đang đặt quá chặt hay quá lỏng, mà không phải đoán.

## Rủi ro: hệ tự học là thứ khó audit nhất

Rủi ro lớn nhất không phải kỹ thuật mà pháp lý — và nó rơi vào doanh nghiệp dùng sản phẩm, không phải vào tôi. Điều đó phải được thiết kế vào sản phẩm chứ không ghi trong hợp đồng.

**Trách nhiệm thuộc về bên triển khai.** Theo EU AI Act, tổ chức chịu trách nhiệm cho những gì agent của họ làm, và nghĩa vụ của deployer không có đường thoát kiểu "lỗi nhà cung cấp"; tổ chức ngoài EU phục vụ người dùng EU cũng chịu nghĩa vụ tương tự. Việc khách tự chạy hạ tầng không chuyển hết trách nhiệm sang họ: bạn vẫn là bên cung cấp hệ thống, nên tài liệu kỹ thuật, hướng dẫn sử dụng và cơ chế giám sát của con người phải đi kèm sản phẩm chứ không để khách tự dựng. Phần lớn nghĩa vụ còn lại đã có hiệu lực đầy đủ từ 2/8/2026 ([SoftwareSeni](https://www.softwareseni.com/what-the-eu-ai-act-requires-of-organisations-deploying-ai-agents)). Việc hệ thống thuộc nhóm rủi ro cao theo Annex III hay không quyết định khoảng 80% khối lượng tài liệu và kiểm thử ([Indext](https://medium.com/@Indext_Data_Lab/ai-agent-audit-the-complete-2026-governance-and-compliance-guide-aa945b2d2f67)).

**Ba khung không thay thế nhau.** NIST AI RMF là hướng dẫn tự nguyện, không có chế tài, xoay quanh Govern, Map, Measure, Manage. ISO/IEC 42001:2023 là hệ quản trị chứng nhận được, với 38 control trong Annex A chia theo chín mục tiêu. EU AI Act là ranh giới pháp lý. Dùng NIST làm bộ từ vựng rủi ro, ISO 42001 làm xương sống quy trình, AI Act làm mức sàn bắt buộc ([SoftwareSeni](https://www.softwareseni.com/what-the-eu-ai-act-requires-of-organisations-deploying-ai-agents), [Secure Privacy](https://secureprivacy.ai/blog/eu-ai-act-vs-nist-ai-rmf-vs-iso-42001-ai-governance-framework-alignment)).

**Một cảnh báo đáng chú ý.** Phân tích của Cloud Security Alliance chỉ ra ISO 42001 có phạm vi ở cấp tổ chức, nên để trống các nghĩa vụ theo từng hệ thống của Điều 17 AI Act ([CSA](https://labs.cloudsecurityalliance.org/research-rb/csa-whitepaper-eu-ai-act-iso42001-pren18286-compliance-20260/)). Chứng nhận ISO không đủ để coi là tuân thủ.

**Điểm hội tụ của cả ba khung là log bất biến.** Cơ quan quản lý và khách hàng doanh nghiệp giờ yêu cầu bằng chứng vận hành, không chấp nhận ảnh chụp màn hình và bản tự khai ([Indext](https://medium.com/@Indext_Data_Lab/ai-agent-audit-the-complete-2026-governance-and-compliance-guide-aa945b2d2f67)). Với một hệ tự học, câu hỏi audit khó hơn một bậc: không chỉ "agent đã làm gì" mà "vì sao hành vi của nó hôm nay khác hôm qua".

Bốn rủi ro kỹ thuật phải xử lý ngay từ thiết kế:

- **Skill giòn.** Một skill học trong ngữ cảnh này hỏng trong ngữ cảnh khác. Giảm thiểu bằng điều kiện tiên quyết, kiểm tra sau thực thi và versioning để rollback ([Agent Protocol](https://learn.engineering.vips.edu/agent-protocols/agent-procedural-memory-pattern)).
- **Context collapse.** Playbook bị viết lại nhiều lần sẽ mất chi tiết. Bắt buộc dùng delta update, không regenerate toàn bộ.
- **Nhiễm độc memory.** Có cả một nhánh khảo sát về tấn công và phòng thủ trên vòng đời memory của LLM agent. Mọi fact phải mang nguồn, phạm vi và quy tắc hết hạn.
- **Học sai thành chuẩn.** Nếu agent học từ hành vi của nhân viên, nó sẽ học cả lối tắt sai quy trình. Cần cổng duyệt của process owner, không chỉ ngưỡng thống kê.

## Sáu quyết định — phương án chốt

Hai cột cũ là đề xuất và phương án bị loại, để bạn thấy tôi đã cân nhắc gì trước khi chọn. Giờ bạn đã chốt mô hình kinh doanh nên bảng đổi thành phương án chốt kèm ràng buộc phải giữ, vì mỗi ràng buộc bỏ qua là một khoản nợ kỹ thuật.

| Quyết định | Phương án chốt | Ràng buộc phải giữ | Vì sao |
| --- | --- | --- | --- |
| Phạm vi xây | Lớp cá nhân hóa trên bộ điều phối mỏng (LangGraph về sau); memory trên Postgres, mượn mô hình song thời gian của Graphiti | Mọi thành phần phải dựng được bằng một docker compose | Khách tự chạy nên không được phụ thuộc dịch vụ quản lý nào |
| Mục tiêu đầu ra | Bán dịch vụ, khách tự chạy hạ tầng, có demo chạy được | Bản free có trần chi tiêu cứng ở mức tài khoản | Bản free vừa là bản cài tham chiếu cho khóa luận, vừa là kênh phân phối cho bản bán |
| Ngành dọc đầu tiên | Quy trình back-office có SOP rõ: mua hàng, duyệt chi, hoàn hàng | Bản free chỉ mở đúng một quy trình mẫu | Quy trình có SOP cho ground truth để đo agent học đúng hay sai |
| Mức tự chủ ban đầu | Shadow mode: agent đề xuất thay đổi, người duyệt toàn bộ | Mức tự chủ là cấu hình theo hạng gói, không hard-code | Không có baseline tin cậy thì không chứng minh được giá trị |
| Cách đo "đã cá nhân hóa" | Bốn chỉ số theo từng tenant — precision, recall, tỉ lệ vi phạm, negative transfer — cộng đường cong khởi động lạnh | Đo riêng từng tenant, không gộp số chung | Benchmark công khai không đo được độ khớp với một doanh nghiệp cụ thể |
| Mô hình phát hành | Core Apache 2.0; platform BSL 1.1, mỗi bản tự chuyển sang Apache 2.0 sau 2 năm | Core không bao giờ import platform, kiểm bằng import-linter trong CI | Core mở để làm artifact tái lập được; platform là thứ khách tự host nên giấy phép là thứ chặn bán lại |
| Đối tượng nghiên cứu | Cơ chế cá nhân hóa, không phải bản free | Dự án không nộp cho trường; không dùng mã, dữ liệu hay tài nguyên của trường trong kho | Hạn mức và cách đóng gói không phải nội dung công bố được |

Hai câu trước đã có trả lời. Còn lại hai câu mới:

- [x] Nhờ được ai duyệt chéo một mẫu ngẫu nhiên các skill không? Thầy hướng dẫn hoặc một bạn cùng lớp là đủ, và nó nâng hẳn độ tin của phần đánh giá.
- [x] Mượn được thẻ tín dụng thật của người nhà để đăng ký Oracle không? Nếu không thì chốt luôn phương án không cần thẻ, và bản free chuyển sang kiểu ngủ khi nhàn rỗi.
- [x] Đã chốt: cuối tháng 11/2026 phải có lát cắt nhỏ nhất chạy được — một quy trình, một tenant, một vòng học đi hết từ trace đến đề xuất được duyệt. Hạn tổng là trước tháng 7/2027.
- [x] Đã chốt: Kaggle, Colab và Lightning AI trước; hai tài khoản Kaggle còn lại chỉ dùng khi thiếu giờ, và checkpoint luôn để trên R2.
- [x] Bài báo để sau khi xong dự án, nếu còn thời gian. Phần đánh giá vẫn làm đủ ngay từ đầu.

## Bắt đầu từ đâu: giai đoạn 1 theo lộ trình và spec

Việc đầu tiên không phải viết agent, mà là dựng cái thước đo. Kế hoạch từng tuần của giai đoạn 1 (5/10 – 29/11/2026) nằm ở tài liệu Lộ trình; đặc tả chi tiết — lược đồ, vòng học, cổng duyệt, hợp đồng đánh giá — nằm ở tab spec của tài liệu Spec kỹ thuật. Kế hoạch bốn tuần và đặc tả tuần 1 viết ngày 2/10 cho BPIC 2019 đã bị thay bởi hai tài liệu đó.

**Thứ không làm trong giai đoạn 1:** agent thực thi và giao diện (giai đoạn 2), hạ tầng bản free, chính sách gói và hạn mức, lớp quản trị (giai đoạn 3 và 4). Làm một mình thì đây là chỗ dễ mất thời gian nhất, và mất ở đây là mất luôn phần chứng minh được giá trị.

## Nguồn

Chỉ bài ACE được đọc toàn văn. Phần còn lại đọc qua trang tóm tắt và kết quả tìm kiếm, nên các con số thị trường cần kiểm lại từ báo cáo gốc trước khi đưa vào bản nộp.

**Nghiên cứu**

- [Agentic Context Engineering (ICLR 2026)](https://arxiv.org/abs/2510.04618) — Stanford, SambaNova, UC Berkeley. Generator/Reflector/Curator, delta update, grow-and-refine.
- [Memory for Autonomous LLM Agents](https://arxiv.org/pdf/2603.07670) — phân loại working, episodic, semantic, procedural và câu hỏi chuyển tầng.
- [Adaptation of Agentic AI: post-training, memory, skills](https://arxiv.org/pdf/2512.16301) — khảo sát thư viện skill, gồm Voyager.
- [Governing Evolving Memory in LLM Agents (SSGM)](https://arxiv.org/pdf/2603.11768) — rủi ro và cơ chế quản trị memory tiến hóa.
- [Tóm tắt ACE trên InfoQ](https://infoq.com/news/2025/10/agentic-context-eng) — bản rút gọn dễ trích cho phần related work.

**Nền tảng và chuẩn**

- [Best Enterprise Agentic AI Platforms 2026](https://www.marktechpost.com/2026/05/19/best-enterprise-level-agentic-ai-platforms-for-2026/) và [bản tham chiếu mở rộng](https://agentic-ai.readthedocs.io/en/latest/AgentPlatforms/enterprise-platforms-2026/)
- [Agentic AI in Enterprise 2026](https://tech-insider.org/agentic-ai-enterprise-2026-market-analysis/) — số liệu Agentforce và thị phần
- [Copilot Studio: đánh giá agent và phản hồi người dùng](https://www.microsoft.com/en-us/microsoft-copilot/blog/?p=7230)
- [Mem0 vs Zep vs Letta](https://www.agenticwire.news/article/mem0-zep-letta-agent-memory) và [so sánh nhà cung cấp memory 2026](https://www.developersdigest.tech/blog/best-ai-agent-memory-providers-2026)
- [Đánh giá harness trước khi chọn vendor memory](https://www.puppyone.ai/blog/best-ai-agent-memory-platforms)
- [A2A Protocol tròn một năm](https://www.hpcwire.com/off-the-wire/linux-foundation-a2a-protocol-marks-one-year-with-broad-enterprise-and-cloud-adoption/) — Linux Foundation
- [Procedural memory skill induction](https://jumpcloud.com/it-index/what-is-procedural-memory-skill-induction) và [mẫu thiết kế procedural memory](https://learn.engineering.vips.edu/agent-protocols/agent-procedural-memory-pattern)
- [Procedural Memory and Skill Libraries](https://alpeshnakrani.com/books/memory-systems/procedural-memory-and-skill-libraries/) — lập luận skill là bộ nhớ thực thi được

**Quản trị và tuân thủ**

- [EU AI Act với tổ chức triển khai agent](https://www.softwareseni.com/what-the-eu-ai-act-requires-of-organisations-deploying-ai-agents)
- [Đối chiếu EU AI Act, NIST AI RMF, ISO 42001](https://secureprivacy.ai/blog/eu-ai-act-vs-nist-ai-rmf-vs-iso-42001-ai-governance-framework-alignment)
- [CSA: khoảng hở giữa ISO 42001 và Điều 17 AI Act](https://labs.cloudsecurityalliance.org/research-rb/csa-whitepaper-eu-ai-act-iso42001-pren18286-compliance-20260/)
- [AI Agent Audit 2026](https://medium.com/@Indext_Data_Lab/ai-agent-audit-the-complete-2026-governance-and-compliance-guide-aa945b2d2f67)

**Hạ tầng free, hạn mức và giấy phép**

- [Oracle Cloud free tier breakdown](https://fullmetalbrackets.com/blog/oci-free-tier-breakdown) — đợt cắt hạn mức tháng 6/2026 và hạn chót 18/8/2026
- [Free cloud hosting 2026, 14 nền tảng](https://snapdeploy.dev/blog/free-cloud-deployment-platforms-2026-comparison) và [bản đồ hosting miễn phí 2026](https://hatchable.com/articles/state-of-free-web-hosting-in-2026)
- [Hạn mức băng thông ra của các free tier](https://egresscost.com/free-tier-egress/)
- [Free LLM API: giới hạn thật và điều kiện kèm theo](https://continuumcode.ai/guides/free-llm-api/) và [bảng so sánh hạn mức](https://blogs.novita.ai/free-llm-api-comparison-2026/)
- [Kinh tế của free tier khi chi phí là inference](https://tianpan.co/blog/2026/04/23/free-tier-abuse-economics-ai-bots)
- [Freemium cho nền tảng AI agent](https://www.gravitee.io/corpus/gen-2199/revenue-management/freemium-api-strategies.html) và [tiêu chí chia gói](https://gravitee.io/corpus/gen-942/financial-economics/freemium-models.html)
- [Khóa riêng cho từng tenant và trần chi tiêu](https://dev.to/xenoncross2718/nodejs-free-tier-abuse-protection-per-tenant-api-keys-and-account-quota-backstops-17d6)
- [So sánh BSL, AGPL, SSPL, Elastic](https://bike4mind.com/blog/the-license-maze) · [xu hướng giấy phép source-available](https://www.goodwinlaw.com/en/insights/publications/2024/09/insights-practices-moving-away-from-open-source-trends-in-licensing) · [Fair Core License](https://keygen.sh/blog/keygen-is-now-fair-source/) · [open source và open core khác nhau ở đâu](https://oneuptime.com/blog/post/2026-03-03-open-source-vs-open-core-whats-the-difference/markdown)

**Dữ liệu đánh giá công khai**

- [BPI Challenge 2015 — bài báo số 1: số case, số sự kiện, số loại hoạt động từng đô thị](https://www.win.tue.nl/bpi/2015/bpic2015_paper_1.pdf)
- [BPI Challenge 2019](https://data.4tu.nl/articles/dataset/BPI_Challenge_2019/12715853) trên 4TU.ResearchData, và [mô tả quy trình từ ban tổ chức ICPM](https://icpmconference.org/2019/?p=302)
- [τ-bench và τ²-bench](https://arxiv.org/pdf/2609.04611) — agent bám chính sách của miền
- [CRMArena-Pro](https://arxiv.org/pdf/2505.18878) — 29.101 bản ghi trên 25 đối tượng Salesforce
- [So sánh các benchmark doanh nghiệp](https://arxiv.org/pdf/2609.09853) — WorkArena++, CRMArena, Spider 2.0
- [Tổng quan benchmark agent 2026](https://www.automationanywhere.com/company/blog/ai-agent-benchmarks)
- [Oracle và quy định về thẻ khi đăng ký](https://dev.to/ashish-codejourney/getting-a-free-oracle-cloud-vps-from-india-the-full-guide-and-the-rupay-wall-nobody-warns-you-4p5o), [vì sao đăng ký OCI hay hỏng](https://itnext.io/why-creating-an-oci-free-tier-account-is-so-hard-and-what-you-can-do-instead-7a06b83ec576)
- [So sánh free tier của các nền tảng hosting, kiểm tháng 9/2026](https://flaviocopes.com/hosting-free-tiers/) và [free tier của AWS, Azure, Google 2026](https://freetier.co/articles/cloud-provider-free-tiers-2026)
