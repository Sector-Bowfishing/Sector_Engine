"""Fish's BrainCertSpec for BRAIN_CERT_KIT_V1: declarative structural truth only. Species science, the golden and species-identity tests stay in the Fish suite."""
import datetime as dt

import fish_support as S
import biological_brain as bb
from brain_cert_kit import BrainCertSpec, Rejection

BASELINE = None


def _baseline():
    global BASELINE
    if BASELINE is None:
        BASELINE = S.updates_for(S.make_bundle())["/brains/biological-state"]
    return BASELINE


def artifact(n, generated_at, consumed, rerun):
    if rerun:                                # a later run on UNCHANGED inputs after the first was published
        return S.build(n=n, now=S.NOW + dt.timedelta(days=2), generated_at=generated_at, published=_baseline(), consumed=consumed).artifact
    return S.build(n=n, generated_at=generated_at, consumed=consumed).artifact


def changed_artifact(n, generated_at):
    p = S.T.synthetic_profile()
    p["knowledge"]["domains"]["dayNightMovement"].update(score=2, status="SCORED")
    p["knowledge"]["overallExact"] = round(sum(d["score"] * d["weight"] for d in p["knowledge"]["domains"].values()) / 100, 2)
    p["knowledge"]["overallRounded"] = bb.round_half(p["knowledge"]["overallExact"])
    return S.build(S.make_bundle([p, S.T.not_assessed()], research_version="0000-00-00.2"), n=n, now=S.NOW + dt.timedelta(days=2), generated_at=generated_at).artifact


SPEC = BrainCertSpec(
    brain_id="biological-state", directory="fish", repo_root=S.REPO, lifecycle="PROFILED", workspace_id="fish-brain", authorized_consumers=("ops", "sector-intelligence"),
    consumes=(), providers=(), runtime_kind="in-process",
    required_files=("brain.json", "BRAIN_OPERATING_CONTRACT.md", "README.md", "contracts/fish-publication-v1.json", "runtime/run.py", "runtime/biological_brain.py",
                    "runtime/publish_artifact.py", "tests", "research/README.md", "research/GAPS.json"),
    unique_module_basenames=("biological_brain.py", "bio_state.py", "capability.py", "movement_outlook.py"), legacy_pointer_dir="jobs/biological-brain",
    allowed_runtime_ext=(".py", ".json", ".md"), research_files=("CHARTER.json", "GAPS.json", "README.md"),
    contract_tokens=("species identity", "legality", "Lake Brain", "Species Registry"),
    bundle_id="fish-publication-v1", contract_file="contracts/fish-publication-v1.json", registry_schema_id="fish-registry-v1", job_id="biological-brain",
    plan_root_prefixes=("species/", "brains/biological-state", "validation/biological-state", "health/brains/biological-state", "activity/"),
    extra_rejections=(Rejection("/lakes/Guntersville_AL/speciesPresence", "CROSS_DOMAIN_PATH"), Rejection("/speciesProfiles/example_fish", "CROSS_DOMAIN_PATH"),
                      Rejection("/species/example_fish/profile", "PATH_NOT_AUTHORIZED"), Rejection("/lakeFleet/Guntersville_AL/slots/biology", "PATH_NOT_AUTHORIZED")),
    write_call_suffixes=("rtdb.update",), allowed_write_sites=frozenset({("run.py", "main", "rtdb.update")}),
    builder_module="runtime/publish_artifact.py",
    local_path_regex=r"/Users/|/home/[a-z]|\bDesktop/|Sector[ _]Research|Sector_Research_Data|~/|expanduser|SECTOR_RESEARCH_ROOT|fish-brain/(sources|datasets|analysis)",
    local_path_exempt_markers=("LEAK_TEXT", "concatenated"),
    arch_findings=(("biological_brain.py", 8), ("brain_platform.py", 8)), baseline_entry_basenames=("biological_brain.py", "brain_platform.py"),
    score_baseline_substring=None, artifact_factory=artifact, changed_artifact_factory=changed_artifact, release_lineage=None,
)
