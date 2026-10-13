"""Writes binding2/notes/west.json (source-evaluation records incl. dead ends) from cand/west.jsonl + the evidence gathered by src_west.py
and the live probes documented in each record's 'tested' field (all probes: 2026-10-13, read-only GETs; one POST to utahlake.gov's public ajax feed)."""
import json, collections

B2 = "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/binding2"
cand = [json.loads(l) for l in open(f"{B2}/cand/west.jsonl")]
by = collections.defaultdict(set)
for c in cand:
    by[c["prov"]].add(c["lakeId"])


def U(*provs):
    s = set()
    for p in provs:
        s |= by.get(p, set())
    return sorted(s)


N = []


def rec(source, org, url, scope, tested, result, evidence, unlocked=(), history="none", access="api", authority=1, license="US public domain / public data", notes=""):
    N.append(dict(source=source, org=org, url=url, scope=scope, tested=tested, result=result, evidence=evidence, lakesUnlocked=list(unlocked), history=history,
                  access=access, authority=authority, license=license, notes=notes))


# ------------------------------------------------------------------ sources that WORK
rec("USBR Pacific Northwest Hydromet (pn-bin instant.pl / daily.pl)", "US Bureau of Reclamation, Columbia-Pacific NW Region", "https://www.usbr.gov/pn-bin/instant.pl?list={cbtt}%20fb&format=csv&start=YYYY-MM-DD&end=YYYY-MM-DD",
    ["WA", "OR", "ID", "MT", "WY"],
    "GET instant.pl and daily.pl (list=csc fb, cre, pot, bnk, hen, pay, gcl, roo; format=csv) for the last 31 days and the full archive (start=1900-01-01). rtindex/res.html parsed for the station-code list.",
    "WORKS",
    "No key, plain CSV. Live 15-min FB (forebay elevation, ft): CSC 4815.5 (00:45 local 2026-10-13), CRE 4825.8, BNK 1568.1, HEN 12.9 (stage), PAY 1.99 (stage). POT: instant.pl returns header only, daily.pl live to yesterday (1030.83 ft). GCL FB hourly stops 2026-10-11/12 (about 1 day stale, CWMS GCL is live); ROO has no data. These are the live copies of the USBR series that RISE republishes 9-13 days late.",
    unlocked=U("usbr-pnhm"), history="CSC 1979-, CRE 1982-, POT 1952-, BNK 1951-, HEN 1977-, PAY 1943- (daily.pl; a 655 ft sentinel in PAY 1991 is removed by the outlier filter)", access="api", authority=1,
    notes="Times are station-local (MDT for ID, PDT for WA/OR); verified against NWRFC UTC stamps for the same values. rtindex/res.html lists ~60 PN reservoirs with FB/AF codes (Upper Snake, SW Idaho, E/C/W Oregon, WA/MT) - useful for re-pointing any other rejected PN reservoir. HEN and PAY are LOCAL-DATUM gauge heights (family stage). Use polite throttling (<=1 req/s).")
rec("California Data Exchange Center (CDEC) JSONDataServlet", "California DWR (aggregator for PG&E, USBR, USACE, utilities)", "https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet?Stations={ID}&SensorNums=6&dur_code={E|H|D}&Start=&End=",
    ["CA"],
    "Station search (staSearch, sensor 6 = RES ELE) returned 196 reservoir-elevation stations (all agencies); JSON requests for ALM and BER with dur_code E, H, D.",
    "WORKS",
    "BER (Berryessa, USBR): event data to 2026-10-12 23:30 PST (428.05 ft), hourly and daily too; daily 1985-. ALM (Lake Almanor, PG&E): daily only (event/hourly return 0 rows), last value 2026-10-12 (4484.5 ft), 12-36 h old; many days 1985- missing.",
    unlocked=U("cdec"), history="BER 1985- (26 complete yrs), ALM 1985- (gappy, 11 complete yrs by the 90% rule); sentinels -1/959746 ft dropped", access="api", authority=2,
    notes="Hourly requests from 1900 are huge (HTTP read timed out); use D for archive and E/H for the recent window. Values -9999 or '--' are no-data. Station list includes many other CA reservoirs (PG&E, SCE, SMUD, EBMUD, SFPUC, USACE, DWR) for re-pointing; Eagle Lake, Mono Lake, Salton Sea are NOT in it.")
