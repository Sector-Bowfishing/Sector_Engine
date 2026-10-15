"""Orchestrator API contract (requirements 20, 21): bounded CONTROL / REVIEW / RESEARCH requests; no arbitrary database mutation is expressible."""
import copy

import pytest

from publisher_fixtures import uuid4
from sector_brain_platform.publisher import api
from sector_brain_platform.publisher.api import AllowlistAuthorizer, Caller, OrchestratorApi, validate_request

OPS = Caller("ops-user-1")


class FakeAuthn:
    def authenticate(self, credential):
        return {"good-token": OPS, "other-token": Caller("ops-user-2")}.get(credential)


class Recorder:
    def __init__(self):
        self.calls = []

    def control(self, r):
        self.calls.append(("control", r)); return {"requestId": r.request_id}

    def review(self, r):
        self.calls.append(("review", r)); return {}

    def research(self, r):
        self.calls.append(("research", r)); return {}

    def artifact(self, r):
        self.calls.append(("artifact", r)); return {}


GRANTS = {"ops-user-1": {"CONTROL": {"RUN_NOW", "PAUSE", "RESUME", "SET_MANUAL", "CHANGE_PROTECTED_SCHEDULE"}, "REVIEW": {"SUBMIT_REVIEW", "ACCEPT_RULE"},
                         "RESEARCH": {"RESEARCH_GAP"}}, "ops-user-2": {"RESEARCH": {"RESEARCH_GAP"}}}


def mk():
    d = Recorder()
    return OrchestratorApi(FakeAuthn(), AllowlistAuthorizer(GRANTS), d), d


def body(kind="CONTROL", action="RUN_NOW", brain="wind", n=1, **params):
    return {"apiVersion": "orchestrator-api-v1", "requestId": uuid4(n), "requestKind": kind, "brainId": brain, "action": action, "params": params or {"scope": "fleet"}}


def test_valid_requests_of_each_kind_reach_only_their_workflow():
    a, d = mk()
    assert a.handle("good-token", body()).outcome == "ACCEPTED"
    assert a.handle("good-token", body("REVIEW", "SUBMIT_REVIEW", n=2, itemId="item-1", verdict="APPROVE", note="ok")).outcome == "ACCEPTED"
    assert a.handle("good-token", body("RESEARCH", "RESEARCH_GAP", "biological-state", n=3, topic="spawn timing", priority=2)).outcome == "ACCEPTED"
    assert [c[0] for c in d.calls] == ["control", "review", "research"]
    assert all(not hasattr(r, "path") and not hasattr(r, "updates") and not hasattr(r, "value") for _, r in d.calls)


def test_authentication_and_authorization_come_first_and_deny_by_default():
    a, d = mk()
    assert a.handle("bad", body()).status == 401 and a.handle(None, body()).status == 401
    assert a.handle("other-token", body()).code == "ACTION_NOT_GRANTED" and a.handle("other-token", body()).status == 403                 # allowlisted, CONTROL not granted
    assert AllowlistAuthorizer({}).may_use_api(OPS) is False
    unlisted = OrchestratorApi(type("A", (), {"authenticate": lambda s, c: Caller("nobody")})(), AllowlistAuthorizer(GRANTS), d)
    assert unlisted.handle("x", body()).code == "NOT_ALLOWLISTED"
    assert d.calls == []


@pytest.mark.parametrize("extra", [{"path": "/lakes/x/states/wind"}, {"value": {"a": 1}}, {"updates": {"/a": 1}}, {"mutations": []}, {"rtdbPath": "/x"}, {"json": "{}"},
                                   {"data": {}}, {"sql": "drop"}, {"url": "https://example.invalid"}])
def test_arbitrary_database_writes_are_not_expressible(extra):
    a, d = mk()
    r = a.handle("good-token", {**body(), **extra})
    assert r.status == 400 and r.code == "UNKNOWN_FIELD" and d.calls == []


@pytest.mark.parametrize("params", [{"scope": "fleet", "path": "/lakes/x"}, {"scope": "fleet", "value": {"a": 1}}, {"scope": {"nested": 1}}, {"scope": ["fleet"]},
                                    {"scope": "/lakes/x"}, {"scope": "a" * 65}, {"scope": ""}, {"scope": True}])
