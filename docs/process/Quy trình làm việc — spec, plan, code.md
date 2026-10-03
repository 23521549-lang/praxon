# Quy trình làm việc — spec, plan, code

Oct 3, 2026 · @ngoc thuan

Tài liệu này là phần **biểu mẫu** của bộ quy tắc. Phần ràng buộc — chín quy tắc, bất biến, cổng máy, kỷ luật cắt phạm vi — nằm ở `CLAUDE.md` ở gốc kho và không lặp lại ở đây. Khi hai tài liệu có vẻ mâu thuẫn, `CLAUDE.md` thắng.

Mục đích của các mẫu dưới đây: làm cho quy tắc "review ở mọi bước" và "đề xuất phải có bằng chứng" thành thứ kiểm được bằng cách đọc, chứ không phụ thuộc vào việc nhớ.

## Ba bước, ba cổng

| Bước | Sản phẩm | Cổng để đi tiếp | Nằm ở |
| --- | --- | --- | --- |
| Spec | Đặc tả một giai đoạn | Cổng spec: hết câu hỏi, không còn rủi ro trung bình hoặc nặng | `docs/specs/<giai-đoạn>/` |
| Plan | Plan con và task | Cổng plan: 7 câu dưới | `docs/plans/<giai-đoạn>/` |
| Code | Mã, test, bản ghi review | Review task, rồi review plan con, rồi cổng giai đoạn của lộ trình | Kho mã và `docs/plans/<giai-đoạn>/` |

## Cổng spec

Cổng không phải một danh sách cố định: nó lớn dần. Luật là **câu nào đã từng bắt được một lỗi thì ở lại cho mọi giai đoạn sau**. Giai đoạn 1 chạy 14 câu và tiến hóa qua năm lần — câu 11 thêm sau khi bắt được lỗi dữ liệu dựa vào trí nhớ, câu 13 thêm sau khi bắt được lỗi đáp án sinh từ chính điều kiện đang đo, câu 14 thêm khi gộp phòng điều khiển. Bộ 14 câu đó nằm ở mục cuối spec giai đoạn 1 và là điểm bắt đầu cho giai đoạn 2.

Mỗi lần chạy cổng ghi lại thành một bảng trong spec: số câu, câu hỏi, kết quả, và nếu không đạt thì sửa gì. Không ghi kết quả chung "đã review".

Bốn câu khung, luôn có mặt dù giai đoạn nào:

1. Có thành phần nào của bước sau lọt vào bước này không?
2. Có đường nào vòng qua một bất biến đã chốt không?
3. Mỗi khẳng định về dữ liệu đã kiểm trên nguồn gốc, hay chỉ dựa vào mô tả và trí nhớ?
4. Còn rủi ro nào ở mức trung bình hoặc nặng không?

## Cổng plan

Plan qua cổng mới được code. Bảy câu:

1. Mỗi task có cổng ra kiểm được bằng máy chưa? Task nào không có thì chia nhỏ tiếp.
2. Task nào chạm vào bất biến nào? Bất biến đó có test chưa?
3. Thứ tự task có chỗ nào phải làm lại vì phụ thuộc ngược không?
4. Nền móng nào rẻ bây giờ mà đắt về sau, đã nằm đủ sớm chưa?
5. Task nào phụ thuộc hạn mức GPU, giấy phép hay người thứ ba? Có đường đi khi nó trượt không?
6. Việc cốt lõi chiếm bao nhiêu phần khẩu phần? Mốc 50% của cầu dao rơi vào task nào?
7. Thứ tự cắt khi chậm của giai đoạn này đã viết ra trước chưa?

## Mẫu plan con

```markdown
# Plan con <số> — <tên>

**Thuộc giai đoạn:** <giai đoạn> · **Khẩu phần:** <số tuần hoặc số ngày>
**Mục tiêu:** một câu, nói điều gì sẽ đúng sau plan con này mà trước đó chưa đúng.
**Cổng ra của plan con:** đo bằng số hoặc bằng phép thử máy chạy được.
**Bất biến mà plan con này chạm tới:** <liệt kê, trỏ về CLAUDE.md>
**Phụ thuộc:** <plan con hoặc việc bên ngoài phải xong trước>
**Thứ tự cắt khi chậm:** <task nào thu hẹp trước, task nào không bao giờ cắt>

## Task

| # | Task | Cổng ra kiểm bằng máy | Trạng thái | Review |
| --- | --- | --- | --- | --- |
| 1 | | | chưa làm / đang làm / xong / phải làm lại | chưa review / đạt / không đạt |

## Review plan con

**Ngày:** · **Người review:**
- Đạt mục tiêu chưa:
- Các task còn khớp với nhau không:
- Task thành vô nghĩa hoặc còn thiếu:
- Nợ kỹ thuật phát sinh và cách xử:
- Kết luận: đạt / quay lại task nào / quay lại spec
```

## Mẫu task

