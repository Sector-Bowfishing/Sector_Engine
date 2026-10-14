#!/usr/bin/env python3
"""Lake Brain staged fleet rollout: batch selection, pre-seed cost, and the score PROJECTION. No network, no writes unless --out is given.

    python3 rollout_plan.py [--bindings TABLE] [--catalog CWMS_CATALOG.jsonl] [--throughput measured_throughput.json] [--out FILE]

PROJECTION ONLY. Nothing here is a measurement of a score; the numbers are what the REAL rubric code
(jobs/brain_platform/sector_brain_platform/scoring.py `score_lake`, the function jobs/brain-scores/score_brains.py calls, rubric
docs/brains/scoring/lake-brain-score-v1.json) returns for facts built from the bindings table, under these assumptions:
  * every lake of a batch becomes REVIEWED and is profiled (the 5 pilots stay profiled), directory = 621 lakes
  * validation stays NOT_VALIDATED (status 0 points and the 5.0 gate), health HEALTHY (no 2.0 gate)
  * the baseline of a lake is SUFFICIENT when its binding says >= 5 complete years (historyClass SUFFICIENT), LIMITED for 2..4, otherwise
    INSUFFICIENT (a TVA guide-only lake has 1 complete year); the pre-seed delivers the binding's history, the pilots keep their deep history
  * operatorPlan = the lake has a guide curve (TVA guide or a guideCurve level) or a zone (both edges); flood state is known when the binding
    has a floodPoolBottom level (it is then NORMAL/IN_POOL, never UNKNOWN); an unplanned lake has neither
  * a lake whose live source answers is `observed`; `--observed-share` < 1 marks the lakes with the oldest research probe as not observed
  * the 5 pilots are the published facts of 2026-10-13 (reproduced here: uncapped 6.3, displayed 3.0)
"""
import argparse
import datetime as dt
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "brain_platform")))
import preseed_fleet as P  # noqa: E402
from sector_brain_platform.scoring import score_lake  # noqa: E402

DIRECTORY_LAKES = 621
PILOT_FLOOD_KNOWN = {"Lake Hartwell|SC"}            # only Hartwell publishes a flood-pool bottom among the pilots (state flood NORMAL; TVA pilots UNKNOWN)
# Pre-declared batch rules (constants; the batch sizes are an OUTPUT of these rules applied to the bindings table):
B_MIN_COMPLETE_YEARS = 15           # "well seeded"
B_PROBE_AGE_SLACK_H = 6.0           # live source fresh at the research probe: age <= the binding's own declared lag + 6 h (RISE declares ~48 h)
B_MAX_EST_SECONDS = 120.0           # one lake's pre-seed must be cheap
C_MIN_CWMS_CALLS = 60               # heavy sub-daily CWMS pulls are "slower history"


def host_of(b):
    hs = b.get("history") or []
    return P.HISTORY_HOST.get(hs[0]["kind"], "none") if hs else "none"


def history_years(b):
    return b.get("historyCompleteYears") or 0


def probe_age(b):
    return ((b.get("verification") or {}).get("probe") or {}).get("ageHours")


def baseline_status(b):
    c = b.get("historyClass")
    if host_of(b) == "tva":
        return "INSUFFICIENT"
    return {"SUFFICIENT": "SUFFICIENT", "LIMITED": "LIMITED"}.get(c, "INSUFFICIENT")


def plan_facts(b):
    p = b.get("plan") or {}
    roles = {l["role"] for l in p.get("levels", [])}
    guide = bool(p.get("tvaOperatingGuide")) or "guideCurve" in roles
    zone = {"zoneTop", "zoneBottom"} <= roles
    return dict(plan=guide or zone, flood="floodPoolBottom" in roles)


