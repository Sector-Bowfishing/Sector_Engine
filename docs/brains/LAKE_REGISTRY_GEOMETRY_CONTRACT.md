# Lake Registry — Geometry Contract v1

**Owner:** Sector Engine (Lake Brain adoption, work package A2). **Status:** PUBLISHED 2026-10-13 (v1). **Delivery route:** static, versioned GeoJSON in the public bucket `gs://sector-lake-registry` plus one small index object; approved by Michael. Builder: `jobs/lake-geometry/`. Research basis: `docs/research/lake-brain/LAKE_BRAIN_GEOMETRY_RESEARCH.md` (branch `docs/lake-brain-research`).

Principle (same as the Brain Platform contract): **Engine owns truth, Ops owns presentation.** The registry owns lake *geometry identity* (which water, which source, which version, how sure). It never invents a shape: a lake with no usable polygon has `geometry: null`, a reason and confidence `MISSING`.

This contract adds **no Engine route and no RTDB node**. `/lakes` (customer-serving) is unchanged; nothing is deployed.

---

## 1. Where things live

| | |
|---|---|
| Bucket | `gs://sector-lake-registry`, project `sector-9393c`, `us-central1`, uniform bucket-level access, public read (`allUsers` `roles/storage.objectViewer`). Writers: project principals only (nothing added). The data is derived from the public-domain USGS NHD and contains nothing private. |
| Base URL | `https://storage.googleapis.com/sector-lake-registry` |
| CORS | `GET`, `HEAD` for `https://sector-bowfishing-ops.web.app`, `https://sector-bowfishing-ops.firebaseapp.com`, `http://localhost:5173`, `http://localhost:4173`; exposes `Content-Type`, `Content-Encoding`, `ETag`; preflight cached 3600 s. Config: `jobs/lake-geometry/cors.json`, applied by `jobs/lake-geometry/setup_bucket.sh`. A new Ops origin (preview channel, custom domain) needs an edit to that file and a re-run. |
| Index | `registry/lakes.v1.json` (621 lakes, 1.52 MB raw, 0.22 MB on the wire), `Cache-Control: public, max-age=300`, `Content-Type: application/json`, `Content-Encoding: gzip` |
| Build record | `registry/manifest.v1.json`, `registry/README.txt` (same cache policy) |
| Geometry | `lakes/{lakeKey}/geometry.v1.display.geojson.gz` and `lakes/{lakeKey}/geometry.v1.analysis.geojson.gz`, `Content-Type: application/geo+json`, `Content-Encoding: gzip`, `Cache-Control: public, max-age=31536000, immutable` |
| `lakeKey` | the Brain RTDB lake key: every run of non-alphanumerics in `lakeId` becomes one `_` (`Guntersville|AL` → `Guntersville_AL`, `Pickwick Lake|TN` → `Pickwick_Lake_TN`). Identical to `jobs/brain_platform/sector_brain_platform/keys.py::lake_key`; parity over all 621 directory ids is a test (`tests/test_lake_geometry.py`). The key is lossy, so the index stores `lakeId` too. |

`Content-Encoding: gzip` is set on the stored object, so `fetch()` decodes it transparently; `curl` needs `--compressed`. A client that does not send `Accept-Encoding: gzip` receives the decoded JSON (GCS decompressive transcoding; verified).

## 2. The index — `registry/lakes.v1.json`

```jsonc
{ "schema": "sector.lake-registry/v1", "geometryVersion": "v1", "generatedAt": "2026-10-13T…Z", "count": 621,
  "baseUrl": "https://storage.googleapis.com/sector-lake-registry", "license": "USGS National Hydrography Dataset (public domain)",
  "lakes": [ /* one entry per directory lake, sorted by lakeId */ ] }
```

One entry (Guntersville, abridged; real values from the build):

