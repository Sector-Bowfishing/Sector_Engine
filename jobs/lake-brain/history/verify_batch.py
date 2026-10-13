#!/usr/bin/env python3
"""Lake Brain staged rollout: READ-ONLY verification of a batch after the job ran (checklist steps 8-12 of LAKE_BRAIN_STAGED_FLEET_ROLLOUT.md).

    python3 verify_batch.py --lakes-file lakes.txt [--manifest preseed_manifest.json] [--expect-profiled N] [--ledger-day 2026/10/13]

Reads (GET only) the Brain RTDB `sector-brain` (never the customer RTDBs) and, for the ledger, the GCS object listing of gs://sector-lake-brain/predictions/.
Auth: `gcloud auth print-access-token` (read scope is enough). It writes nothing. Exit 0 = every hard check passed, 1 = a hard check failed.

Per lake (hard unless marked soft):
  profile exists; sourceCapability.bindingStatus == REVIEWED; readiness.lake in {CALIBRATION, BETA}; historicalCoverage.baselineStatus as expected
  from the pre-seed manifest (SUFFICIENT iff >= 5 complete years there); observationCount >= the pre-seeded row count; state exists, kind OBSERVED, not stale (soft: stale),
  no `historyLiveMismatch` flag (HARD: that is the datum/series mismatch the pre-seed check exists to prevent), floodPoolState known where the binding has a flood level (soft).
Fleet: /health/brains/lake-brain status in {HEALTHY, WARNING} and errorCount reported; /validation/lake-brain status stays NOT_VALIDATED (HARD: a run must not change it);
  /scores/lake-brain printed (value, uncapped) for comparison with the projection; the number of profiled lakes (lakeFleet slots.lake) equals --expect-profiled when given;
  the newest ledger object of the day exists (soft) and lists the provider values it contains.
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request

RTDB = "https://sector-brain.firebaseio.com"
BUCKET = "sector-lake-brain"


def lake_key(lake_id):
    return re.sub(r"[^A-Za-z0-9]+", "_", lake_id)


def token():
    return subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True).stdout.strip()


class Reader:
    """GET-only access. `rtdb(path)` -> parsed JSON or None; `gcs_list(prefix)` -> [object names]. Replaced by a fake in the tests."""

    def __init__(self, base=RTDB, tok=None):
        self.base = base.rstrip("/")
        self.tok = tok or token()

    def _get(self, url):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.tok}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())

    def rtdb(self, path):
        return self._get(f"{self.base}/{path.strip('/')}.json")

    def gcs_list(self, prefix):
        q = urllib.parse.urlencode({"prefix": prefix})
        d = self._get(f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o?{q}")
        return [x["name"] for x in d.get("items", [])]

    def gcs_cat(self, name):
        req = urllib.request.Request(f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/{urllib.parse.quote(name, safe='')}?alt=media",
                                     headers={"Authorization": f"Bearer {self.tok}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode()


def check_lake(rd, lake_id, manifest_entry=None):
    k = lake_key(lake_id)
    hard, soft = [], []
    prof = rd.rtdb(f"lakes/{k}/brain")
    state = rd.rtdb(f"lakes/{k}/states/lake")
    row = dict(lakeId=lake_id)
    if not prof:
        return dict(row, hard=["profile missing"], soft=[])
    cap = prof.get("sourceCapability") or {}
    cov = prof.get("historicalCoverage") or {}
    row.update(bindingStatus=cap.get("bindingStatus"), bindingVersion=cap.get("bindingVersion"), readiness=(prof.get("readiness") or {}).get("lake"),
               baselineStatus=cov.get("baselineStatus"), observationCount=cov.get("observationCount"), historyEnd=cov.get("historyEnd"))
    if cap.get("bindingStatus") != "REVIEWED":
        hard.append(f"bindingStatus {cap.get('bindingStatus')}")
    if row["readiness"] not in ("CALIBRATION", "BETA"):
        hard.append(f"readiness {row['readiness']}")
    if manifest_entry and manifest_entry.get("rows") is not None:
        exp = "SUFFICIENT" if (manifest_entry.get("completeYears") or 0) >= 5 else "LIMITED" if (manifest_entry.get("completeYears") or 0) >= 2 else None
        if exp and cov.get("baselineStatus") != exp:
            hard.append(f"baselineStatus {cov.get('baselineStatus')} but the pre-seed has {manifest_entry.get('completeYears')} complete years (expected {exp})")
        if (cov.get("observationCount") or 0) < manifest_entry["rows"]:
            hard.append(f"observationCount {cov.get('observationCount')} < pre-seeded rows {manifest_entry['rows']}")
    if not state:
        hard.append("state missing")
        return dict(row, hard=hard, soft=soft)
    flags = (state.get("provenance") or {}).get("qualityFlags") or []
    row.update(kind=state.get("kind"), stale=(state.get("freshness") or {}).get("stale"), flood=state.get("floodPoolState"), flags=flags,
               level=state.get("currentElevationFt"))
    if str(state.get("kind")).upper() != "OBSERVED":
        hard.append(f"state kind {state.get('kind')}")
    if any(str(f).startswith("historyLiveMismatch") for f in flags):
        hard.append("historyLiveMismatch flag: " + ", ".join(f for f in flags if str(f).startswith("historyLiveMismatch")))
    if row["stale"]:
        soft.append("state stale")
    if any(str(f).startswith(("primarySourceStale", "fallbackSource")) for f in flags):
        soft.append("fallback/stale primary: " + ", ".join(str(f) for f in flags if str(f).startswith(("primarySourceStale", "fallbackSource"))))
    return dict(row, hard=hard, soft=soft)


def run(rd, lakes, manifest=None, expect_profiled=None, ledger_day=None):
    res = dict(lakes=[check_lake(rd, l, (manifest or {}).get(l)) for l in lakes])
    fleet = []
    health = rd.rtdb("health/brains/lake-brain") or {}
    validation = rd.rtdb("validation/lake-brain") or {}
    score = rd.rtdb("scores/lake-brain") or {}
    lf = rd.rtdb("lakeFleet") or {}
    profiled = sum(1 for v in lf.values() if ((v or {}).get("slots") or {}).get("lake") or ((v or {}).get("readiness") or {}).get("lake"))
    res["fleet"] = dict(health=health.get("status"), durationMs=health.get("durationMs"), errorCount=health.get("errorCount"), staleLakeCount=health.get("staleLakeCount"),
                        deployedVersion=health.get("deployedVersion"), validation=validation.get("status"), profiled=profiled,
                        score=dict(value=score.get("value"), uncapped=score.get("uncapped"), version=score.get("scoreVersion"),
                                   blockers=[b.get("gate") or b.get("dimension") for b in score.get("scoreBlockers", [])]))
    if health.get("status") not in ("HEALTHY", "WARNING"):
        fleet.append(f"health {health.get('status')}")
    if validation.get("status") != "NOT_VALIDATED":
        fleet.append(f"validation status is {validation.get('status')} (a Lake Brain run must leave it NOT_VALIDATED)")
    if expect_profiled is not None and profiled != expect_profiled:
        fleet.append(f"profiled lakes {profiled} != expected {expect_profiled}")
    if ledger_day:
        names = sorted(n for n in rd.gcs_list(f"predictions/{ledger_day}/") if n.endswith(".jsonl"))
        led = dict(objects=len(names), newest=names[-1] if names else None)
        if names:
            lines = [json.loads(l) for l in rd.gcs_cat(names[-1]).splitlines() if l.strip()]
            led.update(records=len(lines), providers=sorted({x.get("provider") for x in lines}), lakes=len({x.get("lakeId") for x in lines}),
                       batchLakesLedgered=sorted(set(lakes) & {x.get("lakeId") for x in lines}))
        res["ledger"] = led
        res["ledgerSoft"] = [] if names else ["no ledger object for the day"]
    res["fleetHard"] = fleet
    bad = [r for r in res["lakes"] if r["hard"]]
    res["ok"] = not bad and not fleet
    res["summary"] = dict(lakes=len(lakes), hardFailures=len(bad), softWarnings=sum(len(r["soft"]) for r in res["lakes"]))
    return res


def main(argv=None, reader=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lakes-file", required=True, help="one lake id per line (e.g. the batch from rollout_plan.v1.json)")
    ap.add_argument("--manifest", help="preseed_manifest.json of the batch's pre-seed")
    ap.add_argument("--expect-profiled", type=int)
    ap.add_argument("--ledger-day", help="yyyy/MM/dd (UTC) of the run, to inspect the newest prediction ledger object")
    ap.add_argument("--rtdb", default=RTDB)
    a = ap.parse_args(argv)
    lakes = [l.strip() for l in open(a.lakes_file) if l.strip()]
    man = json.load(open(a.manifest))["lakes"] if a.manifest else None
    rd = reader or Reader(a.rtdb)
    res = run(rd, lakes, man, a.expect_profiled, a.ledger_day)
    print(json.dumps(res, indent=1, sort_keys=True))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
