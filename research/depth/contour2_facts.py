#!/usr/bin/env python3
"""Depth Brain / contour reference-pool + stage-area validation, step 1: collect FACTS (no comparison computed here).
Reads: candidates.json (reference shares, directory pool/datum), the raw contour sources (NE/ND/OK carry Elevation next to Depth),
the CWMS Elev;Area / Stage;Area rating files fetched on 2026-10-13 (outside git), the Ohio DNR map PDF statements and the
Kansas Biological Survey PhysicalLakeData values (transcribed below with their URLs).
Writes small outputs under docs/brains/depth/data/: contour2_lake_facts.json, contour2_curves.csv.
Run with the contour2 venv python, -I:  .../depth-brain/contour2/venv/bin/python -I research/depth/contour2_facts.py"""
import csv, datetime as dt, json, re
from pathlib import Path
import geopandas as gpd, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

REPO = Path(__file__).resolve().parents[2]
CAND = REPO / "jobs/depth-brain/depth_brain/data/candidates.json"
OUTD = REPO / "docs/brains/depth/data"
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain")
SRC, RAT = RAW / "sources", RAW / "contour2/cwms/ratings"

# --- documented survey reference pools transcribed from the fetched statements --------------------------------------------------
OH_BASE = "https://dam.assets.ohio.gov/image/upload/ohiodnr.gov/documents/wildlife/maps/"
OH = {  # lake: (pool ft as printed, decimals printed, survey year printed, pdf, datum words on the map)
    "Alum Creek Lake|OH": (888, 0, 2001, "alumcreeklake2.pdf", None), "Caesar Creek Lake|OH": (849, 0, 1997, "caesarcreeklake2.pdf", None),
    "Grand Lake St. Marys|OH": (871, 0, 2004, "grandlakestmarys2.pdf", None), "Hoover Reservoir|OH": (894, 0, 2001, "hooverreservoir2.pdf", None),
    "Lake Milton|OH": (948, 0, 1998, "lakemilton2.pdf", None), "Mosquito Creek Lake|OH": (901, 0, 2004, "mosquitocreeklake2.pdf", "above mean sea level"),
    "Pymatuning Reservoir|PA": (1008, 0, 2008, "pymatuninglake2.pdf", None), "Salt Fork Lake|OH": (800, 0, 1998, "saltforklake2.pdf", None),
    "Tappan Lake|OH": (899.3, 1, 1998, "tappanlake2.pdf", "above mean sea level")}
KS_URL = "https://services.kars.geoplatform.ku.edu/arcgis/rest/services/WaterResources/PhysicalLakeData/MapServer/0/query"
KS = {  # KARS PhysicalLakeData Elev_ft (water surface elevation the areas/volumes are computed at) and Survey_yea
    "Cheney Reservoir|KS": (1420.7, 2010), "Clinton Lake|KS": (875.5, 2009), "El Dorado Lake|KS": (1339.0, 2010), "Melvern Lake|KS": (1036.0, 2009),
    "Milford Lake|KS": (1144.4, 2009), "Pomona Lake|KS": (974.0, 2009), "Wilson Lake|KS": (1516.0, 2008)}
# dataset-internal: Elevation + Depth is constant per lake (NE) / ELEVATION - CONTOUR (ND) / elevation + |depth| (OK, with vert_datum + year)
# --- CWMS curves ----------------------------------------------------------------------------------------------------------------
CURVES = {  # lake -> (office, rating id file stem, stage zero ft or None)
    "Alum Creek Lake|OH": ("LRH", "AlumCr.Elev;Area.Standard.Production", None), "Tappan Lake|OH": ("LRH", "Tappan.Elev;Area.Standard.Production", None),
    "Senecaville Lake|OH": ("LRH", "Senecaville.Elev;Area.Standard.Production", None), "Mosquito Creek Lake|OH": ("LRP", "Mosquito.Elev;Area.Standard.Production", None),
    "Lake Milton|OH": ("LRP", "Milton.Elev;Area.Standard.Production", None), "Stonewall Jackson Lake|WV": ("LRP", "StonewallJackson.Elev;Area.Standard.Production", None),
    "Tygart Lake|WV": ("LRP", "Tygart.Elev;Area.Standard.Production", None),
    "Gull Lake|MN": ("MVP", "MissHW_Gull.Stage;Area.Standard.Production", 1100.0), "Leech Lake|MN": ("MVP", "MissHW_Leech.Stage;Area.Standard.Production", 1200.0),
    "Lake Winnibigoshish|MN": ("MVP", "MissHW_Winni.Stage;Area.Standard.Production", 1200.0),
    "Cheney Reservoir|KS": ("SWT", "CHEN.Elev;Area.Linear.Production", None), "El Dorado Lake|KS": ("SWT", "ELDR.Elev;Area.Linear.Production", None),
    "Fort Gibson Lake|OK": ("SWT", "FGIB.Elev;Area.Linear.Production", None), "Sardis Lake|OK": ("SWT", "SARD.Elev;Area.Linear.Production", None),
    "Clinton Lake|KS": ("NWDM", "CLIN-Clinton_Lake-Wakarusa.Elev;Area.Area_Curves.Production", None), "Melvern Lake|KS": ("NWDM", "MELN-Melvern_Lake-Marais_Des_Cygnes.Elev;Area.Area_Curves.Production", None),
    "Milford Lake|KS": ("NWDM", "MILD-Milford_Lake-Republican.Elev;Area.Area_Curves.Production", None), "Pomona Lake|KS": ("NWDM", "POMA-Pomona_Lake-110-Quenemo.Elev;Area.Area_Curves.Production", None),
    "Wilson Lake|KS": ("NWDM", "WILN-Wilson_Lake-Saline.Elev;Area.Area_Curves.Production", None), "Harlan County Lake|NE": ("NWDM", "HACO-Harlan_Co_Lake-Republican.Elev;Area.Area_Curves.Production", None),
    "Swanson Reservoir|NE": ("NWDM", "TREN-Swanson_Res-Republican.Elev;Area.Area_Curves.Production", None), "Branched Oak Lake|NE": ("NWDM", "SC18.Elev;Area.Linear.Step", None),
    "Tiber Reservoir (Lake Elwell)|MT": ("NWDM", "TIBR.Elev;Area.Linear.Step", None), "Bowman-Haley Reservoir|ND": ("NWDM", "BOHA.Elev;Area.Linear.Step", None)}


