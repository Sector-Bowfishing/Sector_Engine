"""Stage 3D.1 §A retrospective benchmark (pre-registered sha 2f935d06…). Untuned sources vs direct NBM on IDENTICAL rows.

  python research/provider_eval.py OUT.json

Pairings:
  by-init (pre-registered): source run t, lead L  <->  NBM init t, lead L                      (synoptic inits)
  availability-matched (diagnostic): source run t is usable at ~t+a; it is compared with the NBM init t+a that Sector would
    hold then, at the same valid time (a: GFS/ICON 3 h, ECMWF IFS/UKMO 6 h; approximate dissemination latencies)
  NDFD: first issuance in hour HH (HH:16) <-> NBM init HH-1 (published ~HH:05), L in {3,6,12,18}.
Truth: METAR (rows.pkl from Stage 3D). Nothing is fitted."""
import json, os, pickle, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sector_wind.sample import circular_error

H = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50")
ROWS = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/stage3d/rows.pkl")
LAT = {"gfs_global": 3, "icon_global": 3, "ecmwf_ifs": 6, "ukmo_global_deterministic_10km": 6, "ncep_nbm_conus": 0}
MPH, KT = 0.44704, 0.514444
T = {"10mph": 10 * MPH, "15mph": 15 * MPH, "20mph": 20 * MPH}
G = {"15kt": 15 * KT, "20kt": 20 * KT, "25kt": 25 * KT}


def om_series(model, t):
    p = os.path.join(H, "openmeteo", model, f"{t:%Y%m%d%H}.json")
    if not os.path.exists(p):
        return None
    js = json.load(open(p)); js = js if isinstance(js, list) else [js]
    ids = ["8A1", "4A6", "DCU", "HSV", "9A4", "MSL", "SNH", "15M"]
    out = {}
    for sid, j in zip(ids, js):
        h = j.get("hourly") or {}
        for i, ts in enumerate(h.get("time", [])):
            vt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
            out[(sid, vt)] = (h["wind_speed_10m"][i], h["wind_direction_10m"][i], h["wind_gusts_10m"][i])
    return out


def ndfd(t):
    p = os.path.join(H, "ndfd", f"{t:%Y%m%d%H}.json")
    if not os.path.exists(p):
        return None
    r = json.load(open(p)); out = {}
    for sid, vv in r["values"].items():
        for ts, x in vv.items():
            out[(sid, datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc))] = (x.get("wspd"), x.get("wdir"), x.get("wgust"))
    return out


def metrics(pairs):
    """pairs: dicts with s,d,g (source), ns,nd,ng (NBM same row), os,od,og (obs), night, lead, set."""
    def one(key_s, key_d, key_g, rows):
        rows = [r for r in rows if r[key_s] is not None]
        if not rows:
            return {"n": 0}
        e = np.array([r[key_s] - r["os"] for r in rows]); ni = [r for r in rows if r["night"]]
        en = np.array([r[key_s] - r["os"] for r in ni]) if ni else np.array([])
        de = np.array([circular_error(r[key_d], r["od"]) for r in rows if r[key_d] is not None and r["od"] is not None and r[key_s] >= 2.6 and r["os"] >= 2.6])
        out = {"n": len(rows), "mae": float(np.abs(e).mean()), "bias": float(e.mean()), "rmse": float(np.sqrt((e ** 2).mean())),
               "nightN": len(en), "nightMAE": float(np.abs(en).mean()) if len(en) else None, "nightBias": float(en.mean()) if len(en) else None,
               "dirN": len(de), "dir22": float((de <= 22.5).mean()) if len(de) else None, "dirMAE": float(de.mean()) if len(de) else None,
               "dir45": float((de <= 45).mean()) if len(de) else None}
        for k, thr in T.items():
            h = sum(r[key_s] >= thr and r["os"] >= thr for r in rows); m = sum(r["os"] >= thr and r[key_s] < thr for r in rows)
            fa = sum(r[key_s] >= thr and r["os"] < thr for r in rows)
            out[k] = {"obs": h + m, "fc": h + fa, "pod": h / (h + m) if h + m else None, "far": fa / (h + fa) if h + fa else None,
                      "csi": h / (h + m + fa) if h + m + fa else None}
        gr = [r for r in rows if r[key_g] is not None]
        cond = np.array([r[key_g] - r["og"] for r in gr if r["og"] is not None])
        out["gustCondBias"] = float(cond.mean()) if len(cond) else None
        for k, thr in G.items():
            h = sum(r[key_g] >= thr and (r["og"] or 0) >= thr for r in gr); m = sum((r["og"] or 0) >= thr and r[key_g] < thr for r in gr)
            fa = sum(r[key_g] >= thr and (r["og"] or 0) < thr for r in gr)
            out["gust" + k] = {"obs": h + m, "fc": h + fa, "pod": h / (h + m) if h + m else None, "far": fa / (h + fa) if h + fa else None}
        bins = [(0, 5, "<5mph"), (5, 10, "5-10"), (10, 15, "10-15"), (15, 20, "15-20"), (20, 99, ">20")]
        out["byObsMph"] = {lab: (lambda rr: {"n": len(rr), "mae": float(np.mean([abs(r[key_s] - r["os"]) for r in rr])) if rr else None,
                                             "bias": float(np.mean([r[key_s] - r["os"] for r in rr])) if rr else None})(
            [r for r in rows if lo * MPH <= r["os"] < hi * MPH]) for lo, hi, lab in bins}
        out["byLead"] = {L: float(np.mean([abs(r[key_s] - r["os"]) for r in rows if r["lead"] == L])) if any(r["lead"] == L for r in rows) else None
                         for L in (1, 3, 6, 12, 18)}
        return out
    return {"source": one("s", "d", "g", pairs), "nbm": one("ns", "nd", "ng", pairs)}


