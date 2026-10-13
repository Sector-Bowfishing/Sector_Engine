# Lake Brain research, Track 1: canonical lake geometry

Thread `geometry`, 2026-10-13. Research only: no deploy, no write to any RTDB or bucket, GET-only against production and public services. Public-safe: only public data, method and aggregates. No private research file content is copied here; private files are named only as "a private research copy".

Machine-readable twin: `docs/research/lake-brain/data/geometry_summary.json`. Reproduce with `research/lake-brain/geometry_audit.py` (and the helper scripts in section 11). Ledger: `docs/research/lake-brain/ledger/geometry.jsonl` (sources `S-geometry-001..025`, blockers `B-geometry-001..012`, actions `M-geometry-01..05`). Bulk data lives only in `Sector_Research_Data/lake-brain/geometry/` (about 3.6 GB, nothing in Git). Per-lake flags for all 621 lakes: `geometry/lake_geometry_flags.csv` (data dir).

Product lens: Sector is a bowfishing product. A canonical lake boundary is what Ops (Lakes > Info) should draw instead of a center-point placeholder, and it drives shoreline, shallow-water and satellite context. This is not a GIS project: the question is "what polygon do we trust, how do we know, and how do we ship it".

## 1. Answers in one page

| Question | Answer |
|---|---|
| Do we already possess Guntersville geometry? | Yes: four copies of our own plus the public NHD service (section 2). The Engine ships it in `jobs/lake-surface/polygons.geojson.gz`: a MultiPolygon (6 parts, 419 holes, 11,694 vertices, 266.2 km2), derived from USGS NHD High Resolution waterbody `139326855` (265.487 km2, feature date 2021-05-26). A full-resolution copy (56,508 vertices) sits in a private research worktree and in the iOS FishIntel cache, and the iOS app bundles 6,504 shoreline segments built from it. |
| Why is it not in the Lake Registry (`GET /lakes`) or Ops? | `/lakes` is generated from a spreadsheet and has no geometry field; the polygon file is a build-time blob copied into three Cloud Run Job images and read only by them (section 3). It is published nowhere: not in a bucket, not in RTDB. The public clarity bucket carries only the four corner coordinates of each raster. Ops draws a placeholder because its `EngineLake` type, the Engine DTO and the bucket all lack geometry, and the Ops Info card reads `identity.polygonStatus`, which no Engine code writes. The bucket also has no CORS config, so the browser could not read an object even if one existed. |
| Is the geometry good? | The Engine polygons are NHD HR shorelines simplified to about 15-20 m: median IoU 0.99 and median area ratio 1.0007 against the NHD feature they came from (590 matched lakes). That proves the right NHD feature was picked. It does not prove the extent is right: NHD is the water surface on the imagery date. Independent checks (NID normal-pool surface area, USACE reservoir polygons, OSM, JRC water history) show 67 lakes where an adjacent unnamed NHD piece was dropped; Lake Hartwell is 136.7 km2 in the Engine vs 217 km2 once its unnamed 80.6 km2 NHD piece is added (NID 226, USACE 234, OSM 220). |
| Confidence over the 621 directory lakes | HIGH 351, MEDIUM 195, LOW 53, MISSING 22 (rules in section 6). Guntersville and Wilson are HIGH; Wheeler, Pickwick and Hartwell are MEDIUM (partial reservoir); see section 2.2. |
| Guntersville holes: islands or artifacts? | Islands. Against JRC Global Surface Water, 8.04 of the 8.50 km2 of hole area (95 %) was land (water <20 % of observations 1984-2021); 14 of 419 holes (0.02 km2) look like water; 155 are smaller than two 30 m pixels. 17 are under 100 m2 and are noise worth dropping. |
| The 22 lakes without a polygon | Not an id mismatch: all 621 directory ids are a superset of the 599 polygon ids and no polygon id is missing from the directory. 12 are Great Lakes entries (Erie x4, Huron, Michigan x3, Ontario, Superior x3) plus Lake of the Woods, Green Bay, Great Salt Lake and Iliamna, which NHD has but the Engine job evidently skipped (size); 5 Hawaii ponds and Chickahominy Lake are not mapped as lake/reservoir polygons in NHD (section 7). |
| Best authoritative source | USGS NHD HR waterbody (REST `nhd/MapServer/12`, and bulk GDB) for the shoreline, unioned across its unnamed pieces; USACE `usace_rez` polygons (418, operator pool) and the NID (point, normal-pool surface area) as pool-extent layers and validators; JRC GSW for independent water-history QA. 3DHP_all is today a repackaged copy of NHD (604 of 609 matched lakes carry workunit `NHD`). |
| Delivery to Ops | Static, versioned GeoJSON in the public bucket (display polygon about 50 m: Guntersville 133 KB raw, 40 KB gzip) plus a small summary object on `/lakes/{id}` (bbox, area, version, source, confidence, URL). Not RTDB. Needs bucket CORS (or an Engine/Hosting route) first (blocker B-geometry-002). |

## 2. Audit: what Sector already has

### 2.1 Every geometry we hold

