#!/usr/bin/env python3
"""Assemble jobs/depth-brain/depth_brain/data/proposals/contour_reference_pools.json (schema depth-twdb-reference-pools-v1 compatible) and
docs/brains/depth/data/contour2_source_semantics.json from the frozen prereg, the lake facts and the validation summary. PROPOSAL ONLY (not read by production).
Source statements below are what the fetched pages / attributes say (2026-10-13); 'fetched' marks what was retrieved by this study, other items are marked."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DD = REPO / "docs/brains/depth/data"
P = json.loads((REPO / "jobs/depth-brain/depth_brain/data/proposals/contour_prereg.json").read_text())
F = json.loads((DD / "contour2_lake_facts.json").read_text())["lakes"]
S = json.loads((DD / "contour2_validation_summary.json").read_text())
R = P["referenceVerification"]["rosterAndStatus"]
SHA = P["freeze"]["sha256"]

# ---- per-source semantics (task 1) -----------------------------------------------------------------------------------------------
SEM = {
 "OH": dict(org="Ohio DNR Division of Wildlife", zeroLevel="DEPTH (stored negative ft) below the water surface the agency map calls the 'normal summer pool elevation' (per-lake PDF maps, fetched 9 of 10 fleet lakes; the GIS service itself has no description, licence or datum text)", valueType="depth below stated normal summer pool (per lake map)",
   survey="per lake map: 'Reservoir last surveyed': Alum Creek 2001, Caesar Creek 1997, Grand Lake St. Marys 2004, Hoover 2001, Lake Milton 1998, Mosquito Creek 2004, Pymatuning 2008, Salt Fork 1998, Tappan 1998; GIS DT_ADDED 2014 only", waterLevelAtSurvey="not stated (maps state the pool the depths are based on, not the level on the survey date)",
   datum="maps print an elevation only; 'above mean sea level' appears for Mosquito Creek and Tappan; no NGVD29/NAVD88 label", licence="UNCLEAR (licence matrix; item metadata empty)", urls=["https://gis.ohiodnr.gov/arcgis/rest/services/DOW_Services/DOW_Lakes_Bathymetry/MapServer", "https://dam.assets.ohio.gov/image/upload/ohiodnr.gov/documents/wildlife/maps/alumcreeklake2.pdf"]),
 "NE": dict(org="Nebraska Game and Parks Commission / USBR mapping program", zeroLevel="contour attributes Depth and Elevation; Elevation + Depth is constant within a lake (range 0-0.22 ft), i.e. depth below a stated pool elevation", valueType="depth below a numeric pool elevation carried on every contour",
   survey="shape attribute SurveyDate (Box Butte 2002, Branched Oak 2003, Calamus 2003, Johnson 2008, Ogallala 2005, Merritt 2001, Sherman 2003, Swanson 2001; Harlan and McConaughy blank)", waterLevelAtSurvey="not stated; the carried elevation is a 'conservation' pool (shape attribute Conservati), which differs from the contour-implied pool for Merritt (2947.0 vs 2953.3), McConaughy (3266.4 vs 3265.0) and Ogallala (3126.3 vs 3126.5)",
   datum="not stated in the item or attributes", licence="PUBLIC_REUSABLE", urls=["https://www.arcgis.com/sharing/rest/content/items/0f0e603f248d4a4bb79f350db3780d72?f=json"]),
 "KS": dict(org="Kansas Biological Survey (KARS)", zeroLevel="'They also reference depth data to the lake elevation'; areas/volumes computed at the listed water surface elevation (PhysicalLakeData Elev_ft)", valueType="depth below the listed water surface elevation",
   survey="PhysicalLakeData Survey_yea: Cheney 2010, Clinton 2009, El Dorado 2010, Melvern 2009, Milford 2009, Pomona 2009, Wilson 2008 (survey period 2006-2013)", waterLevelAtSurvey="CONTRADICTORY: the PhysicalLakeData service text says federal reservoirs use the normal operating (conservation/multi-purpose) pool; the BathymetryContour layer text says the operating water level at the time of the survey; state/local reservoirs use the level on the survey date. Six of seven federal lakes equal the directory pool exactly; Cheney differs by 0.9 ft",
   datum="not stated", licence="ATTRIBUTION_REQUIRED", urls=["https://services.kars.geoplatform.ku.edu/arcgis/rest/services/WaterResources/PhysicalLakeData/MapServer", "https://services.kars.geoplatform.ku.edu/arcgis/rest/services/WaterResources/BathymetryContour/MapServer/layers?f=pjson"]),
 "OK": dict(org="Oklahoma Water Resources Board", zeroLevel="contour attributes depth (negative ft), elevation, vert_datum, year: elevation = pool + depth with a constant pool within most lakes", valueType="depth below a numeric pool elevation with a stated vertical datum (NGVD29 or NAVD88 per lake)",
   survey="attribute year (Fort Gibson 2012, Sardis 1999, Grand 2008, Murray 2001)", waterLevelAtSurvey="not stated; Grand (range 20 ft) and Murray (range 200 ft) have non-constant implied pools", datum="stated per lake (vert_datum)", licence="INTERNAL_ONLY (item licenseInfo 'Internal Use')", urls=["https://owrb.csa.ou.edu/server/rest/services/Surface_Water/LOK_Lakes/MapServer"]),
 "ND": dict(org="ND Game and Fish / ND GIS Hub", zeroLevel="CONTOUR (negative ft) and ELEVATION attributes; ELEVATION - CONTOUR constant per lake", valueType="depth below an implied pool elevation", survey="not in the attributes", waterLevelAtSurvey="not stated; implied pools differ from directory pools by 1.7-2.2 ft",
   datum="not stated", licence="UNCLEAR", urls=["https://ndgishub.nd.gov/arcgis/rest/services/Applications/GNF_LakeContoursCached/MapServer/info/iteminfo?f=pjson"]),
 "MN": dict(org="Minnesota DNR (lake mapping unit; digitised from lake maps)", zeroLevel="depth (negative ft); zero depth is a shoreline digitised from 1991-92 DOQ aerial photography (per the Commons dataset summary retrieved through a web-search extract; the Commons page itself is a script shell and the resources metadata URL returned 404)", valueType="depth below the water surface on the survey map (ordinary high water not stated)",
   survey="metadata layer fldw_end (fetched): Winnibigoshish 1963-10-01 (TOPO MAP/DRG), Leech 1957-07-18, two 'Gull' records: DOW 11030500 1954-07-01 and DOW 04012000 1995-05-23 (which one is the Gull Lake Dam lake was not resolved here)", waterLevelAtSurvey="not stated", datum="not stated", licence="UNCLEAR", urls=["https://gisdata.mn.gov/dataset/water-lake-bathymetry"]),
 "WV": dict(org="WV DNR (Wildlife Resources)", zeroLevel="1-ft contours from sonar processed in ReefMaster; value is depth in ft; no reference level text", valueType="depth (reference level not stated)", survey="per lake in the item description: Beech Fork 2019, Bluestone 2024, Burnsville 2023, Cheat 2011, East Lynn 2021 (lists from the item text)", waterLevelAtSurvey="not stated", datum="not stated", licence="PUBLIC_REUSABLE", urls=["https://www.arcgis.com/sharing/rest/content/items/217289890c2445c7bb3f7b22d5a2b0d5?f=json"]),
 "IN": dict(org="Indiana DNR", zeroLevel="'shoreline of each lake as elevation 0 ... Contour values are feet below the surface' and 'contour values of some lakes were adjusted to coincide with the lake's legal gauge level' (item description)", valueType="depth below the surface; some lakes adjusted to the legal level (which lakes: not stated)", survey="not stated (item updated 2019)", waterLevelAtSurvey="not stated", datum="not stated", licence="ATTRIBUTION_REQUIRED", urls=["https://www.arcgis.com/sharing/rest/content/items/bea7752105a840afbbee1256f9b7a19b?f=json"]),
 "IL": dict(org="IDNR Office of Water Resources", zeroLevel="contour attribute CONTOUR is depth for most lakes but elevation-like for some; survey polygon has norm_pool, surv_date, ver_datum (code, undefined)", valueType="not stated", survey="Lake Springfield surv_date 2020-06-27", waterLevelAtSurvey="not stated", datum="code '2' (undefined)", licence="UNCLEAR", urls=["https://maps.dnr.illinois.gov/geoservices/rest/services/WaterResources/LakeDepthAndCapacity/MapServer"]),
 "MT": dict(org="Montana FWP", zeroLevel="'CONTOUR: Contour depth in feet'; shoreline type S, depth contours C", valueType="depth (reference level not stated)", survey="not stated (publication 2022; sources include BOR, DEQ contractors, FWP)", waterLevelAtSurvey="not stated", datum="not stated", licence="UNCLEAR", urls=["https://fwp-gis.mt.gov/arcgis/rest/directories/arcgisoutput/webResources/metadata/refrnc/lakesBathymetry.htm"]),
 "MA": dict(org="MassWildlife (MassGIS)", zeroLevel="contour DEPTH ft, SHORE flag; GPS/depth sounder; full MassGIS metadata page returned HTTP 403", valueType="depth (reference level not retrieved)", survey="not retrieved", waterLevelAtSurvey="not retrieved", datum="not retrieved", licence="ATTRIBUTION_REQUIRED", urls=["https://www.arcgis.com/sharing/rest/content/items/dfc49081b0a641d489dd38cff0f5ef60?f=json"]),
 "CT": dict(org="CT DEEP", zeroLevel="DEPTH_FT contours, mixed methods (manual soundings, depth finder + GPS, digitised maps); DATADATE per feature", valueType="depth (reference level not stated)", survey="DATADATE attribute (year)", waterLevelAtSurvey="not stated", datum="not stated", licence="PUBLIC_REUSABLE (CC0)", urls=["https://www.arcgis.com/sharing/rest/content/items/bdb59e03b6b14b0f9c7a0f65114dc2b0?f=json"]),
 "NH": dict(org="NHDES / NH Fish and Game", zeroLevel="'bathymetric depth contours in feet'; Garmin sounder points -> TIN -> raster -> contours; 'rough estimate'", valueType="depth (reference level not stated)", survey="dataset time period 2000-01-01 to 2019-10-11", waterLevelAtSurvey="not stated", datum="not stated", licence="ATTRIBUTION_REQUIRED", urls=["https://ftp.granit.sr.unh.edu/GRANIT_Data/Vector_Data/Inland_Water_Resources/d-bathymetry/bathymetry_lakes_lines/bathymetry_lakes_lines.html"]),
 "FL": dict(org="FWC-FWRI (data by ReMetrix, processed by BioSonics)", zeroLevel="one-foot contours (DEPTHF negative)", valueType="depth (reference level not stated in the item text retrieved)", survey="data created 2005-2011 (item description)", waterLevelAtSurvey="not stated", datum="not stated", licence="INTERNAL_ONLY", urls=["https://www.arcgis.com/sharing/rest/content/items/68fbc06232164ce6b6b0d046e906b885?f=json"]),
 "MI": dict(org="MI DNR / IFR", zeroLevel="contours where MinDepth == MaxDepth; band rings otherwise", valueType="depth (reference level not stated in the item text)", survey="not stated", waterLevelAtSurvey="not stated", datum="not stated", licence="PUBLIC_REUSABLE", urls=["https://www.arcgis.com/sharing/rest/content/items/2eceeac00aa74abe858f1deb268b0efb?f=json"]),
 "NJ": dict(org="NJDEP BFBM", zeroLevel="VAL2NUM metres; DATESAMP per feature", valueType="depth (reference level not stated)", survey="DATESAMP attribute (e.g. 2021)", waterLevelAtSurvey="not stated", datum="not stated", licence="RESTRICTED (NOT FOR COMMERCIAL USE)", urls=["https://www.arcgis.com/sharing/rest/content/items/f42bc7d994c142fd8fae7af61a021a33?f=json"]),
 "WA": dict(org="WA Ecology (digitised from USGS Water-Supply Bulletin 43; Sammamish from King County 2013)", zeroLevel="'bathymetric elevation bands (derived from bathymetric contours)'; Depth attribute", valueType="depth (reference level not stated)", survey="USGS/Ecology reconnaissance 1970s; Sammamish 2008 publication", waterLevelAtSurvey="not stated", datum="not stated", licence="UNCLEAR", urls=["https://gis.ecology.wa.gov/serverext/rest/services/Authoritative/ECY/MapServer/3/iteminfo?f=pjson"]),
 "PA": dict(org="Harveys Lake local layer (PA)", zeroLevel="Depth_Ft", valueType="depth (reference level not stated)", survey="not stated", waterLevelAtSurvey="not stated", datum="not stated", licence="UNCLEAR (not fetched)", urls=[]),
}
SEM["MN"]["note"] = "also serves the Gull/Leech/Winnibigoshish Corps lakes"
SRC_KEY = {"CT": "CT", "FL": "FL", "IL": "IL", "IN": "IN", "KS": "KS", "MA": "MA", "MI": "MI", "MN": "MN", "MT": "MT", "ND": "ND", "NE": "NE", "NH": "NH", "NJ": "NJ", "OH": "OH", "OK": "OK", "PA": "PA", "WA": "WA", "WV": "WV"}
(DD / "contour2_source_semantics.json").write_text(json.dumps(SEM, indent=1, sort_keys=True))

# ---- per-lake proposal -----------------------------------------------------------------------------------------------------------
def missing(f, why):
    m = []
    ps = f.get("pSrc")
    if not ps: m.append("water-surface elevation (and its datum) at which the contour depths were measured, i.e. the reference pool or the water level on the survey date")
    if ps and ps["kind"] == "documented_pool_contradictory": m.append("agency confirmation of which water level (normal pool vs level at survey) the depth surface is referenced to, per lake")
    if ps and ps.get("internalRange") and ps["internalRange"] > 0.5: m.append("why the contour-implied pool varies within the lake")
    if f.get("dirDatum") not in ("NGVD29", "NAVD88"): m.append("vertical datum of the directory pool and of the survey pool (directory datum is %s)" % f.get("dirDatum"))
    if ps and f.get("dirPoolFt") is not None and abs(ps["poolFt"] - f["dirPoolFt"]) > 0.25: m.append("which pool is right: source %.2f ft vs directory %.2f ft" % (ps["poolFt"], f["dirPoolFt"]))
    return m

out = {"schema": "depth-twdb-reference-pools-v1", "family": "contour (non-TWDB)", "status": "PROPOSAL (research output; not read by production)", "preregSha256": SHA,
       "generatedFrom": ["docs/brains/depth/data/contour2_lake_facts.json", "docs/brains/depth/data/contour2_validation_summary.json", "docs/brains/depth/data/contour2_source_semantics.json"], "lakes": {}}
for lid, f in sorted(F.items()):
    r = R[lid]; st = r["referenceStatus"]; ps = f.get("pSrc"); sem = SEM[SRC_KEY[f["src"]]]
    ev = [{"url": u, "says": "%s: %s | water level at survey: %s | datum: %s" % (sem["org"], sem["zeroLevel"], sem["waterLevelAtSurvey"], sem["datum"])} for u in sem["urls"][:1]]
    if ps:
        ev.append({"url": ps["url"], "says": "%s -> pool %.2f ft (%s)%s" % (ps["origin"], ps["poolFt"], ps["kind"], "" if ps.get("internalRange") is None else "; implied-pool range within lake %.2f ft" % ps["internalRange"])})
    ev.append({"url": "docs/brains/depth/DEPTH_LICENSING_MATRIX.md", "says": "licence class for source %s: %s (customerDerivedMetricsAllowed=%s)" % (f["src"], ",".join(f["licenceClass"]), f["customerDerivedMetricsAllowed"])})
    if "curve" in f:
        c = f["curve"]; ev.append({"url": "https://cwms-data.usace.army.mil/cwms-data/ratings/%s?office=%s" % (c["ratingId"], c["office"]), "says": "CWMS %s, native datum %s, effective %s, elevations %.1f-%.1f ft%s" % (c["ratingId"], c["datumNative"], c["effectiveDate"][:10], c["elevMin"], c["elevMax"], "" if c["stageZeroFt"] is None else " (stage + %.1f ft gauge zero from the CWMS location elevation, assumption)" % c["stageZeroFt"])})
    val = None; pl = S["perLake"].get(lid)
    if pl:
        p = pl["production"]; dg = S["diagnostics"].get(lid, {})
        val = {"levels": P["levels"]["drawdownBelowPRefFt"], "levelsMeaningFtBelowReferencePool": True, "includedLevels": p["nIncluded"], "publishedLevels": p["nPublished"], "publishRate": None if p["publishRate"] is None else round(p["publishRate"], 3),
               "maeDryShare": None if "mae" not in p else round(p["mae"], 4), "boundsCoverage": p.get("coverage"), "medianBoundsWidth": None if "widthMedian" not in p else round(p["widthMedian"], 3),
               "predictor": "C1 manifest contour shares vs CWMS stage-area curve (independent)" + ("" if pl["group"] == "GRADED" else " -- ASSUMED pool, informational only"),
               "passed": pl["passed"], "preregSha256": SHA, "impliedPoolMinusPRefFt_informational": dg.get("D2_impliedPoolMinusPRefFt")}
    cav = list(r["statusReasons"]) if st == "UNVERIFIED" else []
    if st == "VERIFIED": cav.append("Verified on the documented pool figure equalling the directory pool (R1-R4); the water level on the survey DATE is still not stated by the source.")
    if lid in ("Caesar Creek Lake|OH",): cav.append("No CWMS Elev;Area curve (only Elev;Stor) so no validation was run; validation.passed is null.")
    if f["customerDerivedMetricsAllowed"] != "true": cav.append("Licence blocks customer-facing derived numbers for this source (internal use only).")
    ent = dict(referenceStatus=st, referencePoolFt=(ps["poolFt"] if (ps and (ps.get("internalRange") is None or ps["internalRange"] <= 0.5)) else None) if (st == "VERIFIED" or ps) else None,
               referencePoolDatum=(f["dirDatum"] if st == "VERIFIED" else None), surveyYear=(ps or {}).get("surveyYear"), contourIntervalFt=f["intervalFt"],
               directoryPoolFt=f.get("dirPoolFt"), directoryPoolDatum=f.get("dirDatum"), evidence=ev, validation=val, caveats=cav)
    if st == "UNVERIFIED": ent["missingEvidence"] = missing(f, r["statusReasons"])
    out["lakes"][lid] = ent
p = REPO / "jobs/depth-brain/depth_brain/data/proposals/contour_reference_pools.json"
p.write_text(json.dumps(out, indent=1) + "\n")
v = [k for k, e in out["lakes"].items() if e["referenceStatus"] == "VERIFIED"]
print("wrote", p, len(out["lakes"]), "lakes; VERIFIED", len(v), v, "UNVERIFIED", len(out["lakes"]) - len(v))
