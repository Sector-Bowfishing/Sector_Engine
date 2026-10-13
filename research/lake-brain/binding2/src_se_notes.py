"""Writes notes/se.json (source-evaluation records incl. dead ends) for the binding2 'se' scout. No network access.
Run after src_se.py so that lakesUnlocked can be derived from cand/se.jsonl.
"""
import json, os, collections

OUT = "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/binding2"
cands = [json.loads(l) for l in open(f"{OUT}/cand/se.jsonl")]
by_prov = collections.defaultdict(set)
for c in cands:
    by_prov[c["prov"]].add(c["lakeId"])
U = lambda *p: sorted(set().union(*[by_prov[x] for x in p]))

R = []


def rec(source, org, url, scope, tested, result, evidence, lakes=None, history="none", access="api", authority=5, license="public, no key", notes=""):
    R.append(dict(source=source, org=org, url=url, scope=scope, tested=tested, result=result, evidence=evidence, lakesUnlocked=lakes or [], history=history, access=access,
                  authority=authority, license=license, notes=notes))


# ----------------------------------------------------------------------------------------------- WORKS
rec("Duke Energy Lake View API (api.hydro-derived.duke-energy.app)", "Duke Energy", "https://lakes.hydro-derived.duke-energy.app/",
    U("duke"),
    "GET /lakes/current-level (all Duke lakes) and /lakes/operating-range/<LocationId> (history+forecast) - the unauthenticated JSON endpoints used by the public Duke Energy Lake Levels web app (found in the app's Angular bundle). 2026-10-13.",
    "WORKS",
    "HTTP 200, no key. 43 Duke lakes with Actual/Target/Min/Max and an 'Elevation' field ('760.0 ft (AMSL, NGVD 29 datum)'). operating-range returns 1827 daily means (2021-10-13..today) + 31-day target forecast. "
    "Last obs <1 h old for Norman/Wylie/Wateree/Keowee/Jocassee/James/Hickory/Robinson.",
    U("duke"), "5 y rolling daily mean (2021-10-13+) = 4 complete calendar years (Robinson: since 2022-05-26)", "api", 7,
    "public web-app endpoint; terms not stated (Duke site ToS apply); API is undocumented -> may change",
    "DATUM RESOLUTION for the Catawba/Keowee chain: Duke publishes lake level as LOCAL stage in which 100.00 ft ('Max') is full pond, and the API's 'Elevation' field is the NGVD29 elevation of that mark: "
    "Norman 760.0, Wylie 569.4, Wateree 225.5, Hickory 935.0, James 1200.0, Rhodhiss 995.1, Keowee 800.0, Jocassee 1110.0, Mountain Island 647.5, Fishing Creek 417.2, Great Falls 355.8, Cedar Creek 284.4. "
    "=> NGVD29 elevation = Actual + (Elevation - 100) i.e. gauge zeros Norman 660, Wylie 469.4, Wateree 125.5, Hickory 835, James 1100, Keowee 700, Jocassee 1010. Corroboration: (a) NWPS CWAN7 metadata lists NGVD29 vertical datum value 660 ft (=760-100); "
    "(b) independent absolute series USACE SAS 'Jocassee.Stage.Inst.1Hour.0.Rev-SHEF_SAS' minus Duke local stage = 1010.01 ft median over 1010 days (expected 1110-100=1010). "
    "Non-Catawba Duke lakes (Belews, Harris, Hyco, Julian, Mayo, Robinson, Sutton) are published as ABSOLUTE NGVD29 elevation (Max~=Elevation; Hyco 407.8 vs USGS 02077280 407.75). The offset is documented but NOT applied to any emitted value.")

