#!/usr/bin/env python
"""binding2 source-scout, area "ne" (ME NH VT MA RI CT NY NJ PA DE MD OH).

Reproducible live harvest of NEW public lake-level sources (read-only GETs, <= ~1 req/s per host, no accounts/keys).
Writes under /Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/binding2/:
    cand/ne.jsonl                       one record per (lake, series) that returned live data
    history/<prov>_<station>_<series>.csv.gz   daily values YYYY-MM-DD,value_ft (no header)
    notes/ne.json                       source-evaluation records (written from src_ne_notes.py's NOTES list)
Run:  python src_ne.py [--no-history] [--only prov1,prov2]
Providers: usgs, cwms, nwps, safewaters (Brookfield Safe Waters), nhdes (NHDES RTI Amanzi), njwsa (Manasquan daily ops report).
"""
import sys, os, re, json, gzip, csv, time, argparse, datetime as dt, statistics
sys.path.insert(0, "/Users/mcather/Desktop/Development/Sector_Engine/research/lake-brain/binding")
from common import http_get, get_json
from providers import summarize, year_completeness

B2 = "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/binding2"
CAND = f"{B2}/cand/ne.jsonl"
HISTD = f"{B2}/history"
RAWD = f"{B2}/raw/ne"
for d in (HISTD, RAWD, f"{B2}/cand", f"{B2}/notes"):
    os.makedirs(d, exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc)
FT_PER_M = 3.280839895
UTC = dt.timezone.utc


def iso(t):
    return dt.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_epoch(s):
    """ISO string with offset or Z -> epoch seconds."""
    s = s.replace("Z", "+00:00")
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return d.timestamp()


def daily_mean(points, unit="ft", tz_shift_h=0):
    """points [(epoch_s, v)] -> {YYYY-MM-DD: mean value in ft} (UTC calendar day)."""
    k = FT_PER_M if unit in ("m", "meter", "meters") else 1.0
    acc = {}
    for t, v in points:
        if v is None:
            continue
        day = dt.datetime.fromtimestamp(t + tz_shift_h * 3600, UTC).strftime("%Y-%m-%d")
        a = acc.setdefault(day, [0.0, 0])
        a[0] += v * k
        a[1] += 1
    return {d: round(s / n, 4) for d, (s, n) in acc.items()}


def write_hist(prov, station, series, daily):
    if not daily:
        return None, None, None
    fn = f"{prov}_{station}_{series}.csv.gz".replace("/", "_").replace(":", "_")
    with gzip.open(f"{HISTD}/{fn}", "wt", newline="") as f:
        w = csv.writer(f)
        for k in sorted(daily):
            w.writerow([k, daily[k]])
    yc = year_completeness(daily)
    return f"history/{fn}", [int(min(daily)[:4]), int(max(daily)[:4])], yc


def cached_daily(prov, station, series, fetch, max_age_days=3):
    """Return {date: ft}; reuse the history file written by an earlier run (< max_age_days old) to stay polite."""
    fn = f"{HISTD}/" + f"{prov}_{station}_{series}.csv.gz".replace("/", "_").replace(":", "_")
    if os.path.exists(fn) and time.time() - os.path.getmtime(fn) < max_age_days * 86400:
        return {r[0]: float(r[1]) for r in csv.reader(gzip.open(fn, "rt")) if r}
    return fetch()


CANDS = []


