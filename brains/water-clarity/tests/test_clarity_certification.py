"""Water Clarity Brain (water-clarity, component C1) structural certification tests — Water Clarity Structural Certification V1.

These prove STRUCTURE: location, declaration, ownership, input truth, artifact contract, lineage, freshness, health representation, Publisher compatibility,
write isolation, runtime/research separation and science-neutrality of the move. They prove nothing about the clarity science (it stays NOT_VALIDATED as a
customer number). Synthetic data only; offline; no network; no production write.
"""
import ast
import copy
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

import clarity_support as S
from clarity_support import CLARITY, FIXTURES, REPO, RUNTIME, build, real_run_updates, rig, sealed

import clarity_brain as cb
import publish_artifact as pa
from sector_brain_platform import ConsumptionRecorder, DryRunStore, brain_health as BH, dependency_declarations as DD
from sector_brain_platform.publisher import PublisherMode, Result, default_registry

sys.path.insert(0, os.path.join(REPO, "tools", "architecture"))
import jsonschema_lite  # noqa: E402


def load(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as fh:
        return json.load(fh)


BRAIN = load("brains", "water-clarity", "brain.json")
INPUTS = load("brains", "water-clarity", "contracts", "INPUTS_V1.json")


def walk_files(root, exts=None):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ("__pycache__", ".git", "node_modules", ".pytest_cache", "out")]
        for f in fn:
            if exts is None or f.endswith(exts):
                yield os.path.join(dp, f)


@pytest.fixture(scope="module")
def legacy_updates():
    flat, _, rc = real_run_updates()
    assert rc == 0
    return flat


# ===================================================================================================== 1-2 canonical location, ONE implementation
def test_canonical_package_location_and_shape():
    for p in ("brain.json", "BRAIN_OPERATING_CONTRACT.md", "README.md", "contracts/clarity-publication-v1.json", "contracts/INPUTS_V1.json", "runtime/run.py",
              "runtime/clarity_brain.py", "runtime/publish_artifact.py", "runtime/catalog.json", "tests", "research/README.md", "research/GAPS.json", "deploy/deploy-job.sh"):
        assert os.path.exists(os.path.join(CLARITY, p)), p
    assert load("tools", "architecture", "stable_brain_ids.json")["directoryToBrainId"]["water-clarity"] == "water-clarity"


def test_exactly_one_production_clarity_implementation():
    """No second copy of the Clarity Brain modules anywhere in the repository; the legacy job directory is a pointer README only."""
    found = [r for r in (os.path.relpath(p, REPO) for p in walk_files(REPO, ".py") if os.path.basename(p) in ("clarity_brain.py",) or "clarity" in os.path.relpath(p, REPO).lower() and os.path.basename(p) == "publish_artifact.py")]
    assert sorted(found) == ["brains/water-clarity/runtime/clarity_brain.py", "brains/water-clarity/runtime/publish_artifact.py"], found
    assert os.listdir(os.path.join(REPO, "jobs", "water-clarity-brain")) == ["README.md"]
    assert "RETIRED" in open(os.path.join(REPO, "jobs", "water-clarity-brain", "README.md")).read()


# ===================================================================================================== 3-5 identity, ownership, dependencies
def test_brain_json_validates_and_identity_is_the_stable_machine_id():
    assert jsonschema_lite.validate(BRAIN, load("contracts", "schemas", "brain.schema.json")) == []
    assert BRAIN["brainId"] == "water-clarity" == cb.BRAIN_ID                       # never renamed
    from sector_brain_platform.keys import BRAINS
    assert BRAINS["water-clarity"][0] == cb.SLOT == "waterClarity"
    cm = load("jobs", "brain_platform", "sector_brain_platform", "control_manifest.json")["brains"]["water-clarity"]
    assert cm["displayName"] == "Water Clarity"


def test_lifecycle_is_derived_from_canonical_truth_and_never_promoted():
    cm = load("jobs", "brain_platform", "sector_brain_platform", "control_manifest.json")["brains"]["water-clarity"]
    assert BRAIN["lifecycle"] == cm["lifecycle"] == pa.LIFECYCLE == "CALIBRATION"      # hand-checked drift gate (debt D-9: no generic gate yet)
    assert BRAIN["publisherRequired"] == {"required": True, "cutoverStatus": "SHADOW"}
    assert {d["id"] for d in cm.get("dependencies", [])} <= {c.get("brainId") for c in BRAIN["consumes"] if c["kind"] == "brain"}     # inv 17
    assert cm["freshness"]["staleAfterHours"] == cb.STALE_AFTER_H == 26


def test_ownership_boundaries_in_the_declared_contract():
    text = open(os.path.join(CLARITY, "BRAIN_OPERATING_CONTRACT.md"), encoding="utf-8").read()
    for token in ("## 4. OWNERSHIP", "## 5. NON-OWNERSHIP", "production clarity **number**", "Lake Registry", "Sector Ops owns all labels", "Publisher publication metadata",
                  "RA-20", "GCS_HTTP_LINEAGE_PLATFORM_DEBT", "GCS_WRITE_SEMANTICS_PLATFORM_DEBT"):
        assert token in text, token
    assert len(re.findall(r"^## \d+\. ", text, re.M)) == 19