rec("NWPS Catawba/Keowee chain gauges (Duke relay)", "NOAA NWS / Duke Energy", "https://api.water.noaa.gov/nwps/v1/gauges/<LID>/stageflow/observed",
    U("nwps") and [x for x in U("nwps") if x in ("Lake Norman|NC", "Lake Wylie|SC", "Lake Wateree|SC", "Lake Keowee|SC", "Lake Jocassee|SC", "Lake James|NC", "Lake Hickory|NC")],
    "Observed pool series for CWAN7 FOMS1 WATS1 KEOS1 JCSS1 BRWN7 OXFN7 plus gauge metadata (datums).", "WORKS",
    "HPIRZ hourly, ~97-100 ft local stage: matches Duke within 0.1-0.2 ft (e.g. Norman 99.35 vs Duke 99.36). NWPS metadata gives a vertical datum only for CWAN7 (NGVD29, gauge zero 660 ft); flood-category 'Full Pool' impact text at stage 100 (Norman) / action stage 99 (Wateree).",
    [x for x in U("nwps") if x in ("Lake Norman|NC", "Lake Wylie|SC", "Lake Wateree|SC", "Lake Keowee|SC", "Lake Jocassee|SC", "Lake James|NC", "Lake Hickory|NC")],
    "~30 days only", "api", 6, "NOAA public domain",
    "So the 97-100 ft NWPS values ARE Duke's local datum where 100 = full pond (answer to the datum question); absolute offsets are in the Duke record above.")

rec("SJRWMD WISKI-Web public data store (mdp.sjrwmd.com/data/internet)", "St. Johns River Water Management District", "https://mdp.sjrwmd.com/",
    sorted(by_prov["sjrwmd"]),
    "Directory listing + filters/ts_sw_wl.parquet (4,037-row catalog of all SJRWMD surface-water level series with last value/time) + metadata/w7/stations.parquet; zarr v2 arrays under timeseries/<site>/<station>/Water_Level/{Cmd_E,Day_Mean}/{time,data} (blosc/lz4, decoded with a small pure-python decoder).",
    "WORKS",
    "HTTP 200 static files, no auth/CAPTCHA (the www.sjrwmd.com site itself returns 403 to scripts; the mdp host does not). Live 15-min lake gauges (last obs 3-4 h old) for Apopka (Jake Voss 65.89 ft; N Pumphouse), Harris (61.69), Griffin (Emeralda 57.14), Jesup (3.49), Lochloosa (54.04), Orange Lake (Boardman 52.65), Lake George (Middle Rd 1.98). Also Eustis, Dora, Weir, Crescent etc. (not unbound).",
    sorted(by_prov["sjrwmd"]), "Daily means since 1992-2005 depending on station (Harris 1993, George 1992, Jesup 1996, Lochloosa/Orange 1995, Apopka NP 2005, Jake Voss 2020, Griffin Emeralda 2020)", "bulk", 7,
    "SJRWMD public data; no explicit licence",
    "Datum: store does not label it; 'Cmd_E' is the standard (NGVD29) series, 127 stations additionally carry 'Cmd_E_NAVD88'. Levels agree with NGVD29 regulation stages (Apopka 65.9 vs 66.14 full pool; Harris 61.7 vs 62.2; Lochloosa 54.0 vs 57). "
    "Older USGS/SJRWMD series for Lake Griffin (Leesburg, 1993-2008) exist as SW_03002_LKGRIF (ended 2008) and Apopka SW_03000_APOWG (ended 2016): could be spliced for longer Griffin/Apopka baselines. Site names can be misleading ('Lake George - Middle Rd' is an in-lake gauge at 29.356,-81.581).")

rec("USACE CWMS data API (SAJ) - SFWMD stage mirror", "USACE Jacksonville / SFWMD", "https://cwms-data.usace.army.mil/cwms-data/timeseries?office=SAJ&name=E Tohopekaliga.Elev.Inst.1Hour.0.SFWMD-Raw",
    ["East Lake Tohopekaliga|FL"], "35-day window + full hourly history; S59-Headwater daily.", "WORKS",
    "East Lake Toho 57.54 ft NGVD29 (1.0 h old; reg. top ~58), hourly since 2010-07 (8 complete years); S59-Headwater daily mean since 2021. Wave 1 had matched the neighbouring WEST Lake Tohopekaliga series (53.95 ft) instead.",
    ["East Lake Tohopekaliga|FL"], "2010-2026 hourly", "api", 7, "USACE public", "SAJ also carries Lake Tohopekaliga, Alligator, Gentry, Lizzie, Trout, Center and S-57/S-58/S-60..S-62 structure headwaters (SFWMD data).")

