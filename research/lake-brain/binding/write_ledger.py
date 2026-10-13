"""Write ledger/binding.jsonl (source/blocker/action/dataset/score records) + append MANIFEST rows. Numbers come from binding_summary.json."""
import json, os, hashlib
from common import *

REPO = "/Users/mcather/Desktop/Development/Sector_Engine"
S = json.load(open(f"{REPO}/docs/research/lake-brain/data/binding_summary.json"))
T = "2026-10-13"
src = []
def source(i, name, org, url, dtype, cov, tc, cad, access, auth, dec, reason, lakecov="", notes="", supports="binding", dims=None):
    src.append(dict(kind="source", id=f"S-binding-{i:03d}", question="Q-binding", name=name, org=org, url=url, accessed=T, dataType=dtype, geoCoverage=cov, lakeCoverage=lakecov,
                    timeCoverage=tc, cadence=cad, machineReadable=True, access=access, license="US public domain / public data", authority=auth, supports=supports,
                    scoreDimensions=dims or ["sourceAuthority", "trendQuality", "historyQuality"], decision=dec, reason=reason, localPath="binding/", checksum="", notes=notes))

source(1, "USGS NWIS site service + series catalog (legacy waterservices)", "USGS", "https://waterservices.usgs.gov/nwis/site/", "site inventory with parameter/period-of-record catalog (seriesCatalogOutput)", "US", "1900-present", "daily/15min", "api", 1, "ACCEPTED",
       "Works 2026-10-13. siteOutput=expanded+seriesCatalogOutput is rejected (HTTP 400); use basic + seriesCatalogOutput; 404 means no match. siteType LK per state plus ST/ES/SP with reservoir-elevation params 62614/62615/62616/00062/72020/72022.", notes="iv/dv services used for probes and history. Legacy NWIS is scheduled for retirement in favour of the OGC API; see S-binding-002.")
source(2, "USGS OGC API (api.waterdata.usgs.gov/ogcapi/v0)", "USGS", "https://api.waterdata.usgs.gov/ogcapi/v0/collections", "monitoring-locations, time-series-metadata, daily, latest-continuous", "US", "-", "-", "api", 1, "LEAD",
       "Reachable (40 collections) but anonymous use hit OVER_RATE_LIMIT after about 3 requests; a free API key is required for bulk use. Not needed today because the legacy services work.", notes="Migration target; see M-B01.")
source(3, "USACE CWMS Data API (cwms-data.usace.army.mil/cwms-data)", "USACE", "https://cwms-data.usace.army.mil/cwms-data/catalog/TIMESERIES", "timeseries catalog + data + vertical-datum info", "US (offices LRH LRL LRN LRP MVK MVS SAM SAS SPA SWF SWT ... NWDP NWDM)", "to 1950s", "15min-daily", "api", 1, "ACCEPTED",
       "Default units are SI (m): pass unit=EN. Catalog extents are frozen (latest-time ~2026-09-14 on every series) so liveness must be probed with a data query. Offices NWK/NWO/NWP/NWS/NWW/POA/POH/SAC/SPN have zero public series; their data sit under offices NWDP (NWW/NWP/NWS Columbia basin) and NWDM (Missouri mainstem).", notes="Reproduces Hartwell: SAS hourly pool silent 116.9 h (stale) while USGS 02187010 is live.")
source(4, "USACE Access2Water reporting API", "USACE", "https://water.usace.army.mil/cda/reporting/providers/{district}/locations", "project locations with NIDID alias, latest forebay/pool elevation, operator levels (Top of Normal, Top/Bottom of Flood, Top of Inactive)", "US all districts incl. NWK/NWO/NWW/NWP/NWS", "latest + levels", "hourly-daily", "api", 1, "ACCEPTED",
       "Single GET per district returns every project with geometry, NIDID alias and published conservation/flood levels: best single source for DIRECT_OPERATOR_POOL, operatorPlan and floodDroughtContext evidence. No history endpoint here; history comes from CWMS Data API (office NWDP/NWDM etc.).", dims=["sourceAuthority", "operatorPlan", "floodDroughtContext", "trendQuality"])
