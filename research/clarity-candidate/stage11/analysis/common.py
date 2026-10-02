"""Stage 11 shared analysis helpers. Everything here is fixed by PREREGISTRATION_STAGE11.md (and its addenda)."""
import json, math, hashlib, random, collections, os, sys
import numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D11 = f"{S}/stage11"
sys.path.insert(0, f"{S}/stage10/frozen")
import p1 as P1MOD
from p1 import p1 as P1
import models as M
FT = 3.28084
FREEZE = json.load(open(f"{D11}/FREEZE_STAGE11.json"))
AW783 = next(a["aw783_per_m"] for a in FREEZE["addenda"] if a["id"] == "A")


def champ(f):
    return None if f is None else 11.123 * max(f, 0.1) ** -0.637


def p1nir(rho, sun_elev):
    """P1 with the QAA reference moved to 783 nm (B07): P1's code verbatim except the reference band (addendum A)."""
    lam = {**P1MOD.LAM, "re3": 783.0}; aw = {**P1MOD.AW, "re3": AW783}
    bbw = {**P1MOD.BBW, "re3": 0.00111 * (500.0 / 783.0) ** 4.32}
    r = dict(rho)
    if sun_elev is None or sun_elev < 20: return None, "R1 sun"
    need = ("blue", "green", "red", "re1", "re3")
    if any(r.get(k) is None for k in need): return None, "R2 reflectance"
    VIS = P1MOD.VIS
    if not all(0.001 <= r[k] <= 0.15 for k in VIS) or not (0.003 <= r["re3"] <= 0.15): return None, "R2 reflectance"
    if not (0.25 <= r["blue"] / r["green"] <= 2.0): return None, "R3 blue/green"
    if not (0.10 <= r["red"] / r["green"] <= 2.0): return None, "R4 red/green"
    nd = (r["re1"] - r["red"]) / (r["re1"] + r["red"])
    if not (-0.25 <= nd <= 0.20): return None, "R5 NDCI"
    if r["re1"] > r["green"]: return None, "R6 scum/vegetation"
    G0, G1 = P1MOD.G0, P1MOD.G1
    Rrs = {k: r[k] / math.pi for k in (*VIS, "re3")}
    rrs = {k: v / (0.52 + 1.7 * v) for k, v in Rrs.items()}
    u = {k: (-G0 + math.sqrt(G0 ** 2 + 4 * G1 * v)) / (2 * G1) for k, v in rrs.items()}
    if not all(0 < v < 1 for v in u.values()): return None, "R7 consistency"
    bbp0 = u["re3"] * aw["re3"] / (1 - u["re3"]) - bbw["re3"]
    if bbp0 <= 0: return None, "R7 consistency"
    eta = 2 * (1 - 1.2 * math.exp(-0.9 * rrs["blue"] / rrs["green"]))
    if eta < 0: return None, "R7 consistency"
    th = 90.0 - sun_elev
    kd = {}
    for k in VIS:
        bb = bbw[k] + bbp0 * (lam["re3"] / lam[k]) ** eta
        a = (1 - u[k]) * bb / u[k]
        if a < 0.9 * aw[k]: return None, "R7 consistency"
        kd[k] = (1 + 0.005 * th) * a + (1 - 0.265 * bbw[k] / bb) * 4.259 * (1 - 0.52 * math.exp(-10.8 * a)) * bb
    kt = min(VIS, key=lambda k: kd[k])
    z = math.log(abs(0.14 - Rrs[kt]) / 0.013) / (2.5 * kd[kt]) * FT
    if not (0.5 <= z <= 20): return None, "R8 range"
    return z, None


def ndci(raw):
    re1, red = max(raw["re1"], 0.001), max(raw["red"], 0.001)
    return (re1 - red) / (re1 + red)


def owt(x):
    """Section 6 satellite-only optical water type (production L2A disk)."""
    r = x["raw"]
    if x.get("sun_elev") is None or x["sun_elev"] < 20: return "unsupported"
    if any(r.get(k) is None for k in ("blue", "green", "red", "re1")): return "unsupported"
    if not all(0.001 < r[k] < 0.15 for k in ("blue", "green", "red", "re1")): return "unsupported"
    if r.get("swir16") is not None and r["swir16"] > 0.02: return "unsupported"
    if r["re1"] < 0.003 and r["red"] > 0.02: return "unsupported"
    nd, f = ndci(r), x["fnu"]
    if nd > 0.03 and f >= 8: return "mixed"
    if nd > 0.03: return "algal"
    if f >= 8: return "sediment"
    return "clear"


def insitu_type(x):
    c, t = x.get("chl"), x.get("turb")
    if c is None or t is None: return None
    if c >= 15 and t >= 8: return "mixed"
    if c >= 15: return "algal"
    if t >= 8: return "sediment"
    return "clear"


def cls(ft):
    return 0 if ft >= 6 else 1 if ft >= 3 else 2 if ft >= 2 else 3


def fold(lake, k=5):
    return int(hashlib.md5(lake.encode()).hexdigest(), 16) % k


def lake_boot(rows, fn, B=2000, seed=11):
    """95% CI of fn(rows) by resampling whole lakes."""
    by = collections.defaultdict(list)
    for r in rows: by[r["lake"]].append(r)
    lakes = sorted(by); g = random.Random(seed); v = []
    for _ in range(B):
        smp = [x for _ in lakes for x in by[lakes[g.randrange(len(lakes))]]]
        try:
            y = fn(smp)
        except Exception:
            y = None
        if y is not None and np.isfinite(y): v.append(y)
    v.sort()
    return [round(v[int(.025 * len(v))], 4), round(v[int(.975 * len(v)) - 1], 4)] if len(v) > 100 else None


def load():
    # section 2: every date <= 2025-12-31 (the Stage 7/8 national sets carried 21 rows from 2026; they are dropped here)
    rows = [x for x in json.load(open(f"{D11}/corpus/corpus.json")) if x["date"] <= "2025-12-31"]
    for x in rows:
        x["owt"] = owt(x); x["insitu_type"] = insitu_type(x)
        x["champ"] = champ(x["fnu"])
    return rows