def test_published_contract_is_derived_from_the_publisher_registry():
    r = subprocess.run([sys.executable, os.path.join(CLARITY, "contracts", "describe_contract.py"), "--check"], capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": os.path.join(REPO, "jobs", "brain_platform")})
    assert r.returncode == 0, r.stdout + r.stderr
    declared = {f for p in BRAIN["publishes"] for f in p["pathFamilies"]}
    reg = default_registry()
    from_registry = {f.pattern.replace("{k}", "{k}") for sid in reg.schemas_for("water-clarity") for f in reg.spec(sid).families}
    norm = lambda s: re.sub(r"\{[a-z]+\}", "{}", s)      # noqa: E731
    assert {norm(x) for x in declared} == {norm(x) for x in from_registry}


# -- the real inputs: derived from the code, pinned
READ_FUNCS = {"http_json", "google_api"}


def _read_targets():
    out = []
    for fname in ("run.py", "clarity_brain.py"):
        tree = ast.parse(open(os.path.join(RUNTIME, fname), encoding="utf-8").read())
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in READ_FUNCS and n.args:
                out.append((fname, ast.unparse(n.args[0])))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "urlopen":
                out.append((fname, "urlopen"))
    return out


def _input_id(target):
    if "/lakes" in target and "ENGINE_URL" in target and "/conditions" not in target:
        return "engine-lakes-directory"
    if "ENGINE_URL" in target and "/conditions" in target:
        return "engine-conditions"
    if "STORAGE_API" in target or "it['name']" in target:
        return "lake-surface-run-records"
    if "BUCKET_URL" in target or target.startswith("f'{key}/"):
        return "lake-surface-clarity"
    if "run.googleapis.com" in target and "services/sector-engine" in target:
        return "cloud-run-engine-revision"
    if "executions" in target or "cloudscheduler" in target:
        return "job-health(not called)"
    if target == "urlopen":
        return "catalog-private-overlay"
    if target == "url":
        return "google_api-wrapper"                  # google_api() forwards its caller's URL; the callers are classified above
    return None


def test_declared_dependencies_validate_and_match_what_the_runtime_really_reads():
    targets = _read_targets()
    ids = {t: _input_id(t[1]) for t in targets}
    assert all(v for v in ids.values()), [t for t, v in ids.items() if not v]          # every read the code makes is accounted for in INPUTS_V1.json
    declared = {i["id"] for i in INPUTS["inputs"]}
    used = {v for v in ids.values() if v not in ("job-health(not called)", "catalog-private-overlay", "google_api-wrapper")}
    assert used <= declared, used - declared
    assert {"engine-lakes-directory", "engine-conditions", "lake-surface-clarity", "lake-surface-run-records", "cloud-run-engine-revision"} <= used
    # the only job-status reader (job_health) is dead code: Orchestrator owns job records since the 2026-10-13 cost audit
    tree = ast.parse(open(os.path.join(RUNTIME, "run.py"), encoding="utf-8").read())
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "job_health" not in called
    # brain.json carries exactly what the platform schema can express
    assert BRAIN["consumes"] == [{"kind": "registry", "registry": "lakes", "contractId": "registry.lakes", "minVersion": "1.0.0", "requirement": "REQUIRED"}]
    assert BRAIN["providers"] == [] and INPUTS["providers"]["declared"] == [] and INPUTS["signals"]["declared"] == [] and INPUTS["brains"]["declared"] == []


def test_customer_api_dependency_is_recorded_as_ownership_debt_never_blessed():
    by = {i["id"]: i for i in INPUTS["inputs"]}
    assert by["engine-conditions"]["class"] == "CUSTOMER_API_LEGACY" and "RA-20" in by["engine-conditions"]["ownershipDebt"] and "NOT a legitimate long-term dependency" in by["engine-conditions"]["ownershipDebt"]
    assert "RA-20" in by["engine-lakes-directory"]["ownershipDebt"] and by["engine-lakes-directory"]["lineage"] == "NOT_RECORDED"
    assert BRAIN["customerIntegrationMode"] == "none"                                   # no customer path reads the Brain (the debt is the opposite direction)
    assert "RA-20" in open(os.path.join(CLARITY, "BRAIN_OPERATING_CONTRACT.md"), encoding="utf-8").read()
    for i in INPUTS["inputs"]:
        assert i["class"] in ("PLATFORM_REGISTRY", "PROVIDER_DATA", "OWN_PIPELINE_OUTPUT", "OWN_MODEL", "CUSTOMER_API_LEGACY", "OPERATIONAL_METADATA", "OWN_STATE")
        assert i["lineage"] in ("RECORDED", "NOT_RECORDED", "NOT_APPLICABLE")


def test_no_fabricated_provider_signal_or_brain_edges():
    providers = load("providers", "PROVIDERS.json")["providers"]
    assert not [p for p in providers if "water-clarity" in (p.get("authorizedConsumers") or []) or p.get("acquisitionOwner") == "water-clarity"]
    assert not [c for c in BRAIN["consumes"] if c["kind"] in ("signal", "brain")]
    src = "".join(open(p, encoding="utf-8").read() for p in walk_files(RUNTIME, ".py"))
    for token in ("noaa-nbm", "iem-metar", "pressure-trend", "moon-phase", "signalId"):
        assert token not in src, token
    sources = set(cb.CATALOG["sources"])
    from sector_brain_platform.ownership import SOURCE_OWNERS
    assert sources == {s for s, o in SOURCE_OWNERS.items() if o == "water-clarity"}       # published source records == the sources Clarity owns, nothing more


# ===================================================================================================== 6-8 artifact, fingerprint, lineage
def test_artifact_is_publisher_valid_and_deterministic(legacy_updates):
    st, publish = rig()
    r1 = build(legacy_updates, n=1)
    assert r1.artifact["envelope"] == "publish-artifact-v2" and r1.artifact["lineage"]["artifactSchema"] == "clarity-publication-v1"
    res = publish(r1.artifact)
    assert res.result is Result.SHADOW_READY and res.codes == [] and res.mode is PublisherMode.SHADOW
    again = build(legacy_updates, n=1)
    assert json.dumps(r1.artifact, sort_keys=True) == json.dumps(again.artifact, sort_keys=True)          # no clock, no randomness
    assert not r1.unsupported


def test_semantic_fingerprint_ignores_execution_identity_and_per_run_timestamps(legacy_updates):
    base = build(legacy_updates, n=1)
    fp = base.artifact["lineage"]["outputFingerprint"]
    assert build(legacy_updates, n=2, generated_at="2026-10-13T03:00:00Z").artifact["lineage"]["outputFingerprint"] == fp        # new executionId + generatedAt
    moved = copy.deepcopy(legacy_updates)
    for k, v in moved.items():                                                                              # run-clock fields move: slot lastUpdatedAt, profile updatedAt, registry updatedAt/lastSuccessfulRun, source lastFetchAt
        if k.endswith("/slots/waterClarity") and isinstance(v, dict):
            v["lastUpdatedAt"] = "2026-10-13T09:00:00Z"
        if "/profiles/" in k and isinstance(v, dict):
            v["updatedAt"] = "2026-10-13T09:00:00Z"
        if k == "brains/water-clarity":
            v["updatedAt"] = "2026-10-13T09:00:00Z"; v["lastSuccessfulRun"] = "2026-10-13T09:00:00Z"
        if k.startswith("health/sources/") or (k.startswith("sources/") and isinstance(v, dict)):
            v["lastFetchAt"] = "2026-10-13T09:00:00Z"
    assert build(moved, n=3).artifact["lineage"]["outputFingerprint"] == fp
    assert build(legacy_updates, n=4, consumed=[]).artifact["lineage"]["outputFingerprint"] == fp           # lineage never enters the fingerprint
    assert base.artifact["lineage"]["inputFingerprint"] == build(moved, n=3).artifact["lineage"]["inputFingerprint"]


def test_real_domain_change_changes_the_fingerprint_and_unchanged_republish_is_skipped(legacy_updates):
    st, publish = rig()
    assert publish(build(legacy_updates, n=1).artifact).result is Result.SHADOW_READY
    assert publish(build(legacy_updates, n=2, generated_at="2026-10-13T06:30:00Z").artifact).result is Result.SKIP        # new run, same material -> nothing to publish
    changed = copy.deepcopy(legacy_updates)
    st_key = "lakes/Guntersville_AL/states/waterClarity"
    changed[st_key]["clarityFt"] = round(changed[st_key]["clarityFt"] + 0.5, 2)
    art = build(changed, n=3, generated_at="2026-10-14T06:30:00Z").artifact
    assert art["lineage"]["outputFingerprint"] != build(legacy_updates, n=1).artifact["lineage"]["outputFingerprint"]
    assert publish(art).result is Result.SHADOW_READY
    new_input = copy.deepcopy(changed); new_input[st_key]["evaluationTime"] = "2026-10-14T05:00:00Z"
    assert build(new_input, n=4).artifact["lineage"]["inputFingerprint"] != build(changed, n=3).artifact["lineage"]["inputFingerprint"]   # a new Engine evaluation IS a new input


def test_lineage_is_complete_truthful_and_never_fabricated(legacy_updates):
    art = build(legacy_updates, n=1).artifact
    lin = art["lineage"]
    assert lin["brainId"] == "water-clarity" and lin["lifecycle"] == "CALIBRATION" and lin["reviewStatus"] == "UNREVIEWED" and lin["validationStatus"] == "NOT_VALIDATED"
    assert (lin["knowledgeRelease"], lin["manifestRef"], lin["manifestSha256"]) == ("NONE", "NONE", "NONE")   # no canonical release/manifest exists: never invented
    for k in ("codeVersion", "executionId", "inputFingerprint", "outputFingerprint", "generatedAt", "artifactId"):
        assert lin[k]
    assert "consumed" not in art                                                                              # HTTP/GCS reads are not recorded: UNKNOWN, never []
    assert build(legacy_updates, n=1, consumed=[]).artifact["consumed"] == []                                # [] only when a recorder really recorded "nothing"
    src = "".join(open(p, encoding="utf-8").read() for p in walk_files(RUNTIME, ".py"))
    assert "dependencyType" not in src and "consumedAt" not in src                                           # the runtime never constructs consumption entries by hand


def test_review_and_validation_status_are_never_optimistic():
    c = S.ctx()
    assert (c.review_status, c.validation_status, c.lifecycle) == ("UNREVIEWED", "NOT_VALIDATED", "CALIBRATION")


# ===================================================================================================== 9 consumption capture (RTDB reads only)
def test_actual_consumption_capture_works_for_rtdb_reads_and_http_reads_are_not_faked():
    r = ConsumptionRecorder("water-clarity", clock=lambda: S.NOW)
    db = DryRunStore({"brains": {"water-clarity": {"version": "x"}, "water-temp": {"version": "wt1", "freshness": {"generatedAt": "2026-10-12T05:00:00Z"}}},
                      "lakeFleet": {"G": {"slots": {"waterClarity": {"readiness": "BETA"}}}}, "activity": {}}, "water-clarity", recorder=r)
    db.get("brains/water-clarity"); db.get("lakeFleet"); db.get("activity")                                # what run.py reads: its own state and shared fleet nodes
    assert db.consumed() == [] or all(e["dependencyId"] != "brain:water-clarity" for e in db.consumed())  # own state is never a dependency
    db.get("brains/water-temp")
    assert "brain:water-temp" in {e["dependencyId"] for e in db.consumed()}                                 # a real foreign read IS recorded
    art = build({"brains/water-clarity": {"brainId": "water-clarity", "version": "1.1.0"}}, consumed=db.consumed()).artifact
    st, publish = rig()
    assert publish(art).result is Result.SHADOW_READY
    # the live path attaches the recorder; the dry run reads no RTDB so its report says "not recorded" (None), not "[]"
    tree = ast.parse(open(os.path.join(RUNTIME, "run.py"), encoding="utf-8").read())
    assert any(isinstance(n, ast.keyword) and n.arg == "recorder" for n in ast.walk(tree))
    flat, t, rc = real_run_updates()
    assert rc == 0


def test_live_run_report_carries_recorded_rtdb_reads_only(tmp_path):
    flat, t, rc = real_run_updates(argv=("--batch", "2", "--out", str(tmp_path / "o")))
    rep = json.load(open(tmp_path / "o" / "run_report.json"))
    assert rep["consumedRtdbReads"] == [] and rep["dryRun"] is False          # the run read only its own / shared fleet state: recorded as "nothing that is a dependency"


# ===================================================================================================== 10-11 freshness + healthV1
def _health(executions=None, **kw):
    brains = DD.load_registered_brains(REPO)
    declared = DD.declared_dependencies(brains["water-clarity"])
    return BH.brain_health("water-clarity", declared=declared, declarations_known=True, executions=executions, observations={}, now=S.NOW, **kw)


def test_health_v1_can_represent_clarity_from_engine_truth_alone():
    h = _health()
    assert h["brainId"] == "water-clarity" and h["dependencies"]["declared"] == 1
    assert h["dependencies"]["declaredVsActual"]["consumptionRecorded"] is False        # nothing recorded => never claimed SATISFIED from silence
    assert h["freshness"]["status"] == "UNKNOWN"


def test_unknown_stays_unknown_and_last_successful_run_is_not_evidence_freshness():
    ok = [{"executionId": S.uid(1), "brainId": "water-clarity", "status": "SUCCEEDED", "startedAt": "2026-10-12T06:00:00Z", "finishedAt": "2026-10-12T06:01:00Z"}]
    h = _health(ok)
    assert h["freshness"]["status"] == "UNKNOWN"                                         # a recent successful run does NOT make evidence FRESH
    assert h["process"]["processHealth"] in ("HEALTHY", "UNKNOWN")                       # process health is its own axis
    ex = dict(ok[0], consumed=[{"dependencyId": "brain:wind", "dependencyType": "BRAIN", "consumedAt": "2026-10-12T06:00:30Z"}])
    assert _health([ex])["dependencies"]["declaredVsActual"]["consumedNotDeclared"] == ["brain:wind"]


def test_no_freshness_is_derived_from_last_successful_run_anywhere_in_clarity():
    for p in walk_files(RUNTIME, ".py"):
        src = open(p, encoding="utf-8").read()
        for m in re.finditer(r"freshness[^\n]*lastSuccess|lastSuccess[^\n]*(freshUntil|staleAfter|expiresAt|freshnessStatus)", src):
            if "never" in m.group(0) or "NOT" in m.group(0):
                continue
            pytest.fail(f"{os.path.relpath(p, REPO)}: evidence freshness derived from lastSuccess: {m.group(0)[:100]}")


def _states(**over):
    base = {"stateType": "RAINFALL_MODELED", "evaluationTime": "2026-10-12T06:12:13Z", "satelliteObservationAt": "2026-10-08T16:44:07Z"}
    return {"/lakes/A_AL/states/waterClarity": {**base, **over}}


def test_freshness_keeps_scene_input_generation_and_brain_time_apart_and_uses_the_existing_threshold():
    fr = pa.freshness(_states(), "2026-10-12T06:30:00Z")
    assert fr == {"evidenceObservedAt": "2026-10-08T16:44:07Z", "inputGeneratedAt": "2026-10-12T06:12:13Z", "staleAfter": "2026-10-13T08:12:13Z", "freshnessStatus": "FRESH"}
    assert fr["evidenceObservedAt"] != fr["inputGeneratedAt"]                              # scene time is not the Engine evaluation time
    assert pa.freshness(_states(), "2026-10-13T09:00:00Z")["freshnessStatus"] == "STALE"  # 26 h after the Engine evaluation, TIME model


def test_freshness_unknown_unavailable_and_missing_evidence_are_honest():
    assert pa.freshness({}, "2026-10-12T06:30:00Z") == {"freshnessStatus": "UNKNOWN"}
    no_eval = pa.freshness(_states(evaluationTime=None), "2026-10-12T06:30:00Z")
    assert no_eval["freshnessStatus"] == "UNKNOWN" and "inputGeneratedAt" not in no_eval and "staleAfter" not in no_eval       # unknown stays unknown, never FRESH
    no_scene = pa.freshness(_states(satelliteObservationAt=None), "2026-10-12T06:30:00Z")
    assert "evidenceObservedAt" not in no_scene                                              # gauge reading times are unknown: never substituted by the Engine time
    assert pa.freshness(_states(stateType="UNAVAILABLE", evaluationTime=None, satelliteObservationAt=None), "2026-10-12T06:30:00Z")["freshnessStatus"] == "UNAVAILABLE"


def test_artifact_freshness_block_is_derived_from_states_not_from_process_history(legacy_updates):
    art = build(legacy_updates).artifact
    lake_sections = [s for s in art["sections"] if s["artifactSchema"] == "clarity-lake-state-v1"]
    assert lake_sections and all(s["freshness"]["freshnessStatus"] in ("FRESH", "STALE", "UNKNOWN", "UNAVAILABLE") for s in lake_sections)
    assert all("lastSuccess" not in json.dumps(s.get("freshness")) for s in art["sections"])
    assert all("freshness" not in s for s in art["sections"] if s["artifactSchema"] != "clarity-lake-state-v1")


# ===================================================================================================== 12-13 Publisher shadow
def test_publisher_is_shadow_only_and_end_to_end_handoff_works(legacy_updates):
    assert {m.name for m in PublisherMode} == {"SHADOW", "DRY_RUN"}                                         # no live mode exists
    from sector_brain_platform.publisher.api import AllowlistAuthorizer, Caller, OrchestratorApi

    class Authn:
        def authenticate(self, cred):
            return Caller("clarity-brain-identity") if cred == "clarity-token" else None
    st, _ = rig()
    api = OrchestratorApi(Authn(), AllowlistAuthorizer({"clarity-brain-identity": {"ARTIFACT": {"SUBMIT_ARTIFACT@water-clarity"}}}), st.dispatcher)
    ref = st.writer("water-clarity").write(build(legacy_updates).artifact)
    body = {"apiVersion": "orchestrator-api-v1", "requestId": S.uid(700), "requestKind": "ARTIFACT", "brainId": "water-clarity", "action": "SUBMIT_ARTIFACT",
            "params": {"artifactId": ref.artifact_id, "artifactRef": ref.location, "artifactSha256": ref.sha256, "executionId": ref.execution_id, "expectedSchema": ref.expected_schema}}
    r = api.handle("clarity-token", body)
    assert r.status == 200 and r.result["result"] == "SHADOW_READY" and r.result["live"] is False
    assert st.sink.live_mutations == 0
    plan = st.sink.submitted[-1][0]
    assert "brains/water-clarity/publication" in plan.updates                                                 # the Publisher's own record, in the same single plan
    allowed_roots = ("lakes/", "lakeFleet/", "snapshots/", "brains/water-clarity", "validation/water-clarity", "health/brains/water-clarity", "activity/", "sources/", "health/sources/")
    assert [k for k in plan.updates if not k.startswith(allowed_roots)] == []
    assert any(k.startswith("snapshots/") and k.endswith("/latest/waterClarity") for k in plan.updates)      # Publisher-derived compatibility projection


@pytest.mark.parametrize("path,code", [
    ("/lakes/Guntersville_AL/states/wind", "CROSS_DOMAIN_PATH"),                 # another Brain's slot
    ("/brains/wind/status", "CROSS_DOMAIN_PATH"),                                # another Brain's node
    ("/scores/water-clarity", "CROSS_DOMAIN_PATH"),                              # Platform writes scores
    ("/brains/water-clarity/publication", "RESERVED_PATH"),                      # Publisher-owned
    ("/brains/water-clarity/certification", "RESERVED_PATH"),
    ("/brains/water-clarity", "BRAIN_NODE_REPLACEMENT"),                         # never the whole node
    ("/health/jobs/water-clarity-brain", "CROSS_DOMAIN_PATH"),                   # execution health is Orchestrator-owned
    ("/control/orchestratorV1", "CROSS_DOMAIN_PATH"),
    ("/snapshots/Guntersville_AL/latest/waterClarity", "PLATFORM_DERIVED_PATH"), # Publisher-derived: a Brain cannot author the compatibility copy
])
def test_publisher_rejects_wrong_path_ownership(path, code):
    st, publish = rig()
    res = publish(sealed([{"op": "SET", "path": "/brains/water-clarity/status", "value": "BETA"}, {"op": "SET", "path": path, "value": {"x": 1}}]))
    assert res.result is Result.REJECTED and code in res.codes, res.codes
    assert st.sink.submitted == []


def test_publisher_rejects_wrong_brain_and_wrong_schema_ownership(legacy_updates):
    st, publish = rig()
    art = build(legacy_updates).artifact
    ref = st.writer("wind").write(copy.deepcopy(dict(art, lineage=dict(art["lineage"], brainId="wind"))))
    r = st.publisher.evaluate_reference(ref)
    assert r.result is Result.REJECTED and ("SCHEMA_BRAIN_MISMATCH" in r.codes or "UNKNOWN_SCHEMA" in r.codes)
    bad = copy.deepcopy(art); bad["lineage"]["artifactSchema"] = "wind-publication-v1"
    assert publish(bad).result is Result.REJECTED
    wrong = sealed([{"op": "SET", "path": "/lakes/Guntersville_AL/states/waterClarity", "value": {"a": 1}}], schema="clarity-registry-v1")       # a lake-state path in the registry section
    assert publish(wrong).result is Result.REJECTED
    from sector_brain_platform.publisher import seal_bundle
    wind_try = seal_bundle(brain_id="wind", bundle_id="wind-publication-v1", sections=[{"artifactSchema": "wind-registry-v1", "mutations": [{"op": "SET", "path": "/lakes/G_AL/states/waterClarity", "value": {"a": 1}}]}],
                           lifecycle="CALIBRATION", review_status="UNREVIEWED", validation_status="NOT_VALIDATED", generated_at=S.GENERATED_AT, execution_id=S.uid(11),
                           code_version="t", input_fingerprint="sha256:" + "ab" * 32, registry=default_registry())
    assert publish(wind_try, brain="wind").result is Result.REJECTED             # Wind cannot write Clarity's slot


def test_publisher_requires_freshness_for_lake_state_and_refuses_production_lifecycles(legacy_updates):
    art = build(legacy_updates).artifact
    no_fresh = copy.deepcopy(art)
    for s in no_fresh["sections"]:
        s.pop("freshness", None)
    st, publish = rig()
    r = publish(no_fresh)
    assert r.result is not Result.SHADOW_READY
    prod = copy.deepcopy(art); prod["lineage"]["lifecycle"] = "PRODUCTION"
    st, publish = rig()
    r = publish(prod)
    assert r.result is Result.REJECTED and "LIFECYCLE_NOT_AUTHORIZED" in r.codes


def test_deletes_are_typed_and_null_is_never_an_implicit_delete(legacy_updates):
    st, publish = rig()
    art = build(legacy_updates).artifact
    muts = [m for s in art["sections"] for m in s["mutations"]]
    assert {"op": "DELETE", "path": "/brains/water-clarity/lastError", "reason": "OPTIONAL_CHILD_CLEARED"} in muts      # the single declared optional child
    assert [m for m in muts if m["op"] == "DELETE"] == [m for m in muts if m["op"] == "DELETE" and m["path"] == "/brains/water-clarity/lastError"]
    assert publish(art).result is Result.SHADOW_READY
    nul = sealed([{"op": "SET", "path": "/brains/water-clarity/status", "value": None}])
    assert publish(nul).result is Result.FAILED_VALIDATION
    # a lake state can never be deleted (Clarity keeps the last good state): no delete family exists
    gone = sealed([{"op": "DELETE", "path": "/lakes/Guntersville_AL/states/waterClarity", "reason": "LAKE_LEFT_FLEET"}], schema="clarity-lake-state-v1",
                  freshness={"freshnessStatus": "UNKNOWN"})
    assert publish(gone).result is Result.REJECTED
    # absent / empty / unknown values are plain absence in the artifact
    for lake_path in ("lakes/Guntersville_AL/states/waterClarity",):
        assert "None" not in json.dumps([m for m in muts if m["path"] == "/" + lake_path])


def test_every_registry_child_the_runtime_emits_is_covered_by_the_contract(legacy_updates):
    emitted = set(legacy_updates["brains/water-clarity"])
    from sector_brain_platform.publisher.registry import CLARITY_REGISTRY_CHILDREN
    covered = {c for g in CLARITY_REGISTRY_CHILDREN.values() for c in g}
    assert emitted <= covered, f"registry children without a contract entry: {sorted(emitted - covered)}"
    assert not ({"publication", "certification"} & covered)
    for k in ("lakeId",):
        assert not [m for s in build(legacy_updates).artifact["sections"] for m in s["mutations"] if m["path"].endswith("/" + k)]


def test_unmapped_paths_fail_closed_never_silently_dropped_or_emitted(legacy_updates):
    with pytest.raises(pa.ArtifactBuildError):
        build(dict(legacy_updates, **{"/speciesProfiles/x": {"a": 1}}))
    with pytest.raises(pa.ArtifactBuildError):
        build(dict(legacy_updates, **{"/scores/water-clarity": {"value": 9}}))


# ===================================================================================================== 14-16 direct-write audit, write isolation
WRITE_METHODS = {"update", "put", "patch", "post", "set", "delete"}
FORBIDDEN_IMPORTS = ("firebase_admin", "requests", "google.cloud", "pyrebase")
#: The audit table (docs/architecture/certification/water-clarity/CLARITY_DIRECT_WRITE_AUDIT.md): every RTDB write site in the runtime. Both are LEGACY / RETIREMENT_CANDIDATE.
ALLOWED_LEGACY_WRITE = {("run.py", "write", "rtdb.update"), ("run.py", "main", "rtdb.update")}


def _write_sites(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    sites = set()

    def visit(node, fn):
        for ch in ast.iter_child_nodes(node):
            f = ch.name if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)) else fn
            if isinstance(ch, ast.Call) and isinstance(ch.func, ast.Attribute) and ch.func.attr in WRITE_METHODS:
                full = ast.unparse(ch.func)
                if full.split(".")[0] not in ("os", "json", "shutil") and full.endswith("rtdb.update"):
                    sites.add((os.path.basename(path), fn or "<module>", "rtdb.update"))
            visit(ch, f)
    visit(tree, None)
    return sites


