"""Wind artifact builder through Publisher V1 SHADOW (local, no live system, no network). Covers the 20 required shadow proofs.

Real Wind output is produced by the unchanged publish() against a DryRunWriter; its PATCHes are re-expressed as artifacts and sent through the
Publisher's own handoff (ArtifactWriter -> authenticated API signal -> evaluate_reference). The Publisher code is imported, never re-implemented."""
import copy
import dataclasses
import hashlib
import itertools
import json
from datetime import datetime, timedelta, timezone

import pytest

from sector_wind.brain import artifact as A
from sector_wind.brain import contract as C
from sector_wind.brain.publish import publish
from sector_wind.brain.writer import DryRunWriter
from test_brain import CFG, DIRECTORY, NOW, make_store

from sector_brain_platform.publisher import Result, default_registry, local_shadow_stack, output_fingerprint
from sector_brain_platform.publisher.api import AllowlistAuthorizer, Caller, OrchestratorApi
from sector_brain_platform.publisher.registry import WIND_REGISTRY_CHILDREN, Registry

T = datetime(2026, 10, 15, 3, 0, tzinfo=timezone.utc)
LIVE = "wind-lake-state-v1:lake-live"
iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
uuid4 = lambda n: f"{n:08x}-0000-4000-8000-{n:012x}"


def wind_registry():
    """The Publisher's Wind registration plus Wind's volatile fields (what the platform registry must carry at cutover)."""
    base = default_registry()
    return Registry([dataclasses.replace(base.spec(s), volatile_extra=A.WIND_VOLATILE_EXTRA) for s in base.schemas_for("wind")])


class Authn:
    def authenticate(self, cred):
        return Caller("wind-brain-identity") if cred == "wind-token" else None


class Rig:
    def __init__(self, tmp_path=None):
        self.ids = itertools.count(1)
        self.st = local_shadow_stack(tmp_path, registry=wind_registry(), clock=lambda: T + timedelta(hours=2), id_factory=lambda: uuid4(next(self.ids) + 50000))
        self.api = OrchestratorApi(Authn(), AllowlistAuthorizer({"wind-brain-identity": {"ARTIFACT": {"SUBMIT_ARTIFACT@wind"}}}), self.st.dispatcher)
        self.n = itertools.count(900)

    def submit(self, art):
        ref = self.st.writer("wind").write(art)
        body = {"apiVersion": "orchestrator-api-v1", "requestId": uuid4(next(self.n)), "requestKind": "ARTIFACT", "brainId": "wind", "action": "SUBMIT_ARTIFACT",
                "params": {"artifactId": ref.artifact_id, "artifactRef": ref.location, "artifactSha256": ref.sha256, "executionId": ref.execution_id,
                           "expectedSchema": ref.expected_schema}}
        return self.api.handle("wind-token", body), ref

    def submit_all(self, arts):
        return {key_of(a): self.submit(a)[0].result for a in arts}


@pytest.fixture(scope="module")
def patches(tmp_path_factory):
    st = make_store(tmp_path_factory.mktemp("store"))
    w = DryRunWriter()
    rep = publish(st, CFG, w, now=NOW, run_summary={"runAt": C.iso(NOW), "errors": [], "seconds": 90}, directory=DIRECTORY)
    assert rep["ok"], rep["errors"]
    return w.patches


def ctx(minutes=0, n=1, **kw):
    return A.BuildContext(generated_at=iso(T + timedelta(minutes=minutes)), execution_id=uuid4(1000 + n), code_version="abc123def456", **kw)


def build(patches, minutes=0, n=1, mutate=None, **kw):
    pp = copy.deepcopy(patches)
    if mutate:
        mutate(A.merge_patches(pp) if False else pp)
    res = A.build_artifacts(pp, ctx(minutes, n, **kw))
    A.seal(res.artifacts, output_fingerprint)
    return res


