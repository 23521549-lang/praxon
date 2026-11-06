"""Kappa Cohen cho duyệt chéo mù (plan con 9, task 9.4 — chỉ phần lệnh kappa).

Duyệt chéo mù: hai người duyệt độc lập chấm một phần năm quyết định thủ công.
Kappa đo mức đồng thuận vượt trên ngẫu nhiên; ngưỡng chấp nhận là 0,61
(theo cổng ra của task 9.4).

CHỈ làm phần lệnh tính kappa. Phần rubric là văn bản (docs), cần duyệt nội
dung riêng — không làm trong task này. Task 9.4 chỉ "xong" khi cả hai phần
xong, nên không được báo là xong task 9.4 khi mới có lệnh kappa.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Sequence
from typing import TypeVar

LabelT = TypeVar("LabelT", bound=Hashable)

KAPPA_THRESHOLD = 0.61
"""Ngưỡng chấp nhận của duyệt chéo mù (cổng ra task 9.4: kappa ≥ 0,61).

Con số 0,61 nằm trong cổng ra của task, không phải tham số hiệu chỉnh — nên
nó là một hằng có tên ở đây, không phải số chôn trong logic.
"""


def cohen_kappa(rater_a: Sequence[LabelT], rater_b: Sequence[LabelT]) -> float:
    """Kappa Cohen giữa hai người duyệt trên cùng một dãy nhãn.

    Po là tỉ lệ hai người đồng ý; Pe là tỉ lệ đồng ý kỳ vọng nếu hai người
    chấm độc lập theo phân phối biên của mỗi người. Kappa = (Po - Pe) / (1 - Pe).

    Hai người luôn chấm cùng một nhãn duy nhất thì Pe = 1 và kappa quy ước
    là 1.0 (đồng thuận tuyệt đối).
    """
    if len(rater_a) != len(rater_b):
        raise ValueError(
            f"hai dãy nhãn phải cùng độ dài, nhận được {len(rater_a)} và {len(rater_b)}"
        )
    count = len(rater_a)
    if count == 0:
        raise ValueError("không có nhãn nào để tính kappa")
    agreements = sum(
        1 for first, second in zip(rater_a, rater_b, strict=True) if first == second
    )
    observed = agreements / count
    first_counts = Counter(rater_a)
    second_counts = Counter(rater_b)
    categories = set(first_counts) | set(second_counts)
    expected = sum(
        (first_counts[category] / count) * (second_counts[category] / count)
        for category in categories
    )
    if expected == 1.0:
        return 1.0
    return (observed - expected) / (1.0 - expected)


def kappa_meets_threshold(kappa: float) -> bool:
    """Kappa có đạt ngưỡng chấp nhận của duyệt chéo mù không (≥ 0,61)."""
    return kappa >= KAPPA_THRESHOLD
