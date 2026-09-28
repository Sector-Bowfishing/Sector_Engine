# Clarity Fusion Stage 4: the Current Clarity Engine

2026-09-28. Engine: `Sector_Engine-fusion`, branch `feat/clarity-current-estimate`. iOS: `Sector-mapbox`, branch `feat/clarity-current-estimate`. Both are **uncommitted**.

**Production is unchanged.**
- **Engine:** the new routes answer only with `SECTOR_CURRENT_CLARITY_ROUTES=1`, and nothing was deployed.
- **Jobs:** no job was redeployed.
- **iOS:** the new layer, reports and the Huntability path are Debug-only flags, off by default.
- **Scoring:** Huntability and Sector Intelligence scoring were not switched. This stage stops before that.

Everything below was run on Guntersville against a **local mirror** of the bucket:
- The live bucket holds one published scene (Sep 20), with no per-cell files and no per-arm anchors.
- The mirror adds the ten other usable August–September passes. They were rebuilt from their pass cells with the production fill (§4).
- The hourly rain record was backfilled locally to Aug 13 by the hourly job's own code.

The live hydrology is real. On Sep 28, Town Creek's USGS gauge (03572900) peaked at 48.5× its flow at the Sep 20 pass, with 1.18 in on its drainage since. So the review shows genuine major-change water.

---

## 0. Hardening (done before Stage 4)

