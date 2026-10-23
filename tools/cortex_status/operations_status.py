#!/usr/bin/env python3
"""Map a published engineering-status-ops-v1 (>= 1.2.0) document to Cortex's brain-operations-status-v1 so `cortex.py ops-check --status`
validates exactly what Sector Ops renders (Cortex 2.6.0 operations.md §7).

  python3 tools/cortex_status/operations_status.py --doc published.json --out status.json

The legacy `operationalReadiness` layer is RELEASE readiness (owner decision D-IA-2, Option B): it is carried as `releaseReadiness` beside the four
dimensions, never as a combined readiness verdict. Read-only; no network."""
import argparse
import json
import sys

LANE = {"SHADOW": "INTERNAL_EXPERIMENTAL"}


def convert(doc: dict) -> dict:
    if doc.get("schema") != "engineering-status-ops-v1" or doc.get("state") != "AVAILABLE":
        raise SystemExit("needs an AVAILABLE engineering-status-ops-v1 document")
    brains = []
    for b in doc.get("brains") or []:
        o = b.get("operations")
        if not o:
            raise SystemExit(f"{b.get('brainId')}: no operations block (engineering-status-ops-v1 < 1.2.0 or not overlaid)")
        io = dict(o.get("internalOperation") or {"status": "NOT_VERIFIED"})
        k = o["knowledgeRelease"]
        lane = LANE.get(io.get("status"), "INTERNAL_OBSERVATION")
        out = {"brainId": b["brainId"], "runtimeReadiness": o.get("runtimeReadiness") or {"status": "NOT_VERIFIED"}, "internalOperation": io,
               "scientificValidation": o["scientificValidation"],
               "knowledgeRelease": {"state": k["state"], "releaseId": k.get("releaseId"), "displayedAs": k["state"]},
               "customerEligibility": o["customerEligibility"],
               "scores": [{"measurement": s["measurement"], "displayedAs": s["measurement"], "source": s.get("source")} for s in o.get("scores") or []],
               "outputs": [{"lane": lane, "consumers": ["external.sector-ops", "platform.orchestrator"] + ([] if lane != "INTERNAL_OBSERVATION" else ["platform.scorer"]),
                            "knowledgeState": k["state"]}],
               "runs": [{"mode": "INTERNAL", "knowledgeState": k["state"], "outcome": io.get("lastExecutionResult") or "NOT_OBSERVED"}],
               "releaseReadiness": (b.get("statusLayers") or {}).get("operationalReadiness")}
        if "APPROVED_SCIENCE" in (o.get("executionModes") or []) and k["state"] != "APPROVED":
            out["runs"].append({"mode": "APPROVED_SCIENCE", "knowledgeState": k["state"], "outcome": "REFUSED"})
        brains.append(out)
    out = {"schemaVersion": "cortex.brain-operations-status/1", "generatedAt": doc.get("operationsAsOf") or doc.get("checkedAt"), "brains": brains}
    if isinstance(doc.get("executionControl"), dict):            # Cortex 2.7.0: ops-check reports FALSE_RUNNING if a Brain runs while PAUSED
        out["executionControl"] = {"state": doc["executionControl"].get("state"), "brains": doc["executionControl"].get("brains") or {}}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    st = convert(json.load(open(a.doc, encoding="utf-8")))
    open(a.out, "w", encoding="utf-8").write(json.dumps(st, indent=1) + "\n")
    print(f"wrote {a.out}: {len(st['brains'])} Brains")
    return 0


if __name__ == "__main__":
    sys.exit(main())