```jsonc
{
  "lakeId": "Guntersville|AL", "lakeKey": "Guntersville_AL", "name": "Guntersville",
  "aliases": ["Guntersville Lake"],                       // evidence-based only: NHD GNIS names, USACE / HydroLAKES names that match
  "memberIds": ["Guntersville|AL"],                       // directory ids that are the SAME water (share NHD features); always includes lakeId
  "state": "AL", "states": ["AL"],
  "location": { "lat": 34.42, "lon": -86.26, "source": "sector-directory", "pointFlag": "ok", "distanceToShorelineM": 139 },
  "externalIds": { "nhd": ["139326855"], "gnisId": null, "nidId": "AL09501", "osm": "relation/911315", "wikidata": "Q3561578",
                   "hydrolakes": "820", "grand": "1847" },
  "bbox": [-86.39849, 34.28517, -85.61857, 35.03774],     // [west, south, east, north]; null when geometry is null
  "centroid": [-86.11587, 34.54448], "labelPoint": [-85.93498, 34.66199],   // [lon, lat]; labelPoint is always inside the water
  "areaKm2": 266.822,                                      // equal-area area of the ANALYSIS polygon
  "geometry": {
    "extentKind": "shoreline-nhd-hr-union", "source": "usgs-nhd-hr",
    "sourceIds": ["139326855"], "seedIds": ["139326855"],  // NHD PERMANENT_IDENTIFIERs: all pieces / the matched water body alone
    "sourceDate": "2021-05-26", "sourceDateRange": ["2021-05-26", "2021-05-26"],   // NHD feature dates (FDATE)
    "pickMethod": "engine-overlap", "pieces": 1,
    "adjacentPieces": { "found": 0, "included": 0, "areaKm2": 0, "decision": "no adjacent pieces" },
    "islands": 401, "areaKm2": 266.822, "sourceAreaKm2": 265.487, "areaDisplayKm2": 268.756,
    "displayToleranceM": 50, "analysisToleranceM": 25, "displayToleranceEffectiveM": 50, "analysisToleranceEffectiveM": 25,
    "displayVertices": 5731, "analysisVertices": 8624,
    "displayUrl": ".../lakes/Guntersville_AL/geometry.v1.display.geojson.gz", "analysisUrl": ".../geometry.v1.analysis.geojson.gz",
    "bytes": { "displayGzip": 33646, "displayRaw": 120265, "analysisGzip": 49496, "analysisRaw": 180381 },
    "sha256": { "display": "fb30219f…", "analysis": "9d515e8c…" },     // sha256 of the STORED (gzip) bytes
    "license": "USGS National Hydrography Dataset (public domain)" },
  "poolExtents": [ { "kind": "normalPool", "source": "nid", "areaKm2": 267.09, "ratioToShoreline": 0.999, "id": "AL09501", … },
                   { "kind": "fullPoolElevation", "source": "sector-directory", "elevationFt": 595, "basis": "fullPool", "confidence": "high" } ],
  "geometryVersion": "v1", "geometryUpdatedAt": "2026-10-13T…Z",
  "geometryConfidence": { "level": "HIGH", "score": 0.96, "reasons": [], "before": "HIGH",
                          "evidence": { "nidAreaRatio": 0.999, "usaceAreaRatio": null, "gswWaterSharePct": 84.2, "osmCorroborated": true } },
  "pointFlag": "ok",
  "classification": { "lakeClass": "R1_run_of_river_pool", "regime": "reservoir", "region": "SE", "size": "l", "depthClass": "mid",
                      "residenceTimeDays": 13.0, "hasDam": true }
}
```

Field notes.

