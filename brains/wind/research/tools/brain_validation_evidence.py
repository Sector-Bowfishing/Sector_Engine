"""Freeze the Wind Brain validation summary from already-published, pre-registered evidence (no new science).

  python research/brain_validation_evidence.py     # -> sector_wind/brain/validation_evidence.json

Atmospheric skill: the Stage 3C/3D NBM v5.0 historical corpus (pre-registered, sha in WIND_HISTORICAL_CORPUS_PREREG),
CAL + H1 = 2026-05-06 .. 2026-10-06, METAR at the 8 frozen stations, leads 1/3/6/12/18, forcing UNTUNED (nothing fitted).
H2 (2026-10-07 .. 2026-12-31) is sealed and never read. The production proxy (HRRR = what Open-Meteo Best Match serves
for 0-46 h) is reported on the identical rows where HRRR was archived.
Surface physics: frozen CEM (M0) vs the untouched 2020-2023 buoy holdout (Bowfishing stage, m4_fresh.json).
Scores: Wind Certification Score (frozen rubric) and BWIS v1 (frozen definition) as last computed."""
import json, math, os, pickle, sys
from collections import defaultdict
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "runtime"))  # brains/wind/runtime
import numpy as np
from sector_wind.sample import circular_error
from sector_wind.ingest import load_config

ROWS = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/stage3d/rows.pkl")
FRESH = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/bowfishing/m4_fresh.json")
BWIS = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/bowfishing/bwis.json")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sector_wind", "brain", "validation_evidence.json")
MPH = 0.44704
KT = 0.514444
WIND_TO_ID = {"guntersville": "Guntersville|AL", "wheeler": "Wheeler|AL", "wilson": "Wilson|AL", "pickwick": "Pickwick Lake|TN"}


def metrics(R, s, d, g):
    R = [r for r in R if r.get(s) is not None]
    if not R:
        return None, 0
    e = np.array([r[s] - r["obsS"] for r in R]) / MPH
    night = np.array([r[s] - r["obsS"] for r in R if r["night"]]) / MPH
    dd = np.array([circular_error(r[d], r["obsD"]) for r in R if r.get(d) is not None and r["obsD"] is not None and r[s] >= 2.6 and r["obsS"] >= 2.6])
    gg = np.array([(r[g] - r["obsG"]) / MPH for r in R if r.get(g) is not None and r["obsG"] is not None])
    windy = np.array([abs(r[s] - r["obsS"]) / MPH for r in R if r["obsS"] >= 10 * MPH])
    hit = sum(r[s] >= 15 * MPH and r["obsS"] >= 15 * MPH for r in R); obs15 = sum(r["obsS"] >= 15 * MPH for r in R)
    fa = sum(r[s] >= 15 * MPH and r["obsS"] < 15 * MPH for r in R)
    m = {"speedMaeMph": float(np.abs(e).mean()), "speedBiasMph": float(e.mean()), "nightSpeedMaeMph": float(np.abs(night).mean()) if len(night) else None,
         "nightSpeedBiasMph": float(night.mean()) if len(night) else None, "windyHourSpeedMaeMph": float(windy.mean()) if len(windy) else None,
         "directionMaeDeg": float(dd.mean()) if len(dd) else None, "directionWithin22_5Pct": float(100 * (dd <= 22.5).mean()) if len(dd) else None,
         "gustMaeMph": float(np.abs(gg).mean()) if len(gg) else None, "gustConditionalBiasMph": float(gg.mean()) if len(gg) else None,
         "event15mphPod": hit / obs15 if obs15 else None, "event15mphFar": fa / (hit + fa) if hit + fa else None}
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items()}, len(R)