def test_params_are_closed_scalar_and_bounded(params):
    a, d = mk()
    r = a.handle("good-token", body(**params))
    assert r.status == 400 and d.calls == [], params


def test_schema_bounds():
    a, _ = mk()
    ok = body("RESEARCH", "RESEARCH_GAP", "biological-state", topic="t")
    assert a.handle("good-token", ok).status == 200
    for bad in ({"topic": "t" * 201}, {"topic": "t", "detail": "d" * 4001}, {"topic": "t", "priority": 9}, {"topic": "t", "priority": True}, {"topic": "t", "speciesId": "Bad Id"},
                {"topic": "t", "lakeKey": "a/b"}, {}, {"topic": "t", "x": 1}):
        r = a.handle("good-token", body("RESEARCH", "RESEARCH_GAP", "biological-state", **bad) if bad else {**ok, "params": {}})
        assert r.status == 400, bad
    many = {f"p{i}": 1 for i in range(api.MAX_PARAMS + 1)}
    assert a.handle("good-token", {**ok, "params": many}).status == 400


def test_review_and_research_schemas_are_separate_from_control():
    a, _ = mk()
    assert a.handle("good-token", body("REVIEW", "RUN_NOW", scope="fleet")).code == "UNKNOWN_ACTION"
    assert a.handle("good-token", body("CONTROL", "RESEARCH_GAP", topic="t")).code == "UNKNOWN_ACTION"
    assert a.handle("good-token", body("DELETE", "RUN_NOW")).code == "UNKNOWN_KIND"
    assert a.handle("good-token", body(brain="made-up")).code == "UNKNOWN_BRAIN"
    assert a.handle("good-token", body("REVIEW", "SUBMIT_REVIEW", itemId="i", verdict="MAYBE")).code == "PARAM_ENUM"


@pytest.mark.parametrize("action", ["SET_ENGINE_MODE", "ACTIVATE_PRODUCTION", "PUBLISH_CUSTOMER", "PROMOTE_LIFECYCLE"])
def test_ungrantable_actions_are_rejected_even_if_an_allowlist_lists_them(action):
    d = Recorder()
    with pytest.raises(ValueError):                                  # the authorizer cannot even be constructed with them
        AllowlistAuthorizer({"ops-user-1": {"CONTROL": {action}}})
    a, _ = mk()
    r = a.handle("good-token", body(action=action, scope="fleet"))
    assert r.status == 400 and r.code == "NOT_GRANTABLE" and d.calls == []


def test_protected_actions_need_the_exact_confirmation_from_the_same_caller():
    a, d = mk()
    b = body(action="CHANGE_PROTECTED_SCHEDULE", jobId="wind-hourly", reason="maintenance")
    r = a.handle("good-token", b)
    assert r.outcome == "NEEDS_CONFIRMATION" and d.calls == []
    wrong = {**b, "confirm": {"by": "someone-else", "phrase": "CONFIRM CHANGE_PROTECTED_SCHEDULE wind"}}
    assert a.handle("good-token", wrong).outcome == "NEEDS_CONFIRMATION"
    right = {**b, "confirm": {"by": "ops-user-1", "phrase": "CONFIRM CHANGE_PROTECTED_SCHEDULE wind"}}
    assert a.handle("good-token", right).outcome == "ACCEPTED" and d.calls[0][1].confirmed is True
    assert a.handle("good-token", {**body(), "confirm": {"by": "ops-user-1", "phrase": "x"}}).code == "UNKNOWN_FIELD"      # confirm only where defined


def test_request_ids_must_be_uuid4_and_version_must_match():
    a, _ = mk()
    assert a.handle("good-token", {**body(), "requestId": "123"}).status == 400
    assert a.handle("good-token", {**body(), "apiVersion": "v0"}).status == 400
    assert a.handle("good-token", [1, 2]).status == 400 and a.handle("good-token", None).status == 400


