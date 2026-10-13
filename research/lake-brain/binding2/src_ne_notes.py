"""Source-evaluation records for area "ne" (imported by src_ne.py -> notes/ne.json).

authority scale used (1-7): 7 = federal/state agency of record publishing its own gauge; 6 = dam owner/operator or water utility publishing its own level;
5 = official relay/aggregation of an agency series (NWS/NWPS); 4 = periodic report (monthly/weekly PDF); 3 = third-party/hobby aggregator; 1-2 = no usable data.
"""
import json, os
B2 = "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/binding2"
NE = {"ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "PA", "DE", "MD", "OH"}


def _cands():
    p = f"{B2}/cand/ne.jsonl"
    out = []
    if os.path.exists(p):
        out = [json.loads(l) for l in open(p) if l.strip()]
    return out


def _lakes(prov, **kw):
    return sorted({c["lakeId"] for c in _cands() if c["prov"] == prov and all(c.get(k) == v for k, v in kw.items())})


def build():
    prof = json.load(open(f"{B2}/unbound_profile.json"))
    scope = [r for r in prof if r["state"] in NE and not r["name"].startswith("Lake Erie") and r["name"] != "Lake Ontario"]
    ids = {r["lakeId"]: r for r in scope}
    have = {c["lakeId"] for c in _cands()}
    N = []

    def add(**k):
        k.setdefault("lakesUnlocked", [])
        k.setdefault("notes", "")
        N.append(k)

    # ------------------------------------------------------------------------------------------------ working sources
    add(source="NHDES real-time lake-level platform (RTI 'Amanzi', Dam Bureau telemetry)", org="NH Department of Environmental Services, Dam Bureau",
        url="https://nhdes.rtiamanzi.org/  (REST: /api/locations/?layer__code=STATIONS, /api/timeseries/?location__code=X&parameter__code=PELV, /api/timeseries/<id>/values/?start=&end=)",
        scope=["NH"],
        tested="GET /api/locations/?layer__code=STATIONS (147 stations, no auth), /api/timeseries/?parameter__code=PELV (67 pool-elevation series), /api/timeseries/<id>/values per year 2010-2026, location DATUM_TEXT fields.",
        result="WORKS",
        evidence="Public JSON API, no token needed (the SPA only logs in for editing). Hourly 'Observed Reservoir Pool Elevation' (PELV.PT1H, ft) for 31+ NH lakes; values last 06:00Z 2026-10-13 (age ~2 h). Winnipesaukee 502.52 ft (DES MSL = 500 + gauge), Squam 561.18, Sunapee 1091.98, Newfound 586.45, Winnisquam 482.33, Ossipee 407.33. Station DATUM_TEXT gives 'Full Lake' stage and 'Local = <full-lake elevation> NGVD29'. History retrievable back to 2010-04-21 (15 complete years).",
        lakesUnlocked=_lakes("nhdes"), history="2010-04 .. now, hourly (daily means in history/nhdes_*)", access="api", authority=7,
        license="Public data; NHDES disclaimer: provisional, informational, use at own risk",
        notes="Best general method of the area. Stations without a lake in the directory-unbound list (Mascoma, Highland, Pawtuckaway, Bow, Northwood, Silver Lake Harrisville, ...) are also live (see raw/ne/rti_pelv.json) and may serve other lakes. MAN-entry stations (Great Pond, Grafton Pond, Lovell, Suncook, ...) are weekly manual readings, not live. Great East Lake last obs 2026-10-10 23:00Z (56 h, still passes the 72 h hourly rule). Not present on the platform: Wentworth, Merrymeeting, Massabesic, Umbagog, First Connecticut Lake. Station LFRNH is Murphy Dam on Lake Francis, NOT First Connecticut Lake (directory conflates). NFLNH history has a low outlier (min 530.7 ft) that should be screened.")

    add(source="Brookfield Renewable 'Safe Waters' public facility pages", org="Brookfield Renewable North America (dam owner/operator; Great Lakes Hydro America, Brookfield White Pine, Brookfield Power PA)",
        url="https://www.safewaters.com/facility/<slug>/  (list: https://www.safewaters.com/facility-sitemap.xml, 51 facilities)", scope=["ME", "NH", "PA", "MD", "NY"],
        tested="Fetched all 51 facility pages (server-rendered HTML, 1 req/s); parsed '<h5>NNNN.NN ft as of <local time></h5>' pond-elevation lines. WP REST (wp-json) exposes no facility post type; admin-ajax not needed.",
        result="PARTIAL",
        evidence="Live pond elevations in ft above sea level, updated 15-60 min: Wallenpaupack 1174.53 (matches PPL/Brookfield 2026 drawdown schedule 1174.0-1174.5 for week of 10/4), Moosehead (E&W outlet) 1026.12, Flagstaff 1140.91, Rangeley 1516.53, Upper Dam (Mooselookmeguntic) 1461.50, Errol (Umbagog) 1243.49. Only the CURRENT value is published (no chart data, no history, no JSON): series must be accumulated by polling.",
        lakesUnlocked=_lakes("safewaters"), history="none (current value only)", access="portal", authority=6,
        license="Public safety information; terms not stated. Hourly polling of ~6 pages is light.",
        notes="Datum not stated (operator datum, feet above sea level; plausible NGVD29). Other live Safe Waters pond elevations in the region (lakes not in the unbound list or already bound): Aziscohos 1506.13, Graham Lake 96.61, Middle Dam (Richardson lakes) 1444.29, North Twin 488.86, Millinocket Lake 477.56, Williams 316.83, Wyman 483.69, Harris/Indian Pond 952.70, Brassua 350.00 (looks like a stage, not elevation), Holtwood 169.09, Safe Harbor 226.64, Deep Creek 2458.81. NOT available: Chesuncook (Ripogenus/McKay page shows flow only), Seboomook, Canada Falls, Ragged, Caucomgomoc (flow only), West Grand (not Brookfield). Wave-1 would not have seen this source (no API).")

    add(source="USGS NWIS (iv/dv/site services), 12-state series-catalog scan", org="U.S. Geological Survey",
        url="https://waterservices.usgs.gov/nwis/{iv,dv,site}", scope=sorted(NE),
        tested="nwis/site?seriesCatalogOutput=true&stateCd=XX for parm 00062,62614,62615,62616,72020,72214 (any site type) and 00065 (LK,SP) in all 12 states; iv 30 d + dv/iv history for each hit; proximity (12 km) join with every unbound lake; nwis/iv without parameterCd for the lake sites named in the task.",
        result="PARTIAL",
        evidence="162 live (end >= 2026-09-01) lake/reservoir elevation series in the 12 states, but only 4 sit on unbound lakes: West Grand Lake 01018900 (62615, NAVD88, 296.29 ft, 2010-), Youghiogheny River Lake 03077000 (62615, 1438.83 ft, iv since 2007), Lake Arthur 03106280 (00062, last obs 2026-10-06 = 7 d old, 2007-), plus Haven Lake outlet 01484143 (DE, nearby alternative to Griffith Lake, 2015-). NH/RI/CT have NO live USGS lake-elevation series at all.",
        lakesUnlocked=_lakes("usgs"), history="West Grand 2010-, Youghiogheny 2007- (dv to 2015 + iv), Lake Arthur 2007-, Haven Lake 2015-", access="api", authority=7, license="Public domain (provisional data)",
        notes="West Grand Lake: directory fullPoolFt 259 ft is inconsistent with the gauge (296 ft NAVD88, 15-yr median 298.4, USGS topo ~295 ft): the lake pool is ~295-300 ft NAVD88; treat the directory value as wrong (or on a different datum) rather than the gauge. Pymatuning 03100500 (00062) stopped 2026-06-04.")

    add(source="USGS NWIS stale/discontinued lake series (history only)", org="U.S. Geological Survey",
        url="https://waterservices.usgs.gov/nwis/dv/", scope=["Pymatuning Reservoir|PA", "Lake Winnipesaukee|NH", "Lake Cochituate|MA", "Lake Bomoseen|VT", "Umbagog Lake|NH", "Skaneateles Lake|NY"],
        tested="nwis/site catalog + nwis/iv period=P30D (no parameterCd and with) for 01080000, 04279490, 01098499, 04236000, 03100500, 03106280, 01051715/01051705/01051620; dv/iv history pulled for baseline use.",
        result="STALE",
        evidence="Winnipesaukee 01080000: 00065 gage height ended 2017-09-30 (1937-2017, gauge zero 500.00 ft NGVD29; only temp/pH/cond now). Bomoseen 04279490: 62614 ended 2016-07-19. Cochituate 01098499: 00062 ended 2024-10-07. Skaneateles 04236000: 62614 ended 1995-03-31 (only WQ params remain). Pymatuning 03100500: 00062 ended 2026-06-04. Umbagog 01051715/01051705/01051620 (ME-state sites for the NH/ME lake): 62615 NAVD88 2014-07..2017-05, ended. Cranberry Lake 04260990: annual WQ only.",
        lakesUnlocked=[], history="see history/usgs_<site>_<param>.csv.gz (daily): Pymatuning 2008-2026-06 (13 complete yr), Winnipesaukee 1937-2017, Cochituate 2010-2024, Bomoseen 2002-2016, Skaneateles 1967-1995, Umbagog 2014-2017 (<=2 complete yr)",
        access="api", authority=7, license="Public domain",
        notes="Useful as baseline history if a live feed is bound (Winnipesaukee: add 500 ft; NHDES WEIN3 is the live twin; Umbagog: Safe Waters Errol is the live twin; Pymatuning: no live twin found).")

    add(source="USACE CWMS data API (NAE, LRP)", org="U.S. Army Corps of Engineers", url="https://cwms-data.usace.army.mil/cwms-data/timeseries", scope=["CT", "PA", "MD", "MA", "NH"],
        tested="timeseries + locations + levels for NAE MHD (Mansfield Hollow), LRP Youghiogheny-Lake(+Rt40), LRP Pymatuning-Outflow, NAE STV/SBD.",
        result="PARTIAL",
        evidence="Mansfield Hollow MHD.Elev (15-min, DCP-rev) live: 213.0 ft at 2026-10-13, history from 2005 (20 complete years). Wave-1 R8 'datum failure' = location MHD has no vertical-datum-info; location elevation 195.01 ft is the gauge zero, and the NAE 'Bottom of Normal' stage level (15.0-18.5 ft) gives a 210.0-213.5 ft normal pool, so Elev is an NGVD29-style elevation (assumed). LRP series (Youghiogheny-Lake, native datum NAVD88) last update 2026-09-14: the whole LRP CWMS feed has been silent for 4 weeks, so the wave-1 'candidate' is currently STALE here (but alive through USGS 03077000 and NWPS YGBP1).",
        lakesUnlocked=_lakes("cwms"), history="Mansfield Hollow 2005-2026", access="api", authority=7, license="Public domain",
        notes="Pymatuning-Outflow.Stage and Kinsman are tailwater/inflow stage, not pool (dead end). STV.Stage = Housatonic at Stevenson (river gauge below Lake Zoar dam, not pool).")

    add(source="NOAA/NWS NWPS gauges (api.water.noaa.gov/nwps/v1)", org="NOAA National Water Prediction Service", url="https://api.water.noaa.gov/nwps/v1/gauges", scope=sorted(NE),
        tested="1 bulk bbox call (1706 gauges in the region), proximity (9 km) join with all unbound lakes, /gauges/<lid> and /stageflow/observed for candidates.",
        result="PARTIAL",
        evidence="Live pool/stage-type gauges on unbound lakes: WGLM1 (West Grand, relay of USGS 01018900), YGBP1 (Youghiogheny pool 1438.79 ft, relay of USACE LRP: live although CWMS LRP is stale), MFEM2 ('North Branch Patapsco River at Liberty Reservoir', HGIRR 410.9 ft vs full pool 420 ft, source agency not stated, probably Baltimore ALERT). LLIC3 (Housatonic River at Lake Lillinonah HPIRZ) returns -999 (dead). SCFN3 (Sugar River below Lake Sunapee) is outlet stage 4.15 ft, local stage only.",
        lakesUnlocked=_lakes("nwps"), history="none (about 30 d)", access="api", authority=5, license="Public domain",
        notes="MFEM2 is the only live candidate for Liberty Reservoir; Loch Raven/Prettyboy/Triadelphia/Rocky Gorge have no NWPS pool gauge (only inflow/tailwater river gauges nearby).")

    add(source="NJ Water Supply Authority operations data (Manasquan page + Raritan weekday PDF)", org="New Jersey Water Supply Authority", url="https://www.njwsa.org/manasquan-operations-data.html ; https://www.njwsa.org/uploads/1/0/8/0/108064771/data.pdf",
        scope=["Manasquan Reservoir|NJ", "Round Valley Reservoir|NJ"],
        tested="GET both pages; parsed the HTML daily lines (Manasquan) and decoded the PDF (FlateDecode text) for Round Valley/Spruce Run elevations.",
        result="PARTIAL",
        evidence="Manasquan Reservoir daily elevation 97.56 ft (10/8/2026, last 5 days listed; full pool 100 ft). Round Valley Reservoir elevation 376.48 ft NAVD88 (10/8/2026; full pool 384.20 NAVD88; the PDF says datum changed from NGVD29 to NAVD88 on 2025-11-19, NAVD88 = NGVD29 + 0.8). Report 'Current as of 07:30 Friday Oct 09' (PDF last-modified 2026-10-09); updates on business days so age is 4-5 d on weekends/holidays.",
        lakesUnlocked=_lakes("njwsa"), history="none online (accumulate)", access="pdf", authority=6, license="Public",
        notes="Round Valley page itself shows only a picture linking to data.pdf. The same PDF carries Spruce Run (262.30 ft NAVD88 on 10/9). NJDWSC (Monksville/Wanaque) site returns 403 to automated clients.")

    add(source="MWRA Quabbin/Wachusett reservoir levels", org="Massachusetts Water Resources Authority / MA DCR", url="https://www.mwra.com/node/2411", scope=["Quabbin Reservoir|MA", "Wachusett Reservoir|MA"],
        tested="Parsed the monthly archive tables (static HTML).", result="PARTIAL",
        evidence="Elevation (ft, Boston City Base) published once a month for the 1st: Quabbin 517.64 ft (10/01/2026; full 530 ft BCB), Wachusett 391.37 ft (10/01/2026). 259/260 monthly values since 2005 saved (raw/ne/mwra_*_monthly.csv). Not live (13 d old) and not daily.",
        lakesUnlocked=[], history="monthly since 2005 (not daily)", access="portal", authority=6, license="Public",
        notes="Daily elevation exists at DCR (mass.gov 'Quabbin reservoir kiosk poster - reservoir elevation', DCR DMTF summaries) but mass.gov answers 403 to automated clients (see blocked record). Datum is Boston City Base (530 ft BCB = full reservoir per DCR/MWRA); the BCB-to-NGVD29 offset was not verified here, so treat as a local datum.")

    # ------------------------------------------------------------------------------------------------ blocked / portal-only
    add(source="mass.gov (MA DCR daily Quabbin/Wachusett elevation kiosk posters, DMTF summaries)", org="MA Dept of Conservation and Recreation", url="https://www.mass.gov/doc/quabbin-reservoir-kiosk-poster-reservoir-elevation/download",
        scope=["Quabbin Reservoir|MA", "Wachusett Reservoir|MA"], tested="GET with research UA", result="BLOCKED", evidence="HTTP 403 for the kiosk-poster document and for mass.gov info pages we tried; not bypassed.",
        lakesUnlocked=[], history="none", access="pdf", authority=7, license="n/a", notes="Contact DCR Office of Watershed Management (Belchertown) for a daily series; MWRA monthly table is the fallback.")
    add(source="NHDES website documents (Winnipesaukee chart/graph PDFs, lake level graphs)", org="NHDES Dam Bureau", url="https://www.des.nh.gov/sites/g/files/ehbemt341/files/documents/winnipesaukee-chart2026.pdf",
        scope=["NH"], tested="curl + WebFetch", result="BLOCKED", evidence="HTTP 403 for des.nh.gov documents; not needed because the RTI platform carries the same gauges.",
        lakesUnlocked=[], history="n/a", access="pdf", authority=7, license="n/a", notes="DES chart PDF: MSL correction +500 ft for Winnipesaukee (full lake 504.32 ft), 'Updated 9/3/2026'.")
    add(source="NJ District Water Supply Commission (Wanaque/Monksville)", org="NJDWSC", url="https://www.njdwsc.com/", scope=["Monksville Reservoir|NJ"], tested="GET /", result="BLOCKED",
        evidence="HTTP 403. USGS 01386990 is Wanaque Reservoir (live 62614) and NWPS WRDN4 Wanaque elevation 291.85 ft, but Monksville (upstream, 5.9-7.5 km away) has no gauge found.",
        lakesUnlocked=[], history="none", access="portal", authority=6, license="n/a", notes="Greenwood Lake USGS 01383000 is a different lake.")
    add(source="Great River Hydro 'Waterline' (h2oline.com) + greatriverhydro.com", org="Great River Hydro / Virtual Publishing", url="http://www.h2oline.com/srcs/505126.html",
        scope=["Harriman Reservoir (Whitingham)|VT", "Somerset Reservoir|VT", "First Connecticut Lake|NH"], tested="Site pages 505126 (Harriman), 505124 (Somerset), 335123 (Murphy), 335122 (1st CT Lake), state index pages VT/NH/MA/ME/CT.",
        result="NO_DATA", evidence="Waterline reports river FLOW below the dams (CFS, spill/powerhouse) only; no reservoir elevation. greatriverhydro.com facility pages list only static pool elevations (Harriman 1480.66 ft, Somerset 2133.58 ft).",
        lakesUnlocked=[], history="none", access="portal", authority=6, license="n/a", notes="")
    add(source="FirstLight Power (Candlewood, Zoar, Lillinonah)", org="FirstLight Power", url="https://firstlight.energy/locations/connecticut/", scope=["Candlewood Lake|CT", "Lake Zoar|CT", "Lake Lillinonah|CT"],
        tested="Site map + facility/location/water-management/flood-notification pages; Candlewood Lake Authority and Lake Zoar Authority sites.", result="NO_API",
        evidence="Levels are given only via the 888-417-4837 automated phone line and press releases (normal summer ranges: Candlewood 429.5-427 ft, Zoar 103-100.5, Lillinonah 200-195.5). NWPS LLIC3 (Lake Lillinonah) returns -999.",
        lakesUnlocked=[], history="none", access="portal", authority=6, license="n/a", notes="USACE NAE 'STV' stage is the Housatonic at Stevenson dam tailwater, not the pool.")
    add(source="Maryland / Baltimore reservoirs (Baltimore City DPW, MDE drought reports, WSSC, Constellation Conowingo)", org="Baltimore City DPW; MDE; WSSC Water; Constellation", url="https://publicworks.baltimorecity.gov/ ; https://mde.maryland.gov/programs/water/droughtinformation",
        scope=["Loch Raven Reservoir|MD", "Prettyboy Reservoir|MD", "Liberty Reservoir|MD", "Triadelphia Reservoir|MD", "Rocky Gorge Reservoir|MD", "Conowingo Reservoir|MD", "Piney Run Lake|MD", "Lake Habeeb (Rocky Gap)|MD"],
        tested="Web search + fetch of DPW/WSSC reservoir pages (404 or no data), MDE monthly reservoir pages, NWPS/USGS/CWMS proximity scan.", result="PORTAL_ONLY",
        evidence="DPW publishes only press releases/percent-full; MDE monthly percent-full pages (latest found 2021). No pool-elevation feed for Loch Raven, Prettyboy, Triadelphia, Rocky Gorge, Conowingo (USGS 01578310 and NWPS CNWM2 are tailwater stage). Only Liberty has a gauge (NWPS MFEM2).",
        lakesUnlocked=_lakes("nwps", origin="nws-marfc-unknown"), history="none", access="portal", authority=6, license="n/a", notes="Conowingo license pool limits 101.2-110.2 ft NGVD29 (FERC), normal 109.2 ft; no public telemetry located.")
    add(source="Connecticut MDC (Barkhamsted/Nepaug) reservoir status", org="Metropolitan District Commission", url="https://www.themdc.com/drinking-water/water-supply", scope=["Barkhamsted Reservoir|CT"],
        tested="Fetched themdc.com + search", result="PORTAL_ONLY", evidence="System-wide percent-of-capacity text updated irregularly (last seen 'as of February 28, 2026'); no elevation series. USACE Colebrook Dam (NAE CRD) is a different reservoir 6.6 km away.",
        lakesUnlocked=[], history="none", access="portal", authority=6, license="n/a", notes="")
    add(source="PA DCNR / PA Fish & Boat state-park lakes (Pymatuning, Nockamixon, Marburg, Yellow Creek, Lake Arthur)", org="PA DCNR", url="https://www.pa.gov/agencies/dcnr", scope=["Pymatuning Reservoir|PA", "Lake Nockamixon|PA", "Lake Marburg|PA", "Yellow Creek Lake|PA", "Lake Arthur|PA"],
        tested="Search + USGS/CWMS/NWPS scan", result="NO_DATA",
        evidence="No DCNR level telemetry page. Only USGS carries Pymatuning (stopped 2026-06-04) and Lake Arthur (last 2026-10-06). CWMS Pymatuning-Outflow is tailwater; CWMS Yellow Creek HomerCity is Yellow Creek river stage 4.6 km from the lake.",
        lakesUnlocked=_lakes("usgs", lakeId="Lake Arthur|PA"), history="Pymatuning 2008-2026-06 (usgs_03100500_00062)", access="api", authority=7, license="n/a", notes="")
    add(source="NY: Syracuse DWD (Skaneateles), NYSDEC/Regulating district (Cranberry), NYS Canals", org="City of Syracuse; Oswegatchie River-Cranberry Reservoir Regulating District", url="n/a",
        scope=["Skaneateles Lake|NY", "Cranberry Lake|NY"], tested="Search; USGS 04236000/04260990 catalog; hinckley.canals.ny.gov (host did not resolve)", result="NO_DATA",
        evidence="Skaneateles: only annual/period PDF data sheets (e.g. 2021skaneateleslakedata.pdf: 861.26 ft on 2021-04-19) and a USGS gauge that ended 1995; aggregator pages repackage the stale USGS site. Cranberry: USGS 04260990 has annual WQ only; dam owner is a local regulating district.",
        lakesUnlocked=[], history="Skaneateles USGS 1967-1995 (history/usgs_04236000_62614)", access="pdf", authority=6, license="n/a", notes="")
    add(source="DE DNREC ponds (Andrews, Becks, Concord, Griffith, Killens, Lums, Records, Red Mill, Silver, Trap, Wagamons)", org="DE DNREC / State Parks", url="n/a",
        scope=[k for k in ids if k.endswith("|DE")], tested="USGS catalog scan (lake sites 01484143 Haven Lake outlet, 01487170 Hearns Pond, 01483745/390808075295102 Dover impoundments, 01483510 Garrisons Lake), NWPS/CWMS proximity.", result="NO_DATA",
        evidence="DNREC publishes no pond levels. USGS 62615 sites exist on other Delaware impoundments; Haven Lake outlet 01484143 (Milford) is 1.8 km from the Griffith Lake polygon and is emitted as a nearby alternative only. CWMS NAP 'Dover' = St Jones River at Dover (stream stage).",
        lakesUnlocked=_lakes("usgs", lakeId="Griffith Lake|DE"), history="Haven Lake 2015-", access="api", authority=7, license="n/a", notes="")
    add(source="State lake programs (VT DEC, ME DEP/IFW/MGS/LEA, MA DCR Lakes, CT DEEP, RI DEM)", org="various", url="n/a", scope=[k for k in ids if k.split("|")[1] in ("VT", "ME", "MA", "CT", "RI")],
        tested="Searches for lake-level telemetry/portals for each state; USGS/NWPS/CWMS proximity scan.", result="NO_DATA",
        evidence="No state publishes lake-level telemetry. VT: only Lake Champlain/Memphremagog (USGS, not unbound) and the 2016-ended Bomoseen record. ME: USGS has West Grand, Lewy, Sebago only; Brookfield covers the storage lakes. CT: only USACE Mansfield Hollow. RI/MA: Scituate and Cochituate (stale since 2024-10) only.",
        lakesUnlocked=[], history="none", access="portal", authority=1, license="n/a", notes="")

    # per-lake negative evidence for everything still uncovered
    miss = sorted(k for k in ids if k not in have)
    by = {}
    for k in miss:
        r = ids[k]
        why = "natural lake / no gauge" if r["hasDam"] in ("False", False) else "dam lake without public telemetry found"
        by.setdefault((r["state"], why), []).append(k)
    for (st, why), lst in sorted(by.items()):
        add(source=f"Per-lake negative evidence: {st} lakes ({why})", org="n/a", url="n/a", scope=lst,
            tested="USGS NWIS state catalog + 12 km proximity, NWPS 9 km proximity, wave-1 CWMS/A2W catalog proximity, operator/state portal web searches (see source records above).",
            result="NO_DATA", evidence=("; ".join(f"{k.split('|')[0]} [{ids[k]['operator']}]" for k in lst))[:900],
            lakesUnlocked=[], history="none", access="portal", authority=1, license="n/a",
            notes="Candidates for satellite-altimetry / ungauged baseline handling. Tier-B members of this group are listed in the PORTAL_ONLY/NO_API/BLOCKED records above." if any(ids[k]["bowTier"] == "B" for k in lst) else "")
    return N


NOTES = build()
