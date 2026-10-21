#!/usr/bin/env python3
"""Build the machine-readable engineering status (contracts/schemas/engineering-status-v1.schema.json) from committed Cortex records only.

  python3 tools/cortex_status/build_engineering_status.py --write    # regenerate docs/cortex/engineering-status/engineering-status.json
  python3 tools/cortex_status/build_engineering_status.py --check    # exit 1 if the committed report is stale or invalid

Inputs (docs/cortex/engineering-status/inputs/): source.json, memory-standing-checks.json, verification.json, decisions.json; plus brains/*/brain.json and
the control manifest (Brain ids and lifecycles) and CLAUDE.md (the Cortex pin). Deterministic: no clock, no network, no git call. It reports only what
the records say; it never computes a result, and production status stays whatever the evidence supports (NOT_VERIFIED otherwise).
Nothing is written anywhere but the report file; publishing it to Sector Ops (Firebase, a bucket) is a separate, gated decision.
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DIR = os.path.join(ROOT, "docs", "cortex", "engineering-status")
REPORT = os.path.join(DIR, "engineering-status.json")
SCHEMA = os.path.join(ROOT, "contracts", "schemas", "engineering-status-v1.schema.json")
STATUSES = ["PASS", "FAIL", "PARTIAL", "NOT_VERIFIED", "NOT_APPLICABLE"]
sys.path.insert(0, os.path.join(ROOT, "tools", "architecture"))
from jsonschema_lite import validate  # noqa: E402


def _load(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return json.load(fh)


def _pin():
    m = re.search(r"^Cortex pin:\s*([0-9a-f]{7,40})\s*$", open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8").read(), re.M)
    if not m:
        raise SystemExit("CLAUDE.md names no Cortex pin")
    return m.group(1)


def build() -> dict:
    src = _load(DIR, "inputs", "source.json")
    mem = _load(DIR, "inputs", "memory-standing-checks.json")
    ver = _load(DIR, "inputs", "verification.json")
    dec = _load(DIR, "inputs", "decisions.json")
    manifest = _load(ROOT, "jobs", "brain_platform", "sector_brain_platform", "control_manifest.json")["brains"]
    packages = {}
    for d in sorted(os.listdir(os.path.join(ROOT, "brains"))):
        p = os.path.join(ROOT, "brains", d, "brain.json")
        if not d.startswith("_") and os.path.isfile(p):
            bj = _load(p)
            packages[bj["brainId"]] = {"directory": f"brains/{d}", "lifecycle": bj["lifecycle"]}
    by_id = {b["brainId"]: b for b in mem["brains"]}
    if set(by_id) != set(manifest):
        raise SystemExit(f"memory matrix Brains {sorted(by_id)} != control manifest Brains {sorted(manifest)}")
    check_ids = [c["id"] for c in mem["checks"]]
    brains = []
    for bid in sorted(manifest):
        m = by_id[bid]
        rows = [{"check": c, **m["checks"][c]} for c in check_ids]
        summary = {side: {s: n for s in STATUSES if (n := sum(r[side] == s for r in rows))} for side in ("branch", "production")}
        pkg = packages.get(bid)
        brains.append({"brainId": bid, "directory": pkg["directory"] if pkg else m["directory"],
                       "lifecycle": pkg["lifecycle"] if pkg else manifest[bid]["lifecycle"],
                       "packageStatus": "CANONICAL" if pkg else "BRANCH_ONLY",
                       "structuralCertification": src["structuralCertification"][bid], "memory": rows, "memorySummary": summary,
                       "recovery": m["recovery"], "blockers": src["blockers"].get(bid, [])})
    return {"schema": "engineering-status-v1", "schemaVersion": "1.0.0", "reportId": src["reportId"],
            "standards": {"framework": "Rehtac Cortex", "version": src["cortexVersion"], "pin": _pin(), "pack": src["cortexPack"]},
            "source": {"repository": src["repository"], "branch": src["branch"], "evaluatedCommit": src["evaluatedCommit"], "evaluatedAt": src["evaluatedAt"],
                       "session": src["session"], "productionBasis": mem["productionBasis"]},
            "statusVocabulary": STATUSES, "brains": brains, "verification": ver["results"], "decisions": dec["decisions"], "cortexGaps": src["cortexGaps"]}


def render(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    report = build()
    errs = list(validate(report, _load(SCHEMA)))
    if errs:
        print("engineering-status-v1 schema violations:\n" + "\n".join(errs[:20]))
        return 1
    text = render(report)
    if a.write:
        open(REPORT, "w", encoding="utf-8").write(text)
        print(f"wrote {os.path.relpath(REPORT, ROOT)} ({report['reportId']})")
        return 0
    if not os.path.exists(REPORT) or open(REPORT, encoding="utf-8").read() != text:
        print(f"{os.path.relpath(REPORT, ROOT)} is stale: regenerate with --write")
        return 1
    print(f"{os.path.relpath(REPORT, ROOT)}: OK {report['reportId']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
