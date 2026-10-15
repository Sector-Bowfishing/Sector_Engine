"""Publisher V1 (shadow): validation, authorization, fingerprints, SKIP / SHADOW_READY, plan, records. Requirement numbers refer to the task list."""
import copy
import json

import pytest

from publisher_fixtures import LAKE_A, LAKE_B, T0, iso, make, rebuild, uuid4, wind_artifact, wind_state
from sector_brain_platform.ownership import path_allowed
from sector_brain_platform.publisher import (PathFamily, PublisherMode, Registry, Result, SchemaSpec, UnknownProducer, canonical_bytes, default_registry,
                                             output_fingerprint, wind_specs)

WIND_LAKE = f"/lakes/{LAKE_A}/states/wind"
SHA0 = "sha256:" + "00" * 32


def run(art, **kw):
    pub, hist, sink = make()
    return pub.evaluate(art, producer="wind", **kw), pub, hist, sink


# 1 -----------------------------------------------------------------------------------------------------------------------------------------
def test_valid_wind_artifact_is_accepted_and_shadow_ready():
    r, _, _, sink = run(wind_artifact())
    assert r.result is Result.SHADOW_READY and r.violations == [] and r.live_mutations == 0
    assert len(sink.submitted) == 1 and sink.live_mutations == 0
    assert r.record["status"] == "SHADOW" and r.record["live"] is False and "publishedAt" not in r.record      # never claims a publication


# 2 -----------------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("raw", [None, [], "x", 5, {}, {"envelope": "nope"}, {"envelope": "publish-artifact-v1", "lineage": {"brainId": "wind"}, "mutations": []},
                                 {"envelope": "publish-artifact-v1", "lineage": {"brainId": "wind"}, "mutations": [{"op": "SET"}]},
                                 {"envelope": "publish-artifact-v1", "lineage": {"brainId": "wind"}, "mutations": [{"op": "MERGE", "path": "/a"}]}])
def test_malformed_artifacts_are_rejected(raw):
    r, *_ = run(raw)
    assert r.is_rejection and r.result is Result.FAILED_VALIDATION and r.plan is None


def test_unknown_envelope_key_and_extra_mutation_keys_are_malformed():
    a = wind_artifact(); a["sneaky"] = 1
    assert run(a)[0].codes == ["MALFORMED"]
    a = wind_artifact(); a["mutations"][0]["force"] = True
    assert run(a)[0].codes == ["MALFORMED"]


# 3 -----------------------------------------------------------------------------------------------------------------------------------------
def test_unknown_brain_id_is_rejected():
    a = wind_artifact(); a["lineage"]["brainId"] = "not-a-brain"
    r, *_ = run(a)
    assert r.result is Result.REJECTED and r.codes == ["UNKNOWN_BRAIN"]


def test_submitter_must_match_artifact_brain_identity():
    pub, *_ = make()
    r = pub.evaluate(wind_artifact(), producer="water-temp")
    assert r.codes == ["IDENTITY_MISMATCH"] and r.result is Result.REJECTED


def test_unregistered_producer_is_an_error_not_a_result():
    pub, *_ = make()
    with pytest.raises(UnknownProducer):
        pub.evaluate(wind_artifact(), producer="evil")


# 4 -----------------------------------------------------------------------------------------------------------------------------------------
def test_unknown_schema_is_rejected():
    r, *_ = run(wind_artifact(artifactSchema="wind-made-up-v9"))
    assert r.result is Result.REJECTED and r.codes == ["UNKNOWN_SCHEMA"]


def test_schema_of_another_brain_is_rejected():
    spec = SchemaSpec("water-temp-state-v1", "water-temp", (PathFamily("/lakes/{k}/states/waterTemp"),))
    pub, *_ = make(registry=Registry(wind_specs() + [spec]))
    r = pub.evaluate(wind_artifact(artifactSchema="water-temp-state-v1"), producer="wind")
    assert r.codes == ["SCHEMA_BRAIN_MISMATCH"]


