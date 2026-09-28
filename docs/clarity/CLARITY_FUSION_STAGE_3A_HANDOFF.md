# Clarity Fusion Stage 3A: hand-off

Prepared 2026-09-28 in `Sector_Engine-fusion`, branch `feat/clarity-fusion-stage1`. Stage 3A is research and validation. **Nothing in production changed**: the Water Clarity map, `/conditions`, Huntability, Priority Zones and Fish Attraction are untouched, and nothing was deployed.

**Decision: insufficient evidence for spatial runoff adjustment.** The evidence gate (§9), fixed before the holdout was run, fails on five of its seven criteria.

**Answers to the eight questions**

1. **Does hourly MRMS materially improve the Stage 2 replay?** No.
   - It changed the expected direction on 29 of 1,316 pairs, and the 28 new "murkier" calls were right twice.
   - Direction skill (Peirce) went from 0.082 to 0.073.
   - Clustered by pass date, Stage 2's own skill interval already included zero (−0.08 to 0.24).
2. **Do large embayment heads respond more strongly than whole-arm medians?** It can't be measured for most large arms, because their heads are almost never readable:

   | Arm | Head zone measurable on |
   |---|---|
   | Town Creek | 2.7% of passes |
   | Other five-zone arms (median) | 6.8% |
   | Browns | 55% |
   | South Sauty | 50% |

   - Browns, 0–3 days after a storm: head murkier beyond noise on 3 of 7 events, whole arm on 0 of 7. Suggestive, but far too few events.
   - South Sauty's head does track measured flow: 60% murkier with the gauge ≥ 3× its baseline-pass flow, falling to 11% at the mouth. **All of it is 2026; in 2025 it is 0 of 5.**
3. **Is there repeatable head→mouth progression?** No.
   - 0–3 days after a storm, the head is stronger than the rest in 55–61% of events, not significant at any lag.
   - Split by year: 2026 64% (p = 0.045), 2025 44% (p = 0.76).
   - At every lag, most events show no zone beyond noise.
4. **What lag distribution is supported?**
   - Pooled, the response sits at 0–3 days (upper, middle and lower zones of large arms, and whole small arms), fading by 4–6 days. Small arms still read 33% murkier at 7–10 days.
   - None of this replicates across years: 2025 shows almost no response at any lag. The lag is **not calibrated**.
5. **Which arm classes show measurable response?** Only in 2026:
   - the other large (five-zone) arms, in all but their unreadable heads;
   - the heads and mouths of medium arms;
   - small whole arms.

   The named large arms (Town Creek, South Sauty, Browns) show none at the zone or arm level. Post-hoc, the response is a **cold-season** one (§6.6): Nov–Mar storm windows read murkier 22% (2025) and 57% (2026) of the time; Apr–Oct, 7% and 0%.
6. **Are small arms predictable enough to spatialize before large ones?** No.
   - They respond most when they respond (2026, 2–3 days: 71%, median ×2.85).
   - But the median small arm is measurable on 0% of passes (only a few ever are).
   - Their 2025 events number 3–6 per lag, with no response.
7. **Does a runoff-adjusted challenger beat the static satellite baseline on holdout events?** No, it is worse in both folds:

   | Fold | Challenger error (log10) | Static baseline |
   |---|---|---|
   | Train 2025 → test 2026 | 0.271 | 0.220 |
   | Train 2026 → test 2025 | 0.214 | 0.132 (95% interval of the difference excludes zero) |

   The two years' learned storm adjustments have **opposite signs**.
8. **Is there enough evidence to proceed to a production spatial field?** No.

---

## 1. Hardening

### 1.1 Production commit
- **`be1d893294d2973879e76a21998783681bdcb41d`** on `feat/clarity-fusion-stage1`, tagged `deployed/sector-engine-00044-b6m`. The Stage 2 hand-off's later edits followed as `4925591`. Stage 3A's changes are uncommitted on top.
- **How it was proven.** Cloud Build's own source archive for `00044-b6m` (`gs://run-sources-sector-9393c-us-central1/services/sector-engine/1790551043.301963-a3735ec0…zip`) was downloaded and diffed against `git archive be1d893`: byte-identical. The only differences are dotfiles, `__pycache__`, and the gitignored copies the hourly job's deploy script makes.
- **The job.** `hydrology-hourly`'s newest archive (`…/jobs/hydrology-hourly/1790548642.914304-…zip`, image `sha256:05e4f5b4…`) matches `jobs/hydrology-hourly` file for file. Its copied `catchment_rain.py`, graph and weights are identical to the committed `scripts/hydrology/catchment_rain.py` and `docs/data/hydrology/guntersville/*`.
- **Local only: not pushed** (pushing publishes to the public repo; your call).