def test_no_unauthorized_production_write_in_the_clarity_runtime():
    sites = set()
    for p in walk_files(RUNTIME, ".py"):
        src = open(p, encoding="utf-8").read()
        assert not [m for m in FORBIDDEN_IMPORTS if re.search(rf"^\s*(import|from)\s+{re.escape(m)}", src, re.M)], p
        assert not re.search(r"method\s*=\s*['\"](PATCH|PUT|POST|DELETE)['\"]", src), f"{p}: direct REST write"
        sites |= _write_sites(p)
    assert sites == ALLOWED_LEGACY_WRITE, f"unexpected database write sites: {sorted(sites ^ ALLOWED_LEGACY_WRITE)}"


def test_the_artifact_path_cannot_write_anything(tmp_path):
    """publish_artifact.py is pure (no I/O, no network, no clock, no randomness, no environment); run.py's artifact path only builds/evaluates in memory."""
    tree = ast.parse(open(os.path.join(RUNTIME, "publish_artifact.py"), encoding="utf-8").read())
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not imported & {"urllib", "requests", "subprocess", "random", "uuid", "time", "socket", "os", "shutil", "tempfile", "http"}, imported
    src = ast.unparse(tree)
    for token in ("open(", "datetime.now", "utcnow", ".environ", "urlopen"):
        assert token not in src, token