def test_every_defined_action_has_a_param_schema_and_no_schema_field_looks_like_a_path_or_payload():
    assert set(api.PARAMS) == {a for acts in api.ACTIONS.values() for a in acts}
    banned = {"path", "paths", "value", "values", "updates", "mutations", "payload", "data", "json", "body", "node", "ref", "url"}
    assert not [(a, n) for a, fs in api.PARAMS.items() for n in fs if n.lower() in banned]
    assert all(f.kind in (str, int) for fs in api.PARAMS.values() for f in fs.values())
    assert not set(api.NOT_GRANTABLE) & {a for acts in api.ACTIONS.values() for a in acts}


def test_validate_request_returns_an_immutable_record_without_database_fields():
    r = validate_request(body(), OPS)
    assert r.requested_by == "ops-user-1" and r.kind == "CONTROL"
    with pytest.raises(Exception):
        r.action = "OTHER"
    assert set(vars(r)) == {"request_id", "kind", "brain_id", "action", "params", "requested_by", "confirmed"}


# ---- SUBMIT_ARTIFACT: the API signal identifies an artifact; it never carries content or a path -----------------------------------------------
import datetime as _dt
import itertools as _it

from publisher_fixtures import T0, wind_artifact
from sector_brain_platform.publisher import local_shadow_stack, sha256_ref


def art_api(grants=None):
    ids = _it.count(1)
    st = local_shadow_stack(clock=lambda: T0 + _dt.timedelta(hours=1), id_factory=lambda: uuid4(next(ids) + 50000))
    authz = AllowlistAuthorizer(grants or {"brain-wind": {"ARTIFACT": {"SUBMIT_ARTIFACT@wind"}}, "orchestrator": {"ARTIFACT": {"SUBMIT_ARTIFACT"}}})
    authn = type("A", (), {"authenticate": lambda s, c: {"w": Caller("brain-wind"), "o": Caller("orchestrator")}.get(c)})()
    return OrchestratorApi(authn, authz, st.dispatcher), st


def sub_body(ref, n=900, **over):
    b = {"apiVersion": "orchestrator-api-v1", "requestId": uuid4(n), "requestKind": "ARTIFACT", "brainId": ref.brain_id, "action": "SUBMIT_ARTIFACT",
         "params": {"artifactId": ref.artifact_id, "artifactRef": ref.location, "artifactSha256": ref.sha256, "executionId": ref.execution_id, "expectedSchema": ref.expected_schema}}
    b.update(over)
    return b


def test_submit_artifact_runs_the_publisher_in_shadow_and_returns_only_a_summary():
    api, st = art_api()
    ref = st.writer("wind").write(wind_artifact(n=1))
    r = api.handle("w", sub_body(ref))
    assert r.status == 200 and r.outcome == "ACCEPTED" and r.result["result"] == "SHADOW_READY" and r.result["live"] is False and r.result["mode"] == "SHADOW"
    assert set(r.result) == {"result", "publishId", "codes", "live", "mode"}                  # no plan, no paths, no values leave the Publisher via the API
    assert st.history.get_record("wind", r.result["publishId"])["requestId"] == uuid4(900)
    assert api.handle("w", sub_body(ref, n=901)).result["result"] == "SKIP"


def test_submit_artifact_rejections_come_from_the_publisher_not_the_caller():
    api, st = art_api()
    art = wind_artifact(n=1); art["mutations"].append({"op": "SET", "path": "/speciesProfiles/common_carp", "value": {"a": 1}})
    ref = st.writer("wind").write(art)
    r = api.handle("w", sub_body(ref))
    assert r.status == 200 and r.result["result"] == "REJECTED" and r.result["codes"] == ["CROSS_DOMAIN_PATH"] and st.sink.submitted == []


@pytest.mark.parametrize("extra", [{"path": "/lakes/x/states/wind"}, {"artifact": {"mutations": []}}, {"mutations": [{"op": "SET", "path": "/a", "value": 1}]},
                                   {"updates": {"/a": 1}}, {"value": {"a": 1}}, {"rtdbPath": "/x"}, {"plan": {}}])