rec("Salt River Project Watershed Connection public JSON (streamflow.watershedconnection.com/api/watershedconnectiondata)", "Salt River Project (SRP)", "https://streamflow.watershedconnection.com/api/watershedconnectiondata/getmeasurementdata?measurementId={id}&units=ft&startDate=&endDate=",
    ["AZ"],
    "getstationlist (Accept: application/json), getstation, getlastreadings, getmeasurementdata for Roosevelt (354), Apache (395), Canyon (399), Saguaro (405); also probed start dates back to 2015.",
    "WORKS",
    "Live 5-min 'Official Elevation' (MST): Roosevelt 2090.31 ft (38% full), Apache 1907.2, Canyon 1605.8 (drawn down), Saguaro 1527.2, last obs minutes old. getstationlist reservoirDatas carries maxConservationElevation (2150.78 / 1914 / 1660.5 / 1529.0 ft), matching the directory full pools. Archive responses begin 2023-10-13 even for earlier requested dates.",
    unlocked=U("srp"), history="2023-10-13 .. now (about 3 yrs, 5-min; daily means written)", access="api", authority=1,
    notes="Undocumented but unauthenticated JSON behind SRP's public Watershed Connection web app (no login). 1-month request = 1.5 MB / 2.7 s. Replaces the wave-1 CWMS SPL 'Roosevelt' hit (a stream gauge 6.5 km away). Bartlett, Horseshoe and Cragin are in the same API.")
rec("Colorado DWR / CDSS telemetry REST API", "Colorado Division of Water Resources (data from Denver Water)", "https://dwr.state.co.us/Rest/GET/api/v2/telemetrystations/telemetrytimeseriesraw/?abbrev=DILRESCO&parameter=ELEV",
    ["CO"],
    "telemetrystation (Storage Structure list, 141 stations), telemetrytimeseriesraw / telemetrytimeseriesday with parameter=ELEV (GAGE_HT, STAGE, RES_ELEV return zero records).",
    "WORKS",
    "DILRESCO (Dillon Reservoir): ELEV 15-min, latest 2026-10-13 00:45 MDT = 8980.7 ft (full pool 9017); daily archive 1987-06..2002 and 2021-.. (nothing stored 2003-2020). The parameter must be ELEV; the 'stage' field of the station list is the same elevation but has no history endpoint.",
    unlocked=U("codwr"), history="1987-06..2002 + 2021..now (16 complete years by the 90% rule; sentinel values dropped)", access="api", authority=2,
    notes="Eleven Mile Reservoir is NOT in the CDSS telemetry list (only the South Platte gauges above/below it); Denver Water publishes it only as a weekly Water Watch PDF (percent full). Same API lists ~40 other CO reservoirs with elevation (Blue Mesa, Granby, Cheesman, Twin Lakes, Turquoise, Spinney, John Martin ...).")
rec("USACE CWMS Data API, office NWDP (Northwest Division portal)", "US Army Corps of Engineers NWD (republishing USBR, Seattle District, Tacoma, Seattle City Light data)", "https://cwms-data.usace.army.mil/cwms-data/timeseries?name={ts}&office=NWDP&unit=EN",
    ["WA", "OR", "ID", "MT"],
    "timeseries data queries (unit=EN) for LWSC.Elev-Lake.*, GCL.Elev-Forebay.*, BNK.Elev-Lake.*, MOS.Elev-Forebay.*, CRE/HEN/PAY/CSC Elev-Forebay.",
    "PARTIAL",
    "Live: LWSC (Lake Washington Ship Canal at the Locks = Lake Union pool, 20.4 ft, hourly since 2001-07), GCL forebay (Grand Coulee = Lake Roosevelt, 1285.3 ft hourly 1960-). BNK daily Elev-Lake 1961- to 2026-10-12. MOS (Mossyrock = Riffe Lake) is catalogued 1974- but every data query returns total=0 (dead).",
    unlocked=U("cwms-nwdp"), history="LWSC 2001-, GCL 1960-", access="api", authority=1,
    notes="Catalog extents are not trustworthy (MOS shows latest 2026-10-13 but returns nothing); several NWDP locations have null lat/lon (BNK, CRE) or dam-style names, which is why the wave-1 geo/identity rules rejected GCL, MOS and BNK. Lake Union directory full pool (16 ft) is wrong: the pool is regulated at roughly 20-22 ft.")
