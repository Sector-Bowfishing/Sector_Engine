import json, os
import pytest
from sector_wind.store import GcsStore, LocalStore, open_store
from sector_wind import field as F

def test_gcs_refuses_without_approval(monkeypatch):
    monkeypatch.delenv("SECTOR_WIND_GCS_APPROVED", raising=False)
    with pytest.raises(PermissionError):
        open_store("gs://some-bucket/wind")

def test_gcs_never_opens_shared_buckets(monkeypatch):
    monkeypatch.setenv("SECTOR_WIND_GCS_APPROVED", "yes")
    for b in ("sector-lake-surface", "sector-clarity-candidate"):
        with pytest.raises(PermissionError):
            GcsStore(b, "wind/v1")

def test_local_roundtrip_and_ledger(tmp_path):
    s = LocalStore(str(tmp_path)); s.put_json("a/b.json.gz", {"x": [1, None]})
    assert s.get_json("a/b.json.gz") == {"x": [1, None]}
    s.append_ledger({"product": "NBM", "status": "complete"}); assert s.read_ledger()[0]["status"] == "complete"

def test_assignment_is_deterministic_and_roughly_40_percent():
    ids = [F.session_id("guntersville", f"2026-11-{d:02d}", o) for d in range(1, 31) for o in ("michael", "cory")]
    a = [F.assignment(i) for i in ids]
    assert a == [F.assignment(i) for i in ids]
    share = a.count("calibration") / len(a)
    assert 0.2 < share < 0.6

def test_scoring_map_and_severe_miss():
    assert F.predicted_class(1, "T1") == 1 and F.predicted_class(1, "T4") == 3 and F.predicted_class(4, "T2") == 4
    assert F.severe_miss(1, 4) and F.severe_miss(5, 1) and F.severe_miss(2, 5) and not F.severe_miss(2, 4)
    m = F.surface_metrics([{"predicted": 2, "observed": 2}, {"predicted": 2, "observed": 3}, {"predicted": 1, "observed": 4}])
    assert m["exact"] == pytest.approx(1/3) and m["within1"] == pytest.approx(2/3) and m["severe"] == pytest.approx(1/3)

def test_concordance_ties_and_credit():
    pairs = [{"session": "s1", "hm0_A": 0.10, "hm0_B": 0.02, "obs_A": 3, "obs_B": 1},   # concordant
             {"session": "s2", "hm0_A": 0.10, "hm0_B": 0.02, "obs_A": 2, "obs_B": 2},   # observed tie -> 0.5
             {"session": "s3", "hm0_A": 0.02, "hm0_B": 0.10, "obs_A": 3, "obs_B": 1},   # B predicted more exposed, discordant
             {"session": "s4", "hm0_A": 0.10, "hm0_B": 0.095, "obs_A": 3, "obs_B": 1}]  # prediction tie, excluded
    c = F.concordance(pairs)
    assert c["n"] == 3 and c["predictionTies"] == 1 and c["concordance"] == pytest.approx(0.5)

def test_certify_requires_freeze_and_runs_once(tmp_path):
    with pytest.raises(PermissionError):
        F.certify(str(tmp_path), str(tmp_path / "missing.json"), [], [])
    fz = tmp_path / "WIND_CALIBRATION_FREEZE.json"; fz.write_text(json.dumps({"v": 1}))
    r = F.certify(str(tmp_path), str(fz), [{"predicted": 1, "observed": 1}], [])
    assert r["sufficient"] is False
    with pytest.raises(PermissionError):
        F.certify(str(tmp_path), str(fz), [], [])

def test_aux_diagnostics_do_not_touch_frozen_metrics():
    rows = [{"predictedTexture": "T3", "observedTexture": "T2"}, {"predictedTexture": "T1", "observedTexture": "T1"}]
    m = F.texture_metrics(rows)
    assert m["n"] == 2 and m["exact"] == 0.5 and m["meanSignedError"] == 0.5
    assert F.tags({"predicted": 3, "observed": 1, "shelterFeatures": ["tree line"]}) == ["possibleShelterMiss"]
    assert F.tags({"predicted": 1, "observed": 3}) == ["candidateUnderpredicts"]
    c = F.pair_contrast({}, {"fetchM": 4000, "hm0M": 0.1, "windMS": 5, "texture": "T3"}, {"fetchM": 200, "hm0M": 0.02, "windMS": 4.5, "texture": "T3"})
    assert c["fetchRatio"] == 20 and abs(c["hm0Ratio"] - 5) < 1e-9 and c["windDifferenceAtoB"] == 0.5
    # the frozen predicted_class map is unchanged
    assert F.predicted_class(2, "T3") == 2 and F.TEXTURE_FLOOR == {"T1": 1, "T2": 2, "T3": 2, "T4": 3}
