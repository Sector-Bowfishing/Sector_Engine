#!/usr/bin/env python3
"""Depth Brain / TWDB effective-zone validation (PART C). Computes the preregistered comparison and nothing else.
Verifies the sha256 of jobs/depth-brain/depth_brain/data/proposals/twdb_prereg.json first. Run with the lake-brain venv python, -I.
Outputs (small): docs/brains/depth/data/twdb_validation_rows.csv, twdb_validation_summary.json
Uses the REAL engine code: depth_brain.zones.reference_zones_from_shares / effective_zones."""
import csv, hashlib, json, math, sys
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "jobs/depth-brain"))
from depth_brain import zones as Z   # noqa: E402

PRE = REPO / "jobs/depth-brain/depth_brain/data/proposals/twdb_prereg.json"
OUTD = REPO / "docs/brains/depth/data"
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/terrain/twdb")
MCSV = Path("/Users/mcather/Desktop/Development/Sector_Engine-depth-research/docs/research/depth-brain/data/contour_method_check_twdb.csv")
SIGMA_POOL, SIGMA_LEVEL = 0.25, {"DIRECT_OPERATOR_POOL": 0.1, "DIRECT_LAKE_GAUGE": 0.15}


def verify_prereg():
    doc = json.loads(PRE.read_text()); fr = doc.pop("freeze")
    h = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    if h != fr["sha256"]:
        sys.exit(f"PREREG HASH MISMATCH {h} != {fr['sha256']}")
    doc["freeze"] = fr
    return doc


def read_table(p):
    a = []
    for line in open(p):
        try:
            e, ar, _ = [float(x) for x in line.strip().split(",")[:3]]; a.append((abs(e), ar))
        except Exception:
            pass
    a = np.array(sorted(a)); return a[:, 0], a[:, 1]