rec("USACE CWMS data API (SAM) - Alabama Power Logan Martin", "Alabama Power / USACE Mobile", "https://cwms-data.usace.army.mil/cwms-data/timeseries?office=SAM&name=LoganMartin.Elev.Inst.1Hour.0.Raw-APCO",
    ["Logan Martin|AL"], "LoganMartin.Elev (Raw-APCO and GC-APCO) + NWPS CCSA1", "WORKS",
    "464.14 ft NGVD29 (2 h old), median 463.8 vs full pool 465; NWPS CCSA1 identical (relay). Hourly history since 2017-09 (8 complete years). Dam point is 1.6 km from the polygon centroid (wave-1 geometry rejection) - confirmed candidate.",
    ["Logan Martin|AL"], "2017-2026", "api", 7, "USACE public")

rec("USGS NWIS 02193900 THURMOND LAKE NEAR PLUM BRANCH, SC", "USGS / USACE Savannah", "https://waterservices.usgs.gov/nwis/iv/?sites=02193900&parameterCd=00062",
    ["Clarks Hill / J.S. Thurmond|GA", "Lake Strom Thurmond (Clarks Hill)|SC"], "iv 00062 + dv 00062 (1954 spliced)", "WORKS",
    "00062 reservoir elevation 319.68 ft NGVD29, 15-min, last obs 1 h old; dv since 2005; CWMS SAS Thurmond.Elev-Pool.1Day.Raw-SHEF_SAS (1950-) splices a 70-year daily record. Old USGS 02194500 (dam) ended 2001.",
    ["Clarks Hill / J.S. Thurmond|GA", "Lake Strom Thurmond (Clarks Hill)|SC"], "1954-2026 (68 complete years)", "api", 7, "USGS public",
    "CWMS SAS Thurmond.* hourly series and A2W SAS:02193900 are silent ~5 days (last 2026-10-08): do not use as the live feed. Wave-1 state-mismatch rejection is an artefact (one reservoir, two directory entries). Savannah-district Jocassee/Keowee CWMS series are also silent.")

rec("USGS NWIS 02079490 + CWMS SAW 'ROA JHK' (John H. Kerr)", "USACE Wilmington / USGS", "https://waterservices.usgs.gov/nwis/iv/?sites=02079490&parameterCd=62614",
    ["Kerr Lake (John H. Kerr)|NC"], "iv 62614, dv 62614, CWMS SAW ROA JHK.Elev 5-min/15-min", "WORKS",
    "287.79 ft NGVD29 (0.3 h old) vs conservation pool ~300 (flood top). USGS dv stops 2021-08 but iv is live; CWMS 15-min 2012-2025 + 5-min 2025-. Gauge is the dam in Boydton VA: wave-1 rejected for state-mismatch (lake straddles VA/NC).",
    ["Kerr Lake (John H. Kerr)|NC"], "2005-2026 (20 complete years)", "api", 7, "public")

rec("CWMS SAM Whitten / Stennis (Tenn-Tom)", "USACE Mobile", "https://cwms-data.usace.army.mil/cwms-data/timeseries?office=SAM&name=Whitten.Elev.Inst.15Minutes.0.Raw-USGS",
    ["Bay Springs Lake|MS", "Columbus Lake|MS"], "Whitten and Stennis pool elevation 15-min (Raw-USGS, Raw-CCP), A2W copies, tailwater siblings", "WORKS",
    "Whitten 410.7 ft (median 412.35; summer pool 414), Stennis 163.32 (median 163.38; normal 164). Jamie Whitten L&D = former Bay Springs L&D, Stennis L&D = former Columbus L&D (the names differ, hence wave-1 nameSim 0). A2W/LRIT_TTWW copies are 660 h stale; Raw-USGS/Raw-CCP are live.",
    ["Bay Springs Lake|MS", "Columbus Lake|MS"], "Whitten 2018-; Stennis 2018- (after +100 ft correction)", "api", 7, "USACE public",
    "TRAP: CWMS 'Stennis.Elev...Raw-USGS' (and the 1Hour series) are 100 ft low (63.4 instead of 163.4; validated against Raw-CCP over 489 overlapping days) - history in this scout adds +100 ft before 2025-06-11; USGS 02441390 00065 63.3 is the same gage height, 72020 136.4 is tailwater-influenced.")