### 1.2 Complete test results
- **iOS, full `SectorTests`** on the Sector Tests simulator (`-parallel-testing-enabled NO`), with the Stage 1 expectation fixes and the Tributary Influence repair: **722 run, 721 passed, 0 failed, 1 skipped.** The skip is `StrangerToTheLakeTests.testAnUnnamedStretchIsDescribedByWhereItIs` ("no unnamed area reached the shortlist on these nights"), as before.
- **Engine:** **138/138**. That is the 136 from Stage 2 plus two live-selection tests.

### 1.3 Linux deployment smoke test
- **`scripts/linux-smoke.sh`** builds the same Dockerfile Cloud Build uses and runs it with the Stage 2 routes on. It calls:
  - `/health`;
  - `/conditions` at both gauged arms, the main stem and a lake with no graph;
  - `/conditions/batch` and `/lakes`;
  - `/hydrology/graph`, and `/hydrology` cold and cached;
  - `/clarity/state` (arm, main stem, land) and `/clarity/states`.
- **It fails on** any call with no answer, a dead or restarted container, or a runtime abort in the log. A `/conditions` 503 counts as an answer (upstream feeds can be down).
- **`deploy.sh` now runs it first** and refuses to deploy on failure. `SKIP_LINUX_SMOKE=1` bypasses it knowingly.
- **Verified both ways.** It passes on the current code (68 s). With the `async let` beside the task group in `/hydrology` put back, it reports *"the container died during: hydrology (cold)"* and "freed pointer was not the last allocation".

### 1.4 Live anchor selection (`ClarityStateLoader`)
- **Reads recent scenes.** The loader reads `lakes/<slug>/clarity/history.json`, then each recent pass's `arms/<date>.json` (up to 12 passes within 45 days); `arms/latest.json` only when there is no history.
- **Chooses per arm and for the main stem** with `ClarityHistory.selectAnchor`, the replay's rule: the newest scene that anchors at least moderately, else the newest that anchors at all. A cloudy newest pass no longer displaces a clear one before it.
- **Measures from the chosen scene.** Divergence, rain since the pass and the reconstructed at-pass USGS reading all run from the scene actually used, per arm.
- **Explains the choice.** When the newest scene was passed over, the state says so in its limitations.
- **Tests:**
  - `testLiveSelectionKeepsAClearOlderSceneOverACloudyNewOne`: rain is counted from the older scene, and the note appears.
  - `testANewSceneThatAnchorsWellDisplacesTheOlderOne`: a new moderate scene wins; a future scene is never read; with only weak scenes, the newest weak one stands.
- **Not deployed.** Production stays on `00044-b6m`, where the Stage 2 routes are off. The daily job still does not publish per-arm files; that is your earlier open decision.

### 1.5 Tributary Influence display repair (iOS, `Sector-mapbox`, uncommitted)
- **New field.** `ShorelineSegment.throughWaterToArmMouthM`: the bank's through-water distance to the mouth of its own arm (Stage 1's `throughWaterToMouthM`). It is written into the lake-profile asset by `repaired_profile.py`.
- **Reader.** `TributaryInfluenceEngine` now reads that field, and only that layer does.
- **Coverage.** 4,268 of 6,504 banks carry it (every arm bank but GT-003277, which has no water cell), median 3.5 km. 1,575 fall inside the drawn bands (< 2.5 km).
- **Untouched.** `distanceToTributaryM`, `distanceToChannelM`, `basinClass`, `tributaryId`, `lakeRegion` and every attraction ranking are unchanged, verified field by field against the Stage 1 asset.
- **Descriptor.** The layer's descriptor said 84.4% coverage and 48 systems; it now says 65.6% and 68. Its `beyond` label is "Farther from the mouth" (it was "Main lake", which is wrong for banks deep inside an arm).
- **Tests.** `testTheLayerReadsItsOwnThroughWaterDistance` is new. The coverage expectations are updated in `TributaryInfluenceTests` and `FishIntelLayerTests`.

---

## 2. Within-arm position system (`arm_positions.py`)

For every lake cell of every arm, on the Water Clarity frame (36 mercator m, 29.6 m on the ground):
- **`dHeadM`**: through-water distance from the arm's head;
- **`dMouthM`**: through-water distance to its mouth;
- **`norm`** = dHead / (dHead + dMouth);
- the arm id, parent arm, top-level arm and main-stem receiving region (per arm).

