"""P1, frozen at Stage 10: byte-identical to the model block of stage9/p1_research.py
(Stage 9 pre-registration sha256 4cc30221...). Do not edit; frozen_manifest.json pins its hash."""
import math

FT = 3.28084          # as stage9/p1_research.py

# ------------------------------------------------------------------ P1 (the pre-registered model)
LAM = {"blue": 492.0, "green": 560.0, "red": 665.0, "re1": 704.0}
AW = {"blue": 0.0161, "green": 0.0619, "red": 0.4245, "re1": 0.705}           # Pope & Fry 1997
BBW = {k: 0.00111 * (500.0 / l) ** 4.32 for k, l in LAM.items()}              # Morel 1974, pure fresh water
G0, G1 = 0.089, 0.1245
VIS = ("blue", "green", "red")


def p1(rho, sun_elev, eta_fixed=None, offset=0.0):
    """-> (secchi_ft or None, refusal reason or None, diagnostics). rho: raw BOA reflectance."""
    r = {k: (None if v is None else v - offset) for k, v in rho.items()}
    if sun_elev is None or sun_elev < 20: return None, "R1 sun", {}
    if any(r[k] is None for k in LAM): return None, "R2 reflectance", {}
    if not all(0.001 <= r[k] <= 0.15 for k in VIS) or not (0.003 <= r["re1"] <= 0.15): return None, "R2 reflectance", {}
    if not (0.25 <= r["blue"] / r["green"] <= 2.0): return None, "R3 blue/green", {}
    if not (0.10 <= r["red"] / r["green"] <= 2.0): return None, "R4 red/green", {}
    nd = (r["re1"] - r["red"]) / (r["re1"] + r["red"])
    if not (-0.25 <= nd <= 0.20): return None, "R5 NDCI", {}
    if r["re1"] > r["green"]: return None, "R6 scum/vegetation", {}
    Rrs = {k: r[k] / math.pi for k in LAM}
    rrs = {k: v / (0.52 + 1.7 * v) for k, v in Rrs.items()}
    u = {k: (-G0 + math.sqrt(G0 ** 2 + 4 * G1 * v)) / (2 * G1) for k, v in rrs.items()}
    if not all(0 < v < 1 for v in u.values()): return None, "R7 consistency", {}
    bbp0 = u["re1"] * AW["re1"] / (1 - u["re1"]) - BBW["re1"]
    if bbp0 <= 0: return None, "R7 consistency", {}
    eta = eta_fixed if eta_fixed is not None else 2 * (1 - 1.2 * math.exp(-0.9 * rrs["blue"] / rrs["green"]))
    if eta < 0: return None, "R7 consistency", {}
    th = 90.0 - sun_elev
    kd, a, bb = {}, {}, {}
    for k in VIS:
        bb[k] = BBW[k] + bbp0 * (LAM["re1"] / LAM[k]) ** eta
        a[k] = (1 - u[k]) * bb[k] / u[k]
        if a[k] < 0.9 * AW[k]: return None, "R7 consistency", {}
        kd[k] = (1 + 0.005 * th) * a[k] + (1 - 0.265 * BBW[k] / bb[k]) * 4.259 * (1 - 0.52 * math.exp(-10.8 * a[k])) * bb[k]
    kt = min(VIS, key=lambda k: kd[k])
    z = math.log(abs(0.14 - Rrs[kt]) / 0.013) / (2.5 * kd[kt]) * FT
    diag = {"eta": round(eta, 3), "bbp704": round(bbp0, 5), "band": kt, "kd": {k: round(v, 4) for k, v in kd.items()},
            "a": {k: round(v, 4) for k, v in a.items()}, "ndci": round(nd, 4)}
    if not (0.5 <= z <= 20): return None, "R8 range", diag | {"z": round(z, 2)}
    return z, None, diag


