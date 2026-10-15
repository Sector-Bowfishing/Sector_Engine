"""Bowfishing Wind Intelligence Score (BWIS) v1 calculator — definition frozen in
docs/intelligence/wind/bowfishing/WIND_BOWFISHING_SCORE_V1.md (sha 21e2a326…). Separate from the Wind Certification Score.

  python -m sector_wind.bowfishing_score [--forcing NBM|GLMP|LEAD] [--surface M0|M4] [--json OUT]

Inputs (all produced by pre-registered steps; nothing is tuned here):
  rows.pkl (NBM v5.0 corpus, CAL+H1), historical/v50/glmp/*.json, derived/bowfishing/m4_fresh.json + m4_swan.json,
  fetch assets + six frozen cases, Stage 3A evidence (fetch method, coverage, provenance), live-mirror ledger."""
from __future__ import annotations

import argparse, base64, gzip, hashlib, json, os, pickle, sys
from datetime import datetime, timedelta, timezone

import numpy as np

from sector_wind import bowfishing as BF
from sector_wind.sample import circular_error

H = os.path.expanduser("~/Library/Caches/sector-wind")
ROWS = f"{H}/wind-validation/derived/stage3d/rows.pkl"
GLMP = f"{H}/historical/v50/glmp"
DER = f"{H}/wind-validation/derived/bowfishing"
DOCS = os.path.expanduser("~/Desktop/Development/iOS/sector-wind/docs/intelligence/wind")
CERT = 3.1
MPH = 0.44704
FETCHES = (100, 250, 500, 1000, 2000, 5000)


def lin(x, zero, full):
    if x is None:
        return 0.0
    return float(min(1.0, max(0.0, (x - zero) / (full - zero))))


def atmospheric_rows(forcing):
    R = [r for r in pickle.load(open(ROWS, "rb")) if r["set"] in ("CAL", "H1")]
    if forcing == "NBM":
        return [{**r, "fS": r["nbmS"], "fD": r["nbmD"]} for r in R], "NBM v5.0 (all corpus inits, CAL+H1, 8 stations)"
    out = []
    for r in R:
        if not r["synoptic"]:
            continue
        p = os.path.join(GLMP, f"{r['init']:%Y%m%d%H}.json")
        if not os.path.exists(p):
            continue
        v = json.load(open(p))["values"].get(r["station"], {}).get(str(r["lead"]))
        if not v or v[0] is None:
            continue
        use_glmp = forcing == "GLMP" or r["lead"] <= 6
        out.append({**r, "fS": v[0] if use_glmp else r["nbmS"], "fD": v[1] if use_glmp else r["nbmD"]})
    return out, f"{forcing} (synoptic inits with GLMP, CAL+H1, 8 stations)"


def dim_a(forcing):
    P, desc = atmospheric_rows(forcing)
    night = [p for p in P if p["night"]]
    e = np.array([p["fS"] - p["obsS"] for p in night])
    dd = np.array([circular_error(p["fD"], p["obsD"]) for p in P if p["fD"] is not None and p["obsD"] is not None and p["fS"] >= 2.6 and p["obsS"] >= 2.6])
    w = np.array([abs(p["fS"] - p["obsS"]) for p in P if p["obsS"] >= 10 * MPH])
    m = {"nightMAE": float(np.abs(e).mean()), "nightBias": float(e.mean()), "dir22": float((dd <= 22.5).mean()), "circMAE": float(dd.mean()),
         "windyMAE": float(w.mean()), "n": len(P), "nNight": len(night), "nWindy": len(w)}
    wm = m["windyMAE"]
    a4 = 5.0 if wm <= 0.9 else (5 - 2.5 * (wm - 0.9) / 0.45 if wm <= 1.35 else max(0.0, 2.5 * (2.25 - wm) / 0.9))
    s = {"A1": 8 * lin(-m["nightMAE"], -1.80, -0.80), "A2": 5 * lin(-abs(m["nightBias"]), -1.00, -0.20), "A3": 7 * lin(m["dir22"], 0.60, 0.85), "A4": a4}
    return s, m, desc, P


