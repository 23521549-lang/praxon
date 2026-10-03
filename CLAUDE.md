# Praxon — quy tắc vận hành dự án

Chủ dự án: @ngoc thuan. Bộ quy tắc dưới đây do chủ dự án đặt ngày 3/10/2026 và là **luật của kho này**: phiên làm việc nào cũng đọc trước khi làm, và khi một việc mâu thuẫn với nó thì dừng và hỏi, không tự quyết.

Tài liệu này giữ phần *ràng buộc*. Phần *biểu mẫu* — mẫu spec, mẫu plan, mẫu task, mẫu review, mẫu đề xuất, mẫu bản quyết định kiến trúc — nằm ở [`docs/process/Quy trình làm việc — spec, plan, code.md`](docs/process/Quy%20tr%C3%ACnh%20l%C3%A0m%20vi%E1%BB%87c%20%E2%80%94%20spec,%20plan,%20code.md). Hai tài liệu không lặp nội dung của nhau.

## Dự án đang ở đâu

| Tài liệu | Nội dung |
| --- | --- |
| `docs/product/Enterprise Agentic Framework — Đề xuất kiến trúc tự cá nhân hóa.md` | Định vị, bốn tầng memory kèm cổng duyệt, ba hạng gói, hạ tầng, giấy phép, sáu quyết định đã chốt |
| `docs/roadmap/Lộ trình — Enterprise Agentic.md` | 38 tuần, sáu giai đoạn, năm cổng, thứ tự cắt khi chậm |
| `docs/specs/phase-1-core/Spec kỹ thuật — gói core.md` | Lát cắt tháng 11/2026: lược đồ, vòng học, bảng luật Governor, hợp đồng đánh giá, 17 rủi ro |

**Trạng thái 3/10/2026:** spec giai đoạn 1 đã qua cổng duyệt lần thứ năm (14/14 câu, cả 17 rủi ro ở mức nhẹ). Theo quy tắc 9, bước hợp lệ tiếp theo là **chia plan giai đoạn 1**, chưa phải viết code.

## Chín quy tắc

