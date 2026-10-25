#!/usr/bin/env python3
"""Internal-test multi-Brain bowfishing information (owner directive 2026-10-25). INTERNAL ONLY, read-only, reads no secrets and writes nothing to Firebase.

It assembles what the Brains already publish for one lake into a per-factor table - value, unit, age, freshness limit, status, uncertainty and the capability
class from the pilot readiness record - and adds two things that were validated in research: a seasonal calm-night prior for the nearest station and
the field-tested Fish rules (shown only when SUPPORTED by the field comparison; CONTRADICTED rules are withheld and listed).

Rules it never breaks:
  - No combined score and no fishing recommendation: Intelligence's synthesis is not validated, so the overall answer is ABSTAIN with the reasons.
  - A stale or missing input is shown as such and never filled in; ABSTAIN capabilities are never turned into a number.
  - Each factor keeps its own Brain as the owner of the science (no duplicated scientific ownership).
Also provides the charter contract check used by CI (`contract_gaps`): every dependency declared in a Brain's charter must be symmetric (the producer lists the
consumer) and declared in brain.json `consumes`, or be on the recorded allowlist `integration_contract_gaps.json` (a new undeclared edge fails the test).
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.abspath(os.path.join(HERE, "..", ".."))
DIRS = {"biological-state": "fish", "lake-brain": "lake", "water-temp": "water-temperature"}
SPECIES = {"CARP": "common carp", "SMBF": "smallmouth buffalo", "BMBF": "bigmouth buffalo", "BKBF": "black buffalo", "FWDM": "freshwater drum", "LNGR": "longnose gar",
           "SNGR": "shortnose gar", "STGR": "spotted gar", "BWFN": "bowfin", "GSCP": "grass carp", "SVCP": "silver carp", "BHCP": "bighead carp"}
# freshness limits (hours) from each Brain's own contract (staleAfterHours / observation limits); the satellite limit is days
LIMITS = {"lake": 3.0, "waterTemp": 6.0, "windObservation": 1.5, "windForecast": 6.0, "clarityModel": 26.0, "claritySatellite": 14 * 24.0}


def _t(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def _g(d, dotted):
    for k in dotted.split("."):
        d = d.get(k) if isinstance(d, dict) else None
    return d


def _cls(readiness, brain, cap, default="EXPERIMENTAL"):
    for c in ((readiness or {}).get("brains") or {}).get(brain, {}).get("capabilities") or []:
        if c["id"] == cap:
            return c["class"], c.get("reason")
    return default, None


def _factor(brain, factor, value, unit, when, limit_h, now, klass, reason=None, uncertainty=None, note=None):
    age = None if when is None else round((now - when).total_seconds() / 3600, 2)
    if klass == "ABSTAIN":
        status = "ABSTAIN"
    elif value is None or when is None:
        status = "MISSING"
    else:
        status = "FRESH" if age <= limit_h else "STALE"
    out = {"brain": brain, "factor": factor, "capabilityClass": klass, "status": status, "ageHours": age, "limitHours": limit_h}
    if status in ("FRESH", "STALE"):
        out.update({"value": value, "unit": unit})            # a stale value is still shown, clearly marked: the app decides to grey it, never to refresh it
    if uncertainty:
        out["uncertainty"] = uncertainty
    if reason or note:
        out["reason"] = reason or note
    return out


def species_notes(temp_c, field_tests, spec_tests, p):
    """Field-compared Fish rules that apply now. Only SUPPORTED rules are shown; CONTRADICTED ones are withheld (listed); the rest are not claimed."""
    shown, withheld = [], []
    for t in spec_tests:
        v = (field_tests or {}).get(t["ruleId"])
        if not v or not v.get("decisive"):
            continue
        sp = SPECIES.get(t["species"], t["species"])
        if v["verdict"] == "CONTRADICTED":
            withheld.append({"ruleId": t["ruleId"], "species": sp, "reason": f"field comparison contradicts the rule ({t['claim']}): rate ratio {v['ratio']} (95% CI {v['ciLo']}-{v['ciHi']})"})
            continue
        applies = True
        if t["type"] == "thermal_cold":
            applies = temp_c is not None and temp_c < p["coldC"] and t["expect"] == "cold_lt_warm"
        elif t["type"] == "thermal_warm":
            applies = temp_c is not None and 26 <= temp_c < 30
        elif t["type"] in ("diel", "diel_shallow") and t["expect"] != "night_gt_day":
            applies = False                                      # only positive night findings are shown as night notes
        if applies:
            shown.append({"ruleId": t["ruleId"], "species": sp, "note": t["claim"], "evidence": f"field comparison (river surrogate): rate ratio {v['ratio']} (95% CI {v['ciLo']}-{v['ciHi']})",
                          "label": "EXPERIMENTAL"})
    return {"shown": shown, "withheld": withheld}


def assess(lake_id, nodes, now, readiness=None, wind_climatology=None, month=None, station=None, field_tests=None, spec_tests=None, fp=None, temp_error_c=2.3):
    """nodes: {'lake','waterTemp','wind','waterClarity','depth','vegetation','intelligence'} -> node dicts (or None when absent)."""
    nodes = nodes or {}
    F = []
    L = nodes.get("lake") or {}
    F.append(_factor("lake-brain", "observedPoolElevation", L.get("currentElevationFt"), "ft", _t(L.get("observationTime") or _g(L, "provenance.generatedAt")), LIMITS["lake"], now, *_cls(readiness, "lake-brain", "observedPoolElevation")))
    W = nodes.get("waterTemp") or {}
    tf = W.get("currentTempF")
    tc = None if tf is None else round((tf - 32) / 1.8, 2)
    F.append(_factor("water-temp", "modeledSurfaceTemp", tc, "degC", _t(_g(W, "provenance.generatedAt")), LIMITS["waterTemp"], now, *_cls(readiness, "water-temp", "modeledSurfaceTempWithFleetErrorBound"),
                     uncertainty={"type": "fleetErrorBoundC", "value": temp_error_c, "basis": "fleet RMSE on held-out grab samples; not lake-specific; spring runs cold, autumn warm"}))
    N = nodes.get("wind") or {}
    F.append(_factor("wind", "observation", _g(N, "observation.sustainedMph"), "mph", _t(_g(N, "observation.observedAt")), LIMITS["windObservation"], now, *_cls(readiness, "wind", "observation")))
    F.append(_factor("wind", "forecast", _g(N, "gustMph"), "mph gust", _t(_g(N, "forecast.initTime")), LIMITS["windForecast"], now, *_cls(readiness, "wind", "speedGustForecast")))
    F.append(_factor("wind", "strongWindNight", None, None, None, 0, now, *_cls(readiness, "wind", "strongWindNightForecast", "ABSTAIN")))
    C = nodes.get("waterClarity") or {}
    F.append(_factor("water-clarity", "modeledClarity", C.get("clarityFt"), "ft", _t(C.get("generatedAt")), LIMITS["clarityModel"], now, *_cls(readiness, "water-clarity", "modeledClarity"),
                     note="uncalibrated rain-decay model"))
    F.append(_factor("water-clarity", "satelliteEstimate", None, None, _t(_g(C, "satellite.observedAt")), LIMITS["claritySatellite"], now, *_cls(readiness, "water-clarity", "satelliteEstimate", "ABSTAIN")))
    for b, cap in (("depth", "allDepthOutputs"), ("vegetation", "allVegetationOutputs")):
        F.append(_factor(b, cap, None, None, None, 0, now, "ABSTAIN", "runtime abstains until an approved release; no estimate is produced"))
    prior = None
    if wind_climatology and station and month:
        pr = (wind_climatology.get(station) or {}).get(str(month))
        if pr is not None:
            prior = {"station": station, "month": month, "probabilityOfCalmNight": pr, "basis": "airport hourly wind, held-out-year validated climatology; an over-land proxy for the shoreline",
                     "definition": "every hourly sustained wind <= 8.7 kt and gust <= 13 kt between 21:00 and 04:00 local"}
    notes = species_notes(tc if (tc is not None and F[1]["status"] == "FRESH") else None, field_tests, spec_tests or [], fp or {"coldC": 15.0}) if field_tests else {"shown": [], "withheld": []}
    fresh = [f for f in F if f["status"] == "FRESH"]
    stale = [f for f in F if f["status"] == "STALE"]
    miss = [f for f in F if f["status"] == "MISSING"]
    ab = [f for f in F if f["status"] == "ABSTAIN"]
    return {"schema": "sector-internal-conditions-v1", "lake": lake_id, "asOf": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "mode": "INTERNAL_EXPERIMENTAL_NOT_FOR_CUSTOMERS",
            "factors": F, "seasonalPrior": prior, "speciesNotes": notes,
            "overall": {"fresh": len(fresh), "stale": len(stale), "missing": len(miss), "abstain": len(ab), "recommendation": "ABSTAIN",
                        "reason": "cross-Brain synthesis is not validated; each factor is shown with its own age, label and uncertainty. A stale or missing factor is never filled in.",
                        "limitingFactors": [f"{f['brain']}:{f['factor']} {f['status']}" for f in stale + miss]}}


def read_live(lake_id, token):
    """Read-only GET of the lake's state nodes (no writes, no listing of other paths)."""
    out = {}
    for k in ("lake", "waterTemp", "wind", "waterClarity", "depth", "vegetation", "intelligence"):
        req = urllib.request.Request(f"https://sector-brain.firebaseio.com/lakes/{lake_id}/states/{k}.json", headers={"Authorization": f"Bearer {token}"})
        try:
            out[k] = json.loads(urllib.request.urlopen(req, timeout=30).read() or b"null")
        except OSError:
            out[k] = None
    return out


