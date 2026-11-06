"""Bộ chuẩn bán tổng hợp (plan con 5): bộ sinh log có đáp án tuyệt đối.

Sinh nhiều tenant giả từ mô hình quy trình của BPIC 2015 bằng cách đổi có
kiểm soát một số luật thứ tự theo tenant. Mức nhiễu, tỉ lệ case dở dang và
số case lấy từ log thật, không tự đặt. Biết trước luật nào khác ở tenant
nào nên có ground truth tuyệt đối, và rút được nhiều bộ chuẩn độc lập để
tính khoảng tin cậy với số tenant tùy ý (spec: Bộ chuẩn bán tổng hợp).

Mọi hàm trong gói này là hàm thuần: nhận seed và tham số, trả log kèm đáp
án; không gọi mô hình, không chạm cơ sở dữ liệu.
"""