def main(outp):
    R = pickle.load(open(ROWS, "rb"))
    idx = {(r["station"], r["init"], r["lead"]): r for r in R}
    res = {}
    def row(r, s, d, g):
        return {"s": s, "d": d, "g": g, "ns": r["nbmS"], "nd": r["nbmD"], "ng": r["nbmG"], "os": r["obsS"], "od": r["obsD"], "og": r["obsG"],
                "night": r["night"], "lead": r["lead"], "set": r["set"], "evening": r["valid"].hour in (23, 0, 1)}
    syn = sorted({r["init"] for r in R if r["init"].hour % 6 == 0})
    for model, a in LAT.items():
        for mode in ("byInit", "availability") if a else ("byInit",):
            P = []
            for t in syn:
                ser = om_series(model, t)
                if not ser:
                    continue
                shift = a if mode == "availability" else 0
                for (sid, init, L), r in ((k, v) for k, v in idx.items() if k[1] == t + timedelta(hours=shift)):
                    x = ser.get((sid, r["valid"]))
                    if x and x[0] is not None:
                        P.append(row(r, x[0], x[1], x[2]))
            res[f"openmeteo:{model}:{mode}"] = {s: metrics([p for p in P if p["set"] == s]) for s in ("CAL", "H1")}
            res[f"openmeteo:{model}:{mode}"]["all"] = metrics(P)
            if model == "ncep_nbm_conus":   # parity: Open-Meteo NBM vs direct NOAA NBM on the same rows
                d = np.array([p["s"] - p["ns"] for p in P]); dd = np.array([circular_error(p["d"], p["nd"]) for p in P if p["d"] is not None and p["nd"] is not None and p["ns"] >= 2.6])
                gg = np.array([p["g"] - p["ng"] for p in P if p["g"] is not None and p["ng"] is not None])
                res["parity_openmeteo_nbm"] = {"n": len(d), "speedMeanDiff": float(d.mean()), "speedMAD": float(np.abs(d).mean()), "speedMaxAbs": float(np.abs(d).max()),
                                               "share_within_0.2": float((np.abs(d) <= 0.2).mean()), "dirMedianDiff": float(np.median(dd)) if len(dd) else None,
                                               "gustMeanDiff": float(gg.mean()) if len(gg) else None, "gustMAD": float(np.abs(gg).mean()) if len(gg) else None}
    P = []
    for t in syn:
        nd = ndfd(t)
        if not nd:
            continue
        for L in (3, 6, 12, 18):
            for sid in ("8A1", "4A6", "DCU", "HSV", "9A4", "MSL", "SNH", "15M"):
                r = idx.get((sid, t - timedelta(hours=1), L))
                x = nd.get((sid, r["valid"])) if r else None
                if r and x and x[0] is not None:
                    P.append(row(r, x[0], x[1], x[2]))
    res["ndfd"] = {s: metrics([p for p in P if p["set"] == s]) for s in ("CAL", "H1")}; res["ndfd"]["all"] = metrics(P)
    json.dump(res, open(outp, "w"), indent=1, default=str)
    print("wrote", outp)


if __name__ == "__main__":
    main(sys.argv[1])
