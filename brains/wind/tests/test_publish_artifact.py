"""Wind -> Publisher V2 SHADOW (publish-artifact-v2, bundle wind-publication-v1). Local only: in-memory/tmp stores, no network, no live system.

Real Wind output comes from the UNCHANGED publish() against a DryRunWriter; its PATCHes are re-expressed as ONE sealed bundle and sent through the
Publisher's own handoff (ArtifactWriter -> authenticated API signal -> evaluate_reference). Publisher code is imported, never re-implemented; the
registry is the Publisher's own (no Wind-side volatile or ownership list is injected)."""
import copy
import dataclasses
import itertools
import socket
from datetime import datetime, timedelta, timezone

import pytest

from sector_wind.brain import artifact as A
from sector_wind.brain import contract as C
from sector_wind.brain.publish import publish
from sector_wind.brain.writer import DryRunWriter
from test_brain import CFG, DIRECTORY, NOW, make_store

from sector_brain_platform.publisher import default_registry, local_shadow_stack
from sector_brain_platform.publisher.api import AllowlistAuthorizer, Caller, OrchestratorApi
from sector_brain_platform.publisher.artifact import section_fingerprint
from sector_brain_platform.publisher.canonical import bundle_fingerprint
from sector_brain_platform.publisher.compat import LEGACY_PATH_TABLE
from sector_brain_platform.publisher.registry import WIND_BUNDLE, WIND_HEALTH_DOMAIN_CHILDREN, WIND_REGISTRY_CHILDREN

T = datetime(2026, 10, 15, 3, 0, tzinfo=timezone.utc)
iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
uuid4 = lambda n: f"{n:08x}-0000-4000-8000-{n:012x}"
LAKE = "Guntersville_AL"
LIVE_SEC = ("wind-lake-state-v1", "lake-live")
REG_SEC = ("wind-registry-v1", "default")


class Authn:
    def authenticate(self, cred):
        return Caller("wind-brain-identity") if cred == "wind-token" else None


class Rig:
    def __init__(self, tmp_path=None):
        self.ids = itertools.count(1)
        self.st = local_shadow_stack(tmp_path, registry=default_registry(), clock=lambda: T + timedelta(hours=2), id_factory=lambda: uuid4(next(self.ids) + 50000))
        self.api = OrchestratorApi(Authn(), AllowlistAuthorizer({"wind-brain-identity": {"ARTIFACT": {"SUBMIT_ARTIFACT@wind"}}}), self.st.dispatcher)
        self.n = itertools.count(900)

    def submit(self, art):
        ref = self.st.writer("wind").write(art)
        body = {"apiVersion": "orchestrator-api-v1", "requestId": uuid4(next(self.n)), "requestKind": "ARTIFACT", "brainId": "wind", "action": "SUBMIT_ARTIFACT",
                "params": {"artifactId": ref.artifact_id, "artifactRef": ref.location, "artifactSha256": ref.sha256, "executionId": ref.execution_id,
                           "expectedSchema": ref.expected_schema}}
        return self.api.handle("wind-token", body), ref


@pytest.fixture(scope="module")
def patches(tmp_path_factory):
    st = make_store(tmp_path_factory.mktemp("store"))
    w = DryRunWriter()
    rep = publish(st, CFG, w, now=NOW, run_summary={"runAt": C.iso(NOW), "errors": [], "seconds": 90}, directory=DIRECTORY)
    assert rep["ok"], rep["errors"]
    return w.patches


def ctx(minutes=0, n=1):
    return A.BuildContext(generated_at=iso(T + timedelta(minutes=minutes)), execution_id=uuid4(1000 + n), code_version="abc123def456")


def build(patches, minutes=0, n=1, removals=(), mutate=None):
    pp = copy.deepcopy(patches)
    if mutate:
        mutate(pp)
    return A.build_artifacts(pp, ctx(minutes, n), removals=removals)


def sections(art):
    return {(s["artifactSchema"], s.get("scope", "default")): s for s in art["sections"]}


def reseal(art):
    """Recompute the sealed identity of a hand-modified artifact exactly the way the Publisher does (tests only)."""
    reg = default_registry()
    fps = [(s["artifactSchema"], s.get("scope", "default"), section_fingerprint(reg.spec(s["artifactSchema"]), "wind", s["mutations"])) for s in art["sections"]]
    art["lineage"]["outputFingerprint"] = bundle_fingerprint("wind", art["lineage"]["artifactSchema"], fps)
    art["lineage"].pop("artifactId", None)
    art["lineage"]["artifactId"] = A.sha(art)
    return art


