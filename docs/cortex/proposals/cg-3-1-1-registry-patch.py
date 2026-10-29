#!/usr/bin/env python3
"""CG-3.1-1: the Cortex registry additions the Engine needs (proposal, applied by a Cortex maintenance session; Cortex is read-only in Engine sessions).

  python3 cg-3-1-1-registry-patch.py <path to firebase-data-contracts.json>      # idempotent; then `cortex.py seal <path>` and `cortex.py data-check`

(a) component readers (platform.*, framework.*, security.*) for families the Engine already reads; (b) the two platform health roots the Orchestrator writes; (c) the Orchestrator's publication-coordination
family (the record of what each Brain produced and what happened to it; written only by the Orchestrator, never a Brain intelligence path); (d) platform-authored activity events.
It changes no writer of any existing Brain-intelligence family and no Publisher target."""
import json
import sys

# component readers the Engine's code and manifests already declare (from `cortex.py data-check`); Brain-level reads (brain.wind on /sources and /scores, brain.water-clarity on /jobs ...) and
# the access lists are NOT added: those are owner decisions / scanner false positives (see CORTEX_GAPS CG-3.1-1)
ADD_READERS = {
 "fam.activity": [
  "platform.brain-platform-library"
 ],
 "fam.brains": [
  "framework.architecture-gates",
  "framework.cert-kit-v1",
  "platform.brain-platform-library",
  "platform.orchestrator",
  "platform.scorer"
 ],
 "fam.brains-wind-scores": [
  "platform.brain-platform-library"
 ],
 "fam.control-beta": [
  "platform.brain-platform-library"
 ],
 "fam.control-engineering-status": [
  "platform.brain-platform-library"
 ],
 "fam.control-execution-control": [
  "platform.brain-platform-library"
 ],
 "fam.control-fleet": [
  "platform.brain-platform-library"
 ],
 "fam.control-health-v1": [
  "framework.cert-kit-v1",
  "platform.brain-platform-library"
 ],
 "fam.control-orchestrator": [
  "platform.brain-platform-library"
 ],
 "fam.control-orchestrator-v1": [
  "framework.cert-kit-v1",
  "platform.brain-platform-library"
 ],
 "fam.control-overview": [
  "platform.brain-platform-library"
 ],
 "fam.control-shadow-lane": [
  "platform.brain-platform-library"
 ],
 "fam.engine-score-alias": [
  "framework.cert-kit-v1",
  "platform.brain-platform-library",
  "platform.publisher-live",
  "security.rtdb-target-rules"
 ],
 "fam.health-brains": [
  "platform.brain-platform-library",
  "platform.orchestrator"
 ],
 "fam.health-jobs": [
  "framework.cert-kit-v1",
  "platform.brain-platform-library"
 ],
 "fam.health-sources": [
  "platform.brain-platform-library"
 ],
 "fam.jobs": [
  "framework.cert-kit-v1",
  "platform.brain-platform-library"
 ],
 "fam.lake-brain-node": [
  "platform.brain-platform-library"
 ],
 "fam.lake-profiles": [
  "platform.brain-platform-library"
 ],
 "fam.lake-species-presence": [
  "platform.brain-platform-library",
  "platform.publisher-shadow"
 ],
 "fam.lake-states": [
  "framework.architecture-gates",
  "platform.brain-platform-library"
 ],
 "fam.lake-validation": [
  "platform.brain-platform-library",
  "platform.orchestrator"
 ],
 "fam.lakefleet": [
  "platform.brain-platform-library",
  "platform.orchestrator"
 ],
 "fam.lakefleet-last-updated": [
  "platform.brain-platform-library"
 ],
 "fam.ops-preferences": [
  "platform.brain-platform-library"
 ],
 "fam.scores": [
  "framework.brain-factory",
  "framework.cert-kit-v1",
  "platform.brain-platform-library",
  "platform.orchestrator"
 ],
 "fam.snapshots": [
  "platform.brain-platform-library",
  "platform.orchestrator"
 ],
 "fam.snapshots-generatedat": [
  "platform.brain-platform-library"
 ],
 "fam.snapshots-snapshotversion": [
  "platform.brain-platform-library"
 ],
 "fam.sources": [
  "platform.brain-platform-library",
  "platform.orchestrator"
 ],
 "fam.species": [
  "platform.brain-platform-library"
 ],
 "fam.validation": [
  "platform.brain-platform-library",
  "platform.orchestrator",
  "platform.scorer"
 ],
 "fam.validation-wind-scores": [
  "platform.brain-platform-library"
 ]
}


def fam(fid, pattern, scope, writer, notes, readers):
    return {"id": fid, "pattern": pattern, "domain": "health-control-jobs", "scope": scope, "status": "NOT_VERIFIED", "writer": writer, "readers": readers, "schemaRef": "NOT_VERIFIED",
            "freshness": "NOT_VERIFIED", "freshnessModel": {"kind": "WRITE_TIME"}, "retention": "NOT_VERIFIED", "classification": "INTERNAL", "label": "PLANNED",
            "evidencePaths": [], "evidence": [{"source": "engine-audit", "section": "3"}], "notes": notes + " Status stays NOT_VERIFIED until an evidence source documents the path (the registry requires grounded evidence for CANONICAL).", "lane": "INTERNAL"}


READ = ["external.sector-ops", "platform.publisher-shadow", "verification.cross-component"]
NEW = [fam("fam.health-engine", "/health/engine", "global", "platform.orchestrator", "Engine service health observed and written by the Orchestrator (operational health, not Brain intelligence).", READ),
       fam("fam.health-rtdb", "/health/rtdb", "global", "platform.orchestrator", "Database connectivity health observed and written by the Orchestrator.", READ),
       fam("fam.control-publication", "/control/publicationV1/{brainId}", "per-brain", "platform.orchestrator",
           "PL-19 publication coordination: per Brain the last runs, artifact ids/digests, publication outcome (PUBLISHED/SKIPPED/REJECTED/FAILED) and reason. Operational record owned by the Orchestrator; never Brain intelligence, never written by a Brain or the Publisher.", READ)]


def main(path):
    d = json.load(open(path, encoding="utf-8"))
    byid = {f["id"]: f for f in d["families"]}
    for fid, rs in ADD_READERS.items():
        f = byid[fid]
        f["readers"] = f["readers"] + [r for r in rs if r not in f["readers"]]
    for f in NEW:
        if f["id"] not in byid:
            d["families"].append(f)
    act = byid["fam.activity"]
    act = byid["fam.activity"]
    if "platform-authored" not in (act.get("notes") or ""):
        act["notes"] = (act.get("notes") or "") + " Platform-authored events (score.changed, run.*) carry a platform event id and are owned by platform.orchestrator (the scorer emits score.changed inside the Orchestrator cycle); Brain events embed the Brain id and are owned by that Brain. platform-authored"
    json.dump(d, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    open(path, "a").write("\n")


if __name__ == "__main__":
    main(sys.argv[1])
