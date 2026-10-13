# Lake Registry — Large and Special Waters: Policy Proposal

**Status:** PROPOSAL for Michael's decision (2026-10-13). Nothing here changes the live contract (`LAKE_REGISTRY_GEOMETRY_CONTRACT.md` v1) or the live bucket. **Branch:** `feat/lake-fleet-geometry`.
**Why this exists.** The registry holds 592 shorelines under one "reservoir-style" rule (NHD HR union, 50 m display and 25 m analysis variants, immutable objects). 16 directory entries were held as `geometry: null` / `held-large-water` because that rule was never decided for them (research M-geometry-05). They are not reservoirs: they are shared by several directory entries, cross national borders, hold tens of thousands of island vertices, or are much larger than anything a lake-detail card, a clarity frame or a shallow-water mask was designed for. This document recommends a treatment per water and lists what only Michael can decide.

All numbers below were recomputed on 2026-10-13 from the live bucket (`lakes.v1.json`, generation `1791922998882997`) and from the NHD responses cached for the registry build (server-side generalised to about 9 m). Scripts and raw outputs are outside Git in the session scratch; the method is stated per table.

---

## 1. Which waters are "large or special"

Found by area, directory class and geometry size in the live index.

| Group | Waters | How found |
|---|---|---|
| **Held (geometry null)** — 16 directory entries, 8 NHD water bodies | Superior (MI, MN, WI), Huron (MI), Michigan (IN, MI, WI), **Green Bay (WI)**, Erie (MI, NY, OH, PA), Ontario (NY), Great Salt Lake (UT), Lake of the Woods (MN), Iliamna (AK) | `geometryMissingStatus == held-large-water` (16 of 29 null lakes). 15 of the 16 have `classification.regime == MEGA` (class `X_mega`); Iliamna does not. |
| **Published, MEGA class** — 3 | Lake Pontchartrain LA (1,650 km2), Okeechobee FL (1,376), Lake Oahe SD (1,259; its ND twin is classed `reservoir`) | `regime == MEGA` with geometry. 18 lakes have `MEGA` in total (15 held + 3 published). |
| **Published, large by area** — 21 lakes at least 500 km2 (45 at least 250 km2) | Sakakawea, Oahe x2, Becharof, Red Lake, St. Clair, Champlain, Fort Peck, Salton Sea, Rainy, Teshekpuk, Toledo Bend, Naknek, Kentucky Lake x2, Mead, Winnebago, Mille Lacs, Powell, ... | by `areaKm2` |
| **Published, large by size on the wire** | Rainy Lake 120 KB display gzip (30,492 analysis vertices, 2,552 islands), Oahe 90 KB, Fort Peck 72 KB, Sakakawea 68 KB, Kentucky Lake 59 KB; 9 lakes above 50 KB, 1 above 100 KB | by `bytes.displayGzip` |
| **Published, variable or special water** | Salton Sea, Sevier Lake UT (dry lake bed, LOW), Pyramid, Walker, Mono, Malheur; tidal sounds Sabine, Calcasieu, Pontchartrain | judgement from the index; their NHD vintage and water level matter (`sourceDate`) |
| **Published but binational** | St. Clair (1,124 km2), Champlain (1,121), Rainy (908), Koocanusa, Memphremagog | by name; the first three have areas close to the whole-lake figures usually quoted (not verified here), i.e. the NHD polygon includes the Canadian part |

**Verdict for the published groups:** no change recommended. The largest published display object is 120 KB gzip; median 2.1 KB; total display set 3.62 MB. They already satisfy the contract and nothing about them needs a new `extentKind`. Their only requirement is a consumer rule (section 6).

---

## 2. Facts about the eight held water bodies

Source: the NHD HR polygon cached for the registry build. "Variants" were produced with the registry's own functions (`lake_geometry.simplify_metric`, `finalize_degrees`, `feature_bytes`, `gzip_bytes`), i.e. exactly what the builder would write. Area change is against the source polygon.

