"""Declared legacy direct writes (Cortex 2.2 FD-01/FD-03; Firebase remediation 2026-10-21).

`brain.json` `publishes[0].pathFamilies` is the Publisher contract (Kit P05). `legacyDirectWrites` declares the paths the current direct writer also
writes but the Brain does not author at cutover. Every Brain's own suite proves the declaration equals its runtime write set
(`brains/*/tests/test_declared_write_set.py`); this gate proves each declaration is owned, disjoint from the contract and resolvable:
  * PUBLISHER_COMPATIBILITY_PROJECTION -> a CompatibilityProjection of that Brain's bundle with exactly that target
  * PLATFORM_OWNED_STOP_WRITING / ORCHESTRATOR_DERIVED -> a classification row with that id in the Brain's publish artifact or the platform
    compatibility table (publisher/compat.py)
"""
import glob
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "jobs", "brain_platform"))
from sector_brain_platform import declared_writes as D, ownership as OWN  # noqa: E402
from sector_brain_platform.publisher import registry as REG  # noqa: E402

MANIFESTS = sorted(glob.glob(os.path.join(ROOT, "brains", "*", "brain.json")))
LAKE_WRITERS = {"water-clarity", "wind", "lake-brain", "water-temp", "depth", "vegetation", "sector-intelligence"}


def _load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _concrete(path, brain_id):
    return (path.replace("{k}", "Lake_X_ZZ").replace("{job}", "x-job").replace("{id}", "x").replace("{child}", "status")
            .replace("{event}", f"20261021T000000Z-{brain_id}-1"))


def _projections():
    return {pr.id: pr for name in dir(REG) if name.endswith("_PROJECTIONS") for pr in getattr(REG, name)}


def _classification_sources(brain_dir):
    srcs = glob.glob(os.path.join(brain_dir, "runtime", "**", "publish_artifact.py"), recursive=True) + \
        glob.glob(os.path.join(brain_dir, "runtime", "**", "artifact.py"), recursive=True) + \
        [os.path.join(ROOT, "jobs", "brain_platform", "sector_brain_platform", "publisher", "compat.py")]
    return "\n".join(open(p, encoding="utf-8").read() for p in srcs)


@pytest.mark.parametrize("path", MANIFESTS, ids=lambda p: os.path.basename(os.path.dirname(p)))
def test_legacy_direct_writes_are_owned_disjoint_and_resolvable(path):
    b = _load(path)
    brain_id = b["brainId"]
    assert D.problems(b) == []
    fams, legacy = D.families(b)
    if brain_id in LAKE_WRITERS:
        assert legacy, f"{brain_id} writes per-lake identity fields; its brain.json must declare them"
    projections = _projections()
    text = _classification_sources(os.path.dirname(path))
    for e in legacy:
        assert OWN.path_allowed(brain_id, _concrete(e["path"], brain_id)), f"{brain_id} is not allowed to write {e['path']}"
        if e["disposition"] == "PUBLISHER_COMPATIBILITY_PROJECTION":
            pr = projections.get(e["ref"])
            assert pr is not None, f"{e['ref']}: no such Publisher projection"
            assert pr.target == e["path"], f"{e['ref']} targets {pr.target}, declared {e['path']}"
        else:
            assert f'"{e["ref"]}"' in text, f"{e['ref']}: no classification row in the publish artifact or publisher/compat.py"


def test_snapshot_writes_are_declared_by_every_brain_that_writes_a_snapshot_field():
    """The audit's S-3: a Brain that writes /snapshots/{k}/latest/<field> declares it (contract family or legacy write)."""
    from sector_brain_platform.keys import BRAINS
    for p in MANIFESTS:
        b = _load(p)
        if b["brainId"] not in LAKE_WRITERS:
            continue
        fams, legacy = D.families(b)
        declared = set(fams) | {e["path"] for e in legacy}
        field = BRAINS[b["brainId"]][1]
        assert f"/snapshots/{{k}}/latest/{field}" in declared, b["brainId"]
        assert f"/snapshots/{{k}}/latest/brainVersions/{b['brainId']}" in declared, b["brainId"]
        assert "/snapshots/{k}/latest/lakeId" in declared, b["brainId"]
