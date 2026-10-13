#!/usr/bin/env python3
"""Depth Brain / contour effective-zone validation vs CWMS stage-area curves. Computes the preregistered comparison and nothing else.
Verifies sha256 of contour_prereg.json and of the frozen data files first. Uses the REAL depth_brain.zones code.
Outputs: docs/brains/depth/data/contour2_validation_rows.csv, contour2_validation_summary.json.
Run: .../depth-brain/contour2/venv/bin/python -I research/depth/contour2_validate.py"""
import csv, hashlib, json, math, sys
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "jobs/depth-brain"))
from depth_brain import zones as Z   # noqa: E402

PRE = REPO / "jobs/depth-brain/depth_brain/data/proposals/contour_prereg.json"
DD = REPO / "docs/brains/depth/data"


def verify():
    doc = json.loads(PRE.read_text()); fr = doc.pop("freeze")
    h = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    if h != fr["sha256"]:
        sys.exit(f"PREREG HASH MISMATCH {h} != {fr['sha256']}")
    for k, f in (("factsSha256", "contour2_lake_facts.json"), ("curvesSha256", "contour2_curves.csv")):
        if hashlib.sha256((DD / f).read_bytes()).hexdigest() != doc["dataBinding"][k]:
            sys.exit(f"DATA HASH MISMATCH {f}")
    doc["freeze"] = fr
    return doc


class Curve:
    def __init__(self, e, a):
        o = np.argsort(e); self.e, self.a = np.array(e)[o], np.array(a)[o]
    def A(self, x):
        if x > self.e[-1] + 1e-9: return None
        if x < self.e[0] - 1e-9: return 0.0 if self.a[0] == 0 else None
        return float(np.interp(x, self.e, self.a))


