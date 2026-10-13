#!/usr/bin/env python
"""binding2 source scout, area "mw" (upper Midwest, Plains, Great Lakes).

Regenerates, under /Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/binding2/:
  cand/mw.jsonl                    one record per (lake, series) that answered in a live test
  history/<prov>_<station>_<series>.csv.gz   daily values  YYYY-MM-DD,value_ft  (no header)
  notes/mw_series_check.json       per-series raw test results (machine log)
(notes/mw.json, the human source-evaluation list, is maintained separately in notes_mw.py.)

Read-only HTTP GETs only, <= ~1 request/second per host, no accounts/keys. Never writes outside binding2/.
Usage:  python src_mw.py [section ...]    sections: coops usgs cwms eccc nwps web mndnr   (default: all)
"""
import sys, os, json, gzip, csv, re, time, math, statistics, datetime as dt, urllib.parse, io
sys.path.insert(0, "/Users/mcather/Desktop/Development/Sector_Engine/research/lake-brain/binding")
from common import http_get, get_json, haversine_m, name_sim          # noqa: E402
from providers import summarize, year_completeness, FT_PER_M  # noqa: E402

B2 = "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/binding2"
CAND = f"{B2}/cand/mw.jsonl"
HIST = f"{B2}/history"
NOTES = f"{B2}/notes"
for d in (f"{B2}/cand", HIST, NOTES):
    os.makedirs(d, exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc)
PROFILE = {l["lakeId"]: l for l in json.load(open(f"{B2}/unbound_profile.json"))}

# --------------------------------------------------------------------------- polite HTTP
_last = {}


def get(url, headers=None, timeout=120, retries=3):
    host = urllib.parse.urlparse(url).netloc
    wait = 1.0 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    r = http_get(url, headers, timeout=timeout, retries=retries, sleep=0)
    _last[host] = time.time()
    return r


def gjson(url, headers=None, **kw):
    s, b = get(url, headers, **kw)
    if s != 200:
        return s, None
    try:
        return s, json.loads(b)
    except Exception:
        return s, None


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def epoch(s):
    s = s.replace("Z", "+00:00")
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.timestamp()


# --------------------------------------------------------------------------- outputs
RECORDS = []
LOG = []


def daily_from_pts(pts):
    by = {}
    for t, v in pts:
        by.setdefault(dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"), []).append(v)
    return {k: sum(v) / len(v) for k, v in by.items()}


def clean_daily(daily, elev=True):
    """Drop obvious junk from long archives: isolated first points separated by a >1-year gap, and (for elevation series)
    values far from the series median (e.g. 1.22 ft / 57 ft readings during reservoir filling or unit mix-ups)."""
    if not daily:
        return daily
    ks = sorted(daily)
    while len(ks) > 2 and (dt.date.fromisoformat(ks[1]) - dt.date.fromisoformat(ks[0])).days > 400:
        daily.pop(ks.pop(0))
    if elev:
        med = statistics.median(daily.values())
        if med > 100:
            for k in [k for k, v in daily.items() if v < 0.6 * med or v > 1.4 * med]:
                daily.pop(k)
    return daily


def write_hist(name, daily):
    p = f"{HIST}/{name}.csv.gz"
    with gzip.open(p, "wt", newline="") as f:
        w = csv.writer(f)
        for k in sorted(daily):
            w.writerow([k, round(daily[k], 4)])
    return f"history/{name}.csv.gz"


def safe(s):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(s))[:90]


def emit(lakes, prov, origin, station, stationName, lat, lon, series, family, vdatum, live_pts, apiUrl, pageUrl, notes="",
         relay=False, fullPoolHint=None, daily=None, unit_k=1.0, extra=None, live_only=False):
    """live_pts: [(epoch, value_ft)]; daily: {date: value_ft} history (optional)."""
    sm = summarize(live_pts) if live_pts else dict(n=0)
    if not sm.get("n"):
        LOG.append(dict(lakes=lakes, prov=prov, station=station, series=series, result="no-data-in-window"))
        return False
    last_t = max(t for t, _ in live_pts)
    tnow = time.time()          # fresh clock (the run takes ~15 min; NOW is the import time)
    n30 = len([1 for t, _ in live_pts if t >= tnow - 30 * 86400])
    histPath, histYears, hc = None, None, None
    if daily:
        histPath = write_hist(f"{prov}_{safe(station)}_{safe(series)}", daily)
        ys = sorted(int(k[:4]) for k in daily)
        histYears = [ys[0], ys[-1]]
        hc = year_completeness(daily)["completeYears"]
    for lk in lakes:
        rec = {"lakeId": lk, "prov": prov, "origin": origin, "relay": relay, "station": str(station), "stationName": stationName,
               "lat": lat, "lon": lon, "series": series, "unit": "ft", "family": family, "vdatum": vdatum,
               "lastObs": iso(last_t), "ageH": round((tnow - last_t) / 3600, 1), "n30": n30, "medFt": sm["med_ft"],
               "lastFt": sm["last_ft"], "fullPoolHint": fullPoolHint, "histPath": histPath, "histYears": histYears,
               "apiUrl": apiUrl, "pageUrl": pageUrl, "notes": notes, "live": (tnow - last_t) <= 72 * 3600,
               "histCompleteYears": hc}
        p = PROFILE.get(lk)
        if p and lat is not None:
            rec["distKm"] = round(haversine_m(p["lat"], p["lon"], lat, lon) / 1000, 1)
        if extra:
            rec.update(extra)
        RECORDS.append(rec)
    return True


# --------------------------------------------------------------------------- NOAA CO-OPS (Great Lakes)
COOPS = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
CO_META = {}


def coops_meta():
    if not CO_META:
        s, d = gjson("https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=waterlevels")
        for st in (d or {}).get("stations", []):
            if st.get("greatlakes"):
                CO_META[st["id"]] = st
    return CO_META


def coops_daily(station, y0, y1):
    """daily_mean (IGLD, ft) in 9-year chunks. Returns {date: ft}."""
    out = {}
    y = y0
    while y <= y1:
        e = min(y + 8, y1)
        url = (f"{COOPS}?product=daily_mean&application=SectorEngineResearch&station={station}&begin_date={y}0101&end_date={e}1231"
               f"&datum=IGLD&units=english&time_zone=gmt&format=json")
        s, d = gjson(url)
        for r in (d or {}).get("data", []):
            try:
                out[r["t"][:10]] = float(r["v"])
            except Exception:
                pass
        y = e + 1
    return out