rec("NWRFC station XML (xml.cgi, pe=HF forebay elevation)", "NOAA/NWS Northwest River Forecast Center (relay of Tacoma Power, USBR, utilities)", "https://www.nwrfc.noaa.gov/xml/xml.cgi?id={ID}&pe=HF&dtype=b&numdays=30",
    ["WA", "OR", "ID", "MT"],
    "river_summary.php (all 1049 stations parsed; dozens of reservoir/forebay stations with pool elevation), xml.cgi for MSRW1, CSHW1 (numdays=30, 365, 4000: same ~10 days returned).",
    "PARTIAL",
    "Hourly UTC observed forebay_elevation, latest 2026-10-13 06:00Z: CSHW1 Cushman Dam 712.81 ft, MSRW1 Mossyrock (Riffe Lake) 705.22 ft. Retention is only about 10 days, no archive.",
    unlocked=U("nwrfc"), history="none (10 days)", access="api", authority=4,
    notes="RELAY: Tacoma Power's own lake-level page (mytpu.org River Flows & Lake Levels) links to NWRFC for Riffe and Cushman. Also lists live pool stations for ~40 WA/OR/ID/MT reservoirs (Crescent Lake Dam 4825.83, Henrys/Payette/Cascade FB, Chelan, Lake Pend Oreille, Flathead ...) usable as corroboration. No Timothy Lake, Holter, Wallowa, Malheur.")
rec("USGS NWIS (iv, dv, site) - systematic state sweep", "US Geological Survey", "https://waterservices.usgs.gov/nwis/iv/?format=json&stateCd={ST}&parameterCd=62614,62615,62616,62617,62618,62619,62620,72020,72275,00062,72036,30211&period=P3D",
    ["AK", "HI", "WA", "OR", "CA", "NV", "UT", "AZ", "NM", "CO", "WY", "MT", "ID"],
    "Per-state iv sweep (lake-elevation parameter codes, last 3 days), per-state LK site lists (hasDataTypeCd=iv,dv), bbox site search around every unbound lake, dv full-period download for each candidate.",
    "WORKS",
    "Live new matches: Great Salt Lake 10010100/10010000/10010024/10010027 (4189.5-4189.9 ft NGVD29), Upper Klamath Lake 11507001, 11507000, 11505900, 11505800 (72275 = USBR Klamath Basin datum 4138.7 ft; 62615 on 11507001 = NAVD88 4140.7), Georgetown Lake MT 12325000 (62615 NAVD88 6428.7), Eagle Nest NM 07205500 (62614 8160.0), Payette 13238500 and Henrys 13039000 (00065 gage height). Parameter 72275 is 'above USBRKB datum', 62615 is 'above NAVD88' (the opposite of the wave-1 assumption).",
    unlocked=U("usgs"), history="GSL 10010000 1900-, UKL 11507000 1904-, Payette 1965-, Henrys 1977-, Georgetown 2013-, Eagle Nest 2013- (dv)", access="api", authority=1,
    notes="Not live: Riffe 14234800 (dv ends 2026-08-24), Salton Sea 10254005 (ends 2026-09-22; gauge stranded on dry shore), Pyramid 10336500 (one manual 00062 reading 2026-10-01), Washoe 10348700 (ends 2009-06), Malheur 10401800/10401830 (ends 1989/1979), Timothy 14208600 (no data), Berryessa 11453900 and Almanor 11399000 (no iv/dv series), Cascade 13244500 (no iv series), Moses Lake 12471000 is live but not an unbound-lake match (Potholes is 13.7 km away). Stage-only sites (Henrys, Payette) carry a USGS altitude in the site record (6462.71 ft NAVD88, 4981.73 ft NGVD29) that the verifier must validate before deriving elevation.")
