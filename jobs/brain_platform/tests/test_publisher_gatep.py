"""Gate P (F-1..F-8): one artifact -> one atomic plan, semantic fingerprint / volatile contract, publication metadata, explicit deletes, derived projections."""
import copy
import datetime as dt
import json

import pytest

from gatep_fixtures import bundle, lake_section, registry_section, source_section
from publisher_fixtures import LAKE_A, LAKE_B, T0, make, uuid4, wind_artifact
from sector_brain_platform.publisher import (PathFamily, Registry, Result, SchemaSpec, canonical_bytes, default_registry, output_fingerprint, seal_bundle, sha256_ref)
from sector_brain_platform.publisher.artifact import section_fingerprint
from sector_brain_platform.publisher.canonical import ALGORITHM, bundle_fingerprint
from sector_brain_platform.publisher.registry import WIND_VOLATILE_CONTRACT_V1


def run(art, pub=None):
    pub, hist, sink = (pub or make())
    return pub.evaluate(art, producer="wind"), hist, sink


# ============ F-2: one artifact -> one atomic plan ====================================================================================================
def test_one_multi_section_artifact_yields_one_plan_one_record_one_sink_call():
    pub, hist, sink = make()
    r = pub.evaluate(bundle(1), producer="wind")
    assert r.result is Result.SHADOW_READY and len(sink.submitted) == 1 and sink.submitted[0][0] is r.plan
    keys = set(r.plan.updates)
    assert {f"lakes/{LAKE_A}/states/wind", "brains/wind/version", "sources/noaa-nbm-v5", "health/brains/wind/status"} <= keys      # all three sections, one plan
    assert [k for k in keys if k.endswith("/publication")] == ["brains/wind/publication"]                                         # exactly one publication record
    assert len(hist.records("wind")) == 1
    assert {(s["artifactSchema"], s["scope"]) for s in r.record["sections"]} == {("wind-lake-state-v1", "lake-live"), ("wind-registry-v1", "default"), ("wind-source-registry-v1", "default")}
    for s in r.record["sections"]:                                                                                                  # every section baseline advanced together
        assert hist.head("wind", s["artifactSchema"], s["scope"])["publishId"] == r.publish_id


def test_plan_and_record_are_independent_of_section_and_mutation_order():
    a = bundle(1)
    b = bundle(1, sections=list(reversed([lake_section(), registry_section(), source_section()])))
    for sec in b["sections"]:
        sec["mutations"].reverse()
    b["lineage"]["outputFingerprint"] = a["lineage"]["outputFingerprint"]
    ra, rb = run(a)[0], run(b)[0]
    assert rb.result is Result.SHADOW_READY and ra.plan.canonical() == rb.plan.canonical() and ra.plan.update_sha256 == rb.plan.update_sha256
    assert list(ra.plan.updates) == sorted(ra.plan.updates)


def _poison(art, which, mutate):
    art = copy.deepcopy(art)
    mutate(art["sections"][which])
    return art


@pytest.mark.parametrize("which,mutate,code", [
    (0, lambda s: s["mutations"].append({"op": "SET", "path": "/speciesProfiles/x", "value": {"a": 1}}), "CROSS_DOMAIN_PATH"),
    (1, lambda s: s["mutations"].append({"op": "SET", "path": "/brains/wind/publication", "value": {"a": 1}}), "RESERVED_PATH"),
    (2, lambda s: s["mutations"].append({"op": "SET", "path": "/sources/tva-restapi", "value": {"a": 1}}), "CROSS_DOMAIN_PATH"),
    (1, lambda s: s["mutations"].append({"op": "SET", "path": "/brains/wind", "value": {"a": 1}}), "BRAIN_NODE_REPLACEMENT"),
    (0, lambda s: s["mutations"][0].update(value=None), "NULL_VALUE"),
    (2, lambda s: s["mutations"][0].update(value={"x": {}}), "EMPTY_VALUE"),
    (0, lambda s: s.pop("freshness"), "FRESHNESS_MISSING"),
])
def test_one_bad_mutation_in_any_section_rejects_the_whole_artifact_and_leaves_no_partial_state(which, mutate, code):
    good = bundle(1)
    bad = _poison(good, which, mutate)
    bad["lineage"]["outputFingerprint"] = good["lineage"]["outputFingerprint"]
    pub, hist, sink = make()
    r = pub.evaluate(bad, producer="wind")
    assert r.is_rejection and code in r.codes and r.plan is None
    assert sink.submitted == [] and [x["result"] for x in hist.records("wind")] == [r.result.value]
    for sid, sc in (("wind-lake-state-v1", "lake-live"), ("wind-registry-v1", "default"), ("wind-source-registry-v1", "default")):
        assert hist.head("wind", sid, sc) is None                                         # no section baseline moved