# ------------------------------------------------------------------------------------------------------------------------------- charter contract
def charters(engine=ENGINE):
    out = {}
    for p in sorted(glob.glob(os.path.join(engine, "brains", "*", "research", "CHARTER.json"))):
        c = json.load(open(p, encoding="utf-8"))
        out[c["brainId"]] = c
    return out


def declared_consumes(engine, bid):
    p = os.path.join(engine, "brains", DIRS.get(bid, bid), "brain.json")
    try:
        return {c.get("brain") or c.get("brainId") or c.get("producer") if isinstance(c, dict) else c for c in json.load(open(p, encoding="utf-8")).get("consumes") or []}
    except (OSError, ValueError):
        return set()


def contract_gaps(engine=ENGINE):
    """Edges a charter needs that are (a) not mirrored by the producer's charter or (b) not declared in brain.json `consumes`."""
    ch = charters(engine)
    asym, undeclared = [], []
    for bid, c in ch.items():
        for n in c.get("needsFrom") or []:
            prod = ch.get(n["brain"])
            if prod is None:
                asym.append(f"{bid} needs unknown Brain {n['brain']}")
                continue
            if not any(x["brain"] == bid for x in prod.get("providesTo") or []):
                asym.append(f"{bid} needs {n['brain']}:{n['output']} but {n['brain']}'s charter does not list {bid} as a consumer")
            if n["brain"] not in {str(x) for x in declared_consumes(engine, bid)} and not _declared_any(engine, bid, n["brain"]):
                undeclared.append(f"{bid} <- {n['brain']}")
    for bid, c in ch.items():                                    # and the reverse: everything a Brain says it provides must be needed by the consumer
        for pv in c.get("providesTo") or []:
            cons = ch.get(pv["brain"])
            if cons is None:
                asym.append(f"{bid} provides to unknown Brain {pv['brain']}")
            elif not any(x["brain"] == bid for x in cons.get("needsFrom") or []):
                asym.append(f"{bid} provides {pv['output']} to {pv['brain']} but {pv['brain']}'s charter does not need it")
    return {"asymmetric": sorted(asym), "undeclaredInBrainJson": sorted(set(undeclared))}