| Item | State |
|---|---|
| Stage 3A hardening, history-aware anchor selector, Linux smoke test | committed and pushed (`abfbc9b`, PR Sector-Bowfishing/Sector_Engine#13) |
| Exact deployed production SHA | `be1d893` = `sector-engine-00044-b6m`, tag `deployed/sector-engine-00044-b6m` pushed |
| Tributary Influence through-water fix | committed and pushed (`fce09747`, in PR Sector-Bowfishing/iOS_Sector#213) |
| Linux smoke test, mandatory | kept in `deploy.sh`, and now also checks the four Current Clarity routes (five checks) |
| Engine suite before Stage 4 | 138/138 |
| iOS suite before Stage 4 | 722 run, 721 passed, 1 skipped (pre-existing), 0 failed |

Stage 3B's artefacts are untouched and change no production value.

## 1. The canonical type

`Sources/SectorEngine/Clarity/CurrentClarity.swift`, schema `current-clarity-v1`. There is **one type** for the map, the tap card and the API.

| Field | Meaning |
|---|---|
| `lakeId`, `lat`, `lon`, `supported` | `supported` is false off the water, outside a lake with a graph, or with no scene |
| `region` | `{kind: arm/mainStem, id, name, zone, zoneName}`. `zone` is the Stage 3A zone, the de-identified unit (§7) |
| `evidenceLevel` | A `inSitu` · B `directSatellite` · C `nearbySatellite` · D `stableHistorical` · E `changedHistorical` · F `none` (§2) |
| `magnitudeSupported` | true only for A–D |
| `centralFt`, `lowFt`, `highFt` | secchi-power-v1 and its 80% range. **nil for E and F** |
| `category` | `< 1`, `1–2`, `2–4`, `4–6`, `6+ ft` (the report bins), from `centralFt` |
| `confidence` | high / moderate / low / none. Ordinal, not a probability (§4) |
| `authority` | this cell's: min(region's hydrologic cap, the cell's evidence cap) |
| `primarySource`, `method` | `satelliteObserved` / `satelliteFilled` / `satelliteGrassBed` / `inSituGauge` / `none`. `method` is one of `satelliteDerivedSecchi`, `instrumentMeasured`, `userReportedNightVisibility` or `userReportedDayVisibility` |
| `composition[]` | every piece of evidence considered, with its role: `answer`, `context`, `notCurrent` or `rejected` |
| `observation` | scene date and time, platform, direct/filled/grass, fill reason, through-water distance to the observed evidence, age |
| `lastSupported` | E only: the scene's own number and range, unchanged, and why it isn't current |
| `hydrologicChange` | runoff state, expected direction, `magnitude: "uncalibrated"`, rain since observation (nil = unknown, never 0), flow ratio, flow provenance, the authority cap it leaves |
| `catchmentCompleteness`, `flowProvenance` | `measuredUSGS`, `modeledNWM`, `measuredTVARelease` or `unavailable` |
| `legacyEnvironmentalEstimate` | the old `rain-decay-v0` number, labelled "Legacy environmental estimate…, not an observation". Only with `?legacy=1`, and **never** the answer |
| `display` | the tap card's words, written once in the engine: `valueText`, `rangeText`, `confidenceText`, `sourceText`, `evidenceText`, `notes[]` |
| `limitations[]` | |

### Endpoints

All four are behind `SECTOR_CURRENT_CLARITY_ROUTES=1`; `CurrentClarityAPI.swift` has the details.

| Route | Returns |
|---|---|
| `GET /clarity/current?lake&lat&lon[&legacy=1]` | one coordinate's estimate |
| `GET /clarity/current/lake?lake` | the legend, the scenes in use, each region's state, and **the outcome table**: for every region and every kind of cell, the resolver's own decision (level, confidence, magnitudeSupported) |
| `GET /clarity/current/cells?lake` | the composite: 415,214 water cells, each with its value, code, distance, region, zone and scene. 2.9 MB, ETagged |
| `GET /clarity/current/change?lake&region&since` | a region's hydrologic change since a moment, used for a report's freshness. No coordinate is sent |

**Map = tap = API, by construction:**
- The map colours each cell from the composite and takes its confidence from the table.
- The table is `CurrentClarityResolver.outcome()`, the same function the point API runs.
- The phone reproduces the engine's conversion to 1e-5 ft on a shared golden list. The same list is asserted in both repos.

## 2. The evidence hierarchy (`CurrentClarityResolver`)

**Ranked, never averaged.** The best level that holds answers; the rest go into `composition` as context.

| Level | When | Magnitude |
|---|---|---|
| **A** inSitu | a turbidity sensor in the **same Stage 3A zone**, read in the last 6 h | yes, `instrumentMeasured` |
| **B** directSatellite | the cell was read on its region's chosen scene, scene ≤ 72 h old, drainage stable or minor change | yes |
| **C** nearbySatellite | the cell was filled through the water from readings ≤ 5 km away, scene ≤ 72 h old | yes, with a wider range |
| **D** stableHistorical | B or C with a scene > 72 h old, kept because the drainage hasn't changed | yes |
| **E** changedHistorical | the region's runoff state is moderate, recovering or major since the scene | **no**: `lastSupported` holds the scene's number, unchanged |
| **F** none | no value, or the nearest reading is > 5 km through the water, or there's no scene | **no** |

**The legacy estimate never answers.** The 4.0 ft × rain-decay path survives only in `/conditions` (§12). A regression test pins the only two engine files that build it (`ClarityFactor.swift`, `ConditionsConfig.swift`); a new consumer fails the build.

## 3. Hydrology changes authority, not feet

The hydrologic cap is Stage 2's rule set, unchanged. Stage 3B validated it out of sample, where the authority ladder held at 78/65/61/55%.

| Runoff since the scene | Cap |
|---|---|
| stable (< 0.10 in on the drainage, flow < 1.5×) | high |
| minor change | moderate |
| unknown (no record) | moderate |
| moderate runoff (≥ 0.50 in, or flow ≥ 2×) | low → **E** |
| recovering | low → **E** |
| major runoff (≥ 1.00 in, or measured flow ≥ 5×) | none → **E** |

- A modeled-NWM rise alone is capped at moderate runoff, so it is never presented as measured. Its wording reads "modeled by the National Water Model, not measured".
- The relative-NWM signal Stage 3B replicated is used only here, as evidence of change.
- **No path subtracts or adds feet**; a test asserts E's `lastSupported` equals the stable number exactly.

## 4. Per-cell authority, and whether confidence is calibrated

```
authority(cell)  = min(hydrologic cap of its region, evidence cap of the cell)
confidence(cell) = min(authority, record cap)
```

- **Evidence cap:** direct → high; filled ≤ 500 m → moderate; filled ≤ 5 km → low; grass bed → at most low; beyond 5 km or no path → none.
- **Record cap:** partial catchment → moderate; no catchment → low; no flow record → moderate.

**Each region stands on its own chosen scene.** The scene is picked with `ClarityHistory.selectAnchor`: the newest one that reads the region at least moderately. A region no scene reads falls back to the newest scene's fill and measures the change from it. On Sep 28 that gave six scenes in use: Sep 5, 10, 13, 17, 18 and 20.

Two cells of one arm share its hydrology but not its evidence. On Sep 28 in the main stem:
- a read cell was **D, moderate**, ~4.6 ft (likely 2.0–15.2);
- a cell filled from 2 km away was **D, low**, ~3.7 ft (likely 1.6–12.4).

### The historical replay (item 14)

`ClarityReplay --current` runs every read pass as a target, as of one minute before it, with no look-ahead:
- Each region picks its scene among the passes the daily job would have published in the previous 45 days.
- The regions are built by `CurrentClarityRegions.build`, the live code.
- Every fifth observed cell is resolved by the production resolver and scored against what the target read.
- **The inputs are rebuilds:** 366 scenes rebuilt from 2020–2026 pass cells with `fill_lake.fill_clarity`. They skip `build_clarity`'s grass-under-cloud and grass-to-bank steps, so they are close to, but not identical with, what the job would have published.
- **The rules were fixed before the replay ran:** the caps above are Stage 2's and the fill's held-out error table.

**Untouched years, 2021–2024 (plus 2020 and 2022): 225 target passes, 4.7 M cells.** Error is |log10 FNU| in the table; mean feet error is given as `ft`. Intervals are 95%, by resampling whole target passes.

| | cells | mean error (95% interval) | ft |
|---|---|---|---|
| **high** | 118 k | **0.117** (0.104–0.136) | 0.86 |
| **moderate** | 1.82 M | **0.127** (0.113–0.144) | 0.80 |
| **low** | 140 k | **0.166** (0.132–0.213) | 1.18 |
| B direct | 477 k | 0.105 (0.091–0.124) | 0.65 |
| C nearby | 98 k | 0.124 (0.103–0.157) | 0.69 |
| D stable, older | 1.51 M | 0.137 (0.119–0.161) | 0.89 |
| E, the number it **hid** | 2.53 M | **0.175** (0.153–0.198) | 0.94 |
| F, the fill it **refused** | 75 k | 0.148 (0.112–0.192) | 0.85 |

**Discovery years, 2025–26: 141 targets, 2.9 M cells.** Confidence: high 0.100, moderate 0.102, low 0.127. Levels: B 0.088, C 0.126, D 0.118, E 0.140, F 0.181.

What this shows:
- **Ordered, but only two tiers.** high ≤ moderate < low in both sets, but high and moderate are indistinguishable (0.117 vs 0.127; 0.100 vs 0.102). The real separation is {high, moderate} against low.
- **Refusing E is right.** The numbers E withholds would have been the worst shown in both sets.
- **Refusing F is justified.** It is clearly so on discovery (0.181, the worst). On the untouched years F (0.148) is worse than B and C but about equal to D, so the 5 km line is conservative rather than necessary there.
- **Grass beds are unreliable.** On 2020–24, `low|grass` erred **0.390 log10 (5.1 ft)**, interval 0.15–0.52. On 2025–26 it erred 0.116. Carried-in values are unstable across years (§ blockers).
- **Old scenes in summer hold worse.** D warm 0.158 vs D cold 0.119 on the untouched years.
- **Shares of cells on the untouched years:** E 54%, D 32%, B 10%, C 2%, F 1.6%. Most water, most of the time, is "the drainage has changed since the last good scene". That's honest, and it's the main reason reports matter.
- **The 80% range is conservative.** It covered 97–100% of satellite-to-satellite changes. It is the conversion's error against in-situ Secchi, so this is not its calibration.

## 5–8. Reports: ground truth, private, local

**The model** extends the private trip store's `TripClarityNote`. Every field is optional, so old notes migrate untouched:
- `ownerUid`, `lakeId`;
- `methodRaw`: under bowfishing lights = `userReportedNightVisibility`, by daylight = `userReportedDayVisibility`;
- `underLights`, `depthFt`, `notes`, `photoFileName` (the photo is kept in Application Support/ClarityReports and never uploaded);
- `regionId`, `zoneId`, `cellIndex`, `sharedAt`.

The time and precise position are captured automatically. Position uses the map's 5 m fix, not the 500 m `currentLocation`. Reports can belong to a trip, but need not.

**Intervals, not numbers.** `ClarityBand.interval` is (0,1) (1,2) (2,4) (4,6) (6,nil); 6+ is open-ended. A report never gets a midpoint. The existing `representativeFeet` stays for the offline evaluation only; nothing new reads it.

**Night is not Secchi.** The method is kept on every report and every shared payload. Nothing converts or fits one to the other.

**Privacy (item 7):**
- Reports are read only through `reports(ownedBy:lakeId:)`.
- Sharing is opt-in per report. The payload (`SharedClarityReport`) is exactly `{lakeId, unit, hour, lowFt, highFt, method, underLights, source:"userReported"}`.
- `unit` is the **Stage 3A zone** (`zone:122`), or `region:_mainStem` for the main stem, which has no zones.
- `hour` is rounded down to the hour.
- A test asserts that no coordinate, cell, note, photo or account appears. With no zone or region, nothing is shared rather than falling back to a coordinate.
- The zone is the coarsest unit that still supports calibration, because Stage 3A's evaluation already works at zone level.
- **No upload endpoint exists yet.** The payload is built and tested; the shared store is a blocker.

**Local evidence (item 8):**
- A report speaks for **its own 30 m cell only**: no radius, nothing carried along a creek or over land.
- **Fresh** means under 12 h old with the region's drainage stable or minor since. If the change is unknown, under 3 h. These are rules, not fits.
- The freshness check sends only the region and the time (`/clarity/current/change`), never where the report was made.
- A fresh report leads the tap card; the satellite's own answer follows, unchanged. An older one appears as "Your earlier report …".
- Reports never reach Huntability. The existing guard (`testUserObservationsDoNotReachHuntability`) still holds, and the new A/B path reads only satellite clarity.

## 9–11. The map, the tap card, the key

**Colour means clarity, and only clarity.** The composite draws in the existing Answer ramp. Evidence changes how much colour a cell shows (its `presence`), never the hue:

| Cell | Presence |
|---|---|
| high confidence | 1.0 |
| moderate | 0.78 |
| low | 0.5 |
| E (changed since the scene) | 0.30 |
| F (no supported number) | 0 (not drawn) |

- **Uncertain water fades toward a neutral grey** (`#7A8089`), not toward transparency. A transparent cell would show the basemap's own water colour and read as "clear".
- **Presence is feathered over ~170 m within the water**, so a scene tile's edge or an arm's mouth reads as a gradual change rather than a line. A tap answers its own cell, unfeathered.
- **Measured on the painted image:**
  - Town Creek (E): alpha 163 and greyed, against 217 and saturated in the shipped layer.
  - Crow Creek's head (F, 5.9 km from any reading): transparent.
  - A stable direct cell: near full.
- **Key:** "Water Clarity · Clear ─── Muddy · Sentinel-2 · latest usable observations. Faded water is less certain." There is no paragraph; coverage and provenance are in the tap card.

**Tap card (engine words):**

| Case | Card |
|---|---|
| Direct, stable | **~5.9 ft** · Likely 2.6–19.6 ft · High confidence · Sentinel-2 · Sep 20 · Direct satellite observation · "Observed 8 days ago; the drainage has stayed as it was since." |
| Filled | **~3.7 ft** · Likely 1.6–12.4 ft · Low confidence · Sentinel-2 · Sep 20 · Estimated from satellite readings 1.9 km away through the water (cloud hid this water) · "Observed 8 days ago; only minor rain or flow change since." |
| Major change | **Last supported estimate ~5.8 ft** · Not current · Direct satellite observation · Major hydrologic change since observation · Town Creek flow substantially above its level at the observation (×48.5, measured, USGS 03572900) · 1.18 in of rain on its drainage since the observation · Current visibility change is not yet calibrated. |
| No number | **No supported estimate** · The nearest satellite reading is 7.6 km away through the water: too far to carry a number. |
| With a report | **YOUR REPORT · 2–4 ft under bowfishing lights · Reported 21 minutes ago** · SATELLITE · No supported estimate … · [Report clarity] |

## 15. Creek-head beta workflow

A **Clarity run** bar (Developer → "Clarity run", over Current Clarity) sits at the top of the map, clear of the recentre button and the layer rail:
- five one-tap bands (`<1`, `1–2`, `2–4`, `4–6`, `6+`) and a lights/daylight toggle;
- "N logged · last 2–4 ft", Undo and End.

Each tap is a report at the current precise fix, with a haptic, and the pins appear on the map. It works where the satellite has nothing, for example Town Creek's back water 7.6 km from any reading, which is exactly where it's for. The full sheet is one tap away from any card: five big bands, lights, and optional depth, notes and photo.

## 12. The two-world architecture: A/B (no scoring changed)

### Consumers audited

Two agents audited every clarity consumer, on iOS and on Android (the lakedir checkout) plus the engine.

| Consumer | Today | Against canonical |
|---|---|---|
| Engine `/conditions` clarity factor, gate, `clarityVisibility` | `rain-decay-v0` unless a USGS turbidity gauge is within 10 mi and 6 h. None exists at Guntersville | on Sep 28 it said **4.0 ft at all 62 points** (0.00 in in 72 h) |
| iOS dashboard tile, strip, lake tiles, Tonight sheet | the engine factor's label ("~4.0 ft Clear"); three on-device curves draw the charts (`MetricSheets` 4·e^−0.4R, `MyLakes` 4·e^−0.9R, no floor) | one number per coordinate; the curves disagree with each other |
| iOS Water Clarity map | the bundled Sep 20 pass, all drawn at full confidence | replaced by the composite when the beta is on |
| iOS Huntability, Sector Intelligence, Priority Zones | **one clarity for the whole lake**, parsed from the dashboard's label at the phone's location; the segment is ignored | per-bank canonical behind the flag (below) |
| iOS Trip logbook / TripRecall | a user "Clear/Fair/Stained", default "Fair" | untouched |
| Android | no Water Clarity layer, no Huntability; the tile and row show the engine label; its clarity sheet **recomputes on the phone** (4·e^−k·R48, floor 0.9) | audit only; nothing changed |

`testTheLegacyClarityPathsAreExactlyTheKnownOnes` (in both repos) pins the legacy sites. On the phone they are `ConditionsConfig`, `MyLakes` and `MetricSheets`; in the engine, `ClarityFactor` and `ConditionsConfig`. A new one fails the build and has to be named.

### Legacy against canonical at 62 points

One point per region plus the dashboard city and the lake-tile point (`ab_legacy_vs_canonical_points.json`):
- **The legacy engine gives a number where canonical has none at 24 of 62:** 21 are E (drainage changed) and 3 are F.
- **Where both give a number (38):** legacy minus canonical has a median of −0.6 ft (range −3.0 to +1.0). Legacy sits inside canonical's wide 80% range at all 38, but the **bin differs at 11 of 38**.
- **The dashboard's coordinate is the city (34.358, −86.295), which is on land.** Canonical has no answer there. The dashboard should read the lake's region summary, not a point.

## 13. Huntability: "unknown is not poor" (flag `canonicalClarityHuntability`, off)

- **Flag on:** `waterClarity` reads each bank's own canonical clarity at its anchor, or the nearest water cell within 3.
  - Magnitude supported → the canonical central ft.
  - Unsupported (E or F) → `.unknown`: dropped, weight renormalised, a gap recorded. It is **not** muddy, **not** clear, and has **no stand-in number**. The rule trail says why ("the drainage has changed since the satellite scene").
- **Flag off:** production, byte for byte. A test covers this, and the model attaches the lookup only behind the flag.
- The model's declared shape changed, so `huntability-2026.09.25.1` became **`huntability-2026.09.28.1`**, repinned.

**A/B across all 6,504 Guntersville banks**, on the test night (wind 6 mph, new moon, dry), against Sep 28's composite (`ab_huntability.json.gz`):

| | Flag off (shipped) | Flag on |
|---|---|---|
| Clarity input | 4.0 ft on every bank | per bank; **2,320 banks (36%) unknown** |
| Score change | — | median 0, p10 −2, min −9, **max 0** |
| Band changes | — | **43 banks Prime → Good** |
| Confidence | moderate on all | 543 low, 5,961 moderate |

Nothing goes up, because the legacy 4.0 ft already saturates the clarity favourability (≥ 4 ft = 1.0). The unknown banks cluster in Mud, North Sauty, Town, South Sauty, Browns and Big Spring creeks: the arms with runoff since their scenes.

## 16. The relaxed shore rule: challenger only

`relaxed_challenger.py` ran on **25 clear winter discovery passes** (Nov–Mar, ≥ 50% of open water read). It compares production against the one relaxed variant from Stage 3B: bank standoff 0, structure standoff 30 m, cell minimum 10%.

- The relaxed rule adds **354 k cells, +8.2%** over production's 4.3 M.
- **Adjacency bias** is each relaxed-only cell's log10 FNU minus production-read water within 300 m on the same pass. The **baseline** is production cells measured against their own neighbours.

| Distance to the lake's edge | cells | median bias | p90 | share > +0.1 | baseline share > +0.1 |
|---|---|---|---|---|---|
| 0–30 m | 30 k | +0.020 | +0.169 | 21.7% | 28.0% (few, noisy) |
| 30–60 m | 64 k | +0.023 | +0.171 | 20.2% | 11.7% |
| 60–100 m | 115 k | +0.012 | +0.146 | 15.1% | 5.8% |
| ≥ 100 m | 111 k | +0.007 | +0.130 | 13.7% | 2.1% |

- The median bias is small, but the high tail is **2–7× the baseline's** at every distance beyond 30 m.
- Per-pass medians range from −0.03 to +0.08.
- The tail could be shore glow or real turbid creek water. Without in-situ turbidity (there is no sensor within the engine's 10 mi at Guntersville) or trusted reports, the two can't be told apart.
- **Not approved.** The dataset is saved per pass (`challenger/*.npz`, in the scratchpad) for the day reports or a sensor can judge it.

## 17. Relative flow continues as change evidence

The hourly job keeps recording each arm's NWM and USGS flow, and Stage 3B's replicated association is used only as a hydrologic-change signal (§3). Its prediction gate is not reopened. Independent storms keep accumulating in the hourly record.

## 18. Tests

**Engine 160/160** (138 existing plus 22 in `CurrentClarityTests`):
- the hierarchy: direct outranks distant fill; > 5 km refuses; a grass bed is at most low; in-situ answers in its own zone only;
- major change lowers authority but can't alter feet;
- stable conditions keep an older scene;
- missing rain is unknown, not zero;
- modeled flow is never "measured";
- low authority can't display as high confidence (every combination of runoff, completeness, flow and cell);
- the legacy estimate is never the answer, and `/conditions` marks rain-decay as legacy;
- intervals stay intervals, and night is not Secchi;
- the index decodes and matches the graph, and land is not water;
- each region stands on its own scene and nothing crosses between them;
- **the map's table is the resolver's own decision** for every cell kind and region state;
- a foreign index is refused; the encoding decodes; the phone's golden numbers;
- no scoring source reads Current Clarity;
- the legacy paths are exactly the known ones.

**iOS 14 in `CurrentClarityTests`:**
- the phone reproduces the engine's conversion to the digit, and the outcome column for every cell kind;
- the map and the tap card read the same cell;
- lower confidence never draws more certain; changed water says its number is history;
- intervals stay intervals; night is not Secchi;
- **a report can't become another user's precise coordinate**;
- reports are scoped to their owner and speak only for their cell; freshness follows the water, not the clock;
- **unsupported clarity can't reach Huntability as clear or muddy**; supported clarity reaches it per bank;
- **production Huntability is unchanged with the flag off**;
- the legacy clarity paths are exactly the known ones;
- plus the A/B evaluation, which writes `huntability_ab.json`.

**Also:** the Linux smoke test passes, including the four new routes. Full iOS suite: still running when this was written, with 556 passed and 0 failed so far. All 14 new tests passed, and the repinned Huntability fingerprint passed. The earlier run's two failures (a presence threshold in my own test, and the fingerprint pin) were fixed before this run.

## 19. Screenshots (`docs/clarity/stage4_screens/`)

Real, on the iPhone 17 Pro simulator, local engine, Sep 28 hydrology:

| File | Shows |
|---|---|
| `01_whole_lake.jpg` | whole-lake: canonical colour on the main stem; Town Creek, Big Spring and Short Creek fade (E); creek heads with no number stay uncoloured |
| `02_lake_centre.jpg` | mid-lake: the main stem in colour; South and North Sauty faded (runoff since their Sep 18 scene) |
| `03_creek_arm_town_creek.jpg` | creek arm: Town Creek greyed (major runoff since its scene) |
| `04_creek_back_town_creek.jpg` | creek back: 7.6 km from any reading, not drawn |
| `05_tap_direct_observed.jpg` | direct-observed water card |
| `10_tap_interpolated.jpg` | interpolated water card (1.9 km fill, low) |
| `06_tap_major_change.jpg` | major-change water card: last supported, not current |
| `08_tap_no_supported_estimate.jpg` | creek back: no supported estimate |
| `07_report_sheet.jpg` | the report sheet |
| `09_user_report_creek_back.jpg` | user-reported creek back: the report leads, the satellite refuses |
| `13_creek_head_run.jpg` | the clarity run bar: 2 logged, Undo |
| `00_legacy_layer_sep20.jpg`, `11_ab_legacy_town_creek.jpg` | A/B: the shipped layer draws Town Creek vivid and confident |
| `12_ab_legacy_dashboard_4ft.jpg` | A/B: the dashboard's "~4.0 ft Clear" the same afternoon |

## Running the review locally

```
# the bucket mirror (the live bucket + rebuilt scenes, cells, arms, a 45-day hourly record)
python3 -m http.server 8123 --bind 127.0.0.1 --directory <scratch>/stage4/bucket
# the engine against it
SECTOR_LAKE_SURFACE_BASE=http://127.0.0.1:8123 SECTOR_CURRENT_CLARITY_ROUTES=1 PORT=8080 \
  .build/arm64-apple-macosx/debug/SectorEngineServer
# the simulator (Debug build): Developer → "Current Clarity (beta)", or
xcrun simctl spawn <sim> defaults write io.sector.co currentClarityBaseURL http://127.0.0.1:8080
xcrun simctl spawn <sim> defaults write io.sector.co currentClarityBeta -bool YES
```

The first lake request builds the world from live gauges (about 40 s), then serves from a 10-minute cache.

## Remaining blockers to production cutover

1. **The daily job must publish per-scene cells and per-arm anchors.**
   - Done in code: `daily.py` `current_cells_files`; `deploy-job.sh` copies the index. It was tested locally, and the job's cells file is byte-identical to the mirror's.
   - **Needs your approval to redeploy the job.** Until then the live bucket has no cells, and every region answers "no scene".
2. **Hourly rain must reach back 45 days.** `BACKFILL_HOURS=1110` on one hourly-job run (approval), or wait until about Oct 28 for the record to grow. Until then, scenes older than Sep 14 have unknown rain since (moderate cap).
3. **The engine needs a review deploy** with `SECTOR_CURRENT_CLARITY_ROUTES=1` (a tagged, no-traffic revision). Approval.
4. **Cold start.**
   - Building the lake's world pulls live NWPS and USGS for 68 arms: **36–50 s cold**, then cached 10 min.
   - The composite is 2.9 MB, uncompressed.
   - It needs precomputing (in the hourly job) or keeping warm before real users.
5. **Grass beds (decision).** Carried-in grass values erred 5 ft on 2020–24 but not on 2025–26. Replay evidence says they shouldn't carry a supported number. Your Sep 26 call was to colour the beds. Options: refuse the number but draw beds faded (like E), or keep low confidence.
6. **Confidence tiers (decision).** high and moderate are indistinguishable in error. Either present two tiers, or tighten "high" (for example, direct and ≤ 72 h) and re-test.
7. **The shared report store:** Firebase rules, endpoint and moderation. The payload is built and tested; nothing uploads.
8. **The beta gate is Debug-only.** TestFlight would need a master-account gate.
9. **Android:** audit only. It still recomputes clarity on the phone and has no layer.
10. **Scoring adoption** (Conditions factor, Huntability, Sector Intelligence, dashboard reading a region instead of a land point) waits on review of the A/Bs above. **Stopped here, as specified.**
11. **Other lakes.** The 598 others have no regions index or graph, so they're unsupported.
12. **The in-situ path (A)** is tested only on fixtures: no qualifying sensor on Guntersville.

---

## READY NOW
Supported for production once the plumbing above is deployed:
- **The canonical type and resolver:** one answer for map, tap and API, with provenance on every value.
- **Hydrology-gated authority:** a scene's number stops being "current" after runoff (E), and its feet are never adjusted. Validated: the hidden numbers are the worst shown.
- **Refusal:** no number beyond 5 km of a reading or with no scene (F). The fill it refuses is worse than direct and nearby evidence.
- **Direct and near-filled satellite magnitudes (B/C/D) with their range and a two-level confidence** ({high, moderate} vs low), validated on untouched years.
- **The map treatment:** colour is clarity, uncertainty fades, changed and unsupported water are visibly different. The key has no paragraph.
- **The legacy estimate labelled as legacy**, and detectable by tests wherever it's consumed.

## BETA / LEARNING
Useful now, still collecting calibration evidence:
- **Bowfisher clarity reports and the creek-head run.** Private, intervals, night kept apart from Secchi, cell-local, freshness by drainage. Their reach, their relation to Secchi and their freshness rules are unmeasured.
- **Shared, de-identified reports** at zone level (no store yet).
- **Per-bank canonical clarity in Huntability** (flag, A/B above).
- **The relaxed winter shore rule** as a challenger dataset (+8% cells, heavy positive tail).
- **Relative NWM flow** as change evidence; storms keep accumulating.
- **Grass-bed values and the high-vs-moderate split** (decisions 5 and 6).

## NOT SUPPORTED
Sector keeps refusing:
- **Exact runoff-driven visibility:** no feet added or subtracted for rain, flow or plumes.
- **Plume movement or arrival timing** along an arm or down the main stem.
- **A current number for water whose drainage has changed** since its last good scene (E), and for water more than 5 km from any reading (F).
- **Converting night visibility under lights into Secchi depth** (or the reverse), or fitting one to the other.
- **Propagating a report beyond its own cell**, or across land.
- **A neutral stand-in clarity** (the old 4.0 ft) wherever the evidence is missing.
- **Any lake without a hydrologic graph and regions index.**

**Stopped before switching production Huntability or Sector Intelligence to the new value.**