def test_schema_lineage_and_fingerprint_failures_reject_the_whole_artifact():
    pub, hist, sink = make()
    a = bundle(1); a["sections"][1]["artifactSchema"] = "nope-v1"
    assert pub.evaluate(a, producer="wind").codes == ["UNKNOWN_SCHEMA"]
    a = bundle(2); a["lineage"].pop("codeVersion")
    assert pub.evaluate(a, producer="wind").codes == ["LINEAGE_INCOMPLETE"]
    a = bundle(3); a["sections"][2]["mutations"][0]["value"]["provider"] = "tampered"           # content changed after the Brain declared the fingerprint
    assert pub.evaluate(a, producer="wind").codes == ["FINGERPRINT_MISMATCH"]
    a = bundle(4); a["lineage"]["artifactSchema"] = "wind-unknown-bundle-v1"
    assert pub.evaluate(a, producer="wind").codes == ["UNKNOWN_SCHEMA"]
    assert sink.submitted == [] and all(h is None for h in (hist.head("wind", "wind-registry-v1", "default"),))


def test_section_policy_duplicates_foreign_sections_and_cross_section_overlap():
    pub, _, sink = make()
    a = bundle(1, sections=[lake_section(), lake_section(), registry_section()])
    assert pub.evaluate(a, producer="wind").codes == ["DUPLICATE_SECTION"]
    a = bundle(2, sections=[lake_section(scope="lake-live"), lake_section(scope="lake-static")])                         # same paths in two sections
    assert set(pub.evaluate(a, producer="wind").codes) == {"OVERLAPPING_PATHS"}
    spec = SchemaSpec("depth-state-v1", "depth", (PathFamily("/lakes/{k}/states/depth"),))
    reg = Registry(list(default_registry()._specs.values()) + [spec], [*default_registry()._bundles.values()])
    pub2, *_ = make(registry=reg)
    a = bundle(3, sections=[lake_section(), {"artifactSchema": "depth-state-v1", "mutations": [{"op": "SET", "path": f"/lakes/{LAKE_A}/states/depth", "value": {"d": 1}}]}])
    assert pub2.evaluate(a, producer="wind").codes == ["SECTION_NOT_ALLOWED"]
    assert sink.submitted == []


def test_v1_and_v2_shapes_are_not_mixed():
    a = bundle(1); a["mutations"] = []
    assert run(a)[0].codes == ["MALFORMED"]
    v1 = wind_artifact(n=1); v1["sections"] = []
    assert run(v1)[0].codes == ["MALFORMED"]


def test_unchanged_sections_are_not_republished_but_the_changed_one_is_one_coherent_plan():
    pub, hist, sink = make()
    first = pub.evaluate(bundle(1), producer="wind")
    nxt = pub.evaluate(bundle(2, minutes=60, sections=[lake_section(), registry_section(status="DEGRADED"), source_section()]), producer="wind")
    assert nxt.result is Result.SHADOW_READY and len(sink.submitted) == 2
    sec = {s["artifactSchema"]: s["result"] for s in nxt.record["sections"]}
    assert sec == {"wind-lake-state-v1": "SKIP", "wind-registry-v1": "SHADOW", "wind-source-registry-v1": "SKIP"}
    assert not [k for k in nxt.plan.updates if k.startswith(("lakes/", "sources/"))] and "brains/wind/status" in nxt.plan.updates
    assert hist.head("wind", "wind-lake-state-v1", "lake-live")["publishId"] == first.publish_id                  # skipped section keeps its baseline
    assert hist.head("wind", "wind-registry-v1", "default")["publishId"] == nxt.publish_id


