"""The math. Small on purpose so you can check it by hand.

n = trials run for a task, c = trials that passed.

pass@k  chance that AT LEAST ONE of k tries succeeds  = 1 - C(n-c, k) / C(n, k)
        Right question for "the user can retry and take the best answer".
pass^k  chance that ALL k tries succeed               = C(c, k) / C(n, k)
        Right question for a support agent: every customer gets one shot.
        Introduced by tau-bench (Sierra, 2024). At 75% per try, pass^3 is
        about 42%. Reliability falls off fast.

Both are unbiased estimates from n trials (the same estimator HumanEval used
for pass@k). They are averaged over tasks.
"""

from __future__ import annotations

from math import comb, sqrt


def pass_at_k(n: int, c: int, k: int) -> float:
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    if c < k:
        return 0.0
    return comb(c, k) / comb(n, k)


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% confidence interval for a pass rate. Better than +/- 1.96*SE when n is small."""
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def cohen_kappa(tp: int, fn: int, fp: int, tn: int) -> float:
    """Agreement between judge and human beyond what chance would give."""
    n = tp + fn + fp + tn
    if n == 0:
        return 0.0
    observed = (tp + tn) / n
    p_human_pass = (tp + fn) / n
    p_judge_pass = (tp + fp) / n
    expected = p_human_pass * p_judge_pass + (1 - p_human_pass) * (1 - p_judge_pass)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)
