# Clarity Fusion Stage 1: hand-off

Prepared 2026-09-27 in the `Sector_Engine` worktree `Sector_Engine-fusion`, branch `feat/clarity-fusion-stage1`, stacked on `feat/lake-surface-job`. **Nothing is committed, deployed, or applied to the apps.**

Stage 1 makes the geography and the inputs trustworthy. There is still no fused clarity, no plume and no transport.

**Where things are**
- Scripts: `scripts/hydrology/` (the run order is in its README).
- Data: `docs/data/hydrology/guntersville/`.
- Engine code: `Sources/SectorEngine/Hydrology/` and `API/HydrologyAPI.swift`.
- The audit this follows: `Sector-mapbox/docs/fishintel/WATER_CLARITY_INTEGRATION_AUDIT.md`.

**Waiting on your approval** (none is done):
1. Deploy the engine: the forecast-rain fix plus the new read-only `/hydrology` endpoints (§6, §8).
2. Adopt the repaired membership in the iOS lake profile. There are two variants with very different impact (§2.4).
3. Create the hourly catchment-rain job, a new cloud resource (§3).
4. Change production `/conditions` to use each arm's explicit gauge instead of the nearest one (§4.3).
5. Switch the map to the canonical visibility conversion (§7).

---

## 1. Repaired tributary topology

**Method** (`build_arm_graph.py`, `finalize_graph.py`):
- **Directed network.** The 12,456 cached NHD High Resolution flowlines are joined at shared endpoints; NHD digitizes lines downstream.
- **Systems.** A system is a connected run of same-named lines, so two separate creeks with one name are two systems. An unnamed line that carries a named creek's water belongs to that creek (NHD often continues a creek's path through a wide arm as unnamed connectors). An unnamed feeder belongs to the system it drains into.
- **Water lattice.** The lake is gridded on the Water Clarity frame (2468×2886, about 29.6 m cells): 304,489 water cells in one connected body. 1,859 bridge cells rejoin narrow arms that the centre burn cut off.
- **Allocation.**
  - Every water cell takes the arm it is reached from first *through the water* (multi-source Dijkstra, 8-neighbour, metres).
  - The **main stem** is the corridor within 400 m of the Tennessee's own named channel, measured through the water. That is the old profile's 400 m, now through water instead of straight line.
  - Unnamed coves that drain straight to the river are main-stem shoreline.
- **Head and mouth.** A head is where the creek's line enters the lake outline. Line type can't be used: NHD carries Town Creek and South Sauty as reservoir lines for 20–40 km up their valleys. A mouth is where the creek's longest path hands its water to another system.
- **Main stem.** It runs 124.5 km from Nickajack Dam to Guntersville Dam (TVA gives 75.7 mi). It is cut into 40 regions: at every top-level mouth, and at least every 5 km.

**Result:** 68 arms. 35 flow straight to the main stem and 33 are nested (for example, Jagger Branch → Honeycomb Creek → the river). 12 are large (natural channel at least 15 km) and 56 are minor.

**The two named defects**

| | Before | After |
|---|---|---|
| Town Creek | One id for two creeks 36 km apart. The registry had the northern creek's mouth (34.707, −85.910) and NWM reach (19645450) but the Geraldine creek's gauge (03572900). Its 74 km "reservoir path" spanned both. | `town-creek-marshall`: the Geraldine creek, the Guntersville State Park arm. Head 34.400, −86.068; mouth 34.401, −86.222; 23.1 km of reservoir path; 87 km of channel above; 407 km² above the head, 560 km² at the mouth; HUC12 060300010705 "Minky Creek-Town Creek"; NWM 19649040; USGS 03572900. `town-creek-jackson`: head 34.712, −85.952; mouth 34.707, −85.910; 7 km² basin; NWM 19645450; no gauge. |
| Mink Creek | One id. The registry kept the northern creek, and banks on the southern one (a Browns Creek sub-arm) were tagged with it. | `mink-creek-jackson` (enters the river at 34.559, −86.111) and `mink-creek-marshall` (enters Browns Creek at 34.293, −86.383). |

**Other duplicate names split the same way:** Dry Creek (4 systems), Jones Creek (2), Rocky Branch (2). The registry's `jones-creek` carried the southern creek's mouth and the northern creek's head, 39 km away.

