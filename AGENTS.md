# AGENTS.md

Your operating manual for this workspace, written by you. Your main instructions cover how you work in general. This file is where you keep the specific, durable lessons and conventions you pick up as you work, the kind of thing you'd want a future session to know. It's not about the user (that goes in `USER.md` and your memory) or your personality (that's `SOUL.md`); it's about how you get work done here.

## Conventions
Add an entry whenever you work something out worth keeping, for example:
- a convention you've settled on ("keep data exports in `workspace/exports/` and clean them up monthly")
- a tool or site quirk worth remembering ("site X hides its form behind a cookie banner; dismiss it first")
- a workflow that worked, or a mistake not to repeat

It starts empty and is meant to grow slowly. Don't pad it; a short, accurate file beats a long, stale one.

## Yêu cầu của Thuận — luật cứng (tổng hợp từ CLAUDE.md của praxon, 17/10/2026)

Nguồn gốc: `praxon/CLAUDE.md` (chủ dự án đặt 3/10/2026) — áp cho mọi dự án của Thuận, không chỉ praxon.

### 1. Quy trình phê duyệt — KHÔNG BAO GIỜ tự ý làm
- Mọi việc theo đúng thứ tự: **đề xuất → Thuận duyệt → mới làm**. Không có ngoại lệ ngầm.
- **Một duyệt chỉ bao đúng việc được nêu tên.** Không suy diễn "cùng cụm nên chắc cũng được". Không lấy duyệt A để bao việc B. (Bài học 17/10: tự ý sửa V5/slug fix khi chỉ được duyệt V4.)
- **Trước mọi write/push, tự hỏi 3 câu:** Thuận đã duyệt CỤ THỂ việc này chưa? Mình có đang suy diễn từ duyệt khác không? Không chắc 100% → DỪNG, trình đề xuất, chờ duyệt.
- **Duyệt nội dung ≠ duyệt commit/push.** Hai việc hỏi riêng. Không commit/push trong cùng lượt với lúc đề xuất.
- Đề xuất trình bằng **checklist 6 dòng** (từ CLAUDE.md):
  1. Thay đổi gì — một câu.
  2. Phương án đã cân nhắc — các phương án sống sót, phương án bị loại, tiêu chí so sánh viết TRƯỚC khi so.
  3. Đã tham khảo ai — nền tảng/nghiên cứu tương tự, mượn gì, sửa gì, vì sao cần khác.
  4. Bằng chứng — từng khẳng định gắn mức: đã chạy thử / đã kiểm nguồn / giả thuyết.
  5. Rủi ro mới sinh ra — mức, dấu hiệu theo dõi, hạn kiểm.
  6. Chạm vào đâu và rút lui thế nào — file nào bị sửa, cách quay lại trạng thái cũ.

### 2. Không ẩu — review phải thật, không qua loa
- Đọc spec và plan **nguyên văn** trước khi làm, không làm theo trí nhớ.
- Review = tự tấn công vào chỗ hiểm trên hệ thật, không chỉ đọc lướt code.
- Tìm case thực tế trên mạng khi cần (checklist audit, kỹ thuật tấn công đã biết, cách nền tảng tương tự đã làm).
- Phát hiện lỗi thì **báo trước, đề xuất sau, chờ duyệt** — không tự sửa rồi báo sau.
- **Quay lại từ đầu khi lỗi nằm ở bước trước**: không chữa cháy tại chỗ phát hiện. Nguyên nhân ở task → làm lại task; ở plan → chia lại plan; ở spec → chạy lại cổng spec.

### 3. Bảo mật
- **Không bao giờ hard-code credential/secret** dưới mọi hình thức, kể cả "dev-only". Mật khẩu qua biến môi trường, sinh ngẫu nhiên, hoặc secret của CI.

### 4. Clean code = kiểm bằng máy, không thoái cấp, không nợ kỹ thuật
- Mọi thay đổi phải qua hết cổng máy của repo (lint, typecheck strict, test, coverage) trước khi trình. Không hạ chuẩn để cho qua.
- **Thoái cấp** = làm mất một thứ đã đạt (test, cổng CI, bất biến, chỉ số). Phá bất biến là thoái cấp, không phải đánh đổi.
- **Nợ kỹ thuật** = thay đổi mà đã biết trước phải viết lại. Hai đường: làm đúng ngay, hoặc ghi vào danh sách để sau.
- "Tạm tắt test cho qua", "để sau sẽ dọn", hard-code số chính sách vào mã, bỏ qua lint một lần — tất cả đều cấm.

### 5. Danh tính và quy tắc commit
- Trên mọi repo của Thuận: chỉ hành động dưới danh nghĩa Thuận (23521549-lang / Huỳnh Ngọc Thuận). Không để lộ danh tính trợ lý ở commit, docs, tin nhắn, PR. Không Co-Authored-By, không attribution, không tên/định danh mô hình.
- **Commit xin phép từng lần**: không commit/push/amend/rebase/force-push khi Thuận chưa đồng ý cho đúng lần đó.
- **Một dòng, một `-m`**: thông điệp commit một dòng duy nhất, tiếng Anh, conventional commits. Không `-F`, không heredoc. Thông điệp không gói nổi trong một dòng = commit đang gộp nhiều việc → tách commit.

### 6. Chất lượng đề xuất và giải pháp
- Đề xuất phải chắc chắn, có minh chứng — không "nói khơi khơi".
- **Ba mức bằng chứng**, chỉ hai mức đầu dùng được để quyết:
  - Đã chạy thử (có lệnh, dữ liệu vào, kết quả ra, cách chạy lại).
  - Đã kiểm nguồn (nguồn đã mở thật, ghi ngày đọc, trích đúng chỗ).
  - Giả thuyết (suy luận/kinh nghiệm/trí nhớ/link chưa mở) — phải ghi rõ là giả thuyết và nêu cách kiểm.
- Giải pháp phải mạnh và tối ưu; mỗi điểm quyết định nêu **ít nhất 2 phương án sống sót + phương án bị loại + tiêu chí so sánh trước khi so**.
- Tự review kỹ trước khi trình Thuận. Khi Thuận đã duyệt một hướng thì GIỮ NGUYÊN TUYỆT ĐỐI, không tự ý đổi/thay bằng bản khác.

### 7. An toàn khi làm việc
- Cẩn thận với quyền network đầy đủ: không cài gì đáng ngờ, không làm hại máy/repo của Thuận.
- Package tải về phải ghim version hoặc hash, nguồn rõ ràng.
- Thao tác nguy hiểm (xóa nhánh, force-push, merge) chỉ làm khi có "bảo hiểm": backup trước (git bundle), kiểm tra kỹ trước khi push.

### 8. Quy trình làm việc (spec → plan → code)
Mọi thay đổi đi theo đúng thứ tự này, không nhảy cóc:
1. **Spec**: đọc spec nguyên văn, hiểu bất biến/yêu cầu. Spec chỉ xong khi qua cổng (không còn rủi ro trung bình/nặng).
2. **Plan**: chia plan con → task. Mỗi task phải nêu được: mục tiêu, file bị sửa, cổng ra kiểm bằng máy, bằng chứng, ô review. Task không nêu được cổng ra bằng máy thì chia nhỏ tiếp. Không tự bịa task.
3. **Đề xuất**: theo checklist 6 dòng (mục 1), Thuận duyệt mới làm.
4. **Code**: trên nhánh mới riêng (`<loại>/<mô-tả>`, không prefix lạ). **Chỉ chạm đúng phạm vi task đang làm** — việc phát sinh ngoài phạm vi thì ghi thành task mới, không làm lẫn vào. Không commit vào `main`.
5. **Review 3 cấp** (review không đạt thì không đi tiếp; đạt mà không có bản ghi thì coi như chưa review):
   - Cấp 1 — sau mỗi task: cổng ra đạt bằng máy không? có phá bất biến nào không? có nợ kỹ thuật không? phạm vi có vượt task không?
   - Cấp 2 — sau mỗi plan con: đạt mục tiêu chưa? các task còn khớp nhau không? có task nào vô nghĩa/thiếu không?
   - Cấp 3 — Thuận review ở cổng giai đoạn: trình báo cáo trung thực (đúng/sai/thiếu), chờ kết luận.
6. **Merge**: chỉ khi Thuận cho phép rõ ràng, sau khi review 3 cấp xong.
