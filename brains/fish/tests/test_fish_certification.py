"""Fish Brain (biological-state) architecture certification tests — Fish Structural Certification V1.

These prove STRUCTURE: location, declaration, ownership, artifact contract, lineage, health representation, Publisher compatibility, write isolation,
runtime/research separation and science-neutrality of the migration. They prove nothing about the biology (that stays NOT_VALIDATED).
Synthetic data only; offline; no network; no production write.
"""
import ast
import copy
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys

import pytest

import fish_support as S
from fish_support import FISH, REPO, RUNTIME, build, make_bundle, rig, sealed, updates_for

import biological_brain as bb
import publish_artifact as pa
from sector_brain_platform import ConsumptionRecorder, DryRunStore, brain_health as BH, dependency_declarations as DD
from sector_brain_platform.publisher import PublisherMode, Result, default_registry

sys.path.insert(0, os.path.join(REPO, "tools", "architecture"))
import jsonschema_lite  # noqa: E402


def load(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as fh:
        return json.load(fh)


BRAIN = load("brains", "fish", "brain.json")


def walk_files(root, exts=None):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ("__pycache__", ".git", "node_modules", ".pytest_cache", "out")]
        for f in fn:
            if exts is None or f.endswith(exts):
                yield os.path.join(dp, f)


# ===================================================================================================== 1-2 canonical location, ONE implementation
def test_canonical_package_location_and_shape():
    for p in ("brain.json", "BRAIN_OPERATING_CONTRACT.md", "README.md", "contracts/fish-publication-v1.json", "runtime/run.py", "runtime/biological_brain.py",
              "runtime/publish_artifact.py", "tests", "research/README.md", "research/GAPS.json"):
        assert os.path.exists(os.path.join(FISH, p)), p
    assert load("tools", "architecture", "stable_brain_ids.json")["directoryToBrainId"]["fish"] == "biological-state"


def test_exactly_one_production_fish_implementation():
    """No second copy of the Fish modules anywhere in the repository; the legacy job directory is a pointer README only."""
    marks = ("biological_brain.py", "bio_state.py", "publish_artifact.py", "capability.py", "rules.py")
    found = [os.path.relpath(p, REPO) for p in walk_files(REPO, ".py") if os.path.basename(p) in ("biological_brain.py", "bio_state.py", "capability.py", "movement_outlook.py")]
    assert sorted(found) == sorted(f"brains/fish/runtime/{m}" for m in ("biological_brain.py", "bio_state.py", "capability.py", "movement_outlook.py")), found
    assert os.listdir(os.path.join(REPO, "jobs", "biological-brain")) == ["README.md"]
    assert "RETIRED" in open(os.path.join(REPO, "jobs", "biological-brain", "README.md")).read()
    assert marks  # documentation of what a duplicate would look like


# ===================================================================================================== 3-4 brain.json, brainId
def test_brain_json_validates_and_identity_is_the_stable_machine_id():
    schema = load("contracts", "schemas", "brain.schema.json")
    assert jsonschema_lite.validate(BRAIN, schema) == []
    assert BRAIN["brainId"] == "biological-state" and BRAIN["displayName"] == "Fish Brain"
    assert os.path.basename(FISH) == "fish"                                       # directory != machine id, by design
    assert BRAIN["lifecycle"] == "PROFILED"                                       # never promoted by having a contract
    assert BRAIN["publisherRequired"] == {"required": True, "cutoverStatus": "SHADOW"}   # NOT CUTOVER_COMPLETE: no Publisher production write
    assert BRAIN["customerIntegrationMode"] == "none"
    assert BRAIN["score"]["path"] == "/scores/biological-state"


# ===================================================================================================== 5 ownership boundaries
def test_ownership_boundaries_in_the_declared_contract():
    paths = BRAIN["publishes"][0]["pathFamilies"]
    forbidden = ("speciesPresence", "speciesProfiles", "/lakes/", "/snapshots/", "/scores", "publication", "certification", "/legal", "regulation")
    assert not [p for p in paths if any(f in p for f in forbidden)]
    contract = open(os.path.join(FISH, "BRAIN_OPERATING_CONTRACT.md")).read()
    for owner_line in ("species identity", "legality", "Lake Brain", "Species Registry"):
        assert owner_line in contract


