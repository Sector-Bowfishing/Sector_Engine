"""One Brain identity model (Cortex PL-11 / BR-07; architecture completion 2026-10-20).

The authority is `tools/architecture/stable_brain_ids.json` (locked machine ids, directory -> brainId) together with the registered packages
(`brains/*/brain.json`). Every other hand-kept list must agree with it or name its documented exception, so a drift fails here instead of in production:
  * the orchestrator control manifest, the Python key table (`keys.BRAINS`, which ownership uses) and its Swift mirror (`BrainPlatform.brains`)
    hold the locked ids plus exactly the not-yet-migrated Brains (Depth, Vegetation), with identical slots and snapshot fields in Python and Swift;
  * Python and Swift source ownership are identical; every source owner, provider acquisition owner and job owner is a known Brain (or the platform).
No generator is introduced: the registries stay where their readers expect them; this test is the consistency gate.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "jobs", "brain_platform"))
from sector_brain_platform import jobs as JOBS, keys as KEYS, ownership as OWN  # noqa: E402

UNMIGRATED = {"vegetation"}                                             # registered in the manifest, code only on its branch (not a locked id yet)
NON_BRAIN_OWNERS = {"brain-platform", "sector-engine"}                  # jobs.py owners that are platform components, not Brains


def _load(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return json.load(fh)


STABLE = _load("tools", "architecture", "stable_brain_ids.json")["directoryToBrainId"]
LOCKED = set(STABLE.values())
MANIFEST = set(_load("jobs", "brain_platform", "sector_brain_platform", "control_manifest.json")["brains"])
SWIFT_SRC = open(os.path.join(ROOT, "Sources", "SectorEngine", "Brain", "BrainPlatform.swift"), encoding="utf-8").read()
SWIFT_BRAINS = {m.group(1): (m.group(2), m.group(3)) for m in re.finditer(r'"([a-z-]+)": \("(\w+)", "(\w+)", "[^"]+"\)', SWIFT_SRC)}
CONTRACT_SRC = open(os.path.join(ROOT, "Sources", "SectorEngine", "Brain", "BrainContract.swift"), encoding="utf-8").read()
_OWNERS_LITERAL = CONTRACT_SRC.split("sourceOwners: [String: String] = [", 1)[1].split("\n    ]", 1)[0]
SWIFT_SOURCE_OWNERS = dict(re.findall(r'^\s+"([a-z0-9-]+)": "([a-z-]+)",', _OWNERS_LITERAL, re.M))


def test_registered_packages_are_exactly_the_locked_ids():
    registered = {}
    for d in sorted(os.listdir(os.path.join(ROOT, "brains"))):
        p = os.path.join(ROOT, "brains", d, "brain.json")
        if os.path.exists(p):
            registered[d] = _load("brains", d, "brain.json")["brainId"]
    assert registered == STABLE


def test_manifest_python_and_swift_hold_the_locked_ids_plus_the_unmigrated_brains():
    expected = LOCKED | UNMIGRATED
    assert MANIFEST == expected
    assert set(KEYS.BRAINS) == expected and set(OWN.BRAINS) == expected
    assert set(SWIFT_BRAINS) == expected


def test_python_and_swift_slots_and_snapshot_fields_are_identical():
    assert {b: (v[0], v[1]) for b, v in KEYS.BRAINS.items()} == SWIFT_BRAINS


def test_source_ownership_is_identical_in_python_and_swift_and_owned_by_known_brains():
    assert SWIFT_SOURCE_OWNERS == dict(OWN.SOURCE_OWNERS)
    assert set(OWN.SOURCE_OWNERS.values()) <= LOCKED


def test_every_job_and_provider_owner_is_a_known_brain_or_the_platform():
    assert {m["owner"] for m in JOBS.MANIFEST.values()} <= LOCKED | UNMIGRATED | NON_BRAIN_OWNERS
    providers = _load("providers", "PROVIDERS.json")["providers"]
    assert {p["acquisitionOwner"] for p in providers} <= LOCKED
    assert {c for p in providers for c in p["authorizedConsumers"]} <= LOCKED