def test_other_registered_brains_have_no_schema_yet():
    pub, *_ = make()
    a = wind_artifact(brainId="biological-state", artifactSchema="biological-species-profile-v1")
    assert pub.evaluate(a, producer="biological-state").codes == ["UNKNOWN_SCHEMA"]


# 5 -----------------------------------------------------------------------------------------------------------------------------------------
def test_missing_lineage_is_rejected():
    a = wind_artifact(); del a["lineage"]
    r, *_ = run(a)
    assert r.is_rejection and r.codes == ["LINEAGE_MISSING"]


@pytest.mark.parametrize("field", ["knowledgeRelease", "manifestRef", "manifestSha256", "codeVersion", "executionId", "inputFingerprint", "outputFingerprint",
                                   "generatedAt", "lifecycle", "reviewStatus", "validationStatus", "schema"])
def test_incomplete_lineage_is_rejected(field):
    a = wind_artifact(); del a["lineage"][field]
    r, *_ = run(a)
    assert r.is_rejection and r.codes == ["LINEAGE_INCOMPLETE"], field


@pytest.mark.parametrize("field,bad", [("executionId", "not-a-uuid"), ("generatedAt", "yesterday"), ("inputFingerprint", "abc"), ("artifactId", "x"),
                                       ("manifestSha256", "sha256:short"), ("schema", "brain-lineage-v0")])
def test_ill_formed_lineage_values_are_rejected(field, bad):
    a = wind_artifact(); a["lineage"][field] = bad
    assert run(a)[0].codes == ["LINEAGE_INCOMPLETE"]


def test_release_triplet_must_be_all_none_or_all_declared_and_resolve():
    assert run(wind_artifact(knowledgeRelease="wind-model-v1@c6f6232e"))[0].codes == ["LINEAGE_INCOMPLETE"]
    ok = dict(knowledgeRelease="wind-model-v1@c6f6232e", manifestRef="gs://private-bucket/releases/r1/manifest.json", manifestSha256="sha256:" + "cd" * 32)
    pub, *_ = make(release_resolver=lambda rel, ref, sha: False)
    assert pub.evaluate(wind_artifact(**ok), producer="wind").codes == ["RELEASE_UNRESOLVED"]
    pub, *_ = make(release_resolver=lambda rel, ref, sha: True)
    assert pub.evaluate(wind_artifact(**ok), producer="wind").result is Result.SHADOW_READY


# 6, 7, 8 -----------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("path", ["/lakes/test_lake_alpha/states/waterTemp", "/lakes/test_lake_alpha/speciesPresence", "/speciesProfiles/common_carp",
                                  "/species/common_carp", "/scores/wind", "/scores/engine", "/control/orchestratorV1/summary", "/jobs/wind-hourly",
                                  "/access/someone", "/brains/biological-state/registry", "/brains/water-temp/x", "/validation/biological-state",
                                  "/health/brains/depth", "/snapshots/test_lake_alpha/latest/depth", "/lakes/test_lake_alpha/brain", "/lakes/test_lake_alpha/states/lake"])
def test_wind_cannot_target_other_domains(path):
    a = wind_artifact(mutations=[{"op": "SET", "path": WIND_LAKE, "value": wind_state()}, {"op": "SET", "path": path, "value": {"x": 1}}])
    r, *_ = run(a)
    assert r.result is Result.REJECTED and r.codes == ["CROSS_DOMAIN_PATH"], (path, r.violations)
    assert r.plan is None


def test_fish_path_submitted_as_wind_is_rejected_and_names_the_owner():
    a = wind_artifact(mutations=[{"op": "SET", "path": "/speciesProfiles/common_carp", "value": {"commonName": "Common carp"}}])
    r, *_ = run(a)
    assert r.codes == ["CROSS_DOMAIN_PATH"] and "species" in r.violations[0]["detail"]


