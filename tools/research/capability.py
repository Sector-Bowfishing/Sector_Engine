#!/usr/bin/env python3
"""Bowfishing capability measurement V1 (candidate contract `bowfishing-capability-v1`, owner directive 2026-10-25).

Why it exists. Several existing score contracts measure administrative completion, typed constants or caps (see docs/research/SCORING_CONTRACT_AUDIT_V1.md):
a measured improvement in a Brain's bowfishing usefulness often cannot move them. This contract is computed ONLY from recorded evidence - the latest
campaign's validation metrics, the gap ledger, the Brain's charter fit-for-purpose targets and the pilot readiness record - and it:
  - reports each dimension as MEASURED with its inputs, or UNMEASURED with the reason (never zero, never typed);
  - reports the CURRENT value (deployed behaviour) and the CANDIDATE value (validated candidate changes) side by side, so a validated improvement is visible
    even where an old rubric is capped or gate-based;
  - never touches an authoritative score, engineering score, certification or customer-readiness status: those stay separate;
  - is versioned: historical rubrics are untouched and shown next to it for comparison. Making it authoritative is an owner decision (new rubric version).

Dimensions (weights sum to 1; the composite is the weighted mean over MEASURED dimensions only, and `measuredWeight` says how much of the contract was measurable):
  validationDepth        .25  best evidence tier reached on independent data for the Brain's gaps (ledger)
  predictionFitness      .30  measured error vs the charter's pre-declared fit-for-purpose target
  uncertaintyHandling    .15  calibration of stated uncertainty / refusal boundary
  coverage               .15  share of the fleet (or species) the capability demonstrably covers
  practicalAvailability  .15  share of the charter's predictions usable at the pilot lake (validated 1.0, experimental 0.4, abstain 0)
"""
from __future__ import annotations

import glob
import json
import os

import ledger as L

HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACT = "bowfishing-capability-v1"
VERSION = "1.0.0"
WEIGHTS = {"validationDepth": 0.25, "predictionFitness": 0.30, "uncertaintyHandling": 0.15, "coverage": 0.15, "practicalAvailability": 0.15}
TIER_VALUE = {"INDEPENDENTLY_VALIDATED": 1.0, "CANDIDATE_CHANGE": 0.6, "SCIENTIFIC_SUPPORT": 0.4, "QUALITY_CHECKED": 0.15, "EVIDENCE_LEAD": 0.05, "ACQUIRED": 0.05}
CLASS_VALUE = {"VALIDATED_FOR_INTERNAL_TEST": 1.0, "EXPERIMENTAL": 0.4, "ABSTAIN": 0.0}
FOLDERS = {"biological-state": "fish-brain", "wind": "wind-brain", "water-clarity": "water-clarity", "lake-brain": "lake-brain", "water-temp": "water-temperature",
           "depth": "depth", "vegetation": "vegetation", "sector-intelligence": "sector-intelligence"}
DIRS = {"biological-state": "fish", "lake-brain": "lake", "water-temp": "water-temperature"}


def _meas(value, **inputs):
    return {"status": "MEASURED", "value": None if value is None else round(max(0.0, min(1.0, value)), 4), "inputs": inputs}


def _un(reason):
    return {"status": "UNMEASURED", "value": None, "reason": reason}


def _fit(observed, target, direction):
    """1.0 when the target is met; otherwise the fraction of the way there (so a 2.27 C error against a 2.0 C target is 0.88, not a pass/fail)."""
    if observed is None or observed <= 0 and direction == "lower":
        return None
    return min(1.0, target / observed) if direction == "lower" else min(1.0, observed / target)


def _latest(home: str, folder: str, campaign: str | None):
    """The newest candidate package's validation.json (metrics) for a folder, or the named campaign's."""
    pats = [os.path.join(home, folder, "candidates", campaign, "validation.json")] if campaign else sorted(glob.glob(os.path.join(home, folder, "candidates", "*", "validation.json")))
    for p in reversed(pats):
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8")).get("metrics") or {}
    return {}


def _g(d, dotted, default=None):
    for k in dotted.split("."):
        d = d.get(k) if isinstance(d, dict) else None
    return default if d is None else d


def _fleet(home: str, brain_cfg: dict) -> int:
    d = os.path.join(home, brain_cfg.get("fleetForcingDir") or "water-temperature/validation/valmodel/forcing")
    return len(glob.glob(os.path.join(d, "*.json"))) or 0