rec("CWMS MVK Chicot Pumping Plant landside", "USACE Vicksburg", "https://cwms-data.usace.army.mil/cwms-data/timeseries?office=MVK&name=Chicot Pump-LS.Elev.Inst.1Hour.0.DCP-raw",
    ["Chicot|AR"], "LS and RS elevation series", "PARTIAL",
    "Landside (lake side) elevation 99.9 ft NGVD29 steady for days then rising to 106.6 ft after October 2026 rain; riverside 102.9-113 ft follows the Mississippi. Station is the pumping plant on the lake's NE shore (7 km from centroid).",
    ["Chicot|AR"], "2011-2026 hourly (11 complete years)", "api", 6, "USACE public",
    "Lake Chicot normal pool ~100 ft; profile fullPool 110 appears to be a flood-top. Landside = lake side confirmed by LS flat 99.9 in dry weather. Treat as plausible, geometry-rejected in wave 1.")

rec("CWMS MVN False River at New Roads (52330)", "USACE New Orleans", "https://cwms-data.usace.army.mil/cwms-data/timeseries?office=MVN&name=False_River.Stage.Inst.1Hour.0.rev",
    ["False River|LA"], "35-day window + hourly history", "PARTIAL",
    "Stage 14.2 ft (1 h old), median 14.35; hourly since 1996 (8 complete years). CWMS carries no vertical-datum-info for the location; stage ~14.4 is consistent with the regulated lake (NGVD29 elevation) but the datum is undocumented.",
    ["False River|LA"], "1996-2026", "api", 6, "USACE public", "Family 'stage', datum unknown; the profile fullPool 20 is not a verified pool elevation.")

rec("USGS NWIS 07027000 Reelfoot Lake near Tiptonville TN", "USGS", "https://waterservices.usgs.gov/nwis/iv/?sites=07027000&parameterCd=00065",
    ["Reelfoot Lake|TN"], "iv + dv 00065, site metadata", "WORKS",
    "Gage height 11.17 ft (1 h old), dv 1984-2026 (36 complete years). Gage datum altitude 270.11 ft NAVD88 (USGS site metadata) => ~281.3 ft NAVD88 now (below the 282.4 ft ordinary low-water mark / 282.3 free-flow spillway threshold).",
    ["Reelfoot Lake|TN"], "1984-2026", "api", 7, "USGS public",
    "Offset documented (270.11 ft NAVD88) but not applied. Spillway 07027002/07027003 are discharge-only. TWRA publishes no gauge page (not found).")

rec("USGS NWIS 073802302 Pass Manchac nr Lake Maurepas", "USGS", "https://waterservices.usgs.gov/nwis/iv/?sites=073802302&parameterCd=00065",
    ["Lake Maurepas|LA"], "iv 00065 + yearly iv archive", "PARTIAL",
    "Gage height 1.09 ft (0.4 h), 15-min since 2022-05 (3 complete years); gage datum -0.18 ft NAVD88. It is the pass between Lake Maurepas and Lake Pontchartrain, ~10 km from the centroid, not a station on the open lake.",
    ["Lake Maurepas|LA"], "2022-2026", "api", 5, "USGS public", "CWMS MVN Pass_Manchac.Stage returned no data (catalog end date 2087 is a placeholder). No other live Maurepas level gauge found (CRMS marsh stations are not lake gauges).")

rec("NOAA CO-OPS 8770475 Port Arthur TX", "NOAA CO-OPS", "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?station=8770475&product=hourly_height&datum=NAVD",
    ["Sabine Lake|LA"], "water_level recent + hourly_height by year, NAVD datum", "PARTIAL",
    "1.72 ft NAVD88 (0.1 h old), 6-min; hourly archive present 2012-2026 with gaps (10 complete years). Tidal estuary gauge 7.9 km from the lake centroid on the Sabine-Neches Waterway.",
    ["Sabine Lake|LA"], "2012-2026 (patchy 2013-2017)", "api", 6, "NOAA public domain", "Other CO-OPS stations: Texas Point 8770822 (17.9 km), Rainbow Bridge 8770520 (14.8 km). USGS SAB1/SAB2 in the lake are salinity/temperature only.")