def mut(art, key, path):
    return next(m for m in sections(art)[key]["mutations"] if m["path"] == path)


def _paths(art):
    return {m["path"] for s in art["sections"] for m in s["mutations"]}


# 1, 2, 3 ---- ONE run -> ONE v2 bundle, correct sections, stable identity ------------------------------------------------------------------------
def test_one_run_produces_one_v2_bundle_and_one_publisher_plan(patches, tmp_path):
    res = build(patches)
    art = res.artifact
    assert len(res.artifacts) == 1 and art["envelope"] == "publish-artifact-v2" and art["lineage"]["artifactSchema"] == WIND_BUNDLE      # 1
    assert set(sections(art)) == {LIVE_SEC, ("wind-lake-state-v1", "lake-static"), ("wind-lake-state-v1", "fleet-readiness"), REG_SEC,
                                  ("wind-source-registry-v1", "default")}                                                                  # 2
    assert "mutations" not in art
    rig = Rig(tmp_path)
    r, _ = rig.submit(art)
    assert r.status == 200 and r.result["result"] == "SHADOW_READY" and r.result["live"] is False and r.result["mode"] == "SHADOW"
    assert len(rig.st.sink.submitted) == 1 and rig.st.sink.live_mutations == 0                                                              # ONE sink call, ONE plan
    plan = rig.st.sink.submitted[0][0]
    assert [k for k in plan.updates if k.endswith("/publication")] == ["brains/wind/publication"]                                           # ONE publication record
    rec = rig.st.history.get_record("wind", r.result["publishId"])
    assert len(rig.st.history.records("wind")) == 1 and rec["status"] == "SHADOW" and "publishedAt" not in rec
    assert {(s["artifactSchema"], s["scope"]) for s in rec["sections"]} == set(sections(art))


def test_execution_and_lineage_identity_is_stable(patches):
    a, b = build(patches), build(copy.deepcopy(patches))
    assert A.canonical(a.artifact) == A.canonical(b.artifact)                                                                                # 3
    lin = a.artifact["lineage"]
    assert lin["executionId"] == uuid4(1001) and lin["brainId"] == "wind" and lin["artifactId"].startswith("sha256:") and lin["codeVersion"] == "abc123def456"
    assert lin["knowledgeRelease"] == lin["manifestRef"] == lin["manifestSha256"] == "NONE"
    assert (lin["lifecycle"], lin["reviewStatus"], lin["validationStatus"]) == ("CALIBRATION", "UNREVIEWED", "NOT_VALIDATED")
    c = build(patches, minutes=5, n=2).artifact["lineage"]
    assert c["executionId"] != lin["executionId"] and c["outputFingerprint"] == lin["outputFingerprint"] and c["artifactId"] != lin["artifactId"]
    fr = sections(a.artifact)[LIVE_SEC]["freshness"]
    assert fr["freshnessStatus"] == "FRESH" and "evidenceObservedAt" in fr and "staleAfter" in fr and "expiresAt" not in fr


def test_integrity_hash_semantic_fingerprint_and_publication_metadata_are_distinct(patches):
    rig = Rig()
    art = build(patches).artifact
    r, ref = rig.submit(art)
    rec = rig.st.history.get_record("wind", r.result["publishId"])
    assert ref.sha256 != art["lineage"]["outputFingerprint"] and rec["outputFingerprint"] == art["lineage"]["outputFingerprint"]
    assert rec["publishId"] not in A.canonical(art).decode()


# 4, 5, 6, 7 ---- Wind no longer authors retired paths --------------------------------------------------------------------------------------
def test_wind_no_longer_authors_snapshot_identity_or_job_health_paths(patches):
    res = build(patches)
    p = _paths(res.artifact)
    assert not any(x.startswith("/snapshots") for x in p)                                                                                    # 4
    assert not any(x.endswith("/lakeId") for x in p)                                                                                         # 5
    assert not any(x.startswith("/health/jobs") for x in p)                                                                                  # 6
    assert not any(x.startswith("/health/brains/wind/") and x.rsplit("/", 1)[-1] not in WIND_HEALTH_DOMAIN_CHILDREN for x in p)
    assert {"/health/brains/wind/status", "/health/brains/wind/staleLakeCount"} <= p                                                         # 7
    by = {d["row"]: d for d in res.dropped}
    assert {"snapshot-wind", "snapshot-brainversions-wind", "lakefleet-lakeid", "snapshot-lakeid", "health-jobs-wind-hourly", "health-brains-wind-process"} <= set(by)
    assert res.unsupported == []
    assert by["snapshot-wind"]["mechanism"] == "PUBLISHER_DERIVED" and by["lakefleet-lakeid"]["mechanism"] == "STOP_WRITING"
    assert by["health-jobs-wind-hourly"]["targetOwner"] == "Orchestrator"