---

## 2. Before and after

### 2.1 Membership, all 6,504 shoreline segments (`membership_diff.csv`)

| Change | Segments |
|---|---|
| Unchanged | 4,069 |
| Split name, now its own creek's id (Town / Mink / Jones / Dry / Rocky) | 671 |
| Arm → main stem (corridor or unnamed cove) | 1,345 |
| Arm → a different arm | 290 |
| Main stem → arm | 124 |
| Unclassified → classified | 5 |

**Old associations that crossed land:** 255 of 5,489 (`old_association_land_check.csv`). The test: through-water distance to the named creek's own water is more than 3× the straight line plus 500 m, or there is no water path within 20 km. All 255 are reassigned.
- Worst: Yellow Creek 48 of 77, Town Creek 45, Nichols Branch, Seibold Branch.
- Some reassignments don't cross land by this test. They are the new rule preferring the arm or cove reached first through the water.

**Where the old ids went:**
- **Town Creek** (695 banks): 270 → Marshall, 233 → Jackson, 143 → main stem, 45 → Roseberry Creek, 4 → Minky Creek.
- **Mink Creek** (162 banks): 78 → Jackson, 29 → Marshall (the Browns Creek banks), 39 → main stem, 16 → North Sauty.

### 2.2 Registry audit, all 48 old entries (`registry_audit.csv`)

Every old entry matches a network arm.
- **Mouths:** 5 moved more than 1 km (at most 1.5 km).
- **Heads:** 15 moved more than 1 km. Jones Creek moved 38.9 km, South Sauty 28.8, Crow 26.1, Battle 19.1 and Short Creek 16.3. The old builder took a pond junction far up the valley as the head.
- **Natural channel length:** off by more than 25% for 16 entries (for example South Sauty 34 → 51 km, Short Creek 14 → 42 km, Crow 13 → 50 km).
- **NWM ids:** 32 differ. 27 of the old ids are another reach of the same creek. **5 are a different stream:** Short Creek → Flat Branch, Crow Creek → a Town Creek, Horn Branch → Widows Creek, Hayes Branch → Dripping Spring Branch, and Baker Spring Branch → an unnamed reach (`old_nwm_id_check.json`).
- **Gauges:** one was misattached. `town-creek`'s 03572900 now belongs to `town-creek-marshall`.
- **Flagged instead of guessed** (26 of the old entries, flag counts over all 68 arms):

  | Flag | Arms |
  |---|---|
  | Mouth reach belongs to another stream (name given) | 17 |
  | Mouth basin unresolved | 7 |
  | Mouth basin implausible (Honeycomb, Town Creek (Jackson)) | 2 |
  | No NHDPlus reach at the head | 9 |
  | Tiny reservoir reach | 7 |
  | Head basin suspect (Honeycomb) | 1 |

### 2.3 Downstream consumers: fields that would change if the candidate were adopted (`field_impact.json`)

| Field | Segments changed | Readers (from the audit) |
|---|---|---|
| `tributaryId` | 2,430 | TributaryInfluence, ShorelineSurface, PriorityZoneBuilder (naming), PriorityAreaViews, SegmentTopology |
| `lakeRegion` | 2,435 | PriorityZoneBuilder (grouping, naming), SpatialPrivacyPolicy, SegmentTopology |
| `basinClass` | 2,392 (863 minor→main stem, 510 minor→large, 482 large→main stem, 322 large→minor, …) | most species attraction models |
| `distanceToTributaryM` | 6,504; the meaning changes to through water from the mouth | TributaryInfluence bands, GrassCarpMigration, SmallmouthBuffaloSpawn, thumbnails |
| `distanceToChannelM` | 6,497; 2,218 change by more than 1 km (through water instead of straight line) | SpottedGarBackwater, LongnoseGarOpenWater, CommonCarpYearRound, SmallmouthBuffalo (spawn and year-round) |

### 2.4 Downstream consumers: what the outputs would do

Measured by running the real iOS engines on the shipped profile and on each candidate, every species × every month. It was a temporary test on the Sector Tests simulator, reverted afterwards. Results are in `candidate-profile/impact_*.txt`.