def _charter(engine: str, bid: str) -> dict:
    p = os.path.join(engine, "brains", DIRS.get(bid, bid), "research", "CHARTER.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def compute_brain(engine: str, home: str, bid: str, disc: dict, campaign: str | None, readiness: dict | None) -> dict:
    spec = (disc.get("brains") or {}).get(bid) or {}
    folder = FOLDERS.get(bid) or spec.get("folder")
    M = _latest(home, folder, campaign)
    D = M.get("discovery") or {}
    X = D.get("exp") or {}
    charter = _charter(engine, bid)
    dims_cur, dims_cand = {}, {}
    # validationDepth: best tier any gap reached (ledger), current vs the same (candidate tiers are the ledger tiers)
    led = os.path.join(home, folder, "research", "gap-ledger.json")
    if os.path.exists(led):
        gaps = json.load(open(led, encoding="utf-8")).get("gaps") or {}
        tiers = [g.get("bestTier") for g in gaps.values() if g.get("bestTier")]
        best = max(tiers, key=L.rank, default=None)
        dims_cur["validationDepth"] = _meas(TIER_VALUE.get(best, 0.0) if best else 0.0, bestTier=best, gaps=len(gaps), gapsWithEvidence=len(tiers))
    else:
        dims_cur["validationDepth"] = _un("no gap ledger yet")
    # practicalAvailability from the pilot readiness record
    allcaps = ((readiness or {}).get("brains") or {}).get(bid, {}).get("capabilities") or []
    caps = [c for c in allcaps if c.get("deployed", True)]               # CURRENT counts only what is deployed; candidates (deployed: false) count in the candidate column
    if caps:
        v = sum(CLASS_VALUE.get(c["class"], 0.0) for c in caps) / len(caps)
        dims_cur["practicalAvailability"] = _meas(v, capabilities=len(caps), classes={c: sum(x["class"] == c for x in caps) for c in CLASS_VALUE})
    else:
        dims_cur["practicalAvailability"] = _un("no pilot readiness record for this Brain")
    if len(allcaps) > len(caps):
        v2 = sum(CLASS_VALUE.get(c["class"], 0.0) for c in allcaps) / len(allcaps)
        dims_cand["practicalAvailability"] = {**_meas(v2, capabilities=len(allcaps), classes={c: sum(x["class"] == c for x in allcaps) for c in CLASS_VALUE}), "validated": True,
                                              "note": "includes validated candidates that are not deployed"}
    fleet = _fleet(home, spec)
    ffp = {f["metric"]: f for f in charter.get("fitForPurpose") or []}
    # ---- Brain-specific measured inputs (all read from recorded evidence)
    if bid == "water-temp":
        w1 = os.path.join(home, "water-temperature/validation/campaign-2026-10-22/wt_w1_reproduction.json")
        fleet_rmse = _g(json.load(open(w1)) if os.path.exists(w1) else {}, "metrics.pooled_equalLake_rmse_C")
        ind = D.get("pooledEqualLakeRmseC")
        tgt = (ffp.get("RMSE vs independent surface sensors (C)") or {}).get("target", 2.0)
        vals = [x for x in (_fit(fleet_rmse, tgt, "lower"), _fit(ind, tgt, "lower")) if x is not None]
        if vals:
            dims_cur["predictionFitness"] = _meas(min(vals), fleetRmseC=fleet_rmse, independentRmseC=ind, targetC=tgt, rule="the worse of fleet and independent")
        else:
            dims_cur["predictionFitness"] = _un("no recorded error metrics")
        iv = next((x for k, x in X.items() if k.startswith("wt-interval") and x.get("lakes")), None)
        if iv:
            cov = [v["covBase"] for v in iv["lakes"].values()]
            tol = 0.1
            dims_cur["uncertaintyHandling"] = _meas(sum(abs(c - iv["nominal"]) <= tol for c in cov) / len(cov), independentCoverage=[round(c, 3) for c in cov], nominal=iv["nominal"], tolerance=tol,
                                                    rule="share of independent lakes whose stated 80% band covers 70-90%")
            best_iv = max((x for k, x in X.items() if k.startswith("wt-interval") and x.get("lakes")), key=lambda x: x.get("sensorDeltaIs", -9))
            cc = [v["covCand"] for v in best_iv["lakes"].values()]
            dims_cand["uncertaintyHandling"] = {**_meas(sum(abs(c - best_iv["nominal"]) <= tol for c in cc) / len(cc), independentCoverage=[round(c, 3) for c in cc]),
                                                "validated": False, "note": "best interval hypothesis; reported even when it failed its pre-declared tests, flagged validated=False"}
        else:
            dims_cur["uncertaintyHandling"] = _un("no interval evidence")
        n_ind = D.get("lakesValidated")
        dims_cur["coverage"] = _meas((n_ind or 0) / fleet, lakesWithIndependentSensors=n_ind, fleetLakes=fleet) if fleet else _un("fleet size unknown")
    elif bid == "lake-brain":
        n = D.get("lakesWithFreshLevel")
        dims_cur["predictionFitness"] = _un("no level-prediction error metric exists yet (prospective ledger not scored)")
        dims_cur["uncertaintyHandling"] = _un("no recorded calibration")
        dims_cur["coverage"] = _meas(n / fleet, lakesWithFreshIndependentLevel=n, fleetLakes=fleet) if (n is not None and fleet) else _un("no level-source evidence")
        cw = X.get("cwms-levels") or {}
        if cw.get("newFreshLakes"):
            dims_cand["coverage"] = {**_meas((n + cw["newFreshLakes"]) / fleet, lakes=n + cw["newFreshLakes"]), "validated": True}
    elif bid == "water-clarity":
        dims_cur["predictionFitness"] = _un("Secchi error needs model outputs at the observation dates (not recorded)")
        dims_cur["uncertaintyHandling"] = _un("no recorded calibration")
        a, b = D.get("lakesWithValidObs"), D.get("lakesSearched")
        dims_cur["coverage"] = _meas(a / fleet, lakesWithSecchiObservations=a, fleetLakes=fleet, lakesSearchedThisCampaign=b) if (a is not None and fleet) else _un("no Secchi evidence")
    elif bid == "biological-state":
        rg = X.get("rule-grade") or {}
        dims_cur["predictionFitness"] = _un("no species rule has been compared with a field outcome (FISH-VAL-001)")
        if rg:
            tot = rg["speciesAtPilot"]
            dims_cur["uncertaintyHandling"] = _meas((tot - rg["unsupportedDisplayedBase"]) / tot, speciesShownWithDirectEvidence=tot - rg["unsupportedDisplayedBase"], speciesAtPilot=tot,
                                                    rule="share of species whose rules are shown with direct, fully read evidence today (all are shown)")
            dims_cand["uncertaintyHandling"] = {**_meas((tot - rg["unsupportedDisplayedCand"]) / tot, speciesShownWithDirectEvidence=tot - rg["unsupportedDisplayedCand"]), "validated": False,
                                                "note": "refusal boundary candidate; derived from rule metadata, not a field validation"}
            dims_cur["coverage"] = _meas(rg["experimentalInternal"] / tot, speciesWithEvidenceGradedRules=rg["experimentalInternal"], speciesAtPilot=tot)
        else:
            dims_cur["uncertaintyHandling"] = _un("no rule-grade evidence")
    elif bid == "sector-intelligence":
        dims_cur["predictionFitness"] = _un("no cross-Brain relationship has been validated")
        dims_cur["uncertaintyHandling"] = _un("not measured")
        dims_cur["coverage"] = _un("not measured")
    elif bid == "wind":
        cl = X.get("wind-calm-night-climatology") or {}
        dims_cur["predictionFitness"] = _un("the deployed Wind Brain has no recomputable error metric (strong-wind skill is recorded as text only: POD 0 on 49 events)")
        if cl.get("pooledMaeCand") is not None:
            tgt = (ffp.get("calm-night climatology MAE (probability points)") or {}).get("target", 0.05)
            dims_cand["predictionFitness"] = {**_meas(_fit(cl["pooledMaeCand"], tgt, "lower"), maeCand=cl["pooledMaeCand"], maeBase=cl["pooledMaeBase"], target=tgt, stations=cl["stations"],
                                                      stationsImprovedShare=cl.get("stationsImprovedShare")), "validated": True,
                                              "note": "calm-night climatology candidate on held-out years (airport proxy, not shoreline wind); the strong-wind-night target remains unmeasured"}
        dims_cur["uncertaintyHandling"] = _un("not measured")
        dims_cur["coverage"] = _un("no observed-data coverage metric yet")
    else:
        dims_cur["predictionFitness"] = _un("no recomputable error metric: Brain abstains / unscored")
        dims_cur["uncertaintyHandling"] = _un("not measured")
        dims_cur["coverage"] = _un("no observed-data coverage metric yet")
    for k in WEIGHTS:
        dims_cur.setdefault(k, _un("not measured"))

    def composite(dims):
        m = {k: v for k, v in dims.items() if v["status"] == "MEASURED" and v["value"] is not None}
        w = sum(WEIGHTS[k] for k in m)
        return {"value": round(sum(WEIGHTS[k] * v["value"] for k, v in m.items()) / w, 4) if w else None, "measuredWeight": round(w, 4), "measuredDimensions": sorted(m)}
    cand = {**dims_cur, **{k: v for k, v in dims_cand.items()}}
    return {"brainId": bid, "current": {"dimensions": dims_cur, **composite(dims_cur)}, "candidate": {"dimensions": cand, **composite(cand)},
            "candidateChangesFrom": sorted(dims_cand), "charterFitForPurpose": [f["metric"] for f in charter.get("fitForPurpose") or []]}


def compute(engine: str, home: str, campaign: str | None = None, readiness_path: str | None = None) -> dict:
    disc = json.load(open(os.path.join(HERE, "discovery.json"), encoding="utf-8"))
    rp = readiness_path or os.path.join(home, "shared", "pilot", "guntersville-v1", "PILOT_V1_READINESS.json")
    readiness = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else None
    ids = list(FOLDERS) + [b for b, sp in (disc.get("brains") or {}).items() if b not in FOLDERS and sp.get("folder")]      # a newly onboarded Brain is measured too
    brains = [compute_brain(engine, home, b, disc, campaign, readiness) for b in ids]
    return {"schema": "sector-capability-measurement-v1", "contract": CONTRACT, "version": VERSION, "campaign": campaign, "weights": WEIGHTS,
            "separation": "scientific CANDIDATE measurement. Not an engineering score, not a certification, not customer readiness, not an authoritative score; historical rubrics are unchanged.",
            "brains": brains}


def render(rep: dict, legacy: dict | None = None) -> str:
    out = [f"# Bowfishing capability measurement — {rep['contract']} {rep['version']}", "", rep["separation"], "",
           "Computed only from recorded evidence. UNMEASURED means the evidence to compute it does not exist yet (it is not zero). The composite averages the measured dimensions only; `measured weight` says how much of the contract could be measured.", "",
           "| Brain | Current | Candidate (validated + unvalidated changes) | Measured weight | Legacy score (different measure) |", "|---|---|---|---|---|"]
    for b in rep["brains"]:
        c, k = b["current"], b["candidate"]
        out.append(f"| {b['brainId']} | {c['value'] if c['value'] is not None else '—'} | {k['value'] if k['value'] is not None else '—'}{' (changed: ' + ', '.join(b['candidateChangesFrom']) + ')' if b['candidateChangesFrom'] else ''} | {c['measuredWeight']} | {(legacy or {}).get(b['brainId'], '—')} |")
    out += ["", "## Dimensions", ""]
    for b in rep["brains"]:
        out.append(f"### {b['brainId']}")
        for k, v in b["current"]["dimensions"].items():
            out.append(f"- **{k}**: " + (f"{v['value']} — {json.dumps(v['inputs'])}" if v["status"] == "MEASURED" else f"UNMEASURED — {v['reason']}"))
        for k in b["candidateChangesFrom"]:
            v = b["candidate"]["dimensions"][k]
            out.append(f"  - candidate **{k}**: {v['value']} (validated: {v.get('validated')}) — {v.get('note', '')}")
        out.append("")
    return "\n".join(out)


def main(argv=None) -> int:
    import argparse
    import sys
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True)
    ap.add_argument("--campaign")
    ap.add_argument("--engine", default=os.path.abspath(os.path.join(HERE, "..", "..")))
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    rep = compute(a.engine, a.home, a.campaign)
    legacy = {}
    try:
        fz = json.load(open(os.path.join(a.engine, "docs", "brains", "scoring", "frozen-scores.json"), encoding="utf-8"))
        legacy = {k: f"{v['value']} ({v.get('basis')})" for k, v in fz.items() if isinstance(v, dict) and "value" in v}
    except (OSError, ValueError):
        pass
    out = a.out or os.path.join(a.home, "shared", "campaigns", a.campaign or "latest")
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, "CAPABILITY.json"), "w", encoding="utf-8"), indent=1)
    open(os.path.join(out, "CAPABILITY.md"), "w", encoding="utf-8").write(render(rep, legacy) + "\n")
    print(render(rep, legacy))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