rec("Utah Lake Commission live data feed (WordPress admin-ajax action=ulc_data)", "Utah Lake Commission, data stated to originate from Utah Division of Water Rights", "https://utahlake.gov/water-levels/",
    ["UT"],
    "POST https://utahlake.gov/wp-admin/admin-ajax.php action=ulc_data&refresh=false (the call the public page's script.js makes). Also: USGS bbox search around Utah Lake (stream gauges only), RISE catalog item 4514, waterrights.utah.gov WCAT page.",
    "WORKS",
    "JSON returns template (current 'Elevation (ft)' 4484.24 at 10/13/2026 01:55 AM, hourly, 'All Data is Provisional') plus 90 daily means (CALC_UL_ELEVATION 4484.29 on 2026-10-12). Compromise elevation 4489.045 ft per same page. USBR RISE item 4514 (daily) ended 2020-06; no USGS lake gauge exists.",
    unlocked=U("utahlake"), history="about 90 days only", access="api", authority=3,
    notes="Undocumented relay endpoint (POST); fragile and not a formal API. Origin tag OREM\\UL\\ANALOG\\DEPTH0 suggests Orem City SCADA. Older record: RISE 4514 to 2020-06 (datum identity unconfirmed). Ask Utah DWRi / Utah Lake Commission for a stable feed before binding.")
rec("USBR RISE API (data.usbr.gov/rise/api/result)", "US Bureau of Reclamation", "https://data.usbr.gov/rise/api/result?itemId=341&dateTime[after]=YYYY-MM-DD",
    ["WY", "UT", "WA", "ID", "OR", "CA"],
    "itemId=341 Flaming Gorge daily elevation, full history from 1900; wave-1 lagging items (129979, 129880, 132564, 129466, 10785, 4514) re-checked via hydromet/CDEC instead.",
    "WORKS",
    "Flaming Gorge 341: last result 2 days old (6006.2 ft vs 6040 full pool), daily since the 1960s. For the same reservoirs RISE lags 9-13 days (Cascade, Crescent, Potholes, Berryessa, Henrys, Payette) and is empty for Banks/Utah Lake.",
    unlocked=U("rise"), history="daily from dam closure (1960s)", access="api", authority=1,
    notes="Flaming Gorge appears twice in the directory (|UT point at the dam 40.92,-109.42 and |WY point 41.40,-109.50). Wave-1 R4 rejected the WY entry on state only, but both describe the same pool; one RISE series serves both. Dam coordinates (40.98,-109.57) are in Daggett County, UT.")

# ------------------------------------------------------------------ partial / portal / blocked / relays
rec("USBR Upper Colorado hydrodata reservoir_data pages", "US Bureau of Reclamation, Upper Colorado Region", "https://www.usbr.gov/uc/water/hydrodata/reservoir_data/", ["UT", "WY", "CO", "NM"],
    "GET /uc/water/hydrodata/reservoir_data/ and /{id}/dv/elevation/csv/", "BLOCKED", "Index returns HTTP 403 Forbidden for this client; per-site CSV path 404. RISE item 341 covers Flaming Gorge instead.", access="api", authority=1,
    notes="A web search surfaces usbr.gov/uc/water/hydrodata/reservoir_data/3606/charts/pool_elevation.html, so some paths are public; the CSV URL pattern was not confirmed.")
rec("NOAA NWPS gauges API (api.water.noaa.gov/nwps/v1/gauges/{lid})", "NOAA National Water Prediction Service", "https://api.water.noaa.gov/nwps/v1/gauges/HLKI1", ["ID", "NM", "UT"],
    "GET for HLKI1, EGLN5, GSLU1 (metadata incl. datums); bbox query for Alaska lakes.", "PARTIAL",
    "HLKI1 (Henrys Lake) = USGS 13039000 relay; NWPS shows 2.79 ft (a different offset than the 12.7 ft USGS/USBR stage), datum NGVD29 6437.06, impacts: 16.61 ft = 100% full WITH boards, 15.09 ft = full WITHOUT boards. GSLU1 = USGS 10010100 relay (datum 4189.8). EGLN5 = USGS 07205500, no datum. Anonymous rate limit is 10 requests / 5 min (HTTP 429 hit).",
    access="api", authority=4, notes="RELAY of USGS; use only for corroboration and for full/flood-stage statements. Wave-1 raw nwps/gauges_all.json (12,931 gauges) was used offline for the Alaska/Hawaii proximity search.")
rec("Tacoma Public Utilities - River Flows & Lake Levels page", "Tacoma Power", "https://www.mytpu.org/community-environment-parks/parks-recreation/river-flows-lake-levels/", ["WA"],
    "GET page and scan for data endpoints/WP-JSON.", "PORTAL_ONLY", "Page has no numeric lake elevation; its Riffe Lake and Lake Cushman headings link to NWRFC river_summary pages. Alder Lake boat launch text only.",
    access="portal", authority=2, notes="Real data path is NWRFC (MSRW1, CSHW1). USGS 14234800 Riffe Lake (dv 1973-2026-08) supplies history.")