def test_publisher_derives_the_snapshot_compatibility_copy_from_authorised_source(patches):
    rig = Rig()
    rig.submit(build(patches).artifact)
    plan = rig.st.sink.submitted[0][0]
    assert plan.derived_keys and all(k.endswith("/latest/wind") or k.endswith("/brainVersions/wind") for k in plan.derived_keys)
    for k in (c for c in plan.derived_keys if c.endswith("/latest/wind")):
        lake = k.split("/")[1]
        assert plan.updates[k] == plan.updates[f"lakes/{lake}/states/wind"]


@pytest.mark.parametrize("path,code", [
    (f"/snapshots/{LAKE}/latest/wind", "PLATFORM_DERIVED_PATH"), (f"/snapshots/{LAKE}/latest/brainVersions/wind", "PLATFORM_DERIVED_PATH"),
    (f"/snapshots/{LAKE}/latest/lakeId", None), (f"/lakeFleet/{LAKE}/lakeId", None), ("/health/jobs/wind-hourly", None),
    ("/health/brains/wind/lastRun", None), ("/health/brains/wind/durationMs", None), ("/health/brains/wind/deployedVersion", None),
    ("/brains/wind/publication", "RESERVED_PATH"), ("/brains/wind", "BRAIN_NODE_REPLACEMENT"), ("/brains/wind/someUnapprovedChild", "PATH_NOT_AUTHORIZED"),
    ("/speciesProfiles/common_carp", "CROSS_DOMAIN_PATH"), ("/species/common_carp", "CROSS_DOMAIN_PATH"), (f"/lakes/{LAKE}/speciesPresence", "CROSS_DOMAIN_PATH"),
    (f"/lakes/{LAKE}/states/waterTemp", "CROSS_DOMAIN_PATH"), (f"/lakes/{LAKE}/states/waterClarity", "CROSS_DOMAIN_PATH"),
    (f"/lakes/{LAKE}/states/depth", "CROSS_DOMAIN_PATH"), (f"/lakes/{LAKE}/states/lake", "CROSS_DOMAIN_PATH"),
    ("/brains/biological-state/status", "CROSS_DOMAIN_PATH"), ("/scores/wind", "CROSS_DOMAIN_PATH"), ("/control/overview", "CROSS_DOMAIN_PATH")])
def test_wind_cannot_author_retired_or_foreign_paths_and_the_whole_bundle_rejects(patches, path, code):
    rig = Rig()
    art = build(patches).artifact
    sections(art)[REG_SEC]["mutations"].append({"op": "SET", "path": path, "value": {"x": 1}})
    reseal(art)
    r, _ = rig.submit(art)
    assert r.result["result"] == "REJECTED" and r.result["live"] is False                                                                    # 15
    if code:
        assert code in r.result["codes"]
    assert rig.st.sink.submitted == [] and rig.st.history.head("wind", "wind-lake-state-v1", "lake-live") is None