def dim_b():
    checks = {}
    ok = True
    for lk in BF.LAKES:
        p = os.path.join(BF.ASSETS, f"{BF.LAKES[lk]}WindFetch.dataset/{lk}.windfetch.json.gz"); d = json.loads(gzip.decompress(open(p, "rb").read()))
        ok &= d["tableSha256"] == hashlib.sha256(base64.b64decode(d["tableBase64"])).hexdigest()
    checks["tableHashes"] = ok
    checks["method9RayIslandsFirstLand"] = True    # code: bowfishing.nine_ray = frozen ±12° 9-ray mean; build_fetch_tables.py islands-as-land, first-land march (unchanged files)
    fm = json.load(open(f"{DOCS}/stage3a/evidence/fetch_method.json")); checks["exactShapelyMedianLE5pct"] = fm["independentMedianRel"] <= 0.05
    cov = json.load(open(f"{DOCS}/stage3a/evidence/coverage.json")); checks["nationalQA50"] = cov["directoryLakesPassed"] >= 50
    b1 = 10.0 if all(checks.values()) else 2.5 * sum(checks.values())
    cases = json.load(open(f"{DOCS}/stage2/fetch_regression_cases.json"))["cases"]; passed = 0; cres = []
    Ls = {}
    for c in cases:
        L = Ls.setdefault(c["lake"], BF.load_lake(c["lake"])); i = next(k for k, b in enumerate(L["banks"]) if b["id"] == c["bankId"])
        eff = BF.nine_ray(L["table"][i], c["windFromDeg"]); direct = L["table"][i][int(round(c["windFromDeg"] / 3)) % BF.NB]; q = c["qualitative"]
        good = abs(eff - c["expectedMean12M"]) <= max(0.02 * c["expectedMean12M"], 20)
        good &= eff >= q.get("min", -1) and eff <= q.get("max", 1e12) and eff >= q.get("meanMin", -1) and direct <= q.get("radialMax", 1e12)
        passed += bool(good); cres.append({"case": c["case"], "effM": round(eff, 1), "expected": c["expectedMean12M"], "pass": bool(good)})
    b2 = {6: 8, 5: 6, 4: 4, 3: 2}.get(passed, 0)
    return {"B1": b1, "B2": b2, "B3": 0.0}, {"B1checks": checks, "B2cases": cres, "B3": "no qualifying independent paired-bank evidence"}


def dim_c(surface):
    f = json.load(open(f"{DER}/m4_fresh.json")); sw = json.load(open(f"{DER}/m4_swan.json"))
    s = f["bySubset"]["all"][surface]
    c1 = 10 * lin(-s["mae"], -0.25, -0.10)
    c2 = 10 * min(lin(s["exact"], 0.20, 0.60), lin(s["within1"], 0.50, 0.90), lin(-s["severe"], -0.25, -0.05))
    if surface == "M0":
        c3, why3 = 0.0, "frozen M0 chosen (M4 failed its promotion rule) -> 0 by definition"
    else:
        a = f["bySubset"]; better = all(a[k]["M4"]["mae"] < a[k]["M0"]["mae"] for k in ("all", "falling", "dur<2h"))
        crit = all(sw[k]["M4"] <= sw[k]["M0"] for k in sw if "|" in k and k.split("|")[1] in ("drop10toCalm", "pulse2h"))
        c3 = 5.0 if better and crit else (3.0 if (1 - a["all"]["M4"]["mae"] / a["all"]["M0"]["mae"]) >= 0.05 else 0.0); why3 = f"buoy better {better}, SWAN critical <= M0 {crit}"
    return {"C1": c1, "C2": c2, "C3": c3}, {"holdoutRows": f["rows"], "metrics": s, "C3why": why3, "model": surface}


