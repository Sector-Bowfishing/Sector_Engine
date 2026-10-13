"""History for binding2 bindings: for a chosen binding row return the best daily series and its complete-year count.
Sources tried in order (all already-downloaded or fetched on demand, polite): wave-1 history files (history_results.json), binding2 candidate histPath,
IEM HADS pulls (hads_history.py), and relay IDs (NWPS usgsId -> USGS dv elevation parameter)."""
import csv, gzip, json, os
from common2 import *
from providers import year_completeness, usgs_dv_history
import envelope_promote as EP

W1H = json.load(open(f"{BIND}/history_results.json"))


def load_daily(path):
    if path and os.path.exists(path):
        return {r[0]: float(r[1]) for r in csv.reader(gzip.open(path, "rt")) if r}
    return None


def best_history(lake_id, prov, station, loc, series, hist_path=None, nwps_usgs=None):
    """returns (label, daily dict or None, completeness dict)"""
    opts = []
    w = W1H.get(f"{lake_id}|{prov}|{station}|{loc}", {}).get("best")
    if w:
        opts.append((w["series"], EP.hist_file(w["series"])))
    if hist_path:
        opts.append((f"b2:{os.path.basename(hist_path)}", f"{B2}/{hist_path}" if not hist_path.startswith("/") else hist_path))
    if prov == "twdb":     # wave-1 bookkeeping miss: station is 'Amistad' but the history file and the TWDB URL are lower case
        opts.append((f"twdb:{station.lower()}", f"{BIND}/history/twdb_{station.lower()}.csv.gz"))
    if prov == "coops":
        opts.append((f"coops:{station}", f"{B2}/history/coops_{station}_daily_mean.csv.gz"))
    if prov == "nwps":
        opts.append((f"hads:{station}:{series}", f"{B2}/history/hads_{station}_{series}.csv.gz"))
    best = None
    for label, p in opts:
        d = load_daily(p)
        if not d:
            continue
        c = year_completeness(d)
        if best is None or c["completeYears"] > best[2]["completeYears"]:
            best = (label, d, c)
    return best or (None, None, dict(completeYears=0))


def usgs_iv_history(site, param, y0=2007):
    """Daily means from the NWIS instantaneous-values archive (yearly requests) for sites that have no daily-value series. Cached in binding2/history."""
    import datetime as dt, statistics
    p = f"{B2}/history/usgsiv_{site}_{param}.csv.gz"
    if os.path.exists(p):
        return load_daily(p)
    daily = {}
    for y in range(y0, 2026):
        s_, d = get_json(f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={site}&parameterCd={param}&startDT={y}-01-01&endDT={y}-12-31&siteStatus=all", timeout=180, sleep=0.8)
        if not d:
            continue
        by = {}
        for ts in d["value"]["timeSeries"]:
            nd = ts["variable"].get("noDataValue", -999999)
            for blk in ts["values"]:
                for v in blk["value"]:
                    try:
                        x = float(v["value"])
                    except Exception:
                        continue
                    if x != nd:
                        by.setdefault(v["dateTime"][:10], []).append(x)
        daily.update({k: sum(v) / len(v) for k, v in by.items()})
    with gzip.open(p, "wt", newline="") as f:
        w = csv.writer(f)
        for k in sorted(daily):
            w.writerow([k, round(daily[k], 4)])
    return daily
