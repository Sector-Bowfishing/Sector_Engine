"""Stage 20 track D (physics only; no satellite pair, no Secchi): what the official spectral response functions alone do to
Sector's inputs. Synthetic inland-water reflectance spectra (pure water + phytoplankton + CDOM + mineral particles, the
QAA forward model) are convolved, solar-weighted, with the S2A, S2B and S2C SRFs of the L1C metadata (meta20.json:
the products the engine reads) and with the RSR files ACOLITE uses; band reflectance, the frozen C-gbm features and the
frozen C-gbm prediction are compared. Also fits the physics band adjustment (SBAF, S2C -> S2A) on the synthetic set.
Writes srf20.json."""
import json, os, sys, bz2, math, pickle, itertools
import numpy as np
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage14/analysis")
from lib14 import features
import models13_lib as L
G = pickle.load(open(f"{S}/stage14/engine/frozen_gbm.pkl", "rb"))
META = json.load(open(f"{S}/stage20/meta20.json"))
ACO = f"{S}/stage11/tools/acolite/src/data"
WL = np.arange(400.0, 1001.0, 1.0)
BANDS = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B8A"]


def mtd(group):
    v = next(x for x in META.values() if x.get("group") == group)
    return {b: (s["min"] + s["step"] * np.arange(len(s["values"])), np.array(s["values"])) for b, s in v["srf"].items() if s["values"]}


def aco(fname):
    out, cur, w, r = {}, None, [], []
    for line in open(f"{ACO}/RSR/{fname}"):
        t = line.strip()
        if not t: continue
        if t.startswith(";;") or t.startswith("#"):
            u = t.upper().replace(";", "").replace("#", "").strip()
            if "BAND" in u and u.split()[-1].replace("A", "").isdigit():
                if cur: out[cur] = (np.array(w), np.array(r))
                n = u.split()[-1]; cur = "B8A" if n == "8A" else f"B{int(n):02d}"; w, r = [], []
            continue
        a, b = t.split()[:2]; a = float(a); w.append(a * 1000 if a < 10 else a); r.append(float(b))
    if cur: out[cur] = (np.array(w), np.array(r))
    return out


SRF = {"S2A_mtd": mtd(["S2A", "N0511", "2024"]), "S2B_mtd": mtd(["S2B", "N0511", "2024"]), "S2C_mtd": mtd(["S2C", "N0511", "2025"]),
       "S2C_mtd_N9905": mtd(["S2C", "N9905", "2024"]), "S2C_mtd_N0512": mtd(["S2C", "N0512", "2026"]),
       "S2A_aco": aco("S2A_MSI.txt"), "S2B_aco": aco("S2B_MSI.txt"), "S2C_aco": aco("S2C_MSI_V4.txt"), "S2A_aco_V4": aco("S2A_MSI_V4.txt")}
sol = np.loadtxt(bz2.open(f"{ACO}/Solar/Thuillier2003.txt.bz2", "rt"), comments="#"); E0 = np.interp(WL, sol[:, 0], sol[:, 1])


def onto(srf):
    return {b: np.clip(np.interp(WL, w, r, left=0, right=0), 0, None) for b, (w, r) in srf.items()}


SR = {k: onto(v) for k, v in SRF.items()}
centre = lambda s: float(np.sum(WL * s) / np.sum(s))
width = lambda s: float(np.sum(s >= 0.5 * s.max()))
srf_table = {k: {b: {"centre_nm": round(centre(s), 2), "fwhm_nm": width(s)} for b, s in v.items() if b in BANDS + ["B11", "B12"]} for k, v in SR.items()}
same_baselines = {b: float(np.max(np.abs(SR["S2C_mtd"][b] - SR["S2C_mtd_N9905"][b]))) for b in BANDS}
same_baselines_N0512 = {b: float(np.max(np.abs(SR["S2C_mtd"][b] - SR["S2C_mtd_N0512"][b]))) for b in BANDS}


def load_aw():
    def rd(f, scale):
        rows = []
        for line in open(f"{S}/stage11/tools/aw/{f}", encoding="latin-1"):
            p = line.split()
            try: rows.append((float(p[0]), float(p[1]) * scale))
            except (ValueError, IndexError): pass
        return np.array(sorted(rows))
    pope, kou = rd("pope97.dat", 100.0), rd("kou93b.dat", 100.0)
    a = np.where(WL <= 727.5, np.interp(WL, pope[:, 0], pope[:, 1]), np.interp(WL, kou[:, 0], kou[:, 1]))
    return a


AW = load_aw(); BBW = 0.00111 * (500.0 / WL) ** 4.32
GAUSS = [(435, 18, 0.040), (465, 22, 0.020), (490, 20, 0.012), (535, 25, 0.004), (590, 20, 0.002), (625, 15, 0.003), (676, 10, 0.020)]
APH1 = sum(h * np.exp(-0.5 * ((WL - c) / s) ** 2) for c, s, h in GAUSS)


def spectrum(chl, cdom, tss):
    a = AW + APH1 * chl ** 0.8 + cdom * np.exp(-0.015 * (WL - 440)) + 0.035 * tss * np.exp(-0.0123 * (WL - 443))
    bb = BBW + (0.003 * chl ** 0.62 + 0.015 * tss) * (560.0 / WL) ** 0.6
    u = bb / (a + bb); rrs = 0.089 * u + 0.1245 * u * u; Rrs = 0.52 * rrs / (1 - 1.7 * rrs)
    return math.pi * Rrs


def band(rho, s): return float(np.sum(rho * s * E0) / np.sum(s * E0))