def throughput_from_states(paths):
    """Aggregate the per-lake metrics of one or more preseed state.json files (smoke / measure runs) into seconds per call per host."""
    agg = {}
    lakes = []
    for p in paths:
        st = json.load(open(p))
        for lid, v in st["lakes"].items():
            m = v.get("metrics")
            if not m:
                continue
            lakes.append(lid)
            for h, x in m["byHost"].items():
                a = agg.setdefault(h, dict(calls=0, bytes=0, netSeconds=0.0))
                a["calls"] += x["calls"]
                a["bytes"] += x["bytes"]
                a["netSeconds"] += x["netSeconds"]
    per = {h: dict(calls=a["calls"], bytes=a["bytes"], netSeconds=round(a["netSeconds"], 2), secondsPerCall=round(a["netSeconds"] / a["calls"], 3),
                   bytesPerCall=round(a["bytes"] / a["calls"])) for h, a in sorted(agg.items()) if a["calls"]}
    return dict(schema="lake-brain-preseed-throughput/v1", lakes=sorted(set(lakes)), perHost=per)


def load_throughput(path):
    d = json.load(open(path))
    return {h: v["secondsPerCall"] for h, v in d["perHost"].items()}


DEFAULT_SECONDS_PER_CALL = {"cwms": 1.2, "usgs": 1.5, "rise": 2.8, "hads": 22.0, "tva": 1.2, "a2w": 0.7, "nwps": 0.5}


def lake_cost(b, now, cat, spc):
    calls = P.plan_lake(b, now, cat)
    secs = {h: n * max(P.HOST_GAP_SECONDS[h], spc.get(h, 1.0)) for h, n in calls.items()}
    return calls, secs


def describe(lid, b, now, cat, spc):
    calls, secs = lake_cost(b, now, cat, spc)
    pf = plan_facts(b)
    h = (b.get("history") or [{}])[0]
    return dict(lakeId=lid, liveProvider=b["live"][0]["provider"], historyKind=h.get("kind"), historyStat=h.get("stat"), host=host_of(b),
                nHistory=len(b.get("history") or []), historyClass=b.get("historyClass"), years=history_years(b), baseline=baseline_status(b),
                probeAgeH=probe_age(b), plan=pf["plan"], flood=pf["flood"], estCalls=sum(calls.values()), callsByHost=calls,
                estSeconds=round(sum(secs.values()), 1), strict=bool((b.get("plan") or {}).get("planStrict") or (b.get("plan") or {}).get("floodStrict")))


def select_batches(rows, pilots, now, cat, spc):
    """Deterministic A/B/C/D split of the non-pilot lakes. Returns (batches dict, per-lake description dict)."""
    info = {lid: describe(lid, b, now, cat, spc) for lid, b in sorted(rows.items()) if lid not in pilots}
    ok_b, ok_c, rest = [], [], []
    for lid, d in info.items():
        b = rows[lid]
        composite = d["nHistory"] != 1 or bool(b.get("historyNotes"))
        sub_daily_heavy = d["host"] == "cwms" and d["callsByHost"].get("cwms", 0) > C_MIN_CWMS_CALLS
        slow = d["host"] == "hads" or (d["host"] == "usgs" and d["historyStat"] == "iv") or sub_daily_heavy or d["estSeconds"] > B_MAX_EST_SECONDS
        fresh = d["probeAgeH"] is not None and d["probeAgeH"] <= (b["live"][0].get("lagMin") or 0) / 60.0 + B_PROBE_AGE_SLACK_H
        seeded_ok = d["baseline"] == "SUFFICIENT" and not composite and d["host"] in ("cwms", "usgs", "rise", "hads")
        if seeded_ok and not slow and fresh and d["years"] >= B_MIN_COMPLETE_YEARS:
            ok_b.append(lid)
        elif seeded_ok and slow:
            ok_c.append(lid)
        else:
            rest.append(lid)
    # canary A: one lake per (live provider, history kind/stat) among B-eligible lakes, plus the cheapest HADS lake of C; strict plan evidence first
    def rank(lid):
        d = info[lid]
        return (not (d["plan"] and d["flood"]), not d["strict"], d["estCalls"], lid)
    canary = []
    seen = set()
    for lid in sorted(ok_b, key=rank):
        key = (info[lid]["liveProvider"], info[lid]["historyKind"], info[lid]["historyStat"])
        if key not in seen:
            seen.add(key)
            canary.append(lid)
    hads = sorted((l for l in ok_c if info[l]["host"] == "hads"), key=rank)
    if hads:
        canary.append(hads[0])
    canary = sorted(canary)
    batches = dict(A=canary, B=sorted(set(ok_b) - set(canary)), C=sorted(set(ok_c) - set(canary)), D=sorted(rest))
    return batches, info