# ===================================================================================================== 6-7 declared dependencies, no fake signals
def test_declared_dependencies_validate_and_match_what_the_runtime_really_consumes():
    assert BRAIN["consumes"] == [] and BRAIN["providers"] == []
    brains = DD.load_registered_brains(REPO)
    rows = DD.resolve(DD.declared_dependencies(brains["biological-state"]), brains=brains, signals={}, providers=DD.load_providers(REPO))
    assert rows == []
    manifest = json.load(open(os.path.join(REPO, "jobs", "brain_platform", "sector_brain_platform", "control_manifest.json")))
    assert manifest["brains"]["biological-state"]["dependencies"] == []
    assert DD.drift(brains, manifest) == []                                       # the platform claims no edge Fish does not declare
    g = DD.dependency_graph(brains, manifest=manifest, signals={}, providers=DD.load_providers(REPO))
    assert g["brains"]["biological-state"]["source"] == "brain.json" and g["brains"]["biological-state"]["declarationsKnown"] is True
    assert not [w for w in g["warnings"] if "biological-state" in w]


def test_no_fabricated_signal_declarations():
    signals = {s["signalId"] for s in load("platform", "registries", "signals", "signals.json")["signals"]}
    assert signals and not [c for c in BRAIN["consumes"] if c["kind"] == "signal"]
    blob = json.dumps(BRAIN)
    assert not [s for s in signals if s in blob], "Fish declares no signal: none may appear in brain.json"
    # and no runtime code consumes a Signal Registry signal by id
    runtime_src = "\n".join(open(p, encoding="utf-8").read() for p in walk_files(RUNTIME, ".py"))
    assert not [s for s in signals if f'"{s}"' in runtime_src or f"'{s}'" in runtime_src]


# ===================================================================================================== 8-11 artifact: schema, determinism, fingerprint
def test_artifact_is_publisher_valid_and_deterministic():
    st, publish = rig()
    r1 = build(n=1)
    assert r1.artifact["envelope"] == "publish-artifact-v2" and r1.artifact["lineage"]["artifactSchema"] == "fish-publication-v1"
    res = publish(r1.artifact)
    assert res.result is Result.SHADOW_READY and res.codes == [] and res.mode is PublisherMode.SHADOW
    again = build(n=1)
    assert json.dumps(r1.artifact, sort_keys=True) == json.dumps(again.artifact, sort_keys=True)          # no clock, no randomness


def test_semantic_fingerprint_ignores_execution_identity_and_per_run_timestamps():
    base = build(n=1)
    fp = base.artifact["lineage"]["outputFingerprint"]
    other_exec = build(n=2, generated_at="2026-10-13T03:00:00Z")                                          # new executionId + generatedAt
    assert other_exec.artifact["lineage"]["outputFingerprint"] == fp
    next_day = build(n=3, now=S.NOW + dt.timedelta(days=1, hours=5), generated_at="2026-10-13T23:00:00Z")  # updatedAt / lastSuccessfulRun / versions[].date all move
    assert next_day.artifact["lineage"]["outputFingerprint"] == fp
    baseline = updates_for(make_bundle())["/brains/biological-state"]
    rerun = build(n=5, now=S.NOW + dt.timedelta(days=2), generated_at="2026-10-14T18:00:00Z", published=baseline)      # a re-run after the baseline: no version event is emitted at all
    assert rerun.artifact["lineage"]["outputFingerprint"] == fp
    with_consumed = build(n=4, consumed=[])                                                               # lineage never enters the fingerprint
    assert with_consumed.artifact["lineage"]["outputFingerprint"] == fp
    assert base.artifact["lineage"]["inputFingerprint"] == other_exec.artifact["lineage"]["inputFingerprint"] == next_day.artifact["lineage"]["inputFingerprint"]


def test_real_domain_change_changes_the_fingerprint_and_unchanged_republish_is_skipped():
    st, publish = rig()
    first = publish(build(n=1).artifact)
    assert first.result is Result.SHADOW_READY
    baseline = updates_for(make_bundle())["/brains/biological-state"]
    same = publish(build(n=2, now=S.NOW + dt.timedelta(days=1), generated_at="2026-10-13T18:00:00Z", published=baseline).artifact)
    assert same.result is Result.SKIP                                                                     # new run, same material -> nothing to publish
    p = S.T.synthetic_profile(); p["knowledge"]["domains"]["dayNightMovement"].update(score=2, status="SCORED")
    p["knowledge"]["overallExact"] = round(sum(d["score"] * d["weight"] for d in p["knowledge"]["domains"].values()) / 100, 2)
    p["knowledge"]["overallRounded"] = bb.round_half(p["knowledge"]["overallExact"])
    changed = make_bundle([p, S.T.not_assessed()], research_version="0000-00-00.2")
    art = build(changed, n=3, now=S.NOW + dt.timedelta(days=2), generated_at="2026-10-14T12:00:00Z").artifact
    assert art["lineage"]["outputFingerprint"] != build(n=1).artifact["lineage"]["outputFingerprint"] and art["lineage"]["knowledgeRelease"] == "0000-00-00.2"
    assert publish(art).result is Result.SHADOW_READY


