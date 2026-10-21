"""Water Clarity's BrainCertSpec for BRAIN_CERT_KIT_V1: the declarative, Brain-specific structural truth. Domain science, goldens and input truth stay in the
Brain's own tests; the shared proofs live in tools/brain_certification."""
import copy

import clarity_support as S
from brain_cert_kit import BrainCertSpec, Rejection

_updates = {}


def _legacy_updates():
    if "u" not in _updates:
        flat, _, rc = S.real_run_updates()
        assert rc == 0
        _updates["u"] = flat
    return _updates["u"]


def artifact(n, generated_at, consumed, rerun):
    return S.build(_legacy_updates(), n=n, generated_at=generated_at, consumed=consumed).artifact


def changed_artifact(n, generated_at):
    u = copy.deepcopy(_legacy_updates())
    st = u["lakes/Guntersville_AL/states/waterClarity"]
    st["clarityFt"] = round(st["clarityFt"] + 0.5, 2)
    return S.build(u, n=n, generated_at=generated_at).artifact


SPEC = BrainCertSpec(
    brain_id="water-clarity", directory="water-clarity", release_lineage=tuple(S.pa.release_lineage().values()), repo_root=S.REPO, lifecycle="CALIBRATION", workspace_id="water-clarity",
    authorized_consumers=("ops", "sector-intelligence"),
    consumes=({"kind": "registry", "registry": "lakes", "contractId": "registry.lakes", "minVersion": "1.0.0", "requirement": "REQUIRED"},),
    providers=(),
    required_files=("brain.json", "BRAIN_OPERATING_CONTRACT.md", "README.md", "contracts/clarity-publication-v1.json", "contracts/INPUTS_V1.json", "runtime/run.py",
                    "runtime/clarity_brain.py", "runtime/publish_artifact.py", "runtime/catalog.json", "tests", "research/README.md", "research/GAPS.json", "deploy/deploy-job.sh"),
    unique_module_basenames=("clarity_brain.py",), legacy_pointer_dir="jobs/water-clarity-brain",
    allowed_runtime_ext=(".py", ".json"), research_files=("GAPS.json", "README.md"),
    contract_tokens=("## 4. OWNERSHIP", "## 5. NON-OWNERSHIP", "production clarity **number**", "Lake Registry", "Sector Ops owns all labels", "Publisher publication metadata",
                     "RA-20", "GCS_HTTP_LINEAGE_PLATFORM_DEBT", "GCS_WRITE_SEMANTICS_PLATFORM_DEBT"),
    bundle_id="clarity-publication-v1", contract_file="contracts/clarity-publication-v1.json", registry_schema_id="clarity-registry-v1", job_id="water-clarity-brain",
    plan_root_prefixes=("lakes/", "lakeFleet/", "snapshots/", "brains/water-clarity", "validation/water-clarity", "health/brains/water-clarity", "activity/", "sources/", "health/sources/"),
    extra_rejections=(Rejection("/lakes/Guntersville_AL/states/wind", "CROSS_DOMAIN_PATH"),
                      Rejection("/snapshots/Guntersville_AL/latest/waterClarity", "PLATFORM_DERIVED_PATH")),
    write_call_suffixes=("rtdb.update",),
    allowed_write_sites=frozenset({("run.py", "write", "rtdb.update"), ("run.py", "main", "rtdb.update")}),
    builder_module="runtime/publish_artifact.py",
    local_path_regex=r"/Users/|/home/[a-z]|\bDesktop/|Sector[ _]Research|Sector_Research_Data|~/|expanduser|SECTOR_RESEARCH_ROOT|water-clarity/(sources|datasets|analysis)",
    arch_findings=(("clarity_brain.py", 8),), baseline_entry_basenames=("clarity_brain.py",), score_baseline_substring="water-clarity=8.0/10",
    artifact_factory=artifact, changed_artifact_factory=changed_artifact,
)