def main():
    R = [r for r in pickle.load(open(ROWS, "rb")) if r["set"] in ("CAL", "H1")]
    assert all(r["init"] < datetime(2026, 10, 7, tzinfo=timezone.utc) for r in R), "H2 inits present"   # H2 is defined by init
    cfg = load_config()
    fleet, n = metrics(R, "nbmS", "nbmD", "nbmG")
    prod, n_prod = metrics([r for r in R if r.get("hrrrS") is not None], "hrrrS", "hrrrD", "hrrrG")
    cand_on_prod_rows, _ = metrics([r for r in R if r.get("hrrrS") is not None], "nbmS", "nbmD", "nbmG")
    by_type = defaultdict(list)
    for r in R:
        by_type[r["type"]].append(r)
    per_lake = {}
    for wl, lid in WIND_TO_ID.items():
        rr = [r for r in R if r["lake"] == wl]
        m, k = metrics(rr, "nbmS", "nbmD", "nbmG")
        per_lake[lid] = {"stations": sorted({r["station"] for r in rr}), "sampleCount": k, "metrics": m}
    fresh = json.load(open(FRESH))["bySubset"]["all"]["M0"]
    bwis = json.load(open(BWIS))
    out = {
        "frozenAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "candidateModel": "wind-candidate-2026.10.stage2-baseline",
        "forcing": "NOAA NBM v5.0, direct NODD, Candidate decoder, bilinear to station",
        "window": {"start": "2026-05-06", "end": "2026-10-06", "splits": ["CAL", "H1"], "h2": "SEALED until 2027-01-01 (not read)"},
        "holdoutType": "pre-registered historical corpus; forcing untuned (no fitting), so CAL+H1 are both evaluation data",
        "truth": "METAR/IEM at 8 frozen stations: " + ", ".join(f"{s} ({v['network']})" for s, v in cfg["stations"].items()),
        "sampleCount": n, "lakeCount": len(WIND_TO_ID), "stationCount": len(cfg["stations"]),
        "metrics": fleet,
        "byClass": [{"lakeClass": f"station network {t}", "sampleCount": len(v), "metrics": metrics(v, "nbmS", "nbmD", "nbmG")[0]} for t, v in sorted(by_type.items())],
        "perLake": per_lake,
        "productionProxy": {"model": "HRRR (what Open-Meteo Best Match serves at 0-46 h)", "sampleCount": n_prod, "metrics": prod,
                            "candidateOnSameRows": cand_on_prod_rows},
        "surfacePhysics": {"model": "frozen CEM (M0) + frozen duration rule", "truth": "NDBC lake buoys, untouched 2020-2023 seasons (6 stations)",
                           "sampleCount": fresh["n"], "hm0MaeM": round(fresh["mae"], 4), "hm0BiasM": round(fresh["bias"], 4),
                           "chopClassExactPct": round(100 * fresh["exact"], 1), "chopClassWithin1Pct": round(100 * fresh["within1"], 1),
                           "severeMissPct": round(100 * fresh["severe"], 2),
                           "note": "Buoys are not Sector banks: physics evidence only. No field (bank-scale) surface validation exists."},
        "scores": {"windCertificationScore": 3.1, "windCertificationRubric": "frozen Stage 1/2 rubric v1 (code-derived scoreboard)",
                   "bowfishingWindIntelligenceScore": bwis["BWIS"], "bwisDefinitionSha256": bwis["definitionSha256"]},
        "failedGates": [
            "dim1: >=15 mph POD >= 0.5 with FAR <= 0.5 (NBM POD 0)",
            "dim2: direction >= 85% within 22.5 deg (75.8%)",
            "dim3: gust conditional |bias| <= 1 m/s and >=20 kt POD >= 0.6 / FAR <= 0.6",
            "dim6: no field exposure validation (cap 6/10)",
            "dim7: no field surface validation (cap 6/10)",
            "dim8: 30 live days >= 99% not yet reached",
            "cap7: land-only wind validation (no over-water reference)",
        ],
        "liveValidation": "SEALED: live forecast-vs-observation checks are not computed or published before 2027-01-01 (H2 holdout).",
        "artifactRefs": ["docs/intelligence/wind/stage3c/WIND_HISTORICAL_EVENT_VALIDATION.md",
                         "docs/intelligence/wind/bowfishing/WIND_BOWFISHING_SCORE_REPORT.md",
                         "docs/intelligence/wind/WIND_SCORE_CHANGE_LOG.jsonl"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("sampleCount", "metrics", "productionProxy", "surfacePhysics")}, indent=1))


if __name__ == "__main__":
    main()
