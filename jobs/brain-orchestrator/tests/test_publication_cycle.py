"""The local publication cycle: collects artifacts from a private store, reconciles Cloud Run execution records, records shadow separately, requests nothing while the Publisher is unarmed."""
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "brain_platform", "tests"))
sys.path.insert(0, os.path.join(HERE, ".."))
import publication_cycle as PC                                           # noqa: E402
from publisher_fixtures import T0, wind_artifact                          # noqa: E402
from sector_brain_platform.publisher import ArtifactWriter               # noqa: E402
from sector_brain_platform.publisher.storage import LocalDirObjectStore  # noqa: E402


def test_cycle_collects_reconciles_and_never_claims_publication(tmp_path):
    store_dir, ledger = str(tmp_path / "store"), str(tmp_path / "ledger.json")
    store = LocalDirObjectStore(store_dir)
    art = wind_artifact(n=1)
    ArtifactWriter(store, "wind").write(art)
    run_id = art["lineage"]["executionId"]
    ex = [{"executionId": run_id, "brainId": "wind", "status": "SUCCEEDED", "startedAt": "2026-10-15T02:50:00Z", "endedAt": "2026-10-15T03:10:00Z"},
          {"executionId": "11111111-1111-4111-8111-111111111111", "brainId": "water-temp", "status": "SUCCEEDED", "startedAt": "2026-10-15T02:50:00Z", "endedAt": "2026-10-15T03:10:00Z"},
          {"executionId": "22222222-2222-4222-8222-222222222222", "brainId": "lake-brain", "status": "FAILED", "startedAt": "2026-10-15T02:50:00Z", "endedAt": "2026-10-15T03:10:00Z"}]
    out = PC.run(store_dir, ledger, ex, shadow=True, tasks=[{"id": "T1", "brain": "wind", "title": "measure shoreline wind exposure"}])
    b = out["summary"]["brains"]
    assert b["wind"]["produced"] == 1 and b["wind"]["published"] == 0 and b["wind"]["notRequested"] == 1 and b["wind"]["directWriter"] is True
    assert b["water-temp"]["missingArtifacts"] == 1 and b["lake-brain"]["failed"] == 0 and b["lake-brain"]["notRequested"] == 1
    rec = json.load(open(ledger))["records"]
    wind = next(r for r in rec.values() if r["brainId"] == "wind")
    assert wind["shadow"]["result"] == "SHADOW_READY" and wind["publication"]["outcome"] == "NOT_REQUESTED" and wind["publication"]["reason"] == "DIRECT_WRITER_ACTIVE"
    assert len(out["targetBrains"]) == 9 and "dispatch" in out
    again = PC.run(store_dir, ledger, ex, shadow=True)                       # a second cycle changes nothing
    assert json.load(open(ledger))["records"].keys() == rec.keys() and again["reconcile"]["collected"] == []
