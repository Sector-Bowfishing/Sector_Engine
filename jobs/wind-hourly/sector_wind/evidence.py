"""Wind evidence dashboard (Stage 3A Track A). Read-only over the archive (local mirror or GCS).

  python -m sector_wind.evidence status   --store local:$MIRROR [--start 2026-10-08] [--end ...] [--json out.json]
  python -m sector_wind.evidence harvest  --store local:$MIRROR [--json out.json]

`status` reports archive health, forecast skill by lead (+1/+3/+6/+12/+18 h, night = rubric window
and all hours), event contingency counts, and the gust and direction diagnostics. Event metrics are
shown only when enough observed events exist; otherwise the line says INSUFFICIENT EVENTS. That is a
reporting convention: the frozen rubric's own credit rule is applied by `scoreboard`, unchanged.

`harvest` scans the newest archived NBM cycles for upcoming useful validation regimes around the
four development lakes (forecast >= 10 mph, >= 15 mph, >= 20 kt gust, direction persistence). It
never changes a threshold and never touches field data."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np

from . import monitor
from .sample import circular_error, iso, parse_iso
from .validate import KT, MPH, _metrics, _night, collect, load_obs

LEADS = (1, 3, 6, 12, 18)
CLOCK_START = datetime(2026, 10, 7, 4, 59, tzinfo=timezone.utc)   # live shadow deployed (never reset)
MILESTONES = {"A": (datetime(2026, 10, 8, tzinfo=timezone.utc), datetime(2026, 10, 21, 23, tzinfo=timezone.utc)),
              "B": (datetime(2026, 10, 8, tzinfo=timezone.utc), datetime(2026, 11, 6, 23, tzinfo=timezone.utc))}
MIN_EVENTS_SHOWN = 10        # reporting convention for POD/FAR display only (not a rubric change)
EVENTS = {"10mph": ("speed", 10 * MPH), "15mph": ("speed", 15 * MPH), "gust20kt": ("gust", 20 * KT)}
SPEED_REGIMES = [(0, 2.6, "<2.6 (excluded from direction metric)"), (2.6, 4, "2.6-4"), (4, 6, "4-6"), (6, 99, ">=6")]


def _store(spec):
    from .store import open_store
    return open_store(spec)


def _cfg():
    import os
    return json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lakes.json")))


# ── archive health ───────────────────────────────────────────────────────────────────────────

def archive_health(store, cfg, start, end) -> dict:
    m = monitor.milestone(store, cfg, start, end)
    lakes = list(cfg["lakes"])
    expected = m["hours"] * len(lakes)
    received = round(sum(v["nbmShare"] for v in m["lakes"].values()) * m["hours"])
    now = min(end, datetime.now(timezone.utc))
    full_days = max(0, (now.replace(hour=0, minute=0, second=0, microsecond=0) - MILESTONES["A"][0]).days)
    return {"window": m["window"], "liveSince": iso(CLOCK_START), "completeLiveUTCDays": full_days,
            "milestoneA": {"window": [iso(MILESTONES["A"][0]), iso(MILESTONES["A"][1])], "checkOnOrAfter": "2026-10-22"},
            "milestoneB": {"window": [iso(MILESTONES["B"][0]), iso(MILESTONES["B"][1])], "checkOnOrAfter": "2026-11-07"},
            "nbmCyclesExpected": expected, "nbmCyclesReceived": received,
            "completeness": {lk: {"nbm": round(v["nbmShare"], 4), "rtma": round(v["rtmaShare"], 4)} for lk, v in m["lakes"].items()},
            "partialCycles": m["partialCycles"], "runs": m["runs"], "runsWithErrors": m["runsWithErrors"],
            "schemaDrift": m["schemaMismatches"], "timeLeakSuspects": m["timeLeakSuspects"],
            "medianRetrievalAgeMin": m["nbmAvailabilityAgeMin"]["median"], "p95RetrievalAgeMin": m["nbmAvailabilityAgeMin"]["p95"],
            "fallbackUses": m["runsUsingCatchup"], "problems": m["problems"][:5], "gate": m["gate"]}


# ── skill, events, diagnostics ───────────────────────────────────────────────────────────────

def contingency(recs, kind, thr) -> dict:
    """recs: (fspd, fdir, fgust, ospd, odir, ogust). A missing METAR gust is 'no gust reported'
    (METAR only reports gusts when present); it is never treated as a measured 0 in the bias."""
    i_f, i_o = (0, 3) if kind == "speed" else (2, 5)
    hits = misses = fa = 0
    for r in recs:
        f = (r[i_f] or 0) >= thr; o = (r[i_o] or 0) >= thr
        hits += f and o; misses += o and not f; fa += f and not o
    obs_events = hits + misses
    out = {"observedEvents": obs_events, "forecastEvents": hits + fa, "hits": hits, "misses": misses, "falseAlarms": fa}
    if obs_events < MIN_EVENTS_SHOWN:
        out["status"] = "INSUFFICIENT EVENTS"
    else:
        out["status"] = "SCORED"
        out["pod"] = hits / obs_events
        out["far"] = fa / (hits + fa) if (hits + fa) else None
    return out


def persistence_recs(obs, start, end, lead, night_only):
    pr = []
    for (sid, h), o in obs.items():
        if not (start <= h <= end) or (night_only and not _night(h)):
            continue
        p = obs.get((sid, h - timedelta(hours=lead)))
        if p:
            pr.append((p["speedMS"], p["dirFromDeg"], p["gustMS"], o["speedMS"], o["dirFromDeg"], o["gustMS"]))
    return pr


def _short(m):
    keys = ("n", "mae", "rmse", "bias", "dir_n", "dir_mean", "dir_median", "dir_within22_5", "dir_within45")
    return {k: (round(m[k], 3) if isinstance(m.get(k), float) else m.get(k)) for k in keys if k in m}


def direction_diagnostics(matches) -> dict:
    """Where does direction error live? Split by observed speed regime (including the light winds the
    frozen metric excludes, for diagnosis only), lead and station."""
    def errs(sel):
        e = [circular_error(m["rec"][1], m["rec"][4]) for m in sel if m["rec"][1] is not None and m["rec"][4] is not None]
        if not e:
            return {"n": 0}
        e = np.array(e)
        return {"n": len(e), "mean": round(float(e.mean()), 1), "median": round(float(np.median(e)), 1),
                "within22_5": round(float((e <= 22.5).mean()), 3), "within45": round(float((e <= 45).mean()), 3)}
    reg = {lab: errs([m for m in matches if lo <= m["rec"][3] < hi and m["rec"][0] >= (2.6 if lo >= 2.6 else 0)])
           for lo, hi, lab in SPEED_REGIMES}
    ok = [m for m in matches if m["rec"][0] >= 2.6 and m["rec"][3] >= 2.6]
    return {"byObservedSpeedMS": reg, "byLead": {l: errs([m for m in ok if m["lead"] == l]) for l in LEADS},
            "byStation": {s: errs([m for m in ok if m["station"] == s]) for s in sorted({m["station"] for m in ok})},
            "byLake": {lk: errs([m for m in ok if m["lake"] == lk]) for lk in sorted({m["lake"] for m in ok})}}


def gust_diagnostics(matches) -> dict:
    def cond(sel):
        g = [(m["rec"][2], m["rec"][5]) for m in sel if m["rec"][2] is not None and m["rec"][5] is not None]
        if not g:
            return {"n": 0}
        d = np.array([a - b for a, b in g])
        return {"n": len(g), "conditionalBias": round(float(d.mean()), 2), "conditionalMAE": round(float(np.abs(d).mean()), 2)}
    def sust(sel):
        e = np.array([m["rec"][0] - m["rec"][3] for m in sel])
        return {"n": len(e), "bias": round(float(e.mean()), 2), "mae": round(float(np.abs(e).mean()), 2)} if len(e) else {"n": 0}
    regimes = [(0, 4, "<4 m/s"), (4, 7, "4-7 m/s"), (7, 99, ">=7 m/s")]
    return {"byLead": {l: {"conditional": cond([m for m in matches if m["lead"] == l]),
                           "events20kt": contingency([m["rec"] for m in matches if m["lead"] == l], "gust", 20 * KT)} for l in LEADS},
            "byObservedSustained": {lab: cond([m for m in matches if lo <= m["rec"][3] < hi]) for lo, hi, lab in regimes},
            "sustainedWhenGustReported": sust([m for m in matches if m["rec"][5] is not None]),
            "question": "Is sustained wind good while gusts are poor? Compare sustainedWhenGustReported with the conditional gust bias."}


def status(store, cfg, start, end) -> dict:
    obs = load_obs(store, start - timedelta(days=1), end + timedelta(days=1))
    matches = collect(store, cfg, start, end, LEADS, obs)
    out = {"generatedAt": iso(datetime.now(timezone.utc)), "window": [iso(start), iso(end)],
           "archive": archive_health(store, cfg, start, end), "skill": {}, "events": {}}
    for part, night in (("night", True), ("allHours", False)):
        sk, ev = {}, {}
        for lead in LEADS:
            recs = [m["rec"] for m in matches if m["lead"] == lead and (not night or _night(m["validTime"]))]
            m = _short(_metrics(recs))
            pm = _metrics(persistence_recs(obs, start, end, lead, night))
            m["persistenceMAE"] = round(pm["mae"], 3) if pm.get("n") else None
            m["beatsPersistence"] = (m.get("mae") is not None and m["persistenceMAE"] is not None and m["mae"] < m["persistenceMAE"])
            sk[f"+{lead}h"] = m
            ev[f"+{lead}h"] = {k: contingency(recs, kind, thr) for k, (kind, thr) in EVENTS.items()}
        out["skill"][part] = sk
        out["events"][part] = ev
    out["directionDiagnostics"] = direction_diagnostics(matches)
    out["gustDiagnostics"] = gust_diagnostics(matches)
    out["matches"] = len(matches)
    return out


# ── event harvester ──────────────────────────────────────────────────────────────────────────

def _lake_series(store, lake, newest: datetime, max_back=6):
    """Newest archived NBM cycle for a lake (falling back up to 6 h), as a lake-wide median series."""
    for back in range(max_back + 1):
        c = store.get_json(f"nbm/{lake}/{newest - timedelta(hours=back):%Y%m%d%H}.json.gz")
        if c:
            ser = []
            for st in c["steps"]:
                sp = [x for x in st["speedMS"] if x is not None]
                if not sp:
                    continue
                u = np.nanmedian([-s * math.sin(math.radians(d)) for s, d in zip(st["speedMS"], st["dirFromDeg"]) if s is not None and d is not None] or [0])
                v = np.nanmedian([-s * math.cos(math.radians(d)) for s, d in zip(st["speedMS"], st["dirFromDeg"]) if s is not None and d is not None] or [0])
                g = [x for x in (st.get("gustMS") or []) if x is not None]
                ser.append({"validTime": st["validTime"], "lead": st["leadHours"], "speedMS": float(np.median(sp)),
                            "speedMaxMS": float(np.max(sp)), "gustMaxMS": float(np.max(g)) if g else None,
                            "dirFromDeg": (math.degrees(math.atan2(-u, -v)) + 360) % 360})
            return c["initTime"], ser
    return None, []


def harvest(store, cfg, now: datetime | None = None) -> dict:
    """Upcoming useful regimes. A 'window' is a run of consecutive forecast hours >= 10 mph (lake-wide
    median). Persistence = longest run whose direction stays within ±22.5° of the run's first hour
    (the same tolerance the frozen duration rule uses)."""
    now = now or datetime.now(timezone.utc)
    newest = now.replace(minute=0, second=0, microsecond=0)
    out = {"generatedAt": iso(now), "lakes": {}}
    for lake in cfg["lakes"]:
        init, ser = _lake_series(store, lake, newest)
        ser = [s for s in ser if parse_iso(s["validTime"]) >= newest]
        hours = []
        for s in ser:
            flags = [k for k, ok in (("10mph", s["speedMS"] >= 10 * MPH), ("15mph", s["speedMS"] >= 15 * MPH),
                                     ("gust20kt", (s["gustMaxMS"] or 0) >= 20 * KT)) if ok]
            hours.append({**s, "flags": flags, "night": _night(parse_iso(s["validTime"]))})
        windows, cur = [], []
        for h in hours + [None]:
            if h and "10mph" in h["flags"]:
                cur.append(h); continue
            if cur:
                d0 = cur[0]["dirFromDeg"]; run = 1
                for x in cur[1:]:
                    if circular_error(x["dirFromDeg"], d0) <= 22.5:
                        run += 1
                    else:
                        break
                windows.append({"start": cur[0]["validTime"], "end": cur[-1]["validTime"], "hours": len(cur),
                                "nightHours": sum(x["night"] for x in cur), "peakMedianMS": round(max(x["speedMS"] for x in cur), 2),
                                "peakGustMS": max((x["gustMaxMS"] or 0) for x in cur) or None,
                                "dirFromDeg": round(statistics.median([x["dirFromDeg"] for x in cur])),
                                "directionPersistentHours": run, "has15mph": any("15mph" in x["flags"] for x in cur),
                                "hasGust20kt": any("gust20kt" in x["flags"] for x in cur)})
            cur = []
        out["lakes"][lake] = {"nbmInit": init, "horizonEnd": ser[-1]["validTime"] if ser else None, "windows": windows,
                              "hourly": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in h.items()} for h in hours]}
    return out


# ── text rendering ───────────────────────────────────────────────────────────────────────────

def render_status(s) -> str:
    a = s["archive"]; L = []
    L.append(f"WIND EVIDENCE STATUS  window {s['window'][0]} -> {s['window'][1]}")
    L.append(f"Archive: live since {a['liveSince']}; complete live UTC days {a['completeLiveUTCDays']} / 30 (Milestone A check >= 2026-10-22, B >= 2026-11-07)")
    L.append(f"  NBM cycles {a['nbmCyclesReceived']} / {a['nbmCyclesExpected']} expected; partial {a['partialCycles']}; "
             f"runs {a['runs']} ({a['runsWithErrors']} with errors); schema drift {a['schemaDrift']}; time-leak suspects {a['timeLeakSuspects']}")
    L.append(f"  retrieval age median {a['medianRetrievalAgeMin']} min, p95 {a['p95RetrievalAgeMin']} min; fallback (catch-up) uses {a['fallbackUses']}")
    L.append("  completeness: " + ", ".join(f"{k} NBM {v['nbm']:.1%} RTMA {v['rtma']:.1%}" for k, v in a["completeness"].items()))
    for part in ("night", "allHours"):
        L.append(f"Skill ({part}{', rubric window 01-08 UTC' if part == 'night' else ''}):")
        L.append("  lead    n     MAE   RMSE  bias   dirMAE  <=22.5  <=45   persistMAE beats")
        for lead, m in s["skill"][part].items():
            f = lambda k, w=6, p=2: (f"{m[k]:.{p}f}" if isinstance(m.get(k), (int, float)) and m.get(k) is not None else "-").rjust(w)
            L.append(f"  {lead:>5} {m.get('n', 0):>5} {f('mae')} {f('rmse')} {f('bias')} {f('dir_mean', 7, 1)} {f('dir_within22_5', 7)} "
                     f"{f('dir_within45')} {f('persistenceMAE', 10)} {'yes' if m.get('beatsPersistence') else 'no'}")
        L.append("  events (hits / misses / false alarms; POD/FAR only when >= %d observed):" % MIN_EVENTS_SHOWN)
        for lead, ev in s["events"][part].items():
            parts = []
            for k, c in ev.items():
                tail = f"POD {c['pod']:.2f} FAR {('%.2f' % c['far']) if c['far'] is not None else '-'}" if c["status"] == "SCORED" else "INSUFFICIENT EVENTS"
                parts.append(f"{k}: obs {c['observedEvents']} fc {c['forecastEvents']} ({c['hits']}/{c['misses']}/{c['falseAlarms']}) {tail}")
            L.append(f"  {lead:>5} " + " | ".join(parts))
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "harvest"])
    ap.add_argument("--store", required=True)
    ap.add_argument("--start", default=None); ap.add_argument("--end", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    store, cfg = _store(a.store), _cfg()
    if a.cmd == "status":
        start = datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc) if a.start else CLOCK_START.replace(minute=0)
        # default end: the newest cycle that can already be published (NBM posts ~65 min after init),
        # so a not-yet-published hour is never counted as a gap
        end = (datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc) + timedelta(hours=23)) if a.end else \
            (datetime.now(timezone.utc) - timedelta(minutes=90)).replace(minute=0, second=0, microsecond=0)
        s = status(store, cfg, start, end)
        print(render_status(s))
    else:
        s = harvest(store, cfg)
        for lk, v in s["lakes"].items():
            print(f"{lk}: NBM {v['nbmInit']} -> {v['horizonEnd']}: " + ("; ".join(
                f"{w['start'][5:16]}..{w['end'][11:16]} {w['hours']}h (night {w['nightHours']}) peak {w['peakMedianMS']} m/s from {w['dirFromDeg']}°"
                f"{' 15mph' if w['has15mph'] else ''}{' gust20kt' if w['hasGust20kt'] else ''} steady {w['directionPersistentHours']}h"
                for w in v["windows"]) or "no >= 10 mph window in the horizon"))
    if a.json:
        json.dump(s, open(a.json, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
