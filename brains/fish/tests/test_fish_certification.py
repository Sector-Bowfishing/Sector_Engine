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


# ===================================================================================================== 3-4 brain.json, brainId


# ===================================================================================================== 5 ownership boundaries
def test_ownership_boundaries_in_the_declared_contract():
    paths = BRAIN["publishes"][0]["pathFamilies"]
    forbidden = ("speciesPresence", "speciesProfiles", "/lakes/", "/snapshots/", "/scores", "publication", "certification", "/legal", "regulation")
    assert not [p for p in paths if any(f in p for f in forbidden)]
    contract = open(os.path.join(FISH, "BRAIN_OPERATING_CONTRACT.md")).read()
    for owner_line in ("species identity", "legality", "Lake Brain", "Species Registry"):
        assert owner_line in contract


# ===================================================================================================== 6-7 declared dependencies, no fake signals


# ===================================================================================================== 8-11 artifact: schema, determinism, fingerprint


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


# ===================================================================================================== 18-19 Publisher accepts / rejects


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
    assert sorted(os.listdir(os.path.join(FISH, "research"))) == ["CHARTER.json", "GAPS.json", "README.md"]
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


# ===================================================================================================== domain remainders of proofs now shared in BRAIN_CERT_KIT_V1
def test_display_name_and_directory_differ_from_the_machine_id_by_design():
    assert BRAIN["displayName"] == "Fish Brain" and os.path.basename(FISH) == "fish" and BRAIN["brainId"] == "biological-state"


def test_species_knowledge_is_version_driven_so_the_artifact_invents_no_freshness():
    art = build().artifact
    assert "lastSuccessfulRun" in json.dumps(art) and not [s for s in art["sections"] if "freshness" in s]      # shared P10 proves nothing is derived from lastSuccess