@pytest.mark.parametrize("path", ["/lakes/test_lake_alpha/states/wind/extra", "/lakes/test_lake_alpha/states", "/lakes", "/", "/lakes//states/wind",
                                  "/lakes/a.b/states/wind", "lakes/x/states/wind", "/lakes/x/states/wind/", "/lakes/../scores/wind", "/lakes/bad key/states/wind",
                                  "/sources/usgs-nwis-00010", "/sources/tva-restapi", "/health/sources/open-meteo-forecast", "/activity/2026-10-15-water-temp-x",
                                  "/brains/wind", "/brains", "/brains/wind/publication", "/brains/wind/publication/status", "/brains/wind/certification"])
def test_paths_outside_the_wind_families_fail_closed(path):
    a = wind_artifact(mutations=[{"op": "SET", "path": path, "value": {"x": 1}}])
    r, *_ = run(a)
    assert r.is_rejection and r.plan is None, path


def test_wind_may_target_its_own_registry_sources_health_and_activity_via_their_schemas():
    pub, *_ = make()
    reg = [{"op": "SET", "path": "/brains/wind/lastSuccessfulRun", "value": "2026-10-15T03:00:00Z"}, {"op": "SET", "path": "/validation/wind", "value": {"s": 1}},
           {"op": "SET", "path": "/health/brains/wind", "value": {"status": "HEALTHY"}}, {"op": "SET", "path": "/activity/2026-10-15T03-wind-run", "value": {"k": 1}}]
    a = wind_artifact(artifactSchema="wind-registry-v1", mutations=reg)
    assert pub.evaluate(a, producer="wind").result is Result.SHADOW_READY
    src = [{"op": "SET", "path": "/sources/noaa-nbm-v5", "value": {"s": 1}}, {"op": "SET", "path": "/health/sources/iem-metar-wind", "value": {"s": 1}}]
    assert pub.evaluate(wind_artifact(n=2, artifactSchema="wind-source-registry-v1", mutations=src), producer="wind").result is Result.SHADOW_READY


def test_a_schema_cannot_borrow_another_schemas_paths():
    a = wind_artifact(mutations=[{"op": "SET", "path": "/health/brains/wind", "value": {"status": "HEALTHY"}}])      # lake-state schema
    assert run(a)[0].codes == ["PATH_NOT_AUTHORIZED"]


def test_registered_wind_families_agree_with_the_live_ownership_table():
    """Defence in depth: nothing the Publisher authorises for Wind may be refused by the existing writer-side ownership check."""
    samples = [f"/lakes/{LAKE_A}/states/wind", f"/lakes/{LAKE_A}/profiles/wind", f"/lakes/{LAKE_A}/validation/wind", f"/lakeFleet/{LAKE_A}/slots/wind",
               f"/lakeFleet/{LAKE_A}/readiness/wind", f"/lakeFleet/{LAKE_A}/modelVersions/wind", f"/snapshots/{LAKE_A}/latest/wind",
               "/brains/wind/lastSuccessfulRun", "/validation/wind", "/health/brains/wind", "/activity/2026-10-15T03-wind-run", "/sources/noaa-nbm-v5",
               "/health/sources/noaa-rtma-ru"]
    reg = default_registry()
    for p in samples:
        authorised = any(reg.authorizing_family(s, p) for s in map(reg.spec, reg.schemas_for("wind")))
        assert authorised and path_allowed("wind", p.lstrip("/")), p


def test_reserved_publisher_children_are_never_writable_even_if_a_schema_declares_them():
    greedy = SchemaSpec("wind-greedy-v1", "wind", (PathFamily("/brains/wind/{child}"), PathFamily("/brains/wind")))
    pub, *_ = make(registry=Registry([greedy]))
    for p in ("/brains/wind/publication", "/brains/wind/certification", "/brains/wind"):
        a = wind_artifact(artifactSchema="wind-greedy-v1", mutations=[{"op": "SET", "path": p, "value": {"x": 1}}])
        assert pub.evaluate(a, producer="wind").codes == ["RESERVED_PATH"], p


