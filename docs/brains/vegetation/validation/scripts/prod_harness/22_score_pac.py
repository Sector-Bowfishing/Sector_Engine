"""Lake-level scoring vs FWC LTM sonar PAC / PVI. usage: 22_score_pac.py CELL MODE USE_REJECTED"""
import sys; sys.dont_write_bytecode = True
sys.path.insert(0, "{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
import numpy as np, json, datetime as dt, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
from scipy import ndimage
from scipy.stats import spearmanr, rankdata
import score_lib as SL
ROOT = Path("{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
CELL, MODE, USEREJ = int(sys.argv[1]), sys.argv[2], bool(int(sys.argv[3]))
LYS = [o for o in json.load(open(ROOT.parent.parent/"data/pac_lakeyears.json")) if o["lake"] != "Okeechobee"]
MIN_KNOWN = 0.5

def auc(pos, neg):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if len(pos) == 0 or len(neg) == 0: return float("nan")
    r = rankdata(np.concatenate([pos, neg])); return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))

def stats(rows, boot=2000):
    """rows: dict(lake, share, belt, PVI, PAC)"""
    out = {}
    def one(rs):
        sh = np.array([r["share"] for r in rs]); pv = np.array([r["PVI"] for r in rs]); pa = np.array([r["PAC"] for r in rs])
        d = {}
        if len(rs) >= 5:
            d["rho_PVI"] = float(spearmanr(sh, pv)[0]); d["rho_PAC"] = float(spearmanr(sh, pa)[0])
        d["auc_PVI20v5"] = auc(sh[pv >= 20], sh[pv < 5]); d["auc_PAC50v20"] = auc(sh[pa >= 50], sh[pa < 20])
        return d
    base = one(rows); base["n"] = len(rows); base["n_lakes"] = len({r["lake"] for r in rows})
    base["n_PVI_hi_lo"] = [int(sum(r["PVI"] >= 20 for r in rows)), int(sum(r["PVI"] < 5 for r in rows))]
    base["n_PAC_hi_lo"] = [int(sum(r["PAC"] >= 50 for r in rows)), int(sum(r["PAC"] < 20 for r in rows))]
    lakes = sorted({r["lake"] for r in rows}); byl = {l: [r for r in rows if r["lake"] == l] for l in lakes}
    rng = np.random.default_rng(11); vals = {k: [] for k in ("rho_PVI", "rho_PAC", "auc_PVI20v5", "auc_PAC50v20")}
    for _ in range(boot):
        ix = rng.integers(0, len(lakes), len(lakes)); rs = [r for j in ix for r in byl[lakes[j]]]
        if len(rs) < 8: continue
        d = one(rs)
        for k in vals:
            if k in d and d[k] == d[k]: vals[k].append(d[k])
    base["ci"] = {k: ([float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5)), len(v)] if len(v) > 100 else None) for k, v in vals.items()}
    # per-lake means (one row per lake) as clustering check
    lm = [dict(lake=l, share=np.mean([r["share"] for r in byl[l]]), PVI=np.mean([r["PVI"] for r in byl[l]]), PAC=np.mean([r["PAC"] for r in byl[l]])) for l in lakes]
    base["per_lake_mean"] = one(lm); base["per_lake_mean"]["n"] = len(lm)
    return base

def main():
    res = {"cell": CELL, "mode": MODE, "use_rejected": USEREJ, "observers": {}}
    cache = {}; rows = {o: [] for o in "SAP"}; refused = {o: [] for o in "SAP"}
    for o in LYS:
        f = ROOT/f"out/pac{CELL}_{o['lake_id']}.npz"
        if not f.exists(): continue
        if o["lake_id"] not in cache:
            z = np.load(f, allow_pickle=True); z = {k: z[k] for k in z.files}
            z["_sc"] = SL.prep(z, MODE, USEREJ)
            d = ndimage.distance_transform_edt(z["lake"]) * float(z["ground_m"]); z["_belt"] = z["clarity"] & (d < 90)
            cache[o["lake_id"]] = z
        z = cache[o["lake_id"]]; ref = dt.date.fromisoformat(o["survey_med"]); sc = z["_sc"]
        for on, fn in SL.OBS.items():
            st, info = fn(z, sc, ref)
            cl = z["clarity"]; flag = (st == SL.FLAG) & cl; known = ((st == SL.CLEAR) | (st == SL.FLAG)) & cl
            kfrac = known.sum() / max(1, cl.sum())
            rec = dict(lake=o["lake_id"], name=o["lake"], year=o["year"], PVI=o["PVI"], PAC=o["PAC"], gap=info.get("gap"), kind=info["kind"], known_frac=float(kfrac), km2=o["km2"])
            if info["kind"] == "NONE" or kfrac < MIN_KNOWN or cl.sum() < 20:
                rec["reason"] = "NO_SCENE/NOT_ACCEPTED" if info["kind"] == "NONE" else ("TOO_FEW_KNOWN_CELLS" if kfrac < MIN_KNOWN else "TOO_FEW_CELLS")
                refused[on].append(rec); continue
            rec["share"] = float(flag.sum() / max(1, known.sum()))
            kb = known & z["_belt"]; rec["belt"] = float((flag & z["_belt"]).sum() / max(1, kb.sum())) if kb.sum() >= 10 else float("nan")
            rec["persistence"] = info.get("persistence", "")
            rows[on].append(rec)
    for on in "SAP":
        R = rows[on]; entry = dict(n_lakeyears=len(R), n_refused=len(refused[on]), refused_reasons={k: sum(1 for r in refused[on] if r["reason"] == k) for k in {r["reason"] for r in refused[on]}})
        entry["all"] = stats(R)
        entry["gap_le7"] = stats([r for r in R if r["gap"] is not None and r["gap"] <= 7], boot=500)
        entry["gap_8_21"] = stats([r for r in R if r["gap"] is not None and r["gap"] > 7], boot=500)
        entry["kind_counts"] = {k: sum(1 for r in R if r["kind"] == k) for k in {r["kind"] for r in R}}
        if on == "P": entry["persistence_counts"] = {k: sum(1 for r in R if r["persistence"] == k) for k in {r["persistence"] for r in R}}
        Rb = [dict(r, share=r["belt"]) for r in R if r["belt"] == r["belt"]]; entry["belt"] = stats(Rb, boot=500)
        res["observers"][on] = entry; res.setdefault("rows", {})[on] = R
    json.dump(res, open(ROOT/f"out/pac_{CELL}_{MODE}_rej{int(USEREJ)}.json", "w"), indent=1, default=float)
    f3 = lambda x: "nan" if x is None or x != x else f"{x:.2f}"
    for on in "SAP":
        e = res["observers"][on]; a = e["all"]
        print(MODE, "rej", USEREJ, on, "n", a["n"], "lakes", a["n_lakes"], "refused", e["n_refused"], "rhoPVI", f3(a.get("rho_PVI")), a["ci"]["rho_PVI"] and [round(x, 2) for x in a["ci"]["rho_PVI"][:2]],
              "rhoPAC", f3(a.get("rho_PAC")), "AUC PVI", f3(a["auc_PVI20v5"]), "AUC PAC", f3(a["auc_PAC50v20"]), "lakeMean rhoPVI", f3(a["per_lake_mean"].get("rho_PVI")),
              "belt rhoPVI", f3(e["belt"].get("rho_PVI")))
main()
