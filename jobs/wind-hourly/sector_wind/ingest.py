"""Ingest NBM (forecast), RTMA-RU (analysis) and METAR (observed) into the wind archive.

Archive layout (schema sector-wind-cycle-v1), all under the store root:
  grids/<product>/<lake>.json                  cut-out cells: full-grid index, lat, lon, nx, spacing
  nbm/<lake>/<YYYYMMDDHH>.json.gz               one NBM cycle: init, per-lead steps, qmd percentiles
  rtma/<lake>/<YYYYMMDD>/<HHMM>.json.gz          one RTMA-RU analysis
  metar/<YYYYMMDD>.json.gz                       station observations for the day
  ledger/ingest.jsonl                            every attempt, success or failure

Every forecast step keeps initTime, validTime, leadHours and retrievedAt, so true lead-time
skill can be computed later from forecasts that actually existed at the time."""
from __future__ import annotations

import io
import csv
import json
import os
from datetime import datetime, timedelta, timezone

import numpy as np

from . import DECODER_VERSION, SCHEMA
from .grib import FetchError, DecodeError, cells_in_bbox, decode, fetch, find, grid, read_idx, row_scramble_ratio
from .sample import iso

NBM_CORE = "https://noaa-nbm-grib2-pds.s3.amazonaws.com/blend.{d}/{h:02d}/core/blend.t{h:02d}z.core.f{f:03d}.co.grib2"
NBM_QMD = "https://noaa-nbm-grib2-pds.s3.amazonaws.com/blend.{d}/{h:02d}/qmd/blend.t{h:02d}z.qmd.f{f:03d}.co.grib2"
RTMA_RU = "https://noaa-rtma-pds.s3.amazonaws.com/rtma2p5_ru.{d}/rtma2p5_ru.t{hm}z.2dvaranl_ndfd.grb2"
# Version by cycle init (NOAA/MDL): v4.3 operational 2025-05-27 12Z; v5.0 operational 2026-05-05 (SCN 26-24: from the
# 13Z run), wind speed and gust re-calibrated in v5.0; v5.0 bug fix 2026-06-18; v5.0.14 2026-07-28 (temperature only).
NBM_V50_START = datetime(2026, 5, 5, 13, tzinfo=timezone.utc)


def nbm_version(init: datetime) -> str:
    if init >= NBM_V50_START:
        return "NBM v5.0"
    if init >= datetime(2026, 5, 5, tzinfo=timezone.utc):
        return "NBM v4.3 (transition day 2026-05-05, before the 13Z v5.0 start)"
    if init >= datetime(2025, 5, 27, 12, tzinfo=timezone.utc):
        return "NBM v4.3"
    return "NBM pre-v4.3"


NBM_VERSION = "NBM v5.0"   # current operational generation (kept for callers that need the live label)
LEVEL = "10 m above ground"
DEFAULT_LEADS = list(range(1, 25)) + list(range(27, 49, 3))


def load_config(path: str | None = None) -> dict:
    path = path or os.path.join(os.path.dirname(os.path.dirname(__file__)), "lakes.json")
    return json.load(open(path))


def _now():
    return datetime.now(timezone.utc)


def _round(a, nd):
    return [None if (v is None or np.isnan(v)) else round(float(v), nd) for v in a]


def _ensure_grid_manifest(store, product: str, lake: str, bbox, grid_key: str, spacing_km: float):
    key = f"grids/{product}/{lake}.json"
    existing = store.get_json(key)
    if existing and existing["gridKey"] == grid_key:
        return np.asarray(existing["cells"])
    cells = cells_in_bbox(grid_key, tuple(bbox))
    lat, lon = grid(grid_key)
    nx = int(grid_key.split(":")[1].split("x")[0])
    store.put_json(key, {"schema": SCHEMA, "product": product, "lake": lake, "gridKey": grid_key, "nx": nx,
                         "spacingKm": spacing_km, "cells": cells.tolist(),
                         "lat": _round(lat[cells], 5), "lon": _round(lon[cells], 5)})
    return cells


def _field(url, entries, var, tail="", step=None):
    e = find(entries, var, LEVEL, tail, step)
    if e is None:
        raise DecodeError(f"{var} {tail or 'deterministic'} not in {url}.idx")
    return decode(fetch(url, (e.start, e.end)))


