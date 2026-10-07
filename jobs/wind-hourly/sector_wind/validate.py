"""Forecast/analysis skill from Sector's OWN archive (pre-registration §4).

Only forecasts that existed at the time are scored: each archived NBM cycle keeps its init
time, and a step is scored at its own lead. Stitched analyses are never used as forecasts."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np

from .interp import CutoutIndex, blend, blend_wind
from .sample import circular_error, parse_iso

MPH = 0.44704
KT = 0.514444


def load_obs(store, start: datetime, end: datetime) -> dict:
    """{(station, hour): obs} using the report within 10 min of the top of the hour (nearest)."""
    best = {}
    d = start
    while d <= end:
        day = store.get_json(f"metar/{d:%Y%m%d}.json.gz")
        for o in (day or {}).get("observations", []):
            t = parse_iso(o["validTime"])
            hour = (t + timedelta(minutes=30)).replace(minute=0, second=0)
            dt = abs((t - hour).total_seconds())
            if dt > 600:
                continue
            k = (o["station"], hour)
            if k not in best or dt < best[k][0]:
                best[k] = (dt, o)
        d += timedelta(days=1)
    return {k: v[1] for k, v in best.items()}


def _night(t: datetime) -> bool:
    return 1 <= t.hour <= 8


def _metrics(pairs: list[tuple]) -> dict:
    """pairs: (fspd, fdir, fgust, ospd, odir, ogust)."""
    if not pairs:
        return {"n": 0}
    f = np.array([p[0] for p in pairs]); o = np.array([p[3] for p in pairs]); e = f - o
    out = {"n": len(pairs), "bias": float(e.mean()), "mae": float(np.abs(e).mean()), "rmse": float(np.sqrt((e ** 2).mean()))}
    for name, thr in (("10mph", 10 * MPH), ("15mph", 15 * MPH)):
        ob, fb = o >= thr, f >= thr
        out[f"pod_{name}"] = float((ob & fb).sum() / ob.sum()) if ob.sum() else None
        out[f"far_{name}"] = float((fb & ~ob).sum() / fb.sum()) if fb.sum() else None
        out[f"n_obs_{name}"] = int(ob.sum())
    de = [circular_error(p[1], p[4]) for p in pairs if p[1] is not None and p[4] is not None and p[0] >= 2.6 and p[3] >= 2.6]
    if de:
        de = np.array(de)
        out.update({"dir_n": len(de), "dir_mean": float(de.mean()), "dir_median": float(np.median(de)),
                    "dir_within22_5": float((de <= 22.5).mean()), "dir_within45": float((de <= 45).mean())})
    g = [(p[2], p[5]) for p in pairs if p[2] is not None and p[5] is not None]
    if g:
        g = np.array(g); out.update({"gust_n": len(g), "gust_bias_conditional": float((g[:, 0] - g[:, 1]).mean()),
                                     "gust_mae_conditional": float(np.abs(g[:, 0] - g[:, 1]).mean())})
    ob = np.array([(p[5] or 0) >= 20 * KT for p in pairs]); fb = np.array([(p[2] or 0) >= 20 * KT for p in pairs])
    out["gust20_pod"] = float((ob & fb).sum() / ob.sum()) if ob.sum() else None
    out["gust20_far"] = float((fb & ~ob).sum() / fb.sum()) if fb.sum() else None
    return out


def skill(store, cfg: dict, start: datetime, end: datetime, leads=(1, 3, 6, 12)) -> dict:
    obs = load_obs(store, start - timedelta(days=1), end + timedelta(days=1))
    by_lead = defaultdict(list); by_lead_night = defaultdict(list); by_station_night = defaultdict(list)
    idx_cache = {}
    stations_by_lake = defaultdict(list)
    for sid, st in cfg["stations"].items():
        stations_by_lake[st["lake"]].append(sid)
    t = start.replace(minute=0, second=0, microsecond=0)
    while t <= end:
        for lake in cfg["lakes"]:
            cyc = store.get_json(f"nbm/{lake}/{t:%Y%m%d%H}.json.gz")
            if not cyc:
                continue
            if lake not in idx_cache:
                g = store.get_json(cyc["grid"])
                ci = CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"])
                idx_cache[lake] = {sid: ci.weights(cfg["stations"][sid]["lat"], cfg["stations"][sid]["lon"]) for sid in stations_by_lake[lake]}
            for step in cyc["steps"]:
                if step["leadHours"] not in leads:
                    continue
                vt = parse_iso(step["validTime"])
                for sid, wt in idx_cache[lake].items():
                    o = obs.get((sid, vt))
                    if not o:
                        continue
                    fs, fd = blend_wind(step["speedMS"], step["dirFromDeg"], wt)
                    if fs is None:
                        continue
                    fg = blend(step["gustMS"], wt)
                    rec = (fs, fd, fg, o["speedMS"], o["dirFromDeg"], o["gustMS"])
                    by_lead[step["leadHours"]].append(rec)
                    if _night(vt):
                        by_lead_night[step["leadHours"]].append(rec)
                        by_station_night[(sid, step["leadHours"])].append(rec)
        t += timedelta(hours=1)
    # persistence: obs at valid-lead, night only
    pers = {}
    for lead in leads:
        pr = []
        for (sid, h), o in obs.items():
            if not (start <= h <= end and _night(h)):
                continue
            p = obs.get((sid, h - timedelta(hours=lead)))
            if p:
                pr.append((p["speedMS"], p["dirFromDeg"], p["gustMS"], o["speedMS"], o["dirFromDeg"], o["gustMS"]))
        pers[lead] = _metrics(pr)
    return {"window": [start.isoformat(), end.isoformat()],
            "allHours": {l: _metrics(v) for l, v in sorted(by_lead.items())},
            "night": {l: _metrics(v) for l, v in sorted(by_lead_night.items())},
            "nightByStation": {f"{s}|+{l}h": _metrics(v) for (s, l), v in sorted(by_station_night.items())},
            "persistenceNight": pers}


def rtma_skill(store, cfg: dict, start: datetime, end: datetime) -> dict:
    """RTMA-RU analysis (typed analysis) vs METAR at the top of each hour."""
    obs = load_obs(store, start - timedelta(days=1), end + timedelta(days=1))
    pairs, night = [], []
    idx_cache = {}
    t = start
    while t <= end:
        for lake in cfg["lakes"]:
            a = store.get_json(f"rtma/{lake}/{t:%Y%m%d}/{t:%H%M}.json.gz")
            if not a:
                continue
            if lake not in idx_cache:
                g = store.get_json(a["grid"]); ci = CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"])
                idx_cache[lake] = {sid: ci.weights(st["lat"], st["lon"]) for sid, st in cfg["stations"].items() if st["lake"] == lake}
            for sid, wt in idx_cache[lake].items():
                o = obs.get((sid, t))
                if not o:
                    continue
                fs, fd = blend_wind(a["speedMS"], a["dirFromDeg"], wt)
                if fs is None:
                    continue
                rec = (fs, fd, blend(a["gustMS"], wt), o["speedMS"], o["dirFromDeg"], o["gustMS"])
                pairs.append(rec)
                if _night(t):
                    night.append(rec)
        t += timedelta(hours=1)
    return {"allHours": _metrics(pairs), "night": _metrics(night),
            "caveat": "RTMA assimilates these same METARs: this is consistency, not independent skill."}


def archive_success(store, product: str, start: datetime, end: datetime, step_minutes: int, lakes: list[str]) -> dict:
    """Share of expected cycles present in the archive, per lake (rubric dimension 8)."""
    res = {}
    for lake in lakes:
        exp = got = 0
        t = start
        while t <= end:
            exp += 1
            key = f"nbm/{lake}/{t:%Y%m%d%H}.json.gz" if product == "NBM" else f"rtma/{lake}/{t:%Y%m%d}/{t:%H%M}.json.gz"
            got += store.exists(key)
            t += timedelta(minutes=step_minutes)
        res[lake] = {"expected": exp, "archived": got, "share": got / exp if exp else None}
    return res
