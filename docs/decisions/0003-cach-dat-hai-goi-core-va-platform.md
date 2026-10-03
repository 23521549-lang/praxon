# 0003 — Cách đặt hai gói core và platform

Ngày: 3/10/2026 · Trạng thái: **đã chốt**, chủ dự án duyệt 3/10/2026

**Bối cảnh.** Task 1.1 của plan nói dựng "cấu trúc gói `core/` và `platform/`". Làm đúng chữ đó thì gói `platform` ở cấp cao nhất **đè module `platform` của thư viện chuẩn Python**. Phép thử ngày 3/10/2026 cho thấy nó đè *tùy cách gọi*: khi `src/` nằm đầu `sys.path` — chạy từ thư mục kho, và pytest ở chế độ import `prepend` mặc định — thì `import platform` trỏ vào gói dự án và `platform.python_version()` báo AttributeError; khi `src/` nằm cuối, kiểu editable install, thì stdlib thắng và mọi thứ chạy. Hỏng không ổn định theo cách gọi là loại lỗi khó tìm nhất.

Ngoài ra còn hai ràng buộc có sẵn: hai gói mang **hai giấy phép khác nhau** (core Apache 2.0, platform BSL 1.1), và spec đặt một phép thử ranh giới cụ thể — *"chạy trọn thí nghiệm BPIC 2015 chỉ bằng gói core với một tệp cấu hình và một mô hình chạy cục bộ — chạy được thì ranh giới là thật."*

**Tiêu chí, viết trước khi so.** (a) có đè thư viện chuẩn không; (b) phép thử ranh giới của spec có kiểm được bằng máy không; (c) tách thành hai kho về sau rẻ không; (d) chi phí dựng bây giờ.

**Các phương án.**

| Phương án | a | b | c | d |
| --- | --- | --- | --- | --- |
| 1 · `src/core/` và `src/platform/` ở cấp cao nhất, đúng chữ tài liệu | **Đè stdlib** — đã chứng minh | Trung bình | Rẻ | Rẻ |
| 2 · Một distribution, hai gói con: `praxon/core/` và `praxon/platform/` | Không đè — `platform` chỉ tới được qua `praxon.platform` | **Yếu** — một `pip install` kéo cả hai, nên "chỉ bằng core" chỉ chứng minh được bằng import-linter cộng một test không import `praxon.platform`, không chứng minh được ở mức cài đặt | Rẻ — di chuyển một thư mục | Rẻ |
| 3 · Hai distribution trong một kho: `src/praxon_core/` và `src/praxon_platform/`, mỗi gói một `pyproject.toml` và một tệp giấy phép | Không đè | **Mạnh nhất** — cài `praxon-core` một mình vào môi trường trống rồi chạy thí nghiệm. Đó đúng là phép thử spec đòi, và nó thành một bước CI | Rẻ nhất — mỗi gói đã là một distribution độc lập, tách kho là chuyển thư mục | Đắt hơn: hai `pyproject.toml`, hai lần cài trong CI |

**Quyết định.** Phương án 3.

**Vì sao.** Dự án đã chốt nguyên tắc "quy ước nào không kiểm được bằng máy thì không tính". Phép thử ranh giới của spec chỉ *thực sự* kiểm được bằng máy ở phương án 3: dựng một môi trường trống, `pip install praxon-core`, chạy thí nghiệm, và nếu nó cần bất cứ thứ gì của platform thì bước đó đỏ. Phương án 2 chỉ kiểm được ở mức import, tức là vẫn phải tin rằng import-linter cấu hình đúng — mà ADR 0002 vừa chỉ ra chính cổng đó có thể âm thầm không khớp gì. Thêm nữa, hai giấy phép khác nhau trên hai distribution riêng là thứ không gây tranh cãi khi rà pháp lý ở giai đoạn 4, còn hai thư mục trong một distribution thì phải giải thích.

**Hệ quả.** Được: phép thử ranh giới thành một bước CI thật; giấy phép rõ; tách kho về sau là chuyển thư mục. Mất: hai `pyproject.toml` phải giữ cho khớp phiên bản Python và bộ công cụ; CI cài hai lần nên chậm hơn khoảng một bước. Khó đổi về sau: **cao** — đây là quyết định định hình mọi đường import, nên phải chốt trước khi viết dòng mã đầu tiên.

**Hệ quả lên plan.** Task 1.1 đổi lời: dựng `src/praxon_core/` và `src/praxon_platform/`, mỗi gói một `pyproject.toml` và một tệp giấy phép. Thêm một task 1.8: bước CI cài `praxon-core` một mình vào môi trường trống và khẳng định nó import được mà không có `praxon_platform` — đây là phép thử ranh giới của spec, và nó thuộc nhóm "không bao giờ cắt".

**Bằng chứng.**

| Khẳng định | Mức | Chi tiết |
| --- | --- | --- |
| Gói `platform` cấp cao nhất đè stdlib khi `src/` ở đầu `sys.path`, và `platform.python_version()` báo AttributeError | **Đã chạy thử** 3/10/2026 | Dựng `src/platform/__init__.py` trong thư mục tạm, chạy hai lần với `sys.path.insert(0, "src")` và `sys.path.append("src")`, in `platform.__file__` của mỗi lần |
| pytest mặc định chèn rootdir vào đầu `sys.path` (chế độ `prepend`), nên tình huống hỏng là tình huống thường gặp, không phải ngoại lệ | **Giả thuyết** | Tôi chưa mở tài liệu pytest trong lần soát này. Cách kiểm: chạy pytest thật trên cấu trúc phương án 1 và xem có hỏng không — nhưng không cần kiểm nếu chọn phương án 3 |

**Cách kiểm bằng máy.** Bước CI cài `praxon-core` một mình vào môi trường trống, `python -c "import praxon_core"` phải chạy, và `python -c "import praxon_platform"` phải thất bại. Cộng một test khẳng định không có gói nào ở cấp cao nhất trùng tên một module của thư viện chuẩn.
