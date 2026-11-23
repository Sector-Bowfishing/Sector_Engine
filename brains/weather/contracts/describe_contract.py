#!/usr/bin/env python3
"""Derive Weather's published-contract declaration from the Publisher registry (the authority), so the declaration can never drift from what the
Publisher enforces. The implementation is the shared BRAIN_CERT_KIT_V1 descriptor (tools/brain_certification); this file only declares the contract shape.
The per-lake state document itself is specified in weather-state-v1.md / weather-state-v1.schema.json.

  PYTHONPATH=jobs/brain_platform python3 brains/weather/contracts/describe_contract.py            # print
  PYTHONPATH=jobs/brain_platform python3 brains/weather/contracts/describe_contract.py --check    # exit 1 if the JSON differs
  PYTHONPATH=jobs/brain_platform python3 brains/weather/contracts/describe_contract.py --write
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools", "brain_certification"))
from brain_cert_kit import ContractSpec, describe_contract, run_describe_cli  # noqa: E402

SPEC = ContractSpec(
    contract_dir=HERE, out_file="weather-publication-v1.json", bundle_id="weather-publication-v1",
    builder="brains/weather/runtime/sector_weather/publish.py",
    derived_from="jobs/brain_platform/sector_brain_platform/publisher/registry.py (weather_specs, weather_bundles)",
    status="SHADOW (contract only, not cut over): Weather is CALIBRATION and registered DISABLED; the live writer is gated (run.py --write refuses without an APPROVED knowledge release and WEATHER_WRITE_APPROVED=1); not a production contract",
    section_fields=("families", "deleteFamilies", "deleteReasons", "volatileContract", "requiresRelease", "requiresFreshness", "allowedLifecycles"),
    extras={"registryChildren": ("registry", "WEATHER_REGISTRY_CHILDREN", "children"), "healthDomainChildren": ("registry", "WEATHER_HEALTH_DOMAIN_CHILDREN", "list"),
            "reservedChildren": ("registry", "BRAIN_NODE_OWNERS", "sortedkeys"), "volatileContract": ("volatile",),
            "stateSchema": "brains/weather/contracts/weather-state-v1.schema.json (sector-brain-weather-state-v1); meaning: weather-state-v1.md",
            "snapshot": "none: Weather writes no /snapshots path (no legacy reader exists)",
            "lineage": {"knowledgeRelease": "the verified Weather knowledge release id (runtime/knowledge/knowledge-release.json: the pre-stated thresholds)",
                        "thresholdsVersion": "weather-change-thresholds-v1 (pre-stated 2026-11-22), carried in every state"}})


def describe():
    return describe_contract(SPEC)


if __name__ == "__main__":
    sys.exit(run_describe_cli(SPEC, sys.argv[1:]))