rec("AEP / Appalachian Power plant-levels API", "AEP (Appalachian Power)", "https://aepcom-api.aep.com/api/hydro/plant-levels",
    ["Smith Mountain Lake|VA"], "GET (the endpoint behind smithmountainproject.com/lake-levels)", "PARTIAL",
    "HTTP 200 JSON, Smith Mountain forebay 790.70 ft vs normal full pond 795.00 (also Leesville, Claytor, Buck, ... forebays). Only the current value; no observation timestamp for SM; no history endpoint.",
    ["Smith Mountain Lake|VA"], "none (poll-and-archive)", "api", 7, "public web-app endpoint",
    "NWPS SMIV2 (relay) gives ~daily obs, 790.5 ft on 10-12. USGS has no lake gauge on Smith Mountain Lake. Level swings 1-2 ft/day (pumped storage).")

rec("NWPS Dominion/AEP/USACE pool relays (GASN7, SMIV2, CHDS1, KERV2)", "NOAA NWS", "https://api.water.noaa.gov/nwps/v1/gauges/GASN7/stageflow/observed",
    ["Lake Gaston|VA", "Smith Mountain Lake|VA", "Clarks Hill / J.S. Thurmond|GA", "Lake Strom Thurmond (Clarks Hill)|SC", "Kerr Lake (John H. Kerr)|NC"],
    "observed series for GASN7/SMIV2/CHDS1/KERV2", "WORKS",
    "GASN7 Lake Gaston 199.54 ft (20 h old, ~63 obs/30 d), SMIV2 790.5, CHDS1 319.51, KERV2 287.77 (5-min). Sparse twice-daily cadence for GASN7/SMIV2/CHDS1 caused wave-1 'not live' flags.",
    U("nwps"), "~30 days", "api", 6, "NOAA public domain",
    "Lake Gaston has NO other live source: Dominion publishes only anticipated daily ranges (199.40-199.60 ft, drought operation) on a web page, a phone recording and the NWS relay.")

rec("ARWA Chesdin Reservoir Daily Status Report", "Appomattox River Water Authority", "https://arwava.org/",
    ["Lake Chesdin|VA"], "GET homepage and parse the 'Chesdin Reservoir Daily Status Report' table", "PARTIAL",
    "Pool level 'inches (ft)' below normal pool = 0 (0) for 2026-10-12 (normal pool 157.2 ft per ARWA's Dam Reading Explanation). One value per day, no history, HTML scrape.",
    ["Lake Chesdin|VA"], "none", "portal", 6, "public web page",
    "USGS 02040892 (Rte 602) and 02041650 (Matoaca) are river discharge gauges, not pool level. CWMS NAO Matoaca.Stage is the river below the dam.")

# ----------------------------------------------------------------------------------------------- DEAD ENDS / not usable
rec("SFWMD DBHYDRO Insights Hydro Data Service", "South Florida Water Management District", "https://dataservice-proxy.api.sfwmd.gov/v1/data/help",
    ["East Lake Tohopekaliga|FL"], "GET /v1/data/help; read the Jan-2026 user guide; legacy my.sfwmd.gov/dbhydroplsql", "REQUIRES_LOGIN",
    "API needs a client_id/client_secret from SFWMD (not requested: no accounts). help URL returns an Incapsula 500 'Web Page Blocked' page; legacy host my.sfwmd.gov no longer resolves (DBHYDRO Browser retired 2025). Same stage data is mirrored publicly in USACE CWMS SAJ (see WORKS).",
    [], "n/a", "api", 7, "credentials required")