* `geometry: null` (31 lakes at v1, see section 9): `bbox`, `centroid`, `areaKm2` are null, `geometryConfidence.level` is `MISSING`, `geometryMissingReason` says why and `geometryMissingStatus` is `held-large-water`, `no-nhd` or `pending`. `geometryHeld` (NHD ids and area) or `geometryWithheld` record what exists but was not published.
* `memberIds`: one canonical water body can have several directory ids (Kentucky Lake KY/TN, Lake Oahe ND/SD, Flaming Gorge UT/WY, Kerr NC/VA, Eufaula/W.F. George AL/GA, Clarks Hill/Thurmond GA/SC, East Lake Tohopekaliga / Tohopekaliga). They share NHD features, so each has the same geometry and lists the others. Each member keeps its own object (no cross-lake indirection).
* `externalIds.gnisId` is `null` in v1: the GNIS attribute was not in the research cache and the USGS service was unavailable during the build; adding it is an index-only refresh.
* `areaKm2` vs `displayAreaKm2`: Douglas-Peucker is not area-preserving; the 25 m analysis polygon is +0.5 % and the 50 m display polygon +0.7 to +1.2 % on large reservoirs. Use `areaKm2` for any number, the display polygon only to draw. `sourceAreaKm2` is the sum of the NHD `AREASQKM` of the pieces.
* `pointFlag` audits the *directory coordinate* against the shoreline (not the shoreline): `ok`; `off-water` (the registry point sits on a dam or shore, beyond its rounding tolerance); `identity-risk` (farther than max(3 km, 3 x tolerance, 0.6 x sqrt(area km2) km): the coordinate or the lake is wrong). Rule: `lake_geometry.point_flag`.
* `poolExtents` are *references*, not payloads. `ratioToShoreline` = shoreline area / reference area. `usace-rez` is the USACE reservoir polygon area (max conservation pool, or flood pool for dry dams); `nid` is the owner-reported normal-pool surface area (it has unit errors, e.g. Bull Shoals); `fullPoolElevation` is the directory's feet value.
* `classification` is the lightweight research feature set (`lake_features.csv`): `lakeClass`, `regime`, `region`, `size`, `depthClass`, `residenceTimeDays`, `hasDam`. Informational; fields can be null.
* `geometryVersion` is the *path* version of the geometry objects (`v1`). `geometryUpdatedAt` is the build time of the index entry.

## 3. The geometry objects

Each object is one GeoJSON `Feature` (RFC 7946: WGS84 lon/lat = EPSG:4326, exterior rings counter-clockwise, holes clockwise, 5-decimal coordinates), `Polygon` for a single part, `MultiPolygon` otherwise (159 of the 1,180 objects; 590 lakes x 2 variants). `properties`: `lakeId`, `lakeKey`, `geometryVersion`, `variant` (`display` / `analysis`), `toleranceM` (the effective tolerance), `areaKm2` (of that variant), `extentKind`, `source`, `sourceIds`, `sourceDate`, `license`.

| Variant | Tolerance | Use |
|---|---|---|
| `display` | Douglas-Peucker 50 m (topology preserving) | Draw on the Ops map card. Guntersville 5,731 vertices, 33.6 KB gzip |
| `analysis` | 25 m | Measurement: shoreline length, shallow-water and clarity masks, area. Guntersville 8,624 vertices, 49.5 KB gzip |

The tolerance is capped at 2.5 % of sqrt(area) (minimum 2 m) so a 0.1 km2 pond is not simplified to a 50 m blob; the nominal and effective values are both in the index. Islands (interior rings) of at least 100 m2 are kept (Guntersville: 401 of the 419 NHD islands; the other 18 are under 100 m2); water parts under 100 m2 are dropped except the largest. 95 % of Guntersville's hole area is real land (JRC GSW, research section 5): the islands are the shoreline that matters for bowfishing.

## 4. How the shoreline is made (reproducible)

`jobs/lake-geometry/build_geometry.py` (dry-run by default; `--upload` writes). Inputs are the research caches outside Git; the manifest records their sha256 and the build commit.

