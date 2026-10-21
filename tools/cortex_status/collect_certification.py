#!/usr/bin/env python3
"""Run every registered Brain's Brain Certification Kit V1 suite and record the ACTUAL per-proof outcomes for the engineering status report.

  python3 tools/cortex_status/collect_certification.py [--python PY]     # writes docs/cortex/engineering-status/inputs/certification.json

Each Brain's kit test module (brains/<dir>/tests/test_*_kit_certification.py) runs in that Brain's directory with its pytest.ini, exactly as CI runs
it. Outcomes come from pytest's own report (-rA): PASS, FAIL, or NOT_APPLICABLE for a proof the spec declares not applicable (pytest skip with
the NOT_APPLICABLE reason). Nothing is inferred; a suite that does not run is recorded as NOT_RUN. Local only: no network, no production."""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "docs", "cortex", "engineering-status", "inputs", "certification.json")
LINE = re.compile(r"^(PASSED|FAILED|SKIPPED|ERROR)\s+(?:\[\d+\]\s+)?(\S+?)(?:::(\S+))?(?:\s+-\s+(.*))?$")


def run_brain(py: str, d: str) -> dict:
    tests = os.path.join(ROOT, "brains", d, "tests")
    mods = sorted(f for f in os.listdir(tests) if f.startswith("test_") and f.endswith("_kit_certification.py"))
    if not mods:
        return {"status": "NOT_RUN", "reason": "no Kit V1 test module"}
    r = subprocess.run([py, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", *[os.path.join("tests", m) for m in mods]],
                       cwd=os.path.join(ROOT, "brains", d), capture_output=True, text=True, timeout=900)
    proofs, mutations = {}, {"passed": 0, "failed": 0}
    for raw in r.stdout.splitlines():
        m = LINE.match(raw.strip())
        if not m:
            continue
        outcome, _, name, reason = m.groups()
        name = name or ""
        pm = re.match(r"test_cert_(p\d\d)_", name)
        if pm:
            pid = pm.group(1).upper()
            proofs[pid] = {"PASSED": "PASS", "FAILED": "FAIL", "ERROR": "FAIL"}.get(outcome) or (
                "NOT_APPLICABLE" if reason and "NOT_APPLICABLE" in reason else "SKIPPED")
        elif name.startswith("test_cert_mutation_"):
            mutations["passed" if outcome == "PASSED" else "failed"] += 1
    for raw in r.stdout.splitlines():                                    # a skipped proof reports as "SKIPPED [n] file:line: NOT_APPLICABLE (<brain> Pnn): why"
        pm = re.search(r"NOT_APPLICABLE \(\S+ (P\d\d)\)", raw)
        if raw.startswith("SKIPPED") and pm:
            proofs[pm.group(1)] = "NOT_APPLICABLE"
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    ok = r.returncode == 0 and proofs and all(v in ("PASS", "NOT_APPLICABLE") for v in proofs.values())
    return {"status": "PASS" if ok else "FAIL", "proofs": dict(sorted(proofs.items())), "mutations": mutations, "summary": tail}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args(argv)
    ids = {}
    for d in sorted(os.listdir(os.path.join(ROOT, "brains"))):
        p = os.path.join(ROOT, "brains", d, "brain.json")
        if not d.startswith("_") and os.path.isfile(p):
            ids[d] = json.load(open(p))["brainId"]
    out = {"schemaVersion": "1.0.0", "kit": "BRAIN_CERT_KIT_V1", "collectedWith": "pytest -rA per Brain directory (tools/cortex_status/collect_certification.py)",
           "brains": {ids[d]: {"directory": f"brains/{d}", **run_brain(a.python, d)} for d in ids}}
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(out, indent=2) + "\n")
    bad = [b for b, v in out["brains"].items() if v["status"] != "PASS"]
    print(f"wrote {os.path.relpath(OUT, ROOT)}; failing: {bad or 'none'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