| # | Quy tắc | Nghĩa cụ thể trong kho này | Vi phạm trông như thế nào |
| --- | --- | --- | --- |
| 1 | **Quy trình: spec → plan → code.** Plan chia thành nhiều plan con, mỗi plan con gồm nhiều task; làm từng task rồi review lặp lại. | Không viết code cho một giai đoạn trước khi spec giai đoạn đó qua cổng *và* plan đã chia xong tới mức task. Task là đơn vị nhỏ nhất có cổng ra riêng. | Mở editor sửa code khi plan chưa có task tương ứng; một task to đến mức không nêu được cổng ra bằng máy |
| 2 | **Review ở mọi bước.** Bước nào cũng phải review và kiểm lại; có sai sót thì quay lại làm lại từ đầu. | Ba cấp review: sau mỗi task, sau mỗi plan con, ở cổng giai đoạn. Mỗi review ghi lại thành văn bản. "Từ đầu" nghĩa là từ đầu của bước chứa sai sót — xem mục *Quay lại từ đầu* dưới. | Task đánh xong mà không có ô review; sửa tại chỗ phát hiện lỗi thay vì quay về bước gây ra lỗi |
| 3 | **Tìm giải pháp mạnh nhất và tối ưu nhất.** Gặp vấn đề thì thảo luận để chọn cách tốt nhất, không lấy cách đầu tiên nghĩ ra. | Mỗi điểm quyết định ràng buộc code về sau: nêu ít nhất hai phương án sống sót cộng phương án bị loại kèm lý do, và viết tiêu chí so sánh *trước* khi so. Chốt rồi thì ghi thành bản quyết định kiến trúc. | Một phương án duy nhất, không có phương án bị loại; tiêu chí nghĩ ra sau khi đã chọn |
| 4 | **Luôn tham khảo trước khi đề xuất.** Dựa vào kiến thức, case thực tế và cách các nền tảng tương tự đã làm, rồi cải tiến cho hợp dự án. | Mỗi đề xuất nói rõ: nền tảng hoặc nghiên cứu nào đã làm việc này, mượn phần nào, sửa phần nào và vì sao dự án cần khác. Nguồn mở được, có ngày đọc. | "Tôi nghĩ nên làm thế này" mà không có nơi nào đã làm; mượn nguyên xi mà không nói đã cân nhắc chỗ không khớp |
| 5 | **Không làm thoái cấp dự án, không để nợ kỹ thuật, tuân thủ clean code.** | *Thoái cấp* = thay đổi làm mất một tính chất đã đạt: một test, một cổng CI, một bất biến, một chỉ số. *Nợ kỹ thuật* = thay đổi mà đã biết trước là phải viết lại. Hai đường duy nhất: làm đúng ngay, hoặc ghi vào danh sách để sau kèm cổng nếu nó không ràng buộc gì về sau. *Clean code* ở kho này là phần kiểm được bằng máy — xem mục *Cổng máy*. | "Tạm tắt test cho qua", "để sau sẽ dọn", hard-code một con số chính sách vào mã, bỏ qua lint một lần |
| 6 | **Tự review trước khi đề xuất.** | Trước khi gửi, tự đọc lại đề xuất theo đúng cổng của bước đó, tự tìm chỗ sai, sửa. Phần nào chưa chạy được phép thử thì nói thẳng là chưa có bằng chứng, không để chủ dự án tự phát hiện. | Đề xuất bị bắt lỗi ngay ở câu hỏi đầu tiên của cổng tương ứng |
| 7 | **Đề xuất phải có bằng chứng.** Có phép thử chạy thật hoặc nguồn đã kiểm, không chỉ trích dẫn. | Ba mức bằng chứng, chỉ hai mức đầu được dùng để quyết — xem mục *Bằng chứng*. Mỗi khẳng định gắn đúng mức của nó. | Con số nhớ lại; link dán vào mà chưa mở; "theo kinh nghiệm thì" |
| 8 | **Chủ dự án duyệt trước khi áp dụng.** Đề xuất kèm checklist, duyệt xong mới áp vào spec. | Không tự thay đổi bất cứ thứ gì trong kho — tài liệu, mã, cấu hình, cấu trúc thư mục — khi chưa được chủ dự án duyệt. Đề xuất trình bằng tin nhắn kèm checklist sáu dòng — xem mục *Đề xuất và duyệt*; duyệt rồi mới ghi tệp. Và duyệt rồi mới `git commit` hay `git push`: không bao giờ commit trong cùng lượt với lúc đề xuất. | Ghi tệp rồi mới hỏi; commit và push trong cùng lượt với lúc đề xuất; tự quyết sửa lịch sử git |
| 9 | **Chỉ sang plan khi spec sạch rủi ro.** Spec không còn rủi ro nghiêm trọng; rủi ro còn lại đều ở mức nhẹ và chấp nhận được. | Chạy cổng spec của giai đoạn đó. Không còn rủi ro mức trung bình hoặc nặng, và mỗi rủi ro còn lại có đủ ba thứ: mức, dấu hiệu theo dõi, hạn kiểm. | Chia plan khi còn một rủi ro trung bình "sẽ xử lý trong lúc code" |

## Quy trình: spec → plan → code

```
spec ──(cổng spec: quy tắc 9)──> plan ──(cổng plan)──> task 1 → review → task 2 → review → …
  ↑                                ↑                      │
  └──── sai ở spec ────────────────┴──── sai ở plan ───────┘
```