**Method.**
- 8-neighbour Dijkstra with no diagonal across a land corner, restricted to the arm's own allocation (which includes the Stage 1 bridge cells).
- Head and mouth snap to the nearest cell of the arm's largest connected water body. Mouths snap about 385–412 m, because an arm's allocation stops at the 400 m main-stem corridor.
- A cell across land from the head is never close to it.

**Result.**
- 95.1% of arm water is positioned.
- 4.9% lies in fragments not connected to the arm's main body through its own water (North Sauty 3,301 cells, Mink Creek (Jackson) 729, Seibold 674, …). They are reported and left out, never guessed.

## 3. Zones

**The rule** (fixed from geometry alone, before any zone statistic):
- Order an arm's positioned lake cells by `dHeadM` and cut them into K groups of equal area.
- K is the largest of 5, 3, 2 or 1 such that the arm is ≥ K × 1 km long and every zone holds ≥ 400 cells (0.35 km²).
- Names: head, upper, middle, lower, mouth (K = 3: head, middle, mouth; K = 2: head, mouth; K = 1: whole).

**Why equal area, not equal distance.** Many arms are a long narrow channel and a wide embayment. Town Creek's first 11.4 km of 22.6 hold 6% of its water, so equal-distance bins were empty or unreadably small there.

**Result.**

| Zones per arm | Arms |
|---|---|
| 5 | 13 |
| 3 | 6 |
| 2 | 7 |
| 1 | 33 |
| none (no lake cells) | 9 |

That gives **130 zones**. Town Creek's head zone is 0–17.3 km from its head (the channel plus the back of the embayment); its mouth is 22.0–23.1 km.

**Caveat.** A zone is a distance class, not a contiguous reach. An arm's far side lobes fall in its "mouth" zone (Roseberry's, in `devmap/zone_change_2026-01-28_roseberry-creek.png`, read ×11.2 on a lobe beside the main stem).

## 4. Historical observed zone dataset (`zone_history.py`)

- **Coverage:** 147 passes × 130 zones. Directly observed cells only, after the production read's gates and drops; nothing filled enters an FNU statistic.
- **Per pass × zone:** observed cells; coverage (of non-grass water); FNU p25, p50, p75; canonical visibility (secchi-power-v1, satellite 80% range); cloud, grass and unreadable fractions.
- **Measurable** = ≥ 30 observed cells and ≥ 30% coverage.
- **Anchors:** per pass × arm (and the main stem), in the engine's anchor-file format, with **through-water fill distances** (multi-source Dijkstra from the observed cells, as the product's distance PNG).

**How often a zone can be read** (median over zones, share of the 147 passes):

| Group | head | upper | middle | lower | mouth | whole |
|---|---|---|---|---|---|---|
| Town Creek | **2.7%** | 49% | 62% | 61% | 58% | |
| South Sauty | 50% | 57% | 49% | 57% | 61% | |
| Browns | 55% | 61% | 62% | 54% | 65% | |
| Other large (K = 5, 10 arms) | **6.8%** | 33% | 43% | 46% | 47% | |
| Medium (K = 2–3) | 38% | | 40% | | 49% | |
| Small (K = 1, 33 arms) | | | | | | **0%** |

100 of the 130 zones are measurable on at least one pass; 30 never are. **The backs of most large arms, and most small arms, are beyond what Sentinel-2 can read under the production gates**: narrow water inside the bank standoff, which is also where a creek's runoff would enter.

## 5. Hourly-MRMS replay (item 4) and historical fill distance (item 5)

- **v1** reproduces Stage 2 exactly: 1,309 unique pairs, identical expectations.
- **v2 (`--hourly`)** sees the day before each pass as 23 hourly 01H Pass 2 steps (17Z the day before → 16Z) plus the residual hour that contains the pass, which is never visible to it. 3,427 hours were read, 8 missing (those days stay daily).
- **v3 (`--anchors`)** judges each scene's strength from the reconstructed fill distances instead of observed coverage alone.

On the pairs common to all three:

