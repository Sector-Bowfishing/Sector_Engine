"""The live hourly run (Stage 3 shadow): newest NBM cycle plus catch-up of any missed cycle in the
last few hours, RTMA-RU quarter-hours with catch-up, METAR refresh, a per-lake `latest` bundle for
the master inspector, and a run summary. Nothing here is read by production."""
from __future__ import annotations

import time
import traceback
from datetime import datetime, timedelta, timezone

from . import DECODER_VERSION, SCHEMA
from .ingest import (DEFAULT_LEADS, ingest_metar_day, ingest_nbm_cycle, ingest_rtma, latest_nbm_cycle)
from .sample import iso

NBM_CATCHUP_H = 4
RTMA_CATCHUP_H = 3
BUNDLE_NBM_CYCLES = 3
BUNDLE_RTMA_HOURS = 13


def _nbm_key(lake, t):
    return f"nbm/{lake}/{t:%Y%m%d%H}.json.gz"


def _rtma_key(lake, t):
    return f"rtma/{lake}/{t:%Y%m%d}/{t:%H%M}.json.gz"


def _complete(store, key) -> bool:
    """Archived AND complete. Long leads post later than f001, so a cycle first archived at :05 can
    be partial; catch-up finishes it on a later run."""
    if not store.exists(key):
        return False
    o = store.get_json(key)
    return bool(o) and o.get("status") == "complete"


def run_hourly(store, cfg: dict, now: datetime | None = None, leads=DEFAULT_LEADS) -> dict:
    now = now or datetime.now(timezone.utc)
    t0 = time.time()
    lakes = list(cfg["lakes"])
    summary = {"schema": SCHEMA, "runAt": iso(now), "decoderVersion": DECODER_VERSION, "nbm": {}, "rtma": {}, "metar": {}, "errors": []}
    # NBM: newest published cycle, plus any of the previous hours not yet archived for every lake.
    newest = latest_nbm_cycle(now)
    summary["newestNbmCycle"] = iso(newest) if newest else None
    if newest:
        for back in range(0, NBM_CATCHUP_H + 1):
            c = newest - timedelta(hours=back)
            if back and all(_complete(store, _nbm_key(l, c)) for l in lakes):
                continue
            try:
                summary["nbm"][iso(c)] = ingest_nbm_cycle(store, cfg, c, leads, True)
            except Exception as e:
                summary["errors"].append(f"NBM {iso(c)}: {e!r}")
    else:
        summary["errors"].append("no NBM cycle published in the last 4 h")
    # RTMA-RU: every quarter-hour of the last few hours that is published and missing.
    q = (now - timedelta(minutes=20)).replace(second=0, microsecond=0)
    q = q.replace(minute=(q.minute // 15) * 15)
    for k in range(0, RTMA_CATCHUP_H * 4):
        t = q - timedelta(minutes=15 * k)
        if all(store.exists(_rtma_key(l, t)) for l in lakes):
            continue
        try:
            summary["rtma"][iso(t)] = ingest_rtma(store, cfg, t)
        except Exception as e:
            summary["errors"].append(f"RTMA {iso(t)}: {e!r}")
    # METAR: today and (early in the UTC day) yesterday, refreshed every run.
    for d in sorted({now.date(), (now - timedelta(hours=3)).date()}):
        try:
            summary["metar"][str(d)] = ingest_metar_day(store, cfg, datetime(d.year, d.month, d.day, tzinfo=timezone.utc))
        except Exception as e:
            summary["errors"].append(f"METAR {d}: {e!r}")
    # Latest bundles for the master inspector.
    for lake in lakes:
        try:
            summary.setdefault("bundles", {})[lake] = write_latest_bundle(store, lake, now)
        except Exception as e:
            summary["errors"].append(f"bundle {lake}: {e!r}\n{traceback.format_exc()[-400:]}")
    summary["seconds"] = round(time.time() - t0, 1)
    store.put_json(f"runs/{now:%Y%m%d}/{now:%H%M%S}.json", summary)
    return summary


def write_latest_bundle(store, lake: str, now: datetime) -> dict:
    """latest/<lake>.json.gz in the iOS WindSnapshot schema: grids, the newest NBM cycles and the last
    13 h of RTMA-RU. The app evaluates it AS OF the real current time, so freshness and publication
    latency rules apply exactly as in replay."""
    cycles = []
    t = now.replace(minute=0, second=0, microsecond=0)
    for back in range(0, 8):
        c = store.get_json(_nbm_key(lake, t - timedelta(hours=back)))
        if c:
            for k in ("source", "missing", "grid", "hasPercentiles"):
                c.pop(k, None)
            cycles.append(c)
        if len(cycles) >= BUNDLE_NBM_CYCLES:
            break
    analyses = []
    a0 = now.replace(second=0, microsecond=0); a0 = a0.replace(minute=(a0.minute // 15) * 15)
    for k in range(0, BUNDLE_RTMA_HOURS * 4):
        ts = a0 - timedelta(minutes=15 * k)
        if k >= 12 and ts.minute != 0:    # quarter-hours for the last 3 h, hourly before that
            continue
        x = store.get_json(_rtma_key(lake, ts))
        if x:
            for key in ("source", "grid", "status"):
                x.pop(key, None)
            analyses.append(x)
    analyses.reverse(); cycles.reverse()
    nbm = store.get_json(f"grids/nbm/{lake}.json"); rtma = store.get_json(f"grids/rtma/{lake}.json")
    if not nbm or not cycles:
        raise RuntimeError("no NBM grid or cycles yet")
    for g in (nbm, rtma):
        if g:
            g.pop("schema", None)
    bundle = {"schema": "sector-wind-snapshot-v1", "lake": lake,
              "replayStart": cycles[0]["initTime"], "replayEnd": iso(now),
              "source": f"wind-hourly live shadow archive, built {iso(now)}",
              "nbmGrid": nbm, "rtmaGrid": rtma, "cycles": cycles, "analyses": analyses}
    n = store.put_json(f"latest/{lake}.json.gz", bundle)
    return {"cycles": len(cycles), "analyses": len(analyses), "bytes": n}
