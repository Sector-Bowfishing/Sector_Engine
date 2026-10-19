#!/usr/bin/env python3
"""Wind Bowfishing-First V2: end-to-end NONPRODUCTION demonstration with the real runtime and the real platform scorer.

  python verification/integration/wind_bowfishing_v2_e2e.py [--fetch FULL_FETCH.json.gz] [--out REPORT.json]

Network sockets are DISABLED for the whole run (any connect raises), so nothing can reach the Brain RTDB, the archive bucket,
NOAA or a customer surface. Every wind value is SYNTHETIC (a physically reasonable evening blow: SW 8 mph building to 16 mph and
veering to NW, then easing), written to a temporary local Wind archive in the exact layout the hourly job writes. The lake
geometry is REAL: the committed Guntersville subset by default, or a full frozen fetch table with --fetch.

Steps: archive -> brain.state.build_state (Layer 1) -> decision.build (Layer 2: ranking, alternatives, surface, timeline,
explanations, uncertainty) -> schema + invariants -> capability scenarios (Layer 3) -> platform measurements (BI v2 / Scientific
Confidence / Production Readiness) -> certification preserved -> refresh gate on a temp copy -> score_brains attach (offline)
-> repository and production untouched.
"""
from __future__ import annotations

import argparse
import base64
import copy
import gzip
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
WIND = os.path.join(ROOT, "brains", "wind")
for p in (os.path.join(WIND, "runtime"), os.path.join(ROOT, "jobs", "brain_platform"), os.path.join(ROOT, "jobs", "brain-scores"),
          os.path.join(ROOT, "tools", "architecture")):
    sys.path.insert(0, p)

NOW = datetime(2026, 10, 19, 23, 20, tzinfo=timezone.utc)      # ~6:20 pm CDT, start of a night trip
LAKE, WL = "Guntersville|AL", "guntersville"
MPH = 0.44704
# SYNTHETIC forecast for the trip, hourly from 23Z: (mph, from-deg)
TRIP = [(8, 225), (10, 225), (13, 230), (16, 240), (16, 270), (14, 300), (11, 315), (8, 315), (6, 315)]


class NetworkBlocked(RuntimeError):
    pass


def _block_network():
    def deny(*a, **k):
        raise NetworkBlocked("network disabled in the V2 nonproduction demonstration")
    socket.socket.connect = deny
    socket.create_connection = deny


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _tracked_state():
    return subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True, text=True).stdout