def main():
    P = verify_prereg(); th = P["thresholds"]; levels = P["levels"]["drawdownBelowBasisFt"]
    status = P["referenceVerification"]["declaredOutcomeBeforeResults"]
    mc = {r["key"]: r for r in csv.DictReader(open(MCSV))}
    rows = []
    for lid, L in P["lakes"].items():
        z_, A_ = read_table(RAW / L["key"] / "table.txt")
        A = lambda e: float(np.interp(e, z_, A_, left=0.0))
        b = L["basisFt"]; Aref = A(b); itv = L["publishedContourIntervalFt"]
        assert z_[0] < b - 60 and abs(z_[-1] - b) < 0.2 or lid.startswith("Lake Texoma") or lid.startswith("Lake Livingston")
        cum = {x: (Aref - A(b - x)) / Aref for x in (3.0, 6.0, 10.0)}
        sigma = math.sqrt(SIGMA_POOL ** 2 + SIGMA_LEVEL[L["levelCapability"]] ** 2 + L["datumSigmaFt"] ** 2)
        preds = {"S1": ({"lt3": cum[3.0], "lt6": cum[6.0], "lt10": cum[10.0]}, itv)}
        m = mc.get(L["key"])
        if m and m.get("native_s3"):
            preds["S2"] = ({"lt3": float(m["native_s3"]), "lt6": float(m["native_s6"]), "lt10": float(m["native_s10"])}, itv)
        if m and m.get("d5_s10"):
            preds["S3_d5"] = ({"lt3": float(m["d5_s3"]), "lt6": float(m["d5_s6"]), "lt10": float(m["d5_s10"])}, 5.0)
        if m and m.get("d10_s10"):
            preds["S3_d10"] = ({"lt3": float(m["d10_s3"]), "lt6": float(m["d10_s6"]), "lt10": float(m["d10_s10"])}, 10.0)
        for pname, (sh, interval) in preds.items():
            z = Z.reference_zones_from_shares(sh, interval, 1.0, "A", "TWDB", reference_verified=True)   # counterfactual-verified so Texoma can be computed (informational)
            if pname.startswith("S3"):
                assert sorted(z.cumulative) == [10.0], z.cumulative            # supported-edge rule: no 3/6 ft edges from a 5/10 ft ladder
            if pname in ("S1", "S2") and itv == 5.0:
                assert sorted(z.cumulative) == [10.0], z.cumulative
            for d in levels:
                Lw = b - d
                truth = {"dry": 1 - A(Lw) / Aref, "under3": (A(Lw) - A(Lw - 3)) / Aref, "threeToSix": (A(Lw - 3) - A(Lw - 6)) / Aref,
                         "sixToTen": (A(Lw - 6) - A(Lw - 10)) / Aref, "deeper": A(Lw - 10) / Aref}
                for smode, sg in (("production", sigma), ("zero", 0.0)):
                    r = Z.effective_zones(z, -d, sg)
                    assert r["available"]
                    for band, tv in truth.items():
                        s = r["shares"][band]; lo, hi = s["lo"], s["hi"]
                        rows.append(dict(lakeId=lid, status=status[lid], predictor=pname, intervalFt=interval, sigmaMode=smode, sigmaFt=round(sg, 3), d=d, band=band,
                                         truth=round(tv, 5), lo=lo, hi=hi, mid=round((lo + hi) / 2, 5), err=round((lo + hi) / 2 - tv, 5),
                                         inside=int(lo - 0.0005 <= tv <= hi + 0.0005), width=round(hi - lo, 5)))
    OUTD.mkdir(parents=True, exist_ok=True)
    with open(OUTD / "twdb_validation_rows.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    def stats(rs):
        e = np.array([r["err"] for r in rs]); w = np.array([r["width"] for r in rs]); ins = np.array([r["inside"] for r in rs])
        out = dict(n=len(rs), mae=float(np.abs(e).mean()), maxAbs=float(np.abs(e).max()), bias=float(e.mean()), coverage=float(ins.mean()),
                   widthMedian=float(np.median(w)), widthP90=float(np.percentile(w, 90)))
        if len(rs) > 2:
            out["spearmanPooled"] = float(spearmanr([r["mid"] for r in rs], [r["truth"] for r in rs])[0])
        return out

    def passes(s, pooled=False):
        ok = dict(T1=s["mae"] <= th["T1_MAE_max"], T2=s["maxAbs"] <= th["T2_maxAbsError_max"], T3=s["coverage"] >= th["T3_boundsCoverage_min"], T4=s["widthMedian"] <= th["T4_medianBoundsWidth_max"])
        if pooled:
            ok["T5"] = s.get("spearmanPooled", 0) >= th["T5_pooledSpearman_min"]
        ok["all"] = all(ok.values()); return ok

    S = dict(prereg=dict(sha256=P["freeze"]["sha256"], frozenAtUtc=P["freeze"]["frozenAtUtc"]), perLake={}, pooled={}, perLevelCrossLakeSpearman={}, baseline={}, band={})
    sel = lambda **k: [r for r in rows if all(r[a] == v for a, v in k.items())]
    for lid in P["lakes"]:
        for pn in ("S1", "S2", "S3_d5", "S3_d10"):
            for sm in ("production", "zero"):
                rs = sel(lakeId=lid, predictor=pn, sigmaMode=sm, band="dry")
                if rs:
                    s = stats(rs); s["pass"] = passes(s) if sm == "production" and pn in ("S1", "S2") and status[lid] == "VERIFIED" else None
                    S["perLake"].setdefault(lid, {}).setdefault(pn, {})[sm] = s
    graded = [l for l in P["lakes"] if status[l] == "VERIFIED"]
    for pn in ("S1", "S2"):
        for sm in ("production", "zero"):
            rs = [r for r in rows if r["lakeId"] in graded and r["predictor"] == pn and r["sigmaMode"] == sm and r["band"] == "dry"]
            if rs:
                s = stats(rs); s["lakes"] = sorted({r["lakeId"] for r in rs}); s["pass"] = passes(s, pooled=True) if sm == "production" else None
                S["pooled"].setdefault(pn, {})[sm] = s
        for band in ("under3", "threeToSix", "sixToTen", "deeper"):
            rs = [r for r in rows if r["lakeId"] in graded and r["predictor"] == pn and r["sigmaMode"] == "production" and r["band"] == band]
            if rs:
                S["band"].setdefault(pn, {})[band] = stats(rs)
        for d in levels:
            rs = [r for r in rows if r["lakeId"] in graded and r["predictor"] == pn and r["sigmaMode"] == "production" and r["band"] == "dry" and r["d"] == d]
            if len(rs) > 2:
                S["perLevelCrossLakeSpearman"].setdefault(pn, {})[str(d)] = float(spearmanr([r["mid"] for r in rs], [r["truth"] for r in rs])[0])
    # baseline: leave-one-lake-out mean truth dry share at the same d (graded lakes)
    tr = {(r["lakeId"], r["d"]): r["truth"] for r in rows if r["predictor"] == "S1" and r["sigmaMode"] == "zero" and r["band"] == "dry"}
    be = []
    for l in graded:
        for d in levels:
            oth = [tr[(o, d)] for o in graded if o != l]; be.append(abs(np.mean(oth) - tr[(l, d)]))
    S["baseline"] = dict(maeLeaveOneLakeOutMean=float(np.mean(be)), maxAbs=float(np.max(be)), n=len(be))
    # per-lake final flag
    for lid in P["lakes"]:
        if status[lid] != "VERIFIED":
            S["perLake"][lid]["passed"] = None; continue
        pl = S["perLake"][lid]; flags = [pl[p]["production"]["pass"]["all"] for p in ("S1", "S2") if p in pl]
        pl["passed"] = all(flags); pl["predictorsGraded"] = [p for p in ("S1", "S2") if p in pl]
    (OUTD / "twdb_validation_summary.json").write_text(json.dumps(S, indent=1))
    print(json.dumps(S["pooled"], indent=1)); print(json.dumps({l: {"passed": v.get("passed")} for l, v in S["perLake"].items()}))


if __name__ == "__main__":
    main()
