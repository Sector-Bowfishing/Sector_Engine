"""Stage 11 Part B (PREREGISTRATION_STAGE11.md section 4), radiometric truth: AERONET-OC Level 2.0 Lwn_f/Q against
Sen2Cor (production L2A), ACOLITE (own mask; and water/cloud-only mask) and C2RCC / C2X, on the same matchups.
rho_w(AERONET) = pi * Lwn / F0, F0 = Thuillier 2003 (ACOLITE's copy) averaged over +-5 nm of the exact wavelength.
Bands B01-B05 matched to the nearest AERONET wavelength within 10 nm. Writes part_b_aeronet.json."""
import json, math, bz2, random, collections, sys, os
import numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/stage11"
F0 = np.array([[float(v) for v in l.split()] for l in bz2.open(f"{S}/tools/acolite/src/data/Solar/Thuillier2003.txt.bz2", "rt") if l.strip() and not l.startswith("#")])
def f0(wl):   # mW cm-2 um-1 (Thuillier file is in mW m-2 nm-1 -> /10)
    sel = (F0[:, 0] >= wl - 5) & (F0[:, 0] <= wl + 5)
    return float(F0[sel, 1].mean()) / 10.0
CENTRE = {"B01": 443, "B02": 492, "B03": 560, "B04": 665, "B05": 704}
M = json.load(open(f"{S}/ac/aeronet/matchups.json"))
R = json.load(open(f"{S}/ac/results_aeronet.json"))
R2 = json.load(open(f"{S}/ac/results_aeronet_relaxed.json")) if os.path.exists(f"{S}/ac/results_aeronet_relaxed.json") else {}
jobs = {}
for j in json.load(open(f"{S}/ac/jobs_aeronet.json")):
    jobs.setdefault(j["job"], j)      # 4 names cover two tiles of one overpass; the driver processed the first
mt = {x["item"]: x for x in M if x.get("valid")}
rows = []
for job, r in R.items():
    j = jobs[job]; m = mt[j["c1"]]
    a = m["aeronet"]; ex = {int(k): v for k, v in a["exact_nm"].items()}; lw = {int(k): v for k, v in a["lwn_fq"].items()}
    truth = {}
    for b, c in CENTRE.items():
        cand = [(abs(ex.get(k, k) - c), k) for k in lw if lw[k] > 0]
        if not cand: continue
        d, k = min(cand)
        if d <= 10:
            wl = ex.get(k, k); truth[b] = math.pi * lw[k] / f0(wl)
    s2c = m["sen2cor"]
    proc = {"Sen2Cor (production)": {"B02": s2c.get("rho_blue_v"), "B03": s2c.get("rho_green_v"), "B04": s2c.get("rho_red_v"), "B05": s2c.get("rho_rededge1_v"), "B11": s2c.get("rho_swir16_v")}}
    ac = (r.get("acolite") or {}).get("site") or {}
    proc["ACOLITE (own mask)"] = {b: ac.get(b) for b in list(CENTRE) + ["B11"]} if ac.get("n", 0) >= 5 else {}
    rel = ((R2.get(job) or {}).get("site") or {}).get("relaxed") or {}
    proc["ACOLITE (water/cloud mask)"] = {b: rel.get(b) for b in list(CENTRE) + ["B11"]} if rel.get("n", 0) >= 5 else {}
    for net in ("C2RCC-Nets", "C2X-Nets"):
        c = ((r.get("c2rcc") or {}).get(net) or {}).get("site") or {}
        proc[net] = {b: c.get(b) for b in CENTRE} if c.get("n", 0) >= 5 else {}
    rows.append({"job": job, "site": m["site"], "platform": m["platform"], "dt_min": m["dt_min"], "truth": truth, "proc": proc})
PROCS = ["Sen2Cor (production)", "ACOLITE (own mask)", "ACOLITE (water/cloud mask)", "C2RCC-Nets", "C2X-Nets"]
def err(rw, t):
    return math.log10(rw / t) if (rw is not None and t and rw > 0 and t > 0) else None
