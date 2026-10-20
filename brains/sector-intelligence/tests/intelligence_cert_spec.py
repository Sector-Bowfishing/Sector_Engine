"""Sector Intelligence's BrainCertSpec for BRAIN_CERT_KIT_V1: the declarative, Brain-specific structural truth. Synthesis behaviour stays in the Brain's own
tests; the shared proofs live in tools/brain_certification."""
import intelligence_support as S
from brain_cert_kit import BrainCertSpec, Rejection

_updates = {}


def _run():
    if "u" not in _updates:
        _updates["u"] = S.run_updates()
    return _updates["u"]


def artifact(n, generated_at, consumed, rerun):
    return S.build(_run(), n=n, generated_at=generated_at, consumed=consumed).artifact


def changed_artifact(n, generated_at):
    def bump_wind(ups):
        ups["wind"]["registry"]["version"] = "1.1"            # an upstream Brain published a new version: a real input change
    return S.build(S.run_updates(mutate_upstream=bump_wind), n=n, generated_at=generated_at).artifact


SPEC = BrainCertSpec(
    brain_id="sector-intelligence", directory="sector-intelligence", repo_root=S.REPO, lifecycle="CALIBRATION", workspace_id="sector-intelligence",
    authorized_consumers=("ops",), runtime_kind="in-process",
    consumes=tuple(__import__("json").load(open(S.REPO + "/brains/sector-intelligence/brain.json"))["consumes"]),
    providers=(),
    required_files=("brain.json", "BRAIN_OPERATING_CONTRACT.md", "README.md", "contracts/sector-intelligence-publication-v1.json", "runtime/run.py",
                    "runtime/sector_intelligence_brain.py", "runtime/evaluation.py", "runtime/orchestration.py", "runtime/publish_artifact.py", "runtime/catalog.json",
                    "tests", "research/README.md"),
    unique_module_basenames=("sector_intelligence_brain.py", "evaluation.py"), legacy_pointer_dir="jobs/sector-intelligence-brain",
    allowed_runtime_ext=(".py", ".json"), research_files=("README.md",),
    contract_tokens=("## 4. OWNERSHIP", "## 5. NON-OWNERSHIP", "no rating, score or recommendation", "must not silently substitute for a missing specialist"),
    bundle_id="sector-intelligence-publication-v1", contract_file="contracts/sector-intelligence-publication-v1.json", registry_schema_id="intelligence-registry-v1",
    job_id="sector-intelligence-brain",
    plan_root_prefixes=("lakes/", "lakeFleet/", "snapshots/", "brains/sector-intelligence", "validation/sector-intelligence", "health/brains/sector-intelligence", "activity/"),
    extra_rejections=(Rejection("/lakes/Guntersville_AL/states/wind", "CROSS_DOMAIN_PATH"), Rejection("/snapshots/Guntersville_AL/latest/wind", "CROSS_DOMAIN_PATH")),
    write_call_suffixes=("rtdb.update",), allowed_write_sites=frozenset({("run.py", "main", "rtdb.update")}),
    builder_module="runtime/publish_artifact.py",
    arch_findings=(("sector_intelligence_brain.py", 8), ("brain_platform.py", 8)), baseline_entry_basenames=("brain_platform.py", "sector_intelligence_brain.py"),
    score_baseline_substring=None,
    artifact_factory=artifact, changed_artifact_factory=changed_artifact,
)