def ingest_nbm_cycle(store, cfg: dict, init: datetime, leads=DEFAULT_LEADS, with_qmd: bool = True) -> dict:
    """Pull one NBM cycle, write one archive object per lake. Returns a summary."""
    retrieved = _now()
    lakes = cfg["lakes"]
    per_lake = {k: [] for k in lakes}
    missing = []
    for f in leads:
        url = NBM_CORE.format(d=f"{init:%Y%m%d}", h=init.hour, f=f)
        try:
            ent = read_idx(url)
            step = f"{f} hour fcst"
            spd = _field(url, ent, "WIND", "", step); dr = _field(url, ent, "WDIR", "", step); gs = _field(url, ent, "GUST", "", step)
        except (FetchError, DecodeError) as e:
            missing.append({"lead": f, "error": str(e)[:200]}); continue
        nx = int(spd.grid_key.split(":")[1].split("x")[0])
        any_cells = cells_in_bbox(spd.grid_key, tuple(next(iter(lakes.values()))["bbox"]))
        ratio = row_scramble_ratio(spd.values, any_cells, nx)
        if not (ratio < 3.0):   # decoder failure: never publish a cycle that may be mislocated
            missing.append({"lead": f, "error": f"decoder self-check failed (row/col ratio {ratio:.2f})"}); continue
        q = {}
        # NBM publishes qmd (percentiles) only for the 00/06/12/18Z cycles. Other cycles carry no
        # percentiles; consumers take them from the newest synoptic cycle (labelled) or fall back
        # to the pre-registered +/-1.0 m/s.
        if with_qmd and init.hour % 6 == 0:
            qurl = NBM_QMD.format(d=f"{init:%Y%m%d}", h=init.hour, f=f)
            try:
                qe = read_idx(qurl)
                for name, var, tail in [("speedP10", "WIND", "10% level"), ("speedP50", "WIND", "50% level"),
                                        ("speedP90", "WIND", "90% level"), ("gustP90", "GUST", "90% level")]:
                    q[name] = _field(qurl, qe, var, tail, step)
            except (FetchError, DecodeError) as e:
                q = {}; missing.append({"lead": f, "qmd": str(e)[:200]})
        for lake, lc in lakes.items():
            cells = _ensure_grid_manifest(store, "nbm", lake, lc["bbox"], spd.grid_key, 2.5)
            d = dr.values[cells].copy(); s = spd.values[cells]
            d[s < 0.5] = np.nan  # calm: no direction
            stepobj = {"leadHours": f, "validTime": iso(init + timedelta(hours=f)),
                       "speedMS": _round(np.where(spd.missing[cells], np.nan, s), 2),
                       "dirFromDeg": _round(np.where(dr.missing[cells], np.nan, d), 0),
                       "gustMS": _round(np.where(gs.missing[cells], np.nan, gs.values[cells]), 2)}
            for name, fld in q.items():
                stepobj[name] = _round(np.where(fld.missing[cells], np.nan, fld.values[cells]), 2)
            per_lake[lake].append(stepobj)
    out = {}
    for lake, steps in per_lake.items():
        status = "complete" if steps and not any("error" in m for m in missing) else ("partial" if steps else "failed")
        obj = {"schema": SCHEMA, "kind": "forecast", "model": "NBM", "modelVersion": nbm_version(init),
               "hasPercentiles": bool(steps) and "speedP10" in steps[0],
               "lake": lake, "initTime": iso(init), "retrievedAt": iso(retrieved), "decoderVersion": DECODER_VERSION,
               "source": {"bucket": "noaa-nbm-grib2-pds", "core": NBM_CORE.format(d=f"{init:%Y%m%d}", h=init.hour, f=0).rsplit("/", 1)[0]},
               "grid": f"grids/nbm/{lake}.json", "status": status, "missing": missing, "steps": steps}
        if steps:
            store.put_json(f"nbm/{lake}/{init:%Y%m%d%H}.json.gz", obj)
        store.append_ledger({"product": "NBM", "cycle": iso(init), "lake": lake, "status": status,
                             "leads": len(steps), "missing": len(missing)})
        out[lake] = status
    return out