**Full candidate** (all five fields):
- **Huntability:** no change on any segment in any month.
- **Attraction:** band changes and how many of the top-10% banks stay top-10%:

  | Species | Bands changed (of 6,504) | Top-10% kept |
  |---|---|---|
  | Common carp | 2,780 | 52% |
  | Smallmouth buffalo, spawn (April) | 1,888 | 29% |
  | Smallmouth buffalo, other months | 1,043 | 88% |
  | Grass carp | 890 | 62% |
  | Spotted gar | 884 | 62% |
  | Longnose gar | 572 | 95% |

- **Priority zones:** the displayed top 3 change for most species and months.

**Identity only** (`tributaryId` and `lakeRegion`):
- Attraction, bands, percentiles and huntability do not change at all (0 on every row).
- Only the priority zones' grouping and names change. For example, "Town Creek" becomes "Town Creek (Marshall Co.)" rather than one zone mixing two creeks. Main-stem banks group as "Main channel".

**Reading this:** the large shifts come entirely from `basinClass` and the through-water distances. The species models were tuned against the old straight-line semantics.

**Recommendation:** adopt identity-only now; it fixes every connectivity defect and moves no score. Treat arm classes and through-water distances as a separate, model-by-model decision.

---

## 3. Catchment rainfall architecture

This replaces the ±0.35° four-point "watershed" for the new architecture only. The production path (`MrmsPrecipService`) is untouched.

**Drainage.** Each arm's contributing area is the NHDPlus V2 basin from USGS NLDI:
- the basin at the reach just above the mouth, if that reach is named for this creek, or is unnamed with a plausible size;
- otherwise the basin above the head.

Totals: 64 of 68 arms have one (42 at the mouth, 22 above the head only). The 4 without one have no resolvable reach and are flagged. Polygons are in `catchments/`.

**Grid.** Each basin is stored as fractional NOAA MRMS 0.01° cells (`guntersville.mrms_weights.json`, `catchment_rain.py weights`), with weights summing to 1.

**Aggregation** (`catchment_rain.py rain`), at an hour T:
- **Windows:** basin-mean rain over the last 1, 6, 12, 24, 48 and 72 h, from the MRMS MultiSensor QPE **Pass 2** products valid at T (public on s3 `noaa-mrms-pds`, archived since 2021 or earlier).
- **Current storm:** hourly totals summed back from T to the last 6 dry hours (under 0.01 in).
- **Antecedent:** the 7 days before the 72 h window.
- **Missing data:** a basin with less than 90% of its cells valid gets no value.

**Running it.** An hourly Cloud Run Job at about T−2 h (Pass 2 latency) would publish `gs://sector-lake-surface/rain/<lake>/catchments.json`. The engine's `CatchmentRainfallFeed` reads that file. A feed older than 4 h reads unavailable. **The job does not exist**; until it does, every arm reads `unavailable: the hourly catchment rain job is not running yet`.

**Validated on real storms** (`real-storms/`):

| MRMS basin-mean | Town Creek (Marshall) | South Sauty | Short Creek | North Sauty |
|---|---|---|---|---|
| Storm of 2026-09-11 (at 00Z Sep 12) | 0.60 in | **1.04 in** | 0.41 | 0.18 |
| Storm of 2026-09-21 (24 h to 00Z Sep 22) | 0.61 | 0.35 | **1.12** | 0.11 |
| 72 h to 00Z Sep 23 | **1.17** | 0.68 | 1.46 | 0.47 |

The gauges answered their own basins:
- **South Sauty (03572690):** 1 → 14 cfs on Sep 11, when its basin had 1.04 in.
- **Town Creek (03572900):** 2 cfs on Sep 11 (0.60 in on dry ground), then 0 → 19 cfs on Sep 21–23 (1.17 in over 72 h).

The antecedent dependence is plain, and it is what Stage 2 must calibrate.

**Resolution limit.** MRMS cells are about 1 km. Rain placed exactly on Town Creek's basin reaches its neighbours only through shared boundary cells: South Sauty 0.17 in, and more for small basins (Berry Branch 1.14 in).

**A fragility this replaces.** Production's "today" rain is a single Open-Meteo call, and a failed call reads 0. During the A/B, Beaver read 0.09 in once and 2.95 in on retry.

---

## 4. Flow sources