def test_dry_run_artifact_path_writes_only_local_files_and_never_touches_the_database(tmp_path, monkeypatch):
    os.environ["BRAIN_ACCESS_TOKEN"] = "test-token"
    called = []
    from sector_brain_platform import rtdb as _rtdb
    monkeypatch.setattr(_rtdb.BrainRtdb, "update", lambda *a, **k: called.append("update"))
    monkeypatch.setattr(S.run, "load_directory", lambda: list(S.DIRECTORY))
    monkeypatch.setattr(S.run, "polygon_ids", lambda: {"Guntersville|AL"})
    monkeypatch.setattr(S.run, "bucket_lake", lambda lid: {"latest": S.LATEST, "meta": S.META, "passCount": 16})
    monkeypatch.setattr(S.run, "engine_conditions", lambda lake: S.GUNT)
    monkeypatch.setattr(S.run, "engine_revision", lambda tokens: "sector-engine-test")
    monkeypatch.setattr(S.run, "lake_surface_run", lambda now: None)
    monkeypatch.setattr(sys, "argv", ["run.py", "--dry-run", "--out", str(tmp_path / "o"), "--lakes", "Guntersville|AL"])
    assert S.run.main() == 0
    assert called == []
    assert sorted(os.listdir(tmp_path / "o")) == ["artifact.json", "payload.json", "run_report.json", "shadow_verdict.json"]
    v = json.load(open(tmp_path / "o" / "shadow_verdict.json"))
    assert v["result"] == "SHADOW_READY" and v["live"] is False and v["artifactSchema"] == "clarity-publication-v1"
    art = json.load(open(tmp_path / "o" / "artifact.json"))
    assert "consumed" not in art                                                                             # a dry run reads no RTDB: unknown, not []