source(5, "USBR RISE API", "USBR", "https://data.usbr.gov/rise/api/", "Lake/Reservoir Elevation + Storage daily series", "Western US", "decades", "daily", "api", 1, "ACCEPTED",
       "233 daily non-modeled elevation series; location-to-item link only via catalog-record relationships; filters use dateTime[after]/dateTime[before]. Data lag up to ~2 days.")
source(6, "TWDB Water Data for Texas reservoirs", "Texas Water Development Board", "https://www.waterdatafortexas.org/reservoirs/recent-conditions.json", "daily reservoir elevation, conservation pool elevation, per-reservoir history CSV", "Texas (122 reservoirs)", "1999-present", "daily", "api", 1, "ACCEPTED",
       "State-compiled relay of USACE/river-authority data, so not counted as independent corroboration. Provides conservation-pool elevation as an independent check of directory fullPoolFt.")
source(7, "NOAA NWPS gauges API", "NOAA/NWS", "https://api.water.noaa.gov/nwps/v1/gauges", "observed pool elevation (pedts HP) at 903 gauges", "US", "latest ~30d", "15min-hourly", "api", 1, "ACCEPTED",
       "One bulk call returns all gauges with latest observation (13 MB). No long history; relay of USACE/USGS data, so counted as live check only, not as independent corroboration or history.")
source(8, "NOAA CO-OPS Great Lakes water level", "NOAA", "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=waterlevels", "Great Lakes IGLD85 water levels", "Great Lakes (52 stations)", "decades", "6min", "api", 1, "ACCEPTED",
       "Stations are at harbours, named for the town; lake identity needs polygons (the five Great Lakes have none in the engine set).")
source(9, "TVA RestApi (locations, observed-data-48-hours, operating-guide)", "TVA", "https://www.tva.com/RestApi/locations", "hourly reservoir elevation, daily guide curve and operating zone", "Tennessee/Cumberland systems (43 dams)", "48h + 2y guide", "hourly", "api", 1, "ACCEPTED",
       "Needs a browser User-Agent and Accept: application/json (plain curl is served the Cloudflare/ServiceStack HTML). 43 locations reachable, includes Cumberland dams (Barkley, Center Hill, Cordell Hull, Dale Hollow, Old Hickory, Wolf Creek, J Percy Priest). History beyond the 2-year guide is not available from TVA.")
source(10, "National Inventory of Dams (USACE) via hosted ArcGIS FeatureServer NID_v1", "USACE NID", "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/NID_v1/FeatureServer/0", "dam points, names, rivers, owners, purposes, storage", "US 92,627 dams", "current", "periodic", "api", 1, "ACCEPTED",
       "Paged download works (46 pages of 2000). Official nid.sec.usace.army.mil/api/nation/csv returns 403 and /api/dams/* 404 for anonymous callers (see source 11).", dims=["coverage"])
source(11, "NID official API / bulk export (nid.sec.usace.army.mil)", "USACE NID", "https://nid.sec.usace.army.mil/api/nation/gpkg", "bulk gpkg/csv", "US", "-", "-", "bulk", 1, "DEAD_END",
       "csv endpoint 403; gpkg redirects to an S3 docs URL; dams search routes not found. The hosted FeatureServer in source 10 supersedes it.")
source(12, "WWDH (Internet of Water) USACE EDR mirror", "Internet of Water / Western Water Data Hub", "https://api.wwdh.internetofwater.app/collections/usace-edr", "mirror of the Access2Water data", "US", "-", "-", "api", 3, "LEAD", "Same data as source 4 via OGC EDR; unnecessary since source 4 is first-party.")
source(13, "California CDEC JSONDataServlet", "CA DWR", "https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet", "daily reservoir elevation (sensor 6) by station code", "California", "decades", "daily", "api", 1, "LEAD",
       "Data call works (ORO checked) but there is no machine-readable national station index to auto-match lakes; needs a curated station list. Only the California lakes outside USACE/USBR/USGS coverage would use it.")
