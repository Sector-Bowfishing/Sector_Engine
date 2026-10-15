#!/usr/bin/env python3
"""Derive Wind's published-contract declaration from the Publisher registry (the authority), so the
declaration can never drift from what the Publisher enforces.

  PYTHONPATH=jobs/brain_platform python3 brains/wind/contracts/describe_contract.py            # print
  PYTHONPATH=jobs/brain_platform python3 brains/wind/contracts/describe_contract.py --check    # exit 1 if wind-publication-v1.json differs
  PYTHONPATH=jobs/brain_platform python3 brains/wind/contracts/describe_contract.py --write
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "wind-publication-v1.json")


def describe():
    from sector_brain_platform.publisher import registry as R
    fam = lambda f: {"pattern": f.pattern, "status": f.status}
    sections = []
    for s in R.wind_specs():
        sections.append({"schemaId": s.schema_id, "families": [fam(f) for f in s.families],
                         "deleteFamilies": [f.pattern for f in s.delete_families], "deleteReasons": list(s.delete_reasons),
                         "volatileContract": s.volatile.id if s.volatile else None})
    [bundle] = R.wind_bundles()
    return {
        "contractId": bundle.bundle_id, "brainId": bundle.brain_id, "version": "1.0.0",
        "envelope": "publish-artifact-v2", "fingerprint": "sector-semantic-fingerprint-v2",
        "derivedFrom": "jobs/brain_platform/sector_brain_platform/publisher/registry.py (wind_specs, wind_bundles)",
        "builder": "brains/wind/runtime/sector_wind/brain/artifact.py",
        "baselineScopes": {"wind-lake-state-v1": ["lake-live", "lake-static", "fleet-readiness"]},
        "sections": sorted(sections, key=lambda x: x["schemaId"]),
        "registryChildren": {k: list(v) for k, v in R.WIND_REGISTRY_CHILDREN.items()},
        "reservedChildren": sorted(R.BRAIN_NODE_OWNERS),
        "sourcesAcquired": sorted(R._wind_sources()),
        "compatibilityProjections": [{"id": p.id, "source": p.source, "target": p.target} for p in R.WIND_PROJECTIONS],
        "status": "SHADOW (Publisher Gate P); not wired into the wind-hourly job; not a production contract until cutover",
    }


def main(argv):
    d = describe()
    text = json.dumps(d, indent=2, sort_keys=True) + "\n"
    if "--write" in argv:
        open(OUT, "w").write(text)
        return 0
    if "--check" in argv:
        ok = os.path.exists(OUT) and open(OUT).read() == text
        print("wind-publication-v1.json matches the Publisher registry" if ok else "wind-publication-v1.json is stale: run --write")
        return 0 if ok else 1
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