# ===================================================================================================== 12, 14 lineage, nothing fabricated
def test_lineage_is_complete_truthful_and_never_fabricated():
    b = make_bundle()
    lin = build(b, n=1).artifact["lineage"]
    assert lin["brainId"] == "biological-state" and lin["lifecycle"] == "PROFILED" and lin["reviewStatus"] == "UNREVIEWED" and lin["validationStatus"] == "NOT_VALIDATED"
    assert lin["knowledgeRelease"] == b.research_version and lin["manifestSha256"] == "sha256:" + b.pointer["manifestSha256"]
    assert lin["manifestRef"] == updates_for(b)["/brains/biological-state"]["manifestRef"]
    for k in ("codeVersion", "executionId", "inputFingerprint", "outputFingerprint", "generatedAt"):
        assert lin[k]
    art = build(b, n=1).artifact
    assert "consumed" not in art                                                                           # no recorder => UNKNOWN, not []
    assert all("freshness" not in s for s in art["sections"])                                              # species knowledge is version-driven: no invented freshness
    assert "artifactId" not in lin                                                                         # assigned by the ArtifactWriter, never invented here


def test_review_and_validation_status_are_never_optimistic():
    b = make_bundle()
    assert pa.review_status(b) == "UNREVIEWED" and pa.validation_status(b) == "NOT_VALIDATED"
    # even if a (refused-by-the-runtime) reviewed species appeared, the helper cannot report VALIDATED unless every assessed species is
    b.profiles["example_fish"]["researchMaturity"] = "REVIEWED"
    assert pa.review_status(b) == "REVIEWED" and pa.validation_status(b) == "NOT_VALIDATED"


# ===================================================================================================== 13 actual consumption capture
def test_actual_consumption_capture_works_for_instrumented_reads():
    r = ConsumptionRecorder("biological-state", clock=lambda: S.NOW)
    db = DryRunStore({"brains": {"biological-state": {"version": "x"}, "water-temp": {"version": "wt1", "freshness": {"generatedAt": "2026-10-12T17:00:00Z"}}},
                      "species": {"a": {}}, "snapshots": {"G": {"latest": {"waterTemperature": {"provenance": {"generatedAt": "2026-10-12T17:30:00Z", "brainVersion": "wt2"}}}}}},
                     "biological-state", recorder=r)
    db.get("brains/biological-state"); db.get("species", shallow=True)                                     # what run.py reads: its OWN nodes
    assert db.consumed() == []                                                                             # recorded: read nothing that is a dependency (own state is never a dependency)
    db.get("snapshots/G/latest")                                                                           # what the pilot reads: another Brain's published slot
    ids = {e["dependencyId"]: e for e in db.consumed()}
    assert "brain:water-temp" in ids and ids["brain:water-temp"]["consumedAt"] == "2026-10-12T18:00:00Z"
    art = build(consumed=db.consumed()).artifact
    assert [c["dependencyId"] for c in art["consumed"]] == sorted(ids)                                    # carried verbatim, validated by the Publisher (below)
    st, publish = rig()
    assert publish(art).result is Result.SHADOW_READY


def test_pilot_runner_records_what_it_reads(tmp_path, monkeypatch, capsys):
    import brain_platform as bp
    import run_state
    holder = {}

    def fake_rtdb(url, tokens, brain_id=None, recorder=None):
        holder["db"] = DryRunStore({"snapshots": {"Guntersville_AL": {"latest": {"waterTemperature": {"provenance": {"generatedAt": "2026-10-12T17:30:00Z", "brainVersion": "wt2"}}}}},
                                    "lakes": {"Guntersville_AL": {"speciesPresence": {}}}}, brain_id, recorder=recorder)
        return holder["db"]
    monkeypatch.setattr(bp, "BrainRtdb", fake_rtdb)
    monkeypatch.setattr(bp, "TokenProvider", lambda *a, **k: object())
    rules = tmp_path / "rules"; rules.mkdir()
    (rules / "rules_manifest.json").write_text(json.dumps({"schemaVersion": 1, "rulesVersion": "synthetic", "files": {}, "retired": []}))
    try:
        run_state.main(["--lake", "Guntersville|AL", "--rules", str(rules), "--live", "--now", "2026-10-12T18:00:00Z", "--out", str(tmp_path / "out")])
    except Exception:
        pass                                                                                               # the synthetic ruleset may not satisfy every loader check; the READ is what is asserted
    assert holder["db"].recorder is not None and any(e["dependencyId"] == "brain:water-temp" for e in holder["db"].consumed())


