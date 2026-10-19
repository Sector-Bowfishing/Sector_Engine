"""Collect the evidence the platform scorer needs for Wind's three measurements (Bowfishing Intelligence V2, Scientific
Confidence, Production Readiness). Research-only (reads the research caches and the legacy evidence files); writes ONE
metadata-only JSON (numbers, counts, hashes; no paths, no raw data) that is committed and read by
jobs/brain_platform/sector_brain_platform/wind_measurements.py. Nothing here scores: the scorer applies the rubric.

  python -m sector_wind_research.measurement_evidence --out docs/brains/scoring/evidence/wind-measurements-evidence.json

Inputs are the SAME ones BWIS v1 and the certification scoreboard use (all CAL+H1 / fresh buoy holdout / frozen geometry):
  * atmospheric rows: NBM v5.0 corpus CAL+H1 (rows.pkl) via bowfishing_score.dim_a  -- H2 is never read;
  * deterministic strong-wind / gust event skill: the frozen certification skill file via scoreboard.dims_1_to_4;
  * geometry QA + six canonical cases: bowfishing_score.dim_b;   surface physics vs buoys 2020-23: bowfishing_score.dim_c(M0);
  * field certification ledger, over-water reference, coverage, provenance: the Stage 3A evidence files;
  * the probabilistic strong-wind flag: the exploratory analysis output (reported as EXPLORATORY, never scored);
  * capability scenarios: sector_wind.decision.scenarios on the FULL frozen fetch table of each development lake.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone

import numpy as np

from sector_wind import bowfishing as BF
from sector_wind.brain.lakes import WIND_LAKE_IDS
from sector_wind.decision import scenarios as SCN
from sector_wind.decision.schema import DECISION_SCHEMA, KNOWLEDGE_VERSION
from sector_wind_research import bowfishing_score as BW
from sector_wind_research import scoreboard as SB
from sector_wind_research.bowfishing_assets import load_lake

SCHEMA = "wind-measurements-evidence-v1"
RESEARCH_OUT = os.path.expanduser("~/Desktop/Development/Sector Research/wind-brain/analysis/out")
EVIDENCE_DIR = os.path.join(BW.DOCS, "stage3a", "evidence")
MPH = BF.MPH


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def _r(x, n=4):
    return None if x is None else round(float(x), n)


def atmospheric():
    A, m, desc, P = BW.dim_a("NBM")
    night = [p for p in P if p["night"]]

    def acc(sel):
        S = [p for p in night if sel(p)]
        per = [float(np.mean([BF.decision_class(p["fS"], f) == BF.decision_class(p["obsS"], f) for p in S])) for f in BW.FETCHES]
        return _r(np.mean(per)), len(S), [_r(a) for a in per]

    sym, n_sym, per_sym = acc(lambda p: p["obsS"] >= 5 * MPH or p["fS"] >= 5 * MPH)
    v1, n_v1, _ = acc(lambda p: p["obsS"] >= 5 * MPH)
    w10, n10, _ = acc(lambda p: p["obsS"] >= 10 * MPH)
    allnight, n_all, _ = acc(lambda p: True)
    return {"rows": desc, "nRows": m["n"], "nNight": m["nNight"], "nightSpeedMaeMS": _r(m["nightMAE"]), "nightSpeedBiasMS": _r(m["nightBias"]),
            "directionWithin22_5": _r(m["dir22"]), "directionCircMaeDeg": _r(m["circMAE"], 2), "windyHourMaeMS": _r(m["windyMAE"]), "nWindy": m["nWindy"],
            "decisionAccuracy": {"symmetricNight5mph": sym, "nSymmetric": n_sym, "perFetchSymmetric": per_sym,
                                 "v1ObservedNight5mph": v1, "nV1": n_v1, "observedNight10mph": w10, "nObserved10": n10, "allNight": allnight, "nAllNight": n_all,
                                 "fetchesM": list(BW.FETCHES), "definition": "share of night rows where surface class P from the forecast wind equals P from the "
                                 "observed wind (frozen CEM, 6 h steady), equal weight per fetch; symmetric = observed OR forecast >= 5 mph (BWIS v1 D1 note)"},
            "h2Read": False}


def strong_wind():
    w = json.load(open(os.path.join(EVIDENCE_DIR, "wind_skill_source.json")))
    skill = json.load(open(os.path.join(EVIDENCE_DIR, w["file"])))
    d = SB.dims_1_to_4(skill, w["label"])
    night = skill["nbm"]["night"]; allh = skill["nbm"]["allHours"]
    flag = None
    p = os.path.join(RESEARCH_OUT, "confidence_flag.json")
    if os.path.exists(p):
        f = json.load(open(p))["obs>=10"]
        flag = {"status": "EXPLORATORY", "data": "CAL+H1 (consumed); recalibration test waits for H2 (2027-01-01)", "eventThreshold": "observed >= 10 mph",
                "pod": f["POD"], "far": f["FAR"], "nEvents": f["nEvents"], "n": json.load(open(p))["n"], "fileSha": _sha(p)}
    return {"source": w["label"], "skillFileSha": _sha(os.path.join(EVIDENCE_DIR, w["file"])),
            "observedNight15mphEvents": sum(night[k].get("n_obs_15mph", 0) for k in SB.LEADS if k in night),
            "pod15mphByLead": {k: night[k].get("pod_15mph") for k in SB.LEADS if k in night},
            "far15mphByLead": {k: night[k].get("far_15mph") for k in SB.LEADS if k in night},
            "gust20ktPodByLead": {k: _r(allh[k].get("gust20_pod")) for k in SB.LEADS if k in allh},
            "gust20ktFarByLead": {k: _r(allh[k].get("gust20_far")) for k in SB.LEADS if k in allh},
            "certificationDim1Why": d[1]["why"], "certificationDim3Why": d[3]["why"], "leadDim4Credit": d[4]["credit"],
            "probabilisticFlag": flag}


def geometry():
    B, bm = BW.dim_b()
    return {"qaChecks": bm["B1checks"], "canonicalCases": bm["B2cases"], "canonicalCasesPassed": sum(c["pass"] for c in bm["B2cases"]),
            "canonicalCasesTotal": len(bm["B2cases"])}


def surface():
    C, cm = BW.dim_c("M0")
    s = cm["metrics"]
    return {"model": "M0", "buoyRows": cm["holdoutRows"], "hm0MaeM": _r(s["mae"]), "exact": _r(s["exact"]), "within1": _r(s["within1"]),
            "severe": _r(s["severe"]), "transient": {"m4Promoted": False, "why": cm["C3why"]}}


def field_and_ops():
    E = lambda n: json.load(open(os.path.join(EVIDENCE_DIR, n)))
    ledger = glob.glob(os.path.join(EVIDENCE_DIR, "certification*.jsonl"))
    rows = sum(1 for p in ledger for l in open(p) if l.strip())
    ow, cov, prov = E("overwater.json"), E("coverage.json"), E("provenance.json")
    return {"field": {"certificationLedgerFiles": len(ledger), "observations": rows, "exposurePairs": 0 if not rows else None, "surfaceObservations": 0 if not rows else None,
                      "requirement": "exposure >= 24 holdout pairs (40 full), >= 2 lakes, >= 3 quadrants; surface >= 36 observations (60 full) under Evidence Addendum v1"},
            "overwater": {"measuredStationComparisons": ow.get("measuredStationComparisons") or 0},
            "coverage": {"developmentLakesComplete": cov.get("developmentLakesComplete"), "directoryLakesPassed": cov.get("directoryLakesPassed")},
            "provenance": {k: bool(prov.get(k)) for k in ("kindEverywhere", "unknownIsGrey", "explanationOnEveryResult")}}


def scenarios():
    out = {}
    for wl, lid in WIND_LAKE_IDS.items():
        L = load_lake(wl); L["lakeId"] = lid; L["subset"] = None
        r = SCN.run(L)
        out[lid] = {"banks": r["banks"], "tableSha256": L["tableSha256"], "passed": r["passed"], "total": r["total"],
                    "results": {s["id"]: s["pass"] for s in r["scenarios"]},
                    "failedChecks": {s["id"]: [c["check"] for c in s["checks"] if not c["pass"]] for s in r["scenarios"] if not s["pass"]}}
    return {"suite": SCN.SUITE_ID, "capabilityMap": SCN.CAPABILITY, "lakes": out, "inputClass": "SYNTHETIC wind on the full frozen fetch tables",
            "evidenceClass": "MODEL_CAPABILITY"}


def collect(now=None):
    now = now or datetime.now(timezone.utc)
    head = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True, cwd=os.path.dirname(__file__)).stdout.strip()
    return {"schema": SCHEMA, "brainId": "wind", "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "codeCommit": head or None,
            "knowledgeVersion": KNOWLEDGE_VERSION, "decisionSchema": DECISION_SCHEMA,
            "inputs": {"atmosphericRowsSha": _sha(BW.ROWS), "bwisV1DefinitionSha256": "21e2a3268f36643284036f74d576a9515c3189f5ee7fc60dda2444de6de233c1",
                       "h2": "SEALED until 2027-01-01 (not read)"},
            "atmospheric": atmospheric(), "strongWind": strong_wind(), "geometry": geometry(), "surface": surface(),
            **field_and_ops(), "scenarios": scenarios()}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    ev = collect()
    txt = json.dumps(ev, indent=1, sort_keys=False, default=str)
    for bad in ("/Users/", "Desktop/", "Library/Caches", "Sector Research"):
        assert bad not in txt, f"local path leaked into evidence: {bad}"
    open(a.out, "w").write(txt + "\n")
    print(f"wrote {a.out}: scenarios " + ", ".join(f"{k} {v['passed']}/{v['total']}" for k, v in ev["scenarios"]["lakes"].items()))


if __name__ == "__main__":
    main()
