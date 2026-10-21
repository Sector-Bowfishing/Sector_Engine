"""Cortex 2.1 standing memory checks, cross-Brain (BR-10, BR-11, BR-16, BR-18, PL-13; Cortex 2.1 adoption 2026-10-20).

Every registered Brain package declares where its approved operational knowledge lives at runtime (`brain.json` `knowledge`), and this gate keeps
the declaration true:
  1. store and owner: every package declares its stores; the owner is the Brain; research data is never a runtime fallback;
  2. developer-machine scan: Brain runtime, deploy and shared platform code name no developer-machine path, private research root, Claude session
     file or Sector Pulse host (guard regexes that FORBID those paths are the documented exceptions);
  3. release identity: every PACKAGED_IN_IMAGE release verifies (id + digest) and is staged into the image that runs it;
  4. memory-unavailable behaviour: every declared memory test file exists (the tests themselves run in each Brain's suite);
  5. separation: release manifests list only runtime files (no research/, docs/ or tests/ path);
  6. Pulse independence: no runtime or deploy code targets Sector Pulse, a Mac or localhost as an execution host.
Static and local only: no network, no bucket, no RTDB.
"""
import json
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "jobs", "brain_platform"))
from sector_brain_platform import knowledge_release as K  # noqa: E402

BRAINS = sorted(d for d in os.listdir(os.path.join(ROOT, "brains"))
                if not d.startswith("_") and os.path.isfile(os.path.join(ROOT, "brains", d, "brain.json")))

# Where the packaged release is staged into the image that actually runs the Brain (job image or the orchestrator's in-process image).
STAGING = {"wind": ("brains/wind/deploy/deploy-job.sh", "brains/wind/deploy/Dockerfile"),
           "water-clarity": ("brains/water-clarity/deploy/deploy-job.sh", "brains/water-clarity/deploy/Dockerfile"),
           "sector-intelligence": ("jobs/brain-orchestrator/deploy-job.sh",),
           "depth": ()}                       # no image and no executor (control manifest executionTarget kind none): nothing to stage

SCAN_ROOTS = [os.path.join("brains", b, sub) for b in BRAINS for sub in ("runtime", "deploy")] + [
    os.path.join("jobs", "brain_platform", "sector_brain_platform"), os.path.join("jobs", "brain-orchestrator"), os.path.join("Sources", "SectorEngine"), "Dockerfile"]
SCAN_EXT = (".py", ".swift", ".sh", ".json", ".yaml", ".yml")
DEV_MACHINE = re.compile(r"/Users/|~/Desktop|~/Library|/Volumes/|Desktop/Development|Sector Research|Sector_Research_Data|\.claude/projects|Mac ?mini|macmini", re.I)
PULSE_HOST = re.compile(r"Sector ?Pulse|sector-pulse|sector_pulse|localhost|127\.0\.0\.1", re.I)
# Lines that name those strings only to forbid or describe them (guards and documented local-only tools), never to read from them.
EXCEPTIONS = {
    ("brains/fish/runtime/capability_run.py", "Sector Pulse / Mac mini / developer"),     # local research entry point; writes LOCAL files only, not in any job
    ("brains/fish/runtime/tools/audit_bundle.py", "LEAK_TEXT"),                           # leak guard (denylist)
    ("jobs/brain_platform/sector_brain_platform/wind_measurements.py", "_LOCAL = re.compile"),   # guard: refuses local paths
    ("jobs/brain_platform/sector_brain_platform/score_explanation.py", "_PRIVATE = re.compile"),  # guard: redacts private paths
}