- **Spec** một giai đoạn chỉ coi là xong khi qua cổng spec. Cổng của giai đoạn 1 là 14 câu trong `docs/specs/phase-1-core/`; cổng giai đoạn sau viết lại theo cùng lối, và câu nào đã từng bắt được lỗi thì giữ lại cho giai đoạn sau.
- **Plan** chia hai cấp: plan con theo khối việc, task trong plan con. Một task phải nêu được: mục tiêu, tệp nào bị sửa, cổng ra kiểm bằng máy, bằng chứng cần có, ô review. Task không nêu được cổng ra bằng máy thì chia nhỏ tiếp.
- **Code** chỉ chạm đúng phạm vi task đang làm. Việc phát sinh ngoài phạm vi thì ghi vào plan thành task mới, không làm lẫn vào.

### Quay lại từ đầu

Quy tắc 2 nói có sai sót thì làm lại từ đầu. "Từ đầu" là từ đầu của *bước chứa nguyên nhân*, không phải từ đầu dự án:

| Nguyên nhân nằm ở | Làm lại từ | Kéo theo |
| --- | --- | --- |
| Cách cài đặt một task | Task đó | Không gì |
| Cách chia hoặc thứ tự task | Plan con chứa nó | Mọi task đã làm trong plan con bị xét lại, task nào còn đúng thì giữ |
| Một quyết định trong spec | Spec | Chạy lại cổng spec, chia lại plan của giai đoạn, rồi mới code |

Không bao giờ chữa cháy tại chỗ phát hiện ra lỗi nếu nguyên nhân nằm ở bước trước: đó chính là cách sinh nợ kỹ thuật mà quy tắc 5 cấm.

## Review ba cấp

| Cấp | Khi nào | Hỏi gì | Kết quả ghi ở đâu |
| --- | --- | --- | --- |
| Task | Ngay sau khi task xong, trước khi sang task kế | Cổng ra của task có đạt bằng máy không; có phá bất biến nào không; có để lại nợ kỹ thuật nào không; phạm vi có vượt task không | Ô review trong chính task của plan |
| Plan con | Khi hết task của plan con | Plan con đạt mục tiêu của nó chưa; những task đã làm có còn khớp với nhau không; có task nào thành ra vô nghĩa hoặc thiếu | Mục review cuối plan con |
| Giai đoạn | Ở cổng giai đoạn theo lộ trình | Đúng các điều kiện cổng trong lộ trình, đo bằng số hoặc bằng phép thử máy chạy được | Báo cáo cổng trong `docs/plans/<giai-đoạn>/` |

Review không đạt thì không đi tiếp. Review đạt mà không có bản ghi thì coi như chưa review.

## Bằng chứng

| Mức | Thế nào là đủ | Dùng được để quyết |
| --- | --- | --- |
| **Đã chạy thử** | Có lệnh, dữ liệu vào, kết quả ra, và cách chạy lại. Phép thử chạy lại được bởi người khác. | Có |
| **Đã kiểm nguồn** | Nguồn đã mở thật, ghi ngày đọc, trích đúng chỗ nói điều đang khẳng định. | Có |
| **Giả thuyết** | Suy luận, kinh nghiệm, trí nhớ, link chưa mở. | Không — phải ghi rõ là giả thuyết và nêu cách kiểm |

Hai chỗ trong tài liệu hiện có đã đặt chuẩn này: tài liệu đề xuất ghi rõ "chỉ bài ACE được đọc toàn văn… các con số thị trường cần kiểm lại từ báo cáo gốc", và spec ghi ngày chạy thử cho từng thiết kế. Giữ đúng lối đó: mỗi khẳng định mang mức của nó, không trộn lẫn.

## Đề xuất và duyệt

Mỗi đề xuất gửi chủ dự án mang đủ checklist sáu dòng:

1. **Thay đổi gì** — một câu.
2. **Phương án đã cân nhắc** — các phương án sống sót, phương án bị loại, tiêu chí so sánh (quy tắc 3).
3. **Đã tham khảo ai** — nền tảng hoặc nghiên cứu tương tự, mượn gì, sửa gì (quy tắc 4).
4. **Bằng chứng** — từng khẳng định kèm mức: đã chạy thử / đã kiểm nguồn / giả thuyết (quy tắc 7).
5. **Rủi ro mới sinh ra** — mức, dấu hiệu theo dõi, hạn kiểm; nếu có rủi ro trung bình hoặc nặng thì chưa được áp (quy tắc 9).
6. **Chạm vào đâu và rút lui thế nào** — mục nào của spec, plan hay mã bị sửa, và cách quay lại trạng thái cũ.

Chủ dự án duyệt rồi mới áp. Chưa duyệt thì đề xuất nằm ở đề xuất, không chạm vào `docs/product`, `docs/roadmap`, `docs/specs` hay tài liệu này.

## Cổng máy: clean code là phần kiểm được bằng máy

Spec đã chốt nguyên tắc "quy ước nào không kiểm được bằng máy thì không tính". Các cổng dưới đây dựng ở tuần 1 giai đoạn 1 và từ đó áp cho mọi commit; chi tiết cách kiểm nằm ở bảng *Yêu cầu phi chức năng* của spec.

| Cổng | Kiểm cái gì |
| --- | --- |
| import-linter | `core` không import `platform`; SDK mô hình chỉ trong thư mục adapter; driver cơ sở dữ liệu chỉ trong `repositories`; client MCP và SDK agent chỉ trong gateway và adapter |
| mypy strict trên `core` | `Trajectory`, `Insight`, `Delta`, `Candidate`, `Decision` là kiểu có khai báo, không dict thô |
| ruff, ruff format | Lint và định dạng |
| Độ phủ ≥ 85% trên `core` | Áp từ commit đầu tiên, không phải thêm vào sau |
| pip-licenses | Core không phụ thuộc thư viện AGPL, GPL hay không khai giấy phép |
| Test tích hợp RLS | 21 phép tấn công bị chặn, chạy dưới đúng vai ứng dụng |
| Bước CI tìm biến môi trường | `os.environ` và `getenv` chỉ ở module settings |
| Bước CI chặn dữ liệu | Không có `.xes`, `.csv`, `.gz` trong kho ngoài fixture của test |
| Test hiệu năng khám phá | Log giả cỡ đô thị 1, không lọc trước, dưới 30 giây trên CPU |

## Bất biến không bao giờ phá

Lấy từ ba tài liệu, gom về một chỗ. Phá một trong các dòng này là thoái cấp theo quy tắc 5, không phải đánh đổi.

**Ranh giới và giấy phép**

- `core` không bao giờ import `platform`. Phép thử: chạy trọn thí nghiệm BPIC 2015 chỉ bằng `core` với một tệp cấu hình và một mô hình chạy cục bộ.
- Một mã nguồn, không hai nhánh cho bản free và bản bán. Mọi hạn mức là dữ liệu trong bảng cấu hình gói, không hard-code.
- Không dùng mã, dữ liệu hay tài nguyên của trường trong kho này; không nộp dự án này làm bài tập môn học.
- Dữ liệu bên thứ ba — log BPIC, bộ 104 câu — tải lúc chạy, không đóng gói vào kho.
- Phần khám phá Declare viết clean room từ định nghĩa trong bài báo; không mở mã pm4py.

**Dữ liệu và vòng học**

- `episode` và `event` chỉ thêm: không vai nào có UPDATE hay DELETE.
- Chỉ `applier` và `promoter` ghi tri thức, và chỉ áp candidate đã có quyết định. Không có đường ghi tắt.
- Chỉ `promoter` ghi được `global`, dựa vào tên vai cơ sở dữ liệu, không dựa vào biến phiên.
- Không bao giờ viết lại toàn bộ tập fact — mọi thay đổi là delta trên khóa canonical.
- Mỗi vai là một hàm thuần; không vai nào gọi vai khác.
- Mọi tool call đi qua `ToolGateway`; quyết định của người dùng chỉ vào hệ qua `Candidate` kèm `decided_by` và `rubric_clause`.
- Tiên nghiệm một mình không bao giờ đưa luật lên chính thức; kiểm theo từng luật lúc nạp gói.