def test_overlapping_paths_are_rejected():
    a = wind_artifact(mutations=[{"op": "SET", "path": WIND_LAKE, "value": {"a": 1}}, {"op": "SET", "path": WIND_LAKE, "value": {"a": 2}}])
    assert run(a)[0].codes == ["OVERLAPPING_PATHS"]


def test_schema_registration_refuses_forbidden_roots_and_empty_families():
    for pat in ("/scores/{k}", "/control/x", "/access/{k}", "/jobs/{k}"):
        with pytest.raises(ValueError):
            SchemaSpec("bad-v1", "wind", (PathFamily(pat),))
    with pytest.raises(ValueError):
        SchemaSpec("bad-v1", "wind", ())
    with pytest.raises(ValueError):
        SchemaSpec("bad-v1", "no-such-brain", (PathFamily("/x/{k}"),))


# 9 -----------------------------------------------------------------------------------------------------------------------------------------
def test_output_fingerprint_is_independently_verified():
    a = wind_artifact()
    a["mutations"][0]["value"]["windMS"] = 99.0           # content changed after the Brain declared its fingerprint
    r, *_ = run(a)
    assert r.result is Result.FAILED_VALIDATION and r.codes == ["FINGERPRINT_MISMATCH"]
    a = wind_artifact(outputFingerprint="sha256:" + "00" * 32)
    assert run(a)[0].codes == ["FINGERPRINT_MISMATCH"]


def test_fingerprint_ignores_volatile_fields_key_order_and_mutation_order():
    a, b = wind_artifact(), wind_artifact()
    b["mutations"].reverse()
    b["mutations"][0]["value"] = dict(reversed(list(b["mutations"][0]["value"].items())))
    for m in b["mutations"]:
        if isinstance(m["value"], dict) and "generatedAt" in m["value"]:
            m["value"]["generatedAt"] = "2030-01-01T00:00:00Z"
    f = lambda x: output_fingerprint("wind", "wind-lake-state-v1", x["mutations"])      # noqa: E731
    assert f(a) == f(b)
    c = wind_artifact(speed=9.9)
    assert f(a) != f(c)


def test_fingerprint_binds_brain_and_schema():
    m = wind_artifact()["mutations"]
    assert output_fingerprint("wind", "wind-lake-state-v1", m) != output_fingerprint("wind", "wind-registry-v1", m)
    assert output_fingerprint("wind", "wind-lake-state-v1", m) != output_fingerprint("depth", "wind-lake-state-v1", m)
    assert output_fingerprint("wind", "wind-lake-state-v1", m).startswith("sha256:")


# 10, 11 ------------------------------------------------------------------------------------------------------------------------------------
def test_unchanged_output_is_skip_and_generates_no_mutation():
    pub, hist, sink = make()
    first = pub.evaluate(wind_artifact(n=1), producer="wind")
    assert first.result is Result.SHADOW_READY
    again = wind_artifact(n=2, minutes=60)                                   # new run, new ids/time, same material (volatile fields differ)
    again["mutations"][0]["value"]["generatedAt"] = "2026-10-15T04:00:00Z"
    again = rebuild(again)
    r = pub.evaluate(again, producer="wind")
    assert r.result is Result.SKIP and r.plan is None and len(sink.submitted) == 1
    assert r.record["previousPublishId"] == first.publish_id and r.record["status"] == "SKIPPED_UNCHANGED"


def test_changed_output_is_shadow_ready_again_and_head_advances():
    pub, hist, sink = make()
    a = pub.evaluate(wind_artifact(n=1), producer="wind")
    b = pub.evaluate(wind_artifact(n=2, speed=7.7, minutes=60), producer="wind")
    assert b.result is Result.SHADOW_READY and len(sink.submitted) == 2
    assert b.record["previousPublishId"] == a.publish_id
    assert hist.head("wind", "wind-lake-state-v1")["publishId"] == b.publish_id


