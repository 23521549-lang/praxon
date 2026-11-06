"""Cổng Beta và cận dưới Wilson (task 7.4).

Beta: tiên nghiệm Beta(1 + c*s, 1 + (1-c)*s) — nền đều cộng s quan sát giả
tại tỉ lệ c — hậu nghiệm cộng số đếm thật vào hai tham số. Xác suất
P(X ≥ ngưỡng) tính bằng hàm beta chưa đầy đủ chuẩn hóa, triển khai bằng
phân số liên tục (Numerical Recipes), chỉ dùng `math` của stdlib.

Wilson: cận dưới khoảng tin cậy 95% cho tỉ lệ thành công, dùng làm cổng
luật 2 khi bằng chứng đến từ trace.
"""

from __future__ import annotations

import math
from typing import TypeGuard

from pydantic import BaseModel, ConfigDict, Field

#: z cho khoảng tin cậy 95% (phân vị chuẩn). Hằng số thống kê, không phải
#: tham số chính sách.
Z_95 = 1.96


def _is_count(value: object) -> TypeGuard[int]:
    """Số đếm: int không âm, không phải bool."""
    return isinstance(value, int) and not isinstance(value, bool)


def _check_counts(successes: int, trials: int) -> None:
    """Kiểm số đếm hợp lệ: 0 ≤ thành công ≤ lần thử, lần thử dương."""
    if not _is_count(trials) or trials <= 0:
        raise ValueError(f"số lần thử phải là int dương, nhận {trials!r}")
    if not _is_count(successes) or successes < 0 or successes > trials:
        raise ValueError(f"số thành công phải trong [0, {trials}], nhận {successes!r}")


def wilson_lower(successes: int, trials: int, *, z: float = Z_95) -> float:
    """Cận dưới Wilson cho tỉ lệ thành công, kẹp trong [0, 1]."""
    _check_counts(successes, trials)
    if z <= 0.0:
        raise ValueError(f"z phải dương, nhận {z!r}")
    p = successes / trials
    z2 = z * z
    denom = 1.0 + z2 / trials
    center = p + z2 / (2.0 * trials)
    spread = z * math.sqrt(p * (1.0 - p) / trials + z2 / (4.0 * trials * trials))
    return min(1.0, max(0.0, (center - spread) / denom))


def _betacf(a: float, b: float, x: float) -> float:
    """Phân số liên tục cho hàm beta chưa đầy đủ (Lentz)."""
    max_iter = 200
    eps = 3e-14
    fpmin = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def beta_cdf(x: float, a: float, b: float) -> float:
    """Hàm beta chưa đầy đủ chuẩn hóa I_x(a, b) = P(X ≤ x), X ~ Beta(a, b)."""
    if a <= 0.0 or b <= 0.0:
        raise ValueError(f"tham số Beta phải dương, nhận a={a!r}, b={b!r}")
    if not 0.0 <= x <= 1.0:
        raise ValueError(f"x phải trong [0, 1], nhận {x!r}")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    log_bt = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log(1.0 - x)
    )
    bt = math.exp(log_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def beta_prob_ge(a: float, b: float, threshold: float) -> float:
    """P(X ≥ ngưỡng) với X ~ Beta(a, b)."""
    return 1.0 - beta_cdf(threshold, a, b)


class Prior(BaseModel):
    """Tiên nghiệm của một luật: độ tin c và độ mạnh s (số quan sát giả).

    `strength` None nghĩa là dùng độ mạnh mặc định của chính sách — số 4
    mặc định sống trong tệp chính sách, không hard-code ở đây.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_key: str
    confidence: float = Field(ge=0.0, le=1.0)
    strength: float | None = Field(default=None, gt=0.0)


def prior_to_beta(prior: Prior, strength_default: float) -> tuple[float, float]:
    """Đổi tiên nghiệm thành tham số Beta(1 + c*s, 1 + (1-c)*s)."""
    if strength_default <= 0.0:
        raise ValueError(f"độ mạnh mặc định phải dương, nhận {strength_default!r}")
    strength = prior.strength if prior.strength is not None else strength_default
    a = 1.0 + prior.confidence * strength
    b = 1.0 + (1.0 - prior.confidence) * strength
    return a, b


def prior_prob_ge(prior: Prior, threshold: float, *, strength_default: float) -> float:
    """P(X ≥ ngưỡng) tính từ tiên nghiệm một mình, chưa có số đếm thật."""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"ngưỡng phải trong [0, 1], nhận {threshold!r}")
    a, b = prior_to_beta(prior, strength_default)
    return beta_prob_ge(a, b, threshold)


def posterior_prob_ge(
    prior: Prior,
    successes: int,
    trials: int,
    threshold: float,
    *,
    strength_default: float,
) -> float:
    """P(X ≥ ngưỡng) của hậu nghiệm Beta sau khi cộng số đếm thật."""
    _check_counts(successes, trials)
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"ngưỡng phải trong [0, 1], nhận {threshold!r}")
    a, b = prior_to_beta(prior, strength_default)
    return beta_prob_ge(a + successes, b + trials - successes, threshold)
