#!/usr/bin/env python3
"""Derive Wind's published-contract declaration from the Publisher registry (the authority), so the declaration can never drift from what the Publisher enforces.
The implementation is the shared BRAIN_CERT_KIT_V1 descriptor (tools/brain_certification); this file only declares Wind's contract shape.

  PYTHONPATH=jobs/brain_platform python3 brains/wind/contracts/describe_contract.py            # print
  PYTHONPATH=jobs/brain_platform python3 brains/wind/contracts/describe_contract.py --check    # exit 1 if wind-publication-v1.json differs
  PYTHONPATH=jobs/brain_platform python3 brains/wind/contracts/describe_contract.py --write
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools", "brain_certification"))
from brain_cert_kit import ContractSpec, describe_contract, run_describe_cli  # noqa: E402

SPEC = ContractSpec(
    contract_dir=HERE, out_file="wind-publication-v1.json", bundle_id="wind-publication-v1",
    builder="brains/wind/runtime/sector_wind/brain/artifact.py",
    derived_from="jobs/brain_platform/sector_brain_platform/publisher/registry.py (wind_specs, wind_bundles)",
    status="SHADOW (Publisher Gate P); not wired into the wind-hourly job; not a production contract until cutover",
    section_fields=("families", "deleteFamilies", "deleteReasons", "volatileContract"),
    extras={"baselineScopes": {"wind-lake-state-v1": ["lake-live", "lake-static", "fleet-readiness"]},
            "registryChildren": ("registry", "WIND_REGISTRY_CHILDREN", "children"),
            "reservedChildren": ("registry", "BRAIN_NODE_OWNERS", "sortedkeys"),
            "sourcesAcquired": ("registry", "_wind_sources", "callsorted"),
            "compatibilityProjections": ("registry", "WIND_PROJECTIONS", "projections")})


def describe():
    return describe_contract(SPEC)


if __name__ == "__main__":
    sys.exit(run_describe_cli(SPEC, sys.argv[1:]))