def emit(lakeId, prov, origin, relay, station, stationName, lat, lon, series, unit, family, vdatum, points, apiUrl, pageUrl,
         fullPoolHint=None, daily=None, notes="", window_days=30):
    """points: list of (epoch_s, value) in `unit` (window for the live stats). daily: {date: ft} full history or None."""
    cut = NOW.timestamp() - window_days * 86400
    win = [(t, v) for t, v in points if t >= cut and v is not None]
    s = summarize(win, unit)
    if not s.get("n"):
        print(f"  [skip] {lakeId} {prov}:{station}:{series} no points in last {window_days} d")
        return None
    hp, hy, yc = write_hist(prov, station, series, daily) if daily else (None, None, None)
    rec = {"lakeId": lakeId, "prov": prov, "origin": origin, "relay": relay, "station": station, "stationName": stationName,
           "lat": lat, "lon": lon, "series": series, "unit": "ft", "family": family, "vdatum": vdatum,
           "lastObs": s["last_t"], "ageH": max(0.0, s["age_h"]), "n30": s["n"], "medFt": s["med_ft"], "lastFt": s["last_ft"],
           "fullPoolHint": fullPoolHint, "histPath": hp, "histYears": hy,
           "histCompleteYears": (yc or {}).get("completeYears"), "histMaxConsecutive": (yc or {}).get("maxConsecutive"),
           "apiUrl": apiUrl, "pageUrl": pageUrl, "notes": notes}
    CANDS.append(rec)
    print(f"  [cand] {lakeId:34s} {prov}:{station}:{series} last={s['last_ft']} age={s['age_h']}h n={s['n']} hist={hy} complete={(yc or {}).get('completeYears')}")
    return rec


# =============================================================================================================== USGS
USGS_TARGETS = [
    # lakeId, site, param, vdatum, family, notes
    ("West Grand Lake|ME", "01018900", "62615", "NAVD88", "elev",
     "USGS site datum NAVD88 (alt 0). Reads ~296 ft, directory fullPoolFt (259) looks wrong: lake surface is ~295 ft on USGS topo; "
     "NWPS WGLM1 is a relay of this series. Operator Woodland Pulp/Brookfield dam at Grand Lake Stream."),
    ("Lake Arthur|PA", "03106280", "00062", "unknown", "elev",
     "PA DCNR Moraine SP reservoir; 00062 = 'reservoir water surface elevation above datum' (site datum not listed in the catalog). "
     "Series last reported 2026-10-06 (about 7 d old at test time: sensor outage?)."),
    ("Youghiogheny River Lake|MD", "03077000", "62615", "NAVD88", "elev",
     "USGS site is 'Youghiogheny River Lake at Dam nr Confluence, PA' (dam in PA; lake extends into Garrett Co. MD): wave-1 state-check rejection only. "
     "62615 is NAVD88 by definition; CWMS/USACE series are NGVD29 so expect ~0.3-0.5 ft difference."),
    ("Griffith Lake|DE", "01484143", "62615", "NAVD88", "elev",
     "NEARBY ALTERNATIVE ONLY: 'Haven Lake outlet at Milford DE' (1.8 km from the Griffith Lake polygon); may be a different impoundment. Verify identity."),
]


def usgs_site_meta(site):
    s, b = http_get(f"https://waterservices.usgs.gov/nwis/site/?format=rdb&sites={site}&siteStatus=all", sleep=1.0)
    name, lat, lon, datum = "", None, None, ""
    for ln in b.splitlines():
        if ln.startswith("USGS"):
            p = ln.split("\t")
            name, lat, lon = p[2], float(p[4]), float(p[5])
    return name, lat, lon