def test_an_artifact_older_than_any_changed_section_baseline_rejects_the_whole_artifact():
    pub, hist, sink = make()
    pub.evaluate(bundle(1, minutes=60), producer="wind")
    r = pub.evaluate(bundle(2, minutes=0, sections=[lake_section(speed=9.0), registry_section(status="DEGRADED"), source_section()]), producer="wind")
    assert r.result is Result.REJECTED and set(r.codes) == {"ARTIFACT_OLDER_THAN_BASELINE"} and len(r.violations) == 2 and len(sink.submitted) == 1


# ============ F-1 / F-8: semantic fingerprint and the volatile contract ================================================================================
def test_volatile_scalar_children_do_not_force_a_republish():
    pub, hist, sink = make()
    pub.evaluate(bundle(1), producer="wind")
    only_volatile = bundle(2, minutes=60, sections=[lake_section(), registry_section(updated="2026-10-15T04:00:00Z", last_ok="2026-10-15T04:00:00Z"),
                                                   source_section(last_fetch="2026-10-15T04:00:00Z")])
    r = pub.evaluate(only_volatile, producer="wind")
    assert r.result is Result.SKIP and r.plan is None and len(sink.submitted) == 1 and r.codes == []


def test_a_material_change_next_to_volatile_changes_is_not_hidden():
    pub, *_ = make()
    pub.evaluate(bundle(1), producer="wind")
    for sections in ([lake_section(speed=7.7), registry_section(), source_section()],
                     [lake_section(), registry_section(status="DEGRADED", updated="2026-10-15T04:00:00Z"), source_section()],
                     [lake_section(), registry_section(), source_section(observed="2026-10-15T03:45:00Z", last_fetch="2026-10-15T04:00:00Z")]):     # evidence time is MATERIAL
        r = pub.evaluate(bundle(len(sections) + 10, minutes=60, sections=sections), producer="wind")
        assert r.result is Result.SHADOW_READY, sections
        pub = make()[0]; pub.evaluate(bundle(1), producer="wind")


def test_lineage_freshness_ids_and_publication_metadata_do_not_enter_the_semantic_fingerprint():
    a, b = bundle(1), bundle(9, minutes=500, code_version="cafef00d", input_fingerprint="sha256:" + "ee" * 32)
    b["sections"][0]["freshness"] = {"freshnessStatus": "STALE", "evidenceObservedAt": "2026-10-15T01:00:00Z"}
    assert a["lineage"]["outputFingerprint"] == b["lineage"]["outputFingerprint"]
    sections = [lake_section(), registry_section(), source_section()]
    fps = [section_fingerprint(default_registry().spec(s["artifactSchema"]), "wind", s["mutations"]) for s in sections]
    assert b["lineage"]["outputFingerprint"] == bundle_fingerprint("wind", "wind-publication-v1", [(s["artifactSchema"], s.get("scope", "default"), f) for s, f in zip(sections, fps)])


def test_three_hashes_are_distinct_concepts():
    st_a, st_b = make(), make()
    ra = st_a[0].evaluate(bundle(1), producer="wind")
    rb = st_b[0].evaluate(bundle(1, minutes=30, sections=[lake_section(), registry_section(updated="2026-10-15T09:00:00Z"), source_section()]), producer="wind")
    integrity = lambda art: sha256_ref(canonical_bytes(art))                                    # noqa: E731  input integrity: exact bytes
    assert integrity(bundle(1)) != integrity(bundle(1, minutes=30))                              # integrity hash moves with every byte (ids, times, volatile)
    assert ra.record["outputFingerprint"] == rb.record["outputFingerprint"]                      # semantic fingerprint does not
    assert "publishId" not in canonical_bytes(bundle(1)).decode() and "publishId" not in str(bundle(1)["lineage"])      # publication metadata is neither: Publisher-generated, never in the artifact


