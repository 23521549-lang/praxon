# 0002 — Phạm vi test âm cho cổng máy

Ngày: 3/10/2026 · Trạng thái: **đã chốt**, chủ dự án duyệt 3/10/2026

**Bối cảnh.** `CLAUDE.md` đòi clean code là phần kiểm được bằng máy, và spec đòi mỗi yêu cầu phi chức năng có một cách kiểm tự động. Cả hai nói cổng phải *chạy*; không chỗ nào đòi chứng minh cổng **chặn được**. Một cổng chạy mà không chặn gì thì tệ hơn không có cổng, vì nó tạo cảm giác an toàn. Spec đã nêu đúng một ca như vậy: thiếu dòng `include_external_packages = True` thì luật import-linter về thư viện bên ngoài không chạy, mà CI vẫn xanh.

"Test âm" ở đây nghĩa là: cố tình tạo một vi phạm, xác nhận cổng trả mã khác 0, rồi bỏ vi phạm đi.

**Tiêu chí, viết trước khi so.** (a) chi phí tính bằng số việc thêm; (b) có bắt được lớp lỗi thật nào không; (c) có tiền lệ ở công cụ cùng loại không.

**Các phương án.**

| Phương án | a | b | c |
| --- | --- | --- | --- |
| Không test âm | 0 | Không bắt gì. Hợp đồng import-linter viết sai cú pháp, hoặc script grep có regex không khớp gì, đều xanh | Không |
| Test âm cho **mọi** cổng | ~7 việc | Bắt được, nhưng một phần là kiểm tra nhà sản xuất: mypy, ruff và coverage đã có bộ test riêng của chúng | Quá mức |
| Test âm chỉ cho cổng **có logic do dự án viết** | ~4 việc | Bắt đúng chỗ dễ sai nhất: 4 hợp đồng import-linter, pip-licenses khớp theo từ khóa, hai script grep | Đúng tinh thần |

**Quyết định.** Phương án 3. Test âm bắt buộc cho: bốn hợp đồng import-linter, bước pip-licenses, script tìm `os.environ`/`getenv`, script chặn `.xes`/`.csv`/`.gz`. Không bắt buộc cho mypy strict, ruff, ruff format và cổng độ phủ — các công cụ này không có cấu hình do dự án tự viết mà có thể âm thầm không khớp gì.

**Hệ quả.** Được: mỗi cổng do dự án tự viết đã từng thấy đỏ một lần, nên biết nó hoạt động. Mất: khoảng bốn việc nhỏ ở plan con 1. Khó đổi về sau: thấp.

**Bằng chứng — đã kiểm nguồn, 3/10/2026.** Đây không phải cơ chế tôi tự nghĩ ra; hai công cụ gần nhất với thứ dự án đang xây đều đòi hoặc khuyến nghị đúng việc này:

- **ESLint `RuleTester`** *bắt buộc* mỗi luật có ít nhất một ca `valid` và một ca `invalid`; thiếu ca `invalid` thì bộ test không chạy được. Một luật lint không có ca sai thì không được coi là đã test.
- **OPA / Rego** khuyến nghị tệp test có cả ca `allow` và ca `deny`, chạy bằng `opa test`, và nguyên tắc là không bỏ qua bước test cho bất kỳ policy nào.

Cái tôi **không** kiểm được: không mở được nguồn gốc nào về mutation testing trong lần soát này, nên không dẫn nó làm căn cứ.

**Cách kiểm bằng máy.** Mỗi cổng trong danh sách bắt buộc có một test tự tạo vi phạm trong thư mục tạm, chạy cổng, khẳng định mã thoát khác 0, rồi dọn. Thiếu một test âm thì bộ test của plan con 1 báo đỏ.

**Nguồn**

- [ESLint — custom rule tutorial và RuleTester](https://eslint.org/docs/head/extend/custom-rule-tutorial)
- [typescript-eslint — Rule Tester](https://github.com/typescript-eslint/typescript-eslint/blob/main/docs/architecture/Rule_Tester.mdx)
- [Open Policy Agent — Policy Testing](https://openpolicyagent.org/docs/policy-testing)
- [OPA Rego policy unit tests](https://oneuptime.com/blog/post/2026-02-09-opa-rego-policy-unit-tests/view)