def test_offline_artifact_carries_no_consumed_key_not_an_empty_one(tmp_path):
    out = tmp_path / "out"; d = tmp_path / "b"; d.mkdir()
    S.T.write_bundle(str(d), [S.T.synthetic_profile()])
    import run
    assert run.main(["--dry-run", "--offline", "--bundle", str(d), "--out", str(out)]) == 0
    art = json.load(open(out / "artifact.json"))
    assert "consumed" not in art and art["lineage"]["knowledgeRelease"] == "0000-00-00.1"


# ===================================================================================================== 15-17 healthV1, UNKNOWN semantics, freshness
def _health(executions=None, **kw):
    brains = DD.load_registered_brains(REPO)
    declared = DD.declared_dependencies(brains["biological-state"])
    return BH.brain_health("biological-state", declared=declared, declarations_known=True, executions=executions, observations={}, now=S.NOW, **kw)


def test_health_v1_can_represent_fish_from_engine_truth_alone():
    h = _health()
    assert h["brainId"] == "biological-state" and h["dependencies"]["declared"] == 0 and h["dependencies"]["dependencyHealth"] == "SATISFIED"
    assert h["dependencies"]["basis"] == "CURRENT_STATE" and h["dependencies"]["declaredVsActual"]["consumptionRecorded"] is False


def test_unknown_stays_unknown_and_last_successful_run_is_not_evidence_freshness():
    ok = [{"executionId": S.uid(1), "brainId": "biological-state", "status": "SUCCEEDED", "startedAt": "2026-10-12T17:00:00Z", "finishedAt": "2026-10-12T17:01:00Z"}]
    h = _health(ok)
    assert h["freshness"]["status"] == "UNKNOWN"                                                           # a recent successful run does NOT make evidence FRESH
    assert "freshness" in h["aggregate"].get("unknownComponents", [])
    assert h["process"]["processHealth"] in ("HEALTHY", "UNKNOWN")                                          # process health is its own axis
    # a recorded execution that consumed an undeclared dependency surfaces as drift, never as silence
    ex = dict(ok[0], consumed=[{"dependencyId": "brain:wind", "dependencyType": "BRAIN", "consumedAt": "2026-10-12T17:00:30Z"}])
    h2 = _health([ex])
    assert h2["dependencies"]["declaredVsActual"]["consumedNotDeclared"] == ["brain:wind"]


def test_no_freshness_is_derived_from_last_successful_run_anywhere_in_fish():
    for p in walk_files(RUNTIME, ".py"):
        src = open(p, encoding="utf-8").read()
        for m in re.finditer(r"freshness[^\n]*lastSuccess|lastSuccess[^\n]*(freshUntil|staleAfter|expiresAt|freshnessStatus)", src):
            pytest.fail(f"{os.path.relpath(p, REPO)}: evidence freshness derived from lastSuccess: {m.group(0)[:100]}")
    art = build().artifact
    assert "lastSuccessfulRun" in json.dumps(art) and not [s for s in art["sections"] if "freshness" in s]


# ===================================================================================================== 18-19 Publisher accepts / rejects
def test_publisher_is_shadow_only_and_end_to_end_handoff_works():
    assert {m.name for m in PublisherMode} == {"SHADOW", "DRY_RUN"}                                         # no live mode exists
    from sector_brain_platform.publisher.api import AllowlistAuthorizer, Caller, OrchestratorApi

    class Authn:
        def authenticate(self, cred):
            return Caller("fish-brain-identity") if cred == "fish-token" else None
    st, _ = rig()
    api = OrchestratorApi(Authn(), AllowlistAuthorizer({"fish-brain-identity": {"ARTIFACT": {"SUBMIT_ARTIFACT@biological-state"}}}), st.dispatcher)
    art = build().artifact
    ref = st.writer("biological-state").write(art)
    body = {"apiVersion": "orchestrator-api-v1", "requestId": S.uid(700), "requestKind": "ARTIFACT", "brainId": "biological-state", "action": "SUBMIT_ARTIFACT",
            "params": {"artifactId": ref.artifact_id, "artifactRef": ref.location, "artifactSha256": ref.sha256, "executionId": ref.execution_id, "expectedSchema": ref.expected_schema}}
    r = api.handle("fish-token", body)
    assert r.status == 200 and r.result["result"] == "SHADOW_READY" and r.result["live"] is False
    assert st.sink.live_mutations == 0
    plan = st.sink.submitted[-1][0]
    assert "brains/biological-state/publication" in plan.updates                                            # the Publisher's own record, in the same single plan
    owned = [k for k in plan.updates if not k.startswith(("species/", "brains/biological-state", "validation/biological-state", "health/brains/biological-state", "activity/"))]
    assert owned == []