def test_semantic_fingerprint_is_deterministic_and_algorithm_versioned():
    f = lambda: section_fingerprint(default_registry().spec("wind-registry-v1"), "wind", registry_section()["mutations"])      # noqa: E731
    assert f() == f() and ALGORITHM == "sector-semantic-fingerprint-v2" and f().startswith("sha256:")
    pub, hist, sink = make()
    r1 = pub.evaluate(bundle(1), producer="wind")
    # a baseline written under another algorithm is never treated as "equal"
    from sector_brain_platform.publisher.storage import head_key
    key = head_key("wind", "wind-registry-v1", "default")
    ptr = json.loads(hist.store.get(key)); ptr["fingerprintAlgorithm"] = "old-algorithm"
    hist.store.put(key, canonical_bytes(ptr), if_generation_match=hist.store.generation(key))
    r2 = pub.evaluate(bundle(2, minutes=60), producer="wind")
    assert r2.result is Result.SHADOW_READY and {s["artifactSchema"]: s["result"] for s in r2.record["sections"]}["wind-registry-v1"] == "SHADOW"


def test_volatile_paths_never_hide_a_delete():
    vol = PathFamily("/brains/wind/updatedAt")
    base = [{"op": "SET", "path": "/brains/wind/status", "value": "X"}]
    with_set = base + [{"op": "SET", "path": "/brains/wind/updatedAt", "value": "t1"}]
    assert output_fingerprint("wind", "s", with_set, volatile_paths=(vol,)) == output_fingerprint("wind", "s", base, volatile_paths=(vol,))
    with_del = base + [{"op": "DELETE", "path": "/brains/wind/updatedAt", "reason": "r"}]
    assert output_fingerprint("wind", "s", with_del, volatile_paths=(vol,)) != output_fingerprint("wind", "s", base, volatile_paths=(vol,))


def test_wind_volatile_contract_is_inspectable_named_versioned_and_fully_explained():
    d = WIND_VOLATILE_CONTRACT_V1.describe()
    assert d["id"] == "wind-volatile-v1" and d["version"] == 1
    assert d["keys"] == ["inputAgeHours", "lastFetchAt", "latencyMs"] and d["paths"] == ["/brains/wind/lastSuccessfulRun", "/brains/wind/updatedAt"]
    assert set(d["notes"]) == {f"key:{k}" for k in d["keys"]} | {f"path:{p}" for p in d["paths"]}            # no unexplained entry; no hidden list elsewhere
    reg = default_registry()
    assert {reg.spec(s).volatile.id for s in reg.schemas_for("wind")} == {"wind-volatile-v1"}
    assert not {"observationTime", "forecastGeneratedAt", "latestObservationAt", "latestIssuedAt"} & set(d["keys"])      # evidence times stay material
    from sector_brain_platform.publisher.canonical import DEFAULT_VOLATILE
    assert not set(d["keys"]) & DEFAULT_VOLATILE                                                              # the contract only ADDS to the shared defaults


# ============ F-3: publication metadata ownership ====================================================================================================
def test_publication_metadata_is_written_once_by_the_publisher_and_is_stable_within_the_transaction():
    pub, hist, sink = make()
    r = pub.evaluate(bundle(1), producer="wind")
    node = r.plan.updates["brains/wind/publication"]
    assert node["publishId"] == r.publish_id == sink.submitted[0][1]["publishId"] == hist.records("wind")[0]["publishId"]
    assert node["publisher"] == "orchestrator-publisher" and node["live"] is False and "publishedAt" not in node and "sections" in node
    assert sum(1 for k in r.plan.updates if "publication" in k) == 1


@pytest.mark.parametrize("path", ["/brains/wind/publication", "/brains/wind/publication/publishId", "/brains/wind/certification"])
def test_a_specialist_cannot_author_or_delete_publication_state_in_any_section(path):
    for op in ({"op": "SET", "value": {"x": 1}}, {"op": "DELETE", "reason": "OPTIONAL_CHILD_CLEARED"}):
        sec = registry_section(extra=[{**op, "path": path}])
        r = run(bundle(1, sections=[sec]))[0]
        assert r.result is Result.REJECTED and r.codes == ["RESERVED_PATH"] and r.plan is None


def test_skip_does_not_fabricate_a_publication():
    pub, hist, sink = make()
    pub.evaluate(bundle(1), producer="wind")
    head_before = hist.head("wind", "wind-registry-v1", "default")
    r = pub.evaluate(bundle(2, minutes=60), producer="wind")
    assert r.result is Result.SKIP and r.plan is None and len(sink.submitted) == 1 and r.record["status"] == "SKIPPED_UNCHANGED"
    assert hist.head("wind", "wind-registry-v1", "default") == head_before and "live" not in r.record
    assert all(s["result"] == "SKIP" for s in r.record["sections"])


