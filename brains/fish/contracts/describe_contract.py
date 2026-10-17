#!/usr/bin/env python3
"""Derive Fish's published-contract declaration from the Publisher registry (the authority), so the declaration can never drift from what the Publisher enforces.

  PYTHONPATH=jobs/brain_platform python3 brains/fish/contracts/describe_contract.py            # print
  PYTHONPATH=jobs/brain_platform python3 brains/fish/contracts/describe_contract.py --check    # exit 1 if fish-publication-v1.json differs
  PYTHONPATH=jobs/brain_platform python3 brains/fish/contracts/describe_contract.py --write
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fish-publication-v1.json")


def describe():
    from sector_brain_platform.publisher import registry as R
    fam = lambda f: {"pattern": f.pattern, "status": f.status}      # noqa: E731
    reg = R.default_registry()
    sections = []
    for sid in R.FISH_SCHEMAS:
        s = reg.spec(sid)
        sections.append({"schemaId": s.schema_id, "families": [fam(f) for f in s.families], "deleteFamilies": [f.pattern for f in s.delete_families],
                         "deleteReasons": list(s.delete_reasons), "volatileContract": s.volatile.id, "requiresRelease": s.require_release,
                         "requiresFreshness": s.require_freshness, "allowedLifecycles": list(s.allowed_lifecycles)})
    bundle = reg.bundle(R.FISH_BUNDLE)
    return {
        "contractId": bundle.bundle_id, "brainId": bundle.brain_id, "version": "1.0.0",
        "envelope": "publish-artifact-v2", "fingerprint": "sector-semantic-fingerprint-v2",
        "derivedFrom": "jobs/brain_platform/sector_brain_platform/publisher/registry.py (fish_specs, fish_bundles)",
        "builder": "brains/fish/runtime/publish_artifact.py",
        "sections": sorted(sections, key=lambda x: x["schemaId"]),
        "registryChildren": {k: list(v) for k, v in R.FISH_REGISTRY_CHILDREN.items()},
        "optionalRegistryChildren": list(R.FISH_OPTIONAL_CHILDREN),
        "healthDomainChildren": list(R.FISH_HEALTH_DOMAIN_CHILDREN),
        "reservedChildren": sorted(R.BRAIN_NODE_OWNERS),
        "volatileContract": reg.spec(R.FISH_SCHEMAS[0]).volatile.describe(),
        "lineage": {"knowledgeRelease": "researchVersion of the verified canonical bundle", "manifestRef": "bundle manifest location (runtime value, private)",
                    "manifestSha256": "sha256 of the verified manifest", "freshness": "not supplied: species knowledge is version-driven; evidence freshness stays UNKNOWN",
                    "consumed": "ACTUAL reads recorded by the platform client when available; absent = unknown"},
        "status": "SHADOW (Publisher Gate P); not wired into the in-process job; not a production contract until cutover",
    }


def main(argv):
    d = describe()
    text = json.dumps(d, indent=2, sort_keys=True) + "\n"
    if "--write" in argv:
        open(OUT, "w").write(text)
        return 0
    if "--check" in argv:
        ok = os.path.exists(OUT) and open(OUT).read() == text
        print("fish-publication-v1.json matches the Publisher registry" if ok else "fish-publication-v1.json is stale: run --write")
        return 0 if ok else 1
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
