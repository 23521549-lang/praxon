"""Khoảng tin cậy bootstrap (plan con 8, task 8.3; spec: bootstrap trên case).

Khoảng tin cậy 95% tính bằng bootstrap trên case: lấy mẫu lại các case có
hoàn lại, tính lại chỉ số trên mỗi mẫu, lấy phân vị của các giá trị đó.
Cùng seed thì ra cùng khoảng (tái lập được). Số lần rút lấy từ cấu hình
(`Settings.bootstrap_draws`), không hard-code trong hàm.

Hàm này không biết gì về bốn chỉ số: nó nhận một hàm chỉ số bất kỳ tính
trên một dãy case, nên dùng được cho mọi chỉ số và mọi điều kiện.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from typing import TypeVar

CaseT = TypeVar("CaseT")


def bootstrap_confidence_interval(
    metric: Callable[[Sequence[CaseT]], float],
    cases: Sequence[CaseT],
    *,
    n_draws: int,
    seed: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Khoảng tin cậy bootstrap cho một chỉ số tính trên các case.

    `metric` nhận một dãy case và trả một số; `cases` là các case quan sát
    được, lấy mẫu lại có hoàn lại. `n_draws` là số lần rút (lấy từ cấu hình,
    không hard-code). `seed` cố định thì ra cùng khoảng. `confidence` mặc
    định 0.95 theo spec (khoảng tin cậy 95%).

    Trả về (cận dưới, cận trên): phân vị (1 - confidence) / 2 và
    1 - (1 - confidence) / 2 của các giá trị bootstrap.
    """
    if n_draws < 1:
        raise ValueError(f"số lần rút phải ít nhất 1, nhận được {n_draws}")
    if not cases:
        raise ValueError("không có case nào để bootstrap")
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"độ tin cậy phải trong (0, 1), nhận được {confidence}")

    rng = random.Random(seed)
    count = len(cases)
    estimates = [metric(rng.choices(cases, k=count)) for _ in range(n_draws)]
    estimates.sort()
    alpha = 1.0 - confidence
    lower_index = int(alpha / 2 * n_draws)
    upper_index = min(n_draws - 1, int((1.0 - alpha / 2) * n_draws))
    return estimates[lower_index], estimates[upper_index]
