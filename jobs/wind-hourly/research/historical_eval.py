"""Stage 3C: evaluate the pre-registered NBM v5.0 historical corpus (WIND_HISTORICAL_CORPUS_PREREG.md).

  python research/historical_eval.py skill    OUT.json     # frozen §4 metrics, validate.skill format (scoreboard input)
  python research/historical_eval.py evidence OUT.json     # events, direction + gust diagnostics (evidence.status)
  python research/historical_eval.py gust     OUT.json     # gust candidates A/B/C/D, chronological calibration/holdout split

Nothing here changes the Candidate."""
import json, os, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sector_wind.store import LocalStore
from sector_wind.ingest import load_config
from sector_wind.interp import CutoutIndex, blend
from sector_wind.validate import skill, collect, load_obs, _metrics, _night, KT
from sector_wind import evidence
from sector_wind.sample import iso

ROOT = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50")
START, END = datetime(2026, 5, 6, 0, tzinfo=timezone.utc), datetime(2026, 10, 6, 23, tzinfo=timezone.utc)
LEADS = (1, 3, 6, 12, 18)
SPLIT = datetime(2026, 8, 16, tzinfo=timezone.utc)      # pre-registered: inits before = calibration, from = holdout
G20 = 20 * KT


def gust_rows(store, cfg):
    """One row per (station, lead, valid hour): NBM gust (A), qmd gust P90 (B, synoptic inits only), HRRR gust (C)."""
    obs = load_obs(store, START - timedelta(days=1), END + timedelta(days=2))
    st_by_lake = defaultdict(list)
    for sid, s in cfg["stations"].items():
        st_by_lake[s["lake"]].append(sid)
    w_nbm, w_hrrr, rows = {}, {}, []
    t = START
    while t <= END:
        for lake in cfg["lakes"]:
            c = store.get_json(f"nbm/{lake}/{t:%Y%m%d%H}.json.gz")
            if not c:
                continue
            h = store.get_json(f"hrrr/{lake}/{t:%Y%m%d%H}.json.gz")
            if lake not in w_nbm:
                g = store.get_json(c["grid"]); ci = CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"])
                w_nbm[lake] = {s: ci.weights(cfg["stations"][s]["lat"], cfg["stations"][s]["lon"]) for s in st_by_lake[lake]}
            if h and lake not in w_hrrr:
                g = store.get_json(h["grid"]); ci = CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"])
                w_hrrr[lake] = {s: ci.weights(cfg["stations"][s]["lat"], cfg["stations"][s]["lon"]) for s in st_by_lake[lake]}
            hsteps = {s["leadHours"]: s for s in (h or {}).get("steps", [])}
            for stp in c["steps"]:
                vt = datetime.strptime(stp["validTime"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                for sid, wt in w_nbm[lake].items():
                    o = obs.get((sid, vt))
                    if not o or o["speedMS"] is None:
                        continue
                    hs = hsteps.get(stp["leadHours"])
                    rows.append({"station": sid, "lake": lake, "init": t, "valid": vt, "lead": stp["leadHours"], "night": _night(vt),
                                 "nbmSpeed": blend(stp["speedMS"], wt), "A": blend(stp["gustMS"], wt),
                                 "B": blend(stp["gustP90"], wt) if "gustP90" in stp else None,
                                 "C": blend(hs["gustMS"], w_hrrr[lake][sid]) if hs and lake in w_hrrr else None,
                                 "obsSpeed": o["speedMS"], "obsGust": o["gustMS"]})
        t += timedelta(hours=1)
    return rows


def gust_metrics(rows, key):
    rs = [r for r in rows if r.get(key) is not None]
    cond = [(r[key], r["obsGust"]) for r in rs if r["obsGust"] is not None]
    d = np.array([a - b for a, b in cond]) if cond else np.array([])
    ob = np.array([(r["obsGust"] or 0) >= G20 for r in rs]); fb = np.array([r[key] >= G20 for r in rs])
    hits = int((ob & fb).sum()); obs_ev = int(ob.sum()); fc_ev = int(fb.sum())
    return {"n": len(rs), "conditionalN": len(cond), "conditionalBias": round(float(d.mean()), 3) if len(d) else None,
            "conditionalMAE": round(float(np.abs(d).mean()), 3) if len(d) else None,
            "obsEvents20kt": obs_ev, "fcEvents20kt": fc_ev, "hits": hits,
            "pod": round(hits / obs_ev, 3) if obs_ev else None, "far": round((fc_ev - hits) / fc_ev, 3) if fc_ev else None}


def gust_audit(store, cfg):
    rows = gust_rows(store, cfg)
    cal = [r for r in rows if r["init"] < SPLIT]; hold = [r for r in rows if r["init"] >= SPLIT]
    out = {"split": f"calibration inits < {iso(SPLIT)}; holdout >= (pre-registered)", "rows": len(rows)}
    # D: least squares on calibration rows where METAR reported a gust: obsGust ~ a + b*A + c*nbmSpeed
    fit = [r for r in cal if r["obsGust"] is not None and r["A"] is not None]
    X = np.array([[1.0, r["A"], r["nbmSpeed"]] for r in fit]); y = np.array([r["obsGust"] for r in fit])
    coef = np.linalg.lstsq(X, y, rcond=None)[0] if len(fit) >= 30 else None
    for r in rows:
        r["D"] = float(coef @ [1.0, r["A"], r["nbmSpeed"]]) if coef is not None and r["A"] is not None else None
    out["D_fit"] = {"n": len(fit), "coef[a, b*A, c*speed]": None if coef is None else [round(float(x), 3) for x in coef],
                    "note": "fitted on calibration, gust-reported rows only; evaluated once on holdout"}
    for name, rs in (("calibration", cal), ("holdout", hold), ("all", rows)):
        out[name] = {k: gust_metrics(rs, k) for k in ("A", "B", "C", "D")}
        out[name]["A_on_synoptic_only"] = gust_metrics([r for r in rs if r["B"] is not None], "A")
        out[name]["A_on_hrrr_rows_only"] = gust_metrics([r for r in rs if r["C"] is not None], "A")
    # definition check: how often does NBM gust exceed sustained, and how selective is METAR gust reporting?
    rep = [r for r in rows if r["obsGust"] is not None]
    out["definition"] = {"metarGustReportedShare": round(len(rep) / len(rows), 4) if rows else None,
                         "nbmGustAlwaysPresentShare": round(sum(r["A"] is not None for r in rows) / len(rows), 4) if rows else None,
                         "obsGustMinusObsSpeed_median_ms": round(float(np.median([r["obsGust"] - r["obsSpeed"] for r in rep])), 2) if rep else None,
                         "nbmGustMinusNbmSpeed_median_ms": round(float(np.median([r["A"] - r["nbmSpeed"] for r in rows if r["A"] is not None])), 2),
                         "nbmGustMinusNbmSpeed_median_ms_whenMetarGust": round(float(np.median([r["A"] - r["nbmSpeed"] for r in rep if r["A"] is not None])), 2) if rep else None,
                         "sustainedBiasWhenMetarGust": round(float(np.mean([r["nbmSpeed"] - r["obsSpeed"] for r in rep])), 3) if rep else None}
    # by observed sustained regime and lead (A)
    out["A_byObservedSustained"] = {lab: gust_metrics([r for r in rows if lo <= r["obsSpeed"] < hi], "A")
                                    for lo, hi, lab in ((0, 4, "<4"), (4, 7, "4-7"), (7, 99, ">=7"))}
    out["A_byLead"] = {l: gust_metrics([r for r in rows if r["lead"] == l], "A") for l in LEADS}
    return out


if __name__ == "__main__":
    cmd, outp = sys.argv[1], sys.argv[2]
    store, cfg = LocalStore(ROOT), load_config()
    if cmd == "skill":
        res = {"nbm": skill(store, cfg, START, END, LEADS), "corpus": "NBM v5.0 historical 2026-05-06 -> 2026-10-06 (pre-registered)"}
        res["nbm"]["persistenceNight"] = res["nbm"]["persistenceNight"]
    elif cmd == "evidence":
        res = evidence.status(store, cfg, START, END)
    else:
        res = gust_audit(store, cfg)
    json.dump(res, open(outp, "w"), indent=1, default=str)
    print("wrote", outp)