def usgs_iv(site, param, start, end):
    u = (f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={site}&parameterCd={param}&startDT={start}&endDT={end}&siteStatus=all")
    s, d = get_json(u, timeout=240, sleep=1.0)
    pts = []
    if d:
        for ts in d["value"]["timeSeries"]:
            nd = ts["variable"].get("noDataValue", -999999)
            for blk in ts["values"]:
                for v in blk["value"]:
                    try:
                        x = float(v["value"])
                    except Exception:
                        continue
                    if x == nd:
                        continue
                    pts.append((to_epoch(v["dateTime"]), x))
    return pts


def usgs_dv(site, param):
    """Daily values: daily mean (stat 00003) preferred, otherwise whatever statistic the site publishes (e.g. 32400 end-of-day, 00001 max)."""
    u = (f"https://waterservices.usgs.gov/nwis/dv/?format=json&sites={site}&parameterCd={param}&startDT=1900-01-01"
         f"&endDT={NOW.strftime('%Y-%m-%d')}&siteStatus=all")
    s, d = get_json(u, timeout=300, sleep=1.0)
    if not d or not any(ts["values"][0]["value"] for ts in d["value"]["timeSeries"] if ts["values"]):
        # some sites only publish a once-a-day observation statistic (e.g. 30800 'Observation at 08:00'), which must be requested explicitly
        s, d = get_json(u + "&statCd=30800", timeout=300, sleep=1.0)
    bystat = {}
    if d:
        for ts in d["value"]["timeSeries"]:
            nd = ts["variable"].get("noDataValue", -999999)
            stat = (ts["variable"].get("options", {}).get("option") or [{}])[0].get("optionCode") or "?"
            for blk in ts["values"]:
                for v in blk["value"]:
                    try:
                        x = float(v["value"])
                    except Exception:
                        continue
                    if x != nd:
                        bystat.setdefault(stat, {})[v["dateTime"][:10]] = x
    out = {}
    for stat in ("00003", "32400", "30800", "00001", "00002", "?"):
        for k, x in bystat.get(stat, {}).items():
            out.setdefault(k, x)
    return out


def usgs_history(site, param):
    daily = usgs_dv(site, param)
    last_dv = max(daily) if daily else None
    first_iv_year = int(last_dv[:4]) if last_dv else 2007
    if not last_dv or last_dv < (NOW - dt.timedelta(days=10)).strftime("%Y-%m-%d"):
        # fill from instantaneous values, one year per request (nwis iv archive begins ~2007-10)
        for y in range(max(2007, first_iv_year), NOW.year + 1):
            p = usgs_iv(site, param, f"{y}-01-01", f"{y}-12-31")
            for k, v in daily_mean(p).items():
                daily.setdefault(k, v)
    return daily


def run_usgs(history=True):
    print("== USGS")
    for lakeId, site, param, vd, fam, notes in USGS_TARGETS:
        name, lat, lon = usgs_site_meta(site)
        pts = usgs_iv(site, param, (NOW - dt.timedelta(days=31)).strftime("%Y-%m-%d"), NOW.strftime("%Y-%m-%d"))
        daily = None
        if history and pts:
            daily = cached_daily("usgs", site, param, lambda: usgs_history(site, param))
        emit(lakeId, "usgs", "usgs", False, site, name, lat, lon, param, "ft", fam, vd, pts,
             f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={site}&parameterCd={param}&period=P30D",
             f"https://waterdata.usgs.gov/monitoring-location/{site}/", None, daily, notes)


HIST_ONLY = [
    # site, param, note  (stale / discontinued series kept as baseline history; no live feed -> not a candidate)
    ("03100500", "00062", "Pymatuning Reservoir at Pymatuning Dam PA (PA/OH). Series stopped 2026-06-04 (sensor/telemetry outage, 4 months stale)."),
    ("01080000", "00065", "Lake Winnipesaukee at Weirs Beach NH: gage height ft, gauge datum 500.00 ft NGVD29 (add 500 for elevation). 1937-2017, ended 2017-09-30. Same lake as NHDES WEIN3."),
    ("01098499", "00062", "Lake Cochituate at Framingham MA, NAVD88 site datum; ended 2024-10-07."),
    ("04279490", "62614", "Lake Bomoseen at outlet near Fair Haven VT, NGVD29; ended 2016-07-19."),
    ("01051620", "62615", "Umbagog Lake at Birch Camp ME/NH, NAVD88; 2014-07..2017-05 only."),
    ("01051705", "62615", "Umbagog Lake near Dead Cambridge inlet, NAVD88; 2014-07..2017-05 only."),
    ("01051715", "62615", "Umbagog Lake near Tyler Cove, NAVD88; 2014-08..2017-05 only."),
    ("04236000", "62614", "Skaneateles Lake at Skaneateles NY (NGVD29); 1967-10..1995-03 only."),
]


def run_histonly(history=True):
    print("== USGS history-only (stale/discontinued lake series)")
    out = []
    for site, param, note in HIST_ONLY:
        d = cached_daily("usgs", site, param, lambda: usgs_history(site, param))
        hp, hy, yc = write_hist("usgs", site, param, d)
        print(f"  [hist-only] {site}:{param} years={hy} complete={(yc or {}).get('completeYears')} lastDay={(yc or {}).get('lastDay')}")
        out.append({"station": site, "param": param, "histPath": hp, "histYears": hy, "yc": yc, "note": note})
    json.dump(out, open(f"{RAWD}/hist_only_summary.json", "w"), indent=1)


# =============================================================================================================== CWMS
CWMS = "https://cwms-data.usace.army.mil/cwms-data"
CWMS_TARGETS = [
    ("Youghiogheny River Lake|MD", "LRP", "Youghiogheny-Lake.Elev.Inst.30Minutes.0.OBS", "NGVD29", "USACE LRP CWMS pool elevation at the dam (Buttonhook). State-check rejection in wave 1 only (dam in PA).", 1470.0),
    ("Youghiogheny River Lake|MD", "LRP", "Youghiogheny-Lake-Rt40.Elev.Inst.30Minutes.0.OBS", "NGVD29", "Same lake, upper end near US-40 (Maryland side of the pool).", None),
    ("Mansfield Hollow Lake|CT", "NAE", "MHD.Elev.Inst.15Minutes.0.DCP-rev", "unknown",
     "Wave-1 R8 failure was only a missing datum. NAE location MHD has elevation 59.439 m (=195.0 ft) = gauge zero; USACE NAE 'Bottom of Normal' stage level is 15.0-18.5 ft "
     "(location-level MHD.Stage-Pool), i.e. normal pool elevation 210.0-213.5 ft, so 211-213 ft is consistent with the conservation pool (NGVD29, NAE convention). "
     "Directory full pool 210 is the winter conservation pool.", 213.5),
]


def cwms_get(office, name, begin, end, unit="EN"):
    pts, page = [], None
    for _ in range(40):
        q = f"{CWMS}/timeseries?name={name}&office={office}&begin={begin}&end={end}&unit={unit}&page-size=100000"
        if page:
            q += f"&page={page}"
        s, d = get_json(q, headers={"Accept": "application/json;version=2"}, timeout=240, sleep=1.0)
        if not d:
            break
        for t, v, *_ in d.get("values", []):
            if v is not None:
                pts.append((t / 1000.0, v))
        page = d.get("next-page")
        if not page:
            break
    return pts


def cwms_history(office, name):
    daily = {}
    for y in range(2000, NOW.year + 1):
        p = cwms_get(office, name, f"{y}-01-01T00:00:00", f"{y}-12-31T23:59:59")
        if p:
            daily.update(daily_mean(p))
    return daily


def cwms_loc(office, loc):
    s, d = get_json(f"{CWMS}/locations/{loc}?office={office}", headers={"Accept": "application/json;version=2"}, sleep=1.0)
    return d or {}


def run_cwms(history=True):
    print("== CWMS")
    for lakeId, office, name, vd, notes, fp in CWMS_TARGETS:
        loc = cwms_loc(office, name.split(".")[0])
        lat, lon, long_name = loc.get("latitude"), loc.get("longitude"), loc.get("long-name") or loc.get("public-name") or name
        begin = (NOW - dt.timedelta(days=31)).strftime("%Y-%m-%dT00:00:00")
        pts = cwms_get(office, name, begin, NOW.strftime("%Y-%m-%dT23:59:59"))
        daily = None
        if history and pts:
            daily = cached_daily("cwms", f"{office}-{name.split('.')[0]}", name.split(".")[1], lambda: cwms_history(office, name))
        emit(lakeId, "cwms", "usace", False, f"{office}-{name.split('.')[0]}", long_name, lat, lon, name.split(".")[1], "ft", "elev", vd, pts,
             f"{CWMS}/timeseries?name={name}&office={office}&begin=<iso>&end=<iso>&unit=EN  (Accept: application/json;version=2)",
             "https://water.usace.army.mil/", fp, daily, notes)


# =============================================================================================================== NWPS
NWPS_TARGETS = [
    ("West Grand Lake|ME", "WGLM1", True, "usgs", "NAVD88", "Relay of USGS 01018900 62615 (pedts HPIRG pool elevation)."),
    ("Youghiogheny River Lake|MD", "YGBP1", True, "usace", "unknown", "Relay of the USACE LRP Youghiogheny-Lake pool elevation (NWS 'Central PA Dams' product, HPIRG)."),
    ("Liberty Reservoir|MD", "MFEM2", False, "nws-marfc-unknown", "unknown",
     "NWS point 'North Branch Patapsco River at Liberty Reservoir' (HGIRR, Howard Co. MD, 0.9 km from the directory point); values ~410-412 ft vs Liberty full pool 420 ft (MD DPW press says "
     "Liberty was drawn down to a ~20-year low in 2026). Source agency not stated by NWPS (no usgsId; likely Baltimore City/County ALERT). Not a documented elevation: verify datum and that "
     "it is the pool and not the North Branch inflow."),
]


def run_nwps():
    print("== NWPS")
    for lakeId, lid, relay, origin, vd, notes in NWPS_TARGETS:
        s, g = get_json(f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}", sleep=1.0)
        s2, d = get_json(f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}/stageflow/observed", sleep=1.0)
        if not g or not d:
            print("  [nwps] failed", lid)
            continue
        pts = [(to_epoch(r["validTime"]), r["primary"]) for r in d["data"] if r.get("primary", -999) not in (-999, None)]
        unit = d.get("primaryUnits", "ft")
        emit(lakeId, "nwps", origin, relay, lid, g["name"], g["latitude"], g["longitude"], g["pedts"]["observed"], unit,
             "elev", vd, pts, f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}/stageflow/observed",
             f"https://water.noaa.gov/gauges/{lid}", None, None, notes)


