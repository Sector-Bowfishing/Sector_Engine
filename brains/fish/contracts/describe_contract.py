#!/usr/bin/env python3
"""Derive Fish's published-contract declaration from the Publisher registry (the authority), so the declaration can never drift from what the Publisher enforces.
The implementation is the shared BRAIN_CERT_KIT_V1 descriptor (tools/brain_certification); this file only declares Fish's contract shape.

  PYTHONPATH=jobs/brain_platform python3 brains/fish/contracts/describe_contract.py            # print
  PYTHONPATH=jobs/brain_platform python3 brains/fish/contracts/describe_contract.py --check    # exit 1 if fish-publication-v1.json differs
  PYTHONPATH=jobs/brain_platform python3 brains/fish/contracts/describe_contract.py --write
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools", "brain_certification"))
from brain_cert_kit import ContractSpec, describe_contract, run_describe_cli  # noqa: E402

SPEC = ContractSpec(
    contract_dir=HERE, out_file="fish-publication-v1.json", bundle_id="fish-publication-v1", builder="brains/fish/runtime/publish_artifact.py",
    derived_from="jobs/brain_platform/sector_brain_platform/publisher/registry.py (fish_specs, fish_bundles)",
    status="SHADOW (Publisher Gate P); not wired into the in-process job; not a production contract until cutover",
    section_fields=("families", "deleteFamilies", "deleteReasons", "volatileContract", "requiresRelease", "requiresFreshness", "allowedLifecycles"),
    extras={"registryChildren": ("registry", "FISH_REGISTRY_CHILDREN", "children"), "optionalRegistryChildren": ("registry", "FISH_OPTIONAL_CHILDREN", "list"),
            "healthDomainChildren": ("registry", "FISH_HEALTH_DOMAIN_CHILDREN", "list"), "reservedChildren": ("registry", "BRAIN_NODE_OWNERS", "sortedkeys"),
            "volatileContract": ("volatile",),
            "lineage": {"knowledgeRelease": "researchVersion of the verified canonical bundle", "manifestRef": "bundle manifest location (runtime value, private)",
                        "manifestSha256": "sha256 of the verified manifest", "freshness": "not supplied: species knowledge is version-driven; evidence freshness stays UNKNOWN",
                        "consumed": "ACTUAL reads recorded by the platform client when available; absent = unknown"}})


def describe():
    return describe_contract(SPEC)


if __name__ == "__main__":
    sys.exit(run_describe_cli(SPEC, sys.argv[1:]))