rec("USGS NWIS legacy Florida lake gauges (02237600 Apopka, 02237520 Harris, 02238300 Griffin, 02236210 George, 02234434 Jesup, 02242400 Lochloosa, 02242450 Orange, 02264900 Toho, 02263400 E Toho)", "USGS", "https://waterservices.usgs.gov/nwis/site/?sites=<id>&seriesCatalogOutput=true&siteStatus=all",
    ["Apopka|FL", "Harris|FL", "Griffin|FL", "Lake George|FL", "Jesup|FL", "Lochloosa|FL", "Orange Lake|FL", "East Lake Tohopekaliga|FL"],
    "site series catalog + nwis/iv period=P60D without parameterCd for each site", "STALE",
    "Truly discontinued: last dv Apopka 1993-09, Harris 1993-09, Griffin 1993-09, George 1998-09, Jesup 1997-09, Lochloosa 1995-10, Orange 1995-09, Toho 2011-09, E Toho 1968; iv/uv catalogs empty and iv returns 0 series. No gage-height (00065) or 62615 variant exists. SJRWMD WISKI store replaces them.",
    [], "1933-1998 (historic only)", "api", 7, "USGS public")

rec("USGS NWIS Lake Anna sites 01670144 / 01670209 / 016702576", "USGS Virginia", "https://waterservices.usgs.gov/nwis/site/?sites=01670144&seriesCatalogOutput=true",
    ["Lake Anna|VA"], "series catalog", "NO_DATA", "Water-quality sondes only (temperature, conductance, pH, DO, chlorophyll), 2023-05..2025-01-14, no elevation/gage-height; discontinued.", [], "none", "api", 7, "USGS public",
    "Dominion Energy's Lake Anna page has no level feed (full pond 250 ft; recording only). No NWPS/CWMS lake gauge (NAO Partlow is the North Anna River 10 km upstream). Dead end.")

rec("Dominion Energy Lake Gaston water levels page", "Dominion Energy", "https://www.dominionenergy.com/about/lakes-and-recreation/lake-gaston-and-roanoke-rapids-lake-nc/lake-gaston-water-levels",
    ["Lake Gaston|VA"], "page text", "PORTAL_ONLY",
    "Table of anticipated daily ranges for today+2 days (e.g. 10/13/2026 Drought Operation 199.40-199.60 ft msl) - a forecast, not an observation, no archive; phone recording 252-535-6883.",
    [], "none", "portal", 7, "public web page", "Use NWPS GASN7 (observed) instead.")

rec("CWMS SAS Savannah (Jocassee/Keowee/Thurmond hourly), A2W SAS", "USACE Savannah", "https://cwms-data.usace.army.mil/cwms-data/timeseries?office=SAS&name=Thurmond.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS",
    ["Lake Jocassee|SC", "Lake Keowee|SC", "Clarks Hill / J.S. Thurmond|GA"], "35-day windows", "STALE",
    "Last observations 2026-10-07/08 (118-131 h old): Thurmond.Elev-Pool 319.75, Jocassee.Stage 83.37. Keowee/Jocassee series are Duke data in local stage (not absolute).", [], "Thurmond 1950-; Jocassee 2016-", "api", 6, "USACE public",
    "Useful for history only; Jocassee.Stage.Rev is an ABSOLUTE ft series used here to validate the Duke offset. Duke API is the live source.")

rec("CWMS MVN Catfish Point control structure (Grand Lake LA)", "USACE New Orleans", "https://cwms-data.usace.army.mil/cwms-data/timeseries?office=MVN&name=CatfishPoint_Nth.Stage.Inst.1Hour.0.rev",
    ["Grand Lake|LA"], "35-day window", "STALE",
    "CatfishPoint_Nth stage 2.63 ft, last obs 2026-10-05 (190 h old), 35 points in 35 days (intermittent). Structure is at the south end of Grand Lake on the Mermentau River; stage ~2.5 ft vs fullPool 3.", [], "2006-2026", "api", 6, "USACE public",
    "Re-check later; if it resumes it is the best Grand Lake source. No USGS/CO-OPS lake gauge within 20 km.")

rec("USGS CRMS0568-H01-RT (White Lake NE corner) and 08012531 / 294625092244000", "USGS / CPRA CRMS", "https://waterservices.usgs.gov/nwis/iv/?sites=294717092250000",
    ["White Lake|LA"], "series catalog + iv", "STALE",
    "CRMS0568-H01-RT (marsh edge at White Lake NE shore, gage datum -0.98 ft NAVD88, 63160 water-level elevation) last data 2026-07-29 (76 days old); 08012531 White Lake Div. Ch. and 294625092244000 have no series.", [], "2012-2026 (but stale)", "api", 5, "USGS public",
    "CPRA CIMS (cims.coastal.louisiana.gov) is a portal without a documented API; CRMS 'H' stations are marsh/edge gauges, not open-lake. Dead end unless the CRMS gauge resumes.")

