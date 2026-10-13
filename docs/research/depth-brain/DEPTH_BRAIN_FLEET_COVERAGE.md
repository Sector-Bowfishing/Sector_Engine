# Depth Brain Fleet Coverage (621 lakes)

Matrix: `data/depth_fleet_evidence_matrix.csv` (621 rows) and `data/depth_fleet_evidence_summary.json`. Builder `research/depth-brain/fleet_matrix.py`. Fields: lakeId, lakeName, state, geometryAvailable, authoritativeDepthAvailable, contoursAvailable, globathyAvailable, terrainInferencePossible, bestDepthSource, evidenceTier, absoluteDepthConfidence, relativeDepthConfidence, manualReviewNeeded, licenseStatus (plus contourSources, ienc9ftFootprint, hypsometryTruthAvailable, poolRefAndLevelBoundForShift, levelHistory10y, scoutCandidateOnly).

Rules: contour evidence requires `verified_spatial`; GLOBathy counts only for verified/weak matches whose Dmax is modeled; scout candidates with no spatial verification stay `scoutCandidateOnly`. Nothing is guessed.

## Result

| Evidence tier | Lakes | Meaning |
|---|---|---|
| A | 77 | surveyed contours, whole lake, fine interval (<=3 ft, or 5 ft on deep lakes) |
| B | 26 | coarser interval on deep lakes, or 65-85 % coverage |
| B-partial | 35 | partial coverage, >10 ft interval, datum or polygon doubts (manual review) |
| B-binary | 28 | only the USACE IENC 9 ft contour (footprint intersects; interior unverified) |
| C | 28 | measured hypsometry (CWMS stage-area, TWDB area-capacity), lake-level only |
| D | 371 | modeled/terrain prior only (GLOBathy, 3DEP slope): never scored, never shown as depth |
| U (unknown) | 56 | no defensible evidence (8 HI, 4 MI, 4 NY, 3 DE, 3 IA, 3 RI, 3 UT, 3 WI ...) |

Other counts: 140 lakes have a verified contour match (103 of them tier A/B, 37 partial/coarse); 468 have a usable modeled GLOBathy row (Tier D prior); 290 have a 3DEP slope estimate; 265 can receive a bathymetry-independent **level shift** (bound live level plus pool reference), 153 of those with at least 10 years of history; 322 have either zones or a shift; manual review needed on 117.

By lake type (A/B): reservoir 66, regulated natural 26, natural 11. **No TVA lake has tier A/B** (9 are B-binary from the IENC 9 ft contour, 6 are D, 1 unknown); Guntersville, Wheeler, Wilson and Pickwick are all B-binary. By operator, tier A/B: USACE 32, USBR 9, other/state 53, no operator 9. Large A/B lakes are mostly Texas (Livingston, Texoma, Tawakoni, Cedar Creek), Minnesota (Mille Lacs, Leech, Winnibigoshish, Vermilion), Oklahoma (Grand), Montana (Flathead, Canyon Ferry) and Florida (Kissimmee, internal only); the Southeast bass/carp reservoirs (GA, SC, NC, AL, TN) have none.  Large A/B lakes are mostly Texas (Livingston, Texoma, Tawakoni, Cedar Creek), Minnesota (Mille Lacs, Leech, Winnibigoshish, Vermilion), Oklahoma (Grand), Montana (Flathead, Canyon Ferry) and Florida (Kissimmee, internal only); the Southeast bass/carp reservoirs (GA, SC, NC, AL, TN) have none. 