ens = []
for chl, cdom, tss in itertools.product(np.logspace(-0.5, 2.5, 13), np.logspace(-1.5, 0.8, 9), np.logspace(-1, 2.2, 13)):
    rho = spectrum(chl, cdom, tss); rec = {"chl": chl, "cdom": cdom, "tss": tss}
    for k in ("S2A_mtd", "S2B_mtd", "S2C_mtd", "S2A_aco", "S2C_aco"):
        rec[k] = {b: band(rho, SR[k][b]) for b in BANDS}
    ens.append(rec)


def pred(r):
    F, q = features(r, 45.0); x = [F[k] for k in L.FEATS6 + ["F_kd"]]
    return (float(G.predict(np.array([x]))[0]) if all(math.isfinite(v) for v in x) else None), F


for r in ens:
    for k in ("S2A_mtd", "S2B_mtd", "S2C_mtd"):
        r["p_" + k], r["F_" + k] = pred(r[k])
# realistic subset: S2A prediction 0.5-30 ft and red reflectance in the corpus range
real = [r for r in ens if r["p_S2A_mtd"] is not None and r["p_S2C_mtd"] is not None and math.log10(0.5) <= r["p_S2A_mtd"] <= math.log10(30) and 0.002 <= r["S2A_mtd"]["B04"] <= 0.12]
q = lambda v: [round(float(np.percentile(v, x)), 5) for x in (10, 25, 50, 75, 90)]
out = {"srf_table": srf_table, "s2c_srf_identical_N9905_vs_N0511_maxabs": same_baselines, "s2c_srf_identical_N0512_vs_N0511_maxabs": same_baselines_N0512,
       "n_ensemble": len(ens), "n_realistic": len(real)}
for pair in (("S2C_mtd", "S2A_mtd"), ("S2B_mtd", "S2A_mtd"), ("S2C_aco", "S2A_aco"), ("S2A_aco", "S2A_mtd"), ("S2C_aco", "S2C_mtd")):
    c, a = pair; k = f"{c}_vs_{a}"
    out[k] = {"band_ratio_pctl": {b: q([r[c][b] / r[a][b] for r in real]) for b in BANDS}}
    if c.endswith("_mtd") and a.endswith("_mtd"):
        out[k]["feature_diff_pctl"] = {f: q([r["F_" + c][f] - r["F_" + a][f] for r in real if math.isfinite(r["F_" + c][f]) and math.isfinite(r["F_" + a][f])]) for f in L.FEATS6 + ["F_kd"]}
        d = [r["p_" + c] - r["p_" + a] for r in real]
        out[k]["p_diff_pctl"] = q(d); out[k]["p_diff_mean"] = float(np.mean(d))
        # by optical state (S2A prediction)
        bins = [(-0.31, 0.3), (0.3, 0.6), (0.6, 0.9), (0.9, 1.5)]
        out[k]["p_diff_by_state"] = {f"{lo:.2f}..{hi:.2f}": {"n": sum(1 for r in real if lo <= r["p_S2A_mtd"] < hi), "median": float(np.median([r["p_" + c] - r["p_" + a] for r in real if lo <= r["p_S2A_mtd"] < hi]))}
                                     for lo, hi in bins if any(lo <= r["p_S2A_mtd"] < hi for r in real)}
# physics SBAF S2C -> S2A (fitted on the synthetic set only): rhoA_b = g*rhoC_b (+ k*(rhoC_B06 - rhoC_B04) for B05)
sb = {}
for b in BANDS:
    yA = np.array([r["S2A_mtd"][b] for r in real]); xC = np.array([r["S2C_mtd"][b] for r in real]); w = 1 / np.maximum(yA, 1e-4)
    if b == "B05":
        X = np.vstack([xC, np.array([r["S2C_mtd"]["B06"] - r["S2C_mtd"]["B04"] for r in real])]).T
        coef = np.linalg.lstsq(X * w[:, None], yA * w, rcond=None)[0]; fit = X @ coef; sb[b] = {"g": float(coef[0]), "k": float(coef[1])}
    else:
        coef = np.linalg.lstsq((xC * w)[:, None], yA * w, rcond=None)[0]; fit = xC * coef[0]; sb[b] = {"g": float(coef[0])}
    sb[b]["rel_resid_pctl"] = q(fit / yA - 1)
out["sbaf_S2C_to_S2A"] = sb
def sbaf(r):
    v = dict(r)
    for b, c in sb.items():
        v[b] = c["g"] * r[b] + (c.get("k", 0) * (r["B06"] - r["B04"]) if b == "B05" else 0)
    return v
d = []
for r in real:
    p, _ = pred(sbaf(r["S2C_mtd"]))
    if p is not None: d.append(p - r["p_S2A_mtd"])
out["sbaf_p_diff_pctl"] = q(d); out["sbaf_p_diff_mean"] = float(np.mean(d))
json.dump(out, open(f"{S}/stage20/srf20.json", "w"), indent=1)
print("SRF centres (nm):", {k: {b: v[b]["centre_nm"] for b in ("B02", "B04", "B05", "B06", "B8A")} for k, v in srf_table.items()})
print("S2C SRF N9905 vs N0511 max |diff|:", max(same_baselines.values()), " N0512:", max(same_baselines_N0512.values()))
for k in [x for x in out if isinstance(out[x], dict) and "band_ratio_pctl" in out[x]]:
    print(k, "ratio median", {b: v[2] for b, v in out[k]["band_ratio_pctl"].items()}, "| p diff", out[k].get("p_diff_pctl"))
print("SBAF", {b: {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in c.items()} for b, c in sb.items()})
print("after SBAF p diff", out["sbaf_p_diff_pctl"], "n realistic", len(real))