def _brain(b):
    with open(os.path.join(ROOT, "brains", b, "brain.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _files():
    for r in SCAN_ROOTS:
        full = os.path.join(ROOT, r)
        if os.path.isfile(full):
            yield r
            continue
        for dp, dns, fns in os.walk(full):
            dns[:] = [d for d in dns if d not in ("__pycache__", "tests", "out", "stage", ".build")]
            for fn in fns:
                if fn.endswith(SCAN_EXT) or fn == "Dockerfile":
                    yield os.path.relpath(os.path.join(dp, fn), ROOT)


def test_every_brain_declares_its_approved_memory_owned_by_itself_with_no_research_fallback():
    assert BRAINS == ["depth", "fish", "lake", "sector-intelligence", "water-clarity", "water-temperature", "wind"]
    for b in BRAINS:
        bj = _brain(b)
        k = bj.get("knowledge")
        assert k, f"{b}: brain.json declares no knowledge stores (Cortex BR-10/11)"
        assert k["researchFallback"] is False
        assert k["stores"], b
        for s in k["stores"]:
            assert s["owner"] == bj["brainId"], f"{b}/{s['id']}: memory owned by {s['owner']}"
            assert not DEV_MACHINE.search(s.get("location", "")), f"{b}/{s['id']}: developer-machine location"


def test_declared_memory_tests_exist():
    for b in BRAINS:
        for t in _brain(b)["knowledge"]["tests"]:
            assert os.path.exists(os.path.join(ROOT, t)), f"{b}: declared memory test {t} is missing"


@pytest.mark.parametrize("b", ["depth", "sector-intelligence", "water-clarity", "wind"])
def test_packaged_releases_verify_list_only_runtime_files_and_are_staged_into_the_running_image(b):
    stores = [s for s in _brain(b)["knowledge"]["stores"] if s["store"] == "PACKAGED_IN_IMAGE"]
    assert len(stores) == 1
    mpath = stores[0]["location"]
    rel = K.load_release(os.path.join(ROOT, os.path.dirname(mpath)), _brain(b)["brainId"])
    assert rel["releaseDigest"].startswith("sha256:") and rel["store"] == "PACKAGED_IN_IMAGE"
    for f in rel["files"]:
        assert not re.match(r"(research|docs|tests)/", f) and "/research/" not in f, f"{b}: release lists a non-runtime file {f}"
    for p in STAGING[b]:
        assert K.MANIFEST in open(os.path.join(ROOT, p), encoding="utf-8").read(), f"{b}: {p} does not stage {K.MANIFEST}"


def test_every_packaged_release_in_the_repo_is_declared_by_its_brain():
    found = []
    for dp, dns, fns in os.walk(os.path.join(ROOT, "brains")):
        dns[:] = [d for d in dns if d not in ("__pycache__", ".build")]
        if K.MANIFEST in fns:
            found.append(os.path.relpath(os.path.join(dp, K.MANIFEST), ROOT))
    declared = [s["location"] for b in BRAINS for s in _brain(b)["knowledge"]["stores"] if s["store"] == "PACKAGED_IN_IMAGE"]
    assert sorted(found) == sorted(declared)


def test_runtime_and_deploy_code_has_no_developer_machine_or_pulse_dependency():
    bad = []
    for rel in _files():
        try:
            lines = open(os.path.join(ROOT, rel), encoding="utf-8").read().splitlines()
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(lines, 1):
            if not (DEV_MACHINE.search(line) or PULSE_HOST.search(line)):
                continue
            if any(rel == f and needle in line for f, needle in EXCEPTIONS):
                continue
            if rel.startswith("Sources/") and "localhost" in line:
                continue                    # the Engine server's local-development note, not a Brain runtime
            bad.append(f"{rel}:{i}: {line.strip()[:120]}")
    assert not bad, "runtime/deploy code depends on a developer machine or Sector Pulse:\n" + "\n".join(bad)


def test_the_scan_is_not_vacuous():
    files = set(_files())
    for must in ("brains/wind/runtime/sector_wind/ingest.py", "brains/lake/runtime/LakeBrainJob/main.swift", "brains/water-clarity/deploy/deploy-job.sh",
                 "jobs/brain-orchestrator/orchestrate.py", "jobs/brain_platform/sector_brain_platform/knowledge_release.py"):
        assert must in files, must