# ============ F-4: explicit delete ====================================================================================================================
def test_allowed_optional_child_delete_is_explicit_atomic_and_deterministic():
    sec = registry_section(extra=[{"op": "DELETE", "path": "/brains/wind/lastError", "reason": "OPTIONAL_CHILD_CLEARED"}])
    r1, r2 = run(bundle(1, sections=[sec]))[0], run(bundle(1, sections=[sec]))[0]
    assert r1.result is Result.SHADOW_READY and r1.plan.deletes == ("brains/wind/lastError",) and r1.plan.updates["brains/wind/lastError"] is None
    assert "brains/wind/version" in r1.plan.updates                                           # atomic with the other mutations of the same artifact
    assert [k for k, v in r1.plan.updates.items() if v is None] == ["brains/wind/lastError"] and r1.plan.canonical() == r2.plan.canonical()
    assert r1.record["removed"] == ["/brains/wind/lastError"]


def test_missing_field_is_not_a_delete_and_null_is_never_a_delete():
    pub, *_ = make()
    pub.evaluate(bundle(1, sections=[registry_section(extra=[{"op": "SET", "path": "/brains/wind/lastError", "value": {"message": "x"}}])]), producer="wind")
    r = pub.evaluate(bundle(2, minutes=60, sections=[registry_section(status="DEGRADED")]), producer="wind")          # lastError simply absent now
    assert r.result is Result.SHADOW_READY and "brains/wind/lastError" not in r.plan.updates and r.plan.deletes == ()
    nul = bundle(3, minutes=120, sections=[registry_section(extra=[{"op": "SET", "path": "/brains/wind/lastError", "value": None}])])
    rn = pub.evaluate(nul, producer="wind")
    assert rn.is_rejection and rn.codes == ["NULL_VALUE"] and rn.plan is None


def test_delete_of_a_stale_lake_child_also_deletes_its_derived_snapshot_copy():
    sec = {"artifactSchema": "wind-lake-state-v1", "scope": "lake-live", "freshness": {"freshnessStatus": "UNKNOWN"},
           "mutations": [{"op": "DELETE", "path": f"/lakes/{LAKE_B}/states/wind", "reason": "LAKE_LEFT_FLEET"},
                         {"op": "DELETE", "path": f"/lakeFleet/{LAKE_B}/slots/wind", "reason": "LAKE_LEFT_FLEET"}]}
    r = run(bundle(1, sections=[sec]))[0]
    assert r.result is Result.SHADOW_READY
    assert set(r.plan.deletes) == {f"lakes/{LAKE_B}/states/wind", f"lakeFleet/{LAKE_B}/slots/wind", f"snapshots/{LAKE_B}/latest/wind",
                                   f"snapshots/{LAKE_B}/latest/brainVersions/wind"}                         # both derived compatibility targets follow the authorised source delete
    assert f"snapshots/{LAKE_B}/latest/wind" in r.plan.derived_keys


@pytest.mark.parametrize("path,code", [
    ("/speciesProfiles/common_carp", "CROSS_DOMAIN_PATH"), (f"/lakes/{LAKE_A}/speciesPresence", "CROSS_DOMAIN_PATH"), ("/brains/biological-state/status", "CROSS_DOMAIN_PATH"),
    ("/brains/wind", "BRAIN_NODE_REPLACEMENT"), ("/brains", "BRAIN_NODE_REPLACEMENT"), ("/brains/wind/publication", "RESERVED_PATH"),
    ("/brains/wind/version", "DELETE_NOT_PERMITTED"), (f"/lakes/{LAKE_A}/states", "PATH_NOT_AUTHORIZED"), (f"/lakes/{LAKE_A}", "PATH_NOT_AUTHORIZED"),
    (f"/lakeFleet/{LAKE_A}", "PATH_NOT_AUTHORIZED"), ("/lakes", "PATH_NOT_AUTHORIZED"), ("/validation/wind", "DELETE_NOT_PERMITTED")])