# 8, 9, 10 ---- SKIP, volatility, material evidence -----------------------------------------------------------------------------------------
def test_unchanged_semantic_bundle_skips_and_volatile_execution_metadata_never_forces_publication(patches):
    rig = Rig()
    assert rig.submit(build(patches, 0, 1).artifact)[0].result["result"] == "SHADOW_READY"
    same = build(patches, 60, 2).artifact
    r, _ = rig.submit(same)
    assert r.result["result"] == "SKIP" and len(rig.st.sink.submitted) == 1                                                                   # 8
    heads = {s: rig.st.history.head("wind", *s) for s in sections(same)}
    drift = build(patches, 120, 3).artifact
    for s in drift["sections"]:
        for m in s["mutations"]:
            v = m["value"] if m["op"] == "SET" else None
            if isinstance(v, dict):
                for k, nv in (("inputAgeHours", 9.9), ("lastFetchAt", "2026-10-15T09:00:00Z"), ("latencyMs", 12345), ("generatedAt", "2026-10-15T09:00:00Z"),
                              ("durationMs", 77), ("checkedAt", "2026-10-15T09:00:00Z")):
                    if k in v:
                        v[k] = nv
                if "inputAgeHours" in (v.get("provenance") or {}):
                    v["provenance"]["inputAgeHours"] = 9.9
            if m["path"] in ("/brains/wind/updatedAt", "/brains/wind/lastSuccessfulRun"):
                m["value"] = "2026-10-15T09:00:00Z"
    reseal(drift)
    r, _ = rig.submit(drift)
    assert r.result["result"] == "SKIP" and len(rig.st.sink.submitted) == 1                                                                   # 9
    assert {s: rig.st.history.head("wind", *s) for s in sections(same)} == heads


def test_material_evidence_time_change_publishes_and_only_the_changed_section_is_in_the_plan(patches):
    rig = Rig()
    rig.submit(build(patches, 0, 1).artifact)
    ch = build(patches, 60, 2).artifact
    next(m for m in sections(ch)[LIVE_SEC]["mutations"] if m["path"].endswith("/states/wind"))["value"]["observationTime"] = "2026-10-15T03:10:00Z"
    reseal(ch)
    r, _ = rig.submit(ch)
    assert r.result["result"] == "SHADOW_READY" and len(rig.st.sink.submitted) == 2                                                          # 10
    plan = rig.st.sink.submitted[-1][0]
    rec = rig.st.history.get_record("wind", r.result["publishId"])
    res = {(s["artifactSchema"], s["scope"]): s["result"] for s in rec["sections"]}
    assert res[LIVE_SEC] == "SHADOW" and [v for k, v in res.items() if k != LIVE_SEC] == ["SKIP"] * 4
    assert not any(k.startswith("sources/") or k == "brains/wind/version" for k in plan.updates)


# 11, 12, 13 ---- explicit typed DELETE; null/missing never deletes -------------------------------------------------------------------------
def _err_patches(patches, on):
    pp = copy.deepcopy(patches)
    for p in pp:
        if "brains/wind" in p:
            p["brains/wind"]["lastError"] = {"at": "2026-10-12T06:20:00Z", "message": "boom"} if on else None
    return pp


def test_last_error_cleared_is_an_explicit_typed_delete_and_idempotent(patches):
    rig = Rig()
    healthy = A.build_artifacts(patches, ctx(0, 1))
    assert healthy.deletes == [{"path": "/brains/wind/lastError", "reason": "OPTIONAL_CHILD_CLEARED"}]                                        # 11
    assert mut(healthy.artifact, REG_SEC, "/brains/wind/lastError") == {"op": "DELETE", "path": "/brains/wind/lastError", "reason": "OPTIONAL_CHILD_CLEARED"}
    err = A.build_artifacts(_err_patches(patches, True), ctx(30, 2))
    assert err.deletes == [] and mut(err.artifact, REG_SEC, "/brains/wind/lastError")["op"] == "SET"
    assert rig.submit(err.artifact)[0].result["result"] == "SHADOW_READY"
    r, _ = rig.submit(A.build_artifacts(_err_patches(patches, False), ctx(60, 3)).artifact)
    assert r.result["result"] == "SHADOW_READY"
    plan = rig.st.sink.submitted[-1][0]
    assert plan.updates["brains/wind/lastError"] is None and plan.deletes == ("brains/wind/lastError",)
    assert rig.submit(A.build_artifacts(_err_patches(patches, False), ctx(90, 4)).artifact)[0].result["result"] == "SKIP"


