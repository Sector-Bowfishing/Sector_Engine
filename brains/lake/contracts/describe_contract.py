#!/usr/bin/env python3
"""Derive the Lake Brain's published-contract declaration from the Publisher registry (the authority), so the declaration can never drift from what the
Publisher enforces. The implementation is the shared BRAIN_CERT_KIT_V1 descriptor (tools/brain_certification); this file only declares the contract shape.

  PYTHONPATH=jobs/brain_platform python3 brains/lake/contracts/describe_contract.py            # print
  PYTHONPATH=jobs/brain_platform python3 brains/lake/contracts/describe_contract.py --check    # exit 1 if the JSON differs
  PYTHONPATH=jobs/brain_platform python3 brains/lake/contracts/describe_contract.py --write
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools", "brain_certification"))
from brain_cert_kit import ContractSpec, describe_contract, run_describe_cli  # noqa: E402

SPEC = ContractSpec(
    contract_dir=HERE, out_file="lake-publication-v1.json", bundle_id="lake-publication-v1", builder="brains/lake/runtime/publish_artifact.py",
    derived_from="jobs/brain_platform/sector_brain_platform/publisher/registry.py (lake_specs, lake_bundles)",
    status="SHADOW (Publisher Gate P); not wired into the job; the Swift job still writes through the Swift platform client until an approved cutover",
    section_fields=("families", "deleteFamilies", "deleteReasons", "volatileContract", "requiresRelease", "requiresFreshness", "allowedLifecycles", "projections"),
    extras={"registryChildren": ("registry", "LAKE_REGISTRY_CHILDREN", "children"), "healthDomainChildren": ("registry", "LAKE_HEALTH_DOMAIN_CHILDREN", "list"),
            "reservedChildren": ("registry", "BRAIN_NODE_OWNERS", "sortedkeys"), "volatileContract": ("volatile",),
            "writeSetSource": "the runner's recorded write set on deterministic inputs (tests/golden/*_run_updates.json, regenerated only by the Swift fixture test)",
            "freshness": "stale after lag + 3 x cadence per source (staleAfterHours 3 in the registry); the observation time is never replaced by a run time",
            "lineage": {"knowledgeRelease": "NONE (no versioned knowledge release)", "manifestRef": "NONE", "manifestSha256": "NONE",
                        "consumed": "not recorded by the Swift platform client: absent = unknown, never []"}})


def describe():
    return describe_contract(SPEC)


if __name__ == "__main__":
    sys.exit(run_describe_cli(SPEC, sys.argv[1:]))