1. **Seed = the NHD HR water body.** USGS NHD High Resolution waterbody (REST `nhd/MapServer/12`, FTYPE lake/pond 390 and reservoir 436; public domain). The research cache holds the queries for all 621 lakes (reused; a miss triggers a public GET). Seed rule: the NHD features that overlap the Engine's shipped polygon by at least 30 % of the feature. The directory point is *not* a seed (registry coordinates are rounded and often sit in the neighbouring lake: Big Creek Lake IA is inside Saylorville, Truman Lake MO inside Lake of the Ozarks). Without a usable Engine polygon: the nearest name-matched feature, an unnamed feature containing the point, or any feature containing the point whose area is within 0.8 to 1.25 of an independent pool-area reference (Buckeye Lake OH is NHD "Crane Lake", 11.2 km2, NID 11.3 km2).
2. **Union of connected pieces.** NHD splits large reservoirs at unit boundaries into unnamed pieces; the Engine's name-based pick dropped them. Unnamed or same-named features within 100 m of the seed (or of the Engine outline) and at least 2 % of its area are united with it. Safeguard: the pieces are left out if they move the area *further* from the NID/USACE pool-area reference (6 lakes: Falls Lake NC, Houghton Lake MI, Lake Koocanusa MT, Lake Macbride IA, Monksville Reservoir NJ, Squam Lake NH). A piece claimed by two different lakes (Weiss / Neely Henry on the Coosa) goes to the nearer. Hairline gaps between separately generalised pieces are closed (12 m) only between pieces, never inside one.
3. **Repair.** `GeometryCollection` → polygons only (Devils Lake|ND's LineString dropped); invalid rings repaired (`make_valid`); the three degenerate research polygons (Lake Shafer 4 vertices, Buckeye Lake 6, Lake Waiau 6) are never used as geometry; holes under 100 m2 dropped; result validated at every step; grid snap 1e-5 degrees with validity kept.
4. **Two variants** (section 3), gzip level 9 with `mtime=0`. Rebuilding gives byte-identical objects (verified across builds: 1,180 of 1,180). Objects total 9.1 MB gzip (display 3.62 MB, median 2.1 KB per lake, 95th percentile 25.8 KB, largest Rainy Lake 120 KB; analysis 5.49 MB).

Source generalisation: the cached NHD geometry carries a 0.00008 degree (about 9 m) server-side `maxAllowableOffset`; the 25 m analysis tolerance is applied on top. The NHD polygon is the water surface on its imagery date (`sourceDate`, 2001 to 2023), not the normal pool: that is why `extentKind` is `shoreline-nhd-hr-union` and pool references are separate (`poolExtents`).

## 5. Confidence

`geometryConfidence.level` is derived mechanically by `lake_geometry.derive_confidence` from facts about the *new* geometry; nothing is set by hand. `before` is the level the research audit gave the Engine polygon, kept for the diff.

| Level | Rule |
|---|---|
| `MISSING` | `geometry` is null. |
| `LOW` | Any of: identity risk (directory point farther than the allowance, so the coordinate or the lake is wrong); NID **and** USACE both off by more than 2x; fewer than 20 % of the shoreline was ever water in JRC Global Surface Water 1984 to 2021. |
| `HIGH` | None of the LOW reasons and none of: NID or USACE ratio outside 0.80 to 1.25; GSW water share below 50 %; the Engine's own pick was a fallback (`repaired:*`, `osm`) or the pick was by point/name fallback; NHD name differs from the directory name (token match below 0.5); more than one substantial part (at least 1 % of the area) in the *matched* water; adjacent NHD pieces left out. |
| `MEDIUM` | Everything else. |

How a lake moves from MEDIUM to HIGH: the union brings the area into 0.80 to 1.25 of NID/USACE, the "pool-area ratio" reason disappears and no other reason remains (Hartwell 136.7 → 218.7 km2 against NID 226.4 / USACE 233.6; Pickwick 139.9 → 169.4 against NID 172.8). `score` is ordinal, not a probability: HIGH 0.90 plus 0.02 per independent corroboration (NID or USACE within 10 %, GSW at least 80 %, OSM bbox IoU at least 0.8), at most 0.98; MEDIUM 0.80 minus 0.05 per reason, at least 0.50; LOW 0.45 minus 0.05 per reason beyond the first, at least 0.10.

**HIGH means "NHD-consistent, point-consistent and not contradicted by independent data", not "surveyed".** A lake with no NID/USACE reference (Wheeler: NID entry unusable) can be HIGH only because nothing contradicts it; read `evidence` and `reasons`. Ops should show the level and the first reason, and the `sourceDate`.

Counts at publication (621 directory lakes):

| Level | Research audit (Engine polygon) | After the union (this registry) |
|---|---|---|
| HIGH | 351 | 404 |
| MEDIUM | 195 | 142 |
| LOW | 53 | 44 |
| MISSING | 22 | 31 |

Transitions: HIGH stays HIGH 350; MEDIUM to HIGH 50 (the union closes the pool-area gap: Hartwell, Pickwick, Kentucky Lake, Neely Henry, Flaming Gorge, ...); LOW to HIGH 4 (Lake Oahe ND: union of the dropped 729 km2 piece; Stump Lake ND: same; Lac Courte Oreilles WI: same; Big Creek Lake IA: the research matched the neighbouring Saylorville water body, the Engine outline was right); MEDIUM stays 140; HIGH to MEDIUM 1 (Ross Lake WA: two substantial parts in the matched water); LOW to MEDIUM 1 (Skilak AK: the Engine polygon sat 23 km away on the wrong water, replaced by NHD Skilak Lake 100.2 km2, 99.5 % water in JRC GSW against 0.4 % before).

MISSING rises by 9: lakes that had a research polygon but no verifiable one. Degenerate or misplaced (4 LOW before): Buckeye Lake OH, Chain O'Lakes IL, Lake Shafer IN, Wilson/Kaelepulu HI; MEDIUM before: Lake Waiau HI (6 vertices) and the OSM-derived Conowingo, Ninigret Pond, Point Judith Pond, East Okoboji. Each has its reason in the index; nothing is dropped silently.

## 6. Versioning and immutability

* A versioned geometry object is **never overwritten**. `build_geometry.py --upload` copies with `--no-clobber`.
* New geometry for a lake (new NHD vintage, 3DHP upgrade, operator polygon, policy change) is a **new path**: `geometry.v2.display.geojson.gz` next to the v1 files. The index entry then points at v2 (`geometry.displayUrl`, `geometryVersion: "v2"`, `geometryUpdatedAt`); v1 objects stay readable for caches and rollbacks.
* The index is the only mutable object (`registry/lakes.v1.json`, 5 minute cache). Its schema (`sector.lake-registry/v1`) is additive: new optional fields do not bump it. A breaking change to field names or meaning is `lakes.v2.json` served in parallel.
* A change of more than 10 % in `areaKm2` between versions needs a human review of the diff (v1 objects stay in the bucket, so the previous shoreline is always diffable).
* Adding a lake that had `geometry: null` (the 22 policy lakes, the pending ones) creates new objects under `v1` and is not an overwrite.
* Provenance of the first publication: four objects (Norris Lake TN and Ruby Lake NV, display and analysis) were replaced about 30 minutes after the first upload, before any consumer existed, when an adjacency rule was fixed (the Engine outline now also counts as adjacent). No other object has been replaced, and the full set was re-read anonymously afterwards (1,180 of 1,180 sha256 match the index).

### Update procedure
1. Refresh inputs (new NHD cache entries, `lake_geometry_flags.csv`, features). 2. `python build_geometry.py` (dry run; read the summary and diff the index against the live one). 3. `python build_geometry.py --upload` (geometry no-clobber; index replaced). 4. `python verify_upload.py` (anonymous HTTPS check: status, CORS, headers, sha256 against the index, area). 5. For a *changed* shoreline, bump `GEOMETRY_VERSION` in `lake_geometry.py` first so paths change. 6. Record the build commit and counts from `manifest.v1.json` in the consolidation log.

## 7. Consuming it (Sector Ops: Lakes > `<lake>` > Info)

Fetch the index once per session, then the display geometry of the lake being viewed.

```ts
const BASE = 'https://storage.googleapis.com/sector-lake-registry';
let indexP: Promise<RegistryIndex> | undefined;
export const loadRegistry = () =>
  (indexP ??= fetch(`${BASE}/registry/lakes.v1.json`).then(r => {
    if (!r.ok) throw new Error(`registry ${r.status}`);
    return r.json();            // gzip is decoded by the browser
  }));

export async function loadLakeShore(lakeId: string) {
  const reg = await loadRegistry();
  const lake = reg.lakes.find(l => l.lakeId === lakeId);          // build a Map once if you do many lookups
  if (!lake?.geometry) return { lake, shore: null };               // MISSING: keep the placeholder card, show lake.geometryMissingReason
  const r = await fetch(lake.geometry.displayUrl);                  // immutable: served from cache after the first load
  if (!r.ok) throw new Error(`geometry ${r.status}`);
  return { lake, shore: await r.json() as GeoJSON.Feature<GeoJSON.Polygon | GeoJSON.MultiPolygon> };
}

// Mapbox GL / Leaflet:
map.addSource('lake', { type: 'geojson', data: shore });
map.fitBounds([[lake.bbox[0], lake.bbox[1]], [lake.bbox[2], lake.bbox[3]]], { padding: 24 });
// caption: `NHD water surface ${lake.geometry.sourceDate} · confidence ${lake.geometryConfidence.level}`
```

Rules for the consumer: show `geometryConfidence.level` and the first reason, and the `sourceDate` ("NHD water surface, 2021-05-26"), never present the polygon as the normal pool; if `geometry` is null or a fetch fails, keep the existing placeholder (no error state needed). Use `memberIds` to show one shoreline for the Kentucky Lake KY and TN entries. Do not cache the index in `localStorage` longer than its 5 minutes; do not derive the URL by hand (use `displayUrl`), so a v2 rollout needs no Ops release. Adding Ops origins requires the CORS edit in section 1.

**Follow-up in the Ops repo (not done here; this session does not touch it):** add `src/lib/lakeRegistry.ts` with the loader above and `RegistryIndex` / `RegistryLake` types matching section 2; render the display polygon in `LakeDetail.tsx` `InfoTab` → `MapCard` instead of the "Lake boundary (polygonStatus)" placeholder; show confidence and source date; stop reading `identity.polygonStatus` (no Engine code writes it); add the deployed Ops origin to `cors.json` if it differs from the four listed; optional: a small Playwright check that the first fetch carries `access-control-allow-origin`.

## 8. Why not RTDB, why not `/lakes`

* **RTDB:** it would work (Guntersville is 120 KB raw) but a listener on the lake node downloads the polygon on every subscription, RTDB is not CDN-cached and bandwidth is billed per GB; the 590 display polygons total 3.6 MB gzip (12.7 MB raw), the analysis set 5.5 MB gzip (19.9 MB raw). The Brain RTDB carries state; geometry is reference data with a version. No polygon is in any RTDB.
* **Customer `/lakes` route:** it is customer-serving, ETag-hashed as one 187 KB document and generated from a spreadsheet; geometry would change its version on every refresh and ship 1.5 MB to iOS. Adding fields or routes there is a separate decision and not part of this work. The index carries the same `lakeId` so a later `/lakes` summary (`geometryVersion`, `bbox`, `areaKm2`, `geometryConfidence`, `displayUrl`) is a mechanical copy.

## 9. Known limits and what stayed null

*Counts in this section and in sections 1 to 5 are as published on 2026-10-13T18:44Z (590 with geometry); the state after the 2026-10-13T20:20Z recovery is in section 10. Large and special waters: `LAKE_REGISTRY_LARGE_WATER_POLICY.md` (proposal).*

| Group | Lakes | Why | Next step |
|---|---|---|---|
| Large water, `held-large-water` | 16: Erie x4, Huron, Michigan x3, Ontario, Superior x3, Green Bay, Lake of the Woods, Great Salt Lake, Iliamna | NHD has the shorelines (25,738 to 82,002 km2 for the Great Lakes) but the Engine never outlined them and the display-boundary policy is pending (research M-geometry-05). Nothing was simplified blindly; ids and areas are in `geometryHeld`. | Decide the policy (coarse 250 m boundary, no satellite frame), then publish as v1 additions |
| No NHD lake/reservoir, `no-nhd` | 11: Koele ponds (Lanai), Nuuanu, Puu Loa, Waiakea, Waimaluhia (HI), Chickahominy Lake (VA); Chain O'Lakes (IL) and Lake Waiau (HI), whose research polygons were degenerate or in the wrong place; Conowingo Reservoir (MD), Ninigret Pond and Point Judith Pond (RI), whose only polygon is OSM-derived | Not mapped as FTYPE 390/436 in NHD near the coordinates (Chickahominy is FTYPE 466 swamp/marsh) | OSM (after a licence decision) or manual; allow 466 for tidal impoundments after review |
| `pending` | 4: Buckeye Lake OH, East Okoboji IA, Lake Shafer IN, Wilson Lake / Kaelepulu Pond HI | Each needs a fresh NHD search around its coordinates (the research polygon was degenerate, misplaced or OSM-derived) and the spatial query of the USGS NHD REST service returned 502/504 for the whole build window (attribute-only queries answered) | Re-run `build_geometry.py` when the service recovers (the cache is reused; only these 4 query); it adds v1 objects and refreshes the index |

* The OSM-derived Engine polygons with no NHD corroboration (Conowingo, Ninigret Pond, Point Judith Pond, and East Okoboji if NHD also fails) are **withheld** from the public bucket (`geometryWithheld`): OSM is ODbL (share-alike) and the research flagged a licence review. Lakes with an OSM-sourced Engine polygon that overlaps an NHD water body (Fox Lake IL, Hiwassee, Lake Hudson, Manasquan, Stonewall Jackson, Yellow Creek and others) use the NHD shape only.
* Great Lakes entries share one NHD water body but each directory id would be its own lake record; `memberIds` is not populated for held lakes.
* 40 lakes are `identity-risk` and 125 `off-water` by directory coordinate (research M-geometry-03): the geometry is a real NHD shoreline but the registry coordinate may be wrong; do not use `location` to place a marker when `pointFlag` is not `ok`; use `labelPoint`.
* NHD vintages differ per lake (2001 to 2023); drought-era features understate the pool (Hartwell is dated 2013).
* GSW (30 m) and HydroLAKES are validators only; no GSW or HydroLAKES geometry is published.

## 10. Amendment log (additive; contract semantics unchanged)

### 2026-10-13T20:20:54Z — recovery of the 4 `pending` lakes (index `generatedAt`; branch `feat/lake-fleet-geometry`)

State recomputed from the bucket before and after (all 1,180 / 1,184 geometry objects re-read over HTTPS; sha256, validity, closed rings, counter-clockwise exteriors, area against the index, all checked; 0 problems):

| | Before (verified) | After |
|---|---|---|
| Lakes in the index | 621 | 621 |
| With geometry | 590 | **592** |
| `geometry: null` | 31 (16 held-large-water, 11 no-nhd, 4 pending) | **29** (16 held-large-water, 13 no-nhd, 0 pending) |
| HIGH / MEDIUM / LOW / MISSING | 404 / 142 / 44 / 31 | **404 / 144 / 44 / 29** |
| `extentKind` | `shoreline-nhd-hr-union` x 590 | `shoreline-nhd-hr-union` x 592 |
| Withheld (OSM, ODbL) | 3 (Conowingo, Ninigret, Point Judith) | 4 (+ East Okoboji) |
| Objects in the bucket | 1,183 | 1,188 (+4 geometry, +1 archive of the previous index, index and manifest replaced in place) |

The 590-with-geometry / 621 claim held. Area sanity of the 592: 388 lakes with an NID reference (median ratio 0.97, 295 within 0.80 to 1.25, 20 under 0.5, 28 over 2.0 — the NID unit errors the contract describes), 149 with a USACE reference (median 0.967, 119 within range, 10 under 0.5, none over 2); 184 have neither. GNIS ids are still `null` (index-only refresh pending).

The four lakes:

| Lake | Result | Evidence |
|---|---|---|
| Buckeye Lake OH | **recovered**, MEDIUM | NHD `Crane Lake` (`152133995`, 11.158 km2, FDATE 2007-01-08), seed method `point-area-fallback`, analysis area 11.200 km2 = 0.989 of NID 11.33; directory point inside the polygon; display 404 / analysis 581 vertices; sha256 display `979eb8c3fb903d45ed040df1106ee610f298e49834ace78c36d43fec36ca7c3c`, analysis `0b8195a62248e754c67e0691b62c8861ea7349f6a5025a5e9fcedc43a9a0aa9f` |
| Wilson Lake / Kaelepulu Pond HI | **recovered**, MEDIUM | NHD `Kaʻelepulu Pond` (`32648665`, 0.331 km2, FDATE 2021-12-29), method `point-name-fallback`, 0.334 km2, directory point inside; display and analysis 40 vertices; sha256 display `78d2e2bab9dd31e5ad4b7d1d82b2e8b2679cf386e5b404ec157fc8670768168c`, analysis `f068b78fb92ace1b535aba1b39b4086d175e24029001f8cca83441962ef1d9a6`. This was **not** a transient error: the query succeeded in the original window, but `norm_name` split the Hawaiian okina into two tokens, so the pond never matched. Fixed in `lake_geometry.norm_name` (okina dropped, diacritics folded; ASCII apostrophes unchanged) |
| Lake Shafer IN | **not recoverable from NHD waterbodies**; now `no-nhd` | The attribute and geometry queries answered (HTTP 200, 0.4 to 1.2 s). The only FTYPE 390/436 water within the search window is Lake Freeman (6.35 km2, already published). NHDArea (layer 9) holds a 5.55 km2 FTYPE 336 (CanalDitch) polygon `155353019`, 3 parts spanning lat 40.78 to 41.08 (the river), directory point 239 m outside it: a river-reach polygon, not a lake outline. Not published |
| East Okoboji IA | **not recoverable from NHD waterbodies**; now `no-nhd`, OSM polygon withheld | HTTP 200. Nearest unnamed waterbody `132544104` (25.15 km2, the West Okoboji chain, already the source of West Okoboji) is 1,340 m from the directory point (allowance 788 m). NHDArea `132549700` is a 11.03 km2 FTYPE 460 (StreamRiver) polygon with 117 holes spanning lon -96.07 to -95.04: the Little Sioux River, point 9,130 m away. Not published |

Retrieval of the 4 originally failed because the USGS NHD service returned 502/504 for spatial queries during the first build; on 2026-10-13 about 20:10 UTC all 13 requests (paced at 4 s, UA `Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data)`) answered HTTP 200 on the first attempt (0.3 to 20.3 s). Request log: `Sector_Research_Data/lake-brain/geometry/recovery-2026-10-13/requests.log.jsonl` (outside Git).

Publication (all by `gcloud storage`, project `sector-9393c`):

1. The previous index was copied byte-identically (md5 `7nLSNXQrrDaJP0QGFbfk+g==`) to `registry/archive/lakes.v1.gen1791917397611653.json` (`--no-clobber`) so it stays readable.
2. Four objects were added with `--no-clobber`: `lakes/Buckeye_Lake_OH/` and `lakes/Wilson_Lake_Kaelepulu_Pond_HI/`, each `geometry.v1.display` and `geometry.v1.analysis` (`geojson.gz`, same headers as every other object).
3. `registry/lakes.v1.json` replaced with `--if-generation-match=1791917397611653` (new generation `1791922998882997`, 224,905 bytes stored; sha256 of the uncompressed index `8ae465ab2e39ca78df1b3b37187bb3caba61817320408771bc6803c21132b18d`), and `registry/manifest.v1.json` regenerated with updated counts and an `amendments` record. `README.txt` unchanged.
4. Verified: the generation list of the other 1,181 pre-existing objects is unchanged, the 617 other index entries are equal to the previous entries, the 590 previously published objects keep their sha256 (anonymous HTTPS re-read of all 1,184 objects), and `verify_upload.py` passes for the two new lakes and Guntersville (CORS, headers, sha256, area).

Tooling added in `jobs/lake-geometry/`: `merge_registry.py` (merges a `build_geometry.py --only` build into the live index; refuses any change to a published lake, any sha change, any target that shares an NHD feature with another lake; stages only the new objects), `norm_name` fix, 12 new tests (22 -> 34).

**Side effect to note:** the okina fix also makes **Nuuanu Reservoir HI** match NHD `Nuʻuanu Reservoir Number Four` (0.223 km2, `point-name-fallback`, MEDIUM, directory point 1,341 m off the shoreline, NID ratio 2.25, 28 vertices) in a full offline rebuild. It was **not published** (outside the four lakes) and needs a human check before any full rebuild is uploaded: use `merge_registry.py` for index changes, not `build_geometry.py --upload`.
