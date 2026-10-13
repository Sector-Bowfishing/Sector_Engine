#!/usr/bin/env python3
"""Assemble the machine-readable proposal jobs/depth-brain/depth_brain/data/proposals/twdb_reference_pools.json from the verified report facts
(strings below are what the TWDB reports/pages say, with URLs) and the preregistered validation summary. PROPOSAL ONLY: nothing reads this file in production.
Run with the lake-brain venv python, -I."""
import json
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
S = json.loads((REPO / "docs/brains/depth/data/twdb_validation_summary.json").read_text())
F = json.loads((REPO / "docs/brains/depth/data/twdb_report_facts.json").read_text())
IDX = "https://www.twdb.texas.gov/surfacewater/surveys/completed/index.asp"
B = "https://www.twdb.texas.gov/surfacewater/surveys/completed/files/"
LIC = {"url": IDX, "says": "Authorization for the use or reproduction of any original material is freely granted; TWDB would appreciate acknowledgement; TWDB assumes no liability for misuse 'in a manner not consistent with the survey design', e.g. maps are 'not intended for use as recreational boating maps, fishing maps, or for reservoir boundary determinations'."}
LAKES = {
 "Cedar Creek Reservoir|TX": dict(referenceStatus="VERIFIED", referencePoolFt=322.0, referencePoolDatum="NGVD29", surveyYear=2017, contourIntervalFt=1.0, key="CedarCreek_2017-10", pdf="CedarCreek/2017-10/CedarCreek2017_FinalReport2.pdf",
  says=["Conservation pool elevation is 322.0 ft above mean sea level (NGVD29); soundings Nov 9, 2016 (water surface 320.29 ft) and Apr 3-Oct 26, 2017 (320.33-322.28 ft NGVD29); 33,099 acres at 322.0 ft; elevation-area table at 0.1 ft steps from 257.6 to 322.0 ft; boundary is the 322.0 ft contour extracted from LiDAR (NAVD88 converted to NGVD29).", "TWDB shapefile CedarCreek17_1ftcont: Contour values 258-322 in 1 ft steps are elevations (checked on the downloaded file)."],
  caveats=["Soundings were taken at water surfaces up to 1.7 ft below conservation pool; shallow margins are interpolated.", "Shares were derived from the same table used as truth (S1), so S1 results check arithmetic; S2 (contour raster) is the independent test."]),
 "Lake Conroe|TX": dict(referenceStatus="VERIFIED", referencePoolFt=201.0, referencePoolDatum="NGVD29", surveyYear=2020, contourIntervalFt=1.0, key="conroe_2020-10", pdf="conroe/2020-10/Conroe2020_FinalReport.pdf",
  says=["Conservation pool elevation is 201.0 ft above mean sea level (NGVD29, gage USGS 08067600); soundings Mar 2-Oct 30, 2020 (water surface 199.18-200.31 ft) and Apr 12, 2021 (200.47 ft); 19,894 acres at 201.0 ft; bathymetric elevation-area table at 0.1 ft steps from 139.6 to 201.0 ft (a separate topographic table runs to 212.0 ft).", "Model boundary digitised from 2015 imagery at 201.18 ft water surface and assigned 201.0 ft. TWDB shapefile Conroe20_1ftcont: Contour values 141-201 in 1 ft steps are elevations."],
  caveats=["Areas between 199.0 and 201.0 ft were linearly interpolated by TWDB (flat triangles), so truth near the top of the table is a modelled quantity."]),
 "Lake Fork Reservoir|TX": dict(referenceStatus="VERIFIED", referencePoolFt=403.0, referencePoolDatum="NGVD29", surveyYear=2009, contourIntervalFt=2.0, key="Fork_2009-10", pdf="Fork/2009-10/Fork2009_FinalReport.pdf",
  says=["Conservation pool elevation is 403.0 ft above mean sea level (NGVD29); soundings Jul 28-Nov 5, 2009 (water surface 402.45-404.41 ft) plus May 25, 2010 (403.1 ft); 26,889 acres at 403.0 ft; elevation-area table at 0.1 ft steps from 327.9 to 403.0 ft.", "Boundary digitised from Jan 11, 2009 imagery at 402.26 ft water surface and assigned 403.0 ft. TWDB shapefile Fork09_2ftcont: CONTOUR values 328-402 in 2 ft steps are elevations; the published map is 5 ft."],
  caveats=["Contour product is 2 ft; survey is 17 years old (sedimentation since 2009 not modelled).", "Pool boundary was digitised 0.74 ft below the stated pool, so shallow-margin area at 403.0 is approximate."]),
 "Lake Livingston|TX": dict(referenceStatus="VERIFIED", referencePoolFt=131.1, referencePoolDatum="NGVD29", surveyYear=2019, contourIntervalFt=1.0, key="Livingston_2019-11", pdf="Livingston/2019-11/Livingston2019_FinalReport.pdf",
  says=["Conservation pool elevation is 131.0 ft above mean sea level (NGVD29); soundings Sep 17, 2018-Nov 21, 2019 (water surface 130.97-132.93 ft NGVD29); 77,729 acres at 131.0 ft; bathymetric elevation-area table at 0.1 ft steps from 57.4 to 131.1 ft; model boundary is the 131.17 ft contour.", "The Riverside gauge is NAVD88, 0.43 ft below NGVD29, and TWDB converted it to NGVD29. TWDB shapefile Liv19_1ftcont is a 1 ft contour set."],
  caveats=["The reference shares are measured from 131.1 ft (the table elevation whose area, 78,170 acres, matches the survey pool polygon), 0.1 ft above the conservation pool 131.0 ft and the Sector directory pool 131: within the 0.25 ft pool sigma, recorded here.", "TWDB states the survey underestimates sediment volume and that significant sedimentation has occurred above about the 120.5 ft contour."]),
 "Lake Tawakoni|TX": dict(referenceStatus="VERIFIED", referencePoolFt=437.5, referencePoolDatum="NGVD29", surveyYear=2009, contourIntervalFt=1.0, key="tawakoni_2009-08", pdf="tawakoni/2009-08/Tawakoni2009_FinalReport.pdf",
  says=["Conservation pool elevation is 437.5 ft above mean sea level (NGVD29); soundings Jun 10-Aug 18, 2009 (water surface 435.52-437.25 ft) plus Oct 15 and Nov 4, 2009 (439.71 and 438.84 ft); 37,325 acres at 437.5 ft; elevation-area table at 0.1 ft steps from 374.4 to 437.5 ft.", "Boundary digitised from 2008 imagery at 436.77 ft water surface and assigned 437.5 ft. TWDB shapefile Tawakoni09_1ftcont: CONTOUR values 375-437 in 1 ft steps are elevations."],
  caveats=["Pool boundary digitised about 0.73 ft below stated pool; survey is 17 years old."]),
 "Lake Texoma|TX": dict(referenceStatus="UNVERIFIED", referencePoolFt=620.0, referencePoolDatum=None, surveyYear=2002, contourIntervalFt=5.0, key="Texoma_2002-07", pdf="Texoma/2002-07/Texoma2002_FinalReport.pdf",
  says=["Conservation pool elevation is 617.0 ft above msl (74,686 acres); the 2002 survey (Jun 3-Jul 9, 2002, lake 617.53-619.71 ft) used the 620.0 ft contour from USGS 7.5 minute quadrangle maps as the lake boundary (84,911 acres at 620.0 ft including 4,858 acres of Cumberland Pool); elevation-area table 520.6-620.0 ft.", "Datum is stated only as 'mean sea level' at the USACE Denison Dam gauge (no NGVD29 label). TWDB shapefile Tex_cont_5: 5 ft contours."],
  caveats=["Shares are measured from 620.0 ft, 3.0 ft above the conservation pool 617.0 ft and the Sector directory pool 617; effective zones would be mis-shifted by 3 ft unless the shift were taken from 620.0.", "Datum label absent in the report; survey is 24 years old; 5 ft contour product supports only the 10 ft edge.", "Excluded from pass/fail; informational numbers only."])}
