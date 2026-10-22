"""Vegetation's BrainCertSpec for BRAIN_CERT_KIT_V1: declarative structural truth only. Vegetation science stays in the Brain's own tests."""
import json

import vegetation_support as S
from brain_cert_kit import BrainCertSpec, Rejection


def artifact(n, generated_at, consumed, rerun):
    return S.build(S.run_updates(), n=n, generated_at=generated_at, consumed=consumed).artifact          # same inputs; only the execution identity varies


def changed_artifact(n, generated_at):
    return S.build(S.run_updates(drop_agency_lake="Apopka|FL"), n=n, generated_at=generated_at).artifact   # an agency record changed: a real input change


SPEC = BrainCertSpec(
    brain_id="vegetation", directory="vegetation", repo_root=S.REPO, lifecycle="SHADOW", workspace_id="vegetation",
    authorized_consumers=("ops", "sector-intelligence"), runtime_kind="job",
    consumes=tuple(json.load(open(S.REPO + "/brains/vegetation/brain.json"))["consumes"]),
    providers=(),
    required_files=("brain.json", "BRAIN_OPERATING_CONTRACT.md", "README.md", "contracts/vegetation-publication-v1.json", "runtime/run.py",
                    "runtime/requirements.txt", "runtime/vegetation_brain/knowledge.py", "runtime/vegetation_brain/publish_artifact.py",
                    "runtime/knowledge/knowledge-release.json", "tests", "research/README.md", "research/GAPS.json"),
    unique_module_basenames=("observer.py", "language.py"), legacy_pointer_dir=None,
    allowed_runtime_ext=(".py", ".json", ".txt"), research_files=None,
    contract_tokens=("## 4. OWNERSHIP", "## 5. NON-OWNERSHIP", "Vegetation has no official score", "There is no live writer",
                     "BLOCKED_AWAITING_APPROVED_RELEASE"),
    bundle_id="vegetation-publication-v1", contract_file="contracts/vegetation-publication-v1.json", registry_schema_id="vegetation-registry-v1",
    job_id="vegetation-brain",
    plan_root_prefixes=("lakes/", "lakeFleet/", "snapshots/", "brains/vegetation", "validation/vegetation", "health/brains/vegetation", "activity/"),
    extra_rejections=(Rejection("/lakes/Guntersville_AL/states/depth", "CROSS_DOMAIN_PATH"), Rejection("/scores/vegetation", "CROSS_DOMAIN_PATH")),
    write_call_suffixes=("_store.update",), allowed_write_sites=frozenset({("writer.py", "patch", "self._store.update")}),
    builder_module="runtime/vegetation_brain/publish_artifact.py",
    has_score=False, score_baseline_substring=None,           # Vegetation has NO score: the shared scorer has no Vegetation entry
    release_lineage=S.knowledge().lineage(),
    artifact_factory=artifact, changed_artifact_factory=changed_artifact,
)