### 4.1 Explicit association
An arm's gauge is the active USGS discharge site on the creek's own NHDPlus network: NLDI upstream navigation from the arm's matched reach, active meaning it reported 00060 in the last 7 days.
- 72 USGS sites sit upstream on the arms' networks; exactly **2** report discharge:
  - `town-creek-marshall` → **03572900** TOWN CREEK NEAR GERALDINE AL;
  - `south-sauty-creek` → **03572690** SOUTH SAUTY CREEK NEAR RAINSVILLE.
- No other arm has one. **Browns Creek borrows none**; production gives it Town Creek's gauge, 38 km away.

### 4.2 Provenance (`TributaryFlowService`)

| Provenance | Meaning | Guntersville |
|---|---|---|
| `measuredUSGS` | Its own gauge, reading within 6 h | 2 arms |
| `modeledNWM` | The National Water Model analysis for its own reach (NOAA NWPS; the feature id is the NHDPlus comid, matched by name), plus the model's 18 h short-range forecast. A gauged arm whose gauge is stale falls here, and says so. | 57 arms (55 answered live) |
| `unavailable` | No gauge and no matched reach, with the reason. Never a guess. | 9 arms |

Measured and modeled are never merged. At Town Creek on 2026-09-27 the gauge measured 25.8 cfs and the model's analysis said 14.5.

### 4.3 Production (approval item 4)
Production `/conditions` still takes the nearest USGS discharge gauge by straight line for its clarity "rise" shave (at most 25%, rising limb only). The fix is to use the arm's explicit gauge or none. Today no gauge is rising, so the fix would change no current score, but it changes behaviour during rises.

---

## 5. Main-stem inputs (`MainStemService`)

TVA RestApi, hourly:

| Dam | Role | TVA id | Values (2026-09-27 20:00 UTC) | Provenance |
|---|---|---|---|---|
| Nickajack Dam | Inflow at the head of the reservoir | NKJT1 | release 30,744 cfs; pool 632.87; tailwater 595.05 | `measuredTVA` |
| Guntersville Dam | Outflow | GVDA1 | release 14,900 cfs; pool 593.86; tailwater 555.49 | `measuredTVA` |

- Each dam comes with its 48 h history and today's posted generation schedule (`scheduledTVA`).
- **Current velocity:** exposed as `"unknown: not measured anywhere in the reservoir"`. Nothing converts a release into a speed or a travel time.

---

## 6. Forecast-rain bug

**Fixed** (`ConditionsForecast.swift`, `MrmsPrecipService.swift`).
- **Tonight:** unchanged.
- **Each future night:** its 72 h window is rebuilt day by day:
  - observed MRMS watershed rain for the days already past, from a new per-day `watershedByDay` kept beside the 72 h total, which is not rebuilt from it;
  - today: the larger of the MRMS rain so far and the forecast;
  - forecast rain for the future days.
- **MRMS unavailable:** the old Open-Meteo window path, unchanged.

**Tests** (`ForecastRainTests`, 5):
- dry tonight with heavy rain at +24 h: night +1 muddies;
- heavy rain at +48 h: night +2 and +3 muddy, night +1 and +5 don't;
- tonight still equals the gauge;
- yesterday's observed rain carries into night +1 only;
- no MRMS: the old path.

With the fix switched off, the 3 bug tests **fail** and the 2 invariants pass. With it on, all 5 pass.

**A/B at the same instant** (old build against this build, locally):
- **Tonight:** identical at every checked spot (Guntersville ×2, Thurmond, Knoxville, Evansville, Beaver) once live data matched.
- **Future nights:** they differ only where forecast rain exists.

| Spot and night | Clarity sub-score, new | Old |
|---|---|---|
| Thurmond, night +6 | 18 | 70 |
| Knoxville, night +6 | 46 | 70 |
| Guntersville, night +5 | 64 | 70 |
| Guntersville, night +6 | 34 | 70 |

---

## 7. Canonical turbidity → visibility (`VisibilityModel`)

**Validation** (`visibility_validation.py`, lake-grouped CV; median absolute error, and the share within ±30%):

