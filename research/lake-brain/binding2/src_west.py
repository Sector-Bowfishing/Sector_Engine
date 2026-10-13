"""binding2 wave-2 source scout, area = WEST (AK HI WA OR CA NV UT AZ NM CO WY MT ID).

Read-only, polite (>= ~1 s between requests, sequential). No accounts / keys.  Regenerates
  Sector_Research_Data/lake-brain/binding2/cand/west.jsonl     (one record per (lake, series) that returned LIVE data)
  Sector_Research_Data/lake-brain/binding2/history/<prov>_<station>_<series>.csv.gz   (daily mean, ft, no header)
  Sector_Research_Data/lake-brain/binding2/raw/west_run.json   (per-series run log incl. stale / failed series)
Notes (source evaluation records, dead ends) are written by src_west_notes.py -> notes/west.json.

Usage:  python src_west.py [--no-history] [--only prov1,prov2]
"""
import sys, os, csv, gzip, json, re, time, argparse, datetime as dt, urllib.parse, urllib.request, urllib.error
from zoneinfo import ZoneInfo

sys.path.insert(0, "/Users/mcather/Desktop/Development/Sector_Engine/research/lake-brain/binding")
from common import http_get, get_json, UA          # noqa: E402
from providers import summarize, year_completeness  # noqa: E402

B2 = "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/binding2"
HIST = f"{B2}/history"
for d in (HIST, f"{B2}/cand", f"{B2}/notes", f"{B2}/raw"):
    os.makedirs(d, exist_ok=True)

NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.strftime("%Y-%m-%d")
SLEEP = 1.0
LIVE_MAX_AGE_H = 96.0
JH = {"Accept": "application/json"}


def G(url, headers=None, **kw):
    kw.setdefault("sleep", SLEEP)
    kw.setdefault("timeout", 180)
    return http_get(url, headers, **kw)


def GJ(url, headers=None, **kw):
    kw.setdefault("sleep", SLEEP)
    kw.setdefault("timeout", 180)
    return get_json(url, headers, **kw)


def ts_epoch(s, tz):
    """'YYYY-MM-DD HH:MM[:SS]' in tz (ZoneInfo or fixed-offset timezone) -> epoch seconds."""
    s = s.strip().replace("T", " ")
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            d = dt.datetime.strptime(s, f)
            return d.replace(tzinfo=tz).timestamp()
        except ValueError:
            pass
    raise ValueError(s)


def daily_noon(date_s, tz):
    return dt.datetime.strptime(date_s, "%Y-%m-%d").replace(hour=12, tzinfo=tz).timestamp()


def to_daily(pts, tz):
    by = {}
    for t, v in pts:
        by.setdefault(dt.datetime.fromtimestamp(t, tz).strftime("%Y-%m-%d"), []).append(v)
    return {k: sum(v) / len(v) for k, v in by.items()}


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


PT, MT, MST_AZ = ZoneInfo("America/Los_Angeles"), ZoneInfo("America/Denver"), ZoneInfo("America/Phoenix")
BOISE = ZoneInfo("America/Boise")
PST = dt.timezone(dt.timedelta(hours=-8))


