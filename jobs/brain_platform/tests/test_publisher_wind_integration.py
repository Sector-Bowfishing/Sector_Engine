"""The Wind shadow-integration contract (what Wind's certification session can rely on). Runs the complete handoff:
Brain writes artifact -> API signal (reference) -> Orchestrator loads -> Publisher validates -> SHADOW. No live system is touched."""
import datetime as dt
import itertools

import pytest

from publisher_fixtures import LAKE_A, LAKE_B, T0, uuid4, wind_artifact, wind_state
from sector_brain_platform.publisher import Result, local_shadow_stack, seal_artifact
from sector_brain_platform.publisher.api import AllowlistAuthorizer, Caller, OrchestratorApi


class Authn:
    def authenticate(self, cred):
        return Caller("wind-brain-identity") if cred == "wind-token" else None


def rig(tmp_path=None, id_base=0):
    ids = itertools.count(1 + id_base)
    st = local_shadow_stack(tmp_path, clock=lambda: T0 + dt.timedelta(hours=2), id_factory=lambda: uuid4(next(ids) + 50000))
    api = OrchestratorApi(Authn(), AllowlistAuthorizer({"wind-brain-identity": {"ARTIFACT": {"SUBMIT_ARTIFACT@wind"}}}), st.dispatcher)
    n = itertools.count(900 + id_base)

    def publish(art):
        ref = st.writer("wind").write(art)
        body = {"apiVersion": "orchestrator-api-v1", "requestId": uuid4(next(n)), "requestKind": "ARTIFACT", "brainId": "wind", "action": "SUBMIT_ARTIFACT",
                "params": {"artifactId": ref.artifact_id, "artifactRef": ref.location, "artifactSha256": ref.sha256, "executionId": ref.execution_id,
                           "expectedSchema": ref.expected_schema}}
        return api.handle("wind-token", body)
    return st, publish


def test_wind_shadow_contract_end_to_end(tmp_path):
    st, publish = rig(tmp_path)
    first = publish(wind_artifact(n=1))                                                              # artifact + reference/hash + schema + lineage + fingerprint accepted
    assert first.status == 200 and first.result["result"] == "SHADOW_READY" and first.result["live"] is False
    rec = st.history.get_record("wind", first.result["publishId"])
    assert rec["status"] == "SHADOW" and rec["artifactSchema"] == "wind-lake-state-v1" and rec["outputFingerprint"].startswith("sha256:")
    again = wind_artifact(n=2, minutes=30)                                                           # new run, same material -> SKIP
    again["mutations"][0]["value"]["generatedAt"] = "2026-10-15T09:00:00Z"
    again["lineage"]["outputFingerprint"] = wind_artifact(n=1)["lineage"]["outputFingerprint"]
    assert publish(again).result["result"] == "SKIP"
    changed = publish(wind_artifact(n=3, minutes=60, speed=9.1))                                     # changed -> SHADOW
    assert changed.result["result"] == "SHADOW_READY"
    plan = st.sink.submitted[-1][0]
    assert set(plan.updates) == {f"lakes/{LAKE_A}/states/wind", f"lakes/{LAKE_A}/profiles/wind", f"lakeFleet/{LAKE_A}/slots/wind", f"lakes/{LAKE_B}/states/wind",
                                 "brains/wind/publication"}                                          # authorized Wind paths + the Publisher's own record, one plan
    assert len(st.sink.submitted) == 2 and st.sink.live_mutations == 0


@pytest.mark.parametrize("path,code", [("/speciesProfiles/common_carp", "CROSS_DOMAIN_PATH"), (f"/lakes/{LAKE_A}/speciesPresence", "CROSS_DOMAIN_PATH"),
                                       ("/brains/wind/publication", "RESERVED_PATH"), ("/brains/wind", "BRAIN_NODE_REPLACEMENT"),
                                       ("/scores/wind", "CROSS_DOMAIN_PATH")])
def test_wind_protected_paths_are_rejected_through_the_full_handoff(path, code):
    st, publish = rig()
    art = wind_artifact(n=1, artifactSchema="wind-registry-v1", mutations=[{"op": "SET", "path": "/brains/wind/health", "value": "HEALTHY"},
                                                                          {"op": "SET", "path": path, "value": {"x": 1}}])
    r = publish(art)
    assert r.result["result"] == "REJECTED" and code in r.result["codes"] and st.sink.submitted == []


def test_null_on_miss_cannot_delete_through_the_full_handoff():
    st, publish = rig()
    assert publish(wind_artifact(n=1)).result["result"] == "SHADOW_READY"
    nulled = wind_artifact(n=2, minutes=30, outputFingerprint="sha256:" + "00" * 32,
                           mutations=[{"op": "SET", "path": f"/lakes/{LAKE_A}/states/wind", "value": {"windMS": None}}])
    r = publish(nulled)
    assert r.result["result"] == "FAILED_VALIDATION" and r.result["codes"] == ["NULL_IN_VALUE"] and len(st.sink.submitted) == 1


def test_wind_plan_is_deterministic_across_independent_runs():
    plans = []
    for _ in range(2):
        st, publish = rig()
        publish(wind_artifact(n=1))
        plans.append(st.sink.submitted[0][0])
    assert plans[0].canonical() == plans[1].canonical()


def test_seal_artifact_produces_what_the_publisher_accepts():
    st, publish = rig()
    art = seal_artifact(brain_id="wind", artifact_schema="wind-lake-state-v1", mutations=[{"op": "SET", "path": f"/lakes/{LAKE_A}/states/wind", "value": wind_state()}],
                        lifecycle="SHADOW", review_status="UNREVIEWED", validation_status="NOT_VALIDATED", generated_at="2026-10-15T03:00:00Z",
                        execution_id=uuid4(31), code_version="abc123", input_fingerprint="sha256:" + "11" * 32,
                        freshness={"freshnessStatus": "FRESH"})
    assert publish(art).result["result"] == "SHADOW_READY"


def test_local_directory_stack_survives_a_restart(tmp_path):
    st, publish = rig(tmp_path)
    publish(wind_artifact(n=1))
    st2, publish2 = rig(tmp_path, id_base=1000)                                                                    # a new process on the same directory
    assert publish2(wind_artifact(n=2, minutes=30)).result["result"] == "SKIP"
    assert st2.history.head("wind", "wind-lake-state-v1") is not None
