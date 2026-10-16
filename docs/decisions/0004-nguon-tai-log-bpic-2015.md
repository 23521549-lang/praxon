# 0004 — Nguồn tải log BPIC 2015: 4TU.ResearchData thay cho win.tue.nl

Ngày: 16/10/2026 · Trạng thái: **đã chốt**, chủ dự án duyệt 16/10/2026

**Bối cảnh.** R18 ghi: `www.win.tue.nl` — nơi tải log BPIC 2015 — bị proxy egress từ chối (kiểm ngày 3/10/2026, hai lần), mà bất biến của dự án là log tải lúc chạy, không đóng gói vào kho. R18 ở mức trung bình nên theo quy tắc 9 plan chưa sạch để sang code; hạn xử lý trong plan là trước 5/10/2026, đã quá 11 ngày. Rủi ro chặn plan con 3, 5, 8 và 12.

**Tiêu chí, viết trước khi so.** (a) tính chính thức của nguồn — cùng dữ liệu gốc, không qua trung gian không kiểm được; (b) độ ổn định lâu dài — không phụ thuộc một host mong manh; (c) kiểm chứng được bằng máy — băm và số case đối chiếu được; (d) đi được từ môi trường làm việc hiện tại.

**Các phương án.**

| Phương án | a | b | c | d |
| --- | --- | --- | --- | --- |
| 1 · Giữ `www.win.tue.nl`, mở host trong network access của môi trường | Chính thức | **Yếu** — trang cá nhân của giảng viên, đã chứng minh mong manh bằng chính lần chặn này | Được | **Không đi được** — đã thử hai lần, phụ thuộc môi trường ngoài tầm kiểm soát |
| 2 · Mirror không chính thức (Kaggle datasets, GitHub) | **Không đạt** — không kiểm được nguồn gốc, rủi ro dữ liệu sai lệch | Trung bình | Được | Được |
| 3 · 4TU.ResearchData: 5 dataset riêng từng đô thị, DOI ổn định | **Chính thức** — publisher TU Eindhoven, cùng tác giả van Dongen, parent item BPI Challenge 2015 | **Mạnh nhất** — DOI, có version, dataset Municipality 1 đã có 4.870 lượt tải, nhiều công trình độc lập trích dẫn | Được — task 3.1 vốn đã có kiểm băm, task 3.2 đối chiếu số case với bài báo số 1 | **Đi được** — trang DOI và trang dataset mở được từ môi trường ngày 16/10/2026 |

Năm URL chốt:

- Đô thị 1: `https://data.4tu.nl/articles/dataset/BPI_Challenge_2015_Municipality_1/12709154/1`
- Đô thị 2: `https://data.4tu.nl/articles/dataset/BPI_Challenge_2015_Municipality_2/12697349/1`
- Đô thị 3: `https://data.4tu.nl/articles/dataset/BPI_Challenge_2015_Municipality_3/12718370/1`
- Đô thị 4: `https://data.4tu.nl/articles/dataset/BPI_Challenge_2015_Municipality_4/12697898/1`
- Đô thị 5: `https://data.4tu.nl/articles/dataset/BPI_Challenge_2015_Municipality_5/12713285/1`

**Quyết định.** Phương án 3.

**Vì sao.** Đây không phải phương án chữa cháy mà là nâng cấp: nguồn DOI ổn định hơn trang cá nhân giảng viên — chính lần chặn R18 là bằng chứng đường cũ mong manh. Mọi tiêu chí a–d đều đạt, và không có tiêu chí nào phải đánh đổi. Dùng 5 URL dataset riêng thay vì URL collection chung để mỗi đô thị tải trực tiếp, trích dẫn độc lập.

**Hệ quả.** Được: R18 hạ từ trung bình xuống nhẹ — plan sạch để sang code theo quy tắc 9. Mất: không có; bất biến "tải lúc chạy, không đóng gói vào kho" giữ nguyên. Khó đổi về sau: thấp — chỉ là URL trong task 3.1.

**Hệ quả lên plan.** Task 3.1 đổi lời: tải từ 5 dataset 4TU (URL trong ADR này), kiểm băm, không đóng gói vào kho. Mục R18 trong bảng rủi ro của plan cập nhật cách xử, mức còn lại, dấu hiệu và hạn kiểm theo quyết định này. Dòng trạng thái đầu plan cập nhật: R18 đã xử 16/10/2026.

**Bằng chứng.**

| Khẳng định | Mức | Chi tiết |
| --- | --- | --- |
| 4TU là nguồn chính thức, cùng dữ liệu gốc: publisher TU Eindhoven, parent item BPI Challenge 2015, cùng tác giả van Dongen | **Đã kiểm nguồn** 16/10/2026 | Mở trang DOI `10.4121/uuid:31a308ef-c844-48da-948c-305d167a0ec1` và trang dataset Municipality 1 (`/12709154/1`); trang ghi rõ 5 log file của 5 đô thị Hà Lan, định dạng zip/xml |
| Tải được từ môi trường làm việc hiện tại | **Đã kiểm nguồn** 16/10/2026 | Hai trang trên mở được ngay; `www.win.tue.nl` bị chặn (R18) |
| 5 dataset riêng tồn tại và được dùng rộng rãi | **Đã kiểm nguồn** 16/10/2026 | 5 URL riêng, mỗi URL được nhiều công trình độc lập trích làm nguồn dữ liệu; Municipality 1 có 4.870 lượt tải trên 4TU |
| Nội dung file đúng với log gốc | **Giả thuyết** | Chưa tải file (hàng trăm MB/log). Cách kiểm đã có sẵn trong plan: task 3.1 kiểm băm sau tải, task 3.2 đối chiếu số case 1.199/832/1.409/1.053/1.156 với bài báo số 1 — sai thì cổng bắt, không lọt |

**Cách kiểm bằng máy.** Không thêm cổng mới: task 3.1 (băm khớp giá trị đã ghi) và task 3.2 (số case khớp bài báo số 1) đã là phép kiểm cho nguồn mới. Dấu hiệu theo dõi R18 đổi thành: task 3.1 tải thất bại hoặc băm không khớp.