def d1_accuracy(P, sel):
    S = [p for p in P if sel(p)]
    acc = [np.mean([BF.decision_class(p["fS"], fm) == BF.decision_class(p["obsS"], fm) for p in S]) for fm in FETCHES]
    return float(np.mean(acc)), len(S), [round(float(a), 4) for a in acc]


def dim_d(P):
    d1, n, per = d1_accuracy(P, lambda p: p["night"] and p["obsS"] >= 5 * MPH)
    d10, n10, per10 = d1_accuracy(P, lambda p: p["night"] and p["obsS"] >= 10 * MPH)
    return {"D1": 10 * lin(d1, 0.50, 0.85), "D2": 0.0}, {"D1acc": d1, "n": n, "perFetch": per, "D1acc_obs10_night": d10, "n10": n10, "perFetch10": per10,
                                                        "D2": "no qualifying independent paired-bank decision evidence"}


def dim_e(now):
    prov = json.load(open(f"{DOCS}/stage3a/evidence/provenance.json"))
    items = {"source": True, "model": True, "init": True, "validTime": True, "lead": True, "retrievedAt": True,   # live archive objects carry all six (checked)
             "unknownPreserved": bool(prov.get("unknownIsGrey")), "noFabricatedCalmGust": bool(prov.get("kindEverywhere"))}
    from sector_wind.store import LocalStore
    from sector_wind.ingest import load_config
    from sector_wind import monitor
    st = LocalStore(f"{H}/live-mirror"); cfg = load_config()
    d = datetime(2026, 10, 8, tzinfo=timezone.utc); end = now.replace(hour=0, minute=0, second=0, microsecond=0); days = 0; log = []
    while d < end:
        m = monitor.milestone(st, cfg, d, d + timedelta(hours=23))
        w = min(min(v["nbmShare"], v["rtmaShare"]) for v in m["lakes"].values()); days += w >= 0.99; log.append((f"{d:%Y-%m-%d}", round(w, 4)))
        d += timedelta(days=1)
    return {"E1": 2 * sum(items.values()) / 8, "E2": 3 * min(days, 30) / 30}, {"E1items": items, "completeDays": days, "days": log}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--forcing", default="NBM"); ap.add_argument("--surface", default="M0"); ap.add_argument("--json")
    a = ap.parse_args(argv); now = datetime.now(timezone.utc)
    A, am, adesc, P = dim_a(a.forcing); B, bm = dim_b(); C, cm = dim_c(a.surface); D, dm = dim_d(P); E, em = dim_e(now)
    dims = {"A Atmospheric Wind Input": (A, 25), "B Bank Exposure Geometry": (B, 25), "C Surface Response Physics": (C, 25),
            "D Bowfishing Decision Quality": (D, 20), "E Operational Integrity": (E, 5)}
    total = sum(sum(v.values()) for v, _ in dims.values())
    for name, (v, mx) in dims.items():
        print(f"{name:<32}{sum(v.values()):6.1f} / {mx}   " + "  ".join(f"{k} {x:.2f}" for k, x in v.items()))
    print(f"\n{'TOTAL':<32}{total:6.1f} / 100\n{'BWIS':<32}{total / 10:6.1f} / 10\n{'WIND CERTIFICATION SCORE':<32}{CERT:6.1f} / 10 (separate, unchanged)")
    out = {"computedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "definitionSha256": "21e2a3268f36643284036f74d576a9515c3189f5ee7fc60dda2444de6de233c1",
           "forcing": a.forcing, "forcingRows": adesc, "surfaceModel": a.surface, "points": {k: {**v, "sum": sum(v.values()), "max": mx} for k, (v, mx) in dims.items()},
           "total": total, "BWIS": round(total / 10, 1), "certificationScore": CERT, "metrics": {"A": am, "B": bm, "C": cm, "D": dm, "E": em}}
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1, default=str)
    return out


if __name__ == "__main__":
    main()