# =============================================================================================================== Brookfield Safe Waters
SW_TARGETS = [
    # lakeId, facility slug, which 'ft' item index, notes
    ("Lake Wallenpaupack|PA", "wallenpaupack", "Lake level published by Brookfield (PPL) as feet above sea level; matches the operator's 2026 drawdown schedule (target 1174.0-1174.5 ft for the week of 10/4; normal max about 1187 ft)."),
    ("Moosehead Lake|ME", "moosehead-east-west-outlet", "Moosehead East & West Outlet (Brookfield/Kennebec Hydro). Normal maximum is about 1,029 ft."),
    ("Flagstaff Lake|ME", "flagstaff", "Flagstaff Lake (Long Falls Dam, Dead River), Brookfield; full pool 1,145 ft."),
    ("Rangeley Lake|ME", "rangeley", "Rangeley Lake outlet dam (Brookfield)."),
    ("Mooselookmeguntic Lake|ME", "upper-dam", "Upper Dam, outlet of Mooselookmeguntic Lake (Brookfield)."),
    ("Umbagog Lake|NH", "errol", "Errol dam (Brookfield, Union Water Power) impounds Umbagog Lake; Safe Waters 'Errol' pond level."),
]


def run_safewaters():
    print("== Safe Waters (Brookfield)")
    for lakeId, slug, notes in SW_TARGETS:
        url = f"https://www.safewaters.com/facility/{slug}/"
        s, b = http_get(url, sleep=1.2)
        raw = f"{RAWD}/sw_{slug}.html"
        open(raw, "w").write(b)
        nm = re.search(r"<h1>([^<]*)</h1>", b)
        loc = re.search(r"<p>(Near[^<]*)</p>", b)
        m = re.search(r"<h5>\s*(-?[\d.]+)\s*ft as of (\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}:\d{2} [AP]M) \((E[SD]T)\)", b)
        if not m:
            print("  [sw] no ft value for", slug)
            continue
        off = -4 if m.group(3) == "EDT" else -5
        t = dt.datetime.strptime(m.group(2), "%Y-%m-%d %I:%M:%S %p").replace(tzinfo=dt.timezone(dt.timedelta(hours=off)))
        emit(lakeId, "safewaters", "brookfield", False, slug, (nm.group(1) if nm else slug).replace("&#8211;", "-").replace("&#038;", "&") + " | " + (loc.group(1) if loc else ""),
             None, None, "pond-elevation", "ft", "elev", "unknown", [(t.timestamp(), float(m.group(1)))],
             url, url, None, None,
             notes + " Safe Waters shows only the latest value (no history API, no chart data in the page): the series must be accumulated by polling. "
                     "Vertical datum not stated (feet above sea level; operator datum, probably NGVD29).", window_days=30)


