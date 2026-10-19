#!/usr/bin/env python3
"""Derive Water Clarity's published-contract declaration from the Publisher registry (the authority), so the declaration can never drift from what the Publisher enforces.

  PYTHONPATH=jobs/brain_platform python3 brains/water-clarity/contracts/describe_contract.py            # print
  PYTHONPATH=jobs/brain_platform python3 brains/water-clarity/contracts/describe_contract.py --check    # exit 1 if clarity-publication-v1.json differs
  PYTHONPATH=jobs/brain_platform python3 brains/water-clarity/contracts/describe_contract.py --write
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "clarity-publication-v1.json")


def describe():
    from sector_brain_platform.publisher import registry as R
    fam = lambda f: {"pattern": f.pattern, "status": f.status}      # noqa: E731
    reg = R.default_registry()
    sections = []
    for sid in R.CLARITY_SCHEMAS:
        s = reg.spec(sid)
        sections.append({"schemaId": s.schema_id, "families": [fam(f) for f in s.families], "deleteFamilies": [f.pattern for f in s.delete_families],
                         "deleteReasons": list(s.delete_reasons), "volatileContract": s.volatile.id, "requiresRelease": s.require_release,
                         "requiresFreshness": s.require_freshness, "allowedLifecycles": list(s.allowed_lifecycles),
                         "projections": [{"id": p.id, "kind": p.kind, "source": p.source, "target": p.target, "valueFrom": p.value_from, "owner": p.owner} for p in s.projections]})
    bundle = reg.bundle(R.CLARITY_BUNDLE)
    return {
        "contractId": bundle.bundle_id, "brainId": bundle.brain_id, "version": "1.0.0",
        "envelope": "publish-artifact-v2", "fingerprint": "sector-semantic-fingerprint-v2",
        "derivedFrom": "jobs/brain_platform/sector_brain_platform/publisher/registry.py (clarity_specs, clarity_bundles)",
        "builder": "brains/water-clarity/runtime/publish_artifact.py",
        "sections": sorted(sections, key=lambda x: x["schemaId"]),
        "registryChildren": {k: list(v) for k, v in R.CLARITY_REGISTRY_CHILDREN.items()},
        "healthDomainChildren": list(R.CLARITY_HEALTH_DOMAIN_CHILDREN),
        "slotErrorChildren": list(R.CLARITY_SLOT_ERROR_CHILDREN),
        "reservedChildren": sorted(R.BRAIN_NODE_OWNERS),
        "volatileContract": reg.spec(R.CLARITY_SCHEMAS[0]).volatile.describe(),
        "freshness": {"model": "TIME", "threshold": "staleAfterHours (26) applied to the Engine evaluation time the estimate restates",
                      "evidenceObservedAt": "newest satellite SCENE observation time across lakes; gauge reading times are UNKNOWN in the Engine payload and never substituted",
                      "inputGeneratedAt": "newest Engine /conditions evaluation time (the input product's generation time)",
                      "brainGeneratedAt": "lineage.generatedAt (this run); publication time is the Publisher's",
                      "neverUsed": "lastSuccessfulRun / lastSuccess (process history, not evidence freshness)"},
        "lineage": {"knowledgeRelease": "NONE (no canonical versioned release or manifest; the catalog digest is part of inputFingerprint)", "manifestRef": "NONE", "manifestSha256": "NONE",
                    "consumed": "ACTUAL RTDB reads recorded by the platform client when available; GCS/HTTP reads are NOT recorded (platform debt); absent = unknown, never []"},
        "status": "SHADOW (Publisher Gate P); not wired into the job write path; not a production contract until cutover",
    }


def main(argv):
    d = describe()
    text = json.dumps(d, indent=2, sort_keys=True) + "\n"
    if "--write" in argv:
        open(OUT, "w").write(text)
        return 0
    if "--check" in argv:
        ok = os.path.exists(OUT) and open(OUT).read() == text
        print("clarity-publication-v1.json matches the Publisher registry" if ok else "clarity-publication-v1.json is stale: run --write")
        return 0 if ok else 1
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