| Run | Pairs | "Murkier" held | Base rate | Peirce skill (95%, by date) | Same at next pass, high / mod / low / none |
|---|---|---|---|---|---|
| v1 (Stage 2) | 1,063 | 13.9% | 10.6% | 0.079 (−0.09, 0.26) | 81 / 75 / 77 / 67% |
| v2 + hourly rain | 1,063 | 13.5% | 10.7% | 0.073 (−0.10, 0.26) | 82 / 76 / 74 / 70% |
| v3 + fill distances | 1,056 | 13.2% | 11.0% | 0.063 (−0.11, 0.25) | 81 / 78 / 69 / 70% |

- **Fill distances change anchor strength.** Of the 2,882 historical pass × arm scenes Stage 2's replay rated weak, 1,819 are moderate and 154 strong. **None moved down**, so the missing metadata made Stage 2's replay under-rate scenes, never promote them.
- **v3 as a whole** has 1,732 pairs, direction skill 0.044 (−0.11, 0.21).
- **By target arm:**

  | Arm | Direction skill |
  |---|---|
  | Town Creek | −0.10 |
  | South Sauty | −0.19 |
  | Browns | −0.10 |
  | Boshart | −0.18 |
  | Yellow Creek | +0.19 |
  | Main stem | +0.07 |

  Every interval spans zero. **Arm-level runoff direction has no demonstrated skill with better inputs either.**

## 6. Event studies (`zone_events.py`)

**Definitions and noise.**
- Anomaly = log10 of the zone's median FNU minus the median of the same zone's measurable passes in the prior 45 days that followed a dry week (≥ 2 of them).
- A storm day is ≥ 1.0 in on the arm's drainage in a 17Z–17Z window. The window through 16Z on the pass day is hourly.
- The noise band per position comes from dry-week anomalies: about −0.16 to +0.08…+0.15 log10 for zones, −0.28 to +0.18 for whole small arms. Dry weeks cross the upper band about 10% of the time by construction.
- Scale: 3,157 zone events, 1,027 arm events, 93 lake-wide storm days forming **51 independent storms**.

### 6.1 Large vs small (zone × lag; "murkier" = share beyond noise; p vs the dry-week share, one-sided)

| Group | Zone | 0–1 d | 2–3 d | 4–6 d | 7–10 d | Dry weeks |
|---|---|---|---|---|---|---|
| **Town Creek** | upper–mouth | n 1–2 each, no response | n 2–4: 0–25%, medians ×0.68–0.92 | n 2–5 | n 4–10: 10–25% | 8–17% |
| **South Sauty** | head–mouth | n 1–3 | n 2–4: 0–25% | n 3–7 | n 4–8 | 0–14% |
| **Browns** | head | 1/3 | **2/5 (p 0.08)** | 0/6 | 1/12 | 11% |
| | upper–mouth | 0/3 each | 0–20% | 0–33% | 8–9% | 3–12% |
| **Other large (10 arms)** | head | 1/5 | 2/4 (×1.62) | 1/5 | 1/9 | 5% |
| | upper | **36% (p 0.01)** | **56% (p < 0.001), ×1.39** | **44% (p < 0.001)** | 25% | 11% |
| | middle | **53% (p < 0.001), ×1.43** | **48% (p < 0.001)** | 22% | 22% | 10% |
| | lower | 29% (p 0.04) | **56% (p < 0.001)** | 14% | 18% | 8% |
| | mouth | 9% | **36% (p 0.01)** | 20% | 20% | 10% |
| **Medium (13 arms)** | head | 27% (p 0.05) | **35% (p 0.002)** | 14% | 14% | 11% |
| | mouth | 12% | 24% (p 0.02) | 11% | 14% | 11% |
| **Small (whole arm)** | whole | 27% | **59% (p < 0.001), ×1.79** | 27% | **33% (p < 0.001)** | 10% |

**Arm level (whole-arm median, the Stage 2 quantity).**
- Town Creek, South Sauty and Browns show no response at any lag (n 2–12).
- Other large arms: 33% at 0–1 d, 43% at 2–3 d.
- Small arms: 59% at 2–3 d.

### 6.2 Head vs whole arm (paired, same passes)

| Group | Lag | Head beyond noise | Whole arm beyond noise | Head − arm (median log10) |
|---|---|---|---|---|
| Browns | 0–3 d | 3 of 7 | 0 of 7 | +0.03 / +0.10 |
| Other large | 0–3 d | 3 of 9 (head measurable so rarely) | | |
| Medium | 2–3 d | 43% | 14% (n 7) | |
| All | no storm | | | −0.01 to +0.01 |

**The heads that can be read respond a little more often than their arm's median. Every paired cell is under 10 events.**

### 6.3 Head→mouth progression (events with ≥ 3 measurable zones)

