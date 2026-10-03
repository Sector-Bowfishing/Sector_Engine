"""Stage 20 track A analysis (descriptive; value-blind): the NOMINAL reprocessed S2A/S2C tandem at Sen2Cor level.
Per band S2C vs S2A on the production-gated 60 m disk (both n_valid >= 5): median log10 ratio, median difference, Theil-Sen
slope/intercept, dependence on magnitude (S2A tertiles), on sun elevation and view incidence, by date window (before vs
during the 12-19 Dec preliminary window), by baseline; Sen2Cor aerosol (AOT) and the production FNU. Compared with the
band-response physics expectation (srf20.json, BOA ratio). Writes tandemA20.json."""
import json, os, math, collections
import numpy as np
from scipy.stats import theilslopes
S = os.environ["CLARITY_RESEARCH_ROOT"]
R = json.load(open(f"{S}/stage20/tandem20_readouts.json"))
SRF = json.load(open(f"{S}/stage20/srf20.json"))["S2C_mtd_vs_S2A_mtd"]["band_ratio_pctl"]
BM = {"blue": "B02", "green": "B03", "red": "B04", "rededge1": "B05", "nir": "B08", "nir08": "B8A", "swir16": "B11"}
f = lambda v: v if isinstance(v, (int, float)) and math.isfinite(v) else None
ok = [r for r in R if isinstance(r.get("a"), dict) and isinstance(r.get("c"), dict) and (r["a"].get("n_valid") or 0) >= 5 and (r["c"].get("n_valid") or 0) >= 5]
q = lambda v: [round(float(np.percentile(v, x)), 5) for x in (10, 25, 50, 75, 90)] if v else None


def band_stats(rows, k):
    v = [(f(r["c"].get(f"rho_{k}_v")), f(r["a"].get(f"rho_{k}_v"))) for r in rows]
    v = [(c, a) for c, a in v if c is not None and a is not None]
    lr = [math.log10(c / a) for c, a in v if c > 0.001 and a > 0.001]
    out = {"n": len(v), "n_ratio": len(lr), "log_ratio_median": float(np.median(lr)) if lr else None, "ratio_median": 10 ** float(np.median(lr)) if lr else None,
           "diff_median": float(np.median([c - a for c, a in v])) if v else None}
    if len(v) >= 10:
        sl, ic, lo, hi = theilslopes([c for c, a in v], [a for c, a in v]); out.update({"theil_slope": float(sl), "theil_intercept": float(ic), "slope_ci": [float(lo), float(hi)]})
    return out


out = {"n_site_pass_pairs": len(R), "n_valid_both": len(ok), "baselines": dict(collections.Counter(f"{r['s2a_baseline']}/{r['s2c_baseline']}" for r in R)),
       "products_s2c_generation": dict(collections.Counter(r["s2c_product"].split("_")[-1][:4] for r in R if r.get("s2c_product"))),
       "dt_s": q([r["dt_s"] for r in R]), "bands": {BM[k]: band_stats(ok, k) for k in BM}}
out["srf_expected_ratio_median"] = {b: SRF[b][2] for b in ("B02", "B03", "B04", "B05", "B8A") if b in SRF}
# magnitude dependence (S2A red tertiles)
red = sorted(f(r["a"].get("rho_red_v")) or 0 for r in ok); cut = [red[len(red) // 3], red[2 * len(red) // 3]] if red else [0, 0]
out["by_magnitude"] = {}
for name, lo, hi in (("dark", -1, cut[0]), ("mid", cut[0], cut[1]), ("bright", cut[1], 9)):
    rows = [r for r in ok if lo <= (f(r["a"].get("rho_red_v")) or 0) < hi]
    out["by_magnitude"][name] = {"red_range": [lo, hi], **{BM[k]: band_stats(rows, k)["log_ratio_median"] for k in ("blue", "green", "red", "rededge1")}, "n": len(rows)}
# geometry / time
def grp(name, fn):
    g = collections.defaultdict(list)
    for r in ok: g[fn(r)].append(r)
    out[name] = {k: {"n": len(v), **{BM[b]: band_stats(v, b)["log_ratio_median"] for b in ("blue", "green", "red", "rededge1")}} for k, v in sorted(g.items()) if len(v) >= 10}
grp("by_window", lambda r: "12-19 Dec (preliminary window)" if r["date"] >= "2024-12-12" else "29 Oct - 11 Dec")
grp("by_sun", lambda r: "sun<25" if (r.get("sun_elev") or 0) < 25 else "sun 25-40" if r["sun_elev"] < 40 else "sun>=40")
grp("by_view_inc_diff", lambda r: "|dVZA|<1" if abs((r.get("view_inc_c") or 0) - (r.get("view_inc_a") or 0)) < 1 else "|dVZA|>=1")
grp("by_geo", lambda r: "global" if r["site"].startswith("G:") else "US")
aot = [(f(r["c"].get("aot_site")), f(r["a"].get("aot_site"))) for r in ok]; aot = [(c, a) for c, a in aot if c is not None and a is not None]
out["aot"] = {"n": len(aot), "diff_median": float(np.median([c - a for c, a in aot])) if aot else None, "ratio_median": float(np.median([c / a for c, a in aot if a > 0])) if aot else None}
fn = [(f(r["c"].get("fnu_prod")), f(r["a"].get("fnu_prod"))) for r in ok]; fn = [(c, a) for c, a in fn if c and a and c > 0 and a > 0]
out["fnu_prod"] = {"n": len(fn), "log_ratio_median": float(np.median([math.log10(c / a) for c, a in fn])) if fn else None}
json.dump(out, open(f"{S}/stage20/tandemA20.json", "w"), indent=1)
print("pairs", len(R), "valid both", len(ok), "baselines", out["baselines"], "S2C generation", out["products_s2c_generation"])
for b, v in out["bands"].items(): print(b, {k: (round(x, 4) if isinstance(x, float) else x) for k, x in v.items() if k != "slope_ci"}, "| SRF expects", out["srf_expected_ratio_median"].get(b))
print("magnitude", out["by_magnitude"]); print("window", out["by_window"]); print("AOT", out["aot"], "FNU", out["fnu_prod"])
