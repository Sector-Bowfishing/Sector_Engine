"""Moon and Night Light's BrainCertSpec for BRAIN_CERT_KIT_V1: declarative structural truth only. The astronomy and the darkness rule stay in the
Brain's own tests (test_moon_spec_vectors, test_usno_crosscheck, test_night, test_darkness)."""
import json

import moon_support as S
from brain_cert_kit import BrainCertSpec, Rejection
from moon_brain import lakes as L


def artifact(n, generated_at, consumed, rerun):
    return S.build(S.run_updates(), n=n, generated_at=generated_at, consumed=consumed).artifact          # same inputs; only the execution identity varies


def changed_artifact(n, generated_at):
    cloud = {"Guntersville|AL": S.run_state("2026-11-22T23:00:00Z", 95)}
    return S.build(S.run_updates(weather=cloud), n=n, generated_at=generated_at).artifact                # cloud input arrived: a real input change


SPEC = BrainCertSpec(
    brain_id="moon", directory="moon", repo_root=S.REPO, lifecycle="CALIBRATION", workspace_id="moon",
    authorized_consumers=("ops", "sector-intelligence"), runtime_kind="job",
    consumes=tuple(json.load(open(S.REPO + "/brains/moon/brain.json"))["consumes"]),
    providers=(),
    required_files=("brain.json", "BRAIN_OPERATING_CONTRACT.md", "README.md", "contracts/moon-publication-v1.json", "contracts/moon-night-light-v1.json",
                    "runtime/run.py", "runtime/requirements.txt", "runtime/moon_brain/lakes.py", "runtime/moon_brain/publish_artifact.py",
                    "runtime/knowledge/knowledge-release.json", "tests", "research/README.md", "research/GAPS.json"),
    unique_module_basenames=("ephemeris.py", "darkness.py"), legacy_pointer_dir=None,
    allowed_runtime_ext=(".py", ".json", ".txt"), research_files=None,
    contract_tokens=("## 4. OWNERSHIP", "## 5. NON-OWNERSHIP", "The Moon and Night Light Brain has no official score", "There is no live writer",
                     "DARKNESS_RULE_V1", "MOON_ONLY"),
    bundle_id="moon-publication-v1", contract_file="contracts/moon-publication-v1.json", registry_schema_id="moon-registry-v1",
    job_id="moon-brain",
    plan_root_prefixes=("lakes/", "lakeFleet/", "snapshots/", "brains/moon", "validation/moon", "health/brains/moon"),
    extra_rejections=(Rejection("/lakes/Guntersville_AL/states/wind", "CROSS_DOMAIN_PATH"), Rejection("/scores/moon", "CROSS_DOMAIN_PATH")),
    write_call_suffixes=("_store.update",), allowed_write_sites=frozenset({("writer.py", "patch", "self._store.update")}),
    builder_module="runtime/moon_brain/publish_artifact.py",
    has_score=False, score_baseline_substring=None,           # no Engine readiness score: the shared scorer has no Moon entry
    release_lineage=L.lineage(),
    artifact_factory=artifact, changed_artifact_factory=changed_artifact,
)