def test_write_path_remains_ownership_checked_and_clarity_cannot_write_foreign_or_customer_roots(legacy_updates):
    from sector_brain_platform.ownership import OwnershipError, assert_owned
    assert_owned(legacy_updates, "water-clarity")                                                             # the REAL legacy write set is within Clarity's ownership
    for bad in ("/lakes/G/states/wind", "/scores/water-clarity", "/brains/wind/version", "/control/orchestratorV1", "/snapshots/G/latest/waterTemperature", "/species/x"):
        with pytest.raises(OwnershipError):
            assert_owned({bad: {"x": 1}}, "water-clarity")
    with pytest.raises(Exception):
        S.run.bp.BrainRtdb("https://example-app-prod-default-rtdb.firebaseio.com", object(), brain_id="water-clarity")      # the platform client refuses anything but the Brain RTDB


def test_legacy_write_set_classification_is_complete(legacy_updates):
    """Every path of the real legacy write set is either authored by a Clarity schema, a Publisher-derived projection, or classified (no unknown door)."""
    r = build(legacy_updates)
    assert r.unsupported == []
    classes = {d["classification"] for d in r.dropped}
    assert classes <= {"PLATFORM_OWNED", "DERIVED_COMPATIBILITY_PROJECTION", "LEGACY_READER_DEPENDENCY"}
    rows = {d["row"] for d in r.dropped}
    assert {"lakefleet-lakeid", "snapshot-lakeid", "health-jobs", "health-brains-process", "clarity-snapshot-copy-v1", "clarity-snapshot-brainversion-v1"} <= rows
    path = os.path.join(REPO, "docs", "architecture", "certification", "water-clarity", "CLARITY_DIRECT_WRITE_AUDIT.md")
    audit = open(path, encoding="utf-8").read()
    for row in rows | {"rtdb.update", "GCS_WRITE_SEMANTICS_PLATFORM_DEBT"}:
        assert row in audit, f"direct-write audit does not mention {row}"