def test_lake_removals_use_the_closed_reasons_and_derive_the_snapshot_delete(patches):
    rig = Rig()
    rig.submit(build(patches, 0, 1).artifact)
    rem = [{"path": f"/lakes/{LAKE}/states/wind", "reason": "LAKE_LEFT_FLEET"}, {"path": f"/lakeFleet/{LAKE}/slots/wind", "reason": "LAKE_LEFT_FLEET"},
           {"path": f"/lakes/{LAKE}/validation/wind", "reason": "EVIDENCE_REMOVED"}]

    def drop_lake(pp):
        for p in pp:
            for k in [k for k in p if LAKE in k and (k.startswith("lakes/") and k.endswith(("states/wind", "validation/wind")) or k.endswith("slots/wind"))]:
                del p[k]
    res = build(patches, 60, 2, removals=rem, mutate=drop_lake)
    assert len(res.deletes) == 4 - 1 + 0 or len(res.deletes) >= 3
    r, _ = rig.submit(res.artifact)
    assert r.result["result"] == "SHADOW_READY"
    plan = rig.st.sink.submitted[-1][0]
    assert {f"lakes/{LAKE}/states/wind", f"lakeFleet/{LAKE}/slots/wind", f"lakes/{LAKE}/validation/wind"} <= set(plan.deletes)
    assert plan.updates[f"snapshots/{LAKE}/latest/wind"] is None                                                                              # derived target deleted with its source


def test_missing_or_null_never_becomes_a_delete(patches):
    base = A.merge_patches(copy.deepcopy(patches))
    base[f"lakes/{LAKE}/validation/wind"] = None                                                                                              # legacy "null-on-miss"
    base[f"lakes/{LAKE}/profiles/wind"] = {"a": None, "b": []}
    del base["brains/wind"]["lastError"]                                                                                                      # key absent: nothing happens
    res = A.build_artifacts([base], ctx())
    assert res.deletes == []                                                                                                                  # 12
    assert f"/lakes/{LAKE}/validation/wind" not in _paths(res.artifact) and f"/lakes/{LAKE}/profiles/wind" not in _paths(res.artifact)
    assert res.omitted_unknown >= 2
    rig = Rig()
    assert rig.submit(res.artifact)[0].result["result"] == "SHADOW_READY" and rig.st.sink.submitted[0][0].deletes == ()
    for bad in (None, {"a": None}, {}, []):
        art = build(patches, 5, 9).artifact
        sections(art)[LIVE_SEC]["mutations"][0]["value"] = bad
        reseal(art)
        rr, _ = Rig().submit(art)
        assert rr.result["result"] == "FAILED_VALIDATION" and rr.result["codes"][0] in ("NULL_VALUE", "NULL_IN_VALUE", "EMPTY_VALUE")
    with pytest.raises(A.ArtifactBuildError):
        A.build_artifacts([{f"lakes/{LAKE}/states/wind": {"hourly": [None, 1]}}], ctx())


@pytest.mark.parametrize("rem,why", [
    ([{"path": f"/lakes/{LAKE}/states/wind", "reason": "BECAUSE"}], "reason not in vocabulary"),
    ([{"path": f"/lakes/{LAKE}/states/wind", "reason": "OPTIONAL_CHILD_CLEARED"}], "registry reason on a lake path"),
    ([{"path": f"/lakes/{LAKE}/states", "reason": "LAKE_LEFT_FLEET"}], "parent node, not an exact child"),
    ([{"path": f"/lakes/{LAKE}", "reason": "LAKE_LEFT_FLEET"}], "whole lake"),
    ([{"path": "/brains/wind", "reason": "OPTIONAL_CHILD_CLEARED"}], "whole registry"),
    ([{"path": "/brains/wind/publication", "reason": "OPTIONAL_CHILD_CLEARED"}], "Publisher-owned"),
    ([{"path": "/sources/noaa-nbm-v5", "reason": "EVIDENCE_REMOVED"}], "no delete family on sources"),
    ([{"path": "/speciesProfiles/common_carp", "reason": "LAKE_LEFT_FLEET"}], "foreign domain"),
    ([{"path": f"/snapshots/{LAKE}/latest/wind", "reason": "LAKE_LEFT_FLEET"}], "derived target is the Publisher's")])
def test_invalid_delete_is_rejected_by_the_builder_and_by_the_publisher(patches, rem, why):
    with pytest.raises(A.ArtifactBuildError):
        build(patches, removals=rem)
    art = build(patches).artifact                                                                                                             # bypass the builder: the Publisher still refuses
    sections(art)[REG_SEC]["mutations"] += [{"op": "DELETE", "path": r["path"], "reason": r["reason"]} for r in rem]
    reseal(art)
    r, _ = Rig().submit(art)
    assert r.result["result"] in ("REJECTED", "FAILED_VALIDATION"), why