def _declared_any(engine, bid, producer):
    p = os.path.join(engine, "brains", DIRS.get(bid, bid), "brain.json")
    try:
        txt = json.dumps(json.load(open(p, encoding="utf-8")).get("consumes") or [])
    except (OSError, ValueError):
        return False
    return producer in txt


def main(argv=None) -> int:
    import argparse
    import subprocess
    import sys
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", default="Guntersville_AL")
    ap.add_argument("--snapshot")
    ap.add_argument("--live", action="store_true", help="read the lake's state nodes read-only (needs gcloud auth)")
    ap.add_argument("--home", required=True)
    ap.add_argument("--campaign")
    ap.add_argument("--station", default="HSV")
    ap.add_argument("--now")
    a = ap.parse_args(argv)
    now = _t(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
    if a.live:
        tok = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True).stdout.strip()
        nodes = read_live(a.lake, tok)
    else:
        nodes = json.load(open(a.snapshot, encoding="utf-8"))
    rp = os.path.join(a.home, "shared", "pilot", "guntersville-v1", "PILOT_V1_READINESS.json")
    readiness = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else None
    clim = ft = None
    spec_tests, fp = [], {}
    disc = json.load(open(os.path.join(HERE, "discovery.json"), encoding="utf-8"))
    for av in disc["brains"]["biological-state"]["avenues"]:
        if av["id"] == "fish-ltrm-field-test":
            spec_tests, fp = av["params"]["tests"], av["params"]
    cdir = a.campaign
    if cdir:
        try:
            ft = json.load(open(os.path.join(a.home, "fish-brain", "candidates", cdir, "validation.json")))["metrics"]["discovery"]["exp"]["fish-ltrm-field-test"]["tests"]
            clim = json.load(open(os.path.join(a.home, "wind-brain", "candidates", cdir, "validation.json")))["metrics"]["discovery"]["exp"]["wind-calm-night-climatology"]["monthlyCalmNightProbability"]
        except (OSError, KeyError, ValueError):
            pass
    out = assess(a.lake, nodes, now, readiness, clim, now.month, a.station, ft, spec_tests, fp)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
