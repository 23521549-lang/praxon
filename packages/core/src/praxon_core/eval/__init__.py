"""Đánh giá (plan con 8): bốn chỉ số, khoảng tin cậy bootstrap, kappa duyệt chéo.

Bốn chỉ số luôn báo cùng nhau, theo từng tenant và từng điều kiện (spec:
bảng bốn chỉ số). Khoảng tin cậy 95% tính bằng bootstrap trên case. Kappa
Cohen đo mức đồng thuận của hai người duyệt chéo mù.

Ngoài ra gói này có bài đo F1 trích mẫu Declare từ văn bản trên bộ 104 câu
(task 6.5, `text_to_ltl`): F1 theo từng mẫu Declare + F1 tổng (micro).

Mọi hàm trong gói này là hàm thuần: nhận dữ liệu giả trong test, không gọi
mô hình, không chạm cơ sở dữ liệu.
"""