@pytest.mark.parametrize("path,code", [
    ("/lakes/Guntersville_AL/speciesPresence", "CROSS_DOMAIN_PATH"),            # Lake Brain owns per-lake species presence
    ("/speciesProfiles/example_fish", "CROSS_DOMAIN_PATH"),                      # species profile root belongs to the species registry/profile owner
    ("/brains/wind/status", "CROSS_DOMAIN_PATH"),                                # another Brain's node
    ("/scores/biological-state", "CROSS_DOMAIN_PATH"),                           # Platform writes scores
    ("/brains/biological-state/publication", "RESERVED_PATH"),                   # Publisher-owned
    ("/brains/biological-state/certification", "RESERVED_PATH"),
    ("/brains/biological-state", "BRAIN_NODE_REPLACEMENT"),                      # never the whole node
    ("/health/jobs/biological-brain", "CROSS_DOMAIN_PATH"),                      # execution health is Orchestrator-owned
    ("/species/example_fish/profile", "PATH_NOT_AUTHORIZED"),                    # Species Intelligence Profile publication needs its own reviewed registration (and is not "foreign" to Fish)
    ("/lakeFleet/Guntersville_AL/slots/biology", "PATH_NOT_AUTHORIZED"),         # no per-lake publication: the Biological State is not a product yet
    ("/control/orchestratorV1", "CROSS_DOMAIN_PATH"),
])
def test_publisher_rejects_wrong_path_ownership(path, code):
    st, publish = rig()
    res = publish(sealed([{"op": "SET", "path": "/brains/biological-state/status", "value": "PROFILED"}, {"op": "SET", "path": path, "value": {"x": 1}}]))
    assert res.result is Result.REJECTED and code in res.codes, res.codes
    assert st.sink.submitted == []


def test_publisher_rejects_wrong_brain_and_wrong_schema_ownership():
    st, publish = rig()
    fish_art = build().artifact
    # a Fish artifact submitted under another Brain's identity
    ref = st.writer("wind").write(copy.deepcopy(dict(fish_art, lineage=dict(fish_art["lineage"], brainId="wind"))))
    r = st.publisher.evaluate_reference(ref)
    assert r.result is Result.REJECTED and ("SCHEMA_BRAIN_MISMATCH" in r.codes or "UNKNOWN_SCHEMA" in r.codes)
    # a Wind-owned wind-lake-state schema claimed by Fish
    bad = copy.deepcopy(fish_art); bad["lineage"]["artifactSchema"] = "wind-publication-v1"
    assert publish(bad).result is Result.REJECTED
    # a Fish section whose mutation targets another section's family
    wrong = sealed([{"op": "SET", "path": "/species/example_fish", "value": {"a": 1}}], schema="fish-registry-v1")
    assert publish(wrong).result is Result.REJECTED
    # Wind cannot touch /species
    from sector_brain_platform.publisher import seal_bundle
    wind_try = seal_bundle(brain_id="wind", bundle_id="wind-publication-v1", sections=[{"artifactSchema": "wind-registry-v1", "mutations": [{"op": "SET", "path": "/species/example_fish", "value": {"a": 1}}]}],
                           lifecycle="CALIBRATION", review_status="UNREVIEWED", validation_status="NOT_VALIDATED", generated_at="2026-10-12T18:00:00Z", execution_id=S.uid(11),
                           code_version="t", input_fingerprint="sha256:" + "ab" * 32, registry=default_registry())
    assert publish(wind_try, brain="wind").result is Result.REJECTED


def test_publisher_requires_a_real_release_and_refuses_production_lifecycles_for_fish():
    st, publish = rig()
    art = build().artifact
    none_release = copy.deepcopy(art); none_release["lineage"].update(knowledgeRelease="NONE", manifestRef="NONE", manifestSha256="NONE")
    assert publish(none_release).result is Result.FAILED_VALIDATION
    prod = copy.deepcopy(art); prod["lineage"]["lifecycle"] = "PRODUCTION"
    r = publish(prod)
    assert r.result is Result.REJECTED and "LIFECYCLE_NOT_AUTHORIZED" in r.codes