out = {"matchups": len(rows), "by_site": dict(collections.Counter(r["site"] for r in rows)), "processors": {}}
for p in PROCS:
    rec = {"valid_rate": round(float(np.mean([bool(r["proc"].get(p)) for r in rows])), 3), "bands": {}}
    for b in CENTRE:
        e = [err(r["proc"].get(p, {}).get(b), r["truth"].get(b)) for r in rows]
        neg = sum(1 for r in rows if r["proc"].get(p, {}).get(b) is not None and r["proc"][p][b] <= 0 and r["truth"].get(b))
        e = [v for v in e if v is not None]
        rec["bands"][b] = {"n": len(e), "median_log_bias": round(float(np.median(e)), 3) if e else None,
                           "median_abs_log": round(float(np.median(np.abs(e))), 3) if e else None, "non_positive": neg}
    core = [abs(err(r["proc"].get(p, {}).get(b), r["truth"].get(b))) for r in rows for b in ("B02", "B03", "B04", "B05")
            if err(r["proc"].get(p, {}).get(b), r["truth"].get(b)) is not None]
    rec["B02-B05 median_abs_log"] = round(float(np.median(core)), 3) if core else None
    rec["B02-B05 n"] = len(core)
    rec["by_site"] = {s: round(float(np.median([abs(err(r["proc"].get(p, {}).get(b), r["truth"].get(b))) for r in rows if r["site"] == s for b in ("B02", "B03", "B04", "B05")
                                               if err(r["proc"].get(p, {}).get(b), r["truth"].get(b)) is not None] or [np.nan])), 3) for s in out["by_site"]}
    out["processors"][p] = rec
# paired against Sen2Cor on the same matchup-bands; bootstrap over matchups stratified by site
def paired(p):
    pairs = [(abs(err(r["proc"].get(p, {}).get(b), r["truth"].get(b))), abs(err(r["proc"]["Sen2Cor (production)"].get(b), r["truth"].get(b))), r["site"], r["job"])
             for r in rows for b in ("B02", "B03", "B04", "B05")
             if err(r["proc"].get(p, {}).get(b), r["truth"].get(b)) is not None and err(r["proc"]["Sen2Cor (production)"].get(b), r["truth"].get(b)) is not None]
    if len(pairs) < 20: return None
    a = np.array([x[0] for x in pairs]); s = np.array([x[1] for x in pairs])
    jobsl = sorted({x[3] for x in pairs}); by = collections.defaultdict(list)
    for i, x in enumerate(pairs): by[x[3]].append(i)
    g = random.Random(11); ds = []
    for _ in range(3000):
        idx = [i for _ in jobsl for i in by[jobsl[g.randrange(len(jobsl))]]]
        ds.append(float(np.median(a[idx]) - np.median(s[idx])))
    ds.sort()
    return {"n_pairs": len(pairs), "matchups": len(jobsl), "proc_median_abs_log": round(float(np.median(a)), 3), "sen2cor_median_abs_log": round(float(np.median(s)), 3),
            "relative_improvement": round(float((np.median(s) - np.median(a)) / np.median(s)), 3), "diff_ci95": [round(ds[75], 3), round(ds[2924], 3)]}
out["paired_vs_sen2cor"] = {p: paired(p) for p in PROCS[1:]}
# metric 4, plausibility: share of non-positive rho_w in B02-B05 and the median rho_w(B11) where the processor reports it
def plaus(p):
    v = [r["proc"][p][b] for r in rows if r["proc"].get(p) for b in ("B02", "B03", "B04", "B05") if r["proc"][p].get(b) is not None]
    b11 = [r["proc"][p]["B11"] for r in rows if r["proc"].get(p) and r["proc"][p].get("B11") is not None]
    return {"values": len(v), "share_non_positive": round(sum(1 for x in v if x <= 0) / len(v), 3) if v else None,
            "median_B11": round(float(np.median(b11)), 4) if b11 else None}
out["plausibility"] = {p: plaus(p) for p in PROCS}
json.dump({"summary": out, "rows": rows}, open(f"{S}/analysis/part_b_aeronet.json", "w"), indent=1, default=float)
print(json.dumps(out, indent=1, default=float))