# =============================================================================================================== NHDES RTI Amanzi
RTI = "https://nhdes.rtiamanzi.org/api"
NH_TARGETS = [
    ("Lake Winnipesaukee|NH", "WEIN3"), ("Squam Lake|NH", "SQLNH"), ("Sunapee Lake|NH", "SUNNH"),
    ("Newfound Lake|NH", "NFLNH"), ("Lake Winnisquam|NH", "LWINH"), ("Ossipee Lake|NH", "OSLNH"), ("Ossipee Lake|NH", "OSDNH"),
    ("Great East Lake|NH", "GELNH"), ("First Connecticut Lake|NH", "LFRNH"),
]
NH_NOTES = {
    "LFRNH": "MISMATCH WARNING: station is 'Murphy Dam (Lake Francis)', the NHDES dam that impounds Lake Francis (Pittsburg NH), NOT First Connecticut Lake (impounded by a Great River Hydro dam). "
             "Directory operator text conflates them. Listed as nearby alternative only.",
    "OSDNH": "Ossipee Dam gauge (lake side), same lake level as OSLNH within ~0.2 ft.",
}


def run_nhdes(history=True, directory_names=None):
    print("== NHDES RTI")
    s, locs = get_json(f"{RTI}/locations/?layer__code=STATIONS", sleep=1.0)
    byc = {f["properties"]["code"]: f for f in locs["features"]}
    json.dump(locs, open(f"{RAWD}/rti_locations.json", "w"))
    cache = {}
    for lakeId, code in NH_TARGETS:
        f = byc.get(code)
        if not f:
            print("  [rti] missing", code)
            continue
        if code not in cache:
            s, ts = get_json(f"{RTI}/timeseries/?location__code={code}&parameter__code=PELV&format=json", sleep=1.0)
            cache[code] = ts or []
        for t in cache[code]:
            if t["entry_type"]["code"] == "MAN" or t["interval"] != "PT1H":
                continue
            tid = t["id"]
            start = (NOW - dt.timedelta(days=31)).strftime("%Y-%m-%dT00:00:00Z")
            s, vals = get_json(f"{RTI}/timeseries/{tid}/values/?start={start}&end={NOW.strftime('%Y-%m-%dT23:59:59Z')}", sleep=1.0)
            pts = [(to_epoch(v["datetime"]), v["num_value"]) for v in (vals or []) if v.get("num_value") is not None]
            props = f["properties"]
            datum = next((x["char_value"] for x in props["fields"] if x["attribute_name"]["code"] == "DATUM_TEXT"), "") or ""
            m = re.search(r"Local\s*=\s*([\d.]+)", datum)
            fp = float(m.group(1)) if m else None
            vd = "NGVD29" if "NGVD" in datum.upper() else "unknown"
            lat, lon = f["geometry"]["coordinates"][0][1], f["geometry"]["coordinates"][0][0]
            daily = None
            if history and pts:
                def _fetch(tid=tid):
                    dd = {}
                    for y in range(2009, NOW.year + 1):
                        s_, yv = get_json(f"{RTI}/timeseries/{tid}/values/?start={y}-01-01T00:00:00Z&end={y}-12-31T23:59:59Z", timeout=300, sleep=1.0)
                        if yv:
                            dd.update(daily_mean([(to_epoch(v["datetime"]), v["num_value"]) for v in yv if v.get("num_value") is not None]))
                    return dd
                daily = cached_daily("nhdes", code, "PELV.PT1H", _fetch)
            note = (f"NHDES Dam Bureau real-time station (hourly, NHDES-operated telemetry, provisional). DATUM_TEXT: '{datum}'. "
                    f"Feet above sea level, directly comparable with the NHDES full-lake elevation. " + NH_NOTES.get(code, ""))
            emit(lakeId, "nhdes", "nhdes", False, code, props["name"], round(lat, 5), round(lon, 5), "PELV.PT1H", "ft", "elev", vd, pts,
                 f"{RTI}/timeseries/{tid}/values/?start=<iso>&end=<iso>   (tid from {RTI}/timeseries/?location__code={code}&parameter__code=PELV)",
                 "https://nhdes.rtiamanzi.org/", fp, daily, note)


