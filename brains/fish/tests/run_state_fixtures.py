"""SYNTHETIC fixtures for the run_state golden and fleet tests: a staged rules directory, a snapshot and a presence file.

The golden file tests/golden/run_state_pilot_golden.json was produced from origin/main @ 16d2bc14 (before the fleet mode existed) by
`python3 tests/run_state_fixtures.py --regen-golden <path to that commit's brains/fish/runtime/run_state.py>`. It must never be regenerated
from the code under test: it is the proof that the pilot path did not change."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.join(os.path.dirname(HERE), "runtime")
RUN_STATE = os.path.join(RUNTIME, "run_state.py")
GOLDEN = os.path.join(HERE, "golden", "run_state_pilot_golden.json")
NOW = "2026-04-20T03:00:00Z"
PILOTS = ("Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC")


def _ev(i, stream):
    return {"evidenceId": f"E{i}", "packet": "synthetic", "sourceNo": f"S{i}", "readStatus": "READ-ABSTRACT", "streamId": stream, "directness": "DIRECT",
            "counts": True, "southeast": False}


def _rule(rid, **kw):
    r = {"schemaVersion": 1, "ruleId": rid, "ruleVersion": 1, "speciesId": "example_fish", "kind": "RESPONSE", "status": "RECONCILED",
         "confidence": "LOW", "transferability": {"southeastReservoir": "PARTIAL"}, "applicability": {"months": [3, 4, 5], "regions": ["south"]},
         "feature": {"featureId": "warmRise", "states": ["TRUE"]}, "response": "FAVORABLE", "behavior": "RUN", "evidence": [_ev(1, "stream-a")]}
    r.update(kw)
    return r


def write_rules(d: str, extra=()) -> str:
    os.makedirs(d, exist_ok=True)
    rules = [_rule("EX-FLW-01"),
             _rule("EX-NGT-01", feature={"featureId": "daypart", "states": ["NIGHT"]}, behavior="FEED", applicability={"months": [3, 4, 5, 6], "regions": ["south"]}),
             *extra]
    body = json.dumps({"speciesId": "example_fish", "rules": rules}).encode()
    open(os.path.join(d, "example_fish.json"), "wb").write(body)
    man = {"rulesVersion": "synthetic.1", "files": [{"path": "example_fish.json", "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}]}
    json.dump(man, open(os.path.join(d, "rules_manifest.json"), "w"))
    return d


def snapshot(evidence_class="sensor", gen="2026-04-20T01:00:00Z") -> dict:
    """A measured sensor reading with no trend: the old and the new measured-only gate read it identically, so the golden isolates the runner."""
    wt = {"currentTempF": 64.4, "kind": "measured", "observationType": "OBSERVED", "provenance": {"generatedAt": gen}}
    if evidence_class is not None:
        wt["evidenceClass"] = evidence_class
    return {"lakeState": {"trendState": "RISING", "provenance": {"generatedAt": gen}}, "waterTemperature": wt,
            "waterClarity": {"clarityFt": 2.5, "provenance": {"generatedAt": gen}}}


PRESENCE = {"example_fish": {"presenceState": "established", "confidence": "HIGH"}, "other_fish": {"presenceState": "historical"}}


def stage(d: str) -> dict:
    """rules/, snapshot.json, presence.json under d."""
    write_rules(os.path.join(d, "rules"))
    json.dump(snapshot(), open(os.path.join(d, "snapshot.json"), "w"))
    json.dump(PRESENCE, open(os.path.join(d, "presence.json"), "w"))
    return {"rules": os.path.join(d, "rules"), "snapshot": os.path.join(d, "snapshot.json"), "presence": os.path.join(d, "presence.json")}


def run_pilot(script: str, lake: str, cwd: str, env: dict | None = None) -> dict:
    """One pilot run, exactly as an operator types it; returns stdout, the written file and a second (unchanged) run's stdout."""
    p = stage(cwd)
    args = [sys.executable, script, "--lake", lake, "--rules", p["rules"], "--snapshot", p["snapshot"], "--presence", p["presence"], "--now", NOW, "--out", "out"]
    e = {k: v for k, v in os.environ.items() if k != "FISH_FLEET_RUNNER"} | (env or {})
    first = subprocess.run(args, cwd=cwd, env=e, capture_output=True, text=True, check=True)
    written = sorted(os.listdir(os.path.join(cwd, "out")))
    body = open(os.path.join(cwd, "out", written[0]), encoding="utf-8").read()
    second = subprocess.run(args, cwd=cwd, env=e, capture_output=True, text=True, check=True)
    return {"stdout": first.stdout, "files": written, "file": body, "rerunStdout": second.stdout}