# ===================================================================================================== 17-19 runtime isolation, research separation, public/private
LOCAL_PATH = re.compile(r"/Users/|/home/[a-z]|\bDesktop/|Sector[ _]Research|Sector_Research_Data|~/|expanduser|SECTOR_RESEARCH_ROOT|water-clarity/(sources|datasets|analysis)")


def test_no_local_mac_research_or_cache_paths_in_clarity_runtime():
    bad = []
    for p in walk_files(RUNTIME, (".py", ".json", ".sh", ".txt")):
        for i, line in enumerate(open(p, encoding="utf-8").read().splitlines(), 1):
            if LOCAL_PATH.search(line):
                bad.append(f"{os.path.relpath(p, REPO)}:{i}")
    assert not bad, bad


def test_runtime_works_with_no_research_workspace_no_home_and_no_repo_docs(tmp_path):
    """The staged deploy layout (deploy-job.sh --stage-only): only runtime + platform + outlines, NO docs/, NO research, NO tests, empty HOME."""
    stage = tmp_path / "ctx"
    r = subprocess.run(["bash", os.path.join(CLARITY, "deploy", "deploy-job.sh"), "--stage-only", str(stage)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert sorted(os.listdir(stage)) == ["Dockerfile", "brain_platform.py", "catalog.json", "clarity_brain.py", "polygons.geojson.gz", "publish_artifact.py", "run.py", "sector_brain_platform"]
    snippet = f"""
import json, os, sys, unittest.mock as m
sys.path.insert(0, {os.path.join(CLARITY, 'tests')!r})
import json as j
def fx(n): return j.load(open(os.path.join({FIXTURES!r}, n)))
import run
G, L, M = fx('engine_guntersville_rain_decay.json'), fx('bucket_guntersville_latest.json'), fx('bucket_guntersville_meta.json')
with m.patch.object(run, 'load_directory', return_value=[{{'id':'Guntersville|AL','lat':34.4,'lon':-86.2}}]), \\
     m.patch.object(run, 'bucket_lake', return_value={{'latest':L,'meta':M,'passCount':16}}), m.patch.object(run, 'engine_conditions', return_value=G), \\
     m.patch.object(run, 'engine_revision', return_value='x'), m.patch.object(run, 'lake_surface_run', return_value=None), m.patch.object(sys, 'argv', ['run.py','--dry-run','--out',{str(tmp_path / 'out')!r},'--lakes','Guntersville|AL']):
    sys.exit(run.main())
"""
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path / "nohome"), "PYTHONPATH": "", "PYTHONDONTWRITEBYTECODE": "1"}
    p = subprocess.run([sys.executable, "-c", snippet], cwd=stage, env=env, capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stderr
    v = json.load(open(tmp_path / "out" / "shadow_verdict.json"))
    assert v["result"] == "SHADOW_READY" and v["live"] is False
    r2 = subprocess.run(["bash", os.path.join(CLARITY, "deploy", "deploy-job.sh")], capture_output=True, text=True, env={"PATH": os.environ.get("PATH", "")})
    assert r2.returncode == 2 and "Refusing" in r2.stderr                                                    # a deploy needs Michael's approval


def test_research_is_separate_from_the_production_package():
    odd = [os.path.relpath(p, CLARITY) for p in walk_files(os.path.join(CLARITY, "runtime")) if os.path.splitext(p)[1] not in {".py", ".json"}]
    assert not odd, odd
    ls = lambda d: sorted(n for n in os.listdir(os.path.join(CLARITY, d)) if n != "__pycache__")      # noqa: E731
    assert ls("runtime") == ["brain_platform.py", "catalog.json", "clarity_brain.py", "publish_artifact.py", "run.py"]
    assert ls("research") == ["GAPS.json", "README.md"]
    gaps = load("brains", "water-clarity", "research", "GAPS.json")
    assert jsonschema_lite.validate(gaps, load("contracts", "schemas", "research-gaps.schema.json")) == []
    assert BRAIN["researchWorkspace"] == {"workspaceId": "water-clarity"}                                     # a LOGICAL id; never a physical path
    assert not [p for p in walk_files(CLARITY) if os.path.getsize(p) >= BRAIN["dataBudget"]["maxTrackedFileBytes"]]


PRIVATE_MARKERS = re.compile(r"WEAKEST_CORE_CLASS|ACCURACY_CERT|FREEZE_STAGE18|STRONG_SHARE|research-archive|TCEQ|sector-clarity-candidate|gs://sector-clarity")


def test_no_private_research_or_agency_material_in_the_public_package_or_certification_docs():
    roots = [CLARITY, os.path.join(REPO, "jobs", "water-clarity-brain")]       # the certification docs name the markers they audit; the package must not carry them
    me = os.path.abspath(__file__)
    for root in roots:
        for p in walk_files(root, (".py", ".json", ".md", ".sh", ".txt", ".ini")):
            if os.path.abspath(p) == me or p.endswith(os.path.join("golden", "clarity_science_baseline.json")) or p == os.path.join(RUNTIME, "catalog.json"):
                continue                      # this file names the markers it forbids; the golden is synthetic; the public catalog carries the PRIVATE REFERENCE by design (checked below)
            for i, line in enumerate(open(p, encoding="utf-8").read().splitlines(), 1):
                if PRIVATE_MARKERS.search(line):
                    pytest.fail(f"{os.path.relpath(p, REPO)}:{i}: private research marker")
    assert not os.path.exists(os.path.join(RUNTIME, "catalog.private.json"))
    ignored = open(os.path.join(CLARITY, ".gitignore")).read()
    assert "catalog.private.json" in ignored


def test_synthetic_golden_contains_no_real_private_detail_and_catalog_is_status_level():
    c = json.load(open(os.path.join(RUNTIME, "catalog.json")))
    assert c["certifications"]["r3_1"]["detailRef"]["visibility"] == "PRIVATE" and "bars" not in c["certifications"]["r3_1"]
    assert not re.search(r"WEAKEST_CORE_CLASS|ACCURACY_CERT|STRONG_SHARE|\"bars\"", json.dumps(c))


# ===================================================================================================== 20-21 science preserved, score unchanged
GOLDEN = json.load(open(os.path.join(S.HERE, "golden", "clarity_science_baseline.json")))


def test_existing_clarity_science_output_is_byte_identical_to_the_pre_move_tree():
    """The golden was produced by the PRE-MOVE tree (jobs/water-clarity-brain at origin/main 4ff9bed0) on the same synthetic fixtures and fixed clock."""
    import gen_golden
    now = gen_golden.generate(RUNTIME)
    want = {k: v for k, v in GOLDEN.items() if k != "_provenance"}
    assert json.dumps(now, sort_keys=True) == json.dumps(want, sort_keys=True)
    h = lambda o: hashlib.sha256(json.dumps(o, sort_keys=True, separators=(",", ":")).encode()).hexdigest()      # noqa: E731
    for name in want["scenarios"]:
        assert h(now["scenarios"][name]) == h(want["scenarios"][name]), name


def test_the_production_catalog_and_thresholds_are_unchanged_by_the_move():
    pre = subprocess.run(["git", "-C", REPO, "show", "4ff9bed080fab4e289b95f76b70d37e17347434c:jobs/water-clarity-brain/catalog.json"], capture_output=True, text=True)
    if pre.returncode != 0:
        pytest.skip("pre-move commit not available in this checkout")
    assert json.loads(pre.stdout) == json.load(open(os.path.join(RUNTIME, "catalog.json")))
    assert (cb.STALE_AFTER_H, cb.SAT_FRESH_DAYS) == (26, 14)


FROZEN_BLOCK_SHA256 = "b2cb88becb9dac6ddddec271ee4dd7c5cfd51141bf4f09ac9b4f2dceca9d13a1"      # sha256 of the water-clarity block of docs/brains/scoring/frozen-scores.json at origin/main 4ff9bed0 (BEFORE); AFTER must equal it


def test_research_score_is_unchanged_before_equals_after_and_the_brain_does_not_write_scores(legacy_updates):
    frozen = load("docs", "brains", "scoring", "frozen-scores.json")["water-clarity"]
    assert (frozen["value"], frozen["scale"], frozen["basis"], frozen["scoreVersion"]) == (8.0, 10, "FROZEN", "clarity-research-certification-r3.1")
    assert frozen["appliesTo"]["deploymentStatus"] == "NOT_DEPLOYED"                                          # a research score for the CANDIDATE; production clarity is unscored
    got = hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()
    assert got == FROZEN_BLOCK_SHA256, got
    assert BRAIN["score"]["path"] == "/scores/water-clarity"
    assert not [k for k in legacy_updates if k.lstrip("/").startswith("scores")]                              # C1 writes no score
    r = subprocess.run([sys.executable, os.path.join(REPO, "verification", "integration", "score_baseline.py"), "--check"], capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 0 and "water-clarity=8.0/10" in r.stdout, r.stdout + r.stderr


# ===================================================================================================== 22 registered-Brain architecture gates
def test_registered_brain_architecture_gates_pass_for_clarity_with_no_new_violations():
    import report                                                             # tools/architecture/report.py (path added above)
    own = [f for f in report.check(REPO, legacy=False) if "brains/water-clarity" in f["subject"]]
    # the only registered-Brain finding is the published-label string carried from the legacy job (same retirement condition as Wind's and Fish's)
    assert all(f["invariant"] == 8 and os.path.basename(f["subject"]) == "clarity_brain.py" for f in own), own
    legacy = report.check(REPO, legacy=True)
    baseline = json.load(open(os.path.join(REPO, "tools", "architecture", "baseline", "legacy_violations.json")))
    known, new, resolved = report.compare_to_baseline(legacy, baseline)
    assert new == [] and resolved == [], (new, resolved)                       # NO NEW architecture violations; nothing silently dropped from the baseline
    carried = [e for e in baseline["entries"] if e["path"].startswith("brains/water-clarity/")]
    assert {os.path.basename(e["path"]) for e in carried} == {"clarity_brain.py"} and all(e.get("carriedFrom") for e in carried)
    assert not [e for e in baseline["entries"] if e["path"].startswith("jobs/water-clarity-brain/")]           # the legacy job entries moved with the code


# ===================================================================================================== extra: the engine-miss path (stale carry + error children) is representable and owned
def test_engine_miss_run_keeps_the_last_good_state_and_is_a_publisher_valid_artifact():
    prev = {"Kentucky_Lake_KY": {"lakeId": "Kentucky Lake|KY", "slots": {"waterClarity": {"readiness": "BETA", "lastUpdatedAt": "2026-10-10T00:00:00Z"}}}}

    def engine(lake):
        if lake["id"] == "Kentucky Lake|KY":
            raise TimeoutError("engine timeout")
        return {"Guntersville|AL": S.GUNT, "Aleknagik|AK": S.ALEK}[lake["id"]]
    flat, t, rc = real_run_updates(engine=engine, reads={"lakeFleet": prev})
    assert "lakes/Kentucky_Lake_KY/states/waterClarity" not in flat                                           # never blanks the last good state
    assert flat["lakeFleet/Kentucky_Lake_KY/slots/waterClarity/stale"] is True
    assert "lakeFleet/Kentucky_Lake_KY/slots/waterClarity/lastError" in flat
    from sector_brain_platform.ownership import assert_owned
    assert_owned(flat, "water-clarity")
    st, publish = rig()
    r = build(flat)
    assert r.unsupported == []
    paths = {m["path"] for s in r.artifact["sections"] for m in s["mutations"]}
    assert "/lakeFleet/Kentucky_Lake_KY/slots/waterClarity/stale" in paths and "/lakeFleet/Kentucky_Lake_KY/slots/waterClarity/lastError" in paths
    assert publish(r.artifact).result is Result.SHADOW_READY
