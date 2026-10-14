# Lake Brain coordinate / identity review protocol (fleet-readiness work package C1)

Status: pack built 2026-10-13 (pack id `LBC-2026-10-13-042093aaf3`). **Nothing is applied.** No directory coordinate, registry object, binding, lifecycle
status or `REVIEWED` marker is changed by the pack builder, by the review form, or by the ingest tool. Applying accepted coordinates is a separate,
reviewed change (section 8).

Purpose: the binding review (`LAKE_BRAIN_BINDING_REVIEW_PROTOCOL.md`) held back every otherwise-eligible lake whose directory pin is flagged
`identity_risk` or `off_water` (58 lakes, "HELD - coordinate review pending"). The geometry audit flags 169 directory pins in all (43 `identity_risk`,
126 `off_water`). This protocol turns those into one human-friendly review with a proposed correction and the evidence for it, so Michael can settle
them in one sitting instead of hunting for each lake on a map. Ambiguous identity is never decided by code: it is FLAG with the alternatives shown.

Code (all in `jobs/lake-brain/review/`):
`build_coordinate_review_pack.py` (builder), `coord_evidence.py` (evidence and recommendation rules, pure), `coord_geo.py` (pure-Python geometry),
`coord_fetch.py` (cached read-only fetches), `prep_hydrolakes_neighbours.py` (offline neighbour scan prep, needs the geometry research venv),
`coordinate_review_template.html` (the form), `ingest_coordinate_review.py` (ingest), `validate_coordinate_rules.py` (synthetic controls), tests in
`tests/test_coordinate_pack.py` and `tests/test_coordinate_ingest.py`.
Pack output (not in Git; public-derived data only): `~/Desktop/Sector Handoffs/Sector Engine/Lake Brain Coordinate Review/`
(`coordinate_review.html`, `coordinate_review_pack.csv`, `pack_manifest.json`, `START HERE - README.md`).

## 1. Population