def test_artifact_older_than_the_baseline_is_not_silently_republished():
    pub, *_ = make()
    pub.evaluate(wind_artifact(n=1, minutes=60), producer="wind")
    r = pub.evaluate(wind_artifact(n=2, speed=1.0, minutes=0), producer="wind")
    assert r.result is Result.REJECTED and r.codes == ["ARTIFACT_OLDER_THAN_BASELINE"]


def test_scopes_have_independent_baselines():
    pub, *_ = make()
    a, b = wind_artifact(n=1), wind_artifact(n=2)
    b["scope"] = "lake-test_lake_alpha"
    assert pub.evaluate(a, producer="wind").result is Result.SHADOW_READY
    assert pub.evaluate(b, producer="wind").result is Result.SHADOW_READY


# 12, 13 ------------------------------------------------------------------------------------------------------------------------------------
def test_patch_generation_is_deterministic():
    p1 = make()[0].evaluate(wind_artifact(), producer="wind").plan
    shuffled = wind_artifact(); shuffled["mutations"].reverse()
    p2 = make()[0].evaluate(rebuild(shuffled), producer="wind").plan
    assert p1.canonical() == p2.canonical() and p1.update_sha256 == p2.update_sha256 and list(p1.updates) == sorted(p1.updates)


def test_multi_path_update_is_one_atomic_plan_with_exactly_the_intended_paths():
    r, _, _, sink = run(wind_artifact())
    plan = r.plan
    want = {f"lakes/{LAKE_A}/states/wind", f"lakes/{LAKE_A}/profiles/wind", f"lakeFleet/{LAKE_A}/slots/wind", f"lakes/{LAKE_B}/states/wind"}
    assert set(plan.updates) == want | {"brains/wind/publication"} and plan.path_count == 4 and plan.deletes == ()
    assert len(sink.submitted) == 1 and sink.submitted[0][0] is plan                       # a single hand-off, not one write per path
    assert not [k for k in plan.updates if k.startswith(("speciesProfiles", "scores", "control", "access"))]
    assert all(k and not k.startswith("/") for k in plan.updates)
    assert plan.updates["brains/wind/publication"]["publishId"] == r.publish_id


def test_failure_in_one_mutation_means_no_plan_and_no_partial_state():
    a = wind_artifact(mutations=[{"op": "SET", "path": WIND_LAKE, "value": wind_state()}, {"op": "SET", "path": "/speciesProfiles/x", "value": {"a": 1}}])
    r, pub, hist, sink = run(a)
    assert r.plan is None and sink.submitted == [] and hist.head("wind", "wind-lake-state-v1") is None
    assert [x["result"] for x in hist.records("wind")] == ["REJECTED"]                       # only the rejection record exists


def test_sink_failure_before_commit_leaves_no_published_state():
    pub, hist, sink = make()

    def boom(plan, record):
        raise RuntimeError("sink down")
    sink.submit = boom
    with pytest.raises(RuntimeError):
        pub.evaluate(wind_artifact(), producer="wind")
    assert hist.head("wind", "wind-lake-state-v1") is None and hist.records("wind") == []


def test_plan_embeds_everything_needed_so_no_secondary_write_is_required():
    r, *_ = run(wind_artifact())
    rec = r.plan.updates["brains/wind/publication"]
    for k in ("publishId", "brainId", "artifactId", "executionId", "outputFingerprint", "artifactPatchSha256", "result", "publisher"):
        assert k in rec
    assert "removed" not in rec and None not in rec.values()                                 # RTDB-safe: no empties, no nulls


