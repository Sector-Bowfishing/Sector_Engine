"""Research-only access to the app's per-lake fetch-table assets (moved out of the production `sector_wind.bowfishing`
in Repository Phase 2, byte-for-byte the same loader). The production Wind package never reads these assets: the
runtime fetch tables come from the archive (`sector_wind.brain.state.decode_fetch_table`).

ASSETS keeps its pre-migration default (the app checkout on the research Mac); repointing research paths is a separate,
approval-gated decision (see brains/wind/research/README.md). Never imported by brains/wind/runtime.
"""
from __future__ import annotations

import base64, gzip, json, os, struct
import numpy as np

from sector_wind.bowfishing import LAKES, NB

ASSETS = os.path.expanduser("~/Desktop/Development/iOS/sector-wind/Sector/Assets.xcassets/FishIntel/Wind")


def load_lake(lake):
    p = os.path.join(ASSETS, f"{LAKES[lake]}WindFetch.dataset/{lake}.windfetch.json.gz")
    raw = open(p, "rb").read(); d = json.loads(gzip.decompress(raw))
    banks = d["banks"]
    t = base64.b64decode(d["tableBase64"]); n = len(t) // 2
    table = np.array(struct.unpack(f"<{n}H", t), dtype=float).reshape(len(banks), NB) * 10.0
    return {"lake": lake, "banks": banks, "table": table, "tableSha256": d.get("tableSha256"), "assetSha256": __import__("hashlib").sha256(raw).hexdigest(),
            "geometry": d.get("geometry"), "params": d.get("params")}
