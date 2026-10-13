"""Provider adapters: live-window probe + daily-history fetch. All read-only GETs, cached under raw/probe/."""
import csv, datetime as dt, gzip, io, json, os, statistics, urllib.parse
from common import *

NOW = dt.datetime.now(dt.timezone.utc)
PROBE = f"{RAW}/probe"
HIST = f"{BIND}/history"
os.makedirs(PROBE, exist_ok=True); os.makedirs(HIST, exist_ok=True)
FT_PER_M = 3.280839895


def _safe(k):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in k)[:180]


def cached_json(key, fetch):
    p = f"{PROBE}/{_safe(key)}.json.gz"
    if os.path.exists(p):
        return json.load(gzip.open(p, "rt"))
    v = fetch()
    if v is not None:
        with gzip.open(p, "wt") as f:
            json.dump(v, f)
    return v


def summarize(points, unit="ft"):
    """points: list of (epoch_s, value). Returns last-observation stats (values in ft when unit is m)."""
    pts = sorted((t, v) for t, v in points if v is not None)
    if not pts:
        return dict(n=0)
    k = FT_PER_M if unit in ("m", "meter", "meters") else 1.0
    vals = [v * k for _, v in pts]
    last_t = pts[-1][0]
    return dict(n=len(pts), last_t=dt.datetime.fromtimestamp(last_t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                age_h=round((NOW.timestamp() - last_t) / 3600, 1), last_ft=round(vals[-1], 3), med_ft=round(statistics.median(vals), 3),
                min_ft=round(min(vals), 3), max_ft=round(max(vals), 3), first_t=dt.datetime.fromtimestamp(pts[0][0], dt.timezone.utc).strftime("%Y-%m-%d"))


# ------------------------------------------------------------------ USGS (legacy NWIS web services, still live 2026-10-13)
def usgs_iv_batch(sites, params, days=30):
    key = f"usgs_iv_{'_'.join(sorted(sites))[:60]}_{abs(hash(tuple(sorted(sites))+tuple(sorted(params))))%10**8}_{NOW.strftime('%Y%m%d')}"

    def fetch():
        u = ("https://waterservices.usgs.gov/nwis/iv/?format=json&sites=" + ",".join(sites) + "&parameterCd=" + ",".join(params) +
             f"&period=P{days}D&siteStatus=all")
        s, d = get_json(u, timeout=120)
        return {"status": s, "d": d} if s in (200, 404) else None
    r = cached_json(key, fetch)
    out = {}
    if not r or not r.get("d"):
        return out
    for ts in r["d"]["value"]["timeSeries"]:
        site = ts["sourceInfo"]["siteCode"][0]["value"]
        par = ts["variable"]["variableCode"][0]["value"]
        nd = ts["variable"].get("noDataValue", -999999)
        pts = []
        for blk in ts["values"]:
            for v in blk["value"]:
                try:
                    x = float(v["value"])
                except Exception:
                    continue
                if x == nd:
                    continue
                t = dt.datetime.fromisoformat(v["dateTime"]).timestamp()
                pts.append((t, x))
        out.setdefault(site, {}).setdefault(par, []).extend(pts)
    return out


def usgs_dv_recent(site, param, days=45):
    key = f"usgs_dvr_{site}_{param}_{NOW.strftime('%Y%m%d')}"

    def fetch():
        s, d = get_json(f"https://waterservices.usgs.gov/nwis/dv/?format=json&sites={site}&parameterCd={param}&period=P{days}D&siteStatus=all", timeout=90)
        return {"status": s, "d": d} if s in (200, 404) else None
    r = cached_json(key, fetch)
    pts = []
    if r and r.get("d"):
        for ts in r["d"]["value"]["timeSeries"]:
            for blk in ts["values"]:
                for v in blk["value"]:
                    try:
                        pts.append((dt.datetime.fromisoformat(v["dateTime"] + ("" if "+" in v["dateTime"][10:] or "-" in v["dateTime"][10:] else "+00:00")).timestamp(), float(v["value"])))
                    except Exception:
                        pass
    return pts


def usgs_dv_history(site, param):
    """Full daily-value history for (site,param). Returns {date: value} merging stat 00003 then 32400 (documented)."""
    p = f"{HIST}/usgs_{site}_{param}.csv.gz"
    if os.path.exists(p):
        return {r[0]: float(r[1]) for r in csv.reader(gzip.open(p, "rt")) if r}
    s, d = get_json(f"https://waterservices.usgs.gov/nwis/dv/?format=json&sites={site}&parameterCd={param}&startDT=1900-01-01&endDT={NOW.strftime('%Y-%m-%d')}&siteStatus=all", timeout=300)
    if d is None:
        return None
    bystat = {}
    for ts in d["value"]["timeSeries"]:
        stat = (ts["variable"].get("options", {}).get("option") or [{}])[0].get("optionCode") or "?"
        for blk in ts["values"]:
            for v in blk["value"]:
                try:
                    x = float(v["value"])
                except Exception:
                    continue
                if x == ts["variable"].get("noDataValue", -999999):
                    continue
                bystat.setdefault(stat, {})[v["dateTime"][:10]] = x
    merged = {}
    for stat in ("00003", "32400", "00001", "00002", "?"):   # fill-in order: daily mean first
        for k, x in bystat.get(stat, {}).items():
            merged.setdefault(k, x)
    with gzip.open(p, "wt", newline="") as f:
        w = csv.writer(f)
        for k in sorted(merged):
            w.writerow([k, merged[k]])
    return merged


# ------------------------------------------------------------------ CWMS
CWMS = "https://cwms-data.usace.army.mil/cwms-data"
CH = {"Accept": "application/json;version=2"}


def cwms_ts(office, name, begin, end, unit="EN", page_size=100000, max_pages=30):
    pts, page, info = [], None, {}
    for _ in range(max_pages):
        q = dict(name=name, office=office, begin=begin, end=end, unit=unit, **{"page-size": page_size})
        if page:
            q["page"] = page
        s, d = get_json(CWMS + "/timeseries?" + urllib.parse.urlencode(q), CH, timeout=180, sleep=0.25)
        if d is None:
            return None, {"status": s}
        info = {k: d.get(k) for k in ("units", "interval", "time-zone", "vertical-datum-info", "total")}
        pts += [(v[0] / 1000.0, v[1]) for v in d.get("values", []) if v[1] is not None]
        page = d.get("next-page")
        if not page:
            break
    return pts, info


def cwms_recent(office, name, days=30):
    key = f"cwms_{office}_{name}_{NOW.strftime('%Y%m%d')}"

    def fetch():
        b = (NOW - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ"); e = (NOW + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pts, info = cwms_ts(office, name, b, e)
        return {"pts": pts, "info": info} if pts is not None else None
    return cached_json(key, fetch)


def cwms_history(office, name, since_year=None):
    p = f"{HIST}/cwms_{office}_{_safe(name)}.csv.gz"
    if os.path.exists(p):
        return {r[0]: float(r[1]) for r in csv.reader(gzip.open(p, "rt")) if r}
    b = f"{since_year or 1900}-01-01T00:00:00Z"; e = (NOW + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    pts, info = cwms_ts(office, name, b, e)
    if pts is None:
        return None
    byday = {}
    for t, v in pts:
        byday.setdefault(dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"), []).append(v)
    daily = {k: sum(v) / len(v) for k, v in byday.items()}
    with gzip.open(p, "wt", newline="") as f:
        w = csv.writer(f)
        for k in sorted(daily):
            w.writerow([k, round(daily[k], 4)])
    return daily


# ------------------------------------------------------------------ RISE
def rise_results(item_id, after, before=None, per=2000, max_pages=40):
    out, page = [], 1
    while page <= max_pages:
        q = {"itemId": item_id, "dateTime[after]": after, "itemsPerPage": per, "page": page}
        if before:
            q["dateTime[before]"] = before
        s, d = get_json("https://data.usbr.gov/rise/api/result?" + urllib.parse.urlencode(q), {"Accept": "application/vnd.api+json"}, timeout=120, sleep=0.25)
        if d is None:
            return None
        out += [(dt.datetime.fromisoformat(x["attributes"]["dateTime"]).timestamp(), x["attributes"]["result"]) for x in d["data"] if x["attributes"]["result"] is not None]
        if not d["links"].get("next"):
            break
        page += 1
    return out


def rise_recent(item_id, days=45):
    key = f"rise_{item_id}_{NOW.strftime('%Y%m%d')}"
    return cached_json(key, lambda: rise_results(item_id, (NOW - dt.timedelta(days=days)).strftime("%Y-%m-%d")))


def rise_history(item_id):
    p = f"{HIST}/rise_{item_id}.csv.gz"
    if os.path.exists(p):
        return {r[0]: float(r[1]) for r in csv.reader(gzip.open(p, "rt")) if r}
    pts = rise_results(item_id, "1900-01-01")
    if pts is None:
        return None
    daily = {}
    for t, v in pts:
        daily.setdefault(dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"), []).append(v)
    daily = {k: sum(v) / len(v) for k, v in daily.items()}
    with gzip.open(p, "wt", newline="") as f:
        w = csv.writer(f)
        for k in sorted(daily):
            w.writerow([k, round(daily[k], 4)])
    return daily


# ------------------------------------------------------------------ TWDB
def twdb_history(short):
    p = f"{HIST}/twdb_{_safe(short)}.csv.gz"
    if os.path.exists(p):
        return {r[0]: float(r[1]) for r in csv.reader(gzip.open(p, "rt")) if r}
    s, b = http_get(f"https://www.waterdatafortexas.org/reservoirs/individual/{urllib.parse.quote(short)}.csv", timeout=120)
    if s != 200:
        return None
    daily = {}
    for r in csv.DictReader(io.StringIO("\n".join(l for l in b.splitlines() if not l.startswith("#")))):
        try:
            daily[r["date"]] = float(r["water_level"])
        except Exception:
            pass
    with gzip.open(p, "wt", newline="") as f:
        w = csv.writer(f)
        for k in sorted(daily):
            w.writerow([k, daily[k]])
    return daily


# ------------------------------------------------------------------ completeness (Lake Brain baseline rule, LAKE_BRAIN_INTEGRATION s6)
def year_completeness(daily, today=None):
    """daily: {YYYY-MM-DD: value}. A year is complete when >= 90% of its days have a value (329/365). The current partial year never counts."""
    today = today or NOW
    cur = today.year
    by = {}
    for k in daily:
        by[int(k[:4])] = by.get(int(k[:4]), 0) + 1
    out = {}
    for y, n in by.items():
        if y >= cur:
            continue
        days = 366 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 365
        out[y] = round(n / days, 3)
    complete = sorted(y for y, c in out.items() if c >= 0.90)
    # most recent 30 complete years used by the baseline
    recent = [y for y in complete if y >= cur - 30]
    return dict(completeYears=len(complete), completeYears30=len(recent), firstYear=min(by) if by else None, lastDay=max(daily) if daily else None,
                nDays=len(daily), yearsCovered=len(out), maxConsecutive=_max_run(complete))


def _max_run(ys):
    best = run = 0; prev = None
    for y in ys:
        run = run + 1 if prev is not None and y == prev + 1 else 1
        best = max(best, run); prev = y
    return best
