"""Stage 10 frozen benchmarks (research only; nothing here is deployed).

champion  secchi-power-v1: 11.123 * FNU^-0.637 ft (production), FNU = the production-gated Dogliotti turbidity
C3        Stage 7 two-branch red-band model, fitted once on every historical clean row (c3_frozen.json)
C6        Stage 8 continuous model, c6_model.json exactly (Guntersville offsets used for Guntersville rows)
P1        Stage 9 physical model (p1.py, byte-identical block)
P1S       the separate SWIR-residual experiment: P1 on (rho - rho_B11), all four bands, same guards
"""
import json, math, os
import numpy as np
from p1 import p1 as P1

HERE = os.path.dirname(os.path.abspath(__file__))
C3F = json.load(open(os.path.join(HERE, "c3_frozen.json")))
C6F = json.load(open(os.path.join(HERE, "c6_model.json")))
floor = lambda v: max(v, 0.001)


def champion(fnu):
    return None if fnu is None else 11.123 * max(fnu, 0.1) ** -0.637


def _red_ndci(raw):
    red, re1 = floor(raw["red"]), floor(raw["re1"])
    return red, (re1 - red) / (re1 + red)


def c3(raw):
    """Frozen C3 in feet, or None if an input is missing."""
    if raw.get("red") is None or raw.get("re1") is None:
        return None
    red, nd = _red_ndci(raw)
    lr = math.log10(red); a = 1.0 if nd > 0 else 0.0
    b = C3F["beta"]
    return 10 ** (b[0] * (1 - a) + b[1] * (1 - a) * lr + b[2] * a + b[3] * a * lr)


def c3_in_domain(raw, value):
    """C3's validated input domain (training inputs, 1st-99th pct) and the defensible output range."""
    if value is None:
        return False
    d = C3F["domain"]
    red, nd = _red_ndci(raw)
    lr = math.log10(red)
    lo, hi = d["log10R_ndciGT0"] if nd > 0 else d["log10R_ndciLE0"]
    return lo <= lr <= hi and d["ndci"][0] <= nd <= d["ndci"][1] and d["outputFt"][0] <= value <= d["outputFt"][1]


def c6(raw, guntersville):
    if raw.get("red") is None or raw.get("re1") is None:
        return None
    red, nd = _red_ndci(raw)
    lr = math.log10(red)
    m = C6F["model"]
    mu, sd = np.array(m["mu"], float), np.array(m["sd"], float)
    z = np.concatenate([[1.0], (np.array([lr, nd, nd * lr]) - mu) / sd])
    b = np.array(m["beta"], float) + (np.array(m["delta"], float) if guntersville else 0.0)
    return 10 ** float(z @ b)


def p1s(raw, sun, swir):
    """The SWIR-residual experiment (Stage 10 section 6). Not part of P2."""
    if swir is None or not math.isfinite(swir):
        return None, "no SWIR", {}
    r = max(swir, 0.0)
    return P1({k: (None if v is None else v - r) for k, v in raw.items()}, sun)