| Water (directory entries) | NHD area km2 / NHD name / FDATE | Source polygon | Registry-standard **50 m display** | **250 m** | **250 m, islands under 1 km2 dropped** | Notes |
|---|---|---|---|---|---|---|
| Superior (MI, MN, WI) | 82,002 / Lake Superior / 2019-09-27 | 78,153 vertices, 2,360 holes, valid | 22,587 vertices, **135 KB gz**, 2,211 holes | 11,939 v, 70 KB | 3,179 v, **22 KB** (61 holes), area +0.07 % | MI directory point is 141 m outside the polygon |
| Huron (MI) | 59,060 / Lake Huron / 2020-04-21 | **307,163 vertices, 23,153 holes, 7 parts, invalid (repaired)** | 105,953 v, **557 KB gz** (2.2 MB raw), 17,342 holes | 77,696 v, 395 KB | 7,180 v, **47 KB** (97 holes), +0.39 % | 4,432 km2 of island holes (mostly Georgian Bay and the North Channel, by location) |
| Michigan (IN, MI, WI) **and Green Bay (WI)** | 57,857 / Lake Michigan / 2019-08-28 | 26,584 v, 167 holes, invalid (repaired) | 6,687 v, 43 KB | 2,139 v, 15 KB | 1,556 v, 11 KB | **Green Bay's directory point is inside this same NHD feature**: NHD does not split the bay |
| Erie (MI, NY, OH, PA) | 25,738 / Lake Erie / 2020-01-13 | 36,917 v, 1,432 holes, invalid (repaired) | 12,809 v, 73 KB | 8,143 v, 46 KB | 2,336 v, **14 KB** (13 holes) | 4 directory entries, one water |
| Ontario (NY) | 18,846 / **"Lake America"** / 2026-08-27 | 22,038 v, 248 holes, invalid (repaired) | 5,587 v, 35 KB | 2,085 v, 13 KB | 1,222 v, 8 KB | NHD names it "Lake America" (data quirk) |
| Great Salt Lake (UT) | 3,389 / Great Salt Lake / 2021-06-15 | 5,235 v, 84 holes, valid | 1,659 v, 10 KB | 727 v, 5 KB | 398 v, 3 KB | level is highly variable (section 4) |
| Iliamna (AK) | 2,649 / Iliamna Lake / 2020-10-04 | 15,125 v, 371 holes, valid | 4,487 v, 27 KB | 2,192 v, 13 KB | 682 v, 5 KB | larger than anything published, smaller on the wire than Sakakawea |
| Lake of the Woods (MN) | **1,234 / unnamed / 2014-08-26** | 3,456 v, 35 holes, valid | 990 v, 6 KB | 336 v, 2 KB | 208 v, 1.5 KB | **partial water body** (section 4) |

Reading the table:

* **Size is not the blocker.** Only Huron at the registry-standard 50 m is outside the existing range (557 KB against a published maximum of 120 KB), and only because of its islands. At 250 m with islands under 1 km2 removed, all eight fit in 1.5 to 47 KB; the five Great Lakes together are about 100 KB (the 12 directory entries about 213 KB if each keeps its own copy).
* **The blockers are meaning, not bytes:** one water serves several directory entries; the Great Lakes cross the border; Green Bay is not a separate NHD water; Lake of the Woods is a fragment; the Great Salt Lake has no stable shoreline; and the analysis consumers cannot use a whole Great Lake.
* Four of the five Great Lakes polygons are `is_valid == False` as delivered by NHD and are repaired (`make_valid`) by the builder; the repaired result is valid. A rebuild must keep that step.

---

## 3. Treatment options