```markdown
### Task <số> — <tên>

**Mục tiêu:** một câu.
**Phạm vi:** tệp hoặc module được phép sửa. Ngoài danh sách này thì mở task mới.
**Cổng ra:** lệnh chạy được và kết quả mong đợi. Không viết "xong", viết lệnh.
**Bằng chứng cần có:** phép thử nào chạy thật, hoặc nguồn nào phải kiểm.
**Bất biến phải giữ:** <dòng nào của CLAUDE.md>
**Rủi ro liên quan:** <mã rủi ro trong spec, nếu có>

**Review task** — ngày, người review:
- Cổng ra đạt bằng máy: có / không, kèm kết quả
- Có phá bất biến nào: không / có, cái nào
- Nợ kỹ thuật để lại: không / có, xử thế nào
- Phạm vi có vượt task: không / có
- Kết luận: đạt / làm lại task / nguyên nhân ở plan / nguyên nhân ở spec
```

## Mẫu đề xuất gửi chủ dự án

Sáu dòng checklist là bắt buộc, theo đúng thứ tự. Thiếu dòng nào thì đề xuất chưa gửi được.

```markdown
# Đề xuất — <tên>

Ngày: · Áp vào: <spec mục nào / plan nào / mã nào>

1. **Thay đổi gì** — một câu.
2. **Phương án đã cân nhắc**
   | Phương án | Điểm mạnh | Điểm yếu | Chọn hay loại |
   Tiêu chí so sánh (viết trước khi so):
3. **Đã tham khảo ai** — nền tảng hoặc nghiên cứu nào đã làm, mượn gì, sửa gì cho dự án.
4. **Bằng chứng** — mỗi khẳng định một dòng, kèm mức.
   | Khẳng định | Mức | Chi tiết |
   | | đã chạy thử / đã kiểm nguồn / giả thuyết | lệnh và kết quả, hoặc nguồn và ngày đọc |
5. **Rủi ro mới** — mức, dấu hiệu theo dõi, hạn kiểm. Có rủi ro trung bình hoặc nặng thì chưa được áp.
6. **Chạm vào đâu và rút lui thế nào.**

**Tự review trước khi gửi** (quy tắc 6): đã chạy đề xuất này qua cổng nào, tự tìm thấy và sửa gì.
```

## Mẫu bản quyết định kiến trúc

Một tệp cho mỗi quyết định ràng buộc code về sau, đặt ở `docs/decisions/`, đánh số tăng dần, chỉ thêm. Muốn đổi một quyết định cũ thì viết quyết định mới thay thế nó và trỏ ngược lại, không sửa tệp cũ.

Spec giai đoạn 1 đã đặt hàng sẵn một bản: nguồn của từng mẫu Declare, cho yêu cầu clean room.

```markdown
# <số> — <tên quyết định>

Ngày: · Trạng thái: đã chốt / bị thay thế bởi <số>

**Bối cảnh:** vấn đề là gì, ràng buộc nào có thật.
**Các phương án:** gồm cả phương án bị loại và lý do loại.
**Quyết định:** chọn gì.
**Hệ quả:** được gì, mất gì, phần nào khó đổi về sau.
**Bằng chứng:** phép thử hoặc nguồn, kèm mức.
**Cách kiểm bằng máy:** cổng CI hoặc test nào giữ cho quyết định này không bị phá âm thầm.
```

## Nhịp làm việc một task

1. Đọc lại task: mục tiêu, phạm vi, cổng ra.
2. Gặp điểm quyết định thì dừng code, làm theo quy tắc 3 và 4: tham khảo, nêu hai phương án, so theo tiêu chí viết trước. Nếu nó ràng buộc code về sau thì gửi đề xuất và chờ duyệt.
3. Viết test trước hoặc cùng lúc với mã — cổng độ phủ áp từ commit đầu, không thêm vào sau.
4. Chạy đủ cổng máy tại máy mình trước khi coi là xong.
5. Tự review theo mẫu task, sửa những gì tự thấy.
6. Ghi ô review vào plan. Không đạt thì theo bảng *Quay lại từ đầu* của `CLAUDE.md` để biết quay về đâu.
7. Việc phát sinh ngoài phạm vi: ghi thành task mới trong plan, không làm lẫn vào task đang chạy.

## Một task trông thế nào khi làm đúng

Lấy task đầu tiên của plan giai đoạn 1 làm ví dụ, vì spec đã chốt nó: bảng hồ sơ năm đô thị BPIC 2015.

- **Cổng ra bằng máy:** một lệnh sinh ra bảng hồ sơ từ log tải lúc chạy — số case, số sự kiện, số loại hoạt động, phân phối theo thời gian, các thuộc tính phân loại có mặt — chạy lại cho đúng bảng đó.
- **Bằng chứng:** số case của năm đô thị đối chiếu với bài báo số 1 của BPIC 2015, là nguồn đã kiểm; phần còn lại là phép thử chạy thật trên log gốc.
- **Bất biến phải giữ:** log không đóng gói vào kho; bước CI chặn `.xes`, `.csv`, `.gz` ngoài fixture.
- **Rủi ro liên quan:** R2 mức khác biệt giữa năm đô thị, R4 thuộc tính phân loại nào có thật, R14 phân phối theo thời gian, R15 số hoạt động còn lại sau lọc.
- **Điểm quyết định đã chốt trước:** năm đô thị khác nhau ít không phải lý do dừng, mà là một kết quả cần báo cáo. Chỉ dừng và quay về spec nếu log hỏng hoặc thiếu trường bắt buộc.

Task này nêu được cả năm dòng trên trước khi viết dòng mã đầu tiên. Task nào không nêu được thì chưa đủ nhỏ hoặc spec còn thiếu.
