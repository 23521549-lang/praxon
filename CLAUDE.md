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

## Mười quy tắc

_Quy tắc 10 do chủ dự án duyệt bổ sung ngày 16/10/2026, sau sự việc spike JSONL ngoài plan._

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
| 10 | **Spike ngoài plan phải có kỷ luật.** Code thăm dò viết ra khi chưa có task tương ứng trong plan thì nằm ở nhánh `spike/<tên>`, kèm một dòng ghi nó trả lời câu hỏi nào của plan con nào. | Muốn vào `main` phải bổ sung task vào plan (plan amendment) rồi đi đủ spec → plan → code và review 3 cấp như mọi code khác; spike bị đánh giá loại thì xóa nhánh. | Nhánh `feat/` chứa code không có task trong plan; merge spike khi chưa qua plan amendment; giữ spike mồ côi không ai đánh giá. |