source(14, "Colorado DWR CDSS telemetry REST", "CO DWR", "https://dwr.state.co.us/Rest/GET/api/v2/telemetrystations/telemetrystation/", "telemetry stations incl. GAGE_HT", "Colorado", "-", "15min", "api", 1, "LEAD", "Reachable; not integrated (few CO lakes outside USBR/USACE/USGS).")
source(15, "Operator pages without APIs: Alabama Power, Duke Energy, Georgia Power, Santee Cooper, SRP, LCRA, Dominion, state DEPs", "operators", "-", "lake level web pages", "SE/SW", "-", "-", "portal", 4, "LEAD",
       "Not probed for APIs in this thread; USGS or CWMS (SAM Alabama Power projects) already cover many. Treated as page-only until proven otherwise.", dims=["sourceAuthority"])

blk = [
 dict(kind="blocker", id="B-binding-001", question="Q-binding", missing="Reviewed (human) sign-off on machine-verified bindings", why="Rubric counts only REVIEWED bindings; machine verification is evidence, not a review", scoreDimension="coverage", impact="+0.0 until adopted", attempted=["automated probe reproduces all 5 hand-reviewed pilots"], proxy="review ledger with pre-registered criteria", michaelAction=True, priority="high", status="OPEN"),
 dict(kind="blocker", id="B-binding-002", question="Q-binding", missing="Level source for natural/small lakes with no gauge", why="No national system lists levels for most NE/AK/HI/DE/NH/VT/ME natural lakes or small state-park ponds", scoreDimension="coverage", impact="caps coverage below ~75%", attempted=["USGS LK catalog", "CWMS", "RISE", "NWPS", "TWDB", "CO-OPS"], proxy="none", michaelAction=False, priority="medium", status="OPEN"),
 dict(kind="blocker", id="B-binding-003", question="Q-binding", missing="Daily history >=5 complete years for sources with only a live window (NWPS, TVA, A2W latest)", why="NWPS keeps about 30 days; TVA keeps 2 years", scoreDimension="historyQuality", impact="see binding_summary.json", attempted=["pair with CWMS/USGS daily series at the same site"], proxy="CWMS/USGS history at same site", michaelAction=False, priority="medium", status="WORKED_AROUND"),
 dict(kind="blocker", id="B-binding-004", question="Q-binding", missing="USGS OGC API key", why="Anonymous rate limit trips after ~3 requests; legacy NWIS service retirement would break the pipeline", scoreDimension="coverage", impact="risk only", attempted=["anonymous calls"], proxy="legacy waterservices (works today)", michaelAction=True, priority="low", status="OPEN"),
 dict(kind="blocker", id="B-binding-005", question="Q-binding", missing="Great Lakes / Great Salt Lake polygons", why="No engine polygons for the 5 Great Lakes and Great Salt Lake so spatial matching falls back to name + 25 km", scoreDimension="coverage", impact="small", attempted=["name match"], proxy="name match", michaelAction=False, priority="low", status="WORKED_AROUND"),
 dict(kind="blocker", id="B-binding-006", question="Q-binding", missing="Official anonymous NID API", why="nid.sec.usace.army.mil returns 403", scoreDimension="coverage", impact="none (hosted FeatureServer works)", attempted=["csv", "gpkg", "dams search"], proxy="hosted ArcGIS NID_v1", michaelAction=False, priority="low", status="WORKED_AROUND"),
]
act = [
 dict(kind="action", id="M-B01", what="Optional: create a free USGS API key (api.waterdata.usgs.gov/signup) and store it as a Sector secret so the pipeline can move off the legacy NWIS service", impact="resilience only", priority="low", relatedBlocker="B-binding-004"),
 dict(kind="action", id="M-B02", what="Review and approve the machine-verified binding ledger (research/lake-brain data: verified_bindings.csv) in batches; spot-check the REVIEW-flag rows only", impact="lifts coverage ladder points once adopted as REVIEWED", priority="high", relatedBlocker="B-binding-001"),
]
ds = []
def dataset(path, track, ret, rebuild, note):
    p = f"{DATA}/{path}"
    if not os.path.exists(p):
        return
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    ds.append(dict(kind="dataset", path=path, bytes=os.path.getsize(p), sha256=h, track=track, retention=ret, rebuild=rebuild, note=note))
dataset("binding/catalog.jsonl", "binding", "REBUILDABLE", "python research/lake-brain/binding/build_catalog.py", "normalised series catalog (USGS/CWMS/A2W/RISE/TWDB/NWPS/CO-OPS/TVA)")
dataset("binding/candidates_all.csv", "binding", "REBUILDABLE", "python research/lake-brain/binding/match.py", "static candidate matches (12 per lake)")
dataset("binding/candidates.csv", "binding", "KEEP", "python research/lake-brain/binding/verify.py", "evaluated candidates with review-criteria results")
dataset("binding/verified.csv", "binding", "KEEP", "python research/lake-brain/binding/finalize.py", "per-lake chosen binding with history class")
dataset("binding/probe_results.json", "binding", "KEEP", "python research/lake-brain/binding/probe.py", "live probe results 2026-10-13")
dataset("binding/history_results.json", "binding", "KEEP", "python research/lake-brain/binding/history.py", "year-completeness per candidate site")
dataset("binding/nid_links.csv", "binding", "REBUILDABLE", "python research/lake-brain/binding/nid_link.py", "lake -> NID dam links")
dataset("binding/spotcheck.csv", "binding", "KEEP", "python research/lake-brain/binding/spotcheck.py", "independent spot-check table")
dataset("binding/raw/nid/nid.jsonl", "binding", "REBUILDABLE", "python research/lake-brain/binding/fetch_nid.py", "NID 92,627 dams")
for n in ("raw/usgs", "raw/cwms", "raw/a2w", "raw/rise", "raw/nwps", "raw/twdb", "raw/coops", "raw/tva", "raw/probe", "history"):
    ds.append(dict(kind="dataset", path=f"binding/{n}/", bytes=sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(f"{BIND}/{n}") for f in fs), sha256="", track="binding", retention="REBUILDABLE", rebuild="fetch_*.py / probe.py / history.py in research/lake-brain/binding", note="raw provider downloads and cached probes/history (2026-10-13)"))
scores = [dict(kind="score", step="binding-machine-verification", previous=0.8, candidate=S["pctCore"], dimensions={"coveragePctCore": S["pctCore"], "coveragePctStrict": S["pctStrict"], "coveragePctWithStageOnly": S["pctWithStage"], "ladderPointsStrict": S["ladderPointsStrict"], "coreLakes": S["core"], "flaggedLakes": S["flagged"], "coreWith5yHistory": S["coreHistory"].get("SUFFICIENT")},
               evidence="binding_summary.json", confidence="medium: machine-verified, not human-reviewed", remaining="human review adoption; history for no-5y sites")]
with open(f"{REPO}/docs/research/lake-brain/ledger/binding.jsonl", "w") as f:
    for r in src + blk + act + ds + scores:
        f.write(json.dumps(r) + "\n")
man = f"{DATA}/MANIFEST.jsonl"
have = set(json.loads(l).get("path") for l in open(man))
with open(man, "a") as f:
    for r in ds:
        if r["path"] not in have:
            f.write(json.dumps(r) + "\n")
print(len(src), len(blk), len(act), len(ds))
