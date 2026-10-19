"""Build the real-geometry test fixture for the Bowfishing Decision layer (research-only; run once, output committed).

  python research/tools/build_decision_fixture.py OUT.json.gz

Selects a SUBSET of the frozen Guntersville fetch table (the app asset read by sector_wind_research.bowfishing_assets):
every bank within RADIUS_M of the audit pair (A = GT-005719, SW-facing South Sauty Creek arm; B = GT-001172, sheltered
minor tributary), plus the 40 banks with the longest SW (225 deg) effective fetch on the lake. Rows are copied verbatim
(no recomputation, no smoothing); the fixture records the source asset and table hashes so a test can prove where it came
from. The output uses the same `banks` + `tableBase64` layout as a runtime fetch object (`state.decode_fetch_table`).
"""
from __future__ import annotations

import base64, gzip, hashlib, json, struct, sys

import numpy as np

from sector_wind import bowfishing as BF
from sector_wind_research.bowfishing_assets import load_lake

PAIR = ("GT-005719", "GT-001172")
RADIUS_M = 2500
LONGEST_SW = 40


def main(out):
    L = load_lake("guntersville")
    banks = L["banks"]; ids = {b["id"]: i for i, b in enumerate(banks)}
    keep = set()
    for pid in PAIR:
        a = banks[ids[pid]]["anchor"]
        keep |= {i for i, b in enumerate(banks) if BF.km(a, b["anchor"]) <= RADIUS_M}
    ok = [i for i, b in enumerate(banks) if not b.get("belowResolution")]
    sw = sorted(ok, key=lambda i: -BF.nine_ray(L["table"][i], 225))[:LONGEST_SW]
    keep |= set(sw)
    sel = sorted(keep)
    raw = (np.round(L["table"][sel] / 10.0)).astype(np.uint16)     # decametres, exactly as stored
    blob = struct.pack(f"<{raw.size}H", *raw.ravel().tolist())
    obj = {"schema": "sector-wind-fetch-subset-v1", "lake": "guntersville", "lakeId": "Guntersville|AL",
           "selection": f"banks within {RADIUS_M} m of {PAIR[0]} or {PAIR[1]} + {LONGEST_SW} longest 225-deg effective-fetch banks",
           "sourceAssetSha256": L["assetSha256"], "sourceTableSha256": L["tableSha256"], "geometry": L["geometry"], "params": L["params"],
           "banks": [banks[i] for i in sel], "tableBase64": base64.b64encode(blob).decode(),
           "tableSha256": hashlib.sha256(blob).hexdigest()}
    with open(out, "wb") as f:
        f.write(gzip.compress(json.dumps(obj, separators=(",", ":")).encode(), mtime=0))
    print(f"{len(sel)} banks ({sum(1 for i in sel if banks[i].get('belowResolution'))} belowResolution) -> {out}")


if __name__ == "__main__":
    main(sys.argv[1])