def key_of(a):
    return a["lineage"]["artifactSchema"] + (":" + a["scope"] if a.get("scope") else "")


def by_schema(res):
    """keyed 'schema' or 'schema:scope' (the lake-state schema is split into baseline scopes)."""
    return {key_of(a): a for a in res.artifacts}


# 1-4, 9 ---- valid Wind artifacts accepted, identity, schema, hash/reference, authorised child paths --------------------------------------------
def test_real_wind_output_is_accepted_by_publisher_shadow(patches, tmp_path):
    res = build(patches)
    assert set(by_schema(res)) == {LIVE, "wind-lake-state-v1:lake-static", "wind-lake-state-v1:fleet-readiness", "wind-registry-v1", "wind-source-registry-v1"}
    rig = Rig(tmp_path)
    out = rig.submit_all(res.artifacts)
    assert all(r["result"] == "SHADOW_READY" and r["live"] is False and r["mode"] == "SHADOW" for r in out.values()), out
    for sid, r in out.items():
        rec = rig.st.history.get_record("wind", r["publishId"])
        assert rec["status"] == "SHADOW" and rec["artifactSchema"] == sid.split(":")[0] and "publishedAt" not in rec          # 18 publication record, no live claim
        assert rec["outputFingerprint"] == by_schema(res)[sid]["lineage"]["outputFingerprint"] and rec["scope"] == (sid.split(":")[1] if ":" in sid else "default")
    assert len(rig.st.sink.submitted) == 5 and rig.st.sink.live_mutations == 0                                  # 17 no live mutation


def test_reference_hash_is_verified_and_tampering_is_caught(patches):
    rig = Rig()
    art = by_schema(build(patches))["wind-registry-v1"]
    ref = rig.st.writer("wind").write(art)
    bad = dataclasses.replace(ref, sha256="sha256:" + "ee" * 32)
    r = rig.st.publisher.evaluate_reference(bad)
    assert r.result == Result.REJECTED and "ARTIFACT_HASH_MISMATCH" in r.codes                                   # 4
    fake = dataclasses.replace(ref, brain_id="biological-state", location=ref.location.replace("/wind/", "/biological-state/"))
    assert rig.st.publisher.evaluate_reference(fake).result == Result.REJECTED


def test_plan_paths_are_exactly_the_authorised_wind_families(patches):
    rig = Rig()
    rig.submit_all(build(patches).artifacts)
    paths = {k for plan, _ in rig.st.sink.submitted for k in plan.updates}
    allowed = (r"lakes/[^/]+/(states|profiles|validation)/wind", r"lakeFleet/[^/]+/(slots|readiness|modelVersions)/wind", r"snapshots/[^/]+/latest/wind",
               r"brains/wind/[A-Za-z]+", r"validation/wind", r"health/brains/wind", r"activity/[^/]+-wind-[^/]+", r"sources/[a-z0-9-]+", r"health/sources/[a-z0-9-]+")
    import re
    stray = [p for p in paths if not any(re.fullmatch(a, p) for a in allowed)]
    assert stray == [] and "brains/wind/publication" in paths, stray                                              # 9 + Publisher-owned record
    kids = {p.split("/")[2] for p in paths if p.startswith("brains/wind/")} - {"publication"}
    assert kids <= {c for g in WIND_REGISTRY_CHILDREN.values() for c in g}
    assert "brains/wind" not in paths                                                                            # whole node never written


# 5-6, 16 ---- lineage + independently verified fingerprint, deterministic plan --------------------------------------------------------------
def _indep_fp(art):
    vol = {"generatedAt", "publishedAt", "checkedAt", "ageHours", "durationMs"} | set(A.WIND_VOLATILE_EXTRA)

    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in sorted(o.items()) if k not in vol}
        if isinstance(o, list):
            return [strip(v) for v in o]
        return round(o, 9) if isinstance(o, float) else o
    ms = [{"op": m["op"], "path": m["path"], "value": strip(m["value"])} for m in sorted(art["mutations"], key=lambda m: m["path"])]
    body = {"brainId": art["lineage"]["brainId"], "artifactSchema": art["lineage"]["artifactSchema"], "mutations": ms}
    return "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def test_output_fingerprint_independently_verified(patches):
    for a in build(patches).artifacts:
        assert a["lineage"]["outputFingerprint"] == _indep_fp(a)