# 14, 15 ------------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("value", [None, {}, [], {"a": None}, {"a": {}}, {"a": [1, None]}, {"a": []}])
def test_null_and_empty_values_never_become_implicit_deletes(value):
    a = wind_artifact(mutations=[{"op": "SET", "path": WIND_LAKE, "value": value}])
    r, *_ = run(a)
    assert r.result is Result.FAILED_VALIDATION and r.plan is None and r.codes[0] in ("NULL_VALUE", "NULL_IN_VALUE", "EMPTY_VALUE")


def test_missing_set_value_is_not_a_delete():
    a = wind_artifact(outputFingerprint=SHA0, mutations=[{"op": "SET", "path": WIND_LAKE}])
    assert run(a)[0].codes == ["NULL_VALUE"]


def test_non_finite_numbers_are_rejected():
    a = wind_artifact(outputFingerprint=SHA0, mutations=[{"op": "SET", "path": WIND_LAKE, "value": {"windMS": float("nan")}}])
    assert run(a)[0].codes == ["NON_FINITE"]


def test_absent_data_does_not_delete_what_was_published_before():
    pub, *_ = make()
    pub.evaluate(wind_artifact(n=1), producer="wind")
    fewer = wind_artifact(n=2, minutes=60, speed=5.5, mutations=[{"op": "SET", "path": WIND_LAKE, "value": wind_state(5.5)}])
    r = pub.evaluate(fewer, producer="wind")
    assert r.result is Result.SHADOW_READY and None not in r.plan.updates.values() and r.plan.deletes == ()
    assert set(r.plan.updates) == {WIND_LAKE[1:], "brains/wind/publication"}


def test_explicit_delete_fails_unless_the_schema_permits_it():
    a = wind_artifact(mutations=[{"op": "DELETE", "path": WIND_LAKE, "reason": "retire"}])
    r, *_ = run(a)
    assert r.result is Result.REJECTED and r.codes == ["DELETE_NOT_PERMITTED"] and r.plan is None


def test_explicit_delete_is_rendered_only_when_permitted_and_only_for_that_path():
    spec = SchemaSpec("wind-deletable-v1", "wind", (PathFamily("/lakes/{k}/states/wind"),), delete_families=(PathFamily("/lakes/{k}/states/wind"),))
    pub, hist, sink = make(registry=Registry([spec]))
    muts = [{"op": "SET", "path": f"/lakes/{LAKE_A}/states/wind", "value": wind_state()}, {"op": "DELETE", "path": f"/lakes/{LAKE_B}/states/wind", "reason": "lake retired"}]
    r = pub.evaluate(wind_artifact(artifactSchema="wind-deletable-v1", mutations=muts), producer="wind")
    assert r.result is Result.SHADOW_READY and r.plan.deletes == (f"lakes/{LAKE_B}/states/wind",) and r.record["removed"] == [f"/lakes/{LAKE_B}/states/wind"]
    assert [k for k, v in r.plan.updates.items() if v is None] == [f"lakes/{LAKE_B}/states/wind"]


@pytest.mark.parametrize("mut", [{"op": "DELETE", "path": "/lakes/test_lake_alpha/states/wind"}, {"op": "DELETE", "path": "/lakes/test_lake_alpha/states/wind", "reason": " "},
                                 {"op": "DELETE", "path": "/lakes/test_lake_alpha/states/wind", "reason": "x", "value": {"a": 1}}])
def test_delete_needs_a_reason_and_no_value(mut):
    spec = SchemaSpec("wind-deletable-v1", "wind", (PathFamily("/lakes/{k}/states/wind"),), delete_families=(PathFamily("/lakes/{k}/states/wind"),))
    pub, *_ = make(registry=Registry([spec]))
    r = pub.evaluate(wind_artifact(artifactSchema="wind-deletable-v1", mutations=[mut]), producer="wind")
    assert r.is_rejection and r.plan is None