| # | Where | What | Format / CRS | Parts, holes, vertices | Source and provenance | Date | License | Real polygon? | Fit to be canonical |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Engine repo `jobs/lake-surface/polygons.geojson.gz` (7,500,435 B, sha256 `b17e06cc...`). 11 bit-identical copies in worktrees | 599 features `{id, source, areaKm2, trimmed?}` for 599 of 621 directory ids | GeoJSON FeatureCollection, EPSG:4326, gzip | 441 Polygon, 157 MultiPolygon, 1 GeometryCollection (Devils Lake, a LineString member). 1,304,888 vertices total, median 709, max 41,102; mean segment length 116 m (median); 470 lakes with holes, 23,910 holes in all | Added in `01c3cea4` (2026-09-27, "feat(jobs): daily Water Clarity for every lake"). Source tags: `name` 558, `repaired:largest-nearby` 20, `repaired:contains-point` 10, `osm` 11. Builder script is in no repo or worktree searched (blocker B-geometry-001) | 2026-09-27 (NHD features dated 2001-2023, median about 2013) | USGS NHD is public domain; the 11 `osm` features are ODbL | Yes, real shorelines (none is a bbox or point; three degenerate ones: Lake Shafer 4 vertices, Buckeye Lake 6, Lake Waiau 6) | Good base, 599 lakes. Needs the fixes in section 8 |
| 2 | Private research worktree (NHD HR GeoJSON for Guntersville, Wheeler, Wilson, Pickwick, plus zone polygons) | Full-resolution NHD HR waterbody polygons and derived zones | GeoJSON EPSG:4326 | e.g. Guntersville 1 Polygon, 420 holes, 56,508 vertices | USGS NHD MapServer 12, GNIS-name query, corridor filter; main-body pick only | 2026-10-08 file date | USGS public domain (data); the zones are private research | Yes | Not used. Same pick as the Engine (Pickwick main body 139.494 km2; the 29 km2 adjacent piece is not in it) |
| 3 | iOS repo FishIntel cache (`waterbody.geojson`, `flowlines.geojson`) | Same NHD waterbody for Guntersville, plus 12,456 NHD flowlines | GeoJSON EPSG:4326 | 1 Polygon, 56,508 vertices | `build_lake_profile.py` queries NHD MapServer/12 `GNIS_NAME='Guntersville Lake'` and layer 6 | 2026-09-19 | USGS public domain | Yes | Source for #4; Guntersville only |
| 4 | iOS app asset catalog `Guntersville.shorelines.geojson.gz` (997 KB) and `.segments.geojson.gz` (1.94 MB) | 6,504 bank segments (200 m) and littoral polygons, not the outline | GeoJSON, gzip | 6,504 LineString / Polygon features | Derived from #3 with NHD flowlines, depth contours | 2026-09-19/20 | USGS public domain | Derived products, not a lake outline | Guntersville only; bowfishing shoreline layer, not the canonical boundary |
| 5 | Public bucket `gs://sector-lake-surface/lakes/<slug>/clarity/<date>.json` | Raster placement: 4 corner coordinates, EPSG:3857, 36 m cells | JSON | 4 points (Guntersville bbox -86.4075..-85.6094, 34.2775..35.0452) | Frame derived from #1 | daily | internal | No, a bbox only (the lake shape lives in the PNG alpha) | No |
| 6 | Ops `MapCard` | Center point and a "Lake boundary" capsule | none | none | `GET /lakes` lat/lon | n/a | n/a | No, placeholder | No |
| 7 | App RTDB `redzones` via `Scripts/AddPolygon.py`, `SectorScripts/{Prod,Dev}/AddPolygons*.py` | KML polygons written to the app database (`sector-9393c`, node `redzones`, fields zoneType, sponsorId, tournamentId, state) | RTDB list of lat/lng | n/a | Hand-drawn restricted/tournament zones | n/a | private | Zones, not lake boundaries (read, never run) | No (dead end, S-geometry-024) |

Not found: any lake boundary in the Lake Registry xlsx (`docs/data/Sector_Lakes_APIs_2.xlsx` has only lat/lon and a "Coord Conf" column), in `Sector-lakedir`, or in `Sector-Ops` (its design doc says "Engine doesn't expose geometry to the browser").

### 2.2 The five pilots, geometry by geometry

Engine polygon (E) against the references: NHD HR feature(s), the unnamed adjacent NHD piece the name pick dropped (adj), operator and independent figures. Areas in km2, equal-area projection centred on the lake.

| Lake | Engine geometry | Holes | NHD matched feature (feature date) | E area ratio / IoU vs NHD | Adjacent unnamed NHD piece | Independent checks (NID / USACE / OSM / HydroLAKES / GSW inside >=50 %) | Confidence |
|---|---|---|---|---|---|---|---|
| Guntersville, AL | MultiPolygon, 6 parts (5 slivers < 0.01 km2), 11,694 v, 266.2 | 419 (8.50) | `139326855` Guntersville Lake, 265.49 (2021-05-26) | 1.0015 / 0.988 | none | NID 267.1 / no USACE polygon / OSM relation 911315 234.1 (IoU 0.86, source tag "Yahoo") / HL 207.8 / GSW 84.4 % | HIGH |
| Wheeler, AL | MultiPolygon, 12 parts, 7,972 v, 212.5 | 277 (5.19) | `88572193` Wheeler Lake, 211.91 (2021-03-03) | 1.0014 / 0.988 | `128250303`, 19.4 (9 %) | NID entry not usable / no USACE / no Wheeler-named OSM water / HL 180.4 / GSW 87.5 % | MEDIUM (possible partial pick) |
| Wilson, AL | MultiPolygon, 2 parts, 1,885 v, 63.2 | 24 (0.09) | `87864655` Wilson Lake, 62.87 (2017-06-30) | 1.0032 / 0.990 | none | NID 63.1 / no USACE / OSM 11643538 62.3 (IoU 0.97, tagged river) / HL 58.0 / GSW 92.2 % | HIGH |
| Pickwick Lake, TN | MultiPolygon, 5 parts, 3,985 v, 139.9 | 134 (5.33) | `147604857` Pickwick Lake, 139.49 (2021-05-25) | 1.0018 / 0.990 | `87509895`, 29.1 (21 %) | NID 172.8 (E/NID 0.81; E+adj 169.0) / no USACE / OSM 1750733 162.7 / HL 155.7 / GSW 91.0 % | MEDIUM (partial reservoir) |
| Lake Hartwell, SC | Polygon, 1 part, 9,142 v, 136.7 | 89 (2.64) | `136157939` + `120024414` Hartwell Lake, 73.0 + 63.0 (2013-08-14) | 1.0025 / 0.983 | `120024413`, 80.6 (59 %) | NID 226.4 (E/NID 0.60; E+adj 217.3) / USACE `GA01702` 233.6 / OSM 142716 219.9 / HL 190.6 / GSW 85.3 % | MEDIUM (partial reservoir; fix is mechanical) |