# ------------------------------------------------------------------ USBR Pacific Northwest Hydromet (pn-bin)
def hm_recent(st, tz, days=31, instant=True):
    start = (NOW - dt.timedelta(days=days)).strftime("%Y-%m-%d")
    end = (NOW + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    if instant:
        u = f"https://www.usbr.gov/pn-bin/instant.pl?list={st}%20fb&format=csv&start={start}&end={end}"
    else:
        u = f"https://www.usbr.gov/pn-bin/daily.pl?list={st}%20fb&format=csv&start={start}&end={end}"
    s, b = G(u)
    pts = []
    for ln in b.splitlines()[1:]:
        p = ln.split(",")
        if len(p) < 2 or not p[1].strip():
            continue
        try:
            v = float(p[1])
        except ValueError:
            continue
        if instant:
            pts.append((ts_epoch(p[0], tz), v))
        else:
            if p[0] >= TODAY:      # partial day
                continue
            pts.append((daily_noon(p[0], tz), v))
    return pts


def hm_hist(st):
    u = f"https://www.usbr.gov/pn-bin/daily.pl?list={st}%20fb&format=csv&start=1900-01-01&end={TODAY}"
    s, b = G(u, timeout=300)
    d = {}
    for ln in b.splitlines()[1:]:
        p = ln.split(",")
        if len(p) < 2 or not p[1].strip() or p[0] >= TODAY:
            continue
        try:
            d[p[0]] = float(p[1])
        except ValueError:
            pass
    return d


# ------------------------------------------------------------------ CDEC (California Data Exchange Center)
def cdec(st, sensor, dur, start, tz=PST):
    u = (f"https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet?Stations={st}&SensorNums={sensor}&dur_code={dur}"
         f"&Start={start}&End={(NOW + dt.timedelta(days=2)).strftime('%Y-%m-%d')}")
    s, d = GJ(u, timeout=300)
    out = []
    for x in d or []:
        v = x.get("value")
        if not isinstance(v, (int, float)) or v <= -9000:
            continue
        out.append((x["date"].strip(), float(v)))
    return out


def _nd(s):
    y, m, d = s.split(" ")[0].split("-")
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def cdec_recent(st, dur, tz=PST):
    rows = cdec(st, 6, dur, (NOW - dt.timedelta(days=35)).strftime("%Y-%m-%d"))
    if dur == "D":
        return [(daily_noon(_nd(r[0]), tz), r[1]) for r in rows]
    return [(ts_epoch(r[0], tz), r[1]) for r in rows]


def cdec_hist(st):
    d = {}
    for ds, v in cdec(st, 6, "D", "1900-01-01"):
        k = _nd(ds)
        if k < TODAY:
            d[k] = v
    return d


# ------------------------------------------------------------------ USGS NWIS
_SITE = {}


def usgs_site(site):
    if site in _SITE:
        return _SITE[site]
    s, b = G(f"https://waterservices.usgs.gov/nwis/site/?format=rdb&sites={site}&siteOutput=expanded&siteStatus=all")
    info = {}
    if s == 200:
        rows = [l.split("\t") for l in b.splitlines() if l and not l.startswith("#")]
        if len(rows) >= 3:
            r = dict(zip(rows[0], rows[2]))
            info = dict(name=r.get("station_nm"), lat=float(r["dec_lat_va"]), lon=float(r["dec_long_va"]), alt=(r.get("alt_va") or "").strip(),
                        altdatum=(r.get("alt_datum_cd") or "").strip(), tz=r.get("tz_cd"))
    _SITE[site] = info
    return info


def usgs_iv(site, par, days=31):
    s, d = GJ(f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={site}&parameterCd={par}&period=P{days}D&siteStatus=all")
    best = (0, [], None)
    if not d:
        return [], None
    for t in d["value"]["timeSeries"]:
        nd = t["variable"].get("noDataValue", -999999)
        pts = []
        for blk in t["values"]:
            for v in blk["value"]:
                try:
                    x = float(v["value"])
                except Exception:
                    continue
                if x == nd:
                    continue
                pts.append((dt.datetime.fromisoformat(v["dateTime"]).timestamp(), x))
        if pts and (not best[1] or pts[-1][0] > best[1][-1][0]):
            best = (len(pts), pts, t["variable"])
    return best[1], best[2]


def usgs_dv(site, par):
    s, d = GJ(f"https://waterservices.usgs.gov/nwis/dv/?format=json&sites={site}&parameterCd={par}&startDT=1900-01-01&endDT={TODAY}&siteStatus=all", timeout=300)
    if not d:
        return None
    cands = []
    for t in d["value"]["timeSeries"]:
        nd = t["variable"].get("noDataValue", -999999)
        m = {}
        for blk in t["values"]:
            for v in blk["value"]:
                try:
                    x = float(v["value"])
                except Exception:
                    continue
                if x != nd and v["dateTime"][:10] < TODAY:
                    m[v["dateTime"][:10]] = x
        if m:
            cands.append(m)
    return max(cands, key=lambda m: (max(m), len(m))) if cands else None


# ------------------------------------------------------------------ SRP Watershed Connection (public JSON used by streamflow.watershedconnection.com)
SRP = "https://streamflow.watershedconnection.com/api/watershedconnectiondata"


def srp_pts(mid, a, b):
    s, d = GJ(f"{SRP}/getmeasurementdata?measurementId={mid}&units=ft&startDate={a}&endDate={b}", JH, timeout=300)
    return [(r["readingDate"], r["readingValue"]) for r in (d or {}).get("timeSeriesData", []) if r.get("readingValue") is not None]


def srp_recent(mid):
    a = (NOW - dt.timedelta(days=31)).strftime("%Y-%m-%d")
    b = (NOW + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    return [(ts_epoch(r[0], MST_AZ), r[1]) for r in srp_pts(mid, a, b)]


def srp_hist(mid):
    d, cur = {}, dt.date(2023, 10, 1)
    end = NOW.date()
    by = {}
    while cur <= end:
        nxt = (cur.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
        for r in srp_pts(mid, cur.isoformat(), nxt.isoformat()):
            if r[0][:10] < TODAY:
                by.setdefault(r[0][:10], []).append(r[1])
        cur = nxt
    return {k: sum(v) / len(v) for k, v in by.items()}


# ------------------------------------------------------------------ Colorado DWR / CDSS telemetry
CO = "https://dwr.state.co.us/Rest/GET/api/v2/telemetrystations"


def co_recent(abbrev):
    a = (NOW - dt.timedelta(days=31)).strftime("%m/%d/%Y")
    b = (NOW + dt.timedelta(days=1)).strftime("%m/%d/%Y")
    s, d = GJ(f"{CO}/telemetrytimeseriesraw/?format=json&abbrev={abbrev}&parameter=ELEV&startDate={a}&endDate={b}&pageSize=50000")
    return [(ts_epoch(r["measDateTime"], MT), r["measValue"]) for r in (d or {}).get("ResultList", []) if r.get("measValue") is not None]


def co_hist(abbrev):
    s, d = GJ(f"{CO}/telemetrytimeseriesday/?format=json&abbrev={abbrev}&parameter=ELEV&startDate=01/01/1980&endDate={dt.date.today().strftime('%m/%d/%Y')}&pageSize=50000", timeout=300)
    out = {}
    for r in (d or {}).get("ResultList", []):
        k = r["measDate"][:10]
        if r.get("measValue") is not None and k < TODAY:
            out[k] = r["measValue"]
    return out


# ------------------------------------------------------------------ NWRFC xml (relay of operator telemetry; ~10 days of hourly obs only)
def nwrfc(id_, pe="HF"):
    s, b = G(f"https://www.nwrfc.noaa.gov/xml/xml.cgi?id={id_}&pe={pe}&dtype=b&numdays=30")
    pts = []
    meta = {}
    m = re.search(r"<description>(.*?)</description>", b)
    meta["name"] = m.group(1) if m else id_
    la, lo = re.search(r"<latitude[^>]*>([\d.\-]+)", b), re.search(r"<longitude[^>]*>([\d.\-]+)", b)
    if la and lo:
        meta["lat"], meta["lon"] = float(la.group(1)), -abs(float(lo.group(1)))
    od = b.split("<observedData>")[1].split("</observedData>")[0] if "<observedData>" in b else ""
    for blk in re.findall(r"<observedValue.*?</observedValue>", od, re.S):
        t = re.search(r"<dataDateTime>(.*?)</dataDateTime>", blk)
        v = re.search(r"<forebay_elevation[^>]*>([\d.\-]+)<", blk)
        if t and v:
            pts.append((dt.datetime.fromisoformat(t.group(1).replace("Z", "+00:00")).timestamp(), float(v.group(1))))
    return pts, meta


# ------------------------------------------------------------------ USACE CWMS data API (office NWDP)
CWMS = "https://cwms-data.usace.army.mil/cwms-data"
CH = {"Accept": "application/json;version=2"}


def cwms(office, name, begin, end, unit="EN"):
    pts, page, info = [], None, {}
    for _ in range(40):
        q = dict(name=name, office=office, begin=begin, end=end, unit=unit, **{"page-size": 100000})
        if page:
            q["page"] = page
        s, d = GJ(CWMS + "/timeseries?" + urllib.parse.urlencode(q), CH, timeout=300)
        if d is None:
            return None, {"status": s}
        info = {k: d.get(k) for k in ("units", "interval", "time-zone", "vertical-datum-info")}
        pts += [(v[0] / 1000.0, v[1]) for v in d.get("values", []) if v[1] is not None]
        page = d.get("next-page")
        if not page:
            break
    return pts, info


def cwms_recent(name, office="NWDP"):
    b = (NOW - dt.timedelta(days=31)).strftime("%Y-%m-%dT%H:%M:%SZ")
    e = (NOW + dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    pts, info = cwms(office, name, b, e)
    return pts or []


def cwms_hist(name, tz=PT, office="NWDP", since="1900-01-01"):
    pts, info = cwms(office, name, f"{since}T00:00:00Z", (NOW + dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    if not pts:
        return None
    return {k: v for k, v in to_daily(pts, tz).items() if k < TODAY}


# ------------------------------------------------------------------ USBR RISE
def rise(item, after):
    out, page = [], 1
    while page < 60:
        q = {"itemId": item, "dateTime[after]": after, "itemsPerPage": 2000, "page": page}
        s, d = GJ("https://data.usbr.gov/rise/api/result?" + urllib.parse.urlencode(q), {"Accept": "application/vnd.api+json"}, timeout=300, sleep=0.6)
        if d is None:
            return None
        out += [(dt.datetime.fromisoformat(x["attributes"]["dateTime"]).timestamp(), x["attributes"]["result"]) for x in d["data"] if x["attributes"]["result"] is not None]
        if not d["links"].get("next"):
            break
        page += 1
    return out


def rise_recent(item):
    return rise(item, (NOW - dt.timedelta(days=35)).strftime("%Y-%m-%d")) or []


def rise_hist(item):
    pts = rise(item, "1900-01-01")
    return {k: v for k, v in to_daily(pts, dt.timezone.utc).items() if k < TODAY} if pts else None


# ------------------------------------------------------------------ Utah Lake Commission live feed (WordPress ajax relay of Utah Division of Water Rights / Orem SCADA tags)
def utahlake():
    req = urllib.request.Request("https://utahlake.gov/wp-admin/admin-ajax.php", data=b"action=ulc_data&refresh=false", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode())
    time.sleep(SLEEP)
    tpl = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", d.get("template", "")))
    m = re.search(r"Elevation \(ft\)\s+(\d+/\d+/\d{4} \d+:\d+ [AP]M)\s+([\d.]+) ft", tpl)
    pts = []
    if m:
        pts.append((dt.datetime.strptime(m.group(1), "%m/%d/%Y %I:%M %p").replace(tzinfo=MT).timestamp(), float(m.group(2))))
    daily = {x["ts"]: x["data"]["CALC_UL_ELEVATION"] for x in d.get("sdailyData", []) if x["data"].get("CALC_UL_ELEVATION") is not None}
    for k, v in daily.items():
        pts.append((daily_noon(k, MT), v))
    return sorted(pts), daily


# ------------------------------------------------------------------ candidate machinery
CAND, RUNLOG = [], []
_HCACHE = {}
_OUTL = {}


def safe(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s))[:80]


def drop_outliers(d, valid=None):
    """Drop physically impossible archive values using explicit per-series bounds (spec['valid'] = (lo, hi)); returns (clean, n_dropped).
    Bounds are generous (>= directory pool +/- tens of ft); they only remove sentinels such as -1, 655.35 ft stage, 959746 ft, or pre-1987 gauge-height
    values stored under an elevation parameter."""
    if not valid:
        return d, 0
    lo, hi = valid
    keep = {k: x for k, x in d.items() if lo <= x <= hi}
    return keep, len(d) - len(keep)


def load_hist_file(path):
    with gzip.open(path, "rt") as f:
        return {r[0]: float(r[1]) for r in csv.reader(f) if r}


def emit(spec, args):
    lid = spec["lakeId"]
    log = dict(lakeId=lid, prov=spec["prov"], station=spec["station"], series=spec["series"])
    try:
        pts = spec["recent"]()
    except Exception as e:  # noqa
        log.update(status="ERROR", err=repr(e)[:200]); RUNLOG.append(log); print("ERR", lid, spec["station"], e); return
    cut = NOW.timestamp() - 30 * 86400
    p30 = [(t, v) for t, v in pts if cut <= t <= NOW.timestamp() + 7200]
    sm = summarize(p30, spec.get("unit", "ft")) if p30 else dict(n=0)
    log.update(status="STALE" if sm.get("n", 0) == 0 or sm["age_h"] > LIVE_MAX_AGE_H else "LIVE", summary=sm)
    if log["status"] != "LIVE":
        RUNLOG.append(log); print("STALE/EMPTY", lid, spec["station"], sm); return
    hp, hy, hmeta = None, None, {}
    if spec.get("hist") and not args.no_history:
        key = spec.get("histKey") or (spec["prov"], spec["station"], spec["series"])
        if key not in _HCACHE:
            fn = f"{safe(key[0])}_{safe(key[1])}_{safe(key[2])}.csv.gz"
            fp = f"{HIST}/{fn}"
            d, nout = None, 0
            if args.reuse_history and os.path.exists(fp) and dt.date.fromtimestamp(os.path.getmtime(fp)) == dt.date.today():
                d, nout = drop_outliers(load_hist_file(fp), spec.get("valid"))
            else:
                try:
                    d = spec["hist"]()
                    if d:
                        d, nout = drop_outliers(d, spec.get("valid"))
                except Exception as e:  # noqa
                    d = None; print("hist ERR", key, e)
            _OUTL[key] = nout
            if d:
                with gzip.open(fp, "wt", newline="") as f:
                    w = csv.writer(f)
                    for k in sorted(d):
                        w.writerow([k, round(d[k], 4)])
                _HCACHE[key] = (f"history/{fn}", d)
            else:
                _HCACHE[key] = (None, None)
        hp, d = _HCACHE[key]
        if d:
            yc = year_completeness(d)
            hy = [min(d)[:4], max(d)[:4]]
            hmeta = dict(histOutliersDropped=_OUTL.get(key, 0), completeYears=yc["completeYears"], maxConsecutiveYears=yc["maxConsecutive"], histDays=yc["nDays"], histFirstDay=min(d), histLastDay=max(d))
    rec = dict(lakeId=lid, prov=spec["prov"], origin=spec["origin"], relay=spec.get("relay", False), station=spec["station"], stationName=spec["stationName"],
               lat=spec["lat"], lon=spec["lon"], series=spec["series"], unit="ft", family=spec["family"], vdatum=spec["vdatum"], lastObs=sm["last_t"],
               ageH=sm["age_h"], n30=sm["n"], medFt=sm["med_ft"], lastFt=sm["last_ft"], fullPoolHint=spec.get("fullPoolHint"), histPath=hp,
               histYears=[int(hy[0]), int(hy[1])] if hy else None, apiUrl=spec["apiUrl"], pageUrl=spec["pageUrl"], notes=spec.get("notes", ""))
    rec.update(hmeta)
    if spec.get("nativeUnit") and spec["nativeUnit"] != "ft":
        rec["nativeUnit"] = spec["nativeUnit"]
    CAND.append(rec); log["completeYears"] = hmeta.get("completeYears")
    RUNLOG.append(log)
    print(f"LIVE {lid:32s} {spec['prov']:8s} {spec['station']:22s} age={sm['age_h']:6.1f}h n30={sm['n']:5d} med={sm['med_ft']:9.2f} last={sm['last_ft']:9.2f} hist={hmeta.get('completeYears')}y {hy}", flush=True)


def build_specs():
    S = []
    # ---- USBR PN hydromet
    HMU = "https://www.usbr.gov/pn-bin/instant.pl?list={st}%20fb&format=csv&start=YYYY-MM-DD&end=YYYY-MM-DD"
    HMD = "https://www.usbr.gov/pn-bin/daily.pl?list={st}%20fb&format=csv&start=1900-01-01&end=YYYY-MM-DD"
    hm = [
        # lakeId, st, tz, name, lat, lon, family, vdatum, instant, notes
        ("Lake Cascade|ID", "csc", BOISE, "Cascade Dam and Lake Cascade at Cascade, Idaho", 44.525, -116.0503, "elev", "unknown", True,
         "USBR Hydromet FB = forebay elevation ft (4815.5 ft; directory full pool 4828). RISE 129979 for the same series lags ~13 d; hydromet is the live copy. Times are station-local (MDT)."),
        ("Crescent Lake|OR", "cre", PT, "Crescent Lake near Crescent, OR", 43.5017, -121.9735, "elev", "unknown", True,
         "USBR Hydromet FB forebay elevation ft (4825.8; directory full pool 4845). Same value republished by NWRFC CSDO3MFR and CWMS NWDP CRE. RISE 129880 lags ~13 d."),
        ("Potholes Reservoir|WA", "pot", PT, "Potholes Reservoir and O'Sullivan Dam", 46.9831, -119.2755, "elev", "unknown", False,
         "Hydromet instant.pl returns no rows for POT; daily.pl FB is live to yesterday (daily mean ft). Directory full pool 1046.5; POT is drawn down seasonally (1030.8 ft Oct). RISE 132564 lags ~13 d."),
        ("Banks Lake|WA", "bnk", PT, "Banks Lake and Dry Falls Dam", 47.6171, -119.2993, "elev", "unknown", True,
         "USBR Hydromet FB (1568.1 ft; directory full pool 1570). Also CWMS NWDP BNK.Elev-Lake daily 1961-. RISE 129466 has no recent data."),
        ("Henrys Lake|ID", "hen", BOISE, "Henrys Lake Dam on Henrys Fork nr. Lake, ID", 44.5975, -111.3528, "stage", "local", True,
         "LOCAL-DATUM STAGE (ft on dam gauge; 12.9 ft now, record 17.16 ft Jun-2023), NOT elevation. Gauge-zero elevation is not published by USBR; USGS site 13039000 (same gauge, 00065 gage height 12.7) lists altitude 6462.71 ft NAVD88 (gauge datum) -> elevation ~ stage + 6462.71 (NAVD88) if that altitude is the gauge datum. NWPS impacts: 16.61 ft = 100% full WITH boards, 15.09 ft = full WITHOUT boards. Lead calibration (usgs_stage_calibration.json) found 86% of 58 USGS LK sites agree within 1 ft between stage+alt_va and the elevation parameter, so the alt_va reading is probably the gauge datum. Directory full pool 6473.86 is inconsistent with 6462.71+15.09 = 6477.8 (NAVD88 vs NGVD29 offset ~3 ft explains most). Verifier must confirm."),
        ("Payette Lake|ID", "pay", BOISE, "Payette Lake at McCall, Idaho", 44.9122, -116.1193, "stage", "local", True,
         "LOCAL-DATUM STAGE (1.99 ft). USGS site 13238500 (identical gauge/values) lists gage datum altitude 4981.73 ft NGVD29 -> elevation ~ 4983.72 ft NGVD29 (directory full pool 4988.8 => full stage ~7.07 ft; verify against history max)."),
    ]
    for lid, st, tz, nm, la, lo, fam, vd, inst, note in hm:
        S.append(dict(lakeId=lid, prov="usbr-pnhm", origin="usbr", station=st.upper(), stationName=nm, lat=la, lon=lo, series="FB", family=fam, vdatum=vd,
                      apiUrl=(HMU if inst else HMD).format(st=st), pageUrl="https://www.usbr.gov/pn/hydromet/", notes=note,
                      valid=((-5, 15) if st == "pay" else None),
                      recent=(lambda st=st, tz=tz, inst=inst: hm_recent(st, tz, instant=inst)), hist=(lambda st=st: hm_hist(st))))
    # ---- CDEC
    cd = [("Almanor|CA", "ALM", "LAKE ALMANOR (PG&E)", 40.218, -121.173, "D", "Sensor 6 (RES ELE) is DAILY only for ALM (no event/hourly); last value 1-2 days old. Daily record 1985- with gaps (11 complete years by the 90% rule; 23 gross outliers such as -1 or 959746 ft are dropped). Operator PG&E; directory full pool 4494 (4484.6 ft Oct = drawdown). USGS 11399000 (Lake Almanor at Prattville) has no iv/dv series."),
          ("Berryessa|CA", "BER", "BERRYESSA (USBR Monticello)", 38.513, -122.104, "E", "Event (15-30 min) + hourly + daily sensor 6 RES ELE ft, USBR operator; 428.2 ft vs 440 full pool. RISE 10785 lags 9-13 d; CDEC is the live copy.")]
    for lid, st, nm, la, lo, dur, note in cd:
        S.append(dict(lakeId=lid, prov="cdec", origin="usbr" if st == "BER" else "pge", station=st, stationName=nm, lat=la, lon=lo, series="6.RES_ELE", family="elev", vdatum="unknown",
                      apiUrl=f"https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet?Stations={st}&SensorNums=6&dur_code={dur}&Start=YYYY-MM-DD&End=YYYY-MM-DD",
                      pageUrl=f"https://cdec.water.ca.gov/dynamicapp/staMeta?station_id={st}", notes=note + " Event/hourly times are PST (UTC-8, no DST).",
                      valid=((4380, 4505) if st == "ALM" else (300, 460)),
                      recent=(lambda st=st, dur=dur: cdec_recent(st, dur)), hist=(lambda st=st: cdec_hist(st))))
    # ---- USGS
    us = [
        ("Great Salt Lake|UT", "10010100", "62614", "elev", "GREAT SALT LAKE NEAR SALINE, UT", "NGVD29", "North-arm gauge (lat 41.255, north of the railroad causeway); NWPS GSLU1 is a relay of this series. Directory point is 17.7 km away; GSL is one hydrologic lake but north and south arms differ by up to ~1-2 ft because of the railroad causeway."),
        ("Great Salt Lake|UT", "10010000", "62614", "elev", "GREAT SALT LAKE AT SALTAIR BOAT HARBOR, UT", "NGVD29", "South-arm gauge, longest record (daily 1900-). 49.6 km from directory point."),
        ("Great Salt Lake|UT", "10010024", "62614", "elev", "GSL S. SIDE OF CAUSEWAY, 6 MILES E OF LAKESIDE, UT", "NGVD29", "South arm at the causeway (NOT the north arm; the wave-1 brief called 10010024 Saline, but Saline is 10010100); daily 2018-."),
        ("Great Salt Lake|UT", "10010027", "62614", "elev", "GSL N. SIDE OF CAUSEWAY, 6 MILES E OF LAKESIDE, UT", "NGVD29", "North arm at the causeway (daily 2018-)."),
        ("Upper Klamath Lake|OR", "11507001", "62615", "elev", "UPPER KLAMATH LAKE NR K.FALLS (WEIGHT/MEAN ELEV) OR", "NAVD88", "62615 = elevation above NAVD88 (4140.7 ft). Same site publishes 72275 = USBR Klamath Basin (USBRKB) datum, ~2.0 ft LOWER (4138.7); the directory's 4143 full pool is on the USBRKB datum, so compare 72275 to it. Weighted mean of several lake gauges."),
        ("Upper Klamath Lake|OR", "11507001", "72275", "elev", "UPPER KLAMATH LAKE NR K.FALLS (WEIGHT/MEAN ELEV) OR", "local", "72275 = elevation above USBR Klamath Basin (USBRKB) datum (documented as such by USGS; 4138.7 ft = 4.3 ft below the 4143 directory full pool). Weighted mean of lake gauges; best match to the directory's USBR-datum full pool."),
        ("Upper Klamath Lake|OR", "11505900", "72275", "elev", "UPPER KLAMATH LAKE AT RATTLESNAKE POINT, OR", "local", "USBRKB-datum elevation; single gauge, western shore. Archive before 1986-10-01 is stored as gauge height (~40 ft, i.e. elevation - 4100); those days are dropped (histOutliersDropped)."),
        ("Upper Klamath Lake|OR", "11505800", "72275", "elev", "UPPER KLAMATH LAKE AT ROCKY POINT, OR", "local", "USBRKB-datum elevation; single gauge, northwest shore. Archive before 1986-10-01 is stored as gauge height (~40 ft); those days are dropped (histOutliersDropped)."),
        ("Upper Klamath Lake|OR", "11507000", "72275", "elev", "UPPER KLAMATH LAKE NEAR KLAMATH FALLS, OR", "local", "USBRKB-datum elevation at the Link River/UKL outlet gauge (wave 1 saw this site only via 72020, which is not live). Archive before 1987-10-01 is stored as gauge height (5-40 ft); those days are dropped (histOutliersDropped)."),
        ("Georgetown Lake|MT", "12325000", "62615", "elev", "Georgetown Lake near Philipsburg, MT", "NAVD88", "62615 = elevation above NAVD88 (6428.7 ft; directory has no full pool; Georgetown Lake normal pool is commonly cited ~6430 ft, unverified). Daily since 2013-05."),
        ("Eagle Nest Lake|NM", "07205500", "62614", "elev", "EAGLE NEST LAKE NR EAGLE NEST, NM", "NGVD29", "8160.0 ft; no full pool in directory (NM State Parks publishes none). Daily since 2013-10."),
        ("Henrys Lake|ID", "13039000", "00065", "stage", "HENRYS LAKE NR LAKE ID", "local", "USGS gage height ft (same dam gauge as USBR HEN FB); site altitude 6462.71 ft NAVD88 (alt_va, gauge datum) per USGS site record. Daily since 1977-10."),
        ("Payette Lake|ID", "13238500", "00065", "stage", "PAYETTE LAKE AT MCCALL ID", "local", "USGS gage height ft; gauge datum altitude 4981.73 ft NGVD29 per USGS site record => elevation = stage + 4981.73. Daily since 1965-10."),
    ]
    for lid, site, par, fam, nm, vd, note in us:
        st = lambda site=site: usgs_site(site)
        S.append(dict(lakeId=lid, prov="usgs", origin="usgs", station=site, stationName=nm, lat=None, lon=None, series=par, family=fam, vdatum=vd.split(" ")[0] if vd != "local" else "local",
                      apiUrl=f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={site}&parameterCd={par}&period=P31D&siteStatus=all", pageUrl=f"https://waterdata.usgs.gov/monitoring-location/{site}/",
                      notes=note, _site=site, valid=((4000, 4200) if (site.startswith("1150") or site == "11507000") and par == "72275" and site != "11507001" else None),
                      recent=(lambda site=site, par=par: usgs_iv(site, par)[0]), hist=(lambda site=site, par=par: usgs_dv(site, par))))
    # ---- SRP
    for lid, mid, sid, nm, fp, la, lo in [("Roosevelt|AZ", 354, 8, "Roosevelt Lake (Roosevelt Dam)", 2150.78, 33.6716, -111.1612),
                                          ("Apache|AZ", 395, 23, "Apache Lake (Horse Mesa Dam)", 1914.0, 33.5907, -111.3435),
                                          ("Canyon|AZ", 399, 24, "Canyon Lake (Mormon Flat Dam)", 1660.5, 33.5536, -111.4428),
                                          ("Saguaro|AZ", 405, 25, "Saguaro Lake (Stewart Mountain Dam)", 1529.0, 33.5664, -111.5364)]:
        S.append(dict(lakeId=lid, prov="srp", origin="srp", station=str(sid), stationName=nm, lat=la, lon=lo, series=f"Elevation.Official.{mid}", family="elev", vdatum="unknown",
                      fullPoolHint=fp, apiUrl=f"{SRP}/getmeasurementdata?measurementId={mid}&units=ft&startDate=YYYY-MM-DD&endDate=YYYY-MM-DD", pageUrl=f"https://streamflow.watershedconnection.com/?location={urllib.parse.quote(nm)}",
                      notes=f"SRP Watershed Connection 'Official Elevation' (5-min, MST). fullPoolHint = SRP reservoirData.maxConservationElevation. Archive only from 2023-10-13 (dataAvailableFrom). Unauthenticated JSON used by SRP's public web page.",
                      recent=(lambda mid=mid: srp_recent(mid)), hist=(lambda mid=mid: srp_hist(mid))))
    # ---- Colorado DWR
    S.append(dict(lakeId="Dillon Reservoir|CO", prov="codwr", origin="denver-water", station="DILRESCO", stationName="DILLON RESERVOIR (Denver Water; CO DWR telemetry)", lat=39.6183, lon=-106.0656, series="ELEV", family="elev", vdatum="unknown",
                  apiUrl=f"{CO}/telemetrytimeseriesraw/?format=json&abbrev=DILRESCO&parameter=ELEV&startDate=MM/DD/YYYY&endDate=MM/DD/YYYY", pageUrl="https://dwr.state.co.us/Tools/Stations/DILRESCO",
                  notes="CDSS telemetry ELEV (15-min, MDT) 8980.7 ft vs 9017 ft full pool; daily archive 1987-06..2002 and 2021..now (nothing stored 2003-2020; about 15 complete years by the 90% rule; sentinel values such as 70235.7 and 14908.4 dropped).",
                  valid=(8700, 9030), recent=lambda: co_recent("DILRESCO"), hist=lambda: co_hist("DILRESCO")))
    # ---- NWRFC relays (operator telemetry)
    S.append(dict(lakeId="Lake Cushman|WA", prov="nwrfc", origin="tacoma-power", relay=True, station="CSHW1", stationName="NF SKOKOMISH - CUSHMAN DAM", lat=47.4247, lon=-123.2294, series="HF", family="elev", vdatum="unknown",
                  apiUrl="https://www.nwrfc.noaa.gov/xml/xml.cgi?id=CSHW1&pe=HF&dtype=b&numdays=30", pageUrl="https://www.nwrfc.noaa.gov/river/station/flowplot/flowplot.cgi?CSHW1",
                  notes="NWRFC XML hourly forebay elevation (UTC); only ~10 d retained (n30 reflects that). Tacoma Power (Cushman Dam, FERC licensee) is the data owner; Tacoma's own page links to NWRFC for lake levels. 712.8 ft vs 738 full (FERC range 415-425 ft is for Lower Cushman).",
                  recent=lambda: nwrfc("CSHW1")[0], hist=None))
    S.append(dict(lakeId="Riffe Lake|WA", prov="nwrfc", origin="tacoma-power", relay=True, station="MSRW1", stationName="COWLITZ - MOSSYROCK RESERVOIR", lat=46.5353, lon=-122.4236, series="HF", family="elev", vdatum="unknown",
                  apiUrl="https://www.nwrfc.noaa.gov/xml/xml.cgi?id=MSRW1&pe=HF&dtype=b&numdays=30", pageUrl="https://www.nwrfc.noaa.gov/river/station/flowplot/flowplot.cgi?MSRW1",
                  histKey=("usgs", "14234800", "62614"),
                  notes="NWRFC hourly forebay elevation (UTC, ~10 d retained) relaying Tacoma Power's Mossyrock/Riffe Lake pool (705.2 ft; Tacoma draws to 745 ft by winter, max 749). histPath is NOT this series: it is USGS 14234800 'RIFFE LAKE NEAR MOSSYROCK' NGVD29 62614 daily 1973-10..2026-08-24 (that gauge stopped reporting, so it is a history-only twin of the same pool; verify the two agree where they overlap). CWMS NWDP MOS.Elev-Forebay.Inst.0.0.MIXED-REV is cataloged 1974- but the data API returns zero rows (dead).",
                  recent=lambda: nwrfc("MSRW1")[0], hist=lambda: usgs_dv("14234800", "62614")))
    # ---- CWMS NWDP
    S.append(dict(lakeId="Lake Union|WA", prov="cwms-nwdp", origin="usace", station="LWSC", stationName="Lake Washington Ship Canal (Hiram M. Chittenden Locks)", lat=47.6649, lon=-122.3946, series="Elev-Lake.Ave.1Hour.1Hour.IRIDIUM-REV", family="elev", vdatum="unknown",
                  apiUrl=f"{CWMS}/timeseries?name=LWSC.Elev-Lake.Ave.1Hour.1Hour.IRIDIUM-REV&office=NWDP&begin=YYYY-MM-DDT00:00:00Z&end=YYYY-MM-DDT00:00:00Z&unit=EN", pageUrl="https://www.nws.usace.army.mil/Missions/Civil-Works/Locks-and-Dams/Chittenden-Locks/",
                  notes="USACE Seattle District lake-side gauge at the Locks: Lake Washington/Lake Union/Ship Canal pool (20.4 ft; regulated 20-22 ft NGVD29-like). Directory 'full pool 16' is wrong for this lake (pool is ~21 ft). Hourly since 2001-07; also LWSC-Elev-Lake.Ave.~1Day.0.NWSRADIO-REV 1998-.",
                  recent=lambda: cwms_recent("LWSC.Elev-Lake.Ave.1Hour.1Hour.IRIDIUM-REV"), hist=lambda: cwms_hist("LWSC.Elev-Lake.Ave.1Hour.1Hour.IRIDIUM-REV")))
    S.append(dict(lakeId="Lake Roosevelt (FDR)|WA", prov="cwms-nwdp", origin="usbr", station="GCL", stationName="Grand Coulee Dam (forebay = Lake Roosevelt)", lat=47.95667, lon=-118.9805, series="Elev-Forebay.Inst.1Hour.0.CBT-REV", family="elev", vdatum="unknown",
                  apiUrl=f"{CWMS}/timeseries?name=GCL.Elev-Forebay.Inst.1Hour.0.CBT-REV&office=NWDP&begin=YYYY-MM-DDT00:00:00Z&end=YYYY-MM-DDT00:00:00Z&unit=EN", pageUrl="https://www.usbr.gov/pn/hydromet/rtindex/res.html",
                  notes="Grand Coulee forebay IS Lake Roosevelt (1285.3 ft; full pool 1290). Hourly 1960-; wave-1 rejected on name only. Daily history from GCL.Elev-Forebay.Ave.~1Day.1Day.CBT-REV. Same value on NWRFC GCDW1OTX; USGS 12436000 lags 12+ days.",
                  recent=lambda: cwms_recent("GCL.Elev-Forebay.Inst.1Hour.0.CBT-REV"), hist=lambda: cwms_hist("GCL.Elev-Forebay.Ave.~1Day.1Day.CBT-REV")))
    # ---- RISE (Flaming Gorge; same reservoir under two directory ids)
    for lid in ("Flaming Gorge Reservoir|UT", "Flaming Gorge Reservoir|WY"):
        S.append(dict(lakeId=lid, prov="rise", origin="usbr", station="341", stationName="Flaming Gorge Reservoir Dam and Powerplant (RISE item 341)", lat=40.97789, lon=-109.57304, series="Lake/Reservoir Elevation", family="elev", vdatum="unknown",
                      apiUrl="https://data.usbr.gov/rise/api/result?itemId=341&dateTime[after]=YYYY-MM-DD&itemsPerPage=2000", pageUrl="https://data.usbr.gov/catalog/341",
                      notes="Daily RISE series lags ~2 d (acceptable). Reservoir straddles UT/WY: the dam is in Daggett Co., UT (lat 40.98); the WY directory point (41.40,-109.50) is the north reservoir arm. Wave-1 R4 rejected the WY entry on state only; both ids describe ONE pool (6006.2 ft vs 6040 full pool).",
                      recent=lambda: rise_recent(341), hist=lambda: rise_hist(341)))
    # ---- Utah Lake
    S.append(dict(lakeId="Utah Lake|UT", prov="utahlake", origin="utah-lake-commission", relay=True, station="ULC-CALC_UL_ELEVATION", stationName="Utah Lake (utahlake.gov live data feed)", lat=40.22, lon=-111.80, series="CALC_UL_ELEVATION", family="elev", vdatum="unknown",
                  apiUrl="POST https://utahlake.gov/wp-admin/admin-ajax.php  action=ulc_data&refresh=false", pageUrl="https://utahlake.gov/water-levels/",
                  fullPoolHint=4489.045,
                  notes="Undocumented WordPress-ajax feed behind the Utah Lake Commission's public page: current elevation (hourly, MDT) + 90 daily means; it states data come from the Utah Division of Water Rights ('All data provisional'). Compromise (full) elevation 4489.045 ft per same page. 4484.2 ft now (-4.8 ft). Only ~90 d history here; RISE item 4514 (USBR daily) ends 2020-06 and can supply the older record if the datum is confirmed identical.",
                  recent=lambda: utahlake()[0], hist=lambda: {k: v for k, v in utahlake()[1].items() if k < TODAY}))
    return S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-history", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--reuse-history", action="store_true", help="reuse history files written today instead of re-downloading")
    args = ap.parse_args()
    only = set(a for a in args.only.split(",") if a)
    for spec in build_specs():
        if only and spec["prov"] not in only:
            continue
        if spec.get("_site"):          # fill lat/lon from USGS site record
            si = usgs_site(spec["_site"])
            spec["lat"], spec["lon"] = si.get("lat"), si.get("lon")
            spec["notes"] += f" [USGS site altitude {si.get('alt')} {si.get('altdatum')}]"
        if spec["prov"] == "nwrfc":
            _, meta = nwrfc(spec["station"])
            if meta.get("lat"):
                spec["lat"], spec["lon"] = meta["lat"], meta["lon"]
        emit(spec, args)
    with open(f"{B2}/cand/west.jsonl", "w") as f:
        for r in CAND:
            f.write(json.dumps(r) + "\n")
    json.dump(RUNLOG, open(f"{B2}/raw/west_run.json", "w"), indent=1)
    print("candidates", len(CAND), "lakes", len({r['lakeId'] for r in CAND}), "with >=5 complete yrs", len({r['lakeId'] for r in CAND if (r.get('completeYears') or 0) >= 5}))


if __name__ == "__main__":
    main()
