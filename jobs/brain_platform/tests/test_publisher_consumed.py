"""Publisher envelope slot `consumed` (consumption-lineage-v1): accepted and validated, carried into the publication record, and NEVER part of the
semantic fingerprint — ephemeral consumedAt / execution metadata can never force a republish."""
import copy

import pytest

from publisher_fixtures import T0, iso, make, wind_artifact
from sector_brain_platform.publisher import seal_artifact, seal_bundle, default_registry
from sector_brain_platform.publisher.artifact import parse
from sector_brain_platform.publisher.canonical import material
from sector_brain_platform.publisher.model import Rejected
import datetime as dt


def consumed(n=0, **over):
    e = {"dependencyId": "provider:noaa-nbm-v5", "evidenceObservedAt": iso(T0 - dt.timedelta(minutes=30 + n)), "staleAfter": iso(T0 + dt.timedelta(hours=2)),
         "consumedAt": iso(T0 + dt.timedelta(minutes=n)), "stateVersion": "cycle-12z"}
    e.update(over)
    return [e, {"dependencyId": "registry:lakes", "fingerprint": "sha256:" + "cd" * 32, "consumedAt": iso(T0 + dt.timedelta(minutes=n))}]


def test_consumed_is_accepted_validated_and_recorded_in_the_publication_record():
    pub, hist, sink = make()
    art = wind_artifact(1); art["consumed"] = consumed()
    r = pub.evaluate(art, producer="wind")
    assert r.result.value == "SHADOW_READY"
    rec = hist.get_record("wind", r.publish_id)
    assert [c["dependencyId"] for c in rec["consumed"]] == ["provider:noaa-nbm-v5", "registry:lakes"]
    assert rec["consumed"][0]["dependencyType"] == "PROVIDER_DATA" and rec["consumed"][1]["dependencyType"] == "PLATFORM_REGISTRY"
    plan_rec = [v for k, v in sink.submitted[0][0].updates.items() if k.endswith("/publication")][0]
    assert plan_rec["consumed"] == rec["consumed"]
    p = parse(art, "wind", default_registry())
    assert p.consumed and p.consumed[0]["dependencyId"] == "provider:noaa-nbm-v5"
    assert parse(wind_artifact(2), "wind", default_registry()).consumed is None                      # absent stays None, not []


@pytest.mark.parametrize("bad", [
    "not a list", [{"dependencyId": "nbm"}], [{"dependencyId": "provider:noaa-nbm-v5", "consumedAt": "now"}],
    [{"dependencyId": "provider:noaa-nbm-v5", "weight": 0.5}], [{"dependencyId": "brain:x"}, {"dependencyId": "brain:x"}],
    [{"dependencyId": "brain:x", "dependencyType": "PROVIDER_DATA"}], [{"dependencyId": "brain:x", "freshnessStatus": "GOOD"}],
])
def test_invalid_consumed_fails_validation_and_nothing_is_planned(bad):
    pub, hist, sink = make()
    art = wind_artifact(1); art["consumed"] = bad
    r = pub.evaluate(art, producer="wind")
    assert r.result.value == "FAILED_VALIDATION" and r.codes == ["CONSUMED_INVALID"] and sink.submitted == []
    with pytest.raises(Rejected):
        parse(art, "wind", default_registry())


def test_consumed_is_outside_the_semantic_fingerprint_and_never_forces_a_republish():
    pub, hist, sink = make()
    a = wind_artifact(1); a["consumed"] = consumed(0)
    assert pub.evaluate(a, producer="wind").result.value == "SHADOW_READY"
    b = wind_artifact(2, minutes=30); b["consumed"] = consumed(30, stateVersion="cycle-18z", evidenceObservedAt=iso(T0 + dt.timedelta(minutes=20)))
    assert b["lineage"]["outputFingerprint"] == a["lineage"]["outputFingerprint"]                     # same semantic state, different lineage
    r = pub.evaluate(b, producer="wind")
    assert r.result.value == "SKIP" and len(sink.submitted) == 1
    assert hist.get_record("wind", r.publish_id)["consumed"][0]["stateVersion"] == "cycle-18z"          # the SKIP record still says what was consumed
    c = wind_artifact(3, minutes=45)                                                                # no lineage at all: still the same state
    assert pub.evaluate(c, producer="wind").result.value == "SKIP"
    mat = material("wind", "wind-lake-state-v1", a["mutations"])
    assert "consumed" not in str(mat) and "consumedAt" not in str(mat)
    d = wind_artifact(4, minutes=60, speed=9.9); d["consumed"] = consumed(60)                        # a real state change still publishes (within the fixture clock)
    assert pub.evaluate(d, producer="wind").result.value == "SHADOW_READY" and len(sink.submitted) == 2


def test_seal_helpers_carry_consumed_for_v1_and_v2():
    muts = [{"op": "SET", "path": "/lakes/test_lake_alpha/states/wind", "value": {"kind": "modeled", "windMS": 1.0}}]
    v1 = seal_artifact(brain_id="wind", artifact_schema="wind-lake-state-v1", mutations=muts, lifecycle="CALIBRATION", review_status="UNREVIEWED",
                       validation_status="NOT_VALIDATED", generated_at=iso(T0), execution_id="00000001-0000-4000-8000-000000000001", code_version="c",
                       input_fingerprint="sha256:" + "ab" * 32, consumed=consumed())
    v1b = seal_artifact(brain_id="wind", artifact_schema="wind-lake-state-v1", mutations=muts, lifecycle="CALIBRATION", review_status="UNREVIEWED",
                        validation_status="NOT_VALIDATED", generated_at=iso(T0), execution_id="00000001-0000-4000-8000-000000000001", code_version="c",
                        input_fingerprint="sha256:" + "ab" * 32)
    assert v1["consumed"] == consumed() and "consumed" not in v1b and v1["lineage"]["outputFingerprint"] == v1b["lineage"]["outputFingerprint"]
    v2 = seal_bundle(brain_id="wind", bundle_id="wind-publication-v1", sections=[{"artifactSchema": "wind-lake-state-v1", "scope": "lake-live", "mutations": muts, "freshness": {"freshnessStatus": "FRESH"}}],
                     lifecycle="CALIBRATION", review_status="UNREVIEWED", validation_status="NOT_VALIDATED", generated_at=iso(T0),
                     execution_id="00000001-0000-4000-8000-000000000001", code_version="c", input_fingerprint="sha256:" + "ab" * 32, consumed=consumed())
    assert v2["consumed"] == consumed() and "consumed" not in v2["lineage"]
    pub, hist, sink = make()
    assert pub.evaluate(copy.deepcopy(v2), producer="wind").result.value == "SHADOW_READY"
