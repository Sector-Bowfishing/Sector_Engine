"""Regenerate runtime/water_domain_registry.py (the packaged PROJECTION) from the Species Registry file. Never hand-edit the output.

    python3 gen_water_domain_projection.py          # rewrite
    python3 gen_water_domain_projection.py --check  # exit 1 when the projection is stale
"""
import json
import pprint
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "platform" / "registries" / "species" / "species_water_domains.json"
OUT = Path(__file__).resolve().parents[1] / "water_domain_registry.py"


def render() -> str:
    doc = json.loads(SRC.read_text())
    body = pprint.pformat(doc, width=160, sort_dicts=False).replace("None", "None")
    return ('"""GENERATED from platform/registries/species/species_water_domains.json by tools/gen_water_domain_projection.py. DO NOT EDIT.\n\n'
            'The orchestrator image ships only runtime + platform, so the Fish runtime carries this projection; tests assert it equals the registry."""\n\n'
            f"REGISTRY = {body}\n")


if __name__ == "__main__":
    text = render()
    if "--check" in sys.argv:
        sys.exit(0 if OUT.read_text() == text else 1)
    OUT.write_text(text)