# =============================================================================================================== NJWSA Manasquan
def run_njwsa():
    print("== NJWSA Manasquan")
    url = "https://www.njwsa.org/manasquan-operations-data.html"
    s, b = http_get(url, sleep=1.0)
    open(f"{RAWD}/njwsa_manasquan.html", "w").write(b)
    t = re.sub(r"<[^>]+>", "\n", b).replace("&rsquo;", "'").replace("&rdquo;", '"').replace("&nbsp;", " ")
    t = re.sub(r"\n\s*\n+", "\n", t)
    pts = []
    for m in re.finditer(r"Manasquan Reservoir - (\d+)/(\d+)/(\d{4})\s*\n.*?Elevation - ([\d.]+)", t, re.S):
        d = dt.datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)), 12, tzinfo=dt.timezone(dt.timedelta(hours=-4)))
        pts.append((d.timestamp(), float(m.group(4))))
    emit("Manasquan Reservoir|NJ", "njwsa", "njwsa", False, "manasquan-ops", "Manasquan Reservoir (NJWSA operations report)", 40.16, -74.14,
         "daily-elevation", "ft", "elev", "unknown", pts, url, url, 100.0, None,
         "NJ Water Supply Authority daily operations report: last 5 daily elevations (noon stamp assumed), plus monthly average (Sept 2026 97.48 ft). Page keeps only the current month; "
         "history must be accumulated. Datum not stated (project full pool is 100 ft). Report is updated on business days (age is up to ~5 d on weekends/holidays).")