rec("Oregon Water Resources Department near-real-time hydrographics", "Oregon WRD", "https://apps.wrd.state.or.us/apps/sw/hydro_near_real_time/", ["OR"],
    "ASP.NET form POST (station type R, status NRT) pages 1-2.", "PARTIAL",
    "24 near-real-time reservoir stations (Lake Abert 4251.7, Drews 4895.8, Warm Springs 3343.0, Crane Prairie 4440.2, Wickiup 4296.2, Green Peter 873.3, Applegate 1893.6 ...). None is a scope lake: no Wallowa, Crescent, Malheur Lake, Waldo, Odell, Suttle or Timothy.",
    access="portal", authority=2, notes="Useful only for re-pointing other Oregon reservoirs; displayed through HTML form (no documented API).")
rec("Denver Water supply data (Water Watch report / reservoir page)", "Denver Water", "https://www.denverwater.org/your-water/water-supply-and-planning/supply-data-and-reports", ["CO"],
    "Web search + page references; CO DWR telemetry list queried by county (Park, Summit) for Eleven Mile.", "PORTAL_ONLY",
    "Eleven Mile: only weekly PDF 'Water Watch' (percent full / contents, e.g. 102% in May 2024); no elevation feed. Dillon is available via CO DWR (see above).", access="pdf", authority=2,
    notes="Spillway/normal high water 8,597 ft, min pool 8,490 ft, dam top 8,602 ft (Denver Water elevation-area-capacity table).")
rec("Mono Lake level tables (Mono Lake Committee / LADWP)", "Mono Lake Committee, LADWP", "https://www.monobasinresearch.org/data/levelyearly.php", ["CA"],
    "GET yearly level page; web search for current level.", "PORTAL_ONLY",
    "Yearly 1 October table (Excel last updated Oct-2017); LADWP/MLC annual April-1 reading 6,382.75 ft (2026-04-01). No gauge on USGS, none in CDEC (Grant/Crowley are other lakes).", access="portal", authority=2,
    notes="Not live, 1-2 readings per year.")
rec("Lassen County Eagle Lake monthly survey", "Lassen County Surveyor", "https://susanvillestuff.com/eagle-lake-rises-nearly-two-inches-in-past-month-still-slightly-below-2025-mark/", ["CA"],
    "Web search; USGS bbox query (only 'Eagle Lk trib' and Pine Creek stream gauges); CDEC list.", "PORTAL_ONLY",
    "Monthly manual reading at Gallatin ramp (5,095.18 ft April 2026) reported in local news; no telemetry on USGS or CDEC.", access="portal", authority=3, notes="Not machine-readable, 1 reading/month.")
rec("Salton Sea elevation (USGS 10254005 / USBR LC map / Pacific Institute)", "USGS, USBR Lower Colorado, Pacific Institute", "https://waterdata.usgs.gov/monitoring-location/10254005/", ["CA"],
    "USGS iv period P30D and dv full period; web search.", "STALE",
    "USGS 10254005 62614 last value -244.00 ft on 2026-09-22 (gauge now sits dry); series 1987-10..2026-09-22. USBR publishes only a PDF map (SaltonSeaElevationsMap.pdf).", access="api", authority=1,
    notes="Wave-1 age 495 h still true. Pacific Institute page republishes monthly USGS values. Possible revival if USGS relocates the gauge.")
rec("USGS Pyramid Lake near Nixon (10336500)", "USGS / Pyramid Lake Paiute Tribe", "https://waterdata.usgs.gov/monitoring-location/10336500/", ["NV"],
    "iv P30D (one 00062 value), dv full period (none).", "STALE", "Non-recording gauge: single manual 00062 reading 3801.60 ft dated 2026-10-01 (12 days); no dv series.", access="api", authority=1,
    notes="Tribal fisheries program holds no public feed found.")
