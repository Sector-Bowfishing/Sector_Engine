"""WindState: what the wind and water surface are doing on one lake, built ONLY from the Candidate's own archive
(NBM v5.0 cycles, RTMA-RU analyses, METAR) with the frozen Candidate physics. No new science here.

Values are labelled by what they are: `analysis` (RTMA-RU), `forecast` (NBM), `observation` (METAR). A forecast or an
analysis is never presented as an observation. Unknown stays null. No confidence percentages are emitted."""
from __future__ import annotations

import base64
import math
import struct
from datetime import datetime, timedelta, timezone

import numpy as np

from ..interp import CutoutIndex, blend, blend_wind
from ..sample import parse_iso
from .. import bowfishing as BF
from . import contract as C
from . import exposure as EX
from . import tonight as TN

DUR_TOL_DEG, DUR_BAND, DUR_MIN_MS, DUR_MIN_H, DUR_MAX_H = 22.5, (0.7, 1.3), 1.0, 0.5, 12.0


def _circ(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def frozen_duration_h(series: list[tuple[float | None, float | None]]) -> float | None:
    """Mirror of the app's frozen WindDuration.estimate (WindSurfacePhysics.swift). series = [(speed, dirFrom)] hourly,
    oldest first, ending at the valid hour. None when the valid hour has no wind (the app's Unknown-duration branch)."""
    if not series or series[-1][0] is None:
        return None
    s0, d0 = series[-1]; n = 0
    if d0 is not None and s0 >= DUR_MIN_MS:
        for sp, d in reversed(series):
            if sp is None or d is None or sp < DUR_MIN_MS or sp < DUR_BAND[0] * s0 or sp > DUR_BAND[1] * s0 or _circ(d, d0) > DUR_TOL_DEG:
                break
            n += 1
    return min(DUR_MAX_H, max(DUR_MIN_H, float(n)))


def decode_fetch_table(obj: dict) -> tuple[list[dict], np.ndarray]:
    banks = obj["banks"]; raw = base64.b64decode(obj["tableBase64"]); n = len(raw) // 2
    return banks, np.array(struct.unpack(f"<{n}H", raw), dtype=float).reshape(len(banks), BF.NB) * 10.0


def _weights(store, gridkey, lat, lon):
    g = store.get_json(gridkey)
    if not g:
        return None
    return CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"]).weights(lat, lon)


def _point(obj_arrays, wt):
    """(speed, dir, gust) at the point from cut-out arrays; None-safe."""
    sp, dr = blend_wind(obj_arrays["speedMS"], obj_arrays["dirFromDeg"], wt)
    g = blend(obj_arrays["gustMS"], wt) if obj_arrays.get("gustMS") is not None else None
    return sp, dr, g


def newest_nbm(store, wl, now, back_h=6):
    t = now.replace(minute=0, second=0, microsecond=0)
    partial = None
    for b in range(0, back_h + 1):
        c = store.get_json(f"nbm/{wl}/{(t - timedelta(hours=b)):%Y%m%d%H}.json.gz")
        if c and c.get("steps"):
            if c.get("status") == "complete":
                return c
            partial = partial or c
    return partial


def newest_percentile_cycle(store, wl, now, back_h=int(TN.PERCENTILE_MAX_AGE_H)):
    """NBM publishes qmd percentiles only for 00/06/12/18Z inits. Newest such cycle within back_h, else None."""
    t = now.replace(minute=0, second=0, microsecond=0)
    for b in range(0, back_h + 1):
        ti = t - timedelta(hours=b)
        if ti.hour % 6:
            continue
        c = store.get_json(f"nbm/{wl}/{ti:%Y%m%d%H}.json.gz")
        if c and c.get("steps") and c.get("hasPercentiles"):
            return c
    return None


def rtma_series(store, wl, now, hours=13):
    """Newest RTMA-RU quarter-hour within ANALYSIS_MAX_AGE_H, plus the hourly (:00) analyses of the previous 12 h."""
    a0 = now.replace(second=0, microsecond=0); a0 = a0.replace(minute=(a0.minute // 15) * 15)
    newest = None
    for k in range(0, int(C.ANALYSIS_MAX_AGE_H * 4) + 1):
        ts = a0 - timedelta(minutes=15 * k)
        o = store.get_json(f"rtma/{wl}/{ts:%Y%m%d}/{ts:%H%M}.json.gz")
        if o:
            newest = (ts, o); break
    hourly = []
    if newest:
        h0 = newest[0].replace(minute=0)
        for k in range(hours - 1, 0, -1):
            ts = h0 - timedelta(hours=k)
            hourly.append((ts, store.get_json(f"rtma/{wl}/{ts:%Y%m%d}/{ts:%H%M}.json.gz")))
        hourly.append(newest)
    return newest, hourly


def latest_metar(store, stations, lat, lon, now):
    """Latest METAR at the nearest of this lake's frozen stations (observed evidence, not lake-surface truth)."""
    best = None
    days = sorted({now.date(), (now - timedelta(hours=3)).date()}, reverse=True)
    obs = []
    for d in days:
        m = store.get_json(f"metar/{d:%Y%m%d}.json.gz")
        if m:
            obs += m.get("observations", [])
    for sid, s in stations.items():
        dist = BF.km((lat, lon), (s["lat"], s["lon"])) / 1000
        mine = [o for o in obs if o.get("station") == sid and parse_iso(o["validTime"]) <= now]
        if not mine:
            continue
        o = max(mine, key=lambda o: o["validTime"])
        age = (now - parse_iso(o["validTime"])).total_seconds() / 3600
        cand = {"station": sid, "network": s.get("network"), "distanceKm": round(dist, 1), "observedAt": o["validTime"], "ageHours": round(age, 2),
                "sustainedMph": C.mph(o.get("speedMS")), "gustMph": C.mph(o.get("gustMS")), "directionDeg": o.get("dirFromDeg"),
                "averaging": o.get("averaging"), "sensorHeightM": o.get("sensorHeightM"), "stale": age > C.OBSERVATION_MAX_AGE_H}
        if best is None or dist < best["distanceKm"]:
            best = cand
    return best


def surface_summary(u, d, dur_h, banks, table, tier="AUDITED"):
    """Frozen CEM over every resolvable bank for the CURRENT wind. Lake-level physical description only;
    per-bank rows go to storage (never RTDB) for downstream consumers."""
    ok = [i for i, b in enumerate(banks) if not b.get("belowResolution")]
    t_s = dur_h * 3600 if dur_h is not None else None
    rows, chop, surf, labels = [], [], [], []
    for i in ok:
        eff = BF.nine_ray(table[i], d)
        h = BF.cem(u, eff, t_s)
        lo = BF.cem(max(0.0, u - 1.0), eff * 0.7, t_s); hi = BF.cem(u + 1.0, eff * 1.3, t_s)
        c = BF.chop_class(h); p = BF.surface_p(h, u); chop.append(c); surf.append(p)
        lab = EX.label_bank(d, C.mph(u), EX.facing_deg(banks[i]), c)
        labels.append(lab)
        rows.append({"bankId": banks[i]["id"], "effectiveFetchM": round(eff, 1), "hm0In": round(h / 0.0254, 2), "chopClass": c,
                     "surfaceClass": p, "exposureRank": BF.RANK[c], "confidence": "firm" if BF.chop_class(lo) == BF.chop_class(hi) else "boundary",
                     "bankImpact": lab["label"], "highFetch": lab["highFetch"], "windAngleDeg": lab["alphaDeg"], "geometryTier": tier})
    n = len(ok)
    if not n:
        return None, None
    hm = np.array([r["hm0In"] for r in rows])
    pct = lambda arr, k: round(100.0 * sum(1 for x in arr if x == k) / n, 1)
    modal = max(set(surf), key=surf.count)
    summary = {
        "model": f"frozen CEM (EM 1110-2-1100 II-2-36..39) + frozen duration rule (M0) + frozen SPM84/CEM fetch tables; {C.CANDIDATE_MODEL}",
        "validated": False,
        "validationNote": "No field (bank-scale) surface validation exists; buoy physics only (see /validation/wind surfacePhysics).",
        "forcing": "current wind value of this state", "durationH": dur_h,
        "resolvableBanks": n, "unknownBanks": len(banks) - n,
        "chopClassPct": {BF.CHOP[k]: pct(chop, k) for k in BF.CHOP},
        "surfaceClassPct": {BF.CHOP[k]: pct(surf, k) for k in BF.CHOP},
        "textureClass": BF.TEXTURE[BF.texture_class(u)],
        "medianHm0In": round(float(np.median(hm)), 2), "p90Hm0In": round(float(np.percentile(hm, 90)), 2),
        "boundaryBankPct": round(100.0 * sum(r["confidence"] == "boundary" for r in rows) / n, 1),
        "modalSurfaceClass": BF.CHOP[modal],
    }
    exposure = {"protectedPct": pct(chop, 1), "exposedPct": round(100.0 * sum(1 for x in chop if x >= 4) / n, 1),
                "basis": "share of resolvable bank segments with modeled Hm0 < 1 in (protected) and >= 6 in (exposed) for the current wind; "
                         "physical description only, not a fishing recommendation",
                "bankImpact": EX.label_shares(labels) | {"convention": "alpha = angle between wind-FROM bearing and the bank's facing bearing; DIRECT <=45, CROSS <=90, else PROTECTED; modeled, not field-validated"},
                "geometryTier": tier, "estimated": tier != "AUDITED", "validated": False}
    summary["geometryTier"] = tier
    return {"summary": summary, "exposure": exposure}, rows


def tonight_exposure(banks, table, dir_deg, mean_mph, blow_mph, tier="AUDITED", dur_h=BF.STEADY_H):
    """Share of resolvable banks by bank-impact label for tonight's mean speed and for 'if it blows' (P90). Lake-level only."""
    if dir_deg is None or mean_mph is None:
        return None
    out = {"geometryTier": tier, "estimated": tier != "AUDITED", "validated": False, "direction": round(dir_deg), "durationH": dur_h}
    for key, mph in (("atMean", mean_mph), ("ifItBlows", blow_mph)):
        if mph is None:
            out[key] = None
            continue
        u = mph * 0.44704; labels = []
        for i, b in enumerate(banks):
            if b.get("belowResolution"):
                labels.append(EX.label_bank(dir_deg, mph, None, None, True)); continue
            eff = BF.nine_ray(table[i], dir_deg)
            labels.append(EX.label_bank(dir_deg, mph, EX.facing_deg(b), BF.chop_class(BF.cem(u, eff, dur_h * 3600))))
        out[key] = {"speedMph": mph} | EX.label_shares(labels)
    return out


def build_state(store, cfg, wl, lake_id, dir_lake, now, fetch_obj=None, processing_version=None, geometry_tier="AUDITED"):
    """Returns (state, bank_rows | None, meta). Never raises for missing data: unknown stays null with a quality flag."""
    lk = C.lake_key(lake_id); flags: list[str] = []; stale_reasons: list[str] = []
    lat, lon = dir_lake["lat"], dir_lake["lon"]
    stations = {s: v for s, v in cfg["stations"].items() if v.get("lake") == wl}

    cyc = newest_nbm(store, wl, now)
    hourly, fc_now, fc_plus3 = [], None, None
    steps_pt, p90_steps, p90_cyc = [], None, None
    init = None
    if cyc:
        init = parse_iso(cyc["initTime"])
        if cyc.get("status") != "complete":
            flags.append("nbmPartialCycle")
        wt = _weights(store, cyc.get("grid") or f"grids/nbm/{wl}.json", lat, lon)
        if wt is None:
            flags.append("nbmGridMissing")
        else:
            h0 = now.replace(minute=0, second=0, microsecond=0)
            for s in sorted(cyc["steps"], key=lambda s: s["leadHours"]):
                vt = parse_iso(s["validTime"])
                if vt < h0:
                    continue
                sp, dr, g = _point(s, wt)
                if sp is None:
                    continue
                e = {"at": s["validTime"], "mph": C.mph(sp), "gustMph": C.mph(g), "dirDeg": None if dr is None else round(dr), "leadHours": s["leadHours"]}
                steps_pt.append({"at": s["validTime"], "mph": C.mph(sp), "dirDeg": None if dr is None else round(dr), "gustMph": C.mph(g)})
                if vt == h0:
                    fc_now = (sp, dr, g)
                if vt == h0 + timedelta(hours=3):
                    fc_plus3 = sp
                if len(hourly) < C.HOURLY_MAX:
                    hourly.append(e)
            if fc_now is None and hourly and parse_iso(hourly[0]["at"]) == h0 + timedelta(hours=1):
                s1 = next(s for s in cyc["steps"] if s["validTime"] == hourly[0]["at"]); fc_now = _point(s1, wt)
        cycle_age = (now - init).total_seconds() / 3600
        if cycle_age > C.STALE_FORECAST_CYCLE_H:
            stale_reasons.append(f"forecastCycleStale:{cycle_age:.1f}h>{C.STALE_FORECAST_CYCLE_H:g}h")
    else:
        flags.append("noNbmCycle"); stale_reasons.append("noForecastCycle")

    newest, series = rtma_series(store, wl, now)
    analysis = None
    if newest:
        ts, o = newest
        wt_r = _weights(store, o.get("grid") or f"grids/rtma/{wl}.json", lat, lon)
        if wt_r is not None:
            sp, dr, g = _point(o, wt_r)
            analysis = {"product": "RTMA-RU 2.5 km", "analysisTime": o.get("analysisTime"), "retrievedAt": o.get("retrievedAt"),
                        "ageHours": round((now - parse_iso(o["analysisTime"])).total_seconds() / 3600, 2),
                        "sustainedMph": C.mph(sp), "gustMph": C.mph(g), "directionDeg": None if dr is None else round(dr), "_ms": (sp, dr, g)}
    if analysis is None:
        flags.append("noFreshAnalysis")

    if analysis and analysis["_ms"][0] is not None:
        kind, (cur_s, cur_d, cur_g) = "analysis", analysis["_ms"]
        input_age = analysis["ageHours"]
    elif fc_now and fc_now[0] is not None:
        kind, (cur_s, cur_d, cur_g) = "forecast", fc_now
        input_age = round((now - init).total_seconds() / 3600, 2)
    else:
        kind, cur_s, cur_d, cur_g, input_age = "unavailable", None, None, None, None
        stale_reasons.append("noCurrentValue")
    if analysis:
        analysis.pop("_ms", None)

    trend = None
    if cur_s is not None and fc_plus3 is not None:
        delta = C.mph(fc_plus3) - C.mph(cur_s)
        trend = "steady" if abs(delta) < C.TREND_THRESHOLD_MPH else ("rising" if delta > 0 else "easing")

    transitions = []
    if cur_s is not None and hourly:
        prev = C.mph(cur_s)
        for e in hourly:
            for thr in C.TRANSITION_THRESHOLDS_MPH:
                if prev < thr <= e["mph"]:
                    transitions.append({"at": e["at"], "label": f"rises above {thr} mph", "basis": "NBM forecast"})
                elif prev >= thr > e["mph"]:
                    transitions.append({"at": e["at"], "label": f"drops below {thr} mph", "basis": "NBM forecast"})
            prev = e["mph"]
        transitions = transitions[:6]

    observation = latest_metar(store, stations, lat, lon, now)

    # P90 (NBM qmd) from the newest percentile cycle: the breezy-risk flag. Bilinear to the same point.
    p90_cyc = newest_percentile_cycle(store, wl, now)
    p90_init = None
    if p90_cyc:
        wt90 = _weights(store, p90_cyc.get("grid") or f"grids/nbm/{wl}.json", lat, lon)
        if wt90 is not None:
            p90_init = parse_iso(p90_cyc["initTime"])
            p90_steps = []
            for s90 in p90_cyc["steps"]:
                if s90.get("speedP90") is not None:
                    v = blend(s90["speedP90"], wt90)
                    p90_steps.append({"at": s90["validTime"], "p90Mph": C.mph(v)})
    tzname = TN.tz_for(dir_lake.get("state"), lon)
    current_pt = {"kind": kind, "sustainedMph": C.mph(cur_s), "gustMph": C.mph(cur_g),
                  "directionDeg": None if cur_d is None else round(cur_d),
                  "note": "analysis/forecast value, not an observation"} if kind != "unavailable" else None
    tonight = TN.build_tonight(steps_pt, p90_steps, init, p90_init, now, tzname, current_pt)

    surface_state = exposure = None; bank_rows = None; dur_h = None
    surf_dir = cur_d
    if cur_s is not None and cur_d is None and cur_s < 0.5:
        # Calm: direction is undefined, but below 0.5 m/s the frozen CEM gives Hm0 < 1 in at ANY fetch (fully-developed cap),
        # so the surface answer does not depend on direction. Evaluated at bearing 0 and flagged.
        surf_dir = 0.0; flags.append("calmDirectionUndefined")
    if fetch_obj and cur_s is not None and surf_dir is not None:
        ser = []
        for ts, o in series:
            if not o:
                ser.append((None, None)); continue
            wt_r = _weights(store, o.get("grid") or f"grids/rtma/{wl}.json", lat, lon)
            sp, dr, _ = _point(o, wt_r) if wt_r else (None, None, None)
            ser.append((sp, dr))
        dur_h = frozen_duration_h(ser) if kind == "analysis" else None
        banks, table = decode_fetch_table(fetch_obj)
        res, bank_rows = surface_summary(cur_s, surf_dir, dur_h, banks, table, geometry_tier)
        if tonight.get("available") and tonight["direction"]["shown"]:
            tonight["exposure"] = tonight_exposure(banks, table, tonight["direction"]["fromDeg"], tonight["speed"]["meanMph"],
                                                   tonight["speed"]["ifItBlowsMph"], geometry_tier)
        if res:
            surface_state, exposure = res["summary"], res["exposure"]
        flags.append("surfaceModelNotFieldValidated")
    elif not fetch_obj:
        flags.append("fetchTablesUnavailable")
    flags.append("landOnlyAtmosphericValidation")

    stale = bool(stale_reasons)
    readiness = "DEGRADED" if (stale or kind == "unavailable") else "CALIBRATION"
    sources = []
    if cyc:
        sources.append({"sourceType": "nbmForecast", "sourceId": "NOAA:NBM:v5.0", "lastObservationAt": None, "issuedAt": cyc["initTime"],
                        "retrievedAt": cyc.get("retrievedAt"), "modelVersion": cyc.get("modelVersion")})
    if analysis:
        sources.append({"sourceType": "rtmaAnalysis", "sourceId": "NOAA:RTMA-RU:2p5km", "lastObservationAt": analysis["analysisTime"],
                        "retrievedAt": analysis["retrievedAt"]})
    if observation:
        sources.append({"sourceType": "metarObservation", "sourceId": f"METAR:{observation['station']}", "lastObservationAt": observation["observedAt"]})
    state = {
        "stateSchema": C.STATE_SCHEMA, "lakeId": lake_id, "kind": kind,
        "sustainedMph": C.mph(cur_s), "gustMph": C.mph(cur_g),
        "directionDeg": None if cur_d is None else round(cur_d), "directionCardinal": C.cardinal(cur_d),
        "trend": trend, "trendBasis": f"NBM forecast at +3 h vs current value; |Δ| < {C.TREND_THRESHOLD_MPH:g} mph = steady" if trend else None,
        "surfaceCondition": f"{surface_state['modalSurfaceClass']} (modeled, not field-validated)" if surface_state else None,
        "surfaceState": surface_state, "exposure": exposure,
        "hourly": hourly, "transitions": transitions,
        "forecast": {"model": cyc.get("modelVersion") if cyc else None, "initTime": cyc["initTime"] if cyc else None,
                     "retrievedAt": cyc.get("retrievedAt") if cyc else None, "status": cyc.get("status") if cyc else None,
                     "horizonHours": hourly[-1]["leadHours"] if hourly else None, "kind": "forecast"} if cyc else None,
        "forecastGeneratedAt": cyc["initTime"] if cyc else None,
        "analysis": analysis, "observation": observation,
        "observationTime": observation["observedAt"] if observation and not observation["stale"] else None,
        "representativePoint": {"lat": lat, "lon": lon, "basis": "canonical Sector lake directory coordinate"},
        "tonight": tonight,
        "stale": stale, "staleReasons": stale_reasons, "units": {"speed": "mph", "direction": "degrees FROM, true north"},
        "bankDetailRef": f"brain/wind/latest/{lk}.json.gz" if bank_rows else None,
        "provenance": {
            "brainId": C.BRAIN_ID, "brainVersion": C.BRAIN_VERSION, "modelVersion": C.CANDIDATE_MODEL,
            "processingVersion": processing_version, "generatedAt": C.iso(now), "sources": sources,
            "inputAgeHours": input_age, "readiness": readiness, "qualityFlags": flags + stale_reasons,
            "validationRef": f"/lakes/{lk}/validation/{C.BRAIN_ID}",
        },
    }
    meta = {"kind": kind, "stale": stale, "readiness": readiness, "nbmInit": cyc["initTime"] if cyc else None,
            "analysisTime": analysis["analysisTime"] if analysis else None, "observationAt": observation["observedAt"] if observation else None,
            "durationH": dur_h}
    return state, bank_rows, meta