out = {"schema": "depth-twdb-reference-pools-v1", "status": "PROPOSAL (research output; not read by production)", "preregSha256": S["prereg"]["sha256"], "generatedFrom": ["docs/brains/depth/data/twdb_report_facts.json", "docs/brains/depth/data/twdb_validation_summary.json"], "lakes": {}}
for lid, L in LAKES.items():
    f = F[lid]; pl = S["perLake"][lid]
    ev = [{"url": B + L["pdf"], "says": s} for s in L["says"]] + [{"url": B + L["pdf"].rsplit("/", 1)[0] + "/", "says": f"Local area-capacity table matches the report: table area at conservation pool {f['tableAcresAtConservationPool']} acres vs report {f['reportAcresAtConservationPool']} acres (ratio {f['areaRatioTableOverReportAtConservationPool']})."}, LIC]
    val = None
    if L["referenceStatus"] == "VERIFIED":
        s1 = pl["S1"]["production"]; s2 = pl.get("S2", {}).get("production")
        val = {"levels": [1.5, 3.0, 4.5, 6.0, 8.0], "levelsMeaningFtBelowReferencePool": True, "maeDryShare": round(s1["mae"], 4), "boundsCoverage": s1["coverage"], "medianBoundsWidth": round(s1["widthMedian"], 3),
               "predictor": "S1 table-derived shares (graded)", "independentContour": ({"predictor": "S2", "maeDryShare": round(s2["mae"], 4), "boundsCoverage": s2["coverage"], "medianBoundsWidth": round(s2["widthMedian"], 3)} if s2 else None),
               "passed": pl["passed"], "preregSha256": S["prereg"]["sha256"]}
    out["lakes"][lid] = dict(referenceStatus=L["referenceStatus"], referencePoolFt=L["referencePoolFt"], referencePoolDatum=L["referencePoolDatum"], surveyYear=L["surveyYear"], contourIntervalFt=L["contourIntervalFt"],
                             conservationPoolFtPerTWDB=f["statedConservationPoolFt"], evidence=ev, validation=val, caveats=L["caveats"])
p = REPO / "jobs/depth-brain/depth_brain/data/proposals/twdb_reference_pools.json"
p.write_text(json.dumps(out, indent=1) + "\n"); print("wrote", p)