rec("Washoe Lake / Malheur Lake / Sevier Lake / Timothy Lake gauges", "USGS (OWRD for Malheur basin streams)", "https://waterservices.usgs.gov/nwis/dv/", ["NV", "OR", "UT"],
    "dv period 1900-present for 10348700 (Washoe), 10401800 and 10401830 (Malheur), 14208600 (Timothy); bbox site searches for Sevier Lake (404).", "NO_DATA",
    "Washoe 00062 ends 2009-06-30; Little Washoe returns -999999; Malheur 62614 ends 1989-09-25 and 72020 ends 1979-07-30; Timothy 14208600 has no data in 400 days; Sevier Lake (playa) has no gauge within 0.12 degrees.",
    access="api", authority=1, notes="Timothy Lake (PGE) publishes no public elevation feed found; Holter Lake only has the USGS 06066500 / CWMS HOLM tailwater (not acceptable).")
rec("USGS bbox searches around remaining small natural lakes (WY, MT, OR, WA, ID, NV, UT, AZ)", "USGS", "https://waterservices.usgs.gov/nwis/site/?bBox=...&hasDataTypeCd=iv,dv", ["WY", "MT", "OR", "WA", "ID", "NV", "UT", "AZ"],
    "bBox +-0.12 deg around Yellowstone, Jenny, Whitefish, Waldo, Wallowa, Lake Crescent, Redfish, Ruby, Odell, Fish (UT), Suttle, Lake Mary, Holter.", "NO_DATA",
    "Only stream sites returned (e.g. Yellowstone River at Yellowstone Lk Outlet 06186500, Waldo Lake Outlet 14147000, Wallowa River gauges, Lyre River, Salmon River/Redfish Lake Creek, Odell Creek); Yellowstone, Ruby and Sevier return HTTP 404 (nothing). No lake-surface-elevation series.",
    access="api", authority=1, notes="Outlet stream stage is NOT acceptable as lake level. Satellite altimetry (not tested) is the only systematic proxy for these natural lakes.")
rec("Alaska lakes: USGS + NWPS search", "USGS, NOAA NWPS", "https://waterservices.usgs.gov/nwis/site/ ; https://api.water.noaa.gov/nwps/v1/gauges", ["AK"],
    "USGS site bbox (+-0.25 deg) with hasDataTypeCd=iv,dv for 12 lakes; USGS stateCd=AK siteType=LK listing (6 with iv/dv); NWPS wave-1 raw gauge list nearest-3 per lake; iv liveness check of candidate outlet streams.", "NO_DATA",
    "No lake-level gauge for Aleknagik, Becharof, Kenai, Kvichak/Ugashik, Lake Clark, Naknek, Skilak, Teshekpuk (USGS 15829995 outlet site has no iv/dv), Tustumena, Iliamna, Big Lake, Harding. NWPS has INACTIVE lake gauges AKDA2 (Aleknagik Lake, 2.8 km) and LNKA2 (Lake Nerka). The 4 AK LK sites with data are Long Lk (Juneau), a glacial lake, Black Lk (Chignik) and Fish Cr, none in scope.",
    access="api", authority=1,
    notes="PROXIES (outlet/inflow streams, live 2026-10-12 23:00-23:30 AK): Skilak/Kenai - USGS 15266110 Kenai R bl Skilak Lk outlet (00060+00065), 15258000 Kenai R at Cooper Landing; Tustumena - 15242000 Kasilof R nr Kasilof (00065); Iliamna - 15300500 Kvichak R at Igiugig (00060+00065); Big Lake - 15294005 Willow C / Little Susitna; Harding - 15484000 Salcha R. These are discharge/stage of streams, not lake elevation. Satellite lake-altimetry products (DAHITI, Hydroweb, G-REALM) are not tested here.")
rec("Hawaii reservoirs: USGS + NWPS search", "USGS, NOAA NWPS", "https://waterservices.usgs.gov/nwis/site/?stateCd=HI&siteType=LK", ["HI"],
    "USGS stateCd=HI siteType=LK with iv/dv (14 reservoirs); bbox around Nuuanu, Waimaluhia, Puu Loa, Waita, Koele, Wilson/Kaelepulu, Waiakea, Waiau, Halulu; NWPS nearest gauges from wave-1 raw list.", "NO_DATA",
    "USGS HI lake sites are Alexander, Ka Loko, Puu Ka Ele, Koolau, Ku Tree, Wahiawa (16210000, live stage), Helemano, Kemoo, Upper Kapahi reservoirs: none of the scope reservoirs. Waimaluhia (Hoomaluhia, USACE) is absent from every CWMS office (POH has zero public series). NWPS only has stream gauges 2-10 km away.",
    access="api", authority=1,
    notes="Proxy: none valid. Nearest live reservoirs with levels (out of scope): Wahiawa Reservoir 16210000 (00065), Kauai Alexander Reservoir 16051500 (no recent data). Honolulu BWS (Nuuanu), Grove Farm (Waita), private irrigation (Puu Loa, Koele) publish nothing.")
