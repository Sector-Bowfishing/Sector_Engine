#!/usr/bin/env python3
"""Derive Depth's published-contract declaration from the Publisher registry (the authority), so the declaration can never drift from what the
Publisher enforces. The implementation is the shared BRAIN_CERT_KIT_V1 descriptor (tools/brain_certification); this file only declares the contract shape.

  PYTHONPATH=jobs/brain_platform python3 brains/depth/contracts/describe_contract.py            # print
  PYTHONPATH=jobs/brain_platform python3 brains/depth/contracts/describe_contract.py --check    # exit 1 if the JSON differs
  PYTHONPATH=jobs/brain_platform python3 brains/depth/contracts/describe_contract.py --write
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools", "brain_certification"))
from brain_cert_kit import ContractSpec, describe_contract, run_describe_cli  # noqa: E402

SPEC = ContractSpec(
    contract_dir=HERE, out_file="depth-publication-v1.json", bundle_id="depth-publication-v1",
    builder="brains/depth/runtime/depth_brain/publish_artifact.py",
    derived_from="jobs/brain_platform/sector_brain_platform/publisher/registry.py (depth_specs, depth_bundles)",
    status="SHADOW (Publisher Gate P); not wired into the job; the job publishes only from an APPROVED knowledge release; not a production contract",
    section_fields=("families", "deleteFamilies", "deleteReasons", "volatileContract", "requiresRelease", "requiresFreshness", "allowedLifecycles"),
    extras={"registryChildren": ("registry", "DEPTH_REGISTRY_CHILDREN", "children"), "healthDomainChildren": ("registry", "DEPTH_HEALTH_DOMAIN_CHILDREN", "list"),
            "reservedChildren": ("registry", "BRAIN_NODE_OWNERS", "sortedkeys"), "volatileContract": ("volatile",),
            "snapshot": "the snapshot field and its brainVersion are Brain-authored for published lakes (no Publisher COPY projection)",
            "lineage": {"knowledgeRelease": "the verified Depth knowledge release id (runtime/knowledge/knowledge-release.json)",
                        "manifestRef": "image:knowledge-release.json", "manifestSha256": "the release digest (sha256)",
                        "consumed": "ACTUAL RTDB reads recorded by the platform client when available; absent = unknown, never []"}})


def describe():
    return describe_contract(SPEC)


if __name__ == "__main__":
    sys.exit(run_describe_cli(SPEC, sys.argv[1:]))