| Source | Lakes |
|---|---|
| `geometry/lake_geometry_flags.csv` `point_flag` = `identity_risk` | 43 |
| same file, `point_flag` = `off_water` | 126 |
| live registry `pointFlag` off-water / identity-risk but not flagged above (Dale Hollow Lake TN, Grand Lake CO: the registry's union polygon moved) | 2 |
| **Pack** | **171** |

Relation to the binding review: the 58 coordinate-held lakes (`held_lakes.json` `coordinateFlagged`) are all inside the 169. 83 of the 171 lakes have a
candidate binding in the research table `binding2/verified_v2_full.csv` (any status except NONE); 58 of those are the held ones.
Registry state at build time (`registry/lakes.v1.json`, generated 2026-10-13T18:44:34Z, sha256 `801c0d27...`): 4 of the 171 have `geometry: null`
(Lake Waiau HI, Wilson Lake / Kaelepulu Pond HI, East Okoboji IA, Lake Shafer IN), so the pack reports **NO_GEOMETRY** for them and never invents a proposal.

## 2. Inputs (all read-only; the first two are the "live" ones)

* Registry index and each lake's `geometry.v1.analysis.geojson.gz` from the public bucket `gs://sector-lake-registry` (HTTPS GET, cached).
* Research data (outside Git, `Sector_Research_Data/lake-brain/`): `geometry/lake_geometry_flags.csv` (audit flag, NHD/OSM/USACE names), `directory_lakes_2026-10-13.json`
  (operator), `binding2/verified_v2_full.csv` + `binding/candidates_all.csv` + `binding2/cand/*.jsonl` (candidate bindings and station coordinates),
  `context/nid/nid_v1_subset.json` (National Inventory of Dams: dam name and location), `geometry/hydrolakes` (HydroLAKES v10 outlines, lakes of 10 ha and up,
  through `prep_hydrolakes_neighbours.py`, no network).
* The USGS NHD ArcGIS service was tried for the neighbour scan and dropped: it timed out or stalled for 60 s per request from this network (504). The code path
  remains behind `--with-nhd` (one request at a time, cached, failures not cached). Every input file's sha256 is recorded in `pack_manifest.json`.
* User-Agent: `Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data)`, plus `SECTOR_CONTACT` from the environment when set. No personal mailbox.
  **Michael still has to supply a real role mailbox for it.**

## 3. Rules (written before the first full run; two later tightenings are listed in 3.4)

### 3.1 Geometry class (pin against the canonical registry polygon)

`allowed = max(3000 m, 3 x rounding tolerance, 600 m x sqrt(area km2))` (same rule as the registry `pointFlag`; tolerance = max(300 m, 0.71 x 111 km x 10^-decimals), at least 1 decimal).

| Class | Meaning | Pack |
|---|---|---|
| `NO_GEOMETRY` | the registry has no polygon | 4 |
| `IN_POLYGON` | pin is inside | 1 |
| `OFF_WATER_NEAR` | outside by no more than `allowed` | 125 |
| `OFF_WATER_FAR` | outside by more than `allowed` (identity risk) | 41 |

### 3.2 Evidence

* **Identity signals** (positive): `name` (registry alias / NHD / USACE / OSM / HydroLAKES name matches the directory name, token overlap >= 0.5), `area` (NID or USACE pool
  area within 0.80 to 1.25 of the polygon area), `dam` (the lake's NID dam is within 2 km of the polygon), `binding` (a candidate binding's gauge is within 3 km of the
  polygon), `osm` (registry says OSM corroborates the polygon).
* **Contradictions** (any one blocks PASS): name differs; pool areas all outside 0.5 to 2.0; NID dam more than 5 km from the polygon; binding gauge more than 5 km from the
  polygon; polygon confidence LOW for a reason other than the point distance; a binding whose target the correction changes; the neighbour scan could not be read; and
  a **competing water**:
  a different water within about 6 km that carries the lake's name, a different water (or Sector directory lake) the pin sits inside, or, for an off-water pin, a different
  named / 1 km2+ / directory lake that is **nearer to the pin than the canonical outline**. Outlines that coincide with or adjoin the canonical outline (>= 40 % of their
  vertices inside or within 150 m of it) are the same water and are not competitors.
* The scan of other waters near the pin: HydroLAKES polygons within about 6.5 km plus every other Sector directory lake whose outline is within 6 km (the registry's own
  geometry). Alternatives are listed on the card with name, size, distance and source.

### 3.3 Recommendation (deterministic; PASS is never a decision)

| Class | PASS when | otherwise |
|---|---|---|
| `NO_GEOMETRY` | never | FLAG |
| `IN_POLYGON` | no contradiction | FLAG |
| `OFF_WATER_NEAR` | no contradiction, a safe proposal exists, enough signals (1 if the move is <= max(1000 m, tolerance), else 2) and (the name signal or >= 3 signals) | FLAG |
| `OFF_WATER_FAR` | no contradiction, pin within 15 km of the polygon, name signal, >= 3 signals and (dam or binding signal) | FLAG |

Identity ambiguity (competing water, weak evidence, far pin) is always FLAG. Each card carries a one-sentence why.

### 3.4 Changes made after seeing results (disclosed)

1. `OFF_WATER_FAR` never PASS beyond 15 km (added after the first full run showed PASS rows at 27 km). Can only turn PASS into FLAG.
2. "A different lake is nearer to the pin than the canonical outline" added as a competing-water test after control A (section 7) showed that 14 of 56 transplanted wrong-lake pins were
   wrongly PASS. Can only turn PASS into FLAG. Control A is therefore **in-sample** for this rule (0 of 56 afterwards is not independent evidence; section 7 gives the partly held-out set).
3. A data bug was fixed (HydroLAKES field order in the prep script gave type codes as areas); the pack was rebuilt afterwards. Counts through the iterations: 127 PASS / 44 FLAG (first run), 96 / 75
   (with the nearer-lake test, wrong areas), **114 / 57 (final)**.

## 4. Proposed coordinate

* `IN_POLYGON`: keep the pin.
* `OFF_WATER_NEAR`: the nearest point of the canonical water to the pin, probed from the nearest shore point (24 directions, radii 15 to 500 m) and required to be inside
  the polygon with at least 15 m of clearance from every shore (at least 6 m in narrow arms), rounded to 5 decimals and re-verified inside after rounding.
* `OFF_WATER_FAR`: the registry `labelPoint` (always inside the water); the nearest-water point is shown as the alternative.
* Never proposed when no point can be verified inside the polygon (Garrisons Lake DE: 0.33 km2 and narrow) and for the 4 NO_GEOMETRY lakes. **5 lakes have no proposal, all FLAG.**
* The card also shows the "middle of the lake" (label point) when it is more than 1.5 km from the pin, because on a long reservoir the nearest water to a dam-side pin is not the lake's centre.

## 5. Provider / binding implication (per candidate binding of the lake)

Station coordinates come from the research candidate files. Codes: `NO_BINDING` (none), `UNCHANGED_ON_WATER` (gauge within 3 km of the canonical water: the correction does not
change which lake it points at), `AMBIGUOUS` (3 to 5 km), `AT_RISK` (more than 5 km from the canonical water: may be another lake's gauge or the polygon is wrong; re-review the binding),
`UNVERIFIED` (no station coordinates: never assumed fine). `changes` = whether the gauge was near the old pin but not near the new water, or the reverse.
Pack result: 83 lakes with a candidate binding; 77 `UNCHANGED_ON_WATER`, 5 `AT_RISK` (Weiss AL, East Lake Tohopekaliga FL, Salamonie Lake IN, Mark Twain Lake MO, East Lynn Lake WV), 1 `UNVERIFIED` (Lake Shafer IN); 0 bindings whose target changes.
A binding is never altered or promoted by this review; a held lake stays held until the lead applies the coordinates and a binding re-review (section 8).

## 6. Pack, form and export

* `coordinate_review.html`: one self-contained file, no network. One card per lake: pin, canonical water (name, area, confidence, GNIS/NHD id), in-polygon, distance, proposed point with map links (OpenStreetMap, satellite),
  other waters near the pin, names / areas / NID dam / operator evidence, signals for and concerns against, binding effect, the computer's PASS / FLAG and why. Buttons: **Accept proposed**, **Keep current**,
  **Needs more info** + a note. Progress saved in the browser; filters (FLAG, PASS, undecided, binding needs a second look); sort by biggest move; a "mark every untouched PASS card Accept proposed" button
  (fills only undecided cards, asks to confirm). Accept is disabled when there is no proposal.
* Export columns: `pack_id, lake_id, lake_name, state, computer_recommendation, current_lat, current_lon, proposed_lat, proposed_lon, row_digest, decision, notes, decided_at_utc, reviewer, exported_at_utc`.
  `row_digest` = first 16 hex of sha256 over lake id, both coordinates, the recommendation and the binding codes.
* `coordinate_review_pack.csv`: one row per lake with all evidence columns; `pack_manifest.json`: ids, coordinates, digests, counts and input fingerprints.

## 7. Ingest

`python3 jobs/lake-brain/review/ingest_coordinate_review.py --review-csv <export.csv> [--pack-dir <pack>] [--write]` (dry run by default; `--write` required to write anything).
It refuses (exit 2, nothing written) on: wrong pack id, unknown lake id, duplicate id, a lake of the pack without a row, a blank / `PENDING` / invalid decision, a changed current or proposed
coordinate (tolerance 1e-6), a changed recommendation or digest, or `ACCEPT_PROPOSED` for a lake the pack gave no proposal. On success `--write` writes only
`jobs/lake-brain/data/coordinate_review_decisions.json` (schema `lake-brain-coordinate-review-decisions/v1`, `applied: false`): per-lake decision, accepted coordinate (only for `ACCEPT_PROPOSED`),
`overridesFlag`, bindings affected, `bindingNeedsRereview`, notes, plus the counts and how often Michael accepted PASS rows versus FLAG rows (the first calibration of the rules).

## 8. What happens after the review (not done here)

1. The lead reads `coordinate_review_decisions.json` and prepares a separate change to the directory pins for the `ACCEPT_PROPOSED` lakes (a new registry index entry is index-only; the geometry objects are unchanged). `NEEDS_INFO` lakes stay as they are and go back to research.
2. For the 58 held binding lakes: accepted coordinates and `bindingNeedsRereview` decide whether a lake may re-enter the binding review. The hold lists (`held_lakes.py`, `held_lakes.json`) are not edited by this tool.
3. No lifecycle status, REVIEWED marker or customer surface is touched by any of this.

## 9. How reliable are the recommendations (honest statement)

* **Pack result (final):** 171 lakes, **114 PASS, 57 FLAG** (OFF_WATER_NEAR 98 PASS / 27 FLAG; OFF_WATER_FAR 15 PASS / 26 FLAG; NO_GEOMETRY 0 / 4; IN_POLYGON 1 / 0). By original audit flag:
  off_water 96 PASS / 30 FLAG, identity_risk 16 PASS / 27 FLAG, the 2 registry-only lakes PASS. Of the 58 binding-held lakes: 46 PASS, 12 FLAG.
* **There are no human labels yet.** Nothing in this pack has been checked against Michael's answers. The ingest tool records the first calibration (PASS rows accepted, FLAG rows accepted).
* What is solid: the point-in-polygon result, the distance to the shore, and "the proposed point is inside the canonical polygon" (verified for every proposal, tested). What is only as good as its input: the
  canonical polygon itself (registry confidence: 90 HIGH, 34 MEDIUM, 41 LOW, 4 MISSING of the 169 research lakes; LOW polygons carry a concern and are FLAG when the reason is not the point distance).
  What is heuristic and unvalidated: the identity signals. The `name` signal in particular is often derived from the same NHD match that produced the polygon, so it is not independent of the polygon.
* **Synthetic controls** (`validate_coordinate_rules.py`, only lakes whose pin is already fine and whose polygon confidence is HIGH):
  A (wrong-lake pin: lake L's pin replaced by the real pin of another directory lake 3 to 20 km away, at least 1.5 km off L's water): 56 cases. **Before** the nearer-lake test 14 of 56 were wrongly PASS (25 %);
  after it 0 of 56, but that control was used to design the test (in-sample). A broader set of 61 transplants (every neighbour pair, 5 extra) also gave 0 wrongly PASS. n is small and the control is partly built from the same
  evidence the rule uses, so read it as "no obvious hole in the wrong-lake case", not as a false-PASS rate.
  B (the pin moved onto the lake's own NID dam, 400 m to 5 km off the water): 14 cases, 12 PASS (86 %), every proposal on the lake's own water, but the proposal is a median 6.0 km (90th percentile 11.6 km) from the original good pin,
  because the nearest water to a dam is the dam end of the lake, not its middle. Hence the "middle of the lake" line on the card.
* Expected behaviour on the pack: PASS means "every available signal agrees and no competing lake was found"; the PASS rows with a move over 3 km
  (10 NEAR rows and the 15 FAR rows) deserve the most skim time; the median PASS move for NEAR rows is about 1.6 km. A FLAG row is not evidence of error. Primary reason on the 57 FLAG rows:
  30 competing / nearer lake (11 of them an unnamed water of 1 km2 or more), 13 NID/USACE pool area off by more than 2x, 6 low-confidence polygon, 4 no outline, 4 other (gauge far from the water, pin too far, no safe proposal).
  5 of the FLAG rows also have an `AT_RISK` binding.
* Known gaps: a same-named lake farther than 6 km from the pin is not scanned; HydroLAKES has no waters under 10 ha; the registry polygon can be a partial reservoir; USACE / NID names are only used when already in the research data;
  GNIS ids are mostly absent from the registry index (`gnisId` null in v1).

## 10. Rebuild and verify

```
# one-time offline prep (needs pyogrio + shapely; the geometry research venv has them)
<data>/geometry/venv/bin/python jobs/lake-brain/review/prep_hydrolakes_neighbours.py
# build (reads the public registry, caches under <data>/coords-review/; writes the pack folder)
python3 jobs/lake-brain/review/build_coordinate_review_pack.py --fetch
# controls and tests
python3 jobs/lake-brain/review/validate_coordinate_rules.py --fetch --pairs all --max 400
python3 -m pytest jobs/lake-brain/review -q
# ingest a returned review (dry run, then write)
python3 jobs/lake-brain/review/ingest_coordinate_review.py --review-csv <export.csv>
python3 jobs/lake-brain/review/ingest_coordinate_review.py --review-csv <export.csv> --write
```

Test counts: review suite 24 -> 72 (+48: geometry helpers, the five fixture classes, binding implication, builder outputs, HTML data block, ingest validation and tamper cases).

## 11. Boundaries

Read-only network access only (public registry bucket, optional NHD queries). No cloud mutation, no customer-service change, no `/lakes` change, no iOS/Android change, no customer RTDB access,
no lifecycle promotion, no REVIEWED marker, no `accepted_batch.json`, no edit of the binding review result, no rubric edit.
