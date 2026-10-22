"""Lake provider requirements match their roles (health-plane honesty, 2026-10-22).

Undeclared requirements fail closed to REQUIRED, which made the health plane report Lake FAILED because history-only and fleet/candidate-scope
providers had no health record, although the deployed pilot scope never reads them. History and fleet/candidate providers are OPTIONAL;
the pilot primaries stay REQUIRED. The roles come from the jobs manifest (sector_brain_platform.jobs.MANIFEST["lake-brain"]["inputs"])."""
import json
import os
import re

from sector_brain_platform.jobs import MANIFEST

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN = json.load(open(os.path.join(HERE, "..", "brain.json"), encoding="utf-8"))


def _roles():
    roles = {}
    for s in MANIFEST["lake-brain"]["inputs"]:
        m = re.match(r"^([a-z0-9-]+)(?: \((.+)\))?$", s)
        if m and not s.startswith(("registry:", "archive:")):
            roles[m.group(1)] = m.group(2) or "primary"
    return roles


def test_every_provider_declares_its_requirement():
    assert all(p.get("requirement") in ("REQUIRED", "OPTIONAL") for p in BRAIN["providers"])


def test_requirement_matches_the_provider_role():
    roles = _roles()
    for p in BRAIN["providers"]:
        role = roles.get(p["providerId"])
        assert role is not None, f"{p['providerId']} has no role in the jobs manifest"
        want = "OPTIONAL" if role in ("history", "fleet/candidate scopes") else "REQUIRED"
        assert p["requirement"] == want, (p["providerId"], role, p["requirement"])