# 14 ---- publication metadata is not Brain-authored ----------------------------------------------------------------------------------------
def test_publication_metadata_is_publisher_owned(patches):
    assert not any("publication" in p or "certification" in p for p in _paths(build(patches).artifact))
    for op in ({"op": "SET", "path": "/brains/wind/publication", "value": {"publishId": "forged"}},
               {"op": "DELETE", "path": "/brains/wind/publication", "reason": "OPTIONAL_CHILD_CLEARED"},
               {"op": "SET", "path": "/brains/wind/publication/publishId", "value": "forged"}, {"op": "SET", "path": "/brains/wind/certification", "value": {"s": 1}}):
        art = build(patches).artifact
        sections(art)[REG_SEC]["mutations"].append(op)
        reseal(art)
        r, _ = Rig().submit(art)
        assert r.result["result"] == "REJECTED" and "RESERVED_PATH" in r.result["codes"]


# 16 ---- ordering: an older changed section rejects the whole artifact ---------------------------------------------------------------------------
def test_older_changed_section_rejects_the_whole_artifact(patches):
    rig = Rig()
    rig.submit(build(patches, 60, 1).artifact)
    older = build(patches, 0, 2).artifact
    next(m for m in sections(older)[LIVE_SEC]["mutations"] if m["path"].endswith("/states/wind"))["value"]["sustainedMph"] = 77.7
    mut(older, REG_SEC, "/brains/wind/status")["value"] = "DEGRADED"
    reseal(older)
    r, _ = rig.submit(older)
    assert r.result["result"] == "REJECTED" and "ARTIFACT_OLDER_THAN_BASELINE" in r.result["codes"]
    assert len(rig.st.sink.submitted) == 1                                                                                                     # the changed registry section did NOT publish either
    assert rig.st.history.head("wind", "wind-registry-v1", "default")["generatedAt"] == iso(T + timedelta(minutes=60))


# identity / reference / hash ------------------------------------------------------------------------------------------------------------
def test_identity_schema_lineage_hash_and_fingerprint_are_verified(patches):
    rig = Rig()
    art = build(patches).artifact
    foreign = copy.deepcopy(art)
    foreign["lineage"]["brainId"] = "biological-state"
    with pytest.raises(Exception):
        rig.st.writer("wind").write(foreign)
    unknown = copy.deepcopy(art)
    unknown["lineage"]["artifactSchema"] = "wind-secret-v9"; unknown["lineage"]["artifactId"] = "sha256:" + "01" * 32
    assert rig.submit(unknown)[0].result["codes"] == ["UNKNOWN_SCHEMA"]
    broken = copy.deepcopy(art)
    del broken["lineage"]["codeVersion"]; broken["lineage"]["artifactId"] = "sha256:" + "02" * 32
    assert "LINEAGE_INCOMPLETE" in rig.submit(broken)[0].result["codes"]
    tampered = copy.deepcopy(art)
    sections(tampered)[LIVE_SEC]["mutations"][0]["value"] = {"x": 1}; tampered["lineage"]["artifactId"] = "sha256:" + "03" * 32
    assert "FINGERPRINT_MISMATCH" in rig.submit(tampered)[0].result["codes"]
    ref = rig.st.writer("wind").write(art)
    assert "ARTIFACT_HASH_MISMATCH" in rig.st.publisher.evaluate_reference(dataclasses.replace(ref, sha256="sha256:" + "ee" * 32)).codes
    assert rig.st.sink.submitted == []


# 17 ---- zero live write -------------------------------------------------------------------------------------------------------------------
def test_full_flow_is_zero_live_write_and_opens_no_socket(patches, monkeypatch):
    def no_net(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket, "socket", no_net)
    monkeypatch.setattr(socket, "create_connection", no_net)
    rig = Rig()
    assert rig.submit(build(patches).artifact)[0].result["result"] == "SHADOW_READY" and rig.st.sink.live_mutations == 0


# ownership / equivalence at the builder level ---------------------------------------------------------------------------------------------
def test_ownership_and_fingerprint_logic_come_from_the_publisher_not_from_wind(patches):
    kids = {m["path"].split("/")[3] for m in sections(build(patches).artifact)[REG_SEC]["mutations"] if m["path"].startswith("/brains/wind/")}
    assert kids <= {c for g in WIND_REGISTRY_CHILDREN.values() for c in g}
    src = open(A.__file__).read()
    assert "REGISTRY_CHILDREN" not in src and "WIND_VOLATILE" not in src and "output_fingerprint" not in src and "bundle_fingerprint" not in src
    assert len({r.id for r in LEGACY_PATH_TABLE}) == len(LEGACY_PATH_TABLE)


