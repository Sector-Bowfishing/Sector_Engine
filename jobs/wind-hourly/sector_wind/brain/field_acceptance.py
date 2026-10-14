"""PROPOSED practical acceptance lines for bowfisher quick observations (status PROPOSED_NOT_FROZEN until Michael approves; then freeze with a sha
BEFORE any observation is scored). Complements, never replaces, the frozen pair lines in WIND_BANK_VALIDATION_V2_PREREG.md.

Question behind every line: would a bowfisher trust this enough to choose a bank?
Small-sample guard: a rate line passes only if the observed rate AND the one-sided 95% Clopper-Pearson upper bound are within their limits,
so a lucky handful of calls cannot pass."""
from __future__ import annotations

STATUS = "PROPOSED_NOT_FROZEN"
LINES = {
    "volume": {"minObservations": 60, "minIndependentNights": 8, "minLakes": 2, "minWindQuadrants": 3, "minObservationsWindGe8mph": 15},
    "exposure": {"exact": 0.60, "withinOne": 0.90, "dangerousMissRate": 0.05, "dangerousMissUpper95": 0.15, "minProtectedCalls": 20, "unknownShareReportedMax": 0.35},
    "surface": {"exact": 0.60, "withinOne": 0.90, "dangerousMissRate": 0.03, "dangerousMissUpper95": 0.12, "minCalmCalls": 20, "unknownShareReportedMax": 0.35},
}


def cp_upper(k: int, n: int, conf: float = 0.95) -> float:
    """One-sided Clopper-Pearson upper bound for k events in n trials (pure python bisection on the binomial CDF)."""
    if n <= 0:
        return 1.0
    if k >= n:
        return 1.0
    from math import comb
    cdf = lambda p: sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) > 1 - conf else (lo, mid)
    return round(hi, 4)


def evaluate(exposure: dict, surface: dict, volume: dict) -> dict:
    """exposure: quick_observation.exposure_agreement(); surface: surface_product.agreement(); volume: {observations, nights, lakes, quadrants, windGe8}."""
    L, out = LINES, {"status": STATUS, "checks": {}}
    v = L["volume"]
    vol = {"observations": volume.get("observations", 0) >= v["minObservations"], "nights": volume.get("nights", 0) >= v["minIndependentNights"],
           "lakes": volume.get("lakes", 0) >= v["minLakes"], "quadrants": volume.get("quadrants", 0) >= v["minWindQuadrants"],
           "windGe8": volume.get("windGe8", 0) >= v["minObservationsWindGe8mph"]}
    out["checks"]["volume"] = vol
    e = L["exposure"]; n = exposure.get("protectedCalls") or 0; k = exposure.get("dangerousMiss") or 0
    out["checks"]["exposure"] = {"exact": (exposure.get("exact") or 0) >= e["exact"], "withinOne": (exposure.get("withinOne") or 0) >= e["withinOne"],
                                 "enoughProtectedCalls": n >= e["minProtectedCalls"],
                                 "dangerousMiss": n >= e["minProtectedCalls"] and k / n <= e["dangerousMissRate"] and cp_upper(k, n) <= e["dangerousMissUpper95"],
                                 "dangerousMissUpper95": cp_upper(k, n) if n else None}
    s = L["surface"]; calm_calls = sum((surface.get("confusion(pred->obs)") or {}).get("CALM", {}).values()); k2 = surface.get("roughCalledCalm") or 0
    out["checks"]["surface"] = {"exact": (surface.get("exact") or 0) >= s["exact"], "withinOne": (surface.get("withinOne") or 0) >= s["withinOne"],
                                "enoughCalmCalls": calm_calls >= s["minCalmCalls"],
                                "dangerousMiss": calm_calls >= s["minCalmCalls"] and k2 / calm_calls <= s["dangerousMissRate"] and cp_upper(k2, calm_calls) <= s["dangerousMissUpper95"],
                                "dangerousMissUpper95": cp_upper(k2, calm_calls) if calm_calls else None}
    ok = lambda d: all(val for key, val in d.items() if isinstance(val, bool))
    out["pass"] = {"volume": ok(vol), "exposure": ok(out["checks"]["exposure"]), "surface": ok(out["checks"]["surface"])}
    out["pass"]["all"] = all(out["pass"].values())
    return out
