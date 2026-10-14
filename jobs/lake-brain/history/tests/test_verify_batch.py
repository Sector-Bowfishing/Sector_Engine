"""verify_batch.py with a fake read-only RTDB/GCS reader."""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import verify_batch as V
import rollout_plan as R

LAKE = "Test Lake|ZZ"
K = V.lake_key(LAKE)


def good_tree():
    return {
        f"lakes/{K}/brain": dict(sourceCapability=dict(bindingStatus="REVIEWED", bindingVersion="bindings-x"), readiness=dict(lake="BETA"),
                                 historicalCoverage=dict(baselineStatus="SUFFICIENT", observationCount=3000, historyEnd="2026-10-13")),
        f"lakes/{K}/states/lake": dict(kind="OBSERVED", freshness=dict(stale=False), floodPoolState="NORMAL", currentElevationFt=1.0, provenance=dict(qualityFlags=[])),
        "health/brains/lake-brain": dict(status="HEALTHY", durationMs=9000, errorCount=0, staleLakeCount=0, deployedVersion="abc"),
        "validation/lake-brain": dict(status="NOT_VALIDATED"),
        "scores/lake-brain": dict(value=3.0, uncapped=6.3, scoreVersion="lake-brain-score-v1", scoreBlockers=[dict(gate="coverage")]),
        "lakeFleet": {K: dict(slots=dict(lake=dict(readiness="BETA")))},
    }


class Fake:
    def __init__(self, tree, objects=None):
        self.tree, self.objects = tree, objects or {}

    def rtdb(self, path):
        return self.tree.get(path)

    def gcs_list(self, prefix):
        return [n for n in self.objects if n.startswith(prefix)]

    def gcs_cat(self, name):
        return self.objects[name]


MAN = {LAKE: dict(rows=3000, completeYears=8)}


def test_good_batch_passes_and_reports_ledger():
    line = json.dumps(dict(lakeId=LAKE, provider="a2w"))
    r = V.run(Fake(good_tree(), {"predictions/2026/10/13/1Z-a.jsonl": line + "\n"}), [LAKE], MAN, expect_profiled=1, ledger_day="2026/10/13")
    assert r["ok"] and r["summary"] == dict(lakes=1, hardFailures=0, softWarnings=0)
    assert r["ledger"]["providers"] == ["a2w"] and r["ledger"]["batchLakesLedgered"] == [LAKE]


def mutate(path_fn):
    t = good_tree()
    path_fn(t)
    return V.run(Fake(t), [LAKE], MAN, expect_profiled=1)


def test_each_hard_failure_is_detected():
    cases = {
        "profile missing": lambda t: t.pop(f"lakes/{K}/brain"),
        "bindingStatus": lambda t: t[f"lakes/{K}/brain"]["sourceCapability"].update(bindingStatus="CANDIDATE"),
        "readiness": lambda t: t[f"lakes/{K}/brain"]["readiness"].update(lake="DEGRADED"),
        "baselineStatus": lambda t: t[f"lakes/{K}/brain"]["historicalCoverage"].update(baselineStatus="LIMITED"),
        "observationCount": lambda t: t[f"lakes/{K}/brain"]["historicalCoverage"].update(observationCount=10),
        "state missing": lambda t: t.pop(f"lakes/{K}/states/lake"),
        "state kind": lambda t: t[f"lakes/{K}/states/lake"].update(kind="UNAVAILABLE"),
        "historyLiveMismatch": lambda t: t[f"lakes/{K}/states/lake"]["provenance"].update(qualityFlags=["historyLiveMismatch:+18.2ft"]),
    }
    for want, fn in cases.items():
        r = mutate(fn)
        assert not r["ok"] and any(want in h for l in r["lakes"] for h in l["hard"]), (want, r["lakes"])


def test_fleet_level_failures_and_soft_warnings():
    r = mutate(lambda t: t["validation/lake-brain"].update(status="PARTIAL"))
    assert not r["ok"] and "validation" in r["fleetHard"][0]
    r = mutate(lambda t: t["health/brains/lake-brain"].update(status="FAILED"))
    assert not r["ok"]
    t = good_tree()
    r = V.run(Fake(t), [LAKE], MAN, expect_profiled=2)
    assert not r["ok"] and "profiled lakes 1" in r["fleetHard"][0]
    r = mutate(lambda t: (t[f"lakes/{K}/states/lake"].update(freshness=dict(stale=True)), t[f"lakes/{K}/states/lake"]["provenance"].update(qualityFlags=["primarySourceStale"])))
    assert r["ok"] and r["summary"]["softWarnings"] == 2


def test_main_reads_files(tmp_path, capsys):
    f = tmp_path / "lakes.txt"
    f.write_text(LAKE + "\n\n")
    m = tmp_path / "m.json"
    m.write_text(json.dumps(dict(lakes=MAN)))
    assert V.main(["--lakes-file", str(f), "--manifest", str(m)], reader=Fake(good_tree())) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    bad = good_tree()
    bad["validation/lake-brain"]["status"] = "VALIDATED"
    assert V.main(["--lakes-file", str(f)], reader=Fake(bad)) == 1


def test_script_is_get_only():
    import ast
    tree = ast.parse(open(V.__file__).read())
    reqs = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "Request"]
    assert len(reqs) == 2 and all(len(r.args) == 1 and {k.arg for k in r.keywords} == {"headers"} for r in reqs)          # no data=, no method=: urllib GET
    subs = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "run"]
    assert len(subs) == 1 and ast.literal_eval(subs[0].args[0]) == ["gcloud", "auth", "print-access-token"]           # the only subprocess