def test_authored_values_equal_what_the_legacy_writer_stores(patches):
    flat = A.merge_patches(patches)
    res = build(patches)
    pub = {m["path"]: m["value"] for s in res.artifact["sections"] for m in s["mutations"] if m["op"] == "SET"}
    dropped = {d["path"] for d in res.dropped}
    for key, val in flat.items():
        items = [(f"/{key}/{c}", v) for c, v in val.items()] if key in ("brains/wind", "health/brains/wind") else [("/" + key, val)]
        for p, v in items:
            n = A.normalize(v)
            if p in dropped:
                continue
            if n is A._ABSENT:
                assert p not in pub, p
            else:
                assert pub[p] == n, p


def test_no_score_is_changed_by_the_builder(patches):
    art = build(patches).artifact
    reg = {m["path"]: m["value"] for m in sections(art)[REG_SEC]["mutations"] if m["op"] == "SET"}
    assert reg["/brains/wind/scores"] == A.merge_patches(patches)["brains/wind"]["scores"]
    assert not any(p.startswith("/scores") for p in _paths(art))


# equivalence (Publisher F-9 evaluator) against the legacy writer's own output --------------------------------------------------------------
def _rtdb_view(v):
    """The tree as RTDB stores it (null keys and empty containers vanish); DryRunStore keeps raw Nones."""
    if isinstance(v, dict):
        return {k: x for k, x in ((k, _rtdb_view(x)) for k, x in v.items()) if x not in (None, {}, [])}
    if isinstance(v, list):
        return [x for x in (_rtdb_view(i) for i in v) if x not in (None, {}, [])]
    return v


def test_equivalence_with_the_legacy_writer_output_has_only_expected_differences():
    from sector_brain_platform.publisher.equivalence import evaluate_equivalence, render_target
    import tempfile
    w = DryRunWriter()
    publish(make_store(tempfile.mkdtemp()), CFG, w, now=NOW, run_summary={"runAt": C.iso(NOW), "errors": [], "seconds": 90}, directory=DIRECTORY)
    reg = default_registry()
    art = A.build_artifacts(w.patches, ctx()).artifact
    tgt = render_target(art, reg)
    assert tgt["result"] == "SHADOW_READY" and tgt["derivedKeys"]
    ev = evaluate_equivalence(_rtdb_view(w.tree), tgt["updates"], registry=reg, derived_keys=tgt["derivedKeys"])
    assert ev["verdict"] == "EQUIVALENT_WITH_EXPECTED_DIFFS" and ev["blocking"] == []
    s = ev["summary"]
    assert s["SEMANTIC_MISMATCH"] == 0 and s["UNKNOWN"] == 0 and s["TARGET_ONLY"] == 0 and s["MATCH"] > 1000
    assert set(ev["openCompatibilityRules"]) == {"health-jobs-wind-hourly", "health-brains-wind-process"}                  # what the Orchestrator must still provide at cutover
    rules = {(d["class"], d["rule"]) for d in ev["differences"]}
    assert rules <= {("EXPECTED_MIGRATION_DIFF", "PUBLISHER_METADATA"), ("EXPECTED_MIGRATION_DIFF", "lakefleet-lakeid"), ("EXPECTED_MIGRATION_DIFF", "snapshot-lakeid"),
                     ("LEGACY_ONLY", "health-jobs-wind-hourly"), ("LEGACY_ONLY", "health-brains-wind-process"), ("VOLATILE_ONLY", "volatile-contract")}
    # negative controls: the evaluator is not vacuous
    bad = dict(tgt["updates"])
    k = next(x for x in bad if x.endswith("/states/wind"))
    bad[k] = {**bad[k], "sustainedMph": 99.9}
    assert evaluate_equivalence(_rtdb_view(w.tree), bad, registry=reg, derived_keys=tgt["derivedKeys"])["verdict"] == "NOT_EQUIVALENT"
    tree = _rtdb_view(w.tree)
    tree["brains"]["wind"]["mysteryField"] = 1
    ev2 = evaluate_equivalence(tree, tgt["updates"], registry=reg, derived_keys=tgt["derivedKeys"])
    assert ev2["verdict"] == "NOT_EQUIVALENT" and ev2["summary"]["UNKNOWN"] + ev2["summary"]["SEMANTIC_MISMATCH"] >= 1