| Set | Engine 11.123·T^−0.637 ft | Map (ADEM) 4.84·T^−0.672 m | National refit (CV) |
|---|---|---|---|
| In situ, national (81,661 pairs, 5,220 lakes) | 1.22 ft, 42% | 2.34 ft, 22% (bias +0.24 log) | 0.88 ft, 50% |
| In situ, Alabama (3,311) | 0.81 ft, 60% | 0.91 ft, 57% | 0.81 ft, 56% |
| In situ, Tennessee River reservoirs (130) | 0.94 ft, 64% | 2.51 ft, 27% (bias +0.17) | 1.17 ft, 63% |
| Sentinel-2 FNU vs Secchi (905 match-ups) | 2.18 ft, 31% | 2.91 ft, 30% | 2.45 ft, 30% |

**Choice:** `secchi-power-v1`, the engine's formula, as the central value.
- It is the most accurate on this region's water and on satellite input.
- It is exactly the production gauge path, so adopting it changes no score (tested).
- The map's ADEM formula reads 1.5–1.7× too clear and should be retired: **approval item 5**, changes map numbers.
- The national refit (7.272·T^−0.525 ft) is recorded for when the engine serves more of the country.

**Interface.** `estimate(fnu:source:distanceToObservedM:)` returns `centralFt`, `lowFt` and `highFt` (the 80% range) plus confidence:

| Source | 80% range (log10 of observed / predicted) | Confidence |
|---|---|---|
| In-situ gauge | −0.381 to +0.142 | medium |
| Satellite, observed cell | −0.356 to +0.520 (about ±2.5×) | low |
| Satellite, filled cell | as observed, widened by the fill's held-out error at its distance from a reading | low |

Nothing converted from turbidity is "high". The reflectance band model (interim 1.67 ft, 48%) is the upgrade path for satellite input, through the same interface.

---

## 8. Runtime hydrologic graph

**Where it lives.** `Hydrology.guntersville` is embedded as one JSON literal (`HydrologyData.swift`, 100 KB, generated). That is the lake-directory approach, because the Cloud Run image carries no resource bundle.

**Structure:**
- **Nodes (247):** `head:<arm>`, `arm:<arm>`, `mouth:<arm>`, `ms-00…ms-39`, `nickajack-dam`, `guntersville-dam`, `wheeler-lake`.
- **Edges (246), all downstream:** `head → arm → mouth → arm:<parent> | ms-NN → … → guntersville-dam → wheeler-lake`.
- **Per arm:** identity (NHD reach codes, NHDPlus comids, HUC12, county), lengths, basins, gauge, NWM reach, flow source and flags.

**Queries:** `arm(_:)`, `children(of:)`, `downstreamPath(from:)`, `arms(enteringRegion:)`.

**Point lookup.** `Hydrology.guntersvilleGrid` is a coarse (about 180 m) cell → arm grid on the clarity frame. `membership(lat:lon:)` returns `.mainStem`, `.arm(id)` or `.notWater`. The full-resolution grid is in `guntersville.arm_cells.json`.

**Endpoints** (new, read-only; `/conditions` is untouched):
- `GET /hydrology/graph?lake=Guntersville|AL`
- `GET /hydrology?lake=Guntersville|AL`: live flow per arm with provenance, rain per arm (unavailable until the job exists), and TVA at both dams. Cached 10 min, 8 fetches at a time.

**Sentinel evidence is preserved separately** (item 8). The shipped raster is not touched. `guntersville.clarity_evidence.2026-09-20.json` (1.4 MB) holds, per cell:
- FNU code;
- canonical visibility (central, low, high);
- observed / grass / cloud-haze / unreadable;
- observation date;
- through-water distance to a reading;
- the specific exclusion reason: the first gate failed (1–22), surface grass (30), or read-then-dropped (40–43);
- the cell's arm.

It was rebuilt cell for cell against the shipped raster, and 110,176 cells are observed.

---

## 9. Scenario validation (association layer only; no visibility)

`scenario_association.json` covers the audit's storms plus basin-exact ones.

