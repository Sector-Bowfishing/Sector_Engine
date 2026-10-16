"""Exact one-sided binomial upper confidence bound on an error rate (Clopper-Pearson), shared by the review-pack builder, the
ingestion script and the tests. Pure standard library.

upper_bound(n, k, conf=0.95): the largest true error rate p that is still compatible with seeing only k errors in n checked rows,
i.e. the p solving P(X <= k | n, p) = 1 - conf.  Reference values (n=60): 0 errors -> 4.9 %, 1 -> 7.7 %, 2 -> 10.1 %.
"""
import math


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p), summed in log space so it stays exact for any practical n."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0
    lp, lq = math.log(p), math.log1p(-p)
    terms = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq for i in range(k + 1)]
    m = max(terms)
    return min(1.0, math.exp(m) * sum(math.exp(t - m) for t in terms))


def upper_bound(n: int, k: int, conf: float = 0.95):
    """Exact one-sided upper bound on the error rate, as a fraction in [0, 1]; None when n == 0."""
    if n <= 0:
        return None
    if k < 0 or k > n:
        raise ValueError("k must be between 0 and n")
    if k >= n:
        return 1.0
    alpha = 1.0 - conf
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if binom_cdf(k, n, mid) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


if __name__ == "__main__":
    for n in (40, 60, 80):
        print(n, [round(100 * upper_bound(n, k), 1) for k in range(4)])