def build_facts(rows, profiled, pilots, observed_share=1.0):
    profiles, states = {}, {}
    order = sorted(profiled, key=lambda l: (-(probe_age(rows[l]) or 0.0), l))               # oldest probe first -> first to be 'not observed'
    n_unobs = int(math.floor(len(order) * (1.0 - observed_share) + 1e-9))
    unobs = {l for l in order[:n_unobs] if l not in pilots}
    for lid in sorted(profiled):
        b = rows[lid]
        pf = plan_facts(b)
        if lid in pilots:
            status, plan, flood = "SUFFICIENT", True, lid in PILOT_FLOOD_KNOWN
        else:
            status, plan, flood = baseline_status(b), pf["plan"], pf["flood"]
        profiles[lid] = dict(sourceCapability=dict(level=b["capability"]),
                             operatingPools=dict(guideCurve=dict(available=plan), operatingZoneSource=None),
                             historicalCoverage=dict(baselineStatus=status))
        states[lid] = dict(kind="unavailable" if lid in unobs else "observed", floodPoolState="NORMAL" if (flood and lid not in unobs) else "UNKNOWN")
    return profiles, states


def score(rows, profiled, pilots, now, observed_share=1.0, validation="NOT_VALIDATED"):
    profiles, states = build_facts(rows, profiled, pilots, observed_share)
    facts = dict(registry={}, validation=dict(status=validation), health=dict(status="HEALTHY"), profiles=profiles, states=states,
                 directoryLakeCount=DIRECTORY_LAKES)
    return score_lake(facts, now)


def project(rows, pilots, batches, now, observed_share=1.0):
    now_dt = now
    out = []
    profiled = set(pilots)
    s = score(rows, profiled, pilots, now_dt, observed_share)
    out.append(dict(step="today (5 pilots)", profiled=len(profiled), displayed=s["value"], uncapped=s["uncapped"], gates=[g["gate"] for g in s["scoreBlockers"] if "gate" in g],
                    breakdown={k: v.get("value") for k, v in s["scoreBreakdown"].items()}))
    for name in ("A", "B", "C", "D"):
        profiled |= set(batches[name])
        s = score(rows, profiled, pilots, now_dt, observed_share)
        out.append(dict(step=f"after batch {name}", profiled=len(profiled), displayed=s["value"], uncapped=s["uncapped"],
                        gates=[g["gate"] for g in s["scoreBlockers"] if "gate" in g],
                        breakdown={k: v.get("value") for k, v in s["scoreBreakdown"].items()}))
    return out