def test_delete_permission_is_per_family_not_global():
    spec = SchemaSpec("wind-deletable-v1", "wind", (PathFamily("/lakes/{k}/states/wind"), PathFamily("/lakes/{k}/profiles/wind")),
                      delete_families=(PathFamily("/lakes/{k}/states/wind"),))
    pub, *_ = make(registry=Registry([spec]))
    a = wind_artifact(artifactSchema="wind-deletable-v1", mutations=[{"op": "DELETE", "path": f"/lakes/{LAKE_A}/profiles/wind", "reason": "x"}])
    assert pub.evaluate(a, producer="wind").codes == ["DELETE_NOT_PERMITTED"]


# lifecycle / status / freshness ------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("lc", ["PRODUCTION", "PRODUCTION_READY"])
def test_wind_cannot_claim_production_lifecycle(lc):
    r, *_ = run(wind_artifact(lifecycle=lc))
    assert r.result is Result.REJECTED and r.codes == ["LIFECYCLE_NOT_AUTHORIZED"]


def test_production_lifecycle_needs_both_schema_permission_and_approval_ref():
    spec = SchemaSpec("wind-prod-v1", "wind", (PathFamily("/lakes/{k}/states/wind"),), allowed_lifecycles=("PRODUCTION",))
    pub, *_ = make(registry=Registry([spec]))
    a = wind_artifact(artifactSchema="wind-prod-v1", lifecycle="PRODUCTION", mutations=[{"op": "SET", "path": WIND_LAKE, "value": wind_state()}])
    assert pub.evaluate(a, producer="wind").codes == ["LIFECYCLE_NOT_AUTHORIZED"]
    a = wind_artifact(artifactSchema="wind-prod-v1", lifecycle="PRODUCTION", mutations=[{"op": "SET", "path": WIND_LAKE, "value": wind_state()}])
    a["approvalRef"] = "approval-record-0001"
    assert pub.evaluate(a, producer="wind").result is Result.SHADOW_READY


def test_invalid_vocabulary_and_semantic_inconsistency():
    assert run(wind_artifact(lifecycle="LIVE"))[0].codes == ["INVALID_LIFECYCLE"]
    assert run(wind_artifact(reviewStatus="DONE"))[0].codes == ["INVALID_STATUS"]
    assert run(wind_artifact(validationStatus="GREAT"))[0].codes == ["INVALID_STATUS"]
    assert run(wind_artifact(reviewStatus="NOT_APPLICABLE"))[0].codes == ["INVALID_STATUS"]
    assert run(wind_artifact(validationStatus="VALIDATED", reviewStatus="UNREVIEWED"))[0].codes == ["STATUS_INCONSISTENT"]


def test_freshness_is_required_for_wind_lake_state_and_unknown_is_a_value():
    a = wind_artifact(); del a["freshness"]
    assert run(a)[0].codes == ["FRESHNESS_MISSING"]
    a = wind_artifact(); a["freshness"] = {"freshnessStatus": "UNKNOWN"}
    assert run(a)[0].result is Result.SHADOW_READY
    a = wind_artifact(); a["freshness"]["freshnessStatus"] = None
    assert run(a)[0].codes == ["INVALID_FRESHNESS"]
    a = wind_artifact(); a["freshness"]["staleAfter"], a["freshness"]["expiresAt"] = "2026-10-16T00:00:00Z", "2026-10-15T00:00:00Z"
    assert run(a)[0].codes == ["INVALID_FRESHNESS"]


def test_oversize_artifact_is_rejected():
    spec = SchemaSpec("wind-tiny-v1", "wind", (PathFamily("/lakes/{k}/states/wind"),), max_bytes=100)
    pub, *_ = make(registry=Registry([spec]))
    assert pub.evaluate(wind_artifact(artifactSchema="wind-tiny-v1", mutations=[{"op": "SET", "path": WIND_LAKE, "value": {"x": "y" * 500}}]), producer="wind").codes == ["OVERSIZE"]


def test_value_type_is_checked_structurally():
    a = wind_artifact(mutations=[{"op": "SET", "path": WIND_LAKE, "value": "just a string"}])
    assert run(a)[0].codes == ["VALUE_TYPE"]