| Code | Treatment | What it is |
|---|---|---|
| **A** | Whole-water geometry under the existing contract | Standard `shoreline-nhd-hr-union`, display 50 m + analysis 25 m objects, no new enum |
| **B** | Sector operational subset | A polygon for the part of the water Sector actually reports on (a bay, a basin, a state's waters). Needs a definition that does not exist in the registry |
| **C** | Tiled geometry | Vector tiles or a pre-tiled set (PMTiles / quad-keyed GeoJSON) so a client loads only the visible part |
| **D** | Separate `extentKind` | A display-only coarse outline with its own tolerance and rules, flagged so no analysis consumer takes it |
| **E** | No display polygon | Keep `geometry: null`, with a final, honest status |

C is not recommended for any water at this time: the largest recommended object is 47 KB, which a single GeoJSON fetch serves; tiling would add a build and a hosting path (and a new consumer code path in Ops) for no measured benefit. Revisit only if Michael wants islands-resolved Huron / Georgian Bay (557 KB at 50 m).

---

## 4. Recommendation per water

| Water | Recommended | Reason | Needs from Michael |
|---|---|---|---|
| **Superior, Huron, Michigan, Erie, Ontario** (12 directory entries) | **D** | Whole-lake outline for orientation only; coarse (250 m, islands at least 1 km2), display variant only. Area quoted from NHD `AREASQKM`, not from the simplified polygon. The published bytes are 8 to 47 KB per lake. No `analysis` object: shoreline length, shallow-water masks and clarity frames have no meaning at this scale: the clarity job sizes its memory from the lake's ground area (`MEM_PER_1000KM2_GB = 0.55`, `MEM_TILE_KM2 = 12,100`, task budget `MEM_BUDGET_GB = 14` in `jobs/lake-surface/daily.py`; Kentucky Lake at about 10,000 km2 was measured at 6.5 GB). By the same linear model Superior would need about 45 GB, Michigan and Huron about 32 GB, Erie 14 GB, Ontario 10 GB: Superior, Michigan and Huron cannot fit the task budget | yes: D vs B per entry (below) |
| **Per-state entries** (Erie MI/NY/OH/PA, Michigan IN/MI/WI, Superior MI/MN/WI) | **D now; B later if wanted** | The same polygon for each entry says "this is the lake", not "this is Ohio's Lake Erie". If the product thinks of these entries as state fisheries, the right object is a state-waters subset, which needs an external boundary source (Census TIGER water or NOAA maritime boundaries, EXTERNAL SOURCE) and a definition | **Decision 1** |
| **Green Bay (WI)** | **E (until B is defined)** | NHD has no separate bay: giving it the Lake Michigan polygon would draw 57,857 km2 for a water of roughly one-twentieth that size. A subset needs a defined cut line (Door Peninsula to Menominee?) that the data does not contain | **Decision 2** |
| **Lake of the Woods (MN)** | **E** (or A with `coverage: partial`) | The NHD feature is 1,234 km2 with an unnamed record and covers only part of the lake (bbox lon -95.33 to -94.68, lat 48.83 to 49.38). The other binational waters in the registry (Rainy 908 km2, St. Clair 1,124, Champlain 1,121) have areas close to the whole-lake figures usually quoted for them (not independently verified here), so this one looks like an exception, not a US-only convention. The whole lake is commonly given as roughly three to four times that figure (not verified here). Showing it as the lake would be wrong | **Decision 3**; a complete source is Canadian (NHN, EXTERNAL SOURCE / TERMS) or OSM (ODbL, TERMS) |
| **Great Salt Lake (UT)** | **A with a variability flag** (or E if it is not a product lake) | Small and simple: 10 KB at 50 m, fits the standard rule. But NHD's 2021-06-15 outline is one level of a lake whose area has swung widely; a stored shoreline will be visibly wrong in other years, and the two bays are divided by a causeway. Hypersaline: confirm it is a fishing water | **Decision 4** |
| **Iliamna (AK)** | **A (standard v1 addition)** | 27 KB display / 40 KB analysis fits the existing range (Sakakawea is 68 / 103 KB). It was held only by the builder's `LARGE_WATER_KM2 = 1000` rule when no Engine polygon existed. No new enum | none, once the rule is lifted for non-MEGA waters |
| **Published MEGA / large waters** (Pontchartrain, Okeechobee, Oahe, Sakakawea, Rainy, ...) | **A (no change)** | Already published and measured | none |

### 4.1 Rendering and consumer implications

| Consumer | Today | Effect of the recommendation |
|---|---|---|
| **Sector Ops map (Lakes > lake > Info card)** | No loader yet; contract section 7 follow-up (`lakeRegistry.ts`). Card draws `geometry.displayUrl` with Mapbox GL / Leaflet `fitBounds(bbox)` | D objects work unchanged with `displayUrl`. Huron at 50 m would be 2.2 MB of raw JSON in the browser: another reason for D. The card must show "NHD outline, simplified for display" and the NHD vintage |
| **Mobile (iOS, Android)** | The Swift profile holds only `identity.geometry.registryRef` + `lakeKey` (`LakeBindingTypes.swift`), never a polygon; the customer `/lakes` is untouched | No effect. If a mobile map ever loads the registry, D objects (8 to 47 KB) are acceptable; 50 m Huron (557 KB) would not be |
| **Depth brain / Vegetation brain** | Contract: the `analysis` variant is "for measurement: shoreline length, shallow-water and clarity masks, area" | They must treat a missing `analysisUrl` as "not measurable at this scale" and skip the lake. Proposal below makes that explicit. They must not measure D polygons |
| **Clarity (lake-surface job)** | Frame memory model grows 0.55 GB per 1,000 km2 plus a 12,100 km2 tile term; a lake without an analysis object is not framed (`satelliteSupported = false`, as the research recommended) | Great Lakes stay unframed, as the research section 8.4 intended |
| **Cache and bucket** | Objects immutable, `max-age` one year | D objects add about 100 KB for the five lakes (about 213 KB if duplicated for 12 entries); negligible |

---

## 5. Proposed contract additions (DRAFT; not applied)

These would be a `v1` additive amendment or, if Michael prefers, a documented `v1.1`. **The live contract semantics are unchanged by this file.**

1. **`geometry.extentKind` new values** (today only `shoreline-nhd-hr-union`; `lake_geometry.validate_entry` pins it, so the validator must change with the contract):
   * `shoreline-nhd-hr-coarse` — NHD HR water body, display-only: Douglas-Peucker 250 m, interior rings under 1 km2 removed, repaired, 5-decimal grid. Not an area measurement.
   * `operational-subset` — a Sector-defined part of a larger water (Green Bay, a state's waters). Requires the new `geometry.subsetOf` and `geometry.subsetDefinition`.
2. **Optional fields on `geometry`:** `analysisUrl: null` and `analysisWithheldReason` (string) when `extentKind` is `shoreline-nhd-hr-coarse`; `coverage: "whole-water" | "partial"`; `waterLevelVariable: true`; `transboundary: true`; `subsetOf: { nhdId, name }`; `subsetDefinition: { definedBy, definition, sourceUrl }`.
3. **`areaKm2` for D / partial objects:** the NHD `AREASQKM` of the source (not the simplified polygon); `geometry.areaDisplayKm2` is the simplified polygon's area.
4. **`geometryMissingStatus` new value** `no-display-policy` (replacing `held-large-water` for waters Michael decides not to draw, with the reason text kept). `held-large-water` stays valid for the current 16 until they are decided.
5. **Confidence:** D objects cap at MEDIUM (`reason`: "coarse display outline of a shared multi-state water"), because the independent checks (NID/USACE area, GSW share) do not apply.
6. **Consumer rules (all ship together with the enum):** a consumer that does not know an `extentKind` must treat the lake as geometry-present-but-unmeasurable (draw `displayUrl` if it exists, never measure); `analysisUrl` may be null; use `displayUrl` and `analysisUrl` as given, never construct them.
7. **Builder:** `LARGE_WATER_KM2` becomes a policy table keyed by NHD id (Superior, Huron, Michigan, Erie, Ontario -> `coarse`; Iliamna, Great Salt Lake -> standard; Green Bay and Lake of the Woods -> `no-display-policy`) instead of a size threshold, so a future large reservoir is not silently held and no future MEGA water is silently drawn. The per-state entries share one NHD id, so `memberIds` should group them (the contract says held lakes are not grouped today).

None of this is implemented. Estimated work after a decision: a table entry per water, one new variant function (tolerance and minimum island area parameters already exist as `lake_geometry.make_variant` arguments and `MIN_HOLE_M2`), schema and tests, a dry run, a new-objects-only publish (no existing object changes).

---

## 6. Consumer rule that already applies to published waters

The 21 lakes of at least 500 km2 render fine at their published size; the guidance is: fetch only `displayUrl` for the visible lake (never the analysis object on a map card), and expect up to 120 KB gzip (about 1 MB raw JSON for Rainy). A client that loads many lakes at once (a fleet map) should use `bbox` / `centroid` / `labelPoint` and fetch the polygon on demand.

---

## 7. What Michael must decide

| # | Decision | Options | Recommendation |
|---|---|---|---|
| 1 | Are the per-state Great Lakes entries (Erie x4, Michigan x3, Superior x3) fisheries by state or the whole lake shown under several names? | whole lake (D) now, state-waters subsets (B, needs boundary data) later | D now |
| 2 | Green Bay: a defined area, or no polygon | define the cut line (B) / E | E until a cut line is given |
| 3 | Lake of the Woods: publish the NHD fragment flagged `coverage: partial`, or hold | A-partial / E; a full outline needs a Canadian or ODbL source (licence decision) | E |
| 4 | Great Salt Lake: is it a product lake; if yes, accept a dated outline with `waterLevelVariable` | A-flagged / E | A-flagged if it stays in the product |
| 5 | Approve the contract additions in section 5 (or a smaller subset), and whether they ship as `v1` additive or `v1.1` | | additive `v1`, enum changes only after the Ops loader exists (no consumer today, so no break) |
| 6 | Approve D tolerance and island rule (250 m, islands at least 1 km2) | 250 m / 500 m / 1 km, island cut 0.25 / 1 / 10 km2 | 250 m, 1 km2 (area within 0.4 % on each of the five Great Lakes) |
| 7 | East Okoboji IA and Lake Shafer IN (not large waters, same cause class: NHD models them as river-area polygons, see the contract amendment): source decision for those two | OSM (ODbL), NHDArea FTYPE 336/460 after a shape review, 3DHP, manual | review of the candidate shapes; they are not clean lake outlines today |

Blocker categories: DECISION (1 to 6), TERMS (3, OSM / Canadian data), EXTERNAL SOURCE (state boundaries for B, Canadian hydrography for Lake of the Woods).
