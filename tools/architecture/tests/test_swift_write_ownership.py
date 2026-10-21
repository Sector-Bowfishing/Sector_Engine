"""Swift Brain write ownership (Kit V1 P14 is Python-only and NOT_APPLICABLE for Lake and Water Temperature; this is its Swift equivalent).

For the Swift Brain runtimes (brains/lake, brains/water-temperature) this gate pins, as data:
  1. every database / archive write call site (file, call) with its count, so a new write path cannot appear unreviewed;
  2. every BrainStore the jobs construct carries the Brain's id, so the shared write guard ownership-checks every update;
  3. the shared stores (RTDBRestStore, LocalDirectoryStore) run BrainWriteGuard.validate (BrainOwnership.check) before any write;
  4. the runners' recorded write sets (golden fixtures, regenerated only by the Swift fixture tests) are entirely Brain-owned under the
     platform ownership table (Python and Swift ownership are proven identical by test_brain_identity_consistency.py).
Static and local only.
"""
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "jobs", "brain_platform"))
from sector_brain_platform import ownership as OWN  # noqa: E402

WRITE = re.compile(r"\b(store|archive|writer|primary)\.(update|delete|write)\(")
EXPECTED = {
    "brains/lake/runtime": {
        ("LakeBrain/LakeBrainRunner.swift", "store.update("): 3,
        ("LakeBrain/LakeBrainRunner.swift", "archive.write("): 2,
        ("LakeBrain/LakePredictionLedger.swift", "archive.write("): 1,
        ("LakeBrain/LakeBrainArchive.swift", "primary.write("): 1,          # LayeredLakeBrainArchive: writes only to its primary (never the seed)
        ("LakeBrain/LakeBrainArchive.swift", "writer.update("): 1,          # ReadThroughDryRunStore -> its ownership-checked LocalDirectoryStore
        ("LakeBrain/LakeBrainArchive.swift", "writer.delete("): 1,
    },
    "brains/water-temperature/runtime": {
        ("WaterTemperatureBrain/WaterTemperatureBrainRunner.swift", "store.update("): 4,
    },
}
BRAIN_IDS = {"brains/lake": "lake-brain", "brains/water-temperature": "water-temp"}
GOLDEN = {"lake-brain": "brains/lake/tests/golden/lake_run_updates.json", "water-temp": "brains/water-temperature/tests/golden/water_temp_run_updates.json"}


def _swift(root):
    for dp, _, fs in os.walk(os.path.join(ROOT, root)):
        for f in fs:
            if f.endswith(".swift"):
                p = os.path.join(dp, f)
                yield os.path.relpath(p, os.path.join(ROOT, root)), open(p, encoding="utf-8").read()


def _code(src):
    return "\n".join(line.split("//", 1)[0] for line in src.splitlines())          # comments never count as call sites


def test_swift_write_call_sites_are_pinned():
    for root, expected in EXPECTED.items():
        found = Counter()
        for rel, src in _swift(root):
            for m in WRITE.finditer(_code(src)):
                found[(rel, m.group(0))] += 1
        assert dict(found) == expected, f"{root}: write call sites changed (review, then update the pinned table): {dict(found)}"


def test_every_store_a_swift_job_constructs_is_ownership_checked():
    for pkg, brain in BRAIN_IDS.items():
        for rel, src in _swift(pkg + "/runtime"):
            for line in _code(src).splitlines():
                if re.search(r"\b(RTDBRestStore|LocalDirectoryStore)\(", line):
                    assert "brainId:" in line, f"{pkg}/runtime/{rel}: a store constructed without the Brain id skips the ownership guard: {line.strip()}"


def test_the_shared_swift_stores_ownership_check_every_update():
    src = _code(open(os.path.join(ROOT, "Sources", "SectorEngine", "Brain", "BrainRTDBStore.swift"), encoding="utf-8").read())
    assert "try BrainOwnership.check(paths, brainId: brainId)" in src
    for cls in ("RTDBRestStore", "LocalDirectoryStore"):
        body = src[src.index(f"class {cls}"):]
        upd = body[body.index("func update("):][:400]
        assert "BrainWriteGuard.validate(paths, brainId: brainId)" in upd, f"{cls}.update does not run the ownership guard"


def test_the_recorded_swift_write_sets_are_entirely_brain_owned():
    for brain, rel in GOLDEN.items():
        updates = json.load(open(os.path.join(ROOT, rel), encoding="utf-8"))
        assert updates, rel
        bad = [p for p in updates if not OWN.path_allowed(brain, p)]
        assert not bad, f"{brain}: recorded writes outside its ownership: {bad[:5]}"
