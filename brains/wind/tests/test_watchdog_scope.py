"""W-H3 against Wind's REAL write set (2026-11-23): every lake key a sealed Wind artifact touches under lakes|lakeFleet|snapshots/<k>/ (the cycle
watchdog's LAKE_PATH) is on the list tools/ops/wind_watchdog_lakes.py generates. D3's live + national list alone misses the lakeFleet readiness rows
Wind writes for every directory lake, which is why the list is the whole directory. Local only: tmp store, no network."""
import os
import re
import sys
import uuid

import artifact_entry as E
from sector_wind.ingest import verified_release
from test_brain import CFG, DIRECTORY, NOW, make_store

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tools", "ops"))
import wind_watchdog_lakes as WL                                                  # noqa: E402
from sector_brain_platform.cycle_watchdog import LAKE_PATH                         # noqa: E402


def _written_lakes(tmp_path):
    st = make_store(tmp_path / "archive")
    rep, built = E.build(st, CFG, now=NOW, run_summary=None, execution_id=str(uuid.uuid4()), code_version="wind@test",
                         release=verified_release(), directory=DIRECTORY)
    assert rep["ok"], rep.get("errors")
    paths = [m["path"] for s in built.artifact["sections"] for m in s["mutations"]]
    return {m.group(1) for p in paths for m in [LAKE_PATH.match(p)] if m}, st


def test_every_lake_wind_writes_is_on_the_generated_list(tmp_path):
    written, st = _written_lakes(tmp_path)
    assert written and written <= set(WL.lake_list(st.get_json("fetch/national/MANIFEST.json"), DIRECTORY))


def test_d3_alone_would_trip_publish_outside_lakes(tmp_path):
    written, st = _written_lakes(tmp_path)
    outside = written - set(WL.d3_lakes(st.get_json("fetch/national/MANIFEST.json"), DIRECTORY))
    assert outside, "the fixture directory has lakes beyond live + national, and Wind writes lakeFleet readiness for them"
    assert all(re.match(r"^Lake_St_Clair_MI$|^Wilson_Lake_KS$", k) for k in outside)