def test_unauthorized_deletes_are_rejected_including_subtrees_foreign_and_whole_node(path, code):
    sec = registry_section(extra=[{"op": "DELETE", "path": path, "reason": "OPTIONAL_CHILD_CLEARED"}])
    r = run(bundle(1, sections=[sec]))[0]
    assert r.result is Result.REJECTED and code in r.codes and r.plan is None


def test_delete_reasons_are_a_closed_vocabulary():
    for reason in ("whatever", "", "LAKE_LEFT_FLEET"):                                  # last one is valid for the lake schema but not for the registry schema
        sec = registry_section(extra=[{"op": "DELETE", "path": "/brains/wind/lastError", "reason": reason}])
        assert run(bundle(1, sections=[sec]))[0].codes[0] in ("DELETE_REASON_INVALID", "INVALID_DELETE")
    with pytest.raises(ValueError):
        SchemaSpec("x-v1", "wind", (PathFamily("/a/{k}"),), delete_families=(PathFamily("/a/{k}"),))          # deletes need a declared reason vocabulary


@pytest.mark.parametrize("muts", [
    [{"op": "SET", "path": "/brains/wind/lastError", "value": {"m": 1}}, {"op": "DELETE", "path": "/brains/wind/lastError", "reason": "OPTIONAL_CHILD_CLEARED"}],
    [{"op": "SET", "path": f"/lakes/{LAKE_A}/states/wind", "value": {"k": 1}}, {"op": "DELETE", "path": f"/lakes/{LAKE_A}/states/wind", "reason": "LAKE_LEFT_FLEET"}]])
def test_set_and_delete_of_the_same_path_conflict_even_across_sections(muts):
    wrong = [registry_section(), lake_section(lakes=())] if False else None
    if muts[0]["path"].startswith("/lakes"):
        secs = [{"artifactSchema": "wind-lake-state-v1", "scope": "a", "freshness": {"freshnessStatus": "FRESH"}, "mutations": [muts[0]]},
                {"artifactSchema": "wind-lake-state-v1", "scope": "b", "freshness": {"freshnessStatus": "FRESH"}, "mutations": [muts[1]]}]
    else:
        secs = [registry_section(extra=muts)]
    r = run(bundle(1, sections=secs))[0]
    assert r.result is Result.REJECTED and "SET_DELETE_CONFLICT" in r.codes and r.plan is None


# ============ F-5 / F-6 / F-7: derived projections and platform-owned paths =========================================================================
def test_snapshot_copy_and_brainversion_are_publisher_derived_and_explicit():
    r = run(bundle(1))[0]
    for k in (LAKE_A, LAKE_B):
        assert r.plan.updates[f"snapshots/{k}/latest/wind"] == r.plan.updates[f"lakes/{k}/states/wind"]                  # byte-equal by construction
        assert r.plan.updates[f"snapshots/{k}/latest/brainVersions/wind"] == "wind-test-1"
        assert f"snapshots/{k}/latest/wind" in r.plan.derived_keys
    assert r.record["derived"] == [{"rule": "wind-snapshot-brainversion-v1", "count": 2}, {"rule": "wind-snapshot-copy-v1", "count": 2}]
    assert r.record["pathSha256"] and set(r.plan.derived_keys) <= set(r.plan.updates)
    only_lake = run(bundle(2, sections=[lake_section()]))[0]
    assert not [k for k in only_lake.plan.updates if "brainVersions" in k]                         # no version in the artifact -> no projection (never invented)


@pytest.mark.parametrize("path,code", [
    (f"/snapshots/{LAKE_A}/latest/wind", "PLATFORM_DERIVED_PATH"), (f"/snapshots/{LAKE_A}/latest/brainVersions/wind", "PLATFORM_DERIVED_PATH"),
    (f"/snapshots/{LAKE_A}/latest/lakeId", "CROSS_DOMAIN_PATH"), (f"/lakeFleet/{LAKE_A}/lakeId", "CROSS_DOMAIN_PATH"),
    ("/health/jobs/wind-hourly", "CROSS_DOMAIN_PATH"), ("/health/brains/wind/lastRun", "PATH_NOT_AUTHORIZED"), ("/health/brains/wind/durationMs", "PATH_NOT_AUTHORIZED"),
    ("/health/brains/wind/latestError", "PATH_NOT_AUTHORIZED"), ("/jobs/wind-hourly", "CROSS_DOMAIN_PATH"), ("/activity", "PATH_NOT_AUTHORIZED")])
