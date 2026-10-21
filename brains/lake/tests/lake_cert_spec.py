"""lake-brain's BrainCertSpec for BRAIN_CERT_KIT_V1: the declarative, Brain-specific structural truth. The runtime is Swift; the kit runs over the
runner's RECORDED write set (tests/golden/lake_run_updates.json, produced and drift-checked by the Swift fixture test) through the Python shadow builder
runtime/publish_artifact.py. Domain science stays in the Swift tests (tests/swift)."""
import copy
import json
import os
import uuid

import publish_artifact as pa
from brain_cert_kit import BrainCertSpec, Rejection

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FIXTURE = os.path.join(HERE, "golden", "lake_run_updates.json")
_u = {}


def run_updates():
    if "u" not in _u:
        with open(FIXTURE, encoding="utf-8") as fh:
            _u["u"] = json.load(fh)
    return _u["u"]


def uid(n):
    return str(uuid.UUID(int=n, version=4))


def artifact(n, generated_at, consumed, rerun):
    return pa.build_artifact(run_updates(), pa.BuildContext(generated_at, uid(n), "test@1"), consumed=consumed).artifact


def changed_artifact(n, generated_at):
    u = copy.deepcopy(run_updates())
    u["lakes/Guntersville_AL/states/lake"]["currentElevationFt"] = round(u["lakes/Guntersville_AL/states/lake"]["currentElevationFt"] + 0.5, 2)     # a real domain change
    return pa.build_artifact(u, pa.BuildContext(generated_at, uid(n), "test@1")).artifact


_BRAIN = json.load(open(os.path.join(REPO, "brains", "lake", "brain.json"), encoding="utf-8"))

SPEC = BrainCertSpec(
    brain_id="lake-brain", directory="lake", repo_root=REPO, lifecycle="CALIBRATION", workspace_id="lake-brain",
    authorized_consumers=("ops", "sector-intelligence", "depth", "vegetation"), runtime_kind="job",
    consumes=tuple(_BRAIN["consumes"]), providers=tuple(p["providerId"] for p in _BRAIN["providers"]),
    required_files=("brain.json", "BRAIN_OPERATING_CONTRACT.md", "README.md", "contracts/lake-publication-v1.json", "contracts/describe_contract.py",
                    "runtime/LakeBrain/LakeBrainRunner.swift", "runtime/LakeBrain/LakeLevelClassifier.swift", "runtime/LakeBrainJob/main.swift", "runtime/publish_artifact.py", "tests", "tests/golden/lake_run_updates.json",
                    "research/README.md", "deploy/deploy-job.sh"),
    unique_module_basenames=("LakeBrainRunner.swift", "LakeLevelClassifier.swift",), legacy_pointer_dir=None,
    allowed_runtime_ext=(".py", ".swift"), research_files=("README.md",),
    contract_tokens=("## 4. OWNERSHIP", "## 5. NON-OWNERSHIP", "Sector Intelligence"),
    bundle_id="lake-publication-v1", contract_file="contracts/lake-publication-v1.json", registry_schema_id="lake-registry-v1", job_id="lake-brain",
    plan_root_prefixes=("lakes/", "lakeFleet/", "snapshots/", "brains/lake-brain", "validation/lake-brain", "health/brains/lake-brain", "activity/", "sources/", "health/sources/"),
    extra_rejections=(Rejection("/lakes/Guntersville_AL/states/wind", "CROSS_DOMAIN_PATH"),
                      Rejection("/snapshots/Guntersville_AL/latest/lakeState", "PLATFORM_DERIVED_PATH")),
    write_call_suffixes=("rtdb.update",), allowed_write_sites=frozenset(),      # Python scope: the builder writes nothing (Swift writes: see README)
    builder_module="runtime/publish_artifact.py",
    arch_findings=tuple((e["path"].rsplit("/", 1)[1], e["invariant"]) for e in json.load(open(os.path.join(REPO, "tools", "architecture", "baseline",
                        "legacy_violations.json"), encoding="utf-8"))["entries"] if e["path"].startswith("brains/lake/")),
    baseline_entry_basenames=tuple(e["path"].rsplit("/", 1)[1] for e in json.load(open(os.path.join(REPO, "tools", "architecture", "baseline",
                                   "legacy_violations.json"), encoding="utf-8"))["entries"] if e["path"].startswith("brains/lake/")),
    score_baseline_substring=None,
    artifact_factory=artifact, changed_artifact_factory=changed_artifact,
    not_applicable={"P14": "the runtime's database writes are Swift (BrainStore.update through the Swift Brain platform client), which the kit's "
                            "Python write-site audit cannot parse; the Swift write set is pinned by BrainOwnership.check and tests/swift/LakePublicationFixtureTests.swift"},
)
