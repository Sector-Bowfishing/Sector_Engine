"""Risky-night flag shadow: NBM v5.0 probability fields at the W1 points (Sector_Ops #27, owner approval 2026-11-14, comment 6882501008).

The rule (frozen in W-NOW-2/W-NOW-3, p* = 0.15 not re-tuned): where deterministic NBM 10 m wind is under 15 mph and NBM's own
probability of 15 mph or more (pW15) is 0.15 or more, wind confidence would be lowered. The flag only ever lowers confidence.

This module only RECORDS what the rule would say, per point and lead, from the qmd probability fields. It has no customer output,
publishes nothing and changes no score. Off unless WIND_PW15_SHADOW=1. NBM publishes qmd only for the 00/06/12/18Z cycles.

Archive layout (same store as ingest.py, separate keys):
  pw15-shadow/<YYYYMMDDHH>.json.gz   one synoptic cycle: per point, per lead, deterministic speed, pW15 and the would-flag bit
Scoring against METAR is done later, offline, from this archive."""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np

from . import DECODER_VERSION
from .grib import DecodeError, FetchError, cells_in_bbox, decode, fetch, find, read_idx, row_scramble_ratio
from .ingest import LEVEL, NBM_CORE, NBM_QMD, _field, _now, nbm_version
from .points import _ensure_cells
from .sample import iso

SCHEMA_PW15 = "sector-wind-pw15-shadow-v1"
ENV_FLAG = "WIND_PW15_SHADOW"
MPH = 0.44704
T15 = 15 * MPH          # m/s
P_STAR = 0.15           # frozen; never tuned here
LEADS = (1, 3, 6, 12, 18)   # the leads W-NOW-3 pre-registered


def enabled(env=None) -> bool:
    import os
    return (env if env is not None else os.environ).get(ENV_FLAG) == "1"


def exceed(points, T):
    """P(X > T) from CDF points [(x, F)], monotone after sorting; linear in x; anchored at (0, 0). Identical to forcing_eval.exceed (W-NOW-1..3)."""
    pts = sorted([(0.0, 0.0)] + [(x, f) for x, f in points if x is not None and f is not None and np.isfinite(x) and np.isfinite(f)])
    xs, fs = [p[0] for p in pts], list(np.maximum.accumulate([min(1.0, max(0.0, p[1])) for p in pts]))
    if T >= xs[-1]:
        return max(0.0, 1.0 - fs[-1]) if T == xs[-1] else max(0.0, (1.0 - fs[-1]) * 0.5)
    return float(1.0 - np.interp(T, xs, fs))


def local_night(valid: datetime, lon: float) -> bool:
    """Local-standard night 19:00-02:59, as the pre-registration: local hour = (UTC hour + round(lon/15)) mod 24."""
    lh = (valid.hour + round(lon / 15)) % 24
    return lh >= 19 or lh <= 2


def _qmd_fields(qurl: str, f: int):
    """The four qmd exceedance fields (thresholds sorted ascending) and the 50/75/90% levels for WIND at lead f."""
    qe = read_idx(qurl)
    step = f"{f} hour fcst"
    pr = sorted([(float(x.tail[6:].split(":")[0]), x) for x in qe
                 if x.var == "WIND" and x.level == LEVEL and step in x.step and x.tail.startswith("prob >")], key=lambda z: z[0])
    if len(pr) < 4:
        raise DecodeError("qmd prob thresholds missing")
    probs = [(thr, decode(fetch(qurl, (e.start, e.end)))) for thr, e in pr[:4]]
    lv = {}
    for l in (50, 75, 90):
        e = find(qe, "WIND", LEVEL, f"{l}% level", step)
        if e is None:
            raise DecodeError(f"{l}% level missing")
        lv[l] = decode(fetch(qurl, (e.start, e.end)))
    return probs, lv


def ingest_pw15_shadow(store, pcfg: dict, init: datetime, leads=LEADS) -> dict:
    """Record the would-flag for one synoptic NBM cycle at every point. No customer output."""
    if init.hour % 6 != 0:
        return {"status": "skipped", "reason": "qmd probability fields exist only for the 00/06/12/18Z cycles"}
    retrieved = _now()
    pts = pcfg["points"]
    per_point: dict[str, list] = {k: [] for k in pts}
    missing, cells = [], None
    for f in leads:
        url = NBM_CORE.format(d=f"{init:%Y%m%d}", h=init.hour, f=f)
        qurl = NBM_QMD.format(d=f"{init:%Y%m%d}", h=init.hour, f=f)
        try:
            spd = _field(url, read_idx(url), "WIND", "", f"{f} hour fcst")
            probs, lv = _qmd_fields(qurl, f)
        except (FetchError, DecodeError) as e:
            missing.append({"lead": f, "error": str(e)[:200]}); continue
        cells = cells if cells is not None else _ensure_cells(store, spd.grid_key, pts)
        nx = int(spd.grid_key.split(":")[1].split("x")[0])
        # Decoder self-check on a CONTIGUOUS patch around the first point: the ratio needs neighbouring cells, so the sparse
        # point cells alone give NaN (fails closed). Same patch rule as the W-NOW-3 fetch.
        p0 = pts[next(iter(pts))]
        patch = cells_in_bbox(spd.grid_key, (p0["lon"] - 0.5, p0["lat"] - 0.5, p0["lon"] + 0.5, p0["lat"] + 0.5))
        if not (row_scramble_ratio(spd.values, patch, nx) < 3.0):
            missing.append({"lead": f, "error": "decoder self-check failed"}); continue
        valid = init + timedelta(hours=f)
        for k, c in cells.items():
            if c is None or spd.missing[c] or any(fl.missing[c] for _, fl in probs) or any(fl.missing[c] for fl in lv.values()):
                continue
            curve = [(thr, 1 - float(fl.values[c]) / 100) for thr, fl in probs] + [(float(lv[l].values[c]), l / 100) for l in (50, 75, 90)]
            p15 = exceed(curve, T15)
            s = float(spd.values[c])
            per_point[k].append({"leadHours": f, "validTime": iso(valid), "nbmMS": round(s, 2), "pW15": round(p15, 4),
                                 "night": local_night(valid, pts[k]["lon"]), "nbmUnder15": bool(s < T15),
                                 "wouldFlag": bool(s < T15 and p15 >= P_STAR)})
    status = "complete" if cells is not None and not missing else ("partial" if cells is not None else "failed")
    obj = {"schema": SCHEMA_PW15, "kind": "shadow", "model": "NBM", "modelVersion": nbm_version(init),
           "rule": {"nbmUnderMph": 15, "pStar": P_STAR, "exceedMph": 15, "frozenIn": "W-NOW-2/W-NOW-3", "effect": "lowers wind confidence only"},
           "scope": "shadow record only: no customer output, no score, no publication",
           "pointsVersion": pcfg.get("version"), "initTime": iso(init), "retrievedAt": iso(retrieved),
           "decoderVersion": DECODER_VERSION, "status": status, "missing": missing,
           "points": {k: v for k, v in per_point.items() if v}}
    if obj["points"]:
        store.put_json(f"pw15-shadow/{init:%Y%m%d%H}.json.gz", obj)
    store.append_ledger({"product": "PW15-SHADOW", "cycle": iso(init), "status": status, "points": len(obj["points"]), "missing": len(missing)})
    return {"status": status, "points": len(obj["points"]),
            "flagged": sum(1 for v in obj["points"].values() for r in v if r["wouldFlag"] and r["night"])}