def main():
    P = verify(); th = P["thresholds"]; levels = P["levels"]["drawdownBelowPRefFt"]
    facts = json.load(open(DD / "contour2_lake_facts.json"))["lakes"]; roster = P["referenceVerification"]["rosterAndStatus"]
    cur = {}
    for r in csv.DictReader(open(DD / "contour2_curves.csv")):
        cur.setdefault(r["lakeId"], ([], []))[0].append(float(r["elevFt"])); cur[r["lakeId"]][1].append(float(r["areaAc"]))
    sigma = math.sqrt(0.25 ** 2 + 0.1 ** 2 + 0.1 ** 2)
    rows, excl, diag = [], [], {}
    for lid, R in roster.items():
        if not R["hasCurve"] or R["pRefFt"] is None:
            continue
        f = facts[lid]; C = Curve(*cur[lid]); p = R["pRefFt"]; Aref = C.A(p)
        if not Aref:
            excl.append(dict(lakeId=lid, reason="curve undefined or zero at pRef")); continue
        z = Z.reference_zones_from_shares(f["shares"], f["intervalFt"], f.get("coverage") or 1.0, f["tier"], f["src"], reference_verified=True)
        if z is None:
            excl.append(dict(lakeId=lid, reason="no usable reference shares")); continue
        # diagnostics D1/D2
        sup = sorted(z.cumulative)
        def Sc(P_, e):
            a0, a1 = C.A(P_), C.A(P_ - e)
            return None if (a0 in (None, 0) or a1 is None) else (a0 - a1) / a0
        d1 = {str(e): (None if Sc(p, e) is None else round(z.cumulative[e] - Sc(p, e), 4)) for e in sup}
        best = None
        for k in range(-60, 61):
            P_ = p + k / 10.0; ss = [Sc(P_, e) for e in sup]
            if any(s is None for s in ss): continue
            err = sum((z.cumulative[e] - s) ** 2 for e, s in zip(sup, ss))
            if best is None or err < best[0]: best = (err, P_ - p)
        diag[lid] = dict(D1_contourMinusCurveShareAtPRef=d1, D2_impliedPoolMinusPRefFt=None if best is None else round(best[1], 1), supportedEdges=sup, curveVersion=f["curve"]["effectiveDate"][:10],
                         surveyYear=(f["pSrc"] or {}).get("surveyYear"), curveElevRange=[f["curve"]["elevMin"], f["curve"]["elevMax"]])
        for d in levels:
            Lw = p - d
            if C.A(Lw) is None:
                excl.append(dict(lakeId=lid, d=d, reason="curve does not reach pRef-d")); continue
            def band(lo_off, hi_off):
                a, b = C.A(Lw - lo_off), (C.A(Lw - hi_off) if hi_off is not None else 0.0)
                return None if a is None or b is None else (a - b) / Aref
            truth = {"dry": 1 - C.A(Lw) / Aref, "under3": band(0, 3), "threeToSix": band(3, 6), "sixToTen": band(6, 10), "deeper": (None if C.A(Lw - 10) is None else C.A(Lw - 10) / Aref)}
            for smode, sg in (("production", sigma), ("zero", 0.0)):
                r = Z.effective_zones(z, -d, sg); assert r["available"]
                for bn, tv in truth.items():
                    if tv is None: continue
                    s = r["shares"].get(bn)
                    base = dict(lakeId=lid, group=R["group"], status=R["referenceStatus"], intervalFt=f["intervalFt"], sigmaMode=smode, d=d, band=bn, truth=round(tv, 5))
                    if s is None:
                        rows.append({**base, "published": 0, "lo": "", "hi": "", "mid": "", "err": "", "inside": "", "width": ""})
                    else:
                        lo, hi = s["lo"], s["hi"]; mid = (lo + hi) / 2
                        rows.append({**base, "published": 1, "lo": lo, "hi": hi, "mid": round(mid, 5), "err": round(mid - tv, 5), "inside": int(lo - 0.0005 <= tv <= hi + 0.0005), "width": round(hi - lo, 5)})
    DD.mkdir(parents=True, exist_ok=True)
    with open(DD / "contour2_validation_rows.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    def stats(rs):
        pub = [r for r in rs if r["published"]]; out = dict(nIncluded=len(rs), nPublished=len(pub), publishRate=(len(pub) / len(rs)) if rs else None)
        if pub:
            e = np.array([r["err"] for r in pub]); w = np.array([r["width"] for r in pub]); ins = np.array([r["inside"] for r in pub])
            out.update(mae=float(np.abs(e).mean()), maxAbs=float(np.abs(e).max()), bias=float(e.mean()), coverage=float(ins.mean()), widthMedian=float(np.median(w)), widthP90=float(np.percentile(w, 90)))
            if len(pub) >= 3 and len({r["truth"] for r in pub}) > 1 and len({r["mid"] for r in pub}) > 1:
                out["spearmanPooled"] = float(spearmanr([r["mid"] for r in pub], [r["truth"] for r in pub])[0])
        return out

    def passes(s, pooled=False):
        if not s["nPublished"] or s["nPublished"] < th["T6_minPublishedLevelsPerLake"]:
            return dict(all=False, why="fewer than %d published lake-levels" % th["T6_minPublishedLevelsPerLake"], T6=False)
        ok = dict(T1=s["mae"] <= th["T1_MAE_max"], T2=s["maxAbs"] <= th["T2_maxAbsError_max"], T3=s["coverage"] >= th["T3_boundsCoverage_min"], T4=s["widthMedian"] <= th["T4_medianBoundsWidth_max"], T6=s["publishRate"] >= th["T6_publishRate_min"])
        if pooled: ok["T5"] = s.get("spearmanPooled", 0) >= th["T5_pooledSpearman_min"]
        ok["all"] = all(ok.values()); return ok

    sel = lambda **k: [r for r in rows if all(r[a] == v for a, v in k.items())]
    S = dict(prereg=dict(sha256=P["freeze"]["sha256"], frozenAtUtc=P["freeze"]["frozenAtUtc"]), sigmaProduction=round(sigma, 4), perLake={}, pooled={}, bands={}, diagnostics=diag, excluded=excl, baseline={})
    lakes = sorted({r["lakeId"] for r in rows})
    for lid in lakes:
        g = roster[lid]["group"]; ent = {}
        for sm in ("production", "zero"):
            rs = sel(lakeId=lid, sigmaMode=sm, band="dry"); st = stats(rs)
            if sm == "production" and g == "GRADED": st["pass"] = passes(st)
            ent[sm] = st
        ent["group"] = g; ent["status"] = roster[lid]["referenceStatus"]; ent["intervalFt"] = roster[lid]["intervalFt"]
        ent["passed"] = (ent["production"]["pass"]["all"] if g == "GRADED" else None)
        S["perLake"][lid] = ent
    graded = [l for l in lakes if roster[l]["group"] == "GRADED"]; assumed = [l for l in lakes if roster[l]["group"] != "GRADED"]
    for name, grp in (("GRADED", graded), ("ASSUMED_ALL", assumed), ("ASSUMED_interval_le3", [l for l in assumed if roster[l]["intervalFt"] <= 3]),
                      ("ASSUMED_interval_5", [l for l in assumed if roster[l]["intervalFt"] == 5]), ("ASSUMED_interval_10", [l for l in assumed if roster[l]["intervalFt"] == 10])):
        for sm in ("production", "zero"):
            rs = [r for r in rows if r["lakeId"] in grp and r["sigmaMode"] == sm and r["band"] == "dry"]
            if rs:
                s = stats(rs); s["lakes"] = grp
                if name == "GRADED" and sm == "production": s["pass"] = passes(s, pooled=True)
                S["pooled"].setdefault(name, {})[sm] = s
        for bn in ("under3", "threeToSix", "sixToTen", "deeper"):
            rs = [r for r in rows if r["lakeId"] in grp and r["sigmaMode"] == "production" and r["band"] == bn]
            if rs: S["bands"].setdefault(name, {})[bn] = stats(rs)
    # baseline: leave-one-lake-out mean truth dry share at same d, per group
    tr = {(r["lakeId"], r["d"]): r["truth"] for r in rows if r["sigmaMode"] == "zero" and r["band"] == "dry"}
    for name, grp in (("GRADED", graded), ("ASSUMED_ALL", assumed)):
        be = []
        for l in grp:
            for d in levels:
                if (l, d) not in tr: continue
                oth = [tr[(o, d)] for o in grp if o != l and (o, d) in tr]
                if oth: be.append(abs(np.mean(oth) - tr[(l, d)]))
        S["baseline"][name] = dict(maeLeaveOneLakeOutMean=(float(np.mean(be)) if be else None), n=len(be))
    (DD / "contour2_validation_summary.json").write_text(json.dumps(S, indent=1))
    print(json.dumps({k: v for k, v in S["pooled"].items()}, indent=1)[:3500])
    print({l: (v["group"], v["production"].get("nPublished"), v["production"].get("nIncluded"), v["passed"]) for l, v in S["perLake"].items()})


if __name__ == "__main__":
    main()