Resolution: all NHD features are RESOLUTION 2 (high resolution, 1:24,000 source or better); the Engine copy is simplified (Guntersville 11,694 vs 56,508 vertices, IoU 0.988, a 4.8 km2 symmetric difference, equal to about a 15-20 m tolerance). Shoreline quality: NHD HR includes islands and coves at 5-10 m vertex spacing; GSW sees 84-92 % of each pilot polygon as water at least half the time, the rest being shore pixels and seasonal edge (normal for a reservoir). OSM's Guntersville polygon came from Yahoo imagery and is coarser than NHD (IoU 0.86).

## 3. How the polygons were made, and why they are not exposed

### 3.1 Provenance of `polygons.geojson.gz`
- One commit adds it, `01c3cea4` (Michael Cather, 2026-09-27, Claude Opus 5.5 co-author) with the job that uses it. The commit message gives the method: "Outlines are the NHD lake polygons trimmed to the piece at the lake's point and pieces within 1 km of it: same-named lakes elsewhere had been merged in (Long Pond, MA was 10 pieces over 6,800 km2)". 20 features carry `trimmed: true`.
- So `source: name` means: the NHD HR waterbody layer (`hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/12`) queried by GNIS name, the same `where GNIS_NAME='...'` call that `iOS/Sector-mapbox/scripts/fishintel/build_lake_profile.py` uses for Guntersville. Evidence from the data: `areaKm2` equals the NHD `AREASQKM` to three decimals (Guntersville 265.487, Wilson 62.867, Pickwick 139.494; Wheeler 211.944 = 211.906 + a 0.038 km2 piece), and 555 of 558 `name` polygons overlap an NHD feature with IoU >= 0.93 (median 0.99). It is NHD, not Nominatim.
- `repaired:largest-nearby` (20) and `repaired:contains-point` (10) are fallbacks for lakes where the name lookup failed (the lake's GNIS name differs from the directory name): 28 of those 30 are still NHD geometry (IoU >= 0.93). `osm` (11) is a fallback with a different geometry: only 3 of 11 match an NHD feature, median IoU 0.86 (inferred OSM; not provable because the builder is lost).
- No builder script exists in the Engine repo, its 11 worktrees, `Sector-mapbox`, `Scripts/` or `SectorScripts/` (searched by content and file name; blocker B-geometry-001). The set is therefore not reproducible from the repo; `geometry_audit.py` can regenerate the evidence, not the file.
- Consumers: `jobs/lake-surface/daily.py` (clarity frame per lake), `jobs/lake-surface-dispatch/dispatch.py` (`load_polygons`, bbox for pass search), `jobs/water-clarity-brain/run.py` (publishes `geometryReady`/`satelliteSupported`/`sentinel2Supported` = "lake has a polygon"). `deploy-job.sh` copies the file into each image. Nothing serves it.

### 3.2 Code path: why Ops shows a center point
1. `GET /lakes` (`Sources/SectorEngine/API/LakeDirectoryAPI.swift`) encodes `LakeDTO` from `LakeDirectory.all`, which is generated by `scripts/generate-lake-directory.py` from `docs/data/Sector_Lakes_APIs_2.xlsx` (plus `docs/data/full_pool.csv`). DTO fields: id, name, state, states, lat, lon, hasDam, operatorName, apiLevel, usgsGage, tempSource, cwmsOffice, fullPoolFt, poolBasis, poolConfidence. No geometry, no bbox, no area. The response is 187,633 bytes for 621 lakes and carries a version hash.
2. The only geometry file is the job blob above; no Engine route, bucket object or RTDB node serves it.
3. The lake brain profile (`LakeBrainContract.swift`, `Identity`) has `riverSystem`, `basin`, `lakeType`; nothing writes `polygonStatus`.
4. Ops `LakeDetail.tsx` `InfoTab` -> `MapCard`: draws a gradient, the lat/lon and "Boundary (polygonStatus) and satellite basemap appear once Engine exposes lake geometry". `src/types/brain.ts` defines `identity.polygonStatus` and the mock provider invents it ("MOCK: present"), but production never fills it. `EngineLake` has no geometry, `engineApi` only calls `/health`, `/lakes`, `/conditions`. Ops design notes record the same gap.
5. Even a published object would be blocked today: `sector-lake-surface` returns no `access-control-allow-origin` and has no CORS configuration (read with an authenticated GET), and Firebase Hosting (`sector-bowfishing-ops`) rewrites only the exact paths `/health`, `/lakes`, `/conditions`, `/internal/ops/**`.
6. The clarity raster metadata exposes only `coordinates` (4 corners, EPSG:3857), so a bounding box is the only shape the product publishes today.

Conclusion: not an oversight in one place but a missing contract. Geometry exists for 599 lakes, is consumed internally by three jobs, and has no publication path or identity (id, version, source, confidence) in the registry.

## 4. Quality check of all 599 polygons

Method (`geometry_audit.py`, all 621 directory lakes, results cached): for every lake, local metrics (validity, parts, holes, vertices, equal-area area, point containment); NHD HR and 3DHP candidate waterbodies in the polygon envelope with geometry for the largest 10-14, matched by overlap (>= 30 % of the feature inside the polygon) or point containment; USACE `usace_rez` polygons; NID normal-pool surface area (the NID subset pulled by the context thread, read-only); JRC GSW occurrence tiles (23 tiles, 1.0 GB, 1984-2021); HydroLAKES v10; OSM names and bboxes by state. Directory coordinates are rounded (506 lakes to 2 decimals, 43 to 1 decimal = +/-5 km, 64 to 3, 8 to 4), so point containment uses a per-lake tolerance of 0.71 x the rounding cell (min 300 m).

Important limit: the NHD comparison is circular for provenance (the polygons came from NHD), so it answers "did the Engine pick the right NHD feature". Extent truth comes from NID, USACE, OSM, HydroLAKES and GSW.

### 4.1 Results

| Check | Result |
|---|---|
| Valid geometry | 599 of 599 valid (`shapely.is_valid`) |
| GeometryCollection | 1: Devils Lake|ND = 4 Polygons + 1 LineString. Fix: drop the LineString, keep a MultiPolygon |
| Area, Engine vs NHD feature(s) | 590 lakes matched with polygon: ratio median 1.0007, p05 0.9965, p95 1.0072; IoU median 0.9895, p05 0.961. Outliers (ratio outside 0.92-1.08): Kvichak/Ugashik 0.53, Big Creek Lake IA 0.14, Truman Lake MO 0.52, Fox Lake IL 0.73, Hiwassee NC 0.88, Ruby Lake NV 1.99, Buckeye Lake OH 0.0003, Lake Hudson OK 0.73, Winnapaug RI 1.18, Lake Marion SC 1.14. 9 polygons have no NHD overlap (Skilak, Lake Waiau, Wilson/Kaelepulu HI, East Okoboji, Chain O'Lakes, Lake Shafer, Conowingo, Ninigret, Point Judith) |
| Same lake, two ids | 4 pairs with identical polygons (East Lake Tohopekaliga / Tohopekaliga (Toho); Eufaula / W.F. George AL / Walter F. George GA; Flaming Gorge UT / WY; Kerr Lake NC / Kerr Reservoir VA) and 4 nested or overlapping pairs (Clarks Hill GA / Thurmond SC, East / West Okoboji, Kentucky Lake KY / TN, Lake Oahe ND / SD). The registry needs a canonical lake with member ids |
| Multipart fragments | 158 lakes are multipart; 151 carry sliver parts (< 1 % of area each, 6.2 km2 in all); only 10 have more than one substantial part. Guntersville's five extra parts total about 0.006 km2 |
| Directory point vs polygon | 225 polygons contain the point exactly, 374 do not; 169 are flagged in `point_flag`: 126 are `off_water` (a registry coordinate on a dam or shore, polygon fine) and 43 are `identity_risk`: farther than max(3 km, 3 x tolerance, 0.6 x sqrt(area) km), so either the coordinate or the polygon is the wrong lake (Nelson Lake ND 27.6 km, Swanson NE 26.8, Kenai AK 24.1, Reelfoot TN 23.0, Apache AZ 19.2, Bitter Lake SD 14.2) |
| Name sanity | 33 polygons whose NHD feature name differs from the directory name (Ontario's NHD feature is named "Lake America"; Hiwassee Lake NC matched "Persimmon Lake", Fox Lake IL "Nippersink Lake", Truman Lake "Lake of the Ozarks") |
| Independent pool area | NID surface area matches 389 polygon lakes; Engine/NID ratio median 0.96, 287 (74 %) within 0.8-1.25. NID has unit errors (Bull Shoals 1,839 km2, 10x too large; Eufaula 0.02), so one disagreement is soft. USACE polygons match 149 lakes: Engine/USACE median 0.96, p05 0.39 |
| JRC GSW | median 89 % of a polygon was water >= half the time; 7 polygons < 20 % (Buckeye, Sevier Lake dry, Chain O'Lakes, Ruby Lake, Skilak, Wilson/Kaelepulu, Halulu) |
| Partial reservoirs | 67 lakes have unmatched, unnamed or same-named NHD pieces touching the polygon: 11 where adding them moves the area into agreement with NID/USACE (Hartwell, Pickwick, Kentucky Lake KY +92.9 km2, Norris +36.6, Red Lake MN +482.9, Lake Oahe +729.1, Neely Henry, Weiss, Jordan, Lake Wylie, C.J. Strike); 39 more to review (Wheeler, Texoma +107.2, Amistad, Roosevelt, ...) |
| HydroLAKES v10 | 587 of 621 matched; Engine/HL median 1.06, IoU median 0.85 (a year-2000 water mask: older and coarser, see section 9) |
| Degenerate polygons | Lake Shafer IN (4 vertices, 0 km2), Buckeye Lake OH (6 vertices, 0.003 km2; the real lake is 11 km2), Lake Waiau HI (6 vertices) |

### 4.2 Confidence rules (applied in `geometry_audit.py::classify`)

| Level | Rule |
|---|---|
| MISSING | No Engine polygon |
| LOW | Any of: invalid; no NHD/USACE overlap and no OSM name+bbox agreement; NHD area ratio outside 0.5-2 or IoU < 0.5; BOTH NID and USACE put the polygon outside 0.5-2x of pool area; < 20 % of the polygon ever water in GSW; identity risk (point too far, above) |
| HIGH | `source == name`; valid and not a GeometryCollection; NHD ratio 0.93-1.07, IoU >= 0.93, name match >= 0.5; directory point inside the identity allowance; a single substantial part; unmatched adjacent NHD pieces < 5 % of area; NID and USACE ratios (when present) within 0.80-1.25; GSW >= 50 % water-like (when present) |
| MEDIUM | Everything else: repaired/trimmed/osm source, multiple substantial parts, partial-piece suspicion, one pool-area source disagreeing, weak name |

Counts: HIGH 351, MEDIUM 195, LOW 53, MISSING 22. By source: `name` HIGH 351 / MEDIUM 160 / LOW 47; `repaired:*` 0 / 27 / 3; `osm` 0 / 8 / 3. Dominant LOW reason: identity risk (42 of 53). The most common MEDIUM reasons are NID pool-area disagreement (91), adjacent NHD pieces (46), differing NHD name (28), USACE disagreement (31), repaired/trimmed (18 each). HIGH means "NHD-consistent, point-consistent and not contradicted", not "surveyed": the only truth tests available are the independent area and water-history checks. Per-lake reasons are in the CSV `why` column.

## 5. Guntersville holes: islands or artifacts

Test: JRC GSW occurrence (30 m, 1984-2021), mean over each hole's pixels. Land = < 20 % of observations were water.

| Class | Holes | Area km2 |
|---|---|---|
| Land (< 20 %) | 205 | 8.041 |
| Mixed (20-50 %) | 45 | 0.355 |
| Water-like (>= 50 %) | 14 | 0.023 |
| Sub-pixel (< 2 pixels) | 155 | 0.057 |
| Total | 419 | 8.476 |

95 % of the hole area is real land; the same pattern holds for the other pilots (Wheeler 159 land of 277, 4.996 of 5.19 km2; Pickwick 5.01 of 5.33; Hartwell 2.41 of 2.64; Wilson 0.073 of 0.092). The holes are islands, ridges and peninsula cut-offs that NHD digitised, and for bowfishing they are the shoreline that matters. The rings inherit from NHD (420 rings in the source feature). What to fix: drop holes under about 100 m2 (17 in Guntersville, 1,435 fleet-wide of 23,910) and remove sliver parts; keep the rest. 6 parts / 419 holes is therefore not a defect. The 14 water-like holes are candidates for a manual look, not a rule.

## 6. The 22 lakes without a polygon

| Group | Lakes | NHD today | Why missing | Action |
|---|---|---|---|---|
| Great Lakes and large border water (16) | Erie (MI, NY, OH, PA), Huron (MI), Michigan (IN, MI, WI), Ontario (NY), Superior (MI, MN, WI), Green Bay (WI), Lake of the Woods (MN), Great Salt Lake (UT), Iliamna (AK) | Present: Superior 82,002 km2, Huron 59,060, Michigan 57,857, Erie 25,738, Ontario 18,846 (feature named "Lake America"), Great Salt Lake 3,389, Lake of the Woods 1,234, Iliamna 2,649 | No record of why. The clarity job sizes frames from the polygon area (a 12,100 km2 Sentinel-2 tile model); these are 1.2-8 times larger, so exclusion was probably deliberate or a failure. Inferred, not documented | Decide policy (section 9.4): ship a coarse boundary, no satellite frame |
| Small Hawaii ponds (5) | Koele ponds (Lanai), Nuuanu, Puu Loa, Waiakea, Waimaluhia | None found: NHD large-scale waterbody has only tiny mapped ponds near the points | Not mapped as lake/reservoir in NHD (layers 11 and 12 both queried) | OSM or manual |
| Chickahominy Lake, VA | 1 | The lake is mapped as FTYPE 466 swamp/marsh polygons (5.2, 2.1, 1.6 km2 near the point), filtered out by the lake/reservoir type filter | Type filter | Allow 466 for tidal freshwater impoundments, review |

## 7. Sources tested

All were queried on 2026-10-13. Cadence is from metadata.

| # | Source | Tested | Coverage of the 621 lakes | Quality | Access, ID | License | Cadence | Verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | USGS NHD HR waterbody, REST `nhd/MapServer/12` (fields PERMANENT_IDENTIFIER, GNIS_NAME, AREASQKM, FTYPE, FDATE, RESOLUTION; max 2,000 records; json/geoJSON/PBF) | Envelope queries for 621 lakes, geometry for 1,500+ features, 1 bulk HEAD | 606 matched (590 with an Engine polygon, 16 of the 22 missing lakes); 15 not (9 polygon lakes, Chickahominy, 5 Hawaii ponds) | Shoreline per imagery date (2001-2023, median about 2013, 45 lakes 2021, 7 in 2023); RESOLUTION 2; vertices 5-10 m; splits large reservoirs at unit boundaries (unnamed pieces) | Open REST, anonymous; PERMANENT_IDENTIFIER, GNIS_ID, REACHCODE. Bulk: `NHD_H_National_GDB.zip` 30 GB (2025-09-19), `NHD_H_Alabama_State_GDB.zip` 388 MB (2023-12-27) | Public domain (USGS) | Rolling, per-state/HU updates; service FDATE per feature | ACCEPTED primary |
| 2 | USGS 3DHP_all, REST `3DHP_all/MapServer/60` Waterbody (id3dhp, gnisid, featuretype, workunitid, featuredate) | 621 lakes | 609 matched. 604 carry workunit `NHD` (an NHD copy dated 2023-09-14); 5 are native 3DHP workunits (`300285`, `300286`, `300706`; dated 2025-2026). Top-feature area equals NHD within 0.1 % in 582 of 590 lakes | Same shoreline as NHD today; lidar-native elsewhere over time | REST; no bulk: `StagedProducts/Hydrography/3DHP/Annual/GPKG/` listing is empty (2025-12-08 stub) | Public domain | Annual, growing | ACCEPTED as the upgrade path; prefer a non-`NHD` workunit when newer |
| 3 | USACE Reservoirs `usace_rez` FeatureServer (418 polygons: NAME, DISTRICT, NIDID, OMBIL_SITE_ID, DRY) | Full pull (68 MB) | 149 of 621 lakes | "Maximum conservation pool or a reasonable representation" per item metadata; edited 2024-04-02. For dry/flood-control lakes it is the flood pool (Chatfield, Alamo, Santa Rosa, Beltzville). USACE/NID median 0.99, but only 74 % within 20 %; the Engine/USACE median is 0.96 | Open; NIDID is a direct join to the NID | "Without any use restrictions", national scale (not local mapping) | Ad hoc (2024-04) | ACCEPTED as a labelled pool-extent layer, not the shoreline |
| 4 | USACE National Inventory of Dams (NID) | Public national gpkg HEAD (`/api/nation/gpkg` redirects to S3, 81.7 MB); `/api/nation/dams` needs a filter body (400); `/api/nation/csv` 403; v1 subset already pulled by the context thread | 389 polygon lakes matched by dam name within 25 km | Point; SURFACE_AREA (acres, normal pool), NORMAL_STORAGE; 10x unit errors exist | Public gpkg, no key; NIDID | Public | Annual | ACCEPTED validator and dam/lake link, not a polygon |
| 5 | JRC Global Surface Water occurrence v1.4 (2021 release) | 23 tiles (1.0 GB), all 599 polygons | 100 % of the CONUS/AK/HI footprint | 30 m, 1984-2021 water frequency; independent of NHD | `storage.googleapis.com/global-surface-water/downloads2021/occurrence/occurrence_<lon>_<lat>v1_4_2021.tif`, anonymous | Free and open, cite Pekel et al. 2016 | Static 2021 | ACCEPTED validation and current-vs-history reference |
| 6 | HydroLAKES v10 (SRTM water mask about 2000) | Full pull (820 MB zip), 621 lakes | 587 matched | Older and coarser: IoU median 0.85 vs Engine; Guntersville 207.8 vs 266 km2, Hartwell 190.6; carries GRanD ids | `data.hydrosheds.org/file/hydrolakes/HydroLAKES_polys_v10_shp.zip` | HydroSHEDS licence: free with attribution (verify before shipping) | 2016, static | REFERENCE only; not canonical |
| 7 | OpenStreetMap via Overpass (`overpass-api.de`; `overpass.kumi.systems` unreachable from this host) | 50 state queries (name-token regex), 5 pilot polygons | 593 of 621 have a candidate with name match >= 0.5; geometry compared for pilots only | Pilot polygons: Guntersville 234.1 (Yahoo-era, IoU 0.86), Pickwick 162.7, Hartwell 219.9 (full-pool-like, 116 holes), Wilson 62.3, Wheeler none | Public instances throttle: per-lake queries returned 4 results in 10 min, per-state queries finished in 16 min (FL, MN, NH first tries 504, retried OK). Ids: relation/way, `wikidata`, `gnis:feature_id` | ODbL (share-alike on derived databases) | Continuous | FALLBACK and validator; license review before publishing OSM-derived geometry |
| 8 | NHDPlus HR (REST `NHDPlus_HR/MapServer/9`; bulk National Release 2, 31.3 GB, 2026-02-11) | Layer list only | same HR data | Adds catchments/flow attributes | Bulk GDB, no key | Public domain | Release-driven | LEAD for bulk/network attributes; geometry equals NHD HR |
| 9 | Census TIGERweb Hydro layer 1 (AREAWATER) | Guntersville query | Broken into county-clipped pieces (Guntersville = 77.0 + 99.3 + 16.5 km2 per county, ~193 of 265 km2) | Generalised, county clipped | REST | Public domain | Annual | REJECTED |
| 10 | TVA GIS open data (ArcGIS Online `TVA-GIS`, 563 items) | Searched | Dams (points), boat ramps, stream access, land plans, one lake inundation boundary (Chatuge); no reservoir water polygons | n/a | `egismaps.tva.gov` unreachable (HTTP 000) | TVA open data | n/a | DEAD END for polygons; LEAD: `TVA_Recreation_Layers_Hosted` boat ramps (bowfishing access, outside this track) |
| 11 | EPA WATERS NHDPlus V2 snapshot (`watersgeo.epa.gov/.../NHDSnapshot_NP21`) | Queried | n/a | Service "not started" | REST | Public | n/a | DEAD END |
| 12 | USFWS National Wetlands Inventory REST (`fwsprimary.wim.usgs.gov`) | Queried | n/a | HTTP 500 on query; layers list empty | REST | Public domain | n/a | DEAD END (REST); LEAD bulk state downloads |
| 13 | USGS 3DEP DEM ImageServer (pool extent from DEM at `fullPoolFt`) | `exportImage` 502 and 504; `identify` at Hartwell center returned NoData | n/a | Untested | REST | Public domain | n/a | LEAD; blocked (B-geometry-005) |
| 14 | GeoDAR / GRanD reservoir polygons (Zenodo) | `zenodo.org` unreachable (HTTP 000) | n/a | n/a | n/a | n/a | n/a | LEAD only (B-geometry-004) |
| 15 | State portals (e.g. TWDB existing-reservoir boundaries, 2012-era, shapefile) | Web search only; direct REST guesses unreachable | TX only | Old; normal-pool field unverified | Download page | Public | Irregular | LEAD per state, not needed first; add only where national layers fail |

The Alabama state GDB is 388 MB; extrapolating to all states would be 5-10 GB of GDB for NHD HR waterbodies, so the REST query path (about 1,300 requests, cached) is the right method for 621 lakes and the bulk path only for a full re-build.

## 8. Layered strategy

### 8.1 Precedence of polygons
1. Identity first (never geometry): GNIS id + NHD permanent ids, NID id, USACE OMBIL id, Wikidata, OSM relation, HydroLAKES/GRanD id, recorded per lake as `externalIds`. Fixes name collisions (Long Pond MA) and gives the same-lake pairs of section 4 a canonical lake.
2. Shoreline (`geometry`, the typical water surface): the NHD HR union of the lake's connected 390/436 features, including unnamed and same-named pieces within 100 m, dated by FDATE. A 3DHP waterbody whose workunit is not `NHD` and whose featuredate is newer replaces it. Fill rule: the 67 adjacent-piece lakes (`add_adjacent_pieces`: 11 now; `review`: 39).
3. Operator override: a state or operator polygon (TWDB, a TVA/USACE normal-pool polygon) overrides national data only when it is labelled normal pool, is newer or more detailed, and passes the same QA (area within +/-20 % of NID/USACE, GSW >= 50 % water-like). USACE `usace_rez` is not such a source: it is a pool-extent layer.
4. Fallbacks: OSM relation (license review), then a coarse boundary from HydroLAKES/GSW, then a bbox flagged LOW.
5. Always keep the previous version and a diff report; a change in area > 10 % needs review.

### 8.2 Normal pool vs current water extent
Store separate, explicitly labelled extents, never one polygon pretending to be all three:

| Extent | Meaning | Source | Use |
|---|---|---|---|
| `shoreline` | Typical water surface on a dated image | NHD union / 3DHP | Canonical boundary, Ops card, shoreline length, islands |
| `poolExtents[]` | `normalPool`, `maxConservationPool`, `floodPool` with source and date | USACE `usace_rez` (149 lakes, flood/max pool), NID surface area, DEM at `fullPoolFt` (untested) | Pool context when the lake is high or low |
| `currentExtent` | The water on the latest clear pass | Sentinel-2 water mask already computed by `lake-surface` (per-day PNG), not a registry field | Satellite/clarity layers |

NHD vs the pool shows the problem: Guntersville agrees with NID (265.5 vs 267.1), but Pickwick NHD is 80 % of NID until the unnamed piece is added, and Hartwell's NHD is the drought-era water surface. The registry should carry `extentKind` and `featureDate` so Ops can show "NHD water surface, 2021-05-26".

### 8.3 Conflict and confidence scoring
Per-lake score from the rules in section 4.2, reported with the reason list; inputs are the area ratios to NHD, NID, USACE, HydroLAKES, the GSW inside share, directory point distance, name match and part structure. A disagreement between two independent pool sources (NID and USACE) is a stronger signal than one (NID has unit errors). A lake moves to HIGH only when the polygon is NHD-consistent and independent data does not contradict it. The GSW inside share (median 89 %) is a check on shoreline placement, not an area measure.

### 8.4 Large lakes
Great Lakes: ship a display boundary (simplified at 250 m or the NHD multipolygon as a feature) and set `satelliteSupported=false`; do not run the clarity frame. Lake of the Woods, Iliamna and Great Salt Lake fit the same rule.

## 9. Recommended canonical contract (not implemented)

### 9.1 LakeRegistry geometry fields

```json
{
  "lakeId": "Guntersville|AL",
  "name": "Guntersville",
  "aliases": ["Guntersville Lake", "Lake Guntersville"],
  "memberIds": ["Guntersville|AL"],
  "externalIds": {"gnisId": "01286448", "nhd": ["139326855"], "nidId": "AL09501", "wikidata": "Q3561578", "osm": "relation/911315"},
  "bbox": [-86.3985, 34.2852, -85.6186, 35.0377],
  "centroid": [-86.01, 34.65],
  "geometry": {
    "extentKind": "waterSurface",
    "source": "usgs-nhd-hr",
    "sourceIds": ["139326855"],
    "sourceDate": "2021-05-26",
    "areaKm2": 265.5,
    "islands": 419,
    "displayUrl": "https://storage.googleapis.com/sector-lake-surface/geometry/Guntersville_AL/g3-ab12cd34/display.geojson",
    "analysisUrl": ".../analysis.geojson",
    "displayToleranceM": 50,
    "bytes": {"display": 133175, "displayGzip": 39927},
    "sha256": "..."
  },
  "poolExtents": [{"kind": "maxConservationPool", "source": "usace-rez", "areaKm2": null}],
  "geometryVersion": "g3-ab12cd34",
  "geometryUpdatedAt": "2026-10-13T00:00:00Z",
  "geometryConfidence": {"level": "HIGH", "score": 0.97, "reasons": []},
  "geometrySource": "usgs-nhd-hr"
}
```

Justification of the extras: `memberIds` (one canonical lake, 8 overlapping directory-id pairs), `externalIds` (identity independent of name), `extentKind`/`sourceDate` (water surface vs pool), `islands`/`areaKm2` (cheap sanity), `poolExtents` (separate pool layers), `sha256`/`bytes` (cache and integrity), `geometryConfidence.reasons` (Ops can show why).

### 9.2 Size of Guntersville, and of the fleet

Simplification of the full NHD HR polygon with a topology-preserving filter in a local equal-area projection (tolerance m, vertices, area change, maximum boundary deviation, JSON size at 6 and 5 decimals, gzip, Google polyline):

| Tolerance | Vertices | Area change | Max deviation | GeoJSON 5 dp | gzip 5 dp | Polyline |
|---|---|---|---|---|---|---|
| none (NHD) | 56,508 | 0 | 0 | 1,175,210 B | 274,715 B | 152,509 |
| 5 m | 23,302 | +0.06 % | 8.0 m | 485,148 | 123,140 | 79,479 |
| 10 m | 15,073 | +0.17 % | 17.2 m | 314,072 | 82,446 | 56,375 |
| 25 m | 8,704 | +0.53 % | 33.2 m | 181,766 | 49,313 | 35,244 |
| 50 m | 5,810 | +1.22 % | 77.2 m | 121,602 | 33,399 | 24,863 |
| 100 m | 3,955 | +2.83 % | 99.9 m | 83,087 | 22,954 | 18,021 |
| 250 m | 2,742 | +6.6 % | 249.4 m | 57,891 | 15,765 | 13,463 |

(The other pilots scale similarly: Wheeler 25 m = 5,936 vertices / 33.8 KB gzip, Hartwell 25 m = 6,468 / 35.9 KB.) All 599 Engine polygons: 1.30 M vertices, 27.5 MB raw / 7.26 MB gzip today; at 25 m: 5.1 MB gzip; at 50 m: 12.1 MB raw / 3.36 MB gzip (median lake 1.8 KB gzip, p95 24 KB, max 118 KB); at 100 m: 2.2 MB gzip.

### 9.3 Delivery path
- Display polygon (about 50 m) and analysis polygon (full resolution NHD union) are different artifacts. Ops needs only the display one; clarity/shoreline jobs use analysis.
- Static, immutable, versioned GeoJSON in the public bucket: `geometry/<slug>/<version>/display.geojson`, `analysis.geojson`, with a `geometry/<slug>/latest.json` pointer; `Cache-Control: public, max-age=31536000, immutable` on versioned objects. `GET /lakes` (187.6 KB today) gains per lake: `geometryVersion`, `geometryUrl`, `bbox`, `areaKm2`, `geometryConfidence`, `geometrySource` (about 250 B x 621 = +155 KB uncompressed; the existing ETag keeps it a 304 when unchanged).
- Not RTDB: it would work (RTDB string limit 10 MB; Guntersville 133 KB), but every Ops listener on the lake node would download it on each subscription, it is not CDN-cacheable and bandwidth is billed per GB. RTDB should carry only `geometryVersion`/status.
- Browser access: requires bucket CORS (not configured) or an Engine route `GET /lakes/{id}/geometry` plus a Hosting rewrite `/lakes/**` (today only the exact `/lakes` is proxied). Either needs a human change (M-geometry-02).
- Ops: draw the display polygon on the Mapbox/Leaflet card with a source and date caption; if `geometryUrl` is absent, keep the current placeholder.

## 10. Blockers and Michael actions

| ID | Item | Impact | Priority |
|---|---|---|---|
| B-geometry-001 / M-geometry-04 | The builder that made `polygons.geojson.gz` is in no repo or worktree; provenance is inferred from data. Confirm whether a script exists or accept rebuilding from the section 8 rules | Reproducibility | medium |
| B-geometry-002 / M-geometry-02 | Bucket `sector-lake-surface` has no CORS; Hosting proxies only `/lakes`. Ops cannot fetch any object. Decision: bucket CORS (a bucket-config write) vs Engine route + rewrite | Blocks Ops rendering | high |
| M-geometry-01 | Approve the canonical policy: NHD union + dated `extentKind`, pool layers separate, display/analysis split, contract of section 9 | Unblocks implementation | high |
| M-geometry-03 / B-geometry-011 | Correct 43 identity-risk and review 126 off-water registry coordinates (the sheet has a "Coord Conf" column that is not exported); list in the CSV `point_flag` | Wrong-lake risk | medium |
| M-geometry-05 / B-geometry-012 | Policy for the 22 missing lakes (Great Lakes display-only; Hawaii ponds and Chickahominy manual) | Completeness | low |
| B-geometry-003..010 | Overpass load and kumi outage, Zenodo unreachable, 3DEP 502/504, NWI 500, TVA host unreachable and no polygon, EPA WATERS stopped, 3DHP bulk empty, NID `dams` filter | Recorded dead ends; none blocks the recommendation | low |

## 11. Reproduce
- `research/lake-brain/geometry_audit.py --stage all` (stages `local nhd tdhp osm usace nid gsw hl classify`): writes `geometry/lake_geometry_flags.csv` (data dir) and `data/geometry_summary.json`. Responses are cached; a re-run is minutes. Stages `gsw` and `hl` read outputs of `geometry_gsw.py` and `geometry_hydrolakes.py`, which need the rasterio/pyogrio venv in the data dir.
- `geometry_holes_gsw.py "Guntersville|AL" ...` (islands vs artifacts), `geometry_osm_pilots.py` (pilot OSM polygons), `geometry_simplify_sizes.py` and `--fleet` (section 9.2).
- All sources and parameters are in the ledger; manifest rows are in `Sector_Research_Data/lake-brain/MANIFEST.jsonl`.