def _grid(lat, lon, n=5, step=0.02):
    cells, la, lo = [], [], []
    for r in range(n):
        for c in range(n):
            cells.append(r * n + c); la.append(lat - (n // 2 - r) * step); lo.append(lon + (c - n // 2) * step)
    return {"cells": cells, "lat": la, "lon": lo, "nx": n}


def synthetic_archive(store, iso):
    """A local Wind archive (same keys/schemas as the hourly job) holding SYNTHETIC values only."""
    lat, lon = 34.42, -86.26
    for g in ("nbm", "rtma"):
        store.put_json(f"grids/{g}/{WL}.json", _grid(lat, lon))
    init = NOW.replace(minute=0) - timedelta(hours=1)
    steps = []
    for L in range(1, 13):
        vt = init + timedelta(hours=L)
        k = max(0, min(len(TRIP) - 1, int((vt - NOW.replace(minute=0)).total_seconds() // 3600)))
        mph, d = TRIP[k]
        steps.append({"leadHours": L, "validTime": iso(vt), "speedMS": [mph * MPH] * 25, "dirFromDeg": [float(d)] * 25, "gustMS": [(mph + 6) * MPH] * 25})
    store.put_json(f"nbm/{WL}/{init:%Y%m%d%H}.json.gz", {"schema": "sector-wind-cycle-v1", "kind": "forecast", "model": "NBM", "modelVersion": "NBM v5.0 (SYNTHETIC demo values)",
                                                       "initTime": iso(init), "retrievedAt": iso(init + timedelta(minutes=62)), "status": "complete",
                                                       "grid": f"grids/nbm/{WL}.json", "steps": steps})
    for k in range(0, 14 * 4):                      # 13 h of steady SW 8 mph analyses before the trip
        ts = NOW.replace(minute=15) - timedelta(minutes=15 * k)
        store.put_json(f"rtma/{WL}/{ts:%Y%m%d}/{ts:%H%M}.json.gz", {"kind": "analysis", "analysisTime": iso(ts), "retrievedAt": iso(ts + timedelta(minutes=20)),
                                                                     "grid": f"grids/rtma/{WL}.json", "speedMS": [8 * MPH] * 25, "dirFromDeg": [225.0] * 25, "gustMS": [12 * MPH] * 25})
    return {"id": LAKE, "name": "Guntersville", "state": "AL", "lat": lat, "lon": lon}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", default=os.path.join(WIND, "tests", "fixtures", "guntersville_decision_subset.json.gz"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--samples", default=None, help="directory for sample decision JSON files")
    a = ap.parse_args(argv)

    frozen_path = os.path.join(ROOT, "docs", "brains", "scoring", "frozen-scores.json")
    before = {"frozen": _sha(frozen_path), "git": _tracked_state()}
    _block_network()

    from sector_wind.store import LocalStore
    from sector_wind.ingest import load_config
    from sector_wind.brain import contract as C
    from sector_wind.brain.state import build_state
    from sector_wind.decision import build as B, ranking as R, scenarios as SCN, schema as SC
    from sector_brain_platform import wind_measurements as W, wind_score_refresh as RF, frozen_score
    from jsonschema_lite import iter_errors
    import score_brains

    out, ok = {"demo": "wind-bowfishing-first-v2-e2e", "inputs": "SYNTHETIC wind; real Guntersville geometry", "steps": []}, True

    def step(name, cond, detail):
        nonlocal ok
        ok &= bool(cond)
        out["steps"].append({"step": name, "pass": bool(cond), "detail": detail})
        print(f"{'PASS' if cond else 'FAIL'}  {name}: {detail}")

    raw = open(a.fetch, "rb").read()
    fetch = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    L = R.geometry(fetch, LAKE)
    step("1 load real geometry", len(L["banks"]) > 0 and hashlib.sha256(base64.b64decode(fetch["tableBase64"])).hexdigest() == fetch["tableSha256"],
         f"{len(L['banks'])} banks, table sha {fetch['tableSha256'][:12]}, {'subset' if fetch.get('selection') else 'full table'}")

    with tempfile.TemporaryDirectory() as tmp:
        st = LocalStore(tmp)
        lake_dir = synthetic_archive(st, C.iso)
        state, rows, meta = build_state(st, load_config(), WL, LAKE, lake_dir, NOW, fetch_obj=fetch)
    step("2 synthetic wind -> real Layer 1 state", state["kind"] == "analysis" and state["surfaceState"] is not None,
         f"kind {state['kind']}, {state['sustainedMph']} mph {state['directionCardinal']}, duration {state['surfaceState']['durationH']} h, trend {state['trend']}")

    wind = B.wind_from_state(state)
    trip = wind["hourly"][:len(TRIP)]
    prior = [{"at": C.iso(NOW - timedelta(hours=k)), "speedMS": 8 * MPH, "dirFromDeg": 225.0, "kind": "analysis"} for k in range(12, 0, -1)]
    pair = SCN.pair(L)
    dec = B.build(LAKE, wind, L, NOW, bank_ids=pair, trip_hours=trip, prior_hours=prior, processing_version="e2e-demo")
    sh = dec["shorelines"]
    step("3-4 exposure evaluated, banks ranked", dec["status"] == "READY" and sh["sheltered"] and sh["requested"],
         f"{dec['lakeSummary']['resolvableBanks']} banks: {dec['lakeSummary']['shelteredPct']}% sheltered/low, {dec['lakeSummary']['exposedPct']}% highly exposed, "
         f"{dec['lakeSummary']['unknownBanks']} unknown")

    strong = B.build(LAKE, B.synthetic_wind(16, 240, 3.0, 22), L, NOW, bank_ids=pair)
    ex = [b for b in strong["shorelines"]["exposed"] if b.get("nearestSheltered")]
    step("5 protected alternatives", bool(ex), f"at 16 mph WSW: {ex[0]['bankId']} -> nearest sheltered {ex[0]['nearestSheltered'][0]['bankId']} "
                                              f"{ex[0]['nearestSheltered'][0]['distanceM']} m" if ex else "none")
    a_bank = next(b for b in dec["shorelines"]["requested"] if b["bankId"] == pair[0])
    step("6 surface estimated", a_bank["predictedSurface"] is not None,
         f"{pair[0]}: {a_bank['windExposure']['label']}, {a_bank['predictedSurface']['label']} {a_bank['predictedSurface']['waveHeightIn']} in "
         f"(range {a_bank['predictedSurface']['waveHeightRangeIn']}), driver {a_bank['predictedSurface']['driver']}")
    step("7 explanations", all(b["explanation"] for b in sh["sheltered"] + sh["requested"]) and dec["explanation"], dec["explanation"][:150])
    step("8 uncertainty preserved", dec["confidence"]["level"] in ("LOW", "MODERATE") and dec["limitations"][0]["severity"] == "WARNING"
         and dec["validation"]["validated"] is False,
         f"confidence {dec['confidence']['level']} ({'; '.join(dec['confidence']['reasons'])}); {len(dec['limitations'])} limitations, first {dec['limitations'][0]['id']}")
    tb = {x["bankId"]: x for x in dec["trip"]["banks"]}
    step("   trip timeline", dec["trip"]["events"] and any(e["type"] == "DIRECTION_SHIFT" for e in dec["trip"]["events"]),
         "; ".join(e["at"][11:16] + "Z " + e["text"] for e in dec["trip"]["events"][:4]) + f" | {tb[pair[0]]['summary']}")
    errs = list(iter_errors(dec, json.load(open(os.path.join(WIND, "contracts", "wind-bowfishing-decision-v1.json")))))
    step("9 canonical decision output", errs == [] and SC.check(dec) == [] and dec["decisionSchema"] == SC.DECISION_SCHEMA,
         f"{SC.DECISION_SCHEMA} {SC.KNOWLEDGE_VERSION}, {len(json.dumps(dec)) // 1024} KB, schema errors {len(errs)}")
    stale = copy.deepcopy(state); stale["stale"] = True; stale["staleReasons"] = ["forecastCycleStale:4.2h>3h"]
    sd = B.build(LAKE, B.wind_from_state(stale), L, NOW)
    step("   stale input refused", sd["status"] == "INPUT_STALE" and sd["shorelines"] is None, sd["explanation"][:90])

    scen = SCN.run(L)
    step("10 capability evaluation (scenarios)", scen["passed"] == scen["total"], f"{scen['passed']}/{scen['total']} on this geometry ({scen['evidenceClass']})")

    rubric, ev, brain = W.load_all()
    cert = json.load(open(frozen_path))["wind"]
    m = W.measurements(copy.deepcopy(cert), ev, rubric, brain, NOW)
    bi, sc, pr = m["bowfishingIntelligence"], m["scientificConfidence"], m["productionReadiness"]
    step("11 scoring/reporting evaluation", bi["basis"] == "COMPUTED" and m["consistency"] == [],
         f"BI {bi['value']} ({bi['scoreVersion']}, {bi['rubricStatus']}; measured {bi['split']['measuredSkill']['points']}/{bi['split']['measuredSkill']['max']}, "
         f"capability {bi['split']['modelCapability']['points']}/{bi['split']['modelCapability']['max']})")
    step("12 intelligence / confidence / readiness separated", sc["value"] is None and pr["value"] is None and len({bi["scoreVersion"], sc["version"], pr["version"], cert["scoreVersion"]}) == 4,
         f"Scientific Confidence {sc['overall']} (statuses), Production Readiness {pr['overall']} (gates)")
    step("13 certification preserved", m["certification"]["value"] == 3.3 and m["bowfishingIntelligenceV1"]["value"] == 5.4 and _sha(frozen_path) == before["frozen"],
         "certification 3.3 wind-certification-rubric-v1, BWIS v1 5.4, frozen-scores.json byte-identical")

    with tempfile.TemporaryDirectory() as tmp:
        fz, hist = os.path.join(tmp, "frozen.json"), os.path.join(tmp, "hist.jsonl")
        open(fz, "w").write(open(frozen_path).read())
        cand = copy.deepcopy(cert)
        d8 = cand["scoreBreakdown"]["Freshness/reliability"]
        d8.update(value=round(10 * 11 / 30, 2), points=round(8 * 11 / 30, 2), evidence=d8["evidence"].replace("5/30", "11/30"))
        cand["rawPoints"] = round(sum(v["points"] for v in cand["scoreBreakdown"].values()), 2); cand["uncapped"] = round(cand["rawPoints"] / 10, 2)
        cand["value"] = round(min([cand["uncapped"]] + [b["cap"] for b in cand["scoreBlockers"] if "cap" in b]), 1)
        cand["evidence"] = {**cand["evidence"], "metadataThrough": C.iso(NOW - timedelta(hours=1)), "validArchiveDays": 11}
        acc = RF.refresh(fz, hist, cand, NOW, write=True)
        hyp = copy.deepcopy(cand); hyp["scoreBreakdown"]["Exposure (field)"].update(value=10.0, points=20.0)     # arithmetically consistent jump
        hyp["rawPoints"] = round(sum(v["points"] for v in hyp["scoreBreakdown"].values()), 2); hyp["uncapped"] = round(hyp["rawPoints"] / 10, 2)
        hyp["value"] = round(min([hyp["uncapped"]] + [b["cap"] for b in hyp["scoreBlockers"] if "cap" in b]), 1)
        hyp["evidence"]["metadataThrough"] = C.iso(NOW - timedelta(minutes=30))
        held = RF.refresh(fz, hist, hyp, NOW, write=True)
        step("   score refresh (temp copy)", acc["decision"] == "ACCEPT" and held["decision"] == "HOLD" and json.load(open(fz))["wind"]["value"] == cand["value"],
             f"ILLUSTRATIVE 11-day candidate -> {acc['decision']} {acc['old']['value']} -> {acc['new']['value']}; field-dim jump -> {held['decision']} ({held['reasons'][0][:90]})")

    fr = score_brains.rtdb_safe(json.load(open(frozen_path)))
    scores = {b: {"value": 1.0, "scale": 10, "basis": "COMPUTED", "scoreVersion": "v1", "scoreBreakdown": {}, "scoreBlockers": []} for b in score_brains.UPSTREAM}
    scores["wind"] = frozen_score(fr["wind"])
    old = copy.deepcopy(scores)
    new = score_brains.attach_wind_measurements(scores, {"health": {}}, NOW)
    upd, _ = score_brains.plan_writes(new, {b: {} for b in score_brains.UPSTREAM}, NOW, old_scores=old)
    step("14 reporting contract consistent", "measurements" in new["wind"] and new["wind"]["value"] == 3.3 and not [k for k in upd if k.startswith("activity/")],
         "attach is additive: certification untouched, no score.changed event (plan only; nothing written)")

    try:
        socket.create_connection(("sector-brain.firebaseio.com", 443), timeout=1)
        blocked = False
    except NetworkBlocked:
        blocked = True
    step("15 no production state changes", blocked and _sha(frozen_path) == before["frozen"] and _tracked_state() == before["git"],
         "network blocked for the whole run; repository tracked files unchanged; no RTDB/bucket client created")
    consumer = {"lake": dec["lakeId"], "status": dec["status"], "headline": dec["explanation"], "confidence": dec["confidence"]["level"],
                "topSheltered": [(b["bankId"], b["windExposure"]["label"], b["predictedSurface"]["label"], b["anchor"]) for b in sh["sheltered"][:3]],
                "warnings": [x["id"] for x in dec["limitations"] if x["severity"] == "WARNING"]}
    step("16 suitable for downstream apps", all(consumer.values()) and all(b[3] for b in consumer["topSheltered"]),
         f"bounded JSON; every bank has id, anchor lat/lon, labels, explanation; consumer view: {json.dumps(consumer)[:160]}")

    out["ok"] = ok
    out["bowfishingIntelligence"] = {k: bi[k] for k in ("value", "scoreVersion", "rubricStatus", "split")}
    out["scientificConfidence"] = {"overall": sc["overall"], "items": {i["id"]: i["status"] for i in sc["items"]}}
    out["productionReadiness"] = {"overall": pr["overall"], "gates": {g["gate"]: g["status"] for g in pr["gates"]}}
    if a.samples:
        os.makedirs(a.samples, exist_ok=True)
        json.dump(dec, open(os.path.join(a.samples, "decision_guntersville_evening_blow.json"), "w"), indent=1)
        json.dump(strong, open(os.path.join(a.samples, "decision_guntersville_16mph_wsw.json"), "w"), indent=1)
        json.dump(sd, open(os.path.join(a.samples, "decision_stale_input.json"), "w"), indent=1)
        json.dump(m, open(os.path.join(a.samples, "wind_measurements.json"), "w"), indent=1)
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1)
    print(f"\n{'ALL STEPS PASSED' if ok else 'FAILURES PRESENT'} ({sum(s['pass'] for s in out['steps'])}/{len(out['steps'])})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