def coops_live(station, days=30):
    b = (NOW - dt.timedelta(days=days)).strftime("%Y%m%d %H:%M"); e = NOW.strftime("%Y%m%d %H:%M")
    url = (f"{COOPS}?product=water_level&application=SectorEngineResearch&station={station}&begin_date={urllib.parse.quote(b)}"
           f"&end_date={urllib.parse.quote(e)}&datum=IGLD&units=english&time_zone=gmt&format=json")
    s, d = gjson(url, timeout=180)
    pts = []
    for r in (d or {}).get("data", []):
        try:
            pts.append((dt.datetime.strptime(r["t"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp(), float(r["v"])))
        except Exception:
            pass
    return pts


# lake directory entry -> list of CO-OPS station ids (nearest-first, state-local where one exists)
GL_STATIONS = {
    "Lake Erie|MI": ["9063090", "9063085"],              # Fermi Power Plant (MI), Toledo (OH, Maumee Bay)
    "Lake Erie|OH": ["9063079", "9063063", "9063053", "9063085"],   # Marblehead, Cleveland, Fairport, Toledo
    "Lake Erie|PA": ["9063038"],                         # Erie
    "Lake Erie|NY": ["9063020", "9063028"],              # Buffalo, Sturgeon Point
    "Lake Ontario|NY": ["9052058", "9052076", "9052030"],  # Rochester, Olcott, Oswego
    "Lake Michigan|IN": ["9087044"],                     # Calumet Harbor IL (no CO-OPS station in IN)
    "Lake Michigan|MI": ["9087023", "9087031", "9087096"],  # Ludington, Holland, Port Inland
    "Lake Michigan|WI": ["9087057", "9087068", "9087072"],  # Milwaukee, Kewaunee, Sturgeon Bay Canal
    "Green Bay|WI": ["9087077", "9087072", "9087088"],    # Green Bay East, Sturgeon Bay Canal, Menominee (MI)
    "Lake Huron|MI": ["9075014", "9075065", "9075035", "9075080"],  # Harbor Beach, Alpena, Essexville (Saginaw Bay), Mackinaw City
    "Lake Superior|MI": ["9099018", "9099044", "9099004"],  # Marquette, Ontonagon, Point Iroquois
    "Lake Superior|MN": ["9099064", "9099090"],          # Duluth, Grand Marais
    "Lake Superior|WI": ["9099044", "9099064"],          # no WI station: Ontonagon MI (nearest), Duluth MN
}
GL_LAKEWIDE = {   # USACE LRE coordinating-committee lake-wide mean levels (relay of the binational gauge network)
    "Lake Erie": ("ErieLake", ["Lake Erie|MI", "Lake Erie|OH", "Lake Erie|PA", "Lake Erie|NY"]),
    "Lake Ontario": ("OntarioLake", ["Lake Ontario|NY"]),
    "Lake Superior": ("SuperiorLake", ["Lake Superior|MI", "Lake Superior|MN", "Lake Superior|WI"]),
    "Lake Michigan-Huron": ("MichHuronLake", ["Lake Michigan|IN", "Lake Michigan|MI", "Lake Michigan|WI", "Green Bay|WI", "Lake Huron|MI"]),
}


def run_coops():
    meta = coops_meta()
    done = {}
    for lk, sts in GL_STATIONS.items():
        for sid in sts:
            m = meta.get(sid)
            if not m:
                LOG.append(dict(lake=lk, station=sid, result="not-in-metadata"))
                continue
            if sid not in done:
                pts = coops_live(sid)
                done[sid] = [pts, None]
                if pts:
                    # first year with data from monthly_mean
                    s, d = gjson(f"{COOPS}?product=monthly_mean&application=SectorEngineResearch&station={sid}&begin_date=18500101&end_date={NOW.strftime('%Y%m%d')}"
                                 f"&datum=IGLD&units=english&time_zone=gmt&format=json")
                    yrs = [int(r["year"]) for r in (d or {}).get("data", [])]
                    y0 = max(min(yrs) if yrs else 2000, 1900)
                    done[sid][1] = coops_daily(sid, y0, NOW.year)
            pts, daily = done[sid]
            dist = haversine_m(PROFILE[lk]["lat"], PROFILE[lk]["lon"], float(m["lat"]), float(m["lng"])) / 1000
            note = (f"NOAA CO-OPS NWLON Great Lakes gauge, water level above IGLD85, 6-min. Directory point is {dist:.0f} km away "
                    f"(station state {m['state']}; lake directory has no polygon). Great Lakes have no 'full pool': levels are the natural lake level; "
                    f"CO-OPS publishes Great Lakes Low Water Datum (chart datum) separately via mdapi datums. Daily-mean history via product=daily_mean datum=IGLD; "
                    f"older years only where the digital archive exists (monthly_mean reaches back further but is not daily).")
            emit([lk], "coops", "noaa-coops", sid, m["name"], float(m["lat"]), float(m["lng"]), "water_level_IGLD85", "elev", "IGLD85", pts,
                 f"{COOPS}?product=water_level&station={sid}&date=latest&datum=IGLD&units=english&time_zone=gmt&format=json (begin/end for windows; daily_mean for history)",
                 f"https://tidesandcurrents.noaa.gov/stationhome.html?id={sid}", note, relay=False, fullPoolHint=None, daily=daily,
                 extra={"stationState": m["state"]})
    # lake-wide means
    H = {"Accept": "application/json;version=2"}
    for lakename, (base, lids) in GL_LAKEWIDE.items():
        nm = f"{base}.Stage.Ave.1Day.1Day.gpl-ccp"
        b = (NOW - dt.timedelta(days=45)).strftime("%Y-%m-%dT%H:%M:%SZ"); e = (NOW + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        q = urllib.parse.urlencode({"name": nm, "office": "LRE", "begin": b, "end": e, "unit": "EN", "page-size": 1000})
        s, d = gjson("https://cwms-data.usace.army.mil/cwms-data/timeseries?" + q, H)
        pts = [(v[0] / 1000.0, v[1]) for v in (d or {}).get("values", []) if v[1] is not None]
        # history: whole available record
        q2 = urllib.parse.urlencode({"name": nm, "office": "LRE", "begin": "1900-01-01T00:00:00Z", "end": e, "unit": "EN", "page-size": 100000})
        s2, d2 = gjson("https://cwms-data.usace.army.mil/cwms-data/timeseries?" + q2, H, timeout=180)
        hp = [(v[0] / 1000.0, v[1]) for v in (d2 or {}).get("values", []) if v[1] is not None]
        s3, loc = gjson(f"https://cwms-data.usace.army.mil/cwms-data/locations/{base}?office=LRE", H)
        emit(lids, "cwms-lre", "great-lakes-coordinating-committee", base, f"{lakename} lake-wide mean level (CWMS LRE {nm})",
             (loc or {}).get("latitude"), (loc or {}).get("longitude"), nm, "elev", "IGLD85", pts,
             f"https://cwms-data.usace.army.mil/cwms-data/timeseries?name={nm}&office=LRE&begin=..&end=..&unit=EN",
             "https://www.lre.usace.army.mil/Missions/Great-Lakes-Information/Great-Lakes-Water-Levels/",
             f"Lake-WIDE daily mean level (average of the binational gauge network, Coordinating Committee), not a point gauge; use as lake-level proxy when the "
             f"directory state has no gauge (e.g. Lake Superior WI, Lake Michigan IN). CWMS time-zone US/Eastern, units converted to ft. Publication lags ~4-5 days.",
             relay=True, daily=daily_from_pts(hp) if hp else None)


# --------------------------------------------------------------------------- USGS
NWIS = "https://waterservices.usgs.gov/nwis"


def usgs_site_info(site):
    s, b = get(f"{NWIS}/site/?format=rdb&sites={site}&siteOutput=expanded&siteStatus=all")
    rows = [x.split("\t") for x in (b or "").splitlines() if x and not x.startswith("#")]
    if len(rows) < 3:
        return {}
    h = rows[0]
    r = rows[2]
    return dict(zip(h, r))


def usgs_live(site, param, days=30):
    s, d = gjson(f"{NWIS}/iv/?format=json&sites={site}&parameterCd={param}&period=P{days}D&siteStatus=all", timeout=180)
    pts, info = [], {}
    for ts in (d or {}).get("value", {}).get("timeSeries", []):
        info = dict(name=ts["sourceInfo"]["siteName"], lat=ts["sourceInfo"]["geoLocation"]["geogLocation"]["latitude"],
                    lon=ts["sourceInfo"]["geoLocation"]["geogLocation"]["longitude"])
        nd = ts["variable"].get("noDataValue", -999999)
        for blk in ts["values"]:
            for v in blk["value"]:
                try:
                    x = float(v["value"])
                except Exception:
                    continue
                if x == nd:
                    continue
                pts.append((epoch(v["dateTime"]), x))
    return pts, info


def usgs_dv_hist(site, param):
    s, d = gjson(f"{NWIS}/dv/?format=json&sites={site}&parameterCd={param}&startDT=1900-01-01&endDT={NOW.strftime('%Y-%m-%d')}&siteStatus=all", timeout=300)
    if not d:
        return None
    by = {}
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
                by.setdefault(stat, {})[v["dateTime"][:10]] = x
    merged = {}
    for stat in ["00003", "30800", "32400", "00001", "00002"] + [k for k in by if k not in ("00003", "30800", "32400", "00001", "00002")]:
        for k, x in by.get(stat, {}).items():
            merged.setdefault(k, x)
    return merged


# (lakeIds, site, live param, family, vdatum, fullPool, notes, hist_param, hist_offset)
USGS = [
    (["Houghton Lake|MI"], "442400084472801", "62615", "elev", "NAVD88", None,
     "USGS publishes 62615 'lake or reservoir water surface elevation above specific vertical datum' (NAVD88) for this site, in addition to gage height 00065. Wave 1 only saw 00065 (8 ft, local). "
     "Gage datum = 1129.61 ft NAVD88 (USGS site altitude); history is daily-mean gage height (00065) + 1129.61, offset validated against the live 62615 series.", "00065", "auto"),
    (["Clinton Lake|IL"], "05578300", "00065", "elev", "unknown", 690.0,
     "USGS gage height reads 689.72 ft = absolute lake-surface elevation (gage datum 0; site altitude -0.18 NAVD88 listed). Clinton Lake normal pool 690 ft (Clinton Power Station cooling lake). Vertical datum not stated by USGS (NGVD29/NAVD88 differ by <0.2 ft here).", "00065", None),
    (["Lake Minnetonka|MN"], "05289000", "00065", "elev", "unknown", 929.4,
     "Lake Minnetonka above Gray's Bay outlet. Gage height reads 928.25 = absolute elevation (gage datum 0). Full pool 929.4 (MCWD/DNR OHW). Agrees with NWPS MTKM5 (relay) to 0.01 ft.", "00065", None),
    (["Longview Lake|MO"], "06893791", "00065", "elev", "unknown", 891.0,
     "Longview Reservoir (Jackson County). Gage height reads 891.22 = absolute elevation (gage datum 0); full pool 891. 4.4 km from directory point (dam vs lake centroid). Agrees with A2W NWK:LGVM and CWMS NWDM LGVM.", "00065", None),
    (["Big Green Lake|WI"], "434840089000001", "00065", "stage", "local", None,
     "Green Lake at Green Lake WI, stage in feet above gage zero. USGS lists site altitude 790.13 ft NAVD88 (gage-datum candidate). stage+790.13 = 796.7 (directory full pool 795): NOT verified, do not use as absolute without WDNR confirmation.", "00065", None),
    (["Chain O'Lakes|IL"], "05547500", "00065", "stage", "local", 737.0,
     "Fox Lake near Lake Villa IL (Chain O'Lakes, Fox River, regulated by Stratton Dam). Stage 4.13 ft + USGS gage datum 732.77 ft NAVD88 = 736.90 (directory 737): consistent but offset is USGS site altitude not an explicit gage datum.", "00065", None),
    (["Chain O'Lakes|IL"], "05547000", "00065", "stage", "local", 737.0,
     "Channel Lake near Antioch IL (Chain O'Lakes). Stage 4.25 + site altitude 732.70 = 736.95.", "00065", None),
    (["Chain O'Lakes|IL"], "05548000", "00065", "stage", "local", 737.0,
     "Nippersink Lake at Fox Lake IL (Chain O'Lakes). Stage 4.10 + site altitude 732.77 = 736.87.", "00065", None),
    (["East Okoboji|IA"], "06604200", "00065", "stage", "local", None,
     "West Okoboji Lake at Lakeside Lab (sibling of East Okoboji; the East Okoboji gauge 06604110 reports nothing in the last 30 d). Stage ft above gage zero; USGS site altitude 1391.65 NAVD88 (not verified as gage datum). Iowa Great Lakes level differs between West and East by a few tenths.", "00065", None),
    (["East Okoboji|IA"], "06604000", "00065", "stage", "local", None,
     "Spirit Lake near Orleans IA (adjacent lake in the same chain; site altitude 1387.28 NAVD88). Stage in ft above gage zero.", "00065", None),
    (["Burt Lake|MI"], "04129950", "62615", "elev", "NAVD88", 594.0,
     "SIBLING, NOT Burt Lake: Mullett Lake at outlet near Cheboygan (Inland Waterway, 19 km from Burt Lake directory point). 62615 lake-surface elevation NAVD88 = 593.14 ft. Burt Lake is upstream via Indian River and runs ~0.5-1 ft higher.", "62615", None),
]


def run_usgs():
    for lakes, site, param, fam, vd, fp, notes, hparam, hoff in USGS:
        pts, info = usgs_live(site, param)
        if not pts:
            LOG.append(dict(lakes=lakes, prov="usgs", station=site, series=param, result="no-live-data"))
            continue
        daily = None
        extra = {}
        si = usgs_site_info(site)
        if si.get("alt_va"):
            extra["siteAltFt"] = si["alt_va"]; extra["siteAltDatum"] = si.get("alt_datum_cd")
        hist = usgs_dv_hist(site, hparam or param)
        if hist:
            if hoff == "auto":
                s2, d2 = None, None
                # align live 62615 with daily mean of live 00065 on the same days
                p65, _ = usgs_live(site, "00065")
                d65, d62 = daily_from_pts(p65), daily_from_pts(pts)
                diffs = [d62[k] - d65[k] for k in d65 if k in d62]
                off = round(statistics.median(diffs), 2) if diffs else None
                extra["histOffsetFt"] = off
                extra["histOffsetSpread"] = round(max(diffs) - min(diffs), 3) if diffs else None
                hist = {k: v + off for k, v in hist.items()} if off is not None else None
            elif hoff:
                hist = {k: v + hoff for k, v in hist.items()}
            daily = hist
        emit(lakes, "usgs", "usgs", site, info["name"], info["lat"], info["lon"], param, fam, vd, pts,
             f"{NWIS}/iv/?format=json&sites={site}&parameterCd={param}&period=P30D&siteStatus=all (dv for history)",
             f"https://waterdata.usgs.gov/monitoring-location/{site}/", notes, relay=False, fullPoolHint=fp, daily=daily, extra=extra)


# --------------------------------------------------------------------------- USACE CWMS
CWMS = "https://cwms-data.usace.army.mil/cwms-data"
CH = {"Accept": "application/json;version=2"}


def cwms_pull(office, name, begin, end=None, unit="EN"):
    end = end or (NOW + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    pts, page, info = [], None, {}
    for _ in range(40):
        q = dict(name=name, office=office, begin=begin, end=end, unit=unit, **{"page-size": 100000})
        if page:
            q["page"] = page
        s, d = gjson(CWMS + "/timeseries?" + urllib.parse.urlencode(q), CH, timeout=240)
        if d is None:
            break
        info = {k: d.get(k) for k in ("units", "interval", "vertical-datum-info", "total")}
        pts += [(v[0] / 1000.0, v[1]) for v in d.get("values", []) if v[1] is not None]
        page = d.get("next-page")
        if not page:
            break
    return pts, info


# (lakeIds, office, series name, location id, family, fullPool, notes)
CWMS_S = [
    (["Lake Sakakawea|ND"], "NWDM", "GARR.Elev.Inst.1Hour.0.Best-MRBWM", "GARR", "elev", 1837.5,
     "Garrison Dam & Reservoir pool elevation (native datum NGVD29, NAVD88 offset +1.311 ft estimated), USACE Omaha District Missouri River Basin Water Management. Wave 1 rejected only on a name rule; strong full-pool match (1824 vs 1837.5 = normal annual pool 1837.5, flood pool 1850). Distinct from Lake Audubon (LAUD, 1846 ft) which is the small separate pool at the dam."),
    (["Lake Oahe|ND"], "NWDM", "OAHE.Elev.Inst.1Hour.0.Best-MRBWM", "OAHE", "elev", 1607.5,
     "Oahe Dam & Reservoir pool elevation (NGVD29), USACE Omaha District MRBWM. Reservoir extends from Pierre SD to Bismarck ND; the directory point (46.2,-100.6) is inside the reservoir. The wave-1 candidates for Oahe (Lake Pocasse, Schmidt gauge) were not the main pool."),
    (["Marion Reservoir|KS"], "SWT", "MARI.Elev.Inst.1Hour.0.Ccp-Rev", "MARI", "elev", 1350.5,
     "Marion Reservoir pool elevation NAVD88, USACE Tulsa District. Wave 1 only matched MAR2 (Cottonwood River stage, 4.76 km) and rejected it; MARI is the pool elevation series (1350.57 vs full pool 1350.5)."),
    (["Longview Lake|MO"], "NWDM", "LGVM.Elev.Inst.1Hour.0.Best-NWK", "LGVM", "elev", 891.0,
     "Longview Dam and Lake pool elevation, USACE Kansas City District (relays also appear on A2W, NWPS LNZM7, USGS 06893791). Agrees at 891.2 ft = full pool; wave 1 rejected only on the 3 km geometry rule (directory point vs dam)."),
    (["Lake Pepin|MN"], "MVP", "LakeCity.Elev.Inst.15Minutes.0.rev-MSL1912", "LakeCity", "elev", 667.0,
     "Mississippi River at Lake City MN, ON Lake Pepin (Pool 4); elevation in MSL 1912 datum, USACE St. Paul District. Pool 4 normal 667.0. Wave 1 rejected on name only."),
    (["Lake Pepin|MN"], "MVP", "Wabasha.Elev.Inst.15Minutes.0.rev-MSL1912", "Wabasha", "elev", 667.0,
     "Mississippi River at Wabasha MN (upper end of Lake Pepin / Pool 4 reach), MSL 1912 datum. Sibling gauge on the same pool."),
    (["Lake Pepin|MN"], "MVP", "LockDam_04.Elev.Inst.15Minutes.0.rev-MSL1912", "LockDam_04", "elev", 667.0,
     "Lock & Dam 4 (Alma WI) pool elevation = lower end of Lake Pepin, MSL 1912 datum."),
    (["Big Creek Lake|IA"], "MVR", "PLKI4.Stage.Inst.30Minutes.0.rev", "PLKI4", "stage", 920.0,
     "Big Creek Diversion Dam near Polk City: CWMS 'Stage' reads 920.36 which equals an absolute elevation and the directory full pool 920 (datum not stated). 10 m from the directory point. Likely the Big Creek lake level but datum unconfirmed."),
    (["Lake Poinsett|SD"], "NWDM", "LPSD.Elev.Inst.1Hour.0.Best-NWO", "LPSD", "elev", 1646.0,
     "STALE history companion: USACE Omaha District series for Lake Poinsett ends 2026-03-20 (16 y of hourly elevation from 2010). Useful to pair with the live NWS PONS2 'Lake Elevation' series of the same lake if the two agree (check offset); not live on its own. 1.2 km from the directory point.", True),
    (["Big Creek Lake|IA"], "MVR", "BIGI4.Stage.Inst.30Minutes.0.rev", "BIGI4", "stage", None,
     "Big Creek Ponding Area at Polk City: 'Stage' reads 837.29 (absolute-elevation magnitude). Probably the downstream/Saylorville-affected pond, 4.4 km away: SIBLING, datum unconfirmed."),
]


def run_cwms():
    for ent in CWMS_S:
        lakes, off, name, loc, fam, fp, notes = ent[:7]
        stale_ok = len(ent) > 7 and ent[7]
        b = (NOW - dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pts, info = cwms_pull(off, name, b)
        if not pts and stale_ok:
            hp0, info = cwms_pull(off, name, "1900-01-01T00:00:00Z")
            pts = hp0[-720:]
        if not pts:
            LOG.append(dict(lakes=lakes, prov="cwms", station=f"{off}:{loc}", series=name, result="no-live-data"))
            continue
        s, L = gjson(f"{CWMS}/locations/{loc}?office={off}", CH)
        L = L or {}
        vdi = info.get("vertical-datum-info") or {}
        vd = vdi.get("native-datum") or "unknown"
        if "MSL1912" in name:
            vd = "MSL1912 (~NGVD29)"
        hp, _ = cwms_pull(off, name, "1900-01-01T00:00:00Z")
        daily = clean_daily(daily_from_pts(hp)) if hp else None
        emit(lakes, "cwms-" + off.lower(), "usace", f"{off}:{loc}", L.get("long-name") or L.get("public-name") or loc, L.get("latitude"), L.get("longitude"),
             name, fam, vd.replace("NGVD-29", "NGVD29").replace("NAVD-88", "NAVD88"), pts,
             f"{CWMS}/timeseries?name={name}&office={off}&begin=..&end=..&unit=EN (Accept: application/json;version=2)",
             f"https://water.usace.army.mil/overview/{off.lower()}", notes, relay=False, fullPoolHint=fp, daily=daily)


# --------------------------------------------------------------------------- Environment Canada / WSC (Lake of the Woods Control Board gauges)
ECCC = "https://api.weather.gc.ca/collections"


def eccc_station(st):
    s, d = gjson(f"{ECCC}/hydrometric-stations/items?f=json&STATION_NUMBER={st}")
    f = (d or {}).get("features") or []
    return f[0] if f else None


def run_eccc():
    stations = [("05PD029", "Cyclone Island"), ("05PD011", "Clearwater Bay"), ("05PD008", "Hanson Bay"), ("05PE014", "Keewatin")]
    for st, nick in stations:
        f = eccc_station(st)
        if not f:
            continue
        pr = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        b = (NOW - dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"); e = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
        pts, off = [], 0
        while True:
            s, d = gjson(f"{ECCC}/hydrometric-realtime/items?f=json&STATION_NUMBER={st}&datetime={b}/{e}&limit=1000&offset={off}&sortby=DATETIME", timeout=120)
            fs = (d or {}).get("features", [])
            for x in fs:
                p = x["properties"]
                if p.get("LEVEL") is not None:
                    pts.append((epoch(p["DATETIME"]), p["LEVEL"] * FT_PER_M))
            if len(fs) < 1000:
                break
            off += 1000
        if not pts:
            LOG.append(dict(prov="eccc", station=st, result="no-live-data"))
            continue
        # history: daily-mean collection (to last full year) then the realtime window daily means
        daily, off = {}, 0
        while True:
            s, d = gjson(f"{ECCC}/hydrometric-daily-mean/items?f=json&STATION_NUMBER={st}&limit=10000&offset={off}&sortby=DATE", timeout=180)
            fs = (d or {}).get("features", [])
            for x in fs:
                p = x["properties"]
                if p.get("LEVEL") is not None:
                    daily[p["DATE"][:10]] = p["LEVEL"] * FT_PER_M
            if len(fs) < 10000:
                break
            off += 10000
        for k, v in daily_from_pts(pts).items():
            daily.setdefault(k, v)
        emit(["Lake of the Woods|MN"], "eccc", "wsc-lwcb", st, pr["STATION_NAME"], lat, lon, "LEVEL(m)->ft", "elev", "LWD (Lake of the Woods Datum)", pts,
             f"{ECCC}/hydrometric-realtime/items?f=json&STATION_NUMBER={st}&datetime=..&limit=1000 ; hydrometric-daily-mean for history",
             f"https://wateroffice.ec.gc.ca/report/real_time_e.html?stn={st}",
             f"Water Survey of Canada real-time level for Lake of the Woods ({nick}); contributor {pr['CONTRIBUTOR_EN']} (Lake of the Woods Control Board). "
             f"Native units m above 'Lake of the Woods Datum'; converted to ft (322.7 m = 1058.8 ft, within the LWCB regulated range 1056-1061.25 ft). "
             f"The datum is a local/binational lake datum close to IGLD55/NGVD29-class heights; NWPS WRDM5/SSIM5 'Pool' 59 ft are USGS Warroad / Springsteel Island gauge heights above a local gage zero (~1000 ft). "
             f"Directory point is in Canadian-US waters of the lake; station is in Ontario.",
             relay=False, fullPoolHint=None, daily=daily, extra={"stationState": pr["PROV_TERR_STATE_LOC"]})


# --------------------------------------------------------------------------- NWPS (NWS river forecast points; pool elevation 'HP' + gauges)
NWPS = "https://api.water.noaa.gov/nwps/v1"
# (lakeIds, lid, family, vdatum, fullPool, notes, relayOf)
NWPS_S = [
    (["Lake Minnetonka|MN"], "MTKM5", "elev", "unknown", 929.4, "NWPS pool elevation at Gray's Bay dam (relay of USGS 05289000).", "usgs"),
    (["Longview Lake|MO"], "LNZM7", "elev", "unknown", 891.0, "NWPS pool elevation (relay of USGS 06893791 / USACE).", "usgs"),
    (["Lake McConaughy|NE"], "KNGN1", "elev", "unknown", 3265.0,
     "NWPS 'Pool' (PE=HP) at Kingsley Dam: 3202.5 ft on 2026-10-12 is the LAKE pool (CNPPID publishes the identical 3,202.5 ft for Lake McConaughy; tailwater is ~3,100 ft). Wave 1 treated it as unnamed; it is confirmed by CNPPID.", "cnppid/nbrfc"),
    (["Lake Ogallala|NE"], "KNGN1", "elev", "unknown", 3122.0,
     "Kingsley Dam pool elevation = Lake McConaughy, NOT Lake Ogallala (Ogallala is the small re-regulation lake 14 mi below the dam at ~3,122 ft). Listed only as a nearby-wrong-lake warning.", "cnppid/nbrfc"),
    (["Lake Vermilion|MN"], "LVOM5", "stage", "local", 1350.0,
     "Lake Vermilion Water Level at Outlet near Buyck: NWPS 'Pool' reads 56.75 ft = stage above a local gage zero (not elevation). Gage-zero elevation not published by NWPS.", "usgs/state"),
    (["Big Stone Lake|SD"], "BSLM5", "elev", "unknown", 965.0,
     "Minnesota River at Big Stone Lake (Ortonville MN): NWPS 'Pool' 966.4 ft (observations sparse - 8 obs in 30 d, last 2026-10-05). Gauge is in MN, lake is shared MN/SD.", "usace/mn"),
    (["Lake Poinsett|SD"], "PONS2", "elev", "unknown", 1646.0,
     "Big Sioux River at Lake Poinsett Inlet/Outlet (NWS ABR). PE=HL 'Lake Elevation' reads 1650.82 ft on the lake (directory OHW 1646). Wave 1 only matched an old CWMS LPSD series (no data) 1.2 km away.", "state-sd/nws"),
    (["Marion Reservoir|KS"], "MLBK1", "elev", "NAVD88", 1350.5, "Cottonwood River at Marion Reservoir: NWPS 'Pool' 1350.57 = USACE MARI pool elevation (relay).", "usace"),
    (["Lake of the Woods|MN"], "WRDM5", "stage", "local", 1061.0, "Lake of the Woods at Warroad: NWPS 'Pool' 59 ft above local gage zero (USGS 05140520).", "usgs"),
    (["Lake of the Woods|MN"], "SSIM5", "stage", "local", 1061.0, "Lake of the Woods at Springsteel Island: NWPS 'Pool' 59 ft above local gage zero (USGS 05140521).", "usgs"),
]


def nwps_pts(lid):
    time.sleep(2.5)   # NWPS rate limit: bbox listing is 10 req / 5 min; per-gauge calls are spaced 2.5 s on top of the 1 s host throttle
    s, d = gjson(f"{NWPS}/gauges/{lid}/stageflow")
    if not d:
        return [], {}
    o = d.get("observed") or {}
    pts = []
    for x in o.get("data", []):
        v = x.get("primary")
        if v is None or v <= -900:
            continue
        pts.append((epoch(x["validTime"]), v))
    return pts, o


def run_nwps(extra_specs=None):
    for lakes, lid, fam, vd, fp, notes, rel in NWPS_S + (extra_specs or []):
        pts, o = nwps_pts(lid)
        if not pts:
            LOG.append(dict(lakes=lakes, prov="nwps", station=lid, result="no-live-data"))
            continue
        time.sleep(2.5)
        s, g = gjson(f"{NWPS}/gauges/{lid}")
        g = g or {}
        unit = (o.get("primaryUnits") or "ft")
        if unit.lower() not in ("ft", "feet"):
            LOG.append(dict(lakes=lakes, prov="nwps", station=lid, result=f"unit {unit}"))
            continue
        emit(lakes, "nwps", rel.split("/")[0] if rel else "nws", lid, g.get("name", lid), g.get("latitude"), g.get("longitude"),
             (g.get("pedts") or {}).get("observed", "HP"), fam, vd, pts, f"{NWPS}/gauges/{lid}/stageflow (observed.primary)",
             f"https://water.noaa.gov/gauges/{lid}", notes + f" RELAY of {rel}; NWPS keeps ~30 d only (no archive).", relay=True, fullPoolHint=fp,
             extra={"usgsId": g.get("usgsId"), "dataAttribution": g.get("dataAttribution")})


# --------------------------------------------------------------------------- web pages published by utilities / districts
def txt_rows(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)))


def run_web():
    # CNPPID (Central Nebraska Public Power & Irrigation District) lake elevations
    s, b = get("https://cnppid.com/lake-river-data")
    if s == 200:
        m = re.search(r"Readings for \w+, (\w+ \d+, \d{4})", b)
        rd = dt.datetime.strptime(m.group(1), "%B %d, %Y").replace(tzinfo=dt.timezone.utc) if m else None
        sec = b[b.find("Lake &amp; Reservoir Elevations"):]
        sec = sec[:sec.find("</table>")]
        for name, today, wk, mo, yr in re.findall(r'data-header="Location">([^<]+)</td>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>([^<]+)</td>', sec):
            num = lambda x: float(re.search(r"[\d,]+\.\d", x).group(0).replace(",", ""))
            vals = [(rd.timestamp(), num(today)), (rd.timestamp() - 7 * 86400, num(wk)), (rd.timestamp() - 30 * 86400 + 86400, num(mo))]
            lakes = {"Lake McConaughy": (["Lake McConaughy|NE"], 41.22, -101.66, 3265.0),
                     "Johnson Lake": (["Johnson Lake|NE"], 40.70, -99.83, 2618.0)}.get(name.strip())
            if not lakes:
                LOG.append(dict(prov="cnppid", station=name.strip(), today=num(today), note="not in mw scope"))
                continue
            emit(lakes[0], "cnppid", "cnppid", name.strip().replace(" ", "_"), f"{name.strip()} (CNPPID daily elevation table)", lakes[1], lakes[2],
                 "Today (Feet above Sea Level)", "elev", "unknown (feet above sea level; CNPPID datum unstated, matches NWS NBRFC pool for McConaughy)", vals,
                 "https://cnppid.com/lake-river-data (HTML table, server-rendered)", "https://cnppid.com/lake-river-data",
                 "CNPPID (the operator) publishes one reading per day for its reservoirs plus 1-week / 1-month / 1-year-ago values (only 'today', '1 week ago' and '1 month ago' are used as n30 points here). "
                 "Data are pulled from Nebraska DWEE (AQUARIUS portal, which is disclaimer/accept-gated and was NOT bypassed). No archive download.",
                 relay=False, fullPoolHint=lakes[3], extra={"obsDateFromPage": rd.strftime("%Y-%m-%d"), "yearAgoFt": num(yr)})
    # NIPSCO
    s, b = get("https://www.nipsco.com/our-company/about-us/hydro-power")
    if s == 200:
        t = re.sub(r"(\|\s*)+", "|", txt_rows(b))
        for nm, lake in (("Norway Hydro Plant", "Lake Shafer|IN"), ("Oakdale Hydro Plant", "Lake Freeman|IN")):
            i = t.find(nm)
            m = re.search(r"\(Cubic Feet/Second\)\|(\d{3}\.\d\d) \|.*?Updated last: (\d+/\d+/\d{4} \d+:\d+:\d+ [AP]M)", t[i:i + 900]) if i >= 0 else None
            if not m:
                LOG.append(dict(prov="nipsco", lake=lake, result="parse-fail")); continue
            v = float(m.group(1))
            # 'Local Time' on the page = Indiana (Eastern, EDT in October)
            ts_ = dt.datetime.strptime(m.group(2), "%m/%d/%Y %I:%M:%S %p").replace(tzinfo=dt.timezone(dt.timedelta(hours=-4))).timestamp()
            fp = 645.15 if "Shafer" in lake else 610.35
            lat, lon = (40.78, -86.76) if "Shafer" in lake else (40.65, -86.78)
            emit([lake], "nipsco", "nipsco", "Norway" if "Shafer" in lake else "Oakdale", f"{nm.strip()} - {lake.split('|')[0]} (NIPSCO 'Current Lake Levels')", lat, lon,
                 "Plant Lake Level (El ft local datum)", "elev", "local (operator datum; FERC license limits 645.15/610.35 ft)", [(ts_, v)],
                 "https://www.nipsco.com/our-company/about-us/hydro-power (HTML, server-rendered with 'Updated last' timestamp)", "https://www.nipsco.com/our-company/about-us/hydro-power",
                 "Operator page shows the current plant forebay level with an 'Updated last ... Local Time' stamp (Eastern). Lake level is controlled to a +-2.4 in (Norway) / 3.5 in (Oakdale) band around the FERC target. "
                 "No history is published (nipscohydro.com has an expired TLS certificate). Single-point candidate: n30=1.",
                 relay=False, fullPoolHint=fp, extra={"timestampOnPage": True})
    # We Energies / Wisconsin Public Service / Wisconsin River Power Co hydro page (10-minute updates)
    s, b = get("http://www.wisconsinpublicservice.com/environment/hydrodata.aspx")
    if s == 200:
        t = re.sub(r"(\|\s*)+", "|", txt_rows(b))
        m = re.search(r"Water Levels\|(\d+/\d+/\d{4} \d+:\d+:\d+ [AP]M) CST", t)
        # the page label says CST but the value tracks US/Central wall-clock time (checked against UTC at fetch time): treat as local clock, CDT in Oct
        ts = dt.datetime.strptime(m.group(1), "%m/%d/%Y %I:%M:%S %p").replace(tzinfo=dt.timezone(dt.timedelta(hours=-5))).timestamp() if m else time.time()
        seg = t[t.find("Water Levels|"):t.find("Rain Gage Data")]
        projs = {}
        for mm in re.finditer(r"\|([^|]+?) - (We Energies|WPS|WRPCO)\|(.*?)(?=\|[^|]+? - (?:We Energies|WPS|WRPCO)\||$)", seg):
            hw = re.search(r"Head Water Level\|([\d,\.]+)\|feet", mm.group(3))
            if hw:
                projs[mm.group(1)] = float(hw.group(1).replace(",", ""))
        LOG.append(dict(prov="wps-hydro", projects=projs, pageTime=m.group(1) if m else None))
        for pname, lakes, lat, lon, fp, nt in [("Castle Rock", ["Castle Rock Lake|WI"], 43.8658, -89.9547, 882.0,
                                                "Castle Rock Dam head-water level = Castle Rock Flowage pool (NWS CROW3 page quotes a 882 ft target pool). Wisconsin River Power Co (WRPCO).")]:
            if pname in projs:
                emit(lakes, "wps-hydro", "wrpco", pname.replace(" ", "_"), f"{pname} - WRPCO head water level", lat, lon, "Head Water Level (ft)", "elev",
                     "unknown (project datum, NGVD29-class)", [(ts, projs[pname])],
                     "http://www.wisconsinpublicservice.com/environment/hydrodata.aspx (HTML, updated every 10 min; page carries a timestamp)",
                     "http://www.wisconsinpublicservice.com/environment/hydrodata.aspx",
                     nt + " The same page lists head-water levels for 30 We Energies / WPS / WRPCO projects in WI and Upper MI (incl. Petenwell 923.19 ft, Caldron Falls, High Falls, Michigamme/Way Dam, Tomahawk, Wausau): "
                     "a general method for utility-owned flowages, only Castle Rock is an unbound directory lake in this scout's scope. No history exposed; single timestamped reading (n30=1).",
                     relay=False, fullPoolHint=fp, extra={"pageProjects": len(projs), "timestampOnPage": True})
    # NPPD (Nebraska Public Power District) Reservoir Elevations page: Sutherland Reservoir
    s, b = get("http://v1.nppd.com/About_Us/Energy_Facilities/facilities/water_data2.aspx")
    if s == 200:
        t = re.sub(r"(\|\s*)+", "|", txt_rows(b))
        mt = re.search(r"Today\|(\w{3} \d+ \d+:\d+ [ap]\.m\.)", t)
        ms = re.search(r"Sutherland Reservoir.*?\|(\d{4}\.\d\d) ft\.\|Vol=[\d,]+ a-f\|(\d{4}\.\d\d) ft\..*?\|(\d{4}\.\d\d) ft\.\|Vol=[\d,]+ a-f\|(\d{4}\.\d\d) ft\.", t)
        if mt and ms:
            cdt = dt.timezone(dt.timedelta(hours=-5))
            ts_ = dt.datetime.strptime(f"{dt.datetime.now(cdt).year} " + mt.group(1).replace("a.m.", "AM").replace("p.m.", "PM"), "%Y %b %d %I:%M %p").replace(tzinfo=cdt).timestamp()
            today, wk, mo, yr = [float(x) for x in ms.groups()]
            emit(["Sutherland Reservoir|NE"], "nppd", "nppd", "Sutherland", "Sutherland Reservoir (NPPD 'Reservoir Elevations and Canal Flows')", 41.13, -101.15,
                 "Reservoir elevation (ft)", "elev", "unknown (operator datum, feet above sea level)",
                 [(ts_, today), (ts_ - 7 * 86400, wk), (ts_ - 30 * 86400, mo)],
                 "http://v1.nppd.com/About_Us/Energy_Facilities/facilities/water_data2.aspx (HTML table with timestamp; also v1.nppd.com/chartfx/HydraulicCanalData.aspx 'Sutherland Lake Elevation')",
                 "https://www.nppd.com/powering-nebraska/energy-resources/water-data",
                 "NPPD (operator) page: today (timestamped) / week-ago / month-ago / year-ago elevations + storage; n30 uses today, week-ago, month-ago points. Reads 3050.12 ft; directory full pool 3043 conflicts with "
                 "published normal 3061 (NGPC/Wikipedia) and NPPD fill guideline 3053-3054 spring: the directory fullPool for Sutherland looks wrong, the operator elevation is the reference. 12-month and 1-month graphs exist as images only (chart.aspx IDs).",
                 relay=False, fullPoolHint=3061.0, extra={"yearAgoFt": yr, "timestampOnPage": True})
    # Alliant Energy hydro flow-rate page: Prairie du Sac head water = Lake Wisconsin (alliantenergy.com's WAF intermittently 403s Python's TLS client;
    # curl with the same honest User-Agent and an Accept header is served)
    s, b = get("https://www.alliantenergy.com/our-energy/hydro/flow-rate", headers={"Accept": "text/html,application/xhtml+xml"}, retries=1)
    if s != 200:
        import subprocess
        time.sleep(1.0)
        r = subprocess.run(["curl", "-s", "-m", "60", "-A", "SectorEngine-LakeBrain-research/1.0 (read-only; contact mgcather07@gmail.com)",
                            "-H", "Accept: text/html,application/xhtml+xml", "-w", "\n%{http_code}", "https://www.alliantenergy.com/our-energy/hydro/flow-rate"],
                           capture_output=True, text=True)
        b, _, code = r.stdout.rpartition("\n")
        s = int(code) if code.isdigit() else 0
    if s == 200:
        t = re.sub(r"(\|\s*)+", "|", txt_rows(b))
        i = t.find("Prairie du Sac Flow Rate Data")
        mu = re.search(r"Last update: (\w{3} \d+, \d{4} \d+:\d+:\d+ [AP]M) CST", t[i:]) if i >= 0 else None
        mh = re.search(r"Head Water \(feet NGVD\)\|([\d.]+)", t[i:]) if i >= 0 else None
        if mu and mh:
            ts_ = dt.datetime.strptime(mu.group(1), "%b %d, %Y %I:%M:%S %p").replace(tzinfo=dt.timezone(dt.timedelta(hours=-5))).timestamp()
            emit(["Lake Wisconsin|WI"], "alliant", "alliant-energy", "PrairieduSac", "Prairie du Sac hydro head water (Lake Wisconsin) - Alliant Energy flow-rate page", 43.3, -89.73,
                 "Head Water (feet NGVD)", "elev", "NGVD29", [(ts_, float(mh.group(1)))],
                 "https://www.alliantenergy.com/our-energy/hydro/flow-rate (HTML; needs 'Accept: text/html')", "https://www.alliantenergy.com/our-energy/hydro/flow-rate",
                 "Alliant Energy (Prairie du Sac dam owner) publishes head water in feet NGVD with a timestamp, 4-h/12-h changes; FERC license maintains Lake Wisconsin within ~7 in of 774.4 ft (matches directory full pool 774.4). "
                 "Page label says CST but tracks local clock. Single timestamped point (no history exposed). Wave 1's USGS MP-3 sites are not reporting. Page also gives Kilbourn (Wisconsin Dells) head water 834.19.",
                 relay=False, fullPoolHint=774.4, extra={"timestampOnPage": True})
    # CWLP Springfield
    s, b = get("https://www.cwlp.com/LakesParksHome/LakesParksInformation/LakeWaterLevels.aspx")
    if s == 200:
        rows = re.findall(r"<span>(\d{1,2}/\d{1,2}/\d{4})</span>\s*</td>\s*<td[^>]*>\s*<span>\s*([\d.]+)'?\s*</span>\s*</td>\s*<td[^>]*>\s*<span>\s*([\d.]*)'?\s*</span>", b)
        daily = {}
        for d, cur, prev in rows:
            D = dt.datetime.strptime(d, "%m/%d/%Y")
            if cur:
                daily[D.strftime("%Y-%m-%d")] = float(cur)
            if prev:
                try:
                    daily.setdefault(D.replace(year=D.year - 1).strftime("%Y-%m-%d"), float(prev))
                except ValueError:
                    pass
        cur_pts = [(dt.datetime.strptime(d, "%m/%d/%Y").replace(tzinfo=dt.timezone.utc, hour=12).timestamp(), float(c)) for d, c, p in rows if c]
        if cur_pts:
            emit(["Lake Springfield|IL"], "cwlp", "cwlp-springfield", "SpauldingDam", "Lake Springfield at CWLP plant (Low Service Pump Station stick/sonic reading)", 39.7316, -89.5946,
                 "Current Year Level", "elev", "CWLP datum (nominal full pool 560.00 ft; USGS official full pool 559.35 ft)", cur_pts,
                 "https://www.cwlp.com/LakesParksHome/LakesParksInformation/LakeWaterLevels.aspx (HTML table, last 2 y of readings)",
                 "https://www.cwlp.com/LakesParksHome/LakesParksInformation/LakeWaterLevels.aspx",
                 "City Water Light & Power (operator). Official reading by stick every 2 h at the pump station; web table shows roughly weekly values for the current and previous year "
                 "(history file = those ~weekly points, NOT daily; do not use for year completeness). CWLP datum is 0.65 ft above USGS 559.35 official full pool - apply when comparing to NGVD29. NWS ILX also relays daily (RVA product).",
                 relay=False, fullPoolHint=560.0, daily=daily)


# --------------------------------------------------------------------------- Minnesota DNR LakeFinder (volunteer readings)
DNR_IDS = {  # lakeId -> list of DNR 8-digit ids (found with services.dnr.state.mn.us/api/lakefinder/by_point)
}


def run_mndnr():
    mn = ["Otter Tail Lake|MN", "Lake Bemidji|MN", "White Bear Lake|MN", "Lake Vermilion|MN", "Lake Pepin|MN", "Lake Minnetonka|MN", "Lake of the Woods|MN", "Big Stone Lake|SD"]
    for lk in mn:
        p = PROFILE[lk]
        s, d = gjson(f"https://services.dnr.state.mn.us/api/lakefinder/by_point/v1?lat={p['lat']}&lon={p['lon']}&radius=3000")
        res = (d or {}).get("results") or []
        LOG.append(dict(prov="mndnr", lake=lk, candidates=[(r["id"], r["name"], r["resources"].get("waterLevels")) for r in res][:8]))
        for r in res:
            if not r["resources"].get("waterLevels") or name_sim(r["name"], lk.split("|")[0]) < 0.5:
                continue
            lid = r["id"]
            s, b = get(f"https://maps.dnr.state.mn.us/cgi-bin/lakefinder/water_levels_export.cgi?format=csv&id={lid}")
            if s != 200:
                continue
            rows = list(csv.DictReader(io.StringIO(b)))
            daily, pts = {}, []
            for x in rows:
                try:
                    v = float(x["ELEVATION"]); d0 = x["READ_DATE"]
                except Exception:
                    continue
                daily[d0] = v
                pts.append((dt.datetime.strptime(d0, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp(), v))
            if not pts:
                continue
            pts30 = [(t, v) for t, v in pts if t >= NOW.timestamp() - 400 * 86400] or pts[-5:]
            pt = r["point"]["epsg:4326"]
            # live window for summarize = last 400 d of readings (documented in notes)
            emit([lk], "mndnr", "state-mn-dnr", lid, f"{r['name']} (MN DNR LakeFinder water levels, id {lid})", pt[1], pt[0], "ELEVATION (volunteer staff-gauge reads)", "elev",
                 rows[0].get("DATUM_ADJ", "MSL 1912").replace("MSL 1912", "NGVD29 (MSL 1912)"), pts30,
                 f"https://maps.dnr.state.mn.us/cgi-bin/lakefinder/water_levels_export.cgi?format=csv&id={lid}", f"https://www.dnr.state.mn.us/lakefind/showlevel.html?downum={lid}",
                 "NOT LIVE / SPARSE: MN DNR lake-level program = volunteer weekly-ish staff-gauge readings, mostly April-November, many lakes read only a few times per year. "
                 "Absolute elevations in MSL 1912 (~NGVD29), OHW elevation published on the report page. medFt/lastFt/n30 here are computed over the last 400 days of readings, not 30 d. "
                 "Useful for datum/OHW confirmation and long history (record starts ~1919 for some lakes) but cannot be a live feed.",
                 relay=False, fullPoolHint=None, daily=daily, extra={"n400d": len(pts30)})


# --------------------------------------------------------------------------- Minnesota DNR Cooperative Stream Gaging (CSG) public API, includes lake-level telemetry
CSG_API = "https://webapps.dnr.state.mn.us/csg/api/v1"
# (lakeIds, site id, variable, family, vdatum, fullPool, notes, relayOf)
CSG_S = [
    (["White Bear Lake|MN"], "82016700", 232, "elev", "unknown (MN DNR; LakeFinder uses MSL 1912 ~ NGVD29)", 924.89,
     "White Bear Lake at Manitou Island Rd (DNR telemetry, statutory lake-level gauge under MN Stat 103G.412). 'Level (ft)' reads 921.98 = absolute elevation (OHW 924.89 ft). Hourly since ~2013 (15-min earlier), provisional/approved flags.", None),
    (["Lake Vermilion|MN"], "73050001", 232, "stage", "local", 1350.0,
     "Lake Vermilion outlet near Buyck CR667 (DNR/USGS telemetry). Variable 232 = 'raw levels' (stage above local gage zero), NOT elevation; same gauge as NWPS LVOM5 (56.75).", "usgs"),
]


def run_mncsg():
    import zipfile
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/Chicago")
    s, d = gjson(f"{CSG_API}/sites")
    meta = {x["id"]: x for x in (d or {}).get("sites", [])}
    for lakes, sid, var, fam, vd, fp, notes, rel in CSG_S:
        import urllib.request
        time.sleep(1.0)   # polite spacing; the download endpoint returns a zip (binary), so http_get (text) is not used
        req = urllib.request.Request(f"{CSG_API}/download?ids={sid}&vars={var}", headers={"User-Agent": "SectorEngine-LakeBrain-research/1.0 (read-only; contact mgcather07@gmail.com)"})
        try:
            raw = urllib.request.urlopen(req, timeout=600).read()
            z = zipfile.ZipFile(io.BytesIO(raw))
        except Exception as e:
            LOG.append(dict(prov="mncsg", station=sid, result=f"download-fail {e}")); continue
        pts, hourly = [], {}
        for n in z.namelist():
            if n.startswith("metadata"):
                continue
            for row in csv.DictReader(io.StringIO(z.read(n).decode("utf8", "replace"))):
                try:
                    v = float(row["value"])
                    t = dt.datetime.strptime(row["tstamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz).timestamp()
                except Exception:
                    continue
                hourly.setdefault(row["tstamp"][:10], []).append(v)
                if t >= NOW.timestamp() - 30 * 86400:
                    pts.append((t, v))
        daily = {k: sum(v) / len(v) for k, v in hourly.items()}
        m = meta.get(sid, {})
        emit(lakes, "mncsg", "state-mn-dnr" if not rel else rel, sid, m.get("name", sid), float(m.get("lat", 0)) or None, float(m.get("lon", 0)) or None,
             f"var{var}", fam, vd, pts, f"{CSG_API}/download?ids={sid}&vars={var} (zip of CSV; sites index at {CSG_API}/sites)",
             f"https://www.dnr.state.mn.us/waters/csg/index.html", notes + " Time stamps taken as US/Central local time. Public anonymous API behind the DNR CSG map viewer (not documented; used as the viewer's own download button).",
             relay=bool(rel), fullPoolHint=fp, daily=daily)


SECTIONS = {"mncsg": run_mncsg, "coops": run_coops, "usgs": run_usgs, "cwms": run_cwms, "eccc": run_eccc, "nwps": run_nwps, "web": run_web, "mndnr": run_mndnr}

def flush(section):
    """Merge this section's records into cand/mw.jsonl (replacing any earlier records of the same section)."""
    keep = []
    if os.path.exists(CAND):
        for l in open(CAND):
            r = json.loads(l)
            if r.get("section") != section:
                keep.append(r)
    for r in RECORDS:
        r["section"] = section
    with open(CAND, "w") as f:
        for r in keep + RECORDS:
            f.write(json.dumps(r) + "\n")
    n = len(RECORDS)
    RECORDS.clear()
    return n


if __name__ == "__main__":
    want = sys.argv[1:] or list(SECTIONS)
    if not sys.argv[1:] and os.path.exists(CAND):
        os.remove(CAND)
    for k in want:
        print("== section", k, flush=True)
        try:
            SECTIONS[k]()
        except Exception as e:           # keep going; record the failure
            import traceback
            LOG.append(dict(section=k, error=traceback.format_exc()[-800:]))
            print("   ERROR", e, flush=True)
        print("   records", flush(k), flush=True)
        json.dump(LOG, open(f"{NOTES}/mw_series_check.json", "w"), indent=1)
    print("done;", len(LOG), "log entries")