def test_builder_is_deterministic(patches):
    a, b = build(patches), build(copy.deepcopy(patches))
    assert [A.canonical(x) for x in a.artifacts] == [A.canonical(x) for x in b.artifacts]
    p1, p2 = Rig(), Rig()
    p1.submit_all(a.artifacts); p2.submit_all(b.artifacts)
    assert [pl.canonical() for pl, _ in p1.st.sink.submitted] == [pl.canonical() for pl, _ in p2.st.sink.submitted]       # 16


def test_lineage_is_complete_and_honest(patches):
    for a in build(patches).artifacts:
        lin = a["lineage"]
        assert lin["brainId"] == "wind" and lin["lifecycle"] == "CALIBRATION" and lin["reviewStatus"] == "UNREVIEWED" and lin["validationStatus"] == "NOT_VALIDATED"
        assert lin["knowledgeRelease"] == lin["manifestRef"] == lin["manifestSha256"] == "NONE"                          # no canonical Wind release yet (declared, not invented)
        assert lin["artifactId"].startswith("sha256:") and lin["codeVersion"] == "abc123def456"
    fr = by_schema(build(patches))[LIVE]["freshness"]
    assert fr["freshnessStatus"] == "FRESH" and "evidenceObservedAt" in fr and "staleAfter" in fr and "expiresAt" not in fr


# 7-8 ---- SKIP / SHADOW semantics -------------------------------------------------------------------------------------------------------
def test_unchanged_is_skip_changed_is_shadow_and_volatile_fields_do_not_count(patches):
    rig = Rig()
    first = rig.submit_all(build(patches, minutes=0, n=1).artifacts)
    assert {r["result"] for r in first.values()} == {"SHADOW_READY"}
    again = build(patches, minutes=60, n=2)                                                                         # new run, same material
    # volatile-only drift: timestamps that change every run
    for a in again.artifacts:
        for m in a["mutations"]:
            v = m["value"]
            if isinstance(v, dict):
                for k in ("updatedAt", "lastUpdatedAt", "lastRun", "lastSuccess", "lastFetchAt", "durationMs"):
                    if k in v:
                        v[k] = "2026-10-15T04:00:00Z" if k != "durationMs" else 99999
            # NOTE: scalar CHILD mutations (/brains/wind/updatedAt, /brains/wind/lastSuccessfulRun) are deliberately NOT drifted here: Publisher V1
            # strips volatile keys inside dict values only, so these two always count as material (see test_scalar_volatile_children_are_material).
    A.seal(again.artifacts, output_fingerprint)
    assert {r["result"] for r in rig.submit_all(again.artifacts).values()} == {"SKIP"}                               # 7
    assert len(rig.st.sink.submitted) == 5

    changed = build(patches, minutes=120, n=3)
    for m in by_schema(changed)[LIVE]["mutations"]:
        if m["path"].endswith("/states/wind"):
            m["value"]["sustainedMph"] = (m["value"].get("sustainedMph") or 0) + 3.5
            break
    A.seal(changed.artifacts, output_fingerprint)
    out = rig.submit_all(changed.artifacts)
    assert out[LIVE]["result"] == "SHADOW_READY" and out["wind-registry-v1"]["result"] == "SKIP"                       # 8
    assert {k: v["result"] for k, v in out.items() if k != LIVE} == {k: "SKIP" for k in out if k != LIVE}            # slow scopes do not rewrite
    assert len(rig.st.sink.submitted) == 6 and rig.st.sink.live_mutations == 0
    assert len(rig.st.sink.submitted[-1][0].updates) < 40                                                          # only live state paths + publication, not ~700