| Lag | Events | Median ρ (zone index vs anomaly) | Head stronger | Sign-test p | Median peak (0 = head, 1 = mouth) | No zone beyond noise |
|---|---|---|---|---|---|---|
| 0–1 d | 23 | −0.3 | 61% | 0.14 | 0.5 | 15 |
| 2–3 d | 31 | −0.4 | 55% | 0.36 | 0.5 | 17 |
| 4–6 d | 34 | −0.3 | 56% | 0.24 | 0.5 | 26 |
| 7–10 d | 61 | +0.4 | 34% | 0.99 | 0.75 | 48 |
| dry weeks | 182 | +0.2 | 45% | 0.88 | 0.75 | 154 |

- **Pattern counts at 0–3 d:** none 32; every measurable zone 5; head, not mouth 7; mouth, not head 1; mixed 9.
- **Reading it:** there is a hint that the head leads early and the mouth late, but the late pattern is the same as in dry weeks. Year split, 0–3 d: 2026 64% head-stronger (p = 0.045), 2025 44% (p = 0.76). **Not repeatable.**

### 6.4 Measured flow (USGS; Town Creek and South Sauty)
- **Town Creek.** No zone responds even with the gauge ≥ 3× its baseline-pass flow (murkier 10–13%, medians ×0.84–0.98).
- **South Sauty.** With the gauge ≥ 3×, the share murkier falls down the arm:

  | Zone | Murkier | Events |
  |---|---|---|
  | head | 40% | 15 |
  | upper | 29% | 17 |
  | middle | 13% | 15 |
  | lower | 13% | 15 |
  | mouth | 6% | 17 |

  That is a real head→mouth gradient. **Split by year, the 2026 head is 6 of 10 and the 2025 head 0 of 5 (median ×0.63).**

### 6.5 Modeled flow (NWM, relative to its own baseline-pass value; never as cfs)
- **With the model's flow ≥ 3× its baseline**, zones read murkier 36–49% at every position (head 42%, upper 49%, middle 47%, lower 41%, mouth 36%), against 8–15% below 1.5×. The response appears **everywhere together**, a little weaker at the mouth.
- **By year:**
  - 2026: 38–54%, all p < 0.001.
  - 2025: middle 3 of 6 (p = 0.016) and mouth 4 of 14 (p = 0.045); head, upper and lower not significant (n 3–10).
- **This is the only signal with any support in both years.** 2025's samples are small.

### 6.6 Season (post-hoc; exploratory, not gate evidence)

| | Storm-window (0–3 d) zone events | Murkier (dry-week rate ≈ 10%) | Median |
|---|---|---|---|
| 2025, Nov–Mar | 27 (21 in March) | **22% (p = 0.046)** | ×0.94 |
| 2025, Apr–Oct | 83 (72 in Sep–Oct) | 7% | ×0.80 |
| 2026, Nov–Mar | 143 (121 in January) | **57% (p < 0.001)** | ×1.48 |
| 2026, Apr–Oct | 11 (May) | 0% | ×0.91 |

- The 2025-vs-2026 disagreement mostly follows the season: winter storms raise turbidity in clear water, while warm-season storms don't show over algae-driven turbidity.
- Every 2026 signal above is carried by one January.
- **A hypothesis for Stage 3B, found after looking. It needs its own pre-registered test on new data.**

## 8. Holdout evaluation

- **The unit:** a measurable zone on a pass, with an earlier measurable observation within 45 days and a dry baseline.
- **Static satellite baseline:** the zone's last measurable value (persistence).
- **Challenger:** on runoff cases (a storm day after the last observation, within 10 days), the zone's dry baseline plus the *training* year's median anomaly for its position group (head, rest or whole) and lag bin, where ≥ 8 training events support it.
- **Also reported:** "revert", the dry baseline alone.

| Fold | Learned adjustments (log10) | Runoff cases | MAE static / challenger / revert | Direction accuracy static / challenger | Challenger skill (95%) | MAE difference, challenger − static (95%) |
|---|---|---|---|---|---|---|
| Train 2025 → test 2026 | −0.19 … −0.03 (**clearer**) | 215 | 0.220 / 0.271 / 0.233 | 52% / 44% | 0.04 (−0.03, 0.12) | (−0.016, +0.141) |
| Train 2026 → test 2025 | +0.01 … +0.46 (**murkier**) | 272 | 0.132 / 0.214 / **0.118** | 69% / 31% | 0.08 (−0.17, 0.43) | **(+0.018, +0.115)**: worse |