**Đo lường**

- Ground truth không bao giờ đi qua mô hình, và không điều kiện nào được chấm bằng đáp án sinh từ chính nó.
- Tham số chỉ chỉnh trên phần hiệu chỉnh hoặc trên bộ chuẩn bán tổng hợp. Phần đo khóa bằng `config_hash` và chạy một lần.
- Bốn chỉ số luôn báo cùng nhau kèm khoảng tin cậy, theo từng tenant. Không bao giờ báo tỉ lệ vi phạm một mình.
- Rubric duyệt viết trước và khóa bằng commit, không viết sau khi duyệt.

## Khi chậm thì cắt, không dời mốc

Khẩu phần cố định, phạm vi co giãn. Đến 50% thời gian một giai đoạn mà chưa xong 50% việc cốt lõi thì cầu dao nhảy: cắt phạm vi ngay theo thứ tự đã định sẵn trong lộ trình, không kéo dài và không quyết định cắt gì vào lúc đang gấp.

**Không bao giờ cắt:** baseline và tái lập, cách ly tenant, cổng tool, log chỉ thêm, các cổng CI, rà pháp lý trước khi bán.

Cắt một việc nghĩa là chuyển nó sang danh sách để sau có ghi lý do, không phải làm nó dở dang. Việc dở dang là nợ kỹ thuật.

## Quy tắc commit

- **Commit và push xin phép từng lần.** Không `git commit`, không `git push`, không sửa lịch sử (`amend`, `rebase`, `force-push`) khi chủ dự án chưa đồng ý cho đúng lần đó. Duyệt nội dung không tự động là duyệt commit — hai việc hỏi riêng.
- **Một dòng, một `-m`.** Mỗi commit có đúng một dòng thông điệp, viết bằng một `-m`. Không `-F`, không heredoc, không thân commit nhiều đoạn.
- **Không ghi chính mình vào commit.** Không `Co-Authored-By`, không dòng phiên làm việc, không tên hay định danh mô hình ở bất cứ đâu trong thông điệp. Lịch sử kho ghi *việc gì đã thay đổi*, không ghi *ai hay cái gì đã đánh máy*.
- **Áp cho mọi commit trong kho này**, kể cả commit trên nhánh làm việc rồi gộp vào `main`: gộp chính là lúc dòng attribution lọt vào `main`.
- Thông điệp không gói nổi trong một dòng nghĩa là commit đang gộp nhiều việc. Tách thành nhiều commit, không tách bằng cách viết thêm đoạn.

## Nơi lưu tài liệu

| Đường dẫn | Chứa gì | Ai sửa |
| --- | --- | --- |
| `CLAUDE.md` | Tài liệu này: quy tắc và bất biến | Chỉ sau khi chủ dự án duyệt |
| `docs/process/` | Biểu mẫu: spec, plan, task, review, đề xuất, bản quyết định kiến trúc | Chỉ sau khi chủ dự án duyệt |
| `docs/product/` | Định vị, mô hình gói, quyết định sản phẩm | Chỉ sau khi chủ dự án duyệt |
| `docs/roadmap/` | Giai đoạn, cổng, thứ tự cắt | Chỉ sau khi chủ dự án duyệt |
| `docs/specs/<giai-đoạn>/` | Spec kỹ thuật và cổng spec của giai đoạn | Chỉ sau khi chủ dự án duyệt |
| `docs/plans/<giai-đoạn>/` | Plan con, task, bản ghi review, báo cáo cổng | Chỉ sau khi chủ dự án duyệt |
| `docs/decisions/` | Bản quyết định kiến trúc, mỗi quyết định một tệp, chỉ thêm | Thêm mới được; sửa quyết định cũ thì ghi quyết định mới thay thế |
