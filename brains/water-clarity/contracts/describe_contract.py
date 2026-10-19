#!/usr/bin/env python3
"""Derive Water Clarity's published-contract declaration from the Publisher registry (the authority), so the declaration can never drift from what the Publisher enforces.
The implementation is the shared BRAIN_CERT_KIT_V1 descriptor (tools/brain_certification); this file only declares Clarity's contract shape.

  PYTHONPATH=jobs/brain_platform python3 brains/water-clarity/contracts/describe_contract.py            # print
  PYTHONPATH=jobs/brain_platform python3 brains/water-clarity/contracts/describe_contract.py --check    # exit 1 if clarity-publication-v1.json differs
  PYTHONPATH=jobs/brain_platform python3 brains/water-clarity/contracts/describe_contract.py --write
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools", "brain_certification"))
from brain_cert_kit import ContractSpec, describe_contract, run_describe_cli  # noqa: E402

SPEC = ContractSpec(
    contract_dir=HERE, out_file="clarity-publication-v1.json", bundle_id="clarity-publication-v1", builder="brains/water-clarity/runtime/publish_artifact.py",
    derived_from="jobs/brain_platform/sector_brain_platform/publisher/registry.py (clarity_specs, clarity_bundles)",
    status="SHADOW (Publisher Gate P); not wired into the job write path; not a production contract until cutover",
    section_fields=("families", "deleteFamilies", "deleteReasons", "volatileContract", "requiresRelease", "requiresFreshness", "allowedLifecycles", "projections"),
    extras={"registryChildren": ("registry", "CLARITY_REGISTRY_CHILDREN", "children"), "healthDomainChildren": ("registry", "CLARITY_HEALTH_DOMAIN_CHILDREN", "list"),
            "slotErrorChildren": ("registry", "CLARITY_SLOT_ERROR_CHILDREN", "list"), "reservedChildren": ("registry", "BRAIN_NODE_OWNERS", "sortedkeys"),
            "volatileContract": ("volatile",),
            "freshness": {"model": "TIME", "threshold": "staleAfterHours (26) applied to the Engine evaluation time the estimate restates",
                          "evidenceObservedAt": "newest satellite SCENE observation time across lakes; gauge reading times are UNKNOWN in the Engine payload and never substituted",
                          "inputGeneratedAt": "newest Engine /conditions evaluation time (the input product's generation time)",
                          "brainGeneratedAt": "lineage.generatedAt (this run); publication time is the Publisher's",
                          "neverUsed": "lastSuccessfulRun / lastSuccess (process history, not evidence freshness)"},
            "lineage": {"knowledgeRelease": "NONE (no canonical versioned release or manifest; the catalog digest is part of inputFingerprint)", "manifestRef": "NONE", "manifestSha256": "NONE",
                        "consumed": "ACTUAL RTDB reads recorded by the platform client when available; GCS/HTTP reads are NOT recorded (platform debt); absent = unknown, never []"}})


def describe():
    return describe_contract(SPEC)


if __name__ == "__main__":
    sys.exit(run_describe_cli(SPEC, sys.argv[1:]))