rec("Holter Lake / NorthWestern Energy, Timothy Lake / PGE, Flagstaff Lake Mary, Seattle City Light, PacifiCorp, Idaho Power (utility pages)", "utilities", "n/a", ["MT", "OR", "AZ", "WA", "ID"],
    "Web searches for public elevation feeds/API (Holter, Timothy, Lake Mary); NWRFC and CWMS station lists checked for the same names.", "NO_API",
    "No machine-readable pool elevation found: Holter appears only as tailwater (USGS 06066500, CWMS NWDM HOLM.Stage 3.3 ft) or as FWP static values; Timothy only in a 2005 USGS report (PGE-supplied month-end elevations) and USGS 14208600 with no data; Lake Mary not in USGS/NWRFC.", access="portal", authority=2,
    notes="Would need operator contact (NorthWestern Energy Holter, PGE Clackamas relicensing data, City of Flagstaff).")

# ------------------------------------------------------------------ per-lake dead ends / unsourced
LAKE = {
    "Malheur Lake|OR": ("USGS 10401800/10401830 (history ends 1989/1979), OWRD Malheur Lake basin list (streams only)", "natural playa-marsh lake, gauges discontinued"),
    "Sevier Lake|UT": ("USGS bbox, directory", "terminal playa, usually dry; no gauge (USGS 10218500 is Sevier Bridge Reservoir, a different water body 107 km away)"),
    "Eagle Lake|CA": ("CDEC station list, USGS bbox, Lassen County monthly survey", "no telemetry; monthly manual reading in local news only"),
    "Mono|CA": ("Mono Basin Research yearly table, LADWP/MLC press releases, CDEC list", "1-2 manual readings per year; no gauge"),
    "Salton Sea|CA": ("USGS 10254005 (last obs 2026-09-22), USBR LC elevations PDF", "gauge stranded dry; no replacement"),
    "Eleven Mile Reservoir|CO": ("CO DWR telemetry (not listed), Denver Water Water Watch PDF, NWPS EVNC2 (no obs)", "operator publishes percent-full PDF only"),
    "Holter Lake|MT": ("USGS 06066500 and CWMS NWDM HOLM (tailwater), NorthWestern Energy pages", "only tailwater stage is public"),
    "Pyramid Lake|NV": ("USGS 10336500 (one manual reading 2026-10-01)", "non-recording gauge"),
    "Washoe Lake|NV": ("USGS 10348700 (ended 2009), 10348800 (-999999)", "gauge discontinued"),
    "Timothy Lake|OR": ("USGS 14208600 (no data), NWRFC list, PGE web", "operator publishes nothing machine-readable"),
    "Yellowstone Lake|WY": ("USGS bbox (06186500 is the Yellowstone River at the outlet, discharge), NPS", "no lake gauge"),
    "Lake Mary|AZ": ("USGS bbox (Newman Canyon stream only), SRP API (not an SRP lake), NWRFC", "City of Flagstaff publishes no feed found"),
    "Whitefish Lake|MT": ("USGS bbox (Swift Cr, Whitefish R)", "no lake gauge"),
    "Waldo Lake|OR": ("USGS 14147000 Waldo Lake outlet (stream), OWRD list", "no lake gauge; natural lake"),
    "Wallowa Lake|OR": ("USGS Wallowa River sites, OWRD reservoir list (not present), CWMS NWDP EWAO stream stage", "no lake gauge; irrigation-district dam has no public feed found"),
    "Lake Crescent|WA": ("USGS bbox (Lyre River, Lake Mills stream)", "no lake gauge; natural NPS lake"),
    "Redfish Lake|ID": ("USGS 13293890 / 13293900 Redfish Lake Creek stream gauges", "no lake gauge"),
    "Ruby Lake|NV": ("USGS bbox (HTTP 404, nothing)", "refuge marsh, no gauge"),
    "Odell Lake|OR": ("USGS Odell Creek 14055500, Crescent Cr", "no lake gauge; natural"),
    "Fish Lake|UT": ("USGS Fremont R bl Fish Lake 09329000, Seven Mile Cr", "no lake gauge"),
    "Suttle Lake|OR": ("USGS Lake Creek near Sisters 14088000", "no lake gauge"),
    "Jenny Lake|WY": ("USGS bbox (Cottonwood Creek, Snake River at Moose); Jackson Lake 13010500 is a different lake 15 km away", "no lake gauge; natural NPS lake"),
    "Aleknagik|AK": ("NWPS AKDA2 (INACTIVE), USGS bbox (Wood River nr Aleknagik 15303000 has no iv)", "gauge discontinued; proxy none live"),
    "Becharof|AK": ("USGS/NWPS bbox (404/none); nearest NWPS NAKA2 inactive 86 km", "no gauge; proxy none"),
    "Kenai|AK": ("USGS 15266110/15258000 (Kenai R stage live), NWPS SKLA2", "no lake gauge; outlet-stream proxy only"),
    "Kvichak / Ugashik|AK": ("USGS bbox (404); Kvichak R at Igiugig 15300500 is 56 km from the point", "no lake gauge; proxy 15300500 (Iliamna outflow)"),
    "Lake Clark|AK": ("USGS Tanalian R 15298000, Iliamna R 15300300; NWPS CPAA2 inactive", "no lake gauge"),
    "Naknek|AK": ("NWPS NAKA2 '[INACTIVE] Naknek River at Lake Camp'", "gauge discontinued"),
    "Skilak|AK": ("USGS 15266110 Kenai R bl Skilak Lk outlet (00065 live), NWPS SKLA2", "no lake gauge; outlet-stream proxy only"),
    "Teshekpuk|AK": ("USGS 15829995 Teshekpuk Lk outlet (site only, no iv/dv)", "no data"),
    "Tustumena|AK": ("USGS 15242000 Kasilof R nr Kasilof (00065 live), NWPS KSFA2", "no lake gauge; outflow proxy only"),
    "Big Lake|AK": ("USGS bbox (Deception C 15294010), Willow C 15294005", "no lake gauge"),
    "Harding|AK": ("USGS Salcha R 15484000", "no lake gauge"),
    "Iliamna|AK": ("USGS Roadhouse C, Kvichak R at Igiugig 15300500", "no lake gauge; outflow proxy only"),
    "Koele ponds (Lanai)|HI": ("USGS HI LK list, NWPS nearest (26 km)", "private former plantation ponds; no data"),
    "Nuuanu Reservoir|HI": ("USGS HI LK list (nearest Koolau/Ku Tree 21 km), NWPS Kalihi stream", "Honolulu BWS publishes nothing"),
    "Puu Loa Reservoir|HI": ("USGS Alexander Reservoir 16051500 (19 km), NWPS Kawaikoi", "private irrigation; no data"),
    "Waimaluhia Reservoir|HI": ("CWMS POH catalog empty; NWPS Kawa/Kaneohe streams", "USACE Honolulu flood-control reservoir has no public series"),
    "Waita Reservoir|HI": ("USGS Alexander Reservoir 16051500 (8 km, no recent value)", "Grove Farm private; no data"),
    "Halulu Lake (Niihau)|HI": ("USGS/NWPS (nearest stream 52 km)", "natural playa; no data"),
    "Lake Waiau|HI": ("USGS/NWPS (nearest stream 24 km)", "natural alpine lake; no data"),
    "Waiakea Pond|HI": ("USGS/NWPS (Wailuku R 6 km)", "estuarine pond; no data"),
    "Wilson Lake / Kaelepulu Pond|HI": ("USGS/NWPS Kawainui Marsh KMSH1 (stream)", "coastal pond; no data"),
}
have = {c["lakeId"] for c in cand}
for lid, (tried, why) in LAKE.items():
    if lid in have:
        continue
    N.append(dict(source=f"per-lake dead end: {lid}", org="various", url="n/a", scope=[lid], tested=tried, result="NO_DATA", evidence=why, lakesUnlocked=[], history="none", access="portal", authority=1, license="n/a", notes=""))

json.dump(N, open(f"{B2}/notes/west.json", "w"), indent=1)
print(len(N), "records;", len(have), "lakeIds with candidates")
