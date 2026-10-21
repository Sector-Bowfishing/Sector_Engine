"""Depth's BrainCertSpec for BRAIN_CERT_KIT_V1: declarative structural truth only. Depth science stays in the Brain's own tests."""
import json

import depth_support as S
from brain_cert_kit import BrainCertSpec, Rejection


def artifact(n, generated_at, consumed, rerun):
    return S.build(S.run_updates(), n=n, generated_at=generated_at, consumed=consumed).artifact          # same inputs; only the execution identity varies


def changed_artifact(n, generated_at):
    return S.build(S.run_updates(elev_offset=-0.4), n=n, generated_at=generated_at).artifact     # a new Lake observation: a real input change


SPEC = BrainCertSpec(
    brain_id="depth", directory="depth", repo_root=S.REPO, lifecycle="PROFILED", workspace_id="depth",
    authorized_consumers=("ops", "sector-intelligence"), runtime_kind="in-process",
    consumes=tuple(json.load(open(S.REPO + "/brains/depth/brain.json"))["consumes"]),
    providers=(),
    required_files=("brain.json", "BRAIN_OPERATING_CONTRACT.md", "README.md", "contracts/depth-publication-v1.json", "runtime/run.py",
                    "runtime/depth_brain/knowledge.py", "runtime/depth_brain/publish_artifact.py", "runtime/knowledge/knowledge-release.json",
                    "tests", "research/README.md", "research/GAPS.json"),
    unique_module_basenames=("shift.py", "rating.py", "zones.py"), legacy_pointer_dir=None,
    allowed_runtime_ext=(".py", ".json"), research_files=None,
    contract_tokens=("## 4. OWNERSHIP", "## 5. NON-OWNERSHIP", "Depth has no official score", "BLOCKED_AWAITING_APPROVED_RELEASE"),
    bundle_id="depth-publication-v1", contract_file="contracts/depth-publication-v1.json", registry_schema_id="depth-registry-v1", job_id="depth-brain",
    plan_root_prefixes=("lakes/", "lakeFleet/", "snapshots/", "brains/depth", "validation/depth", "health/brains/depth", "activity/"),
    extra_rejections=(Rejection("/lakes/Guntersville_AL/states/lake", "CROSS_DOMAIN_PATH"), Rejection("/scores/depth", "CROSS_DOMAIN_PATH")),
    write_call_suffixes=("_db.update",), allowed_write_sites=frozenset({("writer.py", "patch", "self._db.update")}),
    builder_module="runtime/depth_brain/publish_artifact.py",
    has_score=False, score_baseline_substring=None,          # Depth has NO score: the shared scorer has no Depth entry
    release_lineage=S.knowledge().lineage(),
    artifact_factory=artifact, changed_artifact_factory=changed_artifact,
)
