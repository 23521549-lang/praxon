"""Khám phá Declare tự viết clean room trong `praxon_core`.

Viết từ định nghĩa hình thức trong bài báo, không mở mã pm4py và không phụ
thuộc pm4py — bất biến này ghi trong spec và CLAUDE.md. Mọi khám phá chạy qua
chỉ mục vị trí đầu/cuối của mỗi hoạt động trong mỗi trace, để một lần duyệt
thẳng không phải quét lại trace cho từng cặp hoạt động.
"""