def run_mwra():
    """MWRA publishes MONTHLY (1st-of-month) Quabbin/Wachusett elevations - not live; saved to raw/ne/mwra_*_monthly.csv for reference only."""
    print("== MWRA monthly reservoir levels (reference only, not a live candidate)")
    s, b = http_get("https://www.mwra.com/node/2411", sleep=1.0)
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", b, flags=re.S)
    t = re.sub(r"<[^>]+>", "\n", t).replace("&nbsp;", " ")
    t = re.sub(r"\n\s*\n+", "\n", t)
    i1, i2, i3 = t.rindex("Quabbin Reservoir Levels Archive"), t.rindex("Wachusett Reservoir Levels Archive"), t.rindex("Precipitation Levels Archive")
    sec = {"quabbin": t[i1:i2], "wachusett": t[i2:i3]}
    for name, key in (("quabbin", "Quabbin Reservoir Levels"), ("wachusett", "Wachusett Reservoir Levels")):
        rows = {}
        for m in re.finditer(r"\n(\d{2})/01/(\d{2})\n([\d.]+)\n([\d,]+)\n([\d.]+)", sec[name]):
            rows[f"{2000 + int(m.group(2)) if int(m.group(2)) < 70 else 1900 + int(m.group(2))}-{m.group(1)}-01"] = float(m.group(3))
        with open(f"{RAWD}/mwra_{name}_monthly.csv", "w") as f:
            for k in sorted(rows):
                f.write(f"{k},{rows[k]}\n")
        last = max(rows) if rows else None
        print(f"  {name}: {len(rows)} monthly values, last {last} = {rows.get(last)} ft")


