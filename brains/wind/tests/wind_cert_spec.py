"""Wind's BrainCertSpec for BRAIN_CERT_KIT_V1: declarative structural truth only. Wind science, Gate-P equivalence tests and the package/staging gates stay in Wind's suites."""
import copy
import os
import tempfile

import test_brain as TB
from sector_wind.brain import artifact as A
from sector_wind.brain import contract as C
from sector_wind.brain.publish import publish
from sector_wind.brain.writer import DryRunWriter
from sector_wind.ingest import verified_release
from brain_cert_kit import BrainCertSpec, Rejection

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
_cache = {}


def _patches():
    if "p" not in _cache:
        st = TB.make_store(tempfile.mkdtemp())
        w = DryRunWriter()
        rep = publish(st, TB.CFG, w, now=TB.NOW, run_summary={"runAt": C.iso(TB.NOW), "errors": [], "seconds": 90}, directory=TB.DIRECTORY)
        assert rep["ok"], rep["errors"]
        _cache["p"] = w.patches
    return copy.deepcopy(_cache["p"])


def _lineage():
    if "l" not in _cache:
        from sector_brain_platform.knowledge_release import lineage_triple
        _cache["l"] = lineage_triple(verified_release())          # the packaged release the runtime verifies on load (BR-11 e)
    return _cache["l"]


def _ctx(n, generated_at):
    rel, ref, digest = _lineage()
    return A.BuildContext(generated_at=generated_at, execution_id=f"{1000 + n:08x}-0000-4000-8000-{1000 + n:012x}", code_version="abc123def456",
                          knowledge_release=rel, manifest_ref=ref, manifest_sha256=digest)


def artifact(n, generated_at, consumed, rerun):
    return A.build_artifacts(_patches(), _ctx(n, generated_at), consumed=list(consumed or ())).artifact


def changed_artifact(n, generated_at):
    pp = _patches()
    for p in pp:
        for k, v in p.items():
            if k.endswith("/states/wind") and isinstance(v, dict) and "observationTime" in v:
                v["observationTime"] = "2026-10-13T06:00:00Z"
    return A.build_artifacts(pp, _ctx(n, generated_at)).artifact


SPEC = BrainCertSpec(
    brain_id="wind", directory="wind", repo_root=REPO, lifecycle="CALIBRATION", workspace_id="wind-brain", authorized_consumers=("ops", "sector-intelligence", "biological-state"),
    consumes=({"kind": "registry", "registry": "lakes", "contractId": "registry.lakes", "minVersion": "1.0.0", "requirement": "REQUIRED"},),
    providers=("noaa-nbm-v5", "noaa-rtma-ru", "iem-metar-wind"), providers_match_registry_sources=True,
    required_files=("brain.json", "BRAIN_OPERATING_CONTRACT.md", "README.md", "contracts/wind-publication-v1.json", "runtime/main.py", "runtime/sector_wind/brain/artifact.py",
                    "tests", "research/README.md", "deploy/deploy-job.sh"),
    unique_module_basenames=("grib.py", "bowfishing.py"), legacy_pointer_dir="jobs/wind-hourly",
    allowed_runtime_ext=(".py", ".json"), research_files=None,
    contract_required_terms=("bowfisher",), contract_forbidden_terms=("angler",),
    bundle_id="wind-publication-v1", contract_file="contracts/wind-publication-v1.json", registry_schema_id="wind-registry-v1", job_id="wind-hourly",
    plan_root_prefixes=("lakes/", "lakeFleet/", "snapshots/", "brains/wind", "validation/wind", "health/brains/wind", "activity/", "sources/", "health/sources/"),
    extra_rejections=(Rejection("/lakes/Guntersville_AL/states/waterClarity", "CROSS_DOMAIN_PATH"), Rejection("/snapshots/Guntersville_AL/latest/wind", "PLATFORM_DERIVED_PATH")),
    forbidden_imports=("firebase_admin", "requests", "pyrebase"),     # google.cloud is allowed: Wind archives to its OWN private bucket (store.py); that is storage, not a Brain-RTDB door
    write_call_suffixes=("_db.update",), allowed_write_sites=frozenset({("writer.py", "patch", "self._db.update")}),
    builder_module="runtime/sector_wind/brain/artifact.py",
    local_path_regex=r"/Users/|~/Desktop|~/Library|Library/Caches|Sector Research|Sector_Research_Data|Desktop/Development|iOS/sector-wind",
    arch_findings=(("profile.py", 8), ("writer.py", 8)), baseline_entry_basenames=("profile.py", "writer.py"), baseline_carried_from_required=False,
    score_baseline_substring="wind=3.3/10", artifact_factory=artifact, changed_artifact_factory=changed_artifact,
    consumed_absent_when_unknown=False,
    release_lineage=_lineage(),    # Wind's builder attests provider consumption from the lake states' recorded sources (domain test stays in test_publish_artifact.py)
)