rec("OWRB Monitoring Data Public Portal (Aquarius) / USGS 07316100", "Oklahoma Water Resources Board / USGS", "https://data-owrb.aquaticinformatics.net/",
    ["Lake Murray (OK)|OK"], "DNS/GET; USGS site catalog + iv for 07316100 Lake Murray near Ardmore", "NO_DATA",
    "data-owrb.aquaticinformatics.net does not resolve from here; the OWRB monitoring page lists only Depth to Water/Stage/Discharge and links USACE Tulsa (Lake Murray is a state-park lake, not USACE). USGS 07316100 has no instantaneous or daily series.", [], "none", "portal", 5, "n/a")

rec("Lake-by-lake negative searches (no gauge found)", "various", "n/a",
    ["Lake Waccamaw|NC", "Lake Washington|MS", "Moon Lake|MS", "Chickahominy Lake|VA", "Douthat Lake|VA", "Mount Storm Lake|WV"],
    "USGS bbox site/iv search (r=0.2-0.3 deg, LK/ES/ST/SP, all statuses), CWMS/A2W/NWPS catalog proximity, web search", "NO_DATA",
    "Waccamaw: only a groundwater well (CC38B10) and WQ dam site, no stage gauge. Lake Washington MS: USGS 330203091020200 is a 2012 4-day water-quality visit. Moon Lake MS: nearest are Coldwater R. at Birdie and 'Long Lake' (different lake, 07287714). "
    "Chickahominy: only the river below Walker's Dam (USGS 02042500 / CWMS NAO Providence Forge); Newport News Waterworks publishes system-percent only. Douthat (VA DCR) and Mount Storm (Dominion cooling lake): no public gauge.",
    [], "none", "portal", 3, "n/a")

rec("Texas TWDB WaterDataForTexas", "TWDB", "https://www.waterdatafortexas.org/reservoirs", [], "scope check", "NO_DATA",
    "No unbound lake in the TX scope remains (all TX lakes were bound in wave 1), so no work needed; no TX lake was tested.", [], "n/a", "api", 7, "public")

rec("SWFWMD / Orange County FL / Lake County FL lake level programs; Georgia Power; SC DNR; Santee Cooper", "various", "n/a", [], "scope check only", "NO_DATA",
    "Not needed for the 40 unbound lakes in scope: every FL unbound lake (Apopka, Harris Chain, George, Jesup, Lochloosa, Orange) is covered by SJRWMD; Lakes Marion/Moultrie/Greenwood/Murray SC and Lanier/Allatoona etc. are already bound via USGS. Not live-tested.",
    [], "n/a", "portal", 3, "n/a")

rec("Re-pointing notes for wave-1 'candidates-rejected' lakes in this area", "n/a", "n/a",
    ["Logan Martin|AL", "East Lake Tohopekaliga|FL", "Harris|FL", "Clarks Hill / J.S. Thurmond|GA", "Kerr Lake (John H. Kerr)|NC", "Lake Strom Thurmond (Clarks Hill)|SC", "Bay Springs Lake|MS", "Columbus Lake|MS", "Chicot|AR", "Lake Gaston|VA"],
    "analysis of candidates.csv rejects", "PARTIAL",
    "Logan Martin/Bay Springs/Columbus/Kerr/Thurmond: wave-1 candidates were correct (rejections were geometry, name-similarity or state-code artefacts). East Toho: wave 1 picked the WEST lake series; correct series is E Tohopekaliga. "
    "Lake Gaston: the wave-1 candidates (Kerr dam series) belong to Kerr Lake; use NWPS GASN7. Kerr's wave-1 NWPS KERV2/USGS/A2W are live and right.",
    [], "n/a", "analysis", 3, "n/a")

json.dump(R, open(f"{OUT}/notes/se.json", "w"), indent=1)
print("notes records:", len(R))