Over all test units, the challenger's MAE is 0.146 vs 0.137 and 0.103 vs 0.092: worse in both folds. Zone ordering on runoff cases: the head is above the rest in 5 of 10 and 10 of 27 events.

## 9. Evidence gate

| Criterion (fixed before the holdout) | Result | |
|---|---|---|
| G1 ≥ 12 independent storms, ≥ 4 per year | 25 (2025: 14, 2026: 11) | **pass** |
| G2 the best-supported claim significant in each year | "whole small arms, 2–3 d": 2025 0 of 3 (p = 1.0), 2026 10 of 14 (p < 0.001) | fail |
| G3 direction ≥ static + 10 points, skill ≥ 0.2 with interval above 0, both folds | 44% vs 52%; 31% vs 69%; skill 0.04 and 0.08, intervals include 0 | fail |
| G4 MAE below static, interval below 0, both folds | worse in both; one interval entirely above 0 | fail |
| G5 head above the rest in ≥ 60% of events, both folds | 50%; 37% | fail |
| G6 measurable zones only | enforced | pass |
| G7 not worse than static overall, both folds | worse in both | fail |

**Result: `insufficient evidence for spatial runoff adjustment`.**

## 10. What is safe for Stage 3B to render

**Safe, for developers only** (never user-facing, never styled like the Water Clarity map):
- **The zone geometry:** arms, equal-area zones and through-water distances. `devmap/zones_overview.png` is the template.
- **Where the satellite can and cannot read each zone** (§4). This is a fact about observation, and the map's "estimated" shading should eventually say it.
- **Historical observed zone change on a given pass**, labelled with its date and "observed, against this zone's dry baseline". `devmap/zone_change_*.png` are the template.
- **The Stage 2 per-arm state**, as it is: direction flags with no feet.

**Not safe, anywhere:**
- any runoff-adjusted visibility, colour pushed down an arm, predicted plume or zone-level runoff forecast;
- any "head first" rendering;
- anything that changes Huntability, Priority Zones or Fish Attraction.

**What would change the answer:**
- **More years.** Sentinel-2 L2A reaches back to 2017, MRMS Pass 2 to late 2020, and the NWM operational archive further. Four more years triples the storm count and gives the cold-season and modeled-flow hypotheses an out-of-sample test.
- **A pre-registered, season-stratified gate** run on those years.
- **The modeled-flow-relative signal (§6.5)**, tested out of sample.
- **The unreadable arm heads.** A sensor or method that reads narrow water: PlanetScope, or Sentinel-2's 10 m bands with a tighter bank rule validated against in-situ turbidity.
- **Wind.** It is preserved for Stage 4 (`wind_asos_4A6_GAD_HSV.csv.gz`, hourly, Scottsboro, Gadsden and Huntsville, Feb 2025–Sep 2026) and not used here.

---

## Files

- **Scripts** (`scripts/hydrology/`, run order in the README): `pass_history.py` (`--cells`, `--only-read`, `--reverse`), `arm_positions.py`, `zone_history.py`, `rain_pass_hours.py`, `replay_skill.py`, `zone_events.py`, `zone_season_check.py`, `zone_map.py`, and `repaired_profile.py` (the `throughWaterToArmMouthM` field). Also `scripts/linux-smoke.sh`.
- **Engine:**
  - `ClarityStateLoader.swift`: history-aware anchors.
  - `ClarityState.swift`: `anchorNote`.
  - `ClarityReplay/main.swift`: `--hourly`, `--anchors`.
  - `deploy.sh`: smoke gate.
  - `Tests/…/ClarityStateTests.swift`: 2 new tests.
- **iOS (`Sector-mapbox`):** `ShorelineSegment.swift`, `TributaryInfluence.swift`, `FishIntelLayerManager.swift`, the lake-profile assets, `TributaryInfluenceTests.swift`, `FishIntelLayerTests.swift`.
- **Data (`docs/data/hydrology/guntersville/stage3a/`):** `arm_positions.npz`, `arm_zones.json`, `zone_history.json.gz`, `anchors/` (147), `zone_events.json`, `rain_pass_hours.json.gz`, `replay_v1|v2|v3.json`, `passes_zone_rerun/`, `wind_asos_4A6_GAD_HSV.csv.gz`, `devmap/` (6 images). The 21 MB of per-cell pass files are not committed; step 1 of the README rebuilds them in about 2 h.

**STOP. No production runoff-adjusted clarity field was built.**