def pdf_text_fragments(b):
    """Minimal text extraction (FlateDecode streams, Tj/TJ operators) - enough for the NJWSA operations report; PDF content is treated as data only."""
    import zlib
    frags = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", b, re.S):
        try:
            d = zlib.decompress(m.group(1))
        except Exception:
            continue
        for a, c in re.findall(rb"\[(.*?)\]\s*TJ|\((.*?)\)\s*Tj", d, re.S):
            frags.append((b"".join(re.findall(rb"\((.*?)(?<!\\)\)", a, re.S)) if a else c).decode("latin1"))
    return frags


def run_njwsa_raritan():
    print("== NJWSA Raritan (Round Valley) operations report PDF")
    url = "https://www.njwsa.org/uploads/1/0/8/0/108064771/data.pdf"
    s, b = http_get(url, binary=True, sleep=1.0)
    if s != 200:
        print("  pdf status", s)
        return
    open(f"{RAWD}/njwsa_raritan_data.pdf", "wb").write(b)
    t = " ".join(f.strip() for f in pdf_text_fragments(b))
    t = re.sub(r"\s+", " ", t)
    m = re.search(r"Current as of: ([\d:]+ [ap]\.m\.)\s*([A-Za-z]+, [A-Za-z]+ \d+, \d{4})", t)
    seg = t[t.index("Round Valley Reservoir"):] if "Round Valley Reservoir" in t else ""
    seg = seg[: seg.index("Full pool")] if "Full pool" in seg else seg
    pts = []
    for mm in re.finditer(r"(\d{1,2})/(\d{1,2})/(\d{2}) (3\d\d\.\d\d)", seg):
        d = dt.datetime(2000 + int(mm.group(3)), int(mm.group(1)), int(mm.group(2)), 7, 30, tzinfo=dt.timezone(dt.timedelta(hours=-4)))
        pts.append((d.timestamp(), float(mm.group(4))))
    emit("Round Valley Reservoir|NJ", "njwsa", "njwsa", False, "raritan-ops-pdf", "Round Valley Reservoir (NJWSA Delaware & Raritan System Operations Report)", 40.62, -74.84,
         "daily-elevation", "ft", "elev", "NAVD88", pts, url, "https://www.njwsa.org/raritan-operations-data.html", 384.20, None,
         f"Weekday PDF report ('Current as of: {m.group(1)+' '+m.group(2) if m else '?'}'); last 6-7 daily Round Valley elevations (07:30 EDT stamp assumed). Datum NAVD88 since 2025-11-19 "
         "(NGVD29 = NAVD88 + 0.8 before that - published on the report); published full pool 384.20 ft NAVD88. No archive online: history must be accumulated (or requested from NJWSA). "
         "Same PDF also carries Spruce Run Reservoir (full pool 272.20 NAVD88).")


# =============================================================================================================== main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-history", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    only = set(filter(None, a.only.split(",")))
    hist = not a.no_history
    steps = [("usgs", lambda: run_usgs(hist)), ("histonly", lambda: run_histonly(hist)), ("cwms", lambda: run_cwms(hist)), ("nwps", run_nwps), ("safewaters", run_safewaters),
             ("nhdes", lambda: run_nhdes(hist)), ("mwra", run_mwra), ("njwsa", lambda: (run_njwsa(), run_njwsa_raritan()))]
    allc = []
    for k, fn in steps:
        part = f"{RAWD}/cand_part_{k}.json"
        if not only or k in only:
            CANDS.clear()
            fn()
            json.dump(CANDS, open(part, "w"))
        if os.path.exists(part):
            allc.extend(json.load(open(part)))
    with open(CAND, "w") as f:
        for r in allc:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(allc)} candidates -> {CAND}")
    try:
        from src_ne_notes import NOTES
        json.dump(NOTES, open(f"{B2}/notes/ne.json", "w"), indent=1)
        print(f"wrote {len(NOTES)} notes")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