def load_curve(office, rid, zero, survey_year):
    d = json.load(open(RAT / f"{office}__{rid.replace('/', '_')}.json"))
    sr = d["simple-rating"]; sr = sr if isinstance(sr, list) else [sr]
    def ey(x): return int(x["effective-date"][:4])
    if survey_year:
        pick = min(sr, key=lambda x: (abs(ey(x) - survey_year), -ey(x)))
    else:
        pick = max(sr, key=ey)
    pts = pick["rating-points"]["point"]
    e = np.array([float(p["ind"]) for p in pts]); a = np.array([float(p["dep"]) for p in pts])
    o = np.argsort(e, kind="stable"); e, a = e[o], a[o]
    vd = (pick.get("vertical-datum-info") or {}).get("native-datum")
    if zero is not None:
        e = e + zero
    return dict(elev=e.tolist(), area=a.tolist(), effectiveDate=pick["effective-date"], versions=[x["effective-date"][:10] for x in sr], datumNative=vd,
                units=pick.get("units-id"), ratingId=d["rating-spec"]["rating-spec-id"], office=office, stageZeroFt=zero)


def main():
    cands = json.load(open(CAND))["candidates"]
    ne = gpd.read_file(SRC / "ne_ngpc/ne_lake_contours.geojson"); ne["imp"] = ne.Elevation + ne.Depth
    nes = gpd.read_file(SRC / "ne_ngpc/ne_lake_shapes.geojson")
    nd = gpd.read_file(SRC / "nd_gnf/nd_gnf_lake_contours.geojson"); nd["imp"] = nd.ELEVATION - nd.CONTOUR
    ok = gpd.read_file(SRC / "ok_owrb/ok_owrb_contours.geojson"); ok["imp"] = ok.elevation - ok.depth   # depth stored negative
    il = gpd.read_file(SRC / "il_idnr/il_lakes_surveyed.geojson")
    NE_NAME = {"Box Butte Reservoir|NE": "Box Butte Reservoir", "Branched Oak Lake|NE": "Branched Oak Lake", "Calamus Reservoir|NE": "Calamus Reservoir", "Harlan County Lake|NE": "Harlan County Lake",
               "Johnson Lake|NE": "Johnson Lake", "Lake McConaughy|NE": "Lake McConaughy", "Lake Ogallala|NE": "Lake Ogallala", "Merritt Reservoir|NE": "Merritt Reservoir",
               "Sherman Reservoir|NE": "Sherman Reservoir", "Swanson Reservoir|NE": "Swanson Reservoir"}
    ND_NAME = {"Bowman-Haley Reservoir|ND": "085", "Nelson Lake|ND": "258", "Patterson Lake|ND": "330"}
    OK_NAME = {"Fort Gibson Lake|OK": "Ft Gibson", "Grand Lake o' the Cherokees|OK": "Grand", "Lake Murray (OK)|OK": "Murray", "Sardis Lake|OK": "Sardis"}
    lakes, curve_rows = {}, []
    for v in cands:
        rz = v.get("referenceZones")
        if not rz or rz["source"] == "TWDB":
            continue
        lid = v["lakeId"]; cum = {float(k): x for k, x in rz["cumulative"].items()}
        f = dict(lakeId=lid, src=rz["source"], tier=v["evidence"]["tier"], intervalFt=rz["intervalFt"], coverage=rz.get("coverage"),
                 shares={f"lt{int(k)}": x for k, x in cum.items()}, dirPoolFt=v["reference"].get("poolFt"), dirDatum=v["reference"].get("datum"),
                 dirBasis=v["reference"].get("basis"), licenceClass=v["licence"]["classes"], customerDerivedMetricsAllowed=v["licence"]["customerDerivedMetricsAllowed"],
                 operator=v.get("operator"))
        ps = None
        if lid in OH:
            p, dec, yr, pdf, words = OH[lid]
            ps = dict(poolFt=float(p), decimals=dec, surveyYear=yr, datumStated=words, origin="ODNR Division of Wildlife lake map PDF: 'Depths based on normal summer pool elevation of X ft'; 'Reservoir last surveyed: YYYY'",
                      url=OH_BASE + pdf, kind="documented_pool", internalRange=None)
        elif lid in KS:
            p, yr = KS[lid]
            ps = dict(poolFt=p, decimals=1, surveyYear=yr, datumStated=None, origin="KARS PhysicalLakeData Elev_ft (water surface elevation that areas/volumes are computed at; service text: federal reservoirs = normal operating (conservation/multi-purpose) pool by USACE/USBR) -- but the BathymetryContour layer text says 'operating water level at the time of the survey' (contradictory)",
                      url=KS_URL, kind="documented_pool_contradictory", internalRange=None)
        elif lid in NE_NAME:
            g = ne[ne.Name == NE_NAME[lid]]; s = nes[nes.Name == NE_NAME[lid]]
            cons = float(s.Conservati.iloc[0]) if len(s) and pd.notna(s.Conservati.iloc[0]) else None
            sy = None
            if len(s) and pd.notna(s.SurveyDate.iloc[0]):
                sy = int(pd.to_datetime(s.SurveyDate.iloc[0], unit="ms").year)
            ps = dict(poolFt=float(g.imp.median()), decimals=1, surveyYear=sy, datumStated=None, origin="NGPC contour attribute Elevation + Depth (constant per lake: median); shape attribute Conservati=%s" % cons,
                      url="https://services.arcgis.com (NGPC Lake Contours item 0f0e603f248d4a4bb79f350db3780d72)", kind="dataset_internal_elevation", internalRange=float(g.imp.max() - g.imp.min()), conservationPoolAttr=cons)
        elif lid in ND_NAME:
            g = nd[nd.LAKE == ND_NAME[lid]]
            ps = dict(poolFt=float(g.imp.median()), decimals=1, surveyYear=None, datumStated=None, origin="ND G&F contour attribute ELEVATION - CONTOUR (constant per lake)", url="https://ndgishub.nd.gov/arcgis/rest/services/Applications/GNF_LakeContoursCached/MapServer",
                      kind="dataset_internal_elevation", internalRange=float(g.imp.max() - g.imp.min()))
        elif lid in OK_NAME:
            g = ok[ok.lake == OK_NAME[lid]]
            ps = dict(poolFt=float(g.imp.median()), decimals=1, surveyYear=int(g.year.iloc[0]) if g.year.notna().any() else None, datumStated=str(g.vert_datum.iloc[0]),
                      origin="OWRB contour attributes elevation + |depth| (constant per lake), vert_datum, year", url="https://owrb.csa.ou.edu/server/rest/services/Surface_Water/LOK_Lakes/MapServer",
                      kind="dataset_internal_elevation", internalRange=float(g.imp.max() - g.imp.min()))
        elif lid == "Lake Springfield|IL":
            r = il[il.name.str.strip() == "Lake Springfield"].iloc[0]
            ps = dict(poolFt=float(r.norm_pool), decimals=1, surveyYear=int(pd.to_datetime(r.surv_date, unit="ms").year), datumStated="code %s (undefined)" % r.ver_datum,
                      origin="IDNR il_lakes_surveyed norm_pool, surv_date, ver_datum; contour semantic (depth vs elevation) is not stated: research resolved it from max_dpth",
                      url="https://maps.dnr.illinois.gov/geoservices/rest/services/WaterResources/LakeDepthAndCapacity/MapServer", kind="attribute_pool_semantics_unstated", internalRange=None)
        f["pSrc"] = ps
        if lid in CURVES:
            o, rid, zero = CURVES[lid]
            c = load_curve(o, rid, zero, ps["surveyYear"] if ps else None)
            f["curve"] = dict(office=o, ratingId=c["ratingId"], datumNative=c["datumNative"], effectiveDate=c["effectiveDate"], versions=c["versions"], stageZeroFt=zero,
                              elevMin=min(c["elev"]), elevMax=max(c["elev"]), nPoints=len(c["elev"]), units=c["units"])
            for e, a in zip(c["elev"], c["area"]):
                curve_rows.append(dict(lakeId=lid, ratingId=c["ratingId"], effectiveDate=c["effectiveDate"][:10], elevFt=round(e, 3), areaAc=a))
        lakes[lid] = f
    OUTD.mkdir(parents=True, exist_ok=True)
    (OUTD / "contour2_lake_facts.json").write_text(json.dumps(dict(schema="depth-contour2-lake-facts-v1", generatedAtUtc=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), lakes=lakes), indent=1, sort_keys=True))
    with open(OUTD / "contour2_curves.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["lakeId", "ratingId", "effectiveDate", "elevFt", "areaAc"]); w.writeheader(); w.writerows(curve_rows)
    print(len(lakes), "lakes;", sum(1 for x in lakes.values() if "curve" in x), "with curve;", len(curve_rows), "curve rows")


if __name__ == "__main__":
    main()