def test_api_rejects_arbitrary_paths_and_mutation_json_on_artifact_submission(extra):
    api, st = art_api()
    ref = st.writer("wind").write(wind_artifact(n=1))
    r = api.handle("w", {**sub_body(ref), **extra})
    assert r.status == 400 and r.code == "UNKNOWN_FIELD" and st.sink.submitted == [] and st.history.records("wind") == []


@pytest.mark.parametrize("param", ["path", "artifact", "content", "mutations", "updates", "payload", "json", "location"])
def test_artifact_params_cannot_smuggle_content_or_paths(param):
    api, st = art_api()
    ref = st.writer("wind").write(wind_artifact(n=1))
    b = sub_body(ref); b["params"][param] = "/lakes/x/states/wind"
    r = api.handle("w", b)
    assert r.status == 400 and r.code == "UNKNOWN_PARAM" and st.history.records("wind") == []


def test_wind_cannot_submit_a_fish_artifact_namespace():
    api, st = art_api()
    fish = st.writer("biological-state").write(wind_artifact(n=5, brainId="biological-state", artifactSchema="biological-species-profile-v1"))
    # 1: Wind names itself but points at Fish's namespace
    r = api.handle("w", sub_body(fish, brainId="wind"))
    assert r.status == 400 and r.code == "NAMESPACE_VIOLATION"
    # 2: Wind submits as Fish: not granted for that Brain
    r = api.handle("w", sub_body(fish))
    assert r.status == 403 and r.code == "ACTION_NOT_GRANTED"
    # 3: an unscoped Orchestrator grant may name any Brain, but still only that Brain's own namespace
    assert api.handle("o", sub_body(fish, brainId="wind")).code == "NAMESPACE_VIOLATION"
    assert st.sink.submitted == [] and st.history.records("wind") == [] and st.history.records("biological-state") == []


@pytest.mark.parametrize("field,val,code", [("artifactSha256", "abc", "ARTIFACT_REF_INVALID"), ("artifactId", "nope", "ARTIFACT_REF_INVALID"),
                                            ("artifactRef", "artifacts/wind/../../x", "NAMESPACE_VIOLATION" if False else "ARTIFACT_REF_INVALID"),
                                            ("artifactRef", "lakes/x/states/wind", "NAMESPACE_VIOLATION"), ("executionId", "x", "ARTIFACT_REF_INVALID"),
                                            ("expectedSchema", "Not A Schema", "ARTIFACT_REF_INVALID"), ("artifactRef", "a" * 500, "PARAM_BOUNDS")])
def test_artifact_reference_is_bounded_and_canonical(field, val, code):
    api, st = art_api()
    ref = st.writer("wind").write(wind_artifact(n=1))
    b = sub_body(ref); b["params"][field] = val
    r = api.handle("w", b)
    assert r.status == 400 and r.code == code, (field, r.code)


def test_hash_mismatch_is_caught_when_the_publisher_loads_the_artifact():
    api, st = art_api()
    ref = st.writer("wind").write(wind_artifact(n=1))
    b = sub_body(ref); b["params"]["artifactSha256"] = sha256_ref(b"other")
    r = api.handle("w", b)
    assert r.status == 200 and r.result["result"] == "REJECTED" and r.result["codes"] == ["ARTIFACT_HASH_MISMATCH"]


def test_artifact_grants_are_per_brain_and_validated():
    with pytest.raises(ValueError):
        AllowlistAuthorizer({"c": {"ARTIFACT": {"SUBMIT_ARTIFACT@not-a-brain"}}})
    with pytest.raises(ValueError):
        AllowlistAuthorizer({"c": {"ARTIFACT": {"WRITE_PATH"}}})
    api, st = art_api({"brain-wind": {"CONTROL": {"RUN_NOW"}}})
    ref = st.writer("wind").write(wind_artifact(n=1))
    assert api.handle("w", sub_body(ref)).status == 403


def test_other_workflows_are_not_wired_in_shadow_and_say_so():
    api, st = art_api({"brain-wind": {"CONTROL": {"RUN_NOW"}}, "orchestrator": {}})
    r = api.handle("w", body())
    assert r.status == 200 and r.result == {"accepted": False, "reason": "workflow not wired in Publisher V1 shadow"}