def test_deletes_are_typed_and_null_is_never_an_implicit_delete():
    st, publish = rig()
    b = make_bundle()
    up = updates_for(b, existing={"retired_fish"})
    assert up["/species/retired_fish"] is None
    art = pa.build_artifact(up, b, S.ctx(1)).artifact
    muts = [m for s in art["sections"] for m in s["mutations"]]
    assert {"op": "DELETE", "path": "/species/retired_fish", "reason": "SPECIES_REMOVED_FROM_REGISTRY"} in muts
    assert publish(art).result is Result.SHADOW_READY
    # optional child cleared: only when the baseline still has it
    pub = dict(updates_for(b)["/brains/biological-state"], coverageMatrix={"x": 1})
    art2 = pa.build_artifact(updates_for(b), b, S.ctx(2), published=pub).artifact
    assert {"op": "DELETE", "path": "/brains/biological-state/coverageMatrix", "reason": "OPTIONAL_CHILD_CLEARED"} in [m for s in art2["sections"] for m in s["mutations"]]
    # a raw null SET is refused by the builder and by the Publisher
    with pytest.raises(pa.ArtifactBuildError):
        pa.build_artifact(dict(up, **{"/validation/biological-state": {"status": None}}), b, S.ctx(3))
    nul = sealed([{"op": "SET", "path": "/brains/biological-state/status", "value": None}])
    assert publish(nul).result is Result.FAILED_VALIDATION


def test_every_registry_child_the_runtime_emits_is_covered_by_the_contract():
    b = make_bundle()
    emitted = set(updates_for(b)["/brains/biological-state"])
    from sector_brain_platform.publisher.registry import FISH_REGISTRY_CHILDREN
    covered = {c for g in FISH_REGISTRY_CHILDREN.values() for c in g}
    assert emitted <= covered, f"registry children without a contract entry: {sorted(emitted - covered)}"
    assert not ({"publication", "certification"} & covered)
    # the legacy health record's process fields are dropped, not published
    dropped = {d["path"].rsplit("/", 1)[1] for d in build().dropped}
    assert dropped == {"lastRun", "lastSuccess", "durationMs", "errorCount", "deployedVersion", "publishMode"}


# ===================================================================================================== 20 direct-write audit
WRITE_METHODS = {"update", "put", "patch", "post", "set", "delete"}
FORBIDDEN_IMPORTS = ("firebase_admin", "requests", "google.cloud", "pyrebase")
ALLOWED_LEGACY_WRITE = {("run.py", "rtdb.update")}          # LEGACY: ownership-checked platform client; RETIREMENT_CANDIDATE at Publisher cutover


