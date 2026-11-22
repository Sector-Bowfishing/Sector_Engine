"""Generation's BrainCertSpec for BRAIN_CERT_KIT_V1: declarative structural truth only. Source parsing and assembly stay in the Brain's own tests."""
import json

import generation_support as S
from brain_cert_kit import BrainCertSpec, Rejection
from generation_brain.fixtures import fixture_transport
from generation_brain.http import Response


def artifact(n, generated_at, consumed, rerun):
    return S.build(S.run_updates(), n=n, generated_at=generated_at, consumed=consumed).artifact          # same inputs; only the execution identity varies


def _jumped_release():
    """TVA publishes a new hour of release (a real input change): the latest discharge row moves from 19,500 to 25,000 cfs."""
    base = fixture_transport(S.FIXTURES)

    def t(url, headers, timeout):
        r = base(url, headers, timeout)
        if "observed-data-48-hours/GVDA1" in url:
            rows = json.loads(r.body)
            rows[-1]["AverageHourlyDischarge"] = "25,000"
            return Response(r.status, json.dumps(rows).encode())
        return r
    return t


def changed_artifact(n, generated_at):
    return S.build(S.run_updates(transport=_jumped_release()), n=n, generated_at=generated_at).artifact


SPEC = BrainCertSpec(
    brain_id="generation", directory="generation", repo_root=S.REPO, lifecycle="CALIBRATION", workspace_id="generation",
    authorized_consumers=("ops", "sector-intelligence"), runtime_kind="job",
    consumes=tuple(json.load(open(S.REPO + "/brains/generation/brain.json"))["consumes"]),
    providers=("swpa-generation-schedule", "tva-generation-schedule", "usace-cwms-release", "usbr-rise-release", "usgs-waterdata-discharge"),
    required_files=("brain.json", "BRAIN_OPERATING_CONTRACT.md", "README.md", "contracts/generation-publication-v1.json",
                    "contracts/generation-dam-state-v1.schema.json", "runtime/run.py", "runtime/generation_brain/knowledge.py",
                    "runtime/generation_brain/publish_artifact.py", "runtime/knowledge/knowledge-release.json", "tests", "research/README.md",
                    "research/GAPS.json", "research/CHARTER.json"),
    unique_module_basenames=("assess.py",), legacy_pointer_dir=None,
    allowed_runtime_ext=(".py", ".json"), research_files=None,
    contract_tokens=("## 4. OWNERSHIP", "## 5. NON-OWNERSHIP", "Generation has no score", "BLOCKED_AWAITING_APPROVED_RELEASE",
                     "never derives units or discharge from megawatts"),
    bundle_id="generation-publication-v1", contract_file="contracts/generation-publication-v1.json", registry_schema_id="generation-registry-v1",
    job_id="generation-brain",
    plan_root_prefixes=("lakes/", "lakeFleet/", "snapshots/", "brains/generation", "validation/generation", "health/brains/generation", "activity/"),
    extra_rejections=(Rejection("/lakes/Guntersville_AL/states/lake", "CROSS_DOMAIN_PATH"), Rejection("/scores/generation", "CROSS_DOMAIN_PATH")),
    write_call_suffixes=("_db.update",), allowed_write_sites=frozenset({("writer.py", "patch", "self._db.update")}),
    builder_module="runtime/generation_brain/publish_artifact.py",
    has_score=False, score_baseline_substring=None,          # Generation has NO score: the shared scorer has no Generation entry
    release_lineage=S.knowledge().lineage(),
    artifact_factory=artifact, changed_artifact_factory=changed_artifact,
)