def test_wind_cannot_author_platform_owned_or_derived_legacy_paths(path, code):
    sec = {"artifactSchema": "wind-registry-v1", "mutations": [{"op": "SET", "path": path, "value": {"x": 1}}]}
    if "snapshots" in path or "lakeFleet" in path:
        sec = {"artifactSchema": "wind-lake-state-v1", "scope": "s", "freshness": {"freshnessStatus": "FRESH"}, "mutations": [{"op": "SET", "path": path, "value": {"x": 1}}]}
    r = run(bundle(1, sections=[sec]))[0]
    assert r.result is Result.REJECTED and r.plan is None and code in r.codes, (path, r.codes)


def test_wind_domain_health_children_and_events_remain_authorable():
    sec = registry_section(extra=[{"op": "SET", "path": "/activity/2026-10-15T03-wind-run", "value": {"kind": "brain.version"}}])
    r = run(bundle(1, sections=[sec]))[0]
    assert r.result is Result.SHADOW_READY and "health/brains/wind/status" in r.plan.updates and "health/brains/wind/staleLakeCount" in r.plan.updates
    assert "activity/2026-10-15T03-wind-run" in r.plan.updates


def test_projection_cannot_collide_with_authored_content():
    spec = default_registry().spec("wind-lake-state-v1")
    assert spec.projections and all(p.retirement_gate and p.owner == "publisher" for p in spec.projections)
    from sector_brain_platform.publisher.registry import CompatibilityProjection
    with pytest.raises(ValueError):
        CompatibilityProjection("p", "/a/{k}", "/b/{k}", "COPY")                              # a projection without a retirement gate cannot be declared
    with pytest.raises(ValueError):
        CompatibilityProjection("p", "/a/{k}", "/b/{k}", "VALUE_FROM", None, retirement_gate="g")


# ============ the whole path for one multi-section artifact: Brain write -> API reference -> Publisher -> ONE plan ================================
def test_multi_section_artifact_through_the_api_handoff_is_one_transaction():
    import itertools
    from publisher_fixtures import T0
    from sector_brain_platform.publisher import local_shadow_stack
    from sector_brain_platform.publisher.api import AllowlistAuthorizer, Caller, OrchestratorApi
    ids = itertools.count(1)
    st = local_shadow_stack(clock=lambda: T0 + dt.timedelta(hours=1), id_factory=lambda: uuid4(next(ids) + 50000))
    api = OrchestratorApi(type("A", (), {"authenticate": lambda s, c: Caller("wind-brain-identity") if c == "t" else None})(),
                          AllowlistAuthorizer({"wind-brain-identity": {"ARTIFACT": {"SUBMIT_ARTIFACT@wind"}}}), st.dispatcher)

    def submit(art, n):
        ref = st.writer("wind").write(art)
        return api.handle("t", {"apiVersion": "orchestrator-api-v1", "requestId": uuid4(n), "requestKind": "ARTIFACT", "brainId": "wind", "action": "SUBMIT_ARTIFACT",
                                "params": {"artifactId": ref.artifact_id, "artifactRef": ref.location, "artifactSha256": ref.sha256, "executionId": ref.execution_id,
                                           "expectedSchema": ref.expected_schema}})
    r = submit(bundle(1), 900)
    assert r.status == 200 and r.result["result"] == "SHADOW_READY" and len(st.sink.submitted) == 1
    assert submit(bundle(2, minutes=30, sections=[lake_section(), registry_section(updated="2026-10-15T09:00:00Z"), source_section()]), 901).result["result"] == "SKIP"
    assert len(st.sink.submitted) == 1 and st.sink.live_mutations == 0
    bad = bundle(3, minutes=60); bad["sections"][1]["mutations"].append({"op": "SET", "path": "/brains/wind", "value": {"a": 1}})
    rb = submit(bad, 902)
    assert rb.result["result"] == "REJECTED" and "BRAIN_NODE_REPLACEMENT" in rb.result["codes"] and len(st.sink.submitted) == 1
