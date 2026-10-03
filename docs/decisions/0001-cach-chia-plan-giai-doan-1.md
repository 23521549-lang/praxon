# 0001 — Cách chia plan giai đoạn 1

Ngày: 3/10/2026 · Trạng thái: **đã chốt**, chủ dự án duyệt 3/10/2026

**Bối cảnh.** Spec giai đoạn 1 qua cổng lần 5 nên bước tiếp là plan. Lộ trình đã chốt tám tuần và việc chính mỗi tuần. Câu còn lại: chia thành bao nhiêu đơn vị review, và đơn vị đó là tuần hay khối việc.

**Tiêu chí, viết trước khi so.** (a) review có đúng ranh giới khối việc không; (b) mốc cầu dao 50% có rơi đúng ranh giới một đơn vị không; (c) đọc để duyệt có dễ không.

**Các phương án.**

| Phương án | a | b | c |
| --- | --- | --- | --- |
| 8 plan con, mỗi tuần một plan con | Kém — tuần 1 gộp CI, lược đồ Postgres và hồ sơ dữ liệu vào một lần review, ba khối không liên quan nhau | Đạt | Tốt |
| 13 plan con theo khối việc, gắn vào tuần | Đạt | Đạt — rơi đúng cuối plan con 9 | Trung bình, nhiều mục hơn |
| Chia theo vai của vòng học (Generator, Reflector, …) | Kém — CI, lược đồ và bộ đánh giá không thuộc vai nào | Không xác định được | Kém |

**Quyết định.** 13 plan con theo khối việc. Plan con là đơn vị review, tuần là khẩu phần.

**Hệ quả.** Được: review đúng ranh giới, cầu dao rơi đúng chỗ. Mất: 13 điểm review thay vì 8, nhiều phí hơn. Khó đổi về sau: thấp — gộp hay tách plan con chỉ là sửa tài liệu, không ràng buộc mã.

**Một quyết định phụ: một tệp hay 13 tệp.** Mẫu trong `docs/process` hàm ý mỗi plan con một tệp. Chọn một tệp cho cả giai đoạn, vì 13 tệp gần như rỗng thì khó duyệt và tham chiếu chéo nặng. Đây là chỗ có thể thành nợ: nếu một plan con phình ra thì tách tệp. Dấu hiệu phải tách: một plan con vượt 10 task, hoặc tệp vượt 600 dòng.

**Bằng chứng.** Số plan con, số task và số ô review đếm bằng script trên chính tệp plan: 13 plan con, 65 task, 13 ô review — **đã chạy thử**. Nguyên tắc khẩu phần cố định lấy từ lộ trình của chủ dự án, vốn dẫn Shape Up; tôi **không mở được nguồn gốc** (basecamp.com bị chính sách mạng chặn) nên không tự khẳng định nó, chỉ thừa nhận là quyết định sẵn có của dự án.

**Cách kiểm bằng máy.** Script đếm plan con, task và ô review; báo đỏ nếu một plan con có task thiếu cổng ra, hoặc có task mà thiếu ô review.