# 19-20 ---- baseline comparison and ordering ------------------------------------------------------------------------------------------
def test_older_artifact_than_baseline_is_rejected(patches):
    rig = Rig()
    rig.submit_all(build(patches, minutes=60, n=1).artifacts)
    older = build(patches, minutes=0, n=2)
    for m in by_schema(older)[LIVE]["mutations"]:
        if m["path"].endswith("/states/wind"):
            m["value"]["sustainedMph"] = 77.7
            break
    A.seal(older.artifacts, output_fingerprint)
    r, _ = rig.submit(by_schema(older)[LIVE])
    assert r.result["result"] == "REJECTED" and "ARTIFACT_OLDER_THAN_BASELINE" in r.result["codes"]                         # 20
    head = rig.st.history.head("wind", "wind-lake-state-v1", "lake-live")
    assert head is not None                                                                                          # 19 baseline exists and was not moved
    assert len(rig.st.sink.submitted) == 5


# 10-14 ---- forbidden paths are rejected through the full handoff ---------------------------------------------------------------------
LAKE = "Guntersville_AL"
LIVE = "wind-lake-state-v1:lake-live"


@pytest.mark.parametrize("schema,path,code", [
    ("wind-registry-v1", "/brains/wind", "BRAIN_NODE_REPLACEMENT"),                                                  # 10
    ("wind-registry-v1", "/brains/wind/publication", "RESERVED_PATH"),                                               # 11
    ("wind-lake-state-v1", "/speciesProfiles/common_carp", "CROSS_DOMAIN_PATH"),                                     # 12
    ("wind-lake-state-v1", "/species/common_carp", "CROSS_DOMAIN_PATH"),
    ("wind-lake-state-v1", f"/lakes/{LAKE}/speciesPresence", "CROSS_DOMAIN_PATH"),                                   # 13
    ("wind-lake-state-v1", f"/lakes/{LAKE}/states/waterTemp", "CROSS_DOMAIN_PATH"),                                  # 14
    ("wind-lake-state-v1", f"/lakes/{LAKE}/states/waterTemperature", "PATH_NOT_AUTHORIZED"),                        # snapshot-field spelling: still rejected
    ("wind-lake-state-v1", f"/lakes/{LAKE}/states/waterClarity", "CROSS_DOMAIN_PATH"),
    ("wind-lake-state-v1", f"/lakes/{LAKE}/states/depth", "CROSS_DOMAIN_PATH"),
    ("wind-lake-state-v1", f"/lakes/{LAKE}/states/lake", "CROSS_DOMAIN_PATH"),
    ("wind-lake-state-v1", "/brains/biological-state/status", "CROSS_DOMAIN_PATH"),
    ("wind-lake-state-v1", "/scores/wind", "CROSS_DOMAIN_PATH"),
    ("wind-lake-state-v1", "/control/overview", "CROSS_DOMAIN_PATH"),
    ("wind-registry-v1", "/health/jobs/wind-hourly", None),                                                          # not authorised by any Wind schema
    ("wind-registry-v1", "/brains/wind/someUnapprovedChild", "PATH_NOT_AUTHORIZED"),
])
def test_forbidden_paths_rejected_through_full_handoff(patches, schema, path, code):
    rig = Rig()
    art = by_schema(build(patches))[LIVE if schema == "wind-lake-state-v1" else schema]
    art["mutations"].append({"op": "SET", "path": path, "value": {"x": 1}})
    A.seal([art], output_fingerprint)
    r, _ = rig.submit(art)
    assert r.result["result"] == "REJECTED" and rig.st.sink.submitted == []
    if code:
        assert code in r.result["codes"]
    # the legitimate mutations in the same artifact are NOT published either (all-or-nothing)
    assert rig.st.sink.live_mutations == 0