**Proofs asked for:**
- **Town Creek's rain belongs to Town Creek.** Rain placed exactly on its basin gives Town Creek and its nested creeks (Minky, Black Oak, Hurricane, Duvall, Mormon Hole) 2.0 in. Its gauge 03572900 answers. South Sauty gets 0.17 in, only from shared ~1 km boundary cells.
- **South Sauty's rain belongs to South Sauty:** 2.0 in on its basin, gauge 03572690. Town Creek gets 0.09 in.
- **Browns Creek borrows no river's gauge.** Rain on its basin: Browns 2.0 in, and no gauge answers, because it has none; its flow is its own NWM reach, labelled modeled. Production gives it Town Creek's gauge.
- **Jagger Branch can't inherit South Sauty.** Its parent and top level are Honeycomb Creek. South Sauty isn't on its downstream path, and South Sauty storms give it 0.0 in. The old ring gave it 2.3 ft of mud for 3 days (audit S2).
- **Across a peninsula is not adjacent.** North Sauty and Roseberry Creek water 385 m apart is 15.0 km apart through the water. Nichols and Brogue Branch: 715 m apart, 9.7 km by water. Marshall and Nichols Branch: 666 m, 13.0 km. Each pair lies in different arms (test-pinned).
- **Direction.** Every arm's path runs head → mouth → parent or region → … → Guntersville Dam → Wheeler, and the regions run in order from Nickajack. Nested arms enter their parent. Town Creek (Jackson) enters at ms-20, upstream of South Sauty (ms-28) and Town Creek (Marshall) (ms-33).

**The audit's circle storms, re-run** (arms receiving at least 0.05 in):

| Storm | Arms that receive rain | Gauges that would answer |
|---|---|---|
| S1: circle south of Geraldine | Short Creek 0.83, Town Creek (M) 0.36, Black Oak 0.26 (it was mostly Short Creek's headwaters) | 03572900 |
| S2: circle over South Sauty | Black Oak 0.78, South Sauty 0.77, Town Creek (M) 0.59 (the two basins interleave on Sand Mountain) | both |
| S3: circle over Browns | Mink (M) 2.0, Beech 1.93, Browns 1.56, Rocky (M) 1.56, Big Spring 1.29 | none |
| S4: 1.5 in lake-wide | 64 arms | both |

Each test spot gets its own arm's basin rain at T+0, 6, 12, 24 and 48 h as window accumulations. These are forcing only, not propagation. Stage 1 cannot say when that water reaches a bank.

---

## 10. Tests

**Engine:** 116 of 116 pass (`swift test`).
- 96 existing.
- 5 `ForecastRainTests`.
- 15 new hydrology tests:

| Suite | Tests | What they cover |
|---|---|---|
| `HydrologyGraphTests` | 10 | The connectivity proofs in §9, main-stem order, nested arms, the channel is main stem |
| `HydrologyInputsTests` | 4 | USGS and NWPS parsing, the unavailable reason, rain-feed parsing and staleness |
| `VisibilityModelTests` | 2 | The central value equals the production gauge path; ranges bracket it and widen with distance |

**iOS:** no app code or asset changed. The impact measurement ran as a temporary test on the Sector Tests simulator and was reverted.

**Regression:**
- `/conditions` code differs only in forecast nights (§6).
- The new endpoints are additive.
- Fish Attraction, Huntability, Priority Zones and the Water Clarity raster are untouched unless approval item 2 is taken.

---

## 11. Remaining unknowns

- **No transport data.** Current velocities, plume travel times, dilution and mixing rates, and resuspension thresholds: Sector measures none of them for Guntersville.
- **Surface visibility of inflows.** Whether a given storm's inflow shows at the surface at all (overflow, interflow or underflow depends on inflow temperature and density).
- **Runoff response per arm.** Its size and recovery need calibration from pass history against basin rain and gauge or NWM flow. The two gauged arms already show that the antecedent state matters (Town Creek didn't answer 0.60 in on dry ground).
- **NWM skill on these small creeks.** It is untested. At Town Creek the model's analysis was 44% below the gauge.
- **Incomplete drainages.** The 22 arms with basins above the head only are missing their local arm land and nested creeks (Browns Creek among them). 4 arms have no drainage at all (Baker Spring among them).
- **MRMS resolution.** About 1 km cells blur small basins, those under about 20 km².
- **Main-stem corridor.** 400 m through water is a rule, not a measurement. The pure nearest-channel variant is recorded per segment (`nearestChannelVariantIsMainStem`) for comparison.
- **Species models.** Whether they should move to through-water distances and the recomputed arm classes (§2.4) is a model question, not a data one.
- **Other lakes.** The graph exists only for Guntersville. The builder is general, but each lake needs its NHD cache, and its heads and mouths reviewed.
