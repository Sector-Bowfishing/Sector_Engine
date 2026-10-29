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


# ===================================================================================================== 3-5 identity, ownership, dependencies


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


def test_last_error_is_the_single_typed_delete_and_absent_values_are_plain_absence(legacy_updates):
    """Domain part of the delete proof (the generic typed-delete / null != delete / no-lake-state-delete proofs are shared: BRAIN_CERT_KIT_V1 P13)."""
    art = build(legacy_updates).artifact
    muts = [m for sec in art["sections"] for m in sec["mutations"]]
    assert [m for m in muts if m["op"] == "DELETE"] == [{"op": "DELETE", "path": "/brains/water-clarity/lastError", "reason": "OPTIONAL_CHILD_CLEARED"}]
    assert "None" not in json.dumps([m for m in muts if m["path"] == "/lakes/Guntersville_AL/states/waterClarity"])


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
#: The audit table (docs/architecture/certification/water-clarity/CLARITY_DIRECT_WRITE_AUDIT.md): every RTDB write site in the runtime. Both are LEGACY / RETIREMENT_CANDIDATE.


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
    assert {"lakefleet-lakeid", "snapshot-lakeid", "health-jobs", "health-brains", "health-sources", "clarity-snapshot-copy-v1", "clarity-snapshot-brainversion-v1"} <= rows
    path = os.path.join(REPO, "docs", "architecture", "certification", "water-clarity", "CLARITY_DIRECT_WRITE_AUDIT.md")
    audit = open(path, encoding="utf-8").read()
    for row in rows | {"rtdb.update", "GCS_WRITE_SEMANTICS_PLATFORM_DEBT"}:
        assert row in audit, f"direct-write audit does not mention {row}"


# ===================================================================================================== 17-19 runtime isolation, research separation, public/private


def test_runtime_works_with_no_research_workspace_no_home_and_no_repo_docs(tmp_path):
    """The staged deploy layout (deploy-job.sh --stage-only): only runtime + platform + outlines, NO docs/, NO research, NO tests, empty HOME."""
    stage = tmp_path / "ctx"
    r = subprocess.run(["bash", os.path.join(CLARITY, "deploy", "deploy-job.sh"), "--stage-only", str(stage)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert sorted(os.listdir(stage)) == ["Dockerfile", "brain_platform.py", "catalog.json", "clarity_brain.py", "knowledge-release.json", "polygons.geojson.gz", "publish_artifact.py", "run.py",
                                   "sector_brain_platform"]
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


def test_runtime_package_is_exactly_the_five_modules_and_the_public_catalog():
    """Domain part of the research-separation proof (file types, research listing, GAPS schema and data budget are shared: BRAIN_CERT_KIT_V1 P17)."""
    ls = sorted(n for n in os.listdir(os.path.join(CLARITY, "runtime")) if n != "__pycache__")
    assert ls == ["brain_platform.py", "catalog.json", "clarity_brain.py", "knowledge-release.json", "publish_artifact.py", "run.py"]     # + the release manifest (BR-11)


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
    assert not [k for k in legacy_updates if k.lstrip("/").startswith("scores")]                              # C1 writes no score (the shared score proof P19 also runs score_baseline --check)



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


# ===================================================================================================== domain remainders of proofs now shared in BRAIN_CERT_KIT_V1
def test_brain_slot_and_display_name_are_stable():
    from sector_brain_platform.keys import BRAINS
    assert BRAINS["water-clarity"][0] == cb.SLOT == "waterClarity"
    cm = load("jobs", "brain_platform", "sector_brain_platform", "control_manifest.json")["brains"]["water-clarity"]
    assert cm["displayName"] == "Water Clarity"


def test_the_freshness_threshold_is_the_existing_26_hours():
    cm = load("jobs", "brain_platform", "sector_brain_platform", "control_manifest.json")["brains"]["water-clarity"]
    assert cm["freshness"]["staleAfterHours"] == cb.STALE_AFTER_H == 26


def test_a_new_engine_evaluation_is_a_new_input_but_run_clock_fields_are_not(legacy_updates):
    base = build(legacy_updates, n=1)
    new_input = copy.deepcopy(legacy_updates)
    new_input["lakes/Guntersville_AL/states/waterClarity"]["evaluationTime"] = "2026-10-14T05:00:00Z"
    assert build(new_input, n=2).artifact["lineage"]["inputFingerprint"] != base.artifact["lineage"]["inputFingerprint"]


def test_the_snapshot_compatibility_copy_is_publisher_derived_in_the_plan(legacy_updates):
    st, publish = rig()
    assert publish(build(legacy_updates).artifact).result is Result.SHADOW_READY
    plan = st.sink.submitted[-1][0]
    assert any(k.startswith("snapshots/") and k.endswith("/latest/waterClarity") for k in plan.updates)