def ingest_rtma(store, cfg: dict, when: datetime) -> dict:
    """One RTMA-RU analysis (15-minute cadence). Typed `analysis`, never `observed`."""
    retrieved = _now()
    url = RTMA_RU.format(d=f"{when:%Y%m%d}", hm=f"{when:%H%M}")
    out = {}
    try:
        ent = read_idx(url)
        spd = _field(url, ent, "WIND"); dr = _field(url, ent, "WDIR"); gs = _field(url, ent, "GUST")
        nx = int(spd.grid_key.split(":")[1].split("x")[0])
        ratio = row_scramble_ratio(spd.values, cells_in_bbox(spd.grid_key, tuple(next(iter(cfg["lakes"].values()))["bbox"])), nx)
        if not (ratio < 3.0):
            raise DecodeError(f"decoder self-check failed (row/col ratio {ratio:.2f})")
    except (FetchError, DecodeError) as e:
        for lake in cfg["lakes"]:
            store.append_ledger({"product": "RTMA-RU", "cycle": iso(when), "lake": lake, "status": "failed", "error": str(e)[:200]})
        return {lake: "failed" for lake in cfg["lakes"]}
    for lake, lc in cfg["lakes"].items():
        cells = _ensure_grid_manifest(store, "rtma", lake, lc["bbox"], spd.grid_key, 2.5)
        d = dr.values[cells].copy(); s = spd.values[cells]; d[s < 0.5] = np.nan
        obj = {"schema": SCHEMA, "kind": "analysis", "product": "RTMA-RU", "lake": lake, "analysisTime": iso(when),
               "retrievedAt": iso(retrieved), "decoderVersion": DECODER_VERSION, "source": {"bucket": "noaa-rtma-pds", "key": url.split(".com/")[1]},
               "grid": f"grids/rtma/{lake}.json", "status": "complete",
               "speedMS": _round(np.where(spd.missing[cells], np.nan, s), 2), "dirFromDeg": _round(np.where(dr.missing[cells], np.nan, d), 0),
               "gustMS": _round(np.where(gs.missing[cells], np.nan, gs.values[cells]), 2)}
        store.put_json(f"rtma/{lake}/{when:%Y%m%d}/{when:%H%M}.json.gz", obj)
        store.append_ledger({"product": "RTMA-RU", "cycle": iso(when), "lake": lake, "status": "complete"})
        out[lake] = "complete"
    return out


IEM = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"


def ingest_metar_day(store, cfg: dict, day: datetime) -> int:
    """All configured stations for one UTC day. sknt/gust knots -> m/s; calm -> no direction;
    no gust group -> gust None (censored, not zero)."""
    import urllib.parse
    d2 = day + timedelta(days=1)
    q = [("data", "sknt"), ("data", "drct"), ("data", "gust"), ("tz", "Etc/UTC"), ("format", "onlycomma"),
         ("latlon", "no"), ("missing", "M"), ("trace", "T"), ("direct", "no"), ("report_type", "3"), ("report_type", "4"),
         ("year1", day.year), ("month1", day.month), ("day1", day.day), ("year2", d2.year), ("month2", d2.month), ("day2", d2.day)]
    q += [("station", s) for s in cfg["stations"]]
    txt = fetch(IEM + "?" + urllib.parse.urlencode(q), timeout=300).decode()
    KT = 0.514444
    rows = []
    for r in csv.DictReader(io.StringIO(txt)):
        if r["sknt"] in ("M", ""):
            continue
        st = cfg["stations"][r["station"]]
        sk = float(r["sknt"])
        rows.append({"station": r["station"], "network": st["network"], "sensorHeightM": st["sensorHeightM"], "averaging": "2-min",
                     "validTime": r["valid"].replace(" ", "T") + ":00Z", "speedMS": round(sk * KT, 2),
                     "dirFromDeg": None if sk == 0 or r["drct"] in ("M", "") else float(r["drct"]) % 360,
                     "gustMS": None if r["gust"] in ("M", "") else round(float(r["gust"]) * KT, 2)})
    store.put_json(f"metar/{day:%Y%m%d}.json.gz", {"schema": SCHEMA, "kind": "observed", "day": f"{day:%Y-%m-%d}",
                                                   "retrievedAt": iso(_now()), "source": IEM, "observations": rows})
    store.append_ledger({"product": "METAR", "cycle": f"{day:%Y-%m-%d}", "lake": "*", "status": "complete", "n": len(rows)})
    return len(rows)


def latest_nbm_cycle(now: datetime | None = None, max_back_h: int = 4) -> datetime | None:
    """Newest cycle whose f001 .co file and index exist."""
    now = now or _now()
    t = now.replace(minute=0, second=0, microsecond=0)
    for back in range(0, max_back_h + 1):
        c = t - timedelta(hours=back)
        try:
            fetch(NBM_CORE.format(d=f"{c:%Y%m%d}", h=c.hour, f=1) + ".idx")
            return c
        except FetchError:
            continue
    return None
