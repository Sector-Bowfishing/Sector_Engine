"""Weather's BrainCertSpec for BRAIN_CERT_KIT_V1: declarative structural truth only. Weather science stays in the Brain's own tests."""
import json

import weather_cert_support as S
from brain_cert_kit import BrainCertSpec, Rejection


def artifact(n, generated_at, consumed, rerun):
    return S.build(S.run_updates(), n=n, generated_at=generated_at, consumed=consumed).artifact          # same inputs; only the execution identity varies


def changed_artifact(n, generated_at):
    return S.build(S.run_updates(lakes=("Champlain|VT",)), n=n, generated_at=generated_at).artifact     # a lake left the run: a real input change


BJ = json.load(open(S.REPO + "/brains/weather/brain.json"))
SPEC = BrainCertSpec(
    brain_id="weather", directory="weather", repo_root=S.REPO, lifecycle="CALIBRATION", workspace_id="weather-brain",
    authorized_consumers=tuple(BJ["authorizedConsumers"]), runtime_kind="job", cutover_status="NOT_STARTED",
    consumes=tuple(BJ["consumes"]), providers=tuple(p["providerId"] for p in BJ["providers"]),
    required_files=("brain.json", "BRAIN_OPERATING_CONTRACT.md", "README.md", "contracts/weather-publication-v1.json", "contracts/weather-state-v1.md",
                    "contracts/weather-state-v1.schema.json", "runtime/run.py", "runtime/requirements.txt", "runtime/sector_weather/knowledge.py",
                    "runtime/sector_weather/publish_artifact.py", "runtime/knowledge/knowledge-release.json", "tests", "research/README.md",
                    "research/GAPS.json", "research/CHARTER.json", "docs/NWS_PROVIDER.md"),
    unique_module_basenames=(), legacy_pointer_dir=None,
    allowed_runtime_ext=(".py", ".json", ".txt"), research_files=None,
    contract_tokens=("## 4. OWNERSHIP", "## 5. NON-OWNERSHIP", "Weather has no score", "gated live writer", "never an invented estimate"),
    bundle_id="weather-publication-v1", contract_file="contracts/weather-publication-v1.json", registry_schema_id="weather-registry-v1",
    job_id="weather-brain",
    plan_root_prefixes=("lakes/", "lakeFleet/", "brains/weather", "validation/weather"),
    extra_rejections=(Rejection("/lakes/Guntersville_AL/states/wind", "CROSS_DOMAIN_PATH"), Rejection("/scores/weather", "CROSS_DOMAIN_PATH"),
                      Rejection("/snapshots/Guntersville_AL/latest/weather", "PATH_NOT_AUTHORIZED")),
    write_call_suffixes=("_store.update", "_db.update"),
    allowed_write_sites=frozenset({("writer.py", "patch", "self._store.update"), ("writer.py", "patch", "self._db.update")}),
    builder_module="runtime/sector_weather/publish_artifact.py",
    has_score=False, score_baseline_substring=None,           # Weather has NO score: the shared scorer has no Weather entry
    release_lineage=S.LINEAGE,
    artifact_factory=artifact, changed_artifact_factory=changed_artifact,
)