def test_illegal_rtdb_keys_in_values_are_rejected():
    a = wind_artifact(mutations=[{"op": "SET", "path": WIND_LAKE, "value": {"bad.key": 1}}])
    assert run(a)[0].codes == ["ILLEGAL_KEY"]


# 17, 18, 19 --------------------------------------------------------------------------------------------------------------------------------
def test_publication_record_is_generated_correctly():
    r, pub, hist, _ = run(wind_artifact(n=7), trigger="MANUAL_REQUEST", request_id=uuid4(777))
    rec = r.record
    assert rec["brainId"] == "wind" and rec["artifactId"] == uuid4(2007) and rec["executionId"] == uuid4(1007)
    assert rec["result"] == "SHADOW_READY" and rec["publisher"] == "orchestrator-publisher" and rec["mode"] == "SHADOW"
    assert rec["trigger"] == "MANUAL_REQUEST" and rec["requestId"] == uuid4(777)
    assert rec["outputFingerprint"] == output_fingerprint("wind", "wind-lake-state-v1", wind_artifact(n=7)["mutations"])
    assert rec["paths"] == {"count": 4, "bytes": r.plan.patch_bytes} and rec["artifactPatchSha256"] == r.plan.artifact_patch_sha256
    assert set(rec["pathSha256"]) == {k for k in r.plan.updates if k != "brains/wind/publication"}
    assert hist.get_record("wind", r.publish_id)["updateSha256"] == r.plan.update_sha256
    assert "PUBLISHED" not in json.dumps(rec) and "COMPLETE" not in json.dumps(rec)
    assert "credential" not in json.dumps(rec).lower()


def test_rejected_and_skipped_outcomes_are_in_history_only():
    pub, hist, sink = make()
    pub.evaluate(wind_artifact(n=1), producer="wind")
    pub.evaluate(wind_artifact(n=2, lifecycle="PRODUCTION"), producer="wind")
    skip = wind_artifact(n=3, minutes=5)
    pub.evaluate(skip, producer="wind")
    assert [r["result"] for r in hist.records("wind")] == ["SHADOW_READY", "REJECTED", "SKIP"]
    assert len(sink.submitted) == 1                                                       # nothing but the one change reached the sink


def test_dry_run_evaluates_but_persists_nothing_and_never_calls_the_sink():
    pub, hist, sink = make(mode=PublisherMode.DRY_RUN)
    r = pub.evaluate(wind_artifact(), producer="wind")
    assert r.result is Result.SHADOW_READY and r.plan is not None and r.persisted is False
    assert sink.submitted == [] and hist.records("wind") == [] and hist.head("wind", "wind-lake-state-v1") is None
    assert pub.evaluate(wind_artifact(), producer="wind").result is Result.SHADOW_READY   # still no baseline, so still changed


def test_evaluate_stored_reads_the_brains_own_artifact_from_the_store():
    pub, hist, _ = make()
    art = wind_artifact(n=4)
    hist.put_artifact("wind", art["lineage"]["artifactId"], art)
    assert pub.evaluate_stored("wind", art["lineage"]["artifactId"]).result is Result.SHADOW_READY
    with pytest.raises(KeyError):
        pub.evaluate_stored("wind", uuid4(1))


def test_artifact_ids_are_immutable():
    pub, *_ = make()
    pub.evaluate(wind_artifact(n=1, speed=1.0), producer="wind")
    clash = wind_artifact(n=1, speed=2.0, minutes=30)                                    # same artifactId, different content
    assert pub.evaluate(clash, producer="wind").codes == ["ARTIFACT_ID_CONFLICT"]


def test_input_artifact_is_not_mutated_by_evaluation():
    a = wind_artifact(); before = canonical_bytes(a)
    make()[0].evaluate(a, producer="wind")
    assert canonical_bytes(a) == before
