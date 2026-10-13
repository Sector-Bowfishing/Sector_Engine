# Depth Brain Blocker Queue

A blocker stops one research path; the campaign continued elsewhere. Machine-readable blockers: `ledger/terrain.jsonl`, `ledger/contour.jsonl`.

| ID | Blocker | Path stopped | Impact on score | Workaround / status | Michael action? | Priority |
|---|---|---|---|---|---|---|
| B-depth-001 | **No public bathymetry for Southeast/TVA/Duke/Santee/Alabama Power reservoirs** (TVA has no public download; 23 states have zero contour/survey candidates) | Tier A/B for the bowfishing core (Guntersville, Wheeler, Wilson, Pickwick, Hartwell, Lanier, Santee) | coverage +1.0, authority +1.0, relative +1.0 | IENC 9 ft binary, shift-only; effective depth; Landsat drawdown pilot | YES: ask TVA, Georgia Power/Duke/Dominion, SC DNR, AL DCNR/AL Power, state fisheries biologists for hydroacoustic surveys or contours; ask Sector users for sonar exports | high |
| B-depth-002 | No bowfishing ground truth (are 0-6 ft flats the places fish are shootable?) | field validation | validation +2 | none yet | YES: 5-10 lake field session or user observation export with depth | high |
| B-depth-003 | TVA/Santee/Duke datum statements not verified against operator documents; NGVD29/NAVD88 shift median 0.64 ft, up to 5.4 ft | absolute depth, zone re-binning | effective depth +1 | shift-only uses pool delta; uncertainty sigma 1.8-3.2 ft if unreconciled | maybe (operator contact) | high |
| B-depth-004 | Shift history missing for 151 qualifying lakes; RISE (46 lakes), Duke (8), most TVA lakes had no fetcher | operating-range class | effective +0.3 | classes marked unchecked | no | medium |
| B-depth-005 | Licences: FL FWC internal only; TWDB not-for-fishing disclaimer; MI/MN/IN/MT/WV/NJ/TN no explicit licence | shipping contour-derived geometry | provenance | publish derived metrics only; keep geometry internal | YES: licence review / permissions | medium |
| B-depth-006 | 24 USGS inventory and ScienceBase name-only matches unverified; zenodo (3D-LAKES) and data.usbr.gov (RISE) unreachable from this host | extra Tier A/B | coverage +0.3 | retry from another network | no | medium |
| B-depth-007 | Wisconsin: no inland contour GIS (draft association layer only); similar gaps in 20 other states | coverage | | web-search budget was exhausted in scouting; re-scout with fresh budget | no | medium |
| B-depth-008 | Per-segment shallow flats cannot be inferred from slope (cell AUC +0.004 over distance); no scalable flats predictor | non-surveyed lakes | relative | distance-to-shore band as coarse proxy; Landsat drawdown for a few lakes | no | low (accept) |
| B-depth-009 | Sentinel-2, JRC monthly water history and tributary-flats tests not run; 3DEP sampling slowed to 1 lake/min (265 of 339 done) | satellite hypsometry | small | Landsat pilot positive on 5 lakes | no | low |
| B-depth-010 | Buchanan, Travis, Possum Kingdom pool polygons unmatched; Minnetonka polygon 55.6 vs 66.7 km2; Illinois pull incomplete (3,402 of 4,828 lines); Rainy Lake 2.6 % covered | single lakes | tiny | flagged manualReviewNeeded | no | low |
