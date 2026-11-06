"""Đánh giá (plan con 8): bốn chỉ số, khoảng tin cậy bootstrap, kappa duyệt chéo.

Bốn chỉ số luôn báo cùng nhau, theo từng tenant và từng điều kiện (spec:
bảng bốn chỉ số). Khoảng tin cậy 95% tính bằng bootstrap trên case. Kappa
Cohen đo mức đồng thuận của hai người duyệt chéo mù.

Mọi hàm trong gói này là hàm thuần: nhận dữ liệu giả trong test, không gọi
mô hình, không chạm cơ sở dữ liệu.
"""