LIVE_DRIVER = r"""
import json, os, sys
script, db_path = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
import brain_platform as bp
DB = json.load(open(db_path))

class FakeRtdb:
    def __init__(self, url, tokens, brain_id=None, recorder=None):
        self.reads = []
    def get(self, path, **kw):
        self.reads.append(path)
        if path in DB.get("_fail", ()):
            raise RuntimeError("injected read failure: " + path)
        node = DB
        for part in path.strip("/").split("/"):
            node = node.get(part) if isinstance(node, dict) else None
        return node
    def consumed(self):
        return list(self.reads)

bp.BrainRtdb = FakeRtdb
bp.TokenProvider = lambda *a, **k: None
import run_state
sys.exit(run_state.main(sys.argv[3:]))
"""

SPECIES = {"example_fish": {"researchMaturity": "RESEARCH", "assessment": "ASSESSED", "knowledge": {"overallRounded": 5.0}},
           "other_fish": {"researchMaturity": "RESEARCH", "assessment": "ASSESSED"}}


def fake_db(keys) -> dict:
    return {"snapshots": {k: {"latest": snapshot()} for k in keys}, "lakes": {k: {"speciesPresence": PRESENCE} for k in keys}, "species": SPECIES}


def run_live(script: str, args: list, cwd: str, db: dict, env: dict | None = None) -> subprocess.CompletedProcess:
    drv, dbp = os.path.join(cwd, "driver.py"), os.path.join(cwd, "db.json")
    open(drv, "w").write(LIVE_DRIVER)
    json.dump(db, open(dbp, "w"))
    e = {k: v for k, v in os.environ.items() if k != "FISH_FLEET_RUNNER"} | (env or {})
    return subprocess.run([sys.executable, drv, script, dbp, *args], cwd=cwd, env=e, capture_output=True, text=True)


def run_pilot_live(script: str, lake: str, cwd: str, key: str, env: dict | None = None) -> dict:
    rules = write_rules(os.path.join(cwd, "rules"))
    args = ["--lake", lake, "--rules", rules, "--live", "--now", NOW, "--out", "out"]
    first = run_live(script, args, cwd, fake_db([key]), env)
    assert first.returncode == 0, first.stderr
    written = sorted(os.listdir(os.path.join(cwd, "out")))
    return {"stdout": first.stdout, "files": written, "file": open(os.path.join(cwd, "out", written[0]), encoding="utf-8").read()}


PILOT_KEYS = {"Guntersville|AL": "Guntersville_AL", "Wheeler|AL": "Wheeler_AL", "Wilson|AL": "Wilson_AL", "Pickwick Lake|TN": "Pickwick_Lake_TN",
              "Lake Hartwell|SC": "Lake_Hartwell_SC"}


def regen_golden(script: str) -> None:
    out, live = {}, {}
    for lake in PILOTS:
        with tempfile.TemporaryDirectory() as d:
            out[lake] = run_pilot(script, lake, d)
        with tempfile.TemporaryDirectory() as d:
            live[lake] = run_pilot_live(script, lake, d, PILOT_KEYS[lake])
    json.dump({"source": "origin/main @ 16d2bc14 brains/fish/runtime/run_state.py (pre-fleet)", "now": NOW, "runs": out, "liveRuns": live},
              open(GOLDEN, "w"), indent=1, sort_keys=True)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--regen-golden":
        regen_golden(sys.argv[2])
    else:
        raise SystemExit(__doc__)