# 15 ---- null / missing cannot delete -----------------------------------------------------------------------------------------------
def test_null_or_empty_values_cannot_delete(patches):
    rig = Rig()
    assert {r["result"] for r in rig.submit_all(build(patches).artifacts).values()} == {"SHADOW_READY"}
    for bad in (None, {"a": None}, {}, []):
        art = by_schema(build(patches, minutes=30, n=5))[LIVE]
        art["mutations"][0]["value"] = bad
        A.seal([art], output_fingerprint)
        r, _ = rig.submit(art)
        assert r.result["result"] == "FAILED_VALIDATION" and r.result["codes"][0] in ("NULL_VALUE", "NULL_IN_VALUE", "EMPTY_VALUE"), r.result
    assert len(rig.st.sink.submitted) == 5
    assert not any(m["op"] == "DELETE" for a in build(patches).artifacts for m in a["mutations"])


def test_builder_never_emits_null_or_empty_and_refuses_nulls_in_lists(patches):
    def walk(o):
        if o is None or o == {} or o == []:
            return False
        if isinstance(o, dict):
            return all(walk(v) for v in o.values())
        if isinstance(o, list):
            return all(walk(v) for v in o)
        return True
    for a in build(patches).artifacts:
        assert all(walk(m["value"]) for m in a["mutations"])
    with pytest.raises(A.ArtifactBuildError):
        A.build_artifacts([{"lakes/Guntersville_AL/states/wind": {"hourly": [None, 1]}}], ctx())


# registry ownership -------------------------------------------------------------------------------------------------------------------
def test_registry_is_published_as_approved_children_only(patches):
    reg = by_schema(build(patches))["wind-registry-v1"]
    kids = {m["path"].split("/")[3] for m in reg["mutations"] if m["path"].startswith("/brains/wind/")}
    approved = {c for g in WIND_REGISTRY_CHILDREN.values() for c in g}
    assert kids and kids <= approved and A.REGISTRY_CHILDREN == approved                                              # builder list == Publisher list
    assert "publication" not in kids and "certification" not in kids
    paths = [m["path"] for m in reg["mutations"]]
    assert "/brains/wind" not in paths
    assert "lastError" not in kids                                                                                   # None today -> omitted, never null


def test_unauthorised_paths_are_reported_not_smuggled(patches):
    res = build(patches)
    d = {x["path"].split("/")[-1] if "lakeId" in x["path"] else x["path"] for x in res.dropped}
    assert "/health/jobs/wind-hourly" in {x["path"] for x in res.dropped}
    assert any(x["path"].endswith("/lakeId") for x in res.dropped) and any("brainVersions" in x["path"] for x in res.dropped)
    published = {m["path"] for a in res.artifacts for m in a["mutations"]}
    assert not any(p.endswith("/lakeId") or "brainVersions" in p or p.startswith("/health/jobs") for p in published)
    assert res.unsupported == []


def test_equivalence_with_current_live_writer(patches):
    """Every value the existing writer stores is in the artifact (modulo RTDB-dropped nulls/empties and the reported unauthorised paths)."""
    flat = A.merge_patches(patches)
    res = build(patches)
    pub = {m["path"].lstrip("/"): m["value"] for a in res.artifacts for m in a["mutations"]}
    dropped = {x["path"].lstrip("/") for x in res.dropped}
    for key, val in flat.items():
        if key in dropped or key == "brains/wind":
            continue
        norm = A.normalize(val)
        if norm is A._ABSENT:
            assert key not in pub
        else:
            assert pub[key] == norm, key
    reg = flat["brains/wind"]
    for child, val in reg.items():
        norm = A.normalize(val)
        if norm is not A._ABSENT:
            assert pub[f"brains/wind/{child}"] == norm
    assert res.omitted_unknown > 0


