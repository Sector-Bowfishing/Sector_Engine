"""P2, the Stage 10 routing challenger, exactly as PREREGISTRATION_P2.md section 3. Frozen: do not edit.

P1 where its 704 nm reference is trustworthy; C3 where P1 is residual-limited but C3 is inside its own
validated domain; otherwise REFUSE. No Secchi value enters any decision here.

The residual test. The image residual at each observation is estimated from the same pixels' own
Sentinel-2 B11 (1610 nm) reflectance, r = max(rho_B11, 0): water leaves essentially nothing at 1610 nm,
so what B11 shows over water is residual (glint, adjacency, aerosol error). P1 is re-run with r removed
from all four bands (a flat residual). The residual sensitivity is
        S = |Z_P1(rho - r) / Z_P1(rho) - 1|
and P1 is trustworthy only if S <= 0.20 (the half-width of the 2-3 ft stained class relative to its
centre, 0.5/2.5): if taking out the scene's own residual estimate would move P1's answer by more than a
class half-width, P1's answer is not a measurement of the water. If P1 refuses once r is removed, S = inf.
"""
import math
from p1 import p1 as P1
import models

S_MAX = 0.20
B05_FLOOR = 0.003          # P1's R2 noise floor on B05 (unchanged)
VIS = ("blue", "green", "red")
AUTH_P1, AUTH_C3 = "Moderate (cap)", "Low (cap)"


def residual_sensitivity(raw, sun, swir, z0):
    if swir is None or not math.isfinite(swir):
        return None, "no residual estimate (B11 missing)"
    r = max(swir, 0.0)
    z1, why1, _ = P1({k: (None if v is None else v - r) for k, v in raw.items()}, sun)
    if z1 is None:
        return math.inf, f"P1 refuses once the residual is removed ({why1})"
    return abs(z1 / z0 - 1.0), None


def route(raw, sun, swir, c3_value=None):
    """-> dict(path P1|C3|refused, ft, reason, authority, S, srr, p1_why).
    c3_value: the C3 estimate to use on the empirical path (default: the frozen C3). The historical
    development check passes C3's held-out prediction here; the routing decision never depends on it."""
    re1 = raw.get("re1"); srr = (re1 / swir) if (re1 is not None and swir and swir > 0) else None
    z0, why, _ = P1(raw, sun)
    out = {"S": None, "srr": srr, "p1_why": why}
    if z0 is not None:
        S, note = residual_sensitivity(raw, sun, swir, z0)
        out["S"] = S
        if S is not None and S <= S_MAX:
            return {**out, "path": "P1", "ft": z0, "reason": f"704 above the image residual (S={S:.2f})",
                    "authority": AUTH_P1, "provenance": "physical (P1)"}
        reason = note if S is None else (f"residual-limited (S={S:.2f})" if math.isfinite(S) else note)
    elif why == "R2 reflectance" and re1 is not None and re1 < B05_FLOOR and \
            all(raw.get(k) is not None and 0.001 <= raw[k] <= 0.15 for k in VIS):
        reason = "704 below the noise floor"
    elif why == "R7 consistency":
        reason = "P1 inversion inconsistent"
    else:
        return {**out, "path": "refused", "ft": None, "reason": f"P1 domain: {why}", "authority": None, "provenance": None}
    v = models.c3(raw) if c3_value is None else c3_value
    if models.c3_in_domain(raw, v):
        return {**out, "path": "C3", "ft": v, "reason": reason, "authority": AUTH_C3, "provenance": "empirical (C3)"}
    return {**out, "path": "refused", "ft": None, "reason": reason + "; C3 outside its validated domain",
            "authority": None, "provenance": None}