def batch_summary(names, info, spc):
    by_host_calls, by_host_secs = {}, {}
    for l in names:
        d = info[l]
        for h, n in d["callsByHost"].items():
            by_host_calls[h] = by_host_calls.get(h, 0) + n
            by_host_secs[h] = by_host_secs.get(h, 0) + n * max(P.HOST_GAP_SECONDS[h], spc.get(h, 1.0))
    # workers run per FIRST history host; live reads of another host add to that host's gate too, so the batch wall is the busiest host
    wall = max(by_host_secs.values()) if by_host_secs else 0.0
    return dict(lakes=len(names), callsByHost=dict(sorted(by_host_calls.items())), totalCalls=sum(by_host_calls.values()),
                secondsByHost={h: round(v) for h, v in sorted(by_host_secs.items())}, wallSecondsParallelByHost=round(wall),
                wallSecondsSerial=round(sum(by_host_secs.values())),
                providers={k: sum(1 for l in names if info[l]["liveProvider"] == k) for k in sorted({info[l]["liveProvider"] for l in names})},
                historyHosts={k: sum(1 for l in names if info[l]["host"] == k) for k in sorted({info[l]["host"] for l in names})})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bindings", default=P.DEFAULT_BINDINGS)
    ap.add_argument("--catalog")
    ap.add_argument("--throughput", help="measured_throughput.json (seconds per call per host); default: built-in estimates")
    ap.add_argument("--now", default="2026-10-13T20:00:00Z")
    ap.add_argument("--observed-share", type=float, default=1.0)
    ap.add_argument("--accepted", help="the real accepted_batch.json: batches are then built from the accepted lakes only (pilots stay)")
    ap.add_argument("--out")
    ap.add_argument("--emit-stage", choices=["A", "B", "C", "D"], help="with --accepted and --out: write the CUMULATIVE staged accepted file (batches A..X restricted to the real accepted batch; "
                    "pilots excluded) in the dict form scripts/generate-lake-bindings.py reads. A derived subset, never a review result")
    ap.add_argument("--make-throughput", help="comma list of preseed state.json files: write their aggregate seconds-per-call JSON to --out and exit")
    a = ap.parse_args(argv)
    if a.make_throughput:
        res = throughput_from_states([x for x in a.make_throughput.split(",") if x])
        P.atomic_write(a.out, json.dumps(res, indent=1, sort_keys=True)) if a.out else print(json.dumps(res, indent=1))
        return 0
    doc, rows = P.load_bindings(a.bindings)
    now = P.parse_iso(a.now)
    pilots = {p["lakeId"] for p in doc.get("pilotReproduction", [])}
    if a.accepted:
        acc = set(json.load(open(a.accepted)))
        rows = {l: b for l, b in rows.items() if l in acc or l in pilots}
    cat = P.load_cwms_catalog(a.catalog) if a.catalog else None
    spc = load_throughput(a.throughput) if a.throughput else dict(DEFAULT_SECONDS_PER_CALL)
    batches, info = select_batches(rows, pilots, now, cat, spc)
    res = dict(now=a.now, pilots=sorted(pilots), assumptions=dict(directory=DIRECTORY_LAKES, validation="NOT_VALIDATED", observedShare=a.observed_share),
               secondsPerCall=spc, batches={k: dict(summary=batch_summary(v, info, spc), lakes=v) for k, v in batches.items()},
               projection=project(rows, pilots, batches, now, a.observed_share),
               projectionObserved90=project(rows, pilots, batches, now, 0.9),
               fleet=batch_summary([l for v in batches.values() for l in v], info, spc))
    if a.emit_stage:
        if not (a.accepted and a.out):
            raise SystemExit("--emit-stage needs --accepted and --out")
        upto = "ABCD"[: "ABCD".index(a.emit_stage) + 1]
        ids = sorted(l for b in upto for l in batches[b])
        stage = dict(lakeIds=ids, stage=a.emit_stage, cumulativeBatches=list(upto), stagedFromAcceptedBatchSha256=P.sha256_file(a.accepted),
                     note="DERIVED subset of the real accepted_batch.json for a staged rollout (jobs/lake-brain/history/rollout_plan.py --emit-stage); not a review result")
        P.atomic_write(a.out, json.dumps(stage, indent=1))
        print(f"stage {a.emit_stage}: {len(ids)} accepted lakes -> {a.out}")
        return 0
    text = json.dumps(res, indent=1)
    if a.out:
        P.atomic_write(a.out, text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