def test_no_score_is_changed_by_the_builder(patches):
    res = build(patches)
    reg = {m["path"]: m["value"] for m in by_schema(res)["wind-registry-v1"]["mutations"]}
    assert reg["/brains/wind/scores"] == A.merge_patches(patches)["brains/wind"]["scores"]
    assert all(not m["path"].startswith("/scores") for a in res.artifacts for m in a["mutations"])


def test_scalar_volatile_children_are_material(patches):
    """PUBLISHER FINDING (not changed here): volatile_extra strips dict KEYS inside a value, but child-level publication makes `lastSuccessfulRun` and
    `updatedAt` scalar mutations addressed by path, which are never stripped. Between two runs with identical science the registry artifact therefore
    still reads as changed (SHADOW_READY, never SKIP) while lake-state and sources SKIP. Needs a Publisher-side rule (platform lane)."""
    rig = Rig()
    rig.submit_all(build(patches, minutes=0, n=1).artifacts)
    later = build(patches, minutes=60, n=2)
    for m in by_schema(later)["wind-registry-v1"]["mutations"]:
        if m["path"] in ("/brains/wind/lastSuccessfulRun", "/brains/wind/updatedAt"):
            m["value"] = "2026-10-15T04:00:00Z"
    A.seal(later.artifacts, output_fingerprint)
    out = rig.submit_all(later.artifacts)
    assert out["wind-registry-v1"]["result"] == "SHADOW_READY" and {v["result"] for k, v in out.items() if k != "wind-registry-v1"} == {"SKIP"}


def test_five_artifacts_are_five_independent_atomic_plans(patches):
    """PUBLISHER FINDING: atomicity is per artifact. One wind-hourly run yields three schemas, hence three plans: lake state/fleet/snapshot, registry/health,
    sources. Cross-schema atomicity (readiness counts vs fleet rows) needs a Publisher-side artifact group or a single Wind schema."""
    rig = Rig()
    rig.submit_all(build(patches).artifacts)
    plans = [pl for pl, _ in rig.st.sink.submitted]
    body = [{k for k in pl.updates if k != "brains/wind/publication"} for pl in plans]
    assert len(plans) == 5 and sum(len(b) for b in body) == len(set().union(*body))                      # disjoint payloads
    assert all("brains/wind/publication" in pl.updates for pl in plans)                                  # ...but each plan overwrites the ONE publication node: last wins


# 2, 3, 5 ---- identity, schema and lineage are verified, not assumed ------------------------------------------------------------------
def test_identity_schema_and_lineage_are_verified(patches):
    rig = Rig()
    art = by_schema(build(patches))["wind-registry-v1"]

    other = copy.deepcopy(art)
    other["lineage"]["brainId"] = "biological-state"                                  # Wind identity submitting as Fish
    A.seal([other], output_fingerprint)
    with pytest.raises(Exception):                                                    # the Wind-scoped writer refuses to store another Brain's artifact
        rig.st.writer("wind").write(other)

    unknown = copy.deepcopy(art)
    unknown["lineage"]["artifactSchema"] = "wind-secret-v9"; unknown["lineage"]["artifactId"] = "sha256:" + "01" * 32
    r, _ = rig.submit(unknown)
    assert r.result["result"] == "REJECTED" and r.result["codes"] == ["UNKNOWN_SCHEMA"]

    broken = copy.deepcopy(art)
    del broken["lineage"]["codeVersion"]; broken["lineage"]["artifactId"] = "sha256:" + "02" * 32
    r, _ = rig.submit(broken)
    assert r.result["result"] == "FAILED_VALIDATION" and "LINEAGE_INCOMPLETE" in r.result["codes"]

    tampered = copy.deepcopy(art)
    tampered["mutations"][0]["value"] = "TAMPERED"; tampered["lineage"]["artifactId"] = "sha256:" + "03" * 32     # declared fingerprint no longer matches
    r, _ = rig.submit(tampered)
    assert r.result["result"] == "FAILED_VALIDATION" and "FINGERPRINT_MISMATCH" in r.result["codes"]
    assert rig.st.sink.submitted == []
