"""binding2 source scout, area 'se' (FL GA SC NC VA WV AL MS LA AR TN TX OK KY). Regenerates cand/se.jsonl + history/*.csv.gz.

Usage:  python src_se.py [duke aep sjrwmd usace usgs nwps ...]   (no args = everything)
All requests are read-only GETs (<= ~1 req/s per host). No accounts / keys. Output under Sector_Research_Data/lake-brain/binding2/.
Sources that WORK: Duke Energy Lake View API (api.hydro-derived.duke-energy.app), AEP plant-levels API, SJRWMD WISKI-Web static zarr store
(mdp.sjrwmd.com/data/internet), USACE CWMS data API, USGS NWIS (waterservices), NOAA NWPS API.
"""
import re
import sys
from src_se_lib import *

CATALOG = {}


def load_catalog():
    if CATALOG:
        return
    for l in open("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/binding/catalog.jsonl"):
        d = json.loads(l)
        CATALOG[d["sid"]] = d


def cat_loc(sid):
    load_catalog()
    d = CATALOG.get(sid) or {}
    return d.get("name"), d.get("lat"), d.get("lon")


# =========================================================================== helpers: CWMS / USGS / NWPS
CW_B = "https://cwms-data.usace.army.mil/cwms-data"


def cwms_recent_pts(office, tsid, days=35):
    b = (NOW - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    e = (NOW + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return cwms_ts(office, tsid, b, e)


def cwms_daily_hist(office, tsid, since="1900-01-01", until=None):
    """Full history of a CWMS series -> {YYYY-MM-DD(UTC): mean ft}. Pages the data API (page-size 100000)."""
    e = until or (NOW + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    pts, info = cwms_ts(office, tsid, f"{since}T00:00:00Z", e)
    if pts is None:
        return None
    return daily_from_pts(pts)


def usgs_iv_pts(site, param, days=35):
    u = (f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={site}&parameterCd={param}&period=P{days}D&siteStatus=all")
    s, d = get_json(u, timeout=120, sleep=1.0)
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
                    if x != nd:
                        pts.append((dt.datetime.fromisoformat(v["dateTime"]).timestamp(), x))
    return pts, u


def usgs_dv_hist(site, param, stat="00003"):
    u = (f"https://waterservices.usgs.gov/nwis/dv/?format=json&sites={site}&parameterCd={param}&statCd={stat}&startDT=1900-01-01&endDT={NOW:%Y-%m-%d}&siteStatus=all")
    s, d = get_json(u, timeout=300, sleep=1.0)
    out = {}
    if d:
        for ts in d["value"]["timeSeries"]:
            nd = ts["variable"].get("noDataValue", -999999)
            for blk in ts["values"]:
                for v in blk["value"]:
                    try:
                        x = float(v["value"])
                    except Exception:
                        continue
                    if x != nd:
                        out[v["dateTime"][:10]] = x
    return out, u


def nwps_series(lid):
    s, d = get_json(f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}/stageflow/observed", timeout=60, sleep=0.8)
    pts = []
    for r in (d or {}).get("data", []):
        v = r.get("primary")
        if v is not None and v > -900:
            pts.append((dt.datetime.fromisoformat(r["validTime"].replace("Z", "+00:00")).timestamp(), v))
    return pts, d


def nwps_meta(lid):
    s, d = get_json(f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}", timeout=60, sleep=0.8)
    return d or {}


# =========================================================================== Duke Energy (Lake View API)
DUKE_API = "https://api.hydro-derived.duke-energy.app"
# unbound lakeId -> (Duke LocationId, display)
DUKE_MAP = {
    "Lake Norman|NC": 14, "Lake Wylie|SC": 25, "Lake Wateree|SC": 24, "Lake Keowee|SC": 18, "Lake Jocassee|SC": 17,
    "Lake James|NC": 12, "Lake Hickory|NC": 21, "Lake Robinson|SC": 38,
}
DUKE_COORD = {  # dam coordinates from NWPS / directory (centroid of directory lake is used when none)
}


def run_duke():
    print("== Duke Energy")
    s, cur = get_json(f"{DUKE_API}/lakes/current-level", timeout=60)
    json.dump(cur, open(f"{RAW_D}/duke_current_level.json", "w"))
    by_loc = {x["LocationId"]: x for x in cur}
    for lakeId, loc in DUKE_MAP.items():
        c = by_loc[loc]
        s, r = get_json(f"{DUKE_API}/lakes/operating-range/{loc}", timeout=120, sleep=1.0)
        hist_rows = r["history"]
        elev_txt = c["Elevation"]
        m = re.match(r"\s*([\d.]+)", elev_txt)
        full_abs = float(m.group(1))
        mx = float(c["Max"])
        absolute = abs(full_abs - mx) < 1.0   # Duke publishes true NGVD29 elevation as 'Actual' (Belews/Hyco/Robinson style)
        daily = {h["date"]: float(h["average"]) for h in hist_rows if h.get("average") not in (None, "")}
        # live window: daily averages (30 d) + the current instantaneous reading
        last_dt = dt.datetime.fromisoformat(c["Date"]).replace(tzinfo=dt.timezone(dt.timedelta(hours=-4)))  # site time is US/Eastern (EDT in Oct)
        pts = [(dt.datetime.fromisoformat(d + "T12:00:00+00:00").timestamp(), v) for d, v in daily.items()
               if d >= (NOW - dt.timedelta(days=31)).strftime("%Y-%m-%d") and d < NOW.strftime("%Y-%m-%d")]
        pts.append((last_dt.timestamp(), float(c["Actual"])))
        p = PROFILE[lakeId]
        off = None if absolute else round(full_abs - mx, 3)
        note = (f"Duke 'Actual' = lake level; Duke 'Max'={c['Max']} is full-pond/top of operating range and Duke's 'Elevation'={elev_txt!r} is the elevation of that mark. "
                + ("Actual is already absolute NGVD29 (Max ~= Elevation). " if absolute else
                   f"Actual is a LOCAL stage where {mx:g} ft == full pond {full_abs:g} ft NGVD29; documented offset to NGVD29 = Elevation - Max = {off:+g} ft (gauge zero {off:g} ft NGVD29). "
                   "Offset is NOT applied to lastFt/medFt/history (stage family); verifier decides. ")
                + f"Duke target={c['Target']}, min={c['Min']}. Series: current-level 'Actual' (instantaneous, ~15-60 min cadence) + operating-range history 'average' (daily mean, 2021-10-13..today; API serves a rolling 5 y window). "
                + "Cross-checks: NWPS gauge relays agree within 0.1-0.2 ft; Hyco/Belews absolute values agree with USGS 02077280.")
        cand = add_cand(lakeId, "duke", "duke", loc, c["LakeDisplayName"], p["lat"], p["lon"], "lake-level-Actual", "elev" if absolute else "stage",
                        "NGVD29" if absolute else "local", pts, fullPoolHint=full_abs, hist=daily,
                        apiUrl=f"{DUKE_API}/lakes/current-level ; {DUKE_API}/lakes/operating-range/{loc}", pageUrl="https://lakes.hydro-derived.duke-energy.app/ (Duke Energy Lake View)",
                        notes=note)
        if cand:
            cand["stageFullPond"] = None if absolute else mx
            cand["offsetToNGVD29Ft"] = off
            cand["offsetSource"] = None if absolute else "Duke Lake View API fields Elevation (AMSL NGVD29) and Max (=100 ft local stage)"
            cand["dukeLocationId"] = loc
            if lakeId == "Lake Jocassee|SC":   # independent absolute series (USACE SAS Jocassee.Stage.Rev, NGVD29 ft) to validate the documented offset
                pts2, _ = cwms_ts("SAS", "Jocassee.Stage.Inst.1Hour.0.Rev-SHEF_SAS", "2021-10-13T00:00:00Z", NOW.strftime("%Y-%m-%dT%H:%M:%SZ"))
                d2 = daily_from_pts(pts2 or [])
                diffs = [d2[k] - daily[k] for k in d2 if k in daily]
                if diffs:
                    cand["offsetValidation"] = dict(against="USACE SAS Jocassee.Stage.Inst.1Hour.0.Rev-SHEF_SAS (absolute ft)", n=len(diffs), medianDiff=round(float(np.median(diffs)), 3),
                                                    p05=round(float(np.percentile(diffs, 5)), 3), p95=round(float(np.percentile(diffs, 95)), 3), expectedOffset=off)
                    cand["notes"] += f" OFFSET INDEPENDENTLY VALIDATED: USACE absolute Jocassee stage minus Duke local stage = {cand['offsetValidation']['medianDiff']} ft median over {len(diffs)} days (expected {off})."
            cand["lat_note"] = "lat/lon = directory lake centroid (Duke API publishes no coordinates)"


# =========================================================================== AEP / Appalachian Power (Smith Mountain Lake)
def run_aep():
    print("== AEP")
    u = "https://aepcom-api.aep.com/api/hydro/plant-levels"
    s, d = get_json(u, timeout=60)
    json.dump(d, open(f"{RAW_D}/aep_plant_levels.json", "w"))
    for loc in d["hydroPlantLevelsAndFlows"]:
        for pr in loc["riverFlowData"]:
            if pr["project"] == "Smith Mountain":
                v = float(pr.get("forebayActual") or pr["forbayActual"])  # sic: API field is misspelled for some payloads
                p = PROFILE["Smith Mountain Lake|VA"]
                add_cand("Smith Mountain Lake|VA", "aep", "aep-appalachian-power", "SMFB", "Smith Mountain forebay (SMFB)", p["lat"], p["lon"], "forebayActual", "elev", "unknown",
                         [(NOW.timestamp(), v)], fullPoolHint=float(pr["normalFullPond"]), hist=None, apiUrl=u,
                         pageUrl="https://www.smithmountainproject.com/lake-levels/",
                         notes=("Single instantaneous value per call (no observation timestamp for the SM forebay, lastObs = fetch time; no history endpoint; n30=1). "
                                f"Operator-stated normal full pond {pr['normalFullPond']} ft (datum not stated, presumably NGVD29/MSL). Level swings 1-2 ft daily (pumped storage). "
                                "Poll-and-archive would be needed to build history. Leesville Lake forebay (LEFB) is in the same payload."))


# =========================================================================== SJRWMD WISKI-Web zarr store
SJ_SPECS = [  # lakeId, station_no, series description
    ("Apopka|FL", "03919/SW_03919_LKAPOPJAKEVOSS", "Lake Apopka Jake Voss (in-lake gauge, since 2020)"),
    ("Apopka|FL", "01928/SW_01928_LKAPOPNP", "Lake Apopka N Pumphouse (lake-side stage, since 2005)"),
    ("Harris|FL", "03005/SW_03005_HARRMELC", "Lake Harris (Harris Chain, since 1993)"),
    ("Griffin|FL", "03921/SW_03921_LKGRIFEMERALDA", "Lake Griffin at Emeralda (since 2020)"),
    ("Jesup|FL", "00141/SW_00141_LJESOV", "Lake Jesup Oviedo (since 1996)"),
    ("Lochloosa|FL", "07148/SW_07148_LKLOCH", "Lochloosa Lake (since 1995)"),
    ("Orange Lake|FL", "00261/SW_00261_ORLKBD", "Orange Lake Boardman (since 1995)"),
    ("Lake George|FL", "00235/SW_00235_LKGEOM", "Lake George 'Middle Rd' (north-central lake gauge)"),
]


def sj_station_meta():
    import pyarrow.parquet as pq
    p = f"{RAW_D}/sj_stations.parquet"
    if not os.path.exists(p):
        s, b = http_get(f"{SJ}/metadata/w7/stations.parquet", binary=True)
        open(p, "wb").write(b)
    return {r["station_no"]: r for r in pq.read_table(p).to_pylist()}


def sj_cmd_tail(path, ndays=35):
    """Last ndays of continuous series (Cmd_E) by reading only the final chunk of time/data."""
    base = f"{SJ}/timeseries/{path}/Cmd_E"
    s, b = http_get(f"{base}/time/.zarray", sleep=0.5)
    zm = json.loads(b)
    n, ch = zm["shape"][0], zm["chunks"][0]
    last = (n - 1) // ch
    start = last * ch
    # time chunk
    s, c = http_get(f"{base}/time/{last}", binary=True, sleep=0.5)
    tdt = np.dtype(zm["dtype"])
    t = np.frombuffer(blosc_decompress(c) if zm["compressor"] else c, tdt)[:n - start]
    s, b2 = http_get(f"{base}/data/.zarray", sleep=0.5)
    dm = json.loads(b2)
    s, c = http_get(f"{base}/data/{last}.0", binary=True, sleep=0.5)
    arr = np.frombuffer(blosc_decompress(c) if dm["compressor"] else c, np.dtype(dm["dtype"])).reshape(dm["chunks"])[:n - start]
    return t.astype(float), arr[:, 0]


def run_sjrwmd():
    print("== SJRWMD WISKI-Web")
    meta = sj_station_meta()
    for lakeId, path, desc in SJ_SPECS:
        site, st = path.split("/")
        m = meta[st]
        try:
            t, v = sj_cmd_tail(f"{path}/Water_Level")
        except Exception as e:
            print("   tail fail", st, e); continue
        cut = NOW.timestamp() - 35 * 86400
        pts = [(float(a), float(b)) for a, b in zip(t, v) if a >= cut and not np.isnan(b)]
        # daily history: Day_Mean (published daily mean)
        base = f"{path}/Water_Level/Day_Mean"
        tt, dd = sj_array(base + "/time"), sj_array(base + "/data")
        hist = {}
        if tt is not None and dd is not None:
            for a, b in zip(tt, dd[:, 0]):
                if not np.isnan(b) and abs(b) < 9000:
                    hist[iso(float(a))[:10]] = float(b)
        p = PROFILE[lakeId]
        add_cand(lakeId, "sjrwmd", "sjrwmd", st, f"{m['site_name']} ({st})", m["station_latitude"], m["station_longitude"], "Water_Level/Cmd_E", "elev",
                 "NGVD29", pts, fullPoolHint=float(p["fullPoolFt"]) if p["fullPoolFt"] not in ("", None) else None, hist=hist,
                 apiUrl=f"{SJ}/timeseries/{path}/Water_Level/Cmd_E/{{time,data}} (zarr v2 + blosc/lz4), Day_Mean/{{time,data}}; catalog {SJ}/filters/ts_sw_wl.parquet",
                 pageUrl="https://mdp.sjrwmd.com/ (SJRWMD WISKI Web, Hydrologic data search)",
                 notes=(f"{desc}. SJRWMD continuous water level 'Cmd_E' (15-min). Datum not stated in the store; Cmd_E is the NGVD29 series (a parallel 'Cmd_E_NAVD88' series exists "
                        f"for 127 other stations), value plausibility vs directory fullPool {p['fullPoolFt']}: last={pts[-1][1]:.2f}. Transmission: {m['DATA_TRANSMISSION']}. "
                        "Daily history = published 'Day_Mean' (UTC date of fixed-EST day start). Provisional quality code 200 for recent data."))


# =========================================================================== USACE / USGS / NWPS composite candidates
def run_usace():
    print("== USACE CWMS + USGS")
    # ---- East Lake Tohopekaliga (SFWMD data via CWMS SAJ)
    nm, la, lo = cat_loc("cwms:SAJ:E Tohopekaliga.Elev.Inst.1Hour.0.SFWMD-Raw")
    tsid = "E Tohopekaliga.Elev.Inst.1Hour.0.SFWMD-Raw"
    pts, info = cwms_recent_pts("SAJ", tsid)
    hist = cwms_daily_hist("SAJ", tsid, "2010-01-01")
    add_cand("East Lake Tohopekaliga|FL", "cwms-saj", "sfwmd", "SAJ:E Tohopekaliga", "East Lake Tohopekaliga (SFWMD stage via USACE CWMS SAJ)", la, lo, tsid, "elev", "NGVD29", pts,
             fullPoolHint=58.0, hist=hist, apiUrl=f"{CW_B}/timeseries?office=SAJ&name={tsid}&begin=...&end=...&unit=EN",
             pageUrl="https://water.usace.army.mil/ (Access2Water SAJ E Tohopekaliga)",
             notes="SFWMD DBHYDRO raw stage (NGVD29, native-datum NGVD-29) mirrored in USACE Jacksonville CWMS; wave 1 wrongly bound the neighbouring Lake Tohopekaliga (West) series. "
                   "DBHYDRO Insights API itself needs client credentials (not used). Lake regulation schedule top ~ 58 ft (profile).")
    tsid2 = "S59-Headwater.Elev.Ave.~1Day.1Day.SFWMD-Computed"
    pts2, _ = cwms_recent_pts("SAJ", tsid2)
    h2 = cwms_daily_hist("SAJ", tsid2, "2021-01-01")
    nm, la, lo = cat_loc("cwms:SAJ:" + tsid2)
    add_cand("East Lake Tohopekaliga|FL", "cwms-saj", "sfwmd", "SAJ:S59-Headwater", "S-59 headwater (East Lake Toho outlet structure)", la, lo, tsid2, "elev", "NGVD29", pts2,
             fullPoolHint=58.0, hist=h2, apiUrl=f"{CW_B}/timeseries?office=SAJ&name={tsid2}", pageUrl="https://my.sfwmd.gov/ (DBHYDRO site S59_H)",
             notes="Structure headwater at S-59 = East Lake Toho pool at the outlet; daily SFWMD-computed mean; history 2021+ only (4 complete years max).")

    # ---- Logan Martin (Alabama Power via CWMS SAM + NWPS CCSA1 relay)
    tsid = "LoganMartin.Elev.Inst.1Hour.0.Raw-APCO"
    pts, info = cwms_recent_pts("SAM", tsid)
    hist = cwms_daily_hist("SAM", tsid, "2017-01-01")
    nm, la, lo = cat_loc("cwms:SAM:" + tsid)
    add_cand("Logan Martin|AL", "cwms-sam", "alabama-power", "SAM:LoganMartin", nm or "Logan Martin (APC)", la, lo, tsid, "elev", "NGVD29", pts, fullPoolHint=465.0, hist=hist,
             apiUrl=f"{CW_B}/timeseries?office=SAM&name={tsid}", pageUrl="https://water.usace.army.mil/",
             notes="Alabama Power Company reservoir elevation (forebay of Logan Martin Dam, Coosa R.) published in USACE Mobile CWMS (vertical-datum-info native NGVD-29). "
                   "Wave 1 rejected on geometry (dam point is 1.6 km from the directory polygon centroid; dam is the lake's downstream end) - confirmed candidate: median ~465 ft vs full pool 465 ft.")
    pts, d = nwps_series("CCSA1")
    meta = nwps_meta("CCSA1")
    add_cand("Logan Martin|AL", "nwps", "alabama-power", "CCSA1", "Coosa River at Logan Martin Dam (NWPS CCSA1)", meta.get("latitude"), meta.get("longitude"), "HPIRZ pool", "elev", "NGVD29", pts,
             relay=True, fullPoolHint=465.0, hist=None, apiUrl="https://api.water.noaa.gov/nwps/v1/gauges/CCSA1/stageflow/observed", pageUrl="https://water.noaa.gov/gauges/CCSA1",
             notes="NWS relay of Alabama Power pool elevation (HPIRZ); agrees with CWMS LoganMartin series (464.1 vs 465.0 ft at slightly different times). 30-day window only.")

    # ---- Thurmond (Savannah District): USGS 02193900 00062 live; CWMS archive for deep history
    for lakeId in ("Clarks Hill / J.S. Thurmond|GA", "Lake Strom Thurmond (Clarks Hill)|SC"):
        pts, u = usgs_iv_pts("02193900", "00062")
        dv, udv = usgs_dv_hist("02193900", "00062")
        hist = dict(dv)
        # splice deeper USACE archive (daily pool elevation 1950-) before USGS record starts
        old = cwms_daily_hist("SAS", "Thurmond.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS", "1950-01-01")
        if old:
            first_usgs = min(dv) if dv else "9999"
            for k, v2 in old.items():
                if k < first_usgs:
                    hist[k] = v2
        add_cand(lakeId, "usgs", "usace", "02193900", "THURMOND LAKE NEAR PLUM BRANCH, SC (USGS 02193900, USACE-operated)", 33.84167, -82.345, "00062", "elev", "NGVD29", pts,
                 fullPoolHint=330.0, hist=hist, apiUrl=u + " ; " + udv, pageUrl="https://waterdata.usgs.gov/monitoring-location/02193900/",
                 notes="USGS reservoir elevation (00062, ft NGVD29) at J. Strom Thurmond Lake, lat/lon is the gauge in Plum Branch SC (reservoir body ~ 10 km above the dam). "
                       "Live ~15-min; this is the only live Thurmond pool source (CWMS SAS Thurmond.* and A2W are silent ~5 days; old USGS 02194500 ended 2001). "
                       "History: USGS dv 00003 from 2005, spliced before that with USACE SAS 'Thurmond.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS' daily pool (1950-). "
                       "Wave 1 rejected for state-mismatch (SC gauge vs GA entry); lake is the same SC/GA reservoir.")

    # ---- Kerr Lake (John H. Kerr): CWMS SAW + USGS 02079490
    for tsid in ("ROA JHK.Elev.Inst.5Minutes.0.USGS-raw",):
        pts, info = cwms_recent_pts("SAW", tsid)
        h5 = cwms_daily_hist("SAW", tsid, "2025-01-01")
        h15 = cwms_daily_hist("SAW", "ROA JHK.Elev.Inst.15Minutes.0.USGS-raw", "2012-01-01", "2025-04-01T00:00:00Z")
        dv, udv = usgs_dv_hist("02079490", "62614")
        hist = dict(dv)
        for src in (h15 or {}, h5 or {}):
            hist.update(src)
        nm, la, lo = cat_loc("cwms:SAW:" + tsid)
        add_cand("Kerr Lake (John H. Kerr)|NC", "cwms-saw", "usace", "SAW:ROA JHK", nm or "John H. Kerr Dam", la, lo, tsid, "elev", "NGVD29", pts, fullPoolHint=300.0, hist=hist,
                 apiUrl=f"{CW_B}/timeseries?office=SAW&name={tsid} ; {udv}", pageUrl="https://water.usace.army.mil/",
                 notes="USACE Wilmington CWMS pool elevation at Kerr Dam (USGS-sourced). Dam/gauge is in Boydton, Mecklenburg Co. VA; lake straddles VA/NC, so wave-1 state-check rejected "
                       "the NC-listed lake. Median 288.9 ft vs flood-control top 300 (conservation pool 295 per USACE). History = USGS dv 62614 (2005-2021) + CWMS 15-min (2012-2025) + 5-min (2025-).")
        pts, u = usgs_iv_pts("02079490", "62614")
        add_cand("Kerr Lake (John H. Kerr)|NC", "usgs", "usace", "02079490", "JOHN H. KERR RESERVOIR AT DAM NEAR BOYDTON, VA", 36.59847608, -78.2988854, "62614", "elev", "NGVD29", pts,
                 fullPoolHint=300.0, hist=None, apiUrl=u, pageUrl="https://waterdata.usgs.gov/monitoring-location/02079490/", relay=False,
                 notes="USGS live lake elevation at the dam; the dv archive stops 2021-08 but iv is live. History is attached to the CWMS candidate above (same series).")

    # ---- Bay Springs Lake (Jamie Whitten L&D = Bay Springs Lake dam) and Columbus Lake (Stennis L&D)
    for lakeId, tsid, spl, note in [
        ("Bay Springs Lake|MS", "Whitten.Elev.Inst.15Minutes.0.Raw-USGS", None,
         "Jamie L. Whitten Lock and Dam (formerly Bay Springs Lock & Dam) impounds Bay Springs Lake; pool elevation ft NGVD29 (USGS-sourced) in USACE Mobile CWMS, live. Wave 1 rejected only on name similarity (0.0). Median ~412.6 vs summer pool 414 ft (seasonal 411-414)."),
        ("Columbus Lake|MS", "Stennis.Elev.Inst.15Minutes.0.Raw-CCP", ["Stennis.Elev.Inst.15Minutes.0.Raw-USGS", "Stennis.Elev.Inst.1Hour.0.Raw-USGS"],
         "Stennis Lock and Dam (formerly Columbus L&D) impounds Columbus Lake, Tenn-Tom Waterway; pool elevation NGVD29, live. Wave 1 rejected only on name similarity. NOTE the older Raw-USGS series in the same location is "
         "missing 100 ft (63.4 vs 163.4); history here = Raw-USGS + 100 ft before 2025-06-11 (offset validated on the overlap) then Raw-CCP."),
    ]:
        pts, info = cwms_recent_pts("SAM", tsid)
        hist = cwms_daily_hist("SAM", tsid, "2015-01-01")
        if spl:
            hs0 = cwms_daily_hist("SAM", spl[0], "2015-01-01")
            ov = [hist[k] - hs0[k] for k in hist if k in hs0]
            off = round(float(np.median(ov))) if ov else None
            print("   Stennis overlap offset (Raw-CCP minus Raw-USGS)", off, len(ov))
            if off == 100:
                for sname in spl:
                    hs = hs0 if sname == spl[0] else cwms_daily_hist("SAM", sname, "2015-01-01")
                    for k, v2 in (hs or {}).items():
                        hist.setdefault(k, v2 + 100)
        nm, la, lo = cat_loc("cwms:SAM:" + tsid)
        add_cand(lakeId, "cwms-sam", "usace", "SAM:" + tsid.split(".")[0], nm or tsid, la, lo, tsid, "elev", "NGVD29", pts,
                 fullPoolHint=float(PROFILE[lakeId]["fullPoolFt"]), hist=hist, apiUrl=f"{CW_B}/timeseries?office=SAM&name={tsid}", pageUrl="https://water.usace.army.mil/", notes=note)

    # ---- Louisiana / Arkansas MVN, MVK stages
    for lakeId, off, tsid, note in [
        ("False River|LA", "MVN", "False_River.Stage.Inst.1Hour.0.rev",
         "USACE New Orleans gauge 'False River at New Roads (52330)', stage (ft, gauge datum not given in CWMS; USGS-style NGVD29 stage zero is typically ~ 0 for this CWMS gauge); live, history 1996-. Treat as local stage."),
        ("Chicot|AR", "MVK", "Chicot Pump-LS.Elev.Inst.1Hour.0.DCP-raw",
         "Lake Chicot Pumping Plant LANDSIDE (= lake side of the levee) elevation ft NGVD29; median ~99.9 ft = lake pool. Gauge is at the pumping plant on the lake's NE shore (7 km from directory centroid). Wave 1 rejected on geometry; river-side series (-RS) is the Mississippi side."),
    ]:
        pts, info = cwms_recent_pts(off, tsid)
        hist = cwms_daily_hist(off, tsid, "1990-01-01")
        nm, la, lo = cat_loc(f"cwms:{off}:{tsid}")
        vd = (info.get("vertical-datum-info") or {}).get("native-datum") if info else None
        fam = "elev" if ".Elev." in tsid else "stage"
        add_cand(lakeId, "cwms-" + off.lower(), "usace", f"{off}:{tsid.split('.')[0]}", nm or tsid, la, lo, tsid, fam, "NGVD29" if vd else "unknown", pts,
                 fullPoolHint=float(PROFILE[lakeId]["fullPoolFt"]), hist=hist, apiUrl=f"{CW_B}/timeseries?office={off}&name={tsid}", pageUrl="https://water.usace.army.mil/", notes=note)


def usgs_iv_daily(site, param, y0):
    """Daily means from the NWIS iv archive, one request per calendar year (used when no dv series exists)."""
    out = {}
    for y in range(y0, NOW.year + 1):
        u = (f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={site}&parameterCd={param}&startDT={y}-01-01T00:00Z&endDT={y}-12-31T23:59Z&siteStatus=all")
        s, d = get_json(u, timeout=300, sleep=1.0)
        by = {}
        for ts in (d or {}).get("value", {}).get("timeSeries", []):
            nd = ts["variable"].get("noDataValue", -999999)
            for blk in ts["values"]:
                for v in blk["value"]:
                    try:
                        x = float(v["value"])
                    except Exception:
                        continue
                    if x != nd:
                        by.setdefault(v["dateTime"][:10], []).append(x)
        out.update({k: sum(v) / len(v) for k, v in by.items()})
    return out


def run_usgs_stage():
    print("== USGS stage-family lake gauges")
    # Reelfoot Lake (TN): gage height, gage datum 270.11 ft NAVD88 (USGS site metadata alt_va) -> absolute = stage + 270.11
    pts, u = usgs_iv_pts("07027000", "00065")
    dv, udv = usgs_dv_hist("07027000", "00065")
    c = add_cand("Reelfoot Lake|TN", "usgs", "usgs", "07027000", "REELFOOT LAKE NR TIPTONVILLE, TN", 36.3873, -89.4214, "00065", "stage", "local", pts, fullPoolHint=282.4, hist=dv,
                 apiUrl=u + " ; " + udv, pageUrl="https://waterdata.usgs.gov/monitoring-location/07027000/",
                 notes="USGS gage height (ft above gage datum) in Reelfoot Lake at the spillway end; USGS site metadata gives gage-datum altitude 270.11 ft NAVD88 (alt_va), so surface elevation = stage + 270.11 ft NAVD88 "
                       "(e.g. stage + 270.11 puts the lake near the statutory natural full pool 283.6 ft MSL / spillway thresholds 282.3-283.5 ft NAVD88 in USGS OFR 2022-1073 when full). Offset not applied to lastFt/medFt/history. "
                       "dv 00065 1984-present; iv live.")
    if c:
        c["offsetToNAVD88Ft"] = 270.11
        c["offsetSource"] = "USGS NWIS site metadata alt_va=270.11 ft NAVD88 (gage datum)"
    # Pass Manchac near Lake Maurepas (LA): gage height, gage datum -0.18 ft NAVD88; channel between Lake Maurepas and Lake Pontchartrain
    pts, u = usgs_iv_pts("073802302", "00065")
    hist = usgs_iv_daily("073802302", "00065", 2022)
    c = add_cand("Lake Maurepas|LA", "usgs", "usgs", "073802302", "Pass Manchac nr. Lake Maurepas, LA", 30.2943, -90.4033, "00065", "stage", "local", pts, fullPoolHint=1.0, hist=hist,
                 apiUrl=u + " ; nwis/iv startDT/endDT per year", pageUrl="https://waterdata.usgs.gov/monitoring-location/073802302/",
                 notes="NOT on the lake surface proper: Pass Manchac is the tidal channel joining Lake Maurepas and Lake Pontchartrain (~10 km from the Maurepas centroid). Gage height in ft above gage datum "
                       "-0.18 ft NAVD88 (USGS alt_va). Tracks lake stage (Maurepas is a nearly flat, wind- and tide-driven brackish lake). History from iv archive 2022-05.")
    if c:
        c["offsetToNAVD88Ft"] = -0.18
        c["offsetSource"] = "USGS NWIS site metadata alt_va=-0.18 ft NAVD88 (gage datum)"


def run_coops():
    print("== NOAA CO-OPS Port Arthur (Sabine Lake)")
    st = "8770475"
    base = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?station=%s&units=english&application=SectorEngineResearch&format=json&time_zone=gmt&datum=NAVD" % st
    s, d = get_json(base + "&product=water_level&date=recent", timeout=60, sleep=0.8)
    pts = []
    for r in (d or {}).get("data", []):
        try:
            pts.append((dt.datetime.strptime(r["t"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp(), float(r["v"])))
        except Exception:
            pass
    # 'recent' = last 72 h; extend to 30 d with hourly_height
    b = (NOW - dt.timedelta(days=31)).strftime("%Y%m%d"); e = NOW.strftime("%Y%m%d")
    s, d2 = get_json(base + f"&product=hourly_height&begin_date={b}&end_date={e}", timeout=60, sleep=0.8)
    for r in (d2 or {}).get("data", []):
        try:
            pts.append((dt.datetime.strptime(r["t"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp(), float(r["v"])))
        except Exception:
            pass
    hist = {}
    for y in range(2010, NOW.year + 1):
        s, dd = get_json(base + f"&product=hourly_height&begin_date={y}0101&end_date={y}1231", timeout=120, sleep=1.0)
        by = {}
        for r in (dd or {}).get("data", []):
            try:
                x = float(r["v"])
            except Exception:
                continue
            by.setdefault(r["t"][:10], []).append(x)
        hist.update({k: sum(v) / len(v) for k, v in by.items()})
    add_cand("Sabine Lake|LA", "coops", "noaa-coops", st, "Port Arthur, TX (Sabine-Neches Waterway, west shore of Sabine Lake)", 29.8667, -93.93, "water_level NAVD88", "elev", "NAVD88", pts,
             fullPoolHint=None, hist=hist, apiUrl=base + "&product=hourly_height&begin_date=YYYYMMDD&end_date=YYYYMMDD ; product=water_level&date=recent",
             pageUrl="https://tidesandcurrents.noaa.gov/stationhome.html?id=8770475",
             notes="Tidal gauge 7.9 km from the Sabine Lake centroid, on the lake's western shore (Sabine-Neches Waterway); Sabine Lake is an open estuary so this tracks the lake surface within wind setup. "
                   "Values in ft NAVD88 (datum epoch 1983-2001). CO-OPS archive is patchy 2010-2017 (see histYears/complete years). Tidal range ~1 ft; treat as an estuary surface, not a managed pool.")


def run_arwa():
    print("== ARWA Chesdin daily status report")
    s, b = http_get("https://arwava.org/", timeout=60)
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"\s+", " ", b)))
    m = re.search(r"Daily Status Report Date: ([\d-]+).*?Pool Level inches \(ft\) ([\-\d.]+) \(([\-\d.]+)\)", txt)
    if not m:
        print("   ARWA parse failed"); return
    d0 = dt.datetime.strptime(m.group(1), "%m-%d-%Y").replace(hour=12, tzinfo=dt.timezone.utc)
    ft = float(m.group(3))
    p = PROFILE["Lake Chesdin|VA"]
    c = add_cand("Lake Chesdin|VA", "arwa", "arwa", "ARWA-DSR", "Chesdin Reservoir Daily Status Report (pool level, ft below normal pool)", p["lat"], p["lon"], "pool-level-below-normal", "stage", "local",
                 [(d0.timestamp(), ft)], fullPoolHint=157.2, hist=None, apiUrl="https://arwava.org/ (HTML table 'Chesdin Reservoir Daily Status Report')", pageUrl="https://arwava.org/",
                 notes=f"One value/day scraped from the authority homepage: 'Pool Level inches (ft)' = {m.group(2)} in ({m.group(3)} ft) BELOW normal pool 157.2 ft (ARWA 'Dam Reading Explanation', 2024). 0 = at spillway crest. "
                       "Sign/overflow behaviour untested. No history endpoint: poll-and-archive only. Stage deficit, not elevation; absolute = 157.2 - deficit (normal pool elevation per ARWA).")
    if c:
        c["stageFullPond"] = 0.0
        c["stageSense"] = "feet below normal pool (0 = full)"


def run_nwps_relays():
    print("== NWPS relays (Catawba/Savannah chain)")
    items = [("Lake Norman|NC", "CWAN7", 760.0), ("Lake Wylie|SC", "FOMS1", 569.4), ("Lake Wateree|SC", "WATS1", 225.5), ("Lake Keowee|SC", "KEOS1", 800.0),
             ("Lake Jocassee|SC", "JCSS1", 1110.0), ("Lake James|NC", "BRWN7", 1200.0), ("Lake Hickory|NC", "OXFN7", 935.0)]
    # sparse (twice-daily) NWS pool-elevation relays that wave 1 considered 'not live' (last obs < 1 day old on 2026-10-13)
    abs_items = [("Lake Gaston|VA", "GASN7", 200.0, "dominion-energy", "Dominion Energy (Gaston Dam) pool elevation, NWS HPIRZ, observations roughly twice daily"),
                 ("Smith Mountain Lake|VA", "SMIV2", 795.0, "aep-appalachian-power", "Appalachian Power Smith Mountain forebay pool elevation, NWS HPIRZ, ~daily"),
                 ("Clarks Hill / J.S. Thurmond|GA", "CHDS1", 330.0, "usace", "USACE Savannah District J. Strom Thurmond pool elevation, NWS HPIRZ, ~daily"),
                 ("Lake Strom Thurmond (Clarks Hill)|SC", "CHDS1", 330.0, "usace", "USACE Savannah District J. Strom Thurmond pool elevation, NWS HPIRZ, ~daily"),
                 ("Kerr Lake (John H. Kerr)|NC", "KERV2", 300.0, "usace", "USACE Wilmington John H. Kerr pool elevation, NWS HPIRG, 5-min")]
    for lakeId, lid, full, origin, desc in abs_items:
        pts, d = nwps_series(lid)
        meta = nwps_meta(lid)
        if not pts:
            print("   no obs", lid); continue
        add_cand(lakeId, "nwps", origin, lid, meta.get("name", lid), meta.get("latitude"), meta.get("longitude"), (d or {}).get("pedts", "") + " pool", "elev", "NGVD29", pts, relay=True,
                 fullPoolHint=full, hist=None, apiUrl=f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}/stageflow/observed", pageUrl=f"https://water.noaa.gov/gauges/{lid}",
                 notes=desc + ". Absolute elevation (ft; datum presumed NGVD29/MSL per operator). NWPS keeps ~30 days only (n30 small = sparse reporting, not a gap). Wave 1 filtered as 'not live' because of sparse cadence.")
    for lakeId, lid, full in items:
        pts, d = nwps_series(lid)
        meta = nwps_meta(lid)
        dv = (((meta.get("datums") or {}).get("vertical") or {}).get("value") or [])
        datum_txt = "; ".join(f"{x.get('abbrev')} gauge-zero {x.get('value')} ft" for x in dv) or "no vertical datum published in NWPS metadata"
        flood = meta.get("flood") or {}
        full_stage = [i for i in flood.get("impacts", []) if "Full" in (i.get("statement") or "")]
        if not pts:
            print("   no obs", lid); continue
        c = add_cand(lakeId, "nwps", "duke", lid, meta.get("name", lid), meta.get("latitude"), meta.get("longitude"), "HPIRZ pool", "stage", "local", pts, relay=True, fullPoolHint=full,
                     hist=None, apiUrl=f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}/stageflow/observed", pageUrl=f"https://water.noaa.gov/gauges/{lid}",
                     notes=(f"NWS relay of Duke Energy lake level (stage, 100 ft ~ full pond). NWPS vertical datum metadata: {datum_txt}. "
                            f"NWPS impact text at 'Full Pool': {[i.get('stage') for i in full_stage]}. Duke Lake View API (see duke candidate) publishes the full-pond elevation ({full} ft NGVD29 at 100.0 local ft). 30-day window only."))
        if c:
            c["offsetToNGVD29Ft"] = (dv[0]["value"] if dv else None)
            c["offsetSource"] = "NWPS gauge metadata datums.vertical" if dv else None


if __name__ == "__main__":
    which = sys.argv[1:] or ["duke", "aep", "sjrwmd", "usace", "nwps", "usgsstage", "coops", "arwa"]
    if os.path.exists(CAND_F) and sys.argv[1:]:
        for l in open(CAND_F):
            c = json.loads(l)
            CANDS[(c["lakeId"], c["prov"], c["station"], c["series"])] = c
    for w in which:
        {"duke": run_duke, "aep": run_aep, "sjrwmd": run_sjrwmd, "usace": run_usace, "nwps": run_nwps_relays, "usgsstage": run_usgs_stage, "coops": run_coops, "arwa": run_arwa}[w]()
        flushCANDS()