def _calls(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in WRITE_METHODS:
            yield n.func.attr, ast.unparse(n.func), n.lineno


def test_no_unauthorized_production_write_in_the_fish_runtime():
    sites = set()
    for p in walk_files(RUNTIME, ".py"):
        rel = os.path.relpath(p, RUNTIME)
        src = open(p, encoding="utf-8").read()
        assert not [m for m in FORBIDDEN_IMPORTS if re.search(rf"^\s*(import|from)\s+{re.escape(m)}", src, re.M)], rel
        assert not re.search(r"method\s*=\s*['\"](PATCH|PUT|POST|DELETE)['\"]", src), f"{rel}: direct REST write"
        for attr, full, line in _calls(p):
            if full.split(".")[0] in ("os", "json", "shutil") or full.endswith(("updates.update", "up.update", "out.update", "summary.update", "d.update", "_cache.update")):
                continue                                                   # dict/json/os helpers, not a database client
            if attr == "update" and full.endswith("rtdb.update"):
                sites.add((rel, "rtdb.update"))
    assert sites == ALLOWED_LEGACY_WRITE, f"unexpected database write sites: {sorted(sites ^ ALLOWED_LEGACY_WRITE)}"


def test_the_artifact_path_cannot_write_anything(tmp_path):
    """publish_artifact.py is pure (no I/O, no network, no clock, no randomness, no environment); run.py's artifact path only builds/evaluates in memory."""
    tree = ast.parse(open(os.path.join(RUNTIME, "publish_artifact.py"), encoding="utf-8").read())
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not imported & {"urllib", "requests", "subprocess", "random", "uuid", "time", "socket", "os", "shutil", "tempfile", "http"}, imported
    src = ast.unparse(tree)
    for token in ("open(", "datetime.now", "utcnow", ".environ"):
        assert token not in src, token
    d = tmp_path / "b"; d.mkdir()
    S.T.write_bundle(str(d), [S.T.synthetic_profile()])
    import run
    assert run.main(["--dry-run", "--offline", "--bundle", str(d), "--out", str(tmp_path / "o")]) == 0     # offline: no rtdb object exists at all


def test_write_path_remains_ownership_checked_and_fish_cannot_write_foreign_or_customer_roots():
    from sector_brain_platform.ownership import OwnershipError, assert_owned
    b = make_bundle()
    assert_owned(updates_for(b), "biological-state")
    for bad in ("/lakes/G/speciesPresence/gar", "/scores/biological-state", "/brains/wind/version", "/speciesProfiles/x", "/control/orchestratorV1", "/snapshots/G/latest/waterTemperature"):
        with pytest.raises(OwnershipError):
            assert_owned({bad: {"x": 1}}, "biological-state")
    import run
    with pytest.raises(Exception):
        run.bp.BrainRtdb("https://example-app-prod-default-rtdb.firebaseio.com", object(), brain_id="biological-state")      # the platform client refuses anything but the Brain RTDB


# ===================================================================================================== 21-23 runtime isolation, research separation
LOCAL_PATH = re.compile(r"/Users/|/home/[a-z]|\bDesktop/|Sector[ _]Research|Sector_Research_Data|~/|expanduser|SECTOR_RESEARCH_ROOT|fish-brain/(sources|datasets|analysis)")


def test_no_local_mac_research_or_cache_paths_in_fish_runtime():
    bad = []
    for p in walk_files(RUNTIME, (".py", ".json", ".sh", ".txt")):
        for i, line in enumerate(open(p, encoding="utf-8").read().splitlines(), 1):
            if LOCAL_PATH.search(line) and "LEAK_TEXT" not in line and "concatenated" not in line:
                bad.append(f"{os.path.relpath(p, REPO)}:{i}")
    assert not bad, bad


def test_runtime_works_with_no_research_workspace_no_home_and_no_repo_docs(tmp_path):
    d = tmp_path / "b"; d.mkdir()
    S.T.write_bundle(str(d), [S.T.synthetic_profile(), S.T.not_assessed()])
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path / "nohome"), "PYTHONPATH": "", "PYTHONDONTWRITEBYTECODE": "1"}
    stage = tmp_path / "stage" / "jobs"                       # the orchestrator-image layout: only runtime + platform, NO docs/, NO research
    import shutil
    shutil.copytree(RUNTIME, stage / "biological-brain", ignore=shutil.ignore_patterns("__pycache__", "out"))
    shutil.copytree(os.path.join(REPO, "jobs", "brain_platform"), stage / "brain_platform", ignore=shutil.ignore_patterns("__pycache__", "tests"))
    r = subprocess.run([sys.executable, "run.py", "--dry-run", "--offline", "--bundle", str(d), "--out", str(tmp_path / "out")], cwd=stage / "biological-brain", env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    summary = json.loads(r.stdout)
    assert summary["publisher"]["result"] == "SHADOW_READY" and summary["publisher"]["live"] is False
    assert os.path.exists(tmp_path / "out" / "artifact.json")


def test_research_is_separate_from_the_production_package():
    allowed_runtime_ext = {".py", ".json", ".md"}
    odd = [os.path.relpath(p, FISH) for p in walk_files(os.path.join(FISH, "runtime")) if os.path.splitext(p)[1] not in allowed_runtime_ext]
    assert not odd, odd
    json_outside_schemas = [os.path.relpath(p, FISH) for p in walk_files(os.path.join(FISH, "runtime"), ".json") if f"{os.sep}schemas{os.sep}" not in p]
    assert not json_outside_schemas, json_outside_schemas                         # no data files in the runtime package
    assert sorted(os.listdir(os.path.join(FISH, "research"))) == ["GAPS.json", "README.md"]
    gaps = load("brains", "fish", "research", "GAPS.json")
    assert jsonschema_lite.validate(gaps, load("contracts", "schemas", "research-gaps.schema.json")) == []
    assert BRAIN["researchWorkspace"] == {"workspaceId": "fish-brain"}            # a LOGICAL id; never a physical path
    big = [p for p in walk_files(FISH) if os.path.getsize(p) >= BRAIN["dataBudget"]["maxTrackedFileBytes"]]
    assert not big


def test_no_per_lake_species_presence_labels_or_private_locations_in_the_public_package():
    rx = re.compile(r"biology/v1/releases/|\"presenceState\"\s*:\s*\"(established|historical|stocked)\"")
    for p in [q for q in walk_files(FISH, (".py", ".json", ".md")) if os.sep + "tests" + os.sep not in q]:       # tests carry SYNTHETIC fixtures that mimic the shape
        for i, line in enumerate(open(p, encoding="utf-8").read().splitlines(), 1):
            if rx.search(line):
                pytest.fail(f"{os.path.relpath(p, REPO)}:{i}: private location / presence label")


# ===================================================================================================== 24-25 science + species identity preserved
GOLDEN = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden", "fish_science_baseline.json")))


def h(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@pytest.mark.parametrize("name", ["two_species", "three_species"])
def test_existing_fish_science_output_is_byte_identical_to_the_pre_migration_tree(name):
    """The golden was produced by the PRE-MOVE tree (jobs/biological-brain at 80bc2ff0, before any Fish certification change) on the same synthetic bundles."""
    T = S.T
    profiles = {"two_species": [T.synthetic_profile(), T.not_assessed()],
                "three_species": [T.synthetic_profile("alpha_fish", [6, 5, 4, 3, 2, 1, 0, 2]), T.synthetic_profile("beta_fish", [1, 2, 3, 4, 5, 6, 7, 8]), T.not_assessed("gamma_group")]}[name]
    b = make_bundle(profiles)
    up = bb.build_updates(b, now=S.NOW, uri_root="local:x", deployment="t@1", descriptor=S.orch.DESCRIPTOR, duration_ms=5, published=None, existing_species={"gone_fish"}, event_id=S.EVENT_ID)
    g = GOLDEN[name]
    assert h(up) == g["updates"] and sorted(up) == g["paths"]
    assert {k: h(v) for k, v in sorted(up.items()) if k.startswith("/species/") and v} == g["species"]
    assert h(up["/brains/biological-state"]) == g["registry"] and h(up["/validation/biological-state"]) == g["validation"] and h(up["/health/brains/biological-state"]) == g["health"]
    assert S.orch.plan(None, b.pointer, bb.BRAIN_VERSION) == g["plan"] and h(S.orch.DESCRIPTOR) == g["descriptor"]
    up2 = bb.build_updates(b, now=S.NOW, uri_root="local:x", deployment="t@1", descriptor=S.orch.DESCRIPTOR, duration_ms=5, published=None, existing_species=set(), event_id=None, include_profiles=True)
    w = g["withProfiles"]
    assert h(up2) == w["updates"] and {k: h(v.get("profile")) for k, v in sorted(up2.items()) if k.startswith("/species/") and v} == w["profiles"]
    assert h(up2["/brains/biological-state"].get("coverageMatrix")) == w["coverage"]


def test_species_identity_semantics_pass_through_verbatim_and_fish_does_not_own_identity_or_presence():
    b = make_bundle([S.T.synthetic_profile(), S.T.not_assessed()])
    up = updates_for(b)
    node = up["/species/example_fish"]
    prof = b.profiles["example_fish"]
    for k in ("speciesId", "displayName", "scientificName", "aliases", "appKeys", "taxonomyStatus"):
        assert node[k] == prof[k], k                                              # identity fields are passed through, never renamed/merged/recomputed
    assert sorted(k.rsplit("/", 1)[1] for k in up if k.startswith("/species/") and up[k]) == sorted(b.profiles)     # no species added/removed/merged
    assert not [k for k in up if "speciesPresence" in k or k.startswith("/speciesProfiles")]
    assert not [c for c in BRAIN["consumes"] if c.get("registry") == "species"]    # Fish does not read the Species Registry today, so it does not declare it
    assert "legal" not in json.dumps(node).lower() or "policyNote" in node         # legality is policy-layer; only a reference note may travel


# ===================================================================================================== 26 registered-Brain architecture gates
def test_registered_brain_architecture_gates_pass_for_fish_with_no_new_violations():
    import report                                                             # tools/architecture/report.py (path added above)
    own = [f for f in report.check(REPO, legacy=False) if "brains/fish" in f["subject"]]
    # the only registered-Brain findings are the published-label strings carried from the legacy job (same retirement condition as Wind's two)
    assert all(f["invariant"] == 8 and os.path.basename(f["subject"]) in ("biological_brain.py", "brain_platform.py") for f in own), own
    legacy = report.check(REPO, legacy=True)
    baseline = json.load(open(os.path.join(REPO, "tools", "architecture", "baseline", "legacy_violations.json")))
    known, new, resolved = report.compare_to_baseline(legacy, baseline)
    assert new == [] and resolved == [], (new, resolved)                       # NO NEW architecture violations; nothing silently dropped from the baseline
    carried = [e for e in baseline["entries"] if e["path"].startswith("brains/fish/")]
    assert {os.path.basename(e["path"]) for e in carried} == {"biological_brain.py", "brain_platform.py"} and all(e.get("carriedFrom") for e in carried)
