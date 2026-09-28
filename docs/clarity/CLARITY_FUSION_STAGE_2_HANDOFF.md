# Clarity Fusion Stage 2: hand-off

Prepared 2026-09-27 in the `Sector_Engine` worktree `Sector_Engine-fusion`, branch `feat/clarity-fusion-stage1` (Stage 2 is on the same branch), stacked on `feat/lake-surface-job`. **Nothing is committed.** The Stage 1 items you approved are deployed (§0). Stage 2 itself is not deployed and does not score.

Stage 2 answers one question per arm: *what does Sector currently believe this arm's clarity is, and why?* It gives one state per hydrologic arm and one for the main stem. Each state fuses:
- the latest satellite scene of that water;
- rain over that arm's own drainage since the scene;
- that creek's own flow, measured or modeled and never merged;
- how wet the ground was when the scene was taken;
- how complete each of those inputs is.

There is no plume transport, no wind transport and no per-cell field.

**The short version**
- **The state is built, testable and live-readable.** It is read-only, behind a flag (§12), and `/conditions` does not use it.
- **Authority falls on evidence, never on age (§3).** In the replay, the authority ladder is monotonic: scenes it kept at *high* matched the next clear pass 79% of the time; scenes it dropped to *none*, 65%.
- **No storm effect can be sized yet (§6).** Storms do make arms murkier, and the satellite read does see plumes (Short Creek 2.8 → 23.9 FNU; Boshart Creek ×5.8). But across 147 passes and 1,024 arm events, the response is a minority outcome. Its size varies by arm, and its timing disagrees between 2025 and 2026. So the runoff state gives a direction and never moves the feet.
- **The hydrologic direction has little skill at the next clear pass (§10).**
  - When the state expected *murkier*, the next pass read murkier 15% of the time, against 11% when it expected no change.
  - After the biggest storms (major runoff, ≥ 1.5 in since the scene), 25%.
  - When the scene had caught runoff that then receded, *clearer* held 28% of the time.
- **The National Water Model tracks the ups and downs but not the size (§8).** Over 584 days its rank correlation with the gauges is 0.90–0.91. But it reads 1.2× the Town Creek gauge and 2.9× South Sauty (9.7× at low flow), and it misses 37–50% of the gauges' day-over-day doublings. Modeled flow is therefore used only relative to itself, and a model rise alone is capped at *moderate runoff*.

**Where things are**
- Engine: `Sources/SectorEngine/Hydrology/ClarityState.swift` (types and the pure engine), `ClarityStateLoader.swift` (live inputs), `ClarityHistory.swift` (as-of reads for the replay), `API/ClarityStateAPI.swift`.
- Replay: `Sources/ClarityReplay/`.
- Tests: `Tests/SectorEngineTests/ClarityStateTests.swift`.
- Scripts: `scripts/hydrology/`. The Stage 2 run order is in its README.
- Data: `docs/data/hydrology/guntersville/stage2/`.
- Hourly job: `jobs/hydrology-hourly/`.

---

## 0. Stage 1 decisions, carried out

| # | Decision | Done |
|---|---|---|
| 1 | Deploy the forecast-rain fix and the read-only `/hydrology` endpoints | See §0.1 |
| 2 | Adopt identity-only membership (`tributaryId` + `lakeRegion`) | iOS assets regenerated (`Sector-mapbox`, uncommitted). One segment the new membership could not place (GT-003277, no water cell) keeps its shipped creek instead of a fake `unclassified` id. `basinClass` and both distances keep their shipped values. |
| 3 | Build and deploy the hourly catchment-rain job | Deployed. Cloud Run Job `hydrology-hourly`, Scheduler every hour at :15 UTC, service account `lake-surface-job@`. The first run backfilled 30 days. See §4. |
| 4 | Clarity reads each arm's explicit gauge or none | In the deploy (§0.1). No lake without a graph borrows a gauge any more. |
| 5 | Adopt `secchi-power-v1` as canonical, keeping the range and provenance | Engine: `clarityVisibility` on `/conditions`. iOS map: `visibilityFeet` = 11.123·FNU^−0.637 plus a `likely X–Y ft` range in the probe. |

**iOS tests** (Sector Tests sim, full `SectorTests`): 721 ran, 719 passed and 2 failed, both expectation changes from items 2 and 5. Both are fixed and re-run (40/40 in the four affected classes):
- `testClarityConversionMatchesTheEngine` had a hand-typed 7.14 where the formula gives 7.15.
- `TributaryInfluenceTests.testTheRealLakeHasEnoughTributaryDataToDrawAtAll` required 80% of *all* banks to have a creek. Under the adopted membership, main-stem banks belong to no creek, so 4,269 of 6,504 banks (65.6%) do. The test now requires every bank off the main stem to have its creek (4,269 of 4,269).

**Found in passing, not changed:** the creek-mouth layer (`TributaryInfluenceEngine`) pairs each bank's `tributaryId` with its `distanceToTributaryM`. On 414 banks the adopted identity now names a different creek than the shipped distance was measured to (290 arm → another arm, 124 main stem → arm). That layer draws those banks' "at mouth / near / within" bands against the wrong creek. The fix is the through-water distance you held back from the species models. It is your call whether that layer (which is not a species model) takes it.

### 0.1 Engine deploy

- `sector-engine-00040-clq`, the first build, was tagged and tested with no traffic against production (00039) at nine points:
  - Tonight's score was identical at all nine.
  - Every difference was an approved change:
    - Town Creek reads its own gauge (~3.5 ft vs ~4.0 ft).
    - Future nights use their real forecast rain (nights 5–6 drop, for example Wheeler's night 5 from 40 to 28).
    - The new `clarityVisibility` field appears.
    - Lakes without a graph no longer borrow the nearest gauge (Travis, 3.9 → 4.0 ft).
  - **One regression.** At South Sauty the top-level `discharge` came back empty on Cloud Run, reproducibly, and not locally. The nearest-discharge lookup and the new arm-gauge lookup ran side by side. They now run one after the other.
- `00041-dpx`: that fix, written as a closure inside an `async let`, **aborted the Linux Swift runtime** on the first request ("freed pointer was not the last allocation", signal 6). It never took traffic. The sequential fetch is now a plain static function.
- `DEPLOY_RESULT_PLACEHOLDER`

**Pre-existing, not changed:**
- Production's nearest-discharge lookup is flaky on its own. At the Town Creek point 00039 returned no discharge on one call and 25.8 cfs on the next.
- `generation.distanceMiles` is shared across points through a cache: every point read 17.83 mi on both revisions.

---

## 1. Arm-state schema (`ArmClarityState`)

| Field | Meaning |
|---|---|
| `lakeId`, `armId`, `armName`, `timestamp` | |
| `satelliteSceneDate`, `satelliteAnchorFNU`, `satelliteAnchorVisibility` | The scene's median FNU for the arm and its canonical visibility (central, 80% low–high). |
| `satelliteAnchorStrength`, `satelliteAnchorReason` | `strong`, `moderate`, `weak` or `none`, and why (§2). |
| `satelliteObservedPct`, `satelliteFilledPct`, `medianFillDistanceM` | Observed vs filled composition. |
| `rain1hIn` … `rain72hIn`, `currentStormTotalIn` | Windows ending where the hourly record ends, which is about 2 h behind now. |
| `antecedent7dIn` | Rain in the 7 days before the scene (was the ground wet when it was taken?). |
| `dischargeCurrentCfs`, `dischargeAtSatellitePassCfs`, `dischargeTrend`, `dischargeProvenance` | One series, never mixed: the arm's gauge if it read in the last 6 h, else its model reach. The at-pass value must share the provenance of now. |
| `catchmentCompleteness` | `complete`, `partial` or `unavailable` (§5). |
| `divergence` | Everything that changed since the scene (§3). |
| `runoffAnomaly` | Rain since the pass, flow now over flow at the pass, and peak since the pass over flow at the pass, with provenance. |
| `runoff` | `state` (`stable`, `minorChange`, `moderateRunoff`, `majorRunoff`, `recovering`, `unknown`), `expectedDirection`, `magnitude` (always `uncalibrated`), and each piece of evidence. |
| `satelliteAuthority` | `high`, `moderate`, `low` or `none`, with its reason. |
| `currentVisibility` | `basis` (`satelliteAnchor`, `baseline` or `none`), numbers, `magnitudeSupported`, `warning`, and the scene's own at-pass numbers for reference. |
| `confidence` | `medium`, `low` or `veryLow` with reasons. Ordinal, not a probability. |
| `limitations`, `provenance` | A trail of every input's value and source. |

`MainStemClarityState` carries the same scene, authority, visibility and confidence fields. Its inputs are:
- direct rain on the reservoir surface;
- Nickajack's and Guntersville's 24 h mean release (now, at the pass, trend);
- `releaseProvenance`;
- `currentVelocity: "unknown: not measured anywhere in the reservoir"` (§9).

---

## 2. Satellite anchor (`SatelliteAnchor`, `arm_anchor.py`)

Per arm, from the published Water Clarity product. It uses the clarity, measured and distance PNGs, which sit on the same frame as the arm grid.

- **Water cells:** measured code 255 (read), 2 (cloud-hid it) or 1 (unreadable). Grass beds (3) are excluded: the layer colours them but the satellite never reads them.
- **Observed:** code 255. **Filled:** codes 1 and 2.
- **`filledWithin500mCells`**, **`medianFillDistanceM`:** from the distance PNG (1 + through-water metres / 100).
- **FNU distribution:** n, p25, p50, p75, for observed cells and for all cells. The per-cell evidence stays in the product.

**Strength** (rules, not fits):

| Strength | Rule |
|---|---|
| strong | ≥ 50% of the arm read, and ≥ 25 cells |
| moderate | read or filled from ≤ 500 m over ≥ 50% of the arm, and ≥ 10 cells read |
| weak | something read, but most of the arm is fill from further away |
| none | nothing of this arm read |

A strong anchor needs the majority *observed*, so "most pixels distant fill" can never be strong. For reference, the fill's own held-out error at 500 m is already 0.45 ft.

**Visibility at the pass:** from the median *observed* FNU when 10+ cells were read. Otherwise from the median of all cells as an estimate, widened by the fill error at the median fill distance (`VisibilityModel`).

**The 2026-09-20 scene** (36% of the lake read):

| Anchor strength | Arms |
|---|---|
| strong | 13 |
| moderate | 12 |
| weak | 5 |
| none | 38 (9 with no water cells, 29 not read) |

For example:
- **Town Creek:** 72% read, 28% filled at a median 100 m. Strong, 3.40 FNU → ~5.1 ft (2.2–16.9).
- **South Sauty:** 6% read, 94% filled at a median 1 km. Weak.
- **Baker Spring:** nothing read. None.

**Replay rule** (`ClarityHistory.selectAnchor`): the newest scene that anchors at least moderately, else the newest that anchors at all. A cloudy new scene does not displace a clear older one; the older scene's divergence carries the change since. This has a cost. On 2026-01-11, South Sauty's new scene (34% read) caught the storm plume, but it rated weak in the replay (which has no fill distances), so the state kept the clear 2026-01-01 scene. The live loader reads only the latest product.

---

## 3. Divergence and authority

**Divergence** (`Divergence`, since the scene):
- **Rain since the pass.** It is unknown (never zero) if under 90% of the interval was read. An unread hour is not a dry hour.
- **The storm under way, and its part since the pass.** A storm runs back to 6 dry hours.
- **Rain in the last 24 h and 72 h**, and the 7 days and 72 h before the scene.
- **Flow now, at the pass, and the peak since**, from one series:
  - The arm's own USGS gauge if it read in the last 6 h, else its NWM reach.
  - The at-pass value must be within 3 h (measured) or 13 h (modeled) and share the provenance of now.
  - A measured value is never compared with a modeled one.
- **Flow trend:** the 12 h change, with ±10% counting as steady.

**Runoff state** (`ClarityStateEngine.runoff`). Each piece of evidence gives a level, and the state is the highest:

| Evidence | minorChange | moderateRunoff | majorRunoff |
|---|---|---|---|
| Catchment rain since the pass | ≥ 0.10 in | ≥ 0.50 in | ≥ 1.00 in |
| Peak flow since the pass ÷ flow at the pass | ≥ 1.5× | ≥ 2× | ≥ 5× |
| (main stem) 24 h-mean Nickajack release now ÷ at the pass | ≥ 1.5× | ≥ 2× | ≥ 3× |

- **A modeled rise alone** is capped at `moderateRunoff`.
- **`recovering`** has two cases:
  - Moderate or major runoff since the scene, now over: under 0.05 in in 24 h, and flow back to ≤ 50% of its peak and not rising. Without a flow record, dry for 72 h. The direction stays *murkier than the pass*.
  - The scene itself caught runoff (≥ 0.5 in in the 72 h before it) and flow has since fallen below the pass value ÷ 1.5. The direction becomes *clearer than the pass*.
- **`unknown`**: no scene, or no rain record and no flow.

**Authority** is capped by the runoff state and by the anchor's own strength. **Age is not an input anywhere.**

| Runoff | Authority cap | Why |
|---|---|---|
| stable | high | the drainage is as it was when the scene was taken |
| minorChange | moderate | |
| moderateRunoff | low | |
| majorRunoff | none | the scene no longer describes this water |
| recovering | low | |
| unknown | moderate | no record shows the drainage stayed the same |

A strong anchor allows high, moderate allows moderate, and weak allows low.

**Current visibility:**
- **Authority moderate or high:** the scene's numbers, with `magnitudeSupported`.
- **Otherwise:** the baseline's numbers, unadjusted, plus the directional warning. The baseline is the engine's existing clarity estimate at the point (`/conditions` `clarityVisibility`). With no baseline there is no number at all. **Nothing in Stage 2 adjusts a foot.**

**Confidence** is an ordinal ladder: every weakness costs a step.
- anchor moderate 1, weak 2, none 3;
- runoff minor or unknown 1, moderate or recovering 2, major 3;
- catchment partial 1, unavailable 2;
- incomplete rain record 1;
- no flow 1.

Up to 1 step is `medium`, 2–3 is `low`, 4 or more is `veryLow`.

---

## 4. Rainfall and flow provenance

**The hourly job** (`jobs/hydrology-hourly/hourly.py`) runs for T = now − 2 h, because MRMS Pass 2 is gauge-corrected about 2 h late. It publishes:
- **`rain/<slug>/catchments.json`:** per arm, the 1/6/12/24/48/72 h MRMS Pass 2 accumulations, the current storm, and the 7 days before the 72 h window. This is the Stage 1 `CatchmentRainfallFeed` format.
- **`hydrology/<slug>/hourly/<date>.json`:**
  - each hour's basin-mean `rain1h` per arm, plus `_lakeSurface`, the reservoir's own surface: 265.5 km², 623 MRMS cells, added for the main stem;
  - each arm's USGS reading and its NWM analysis, stored side by side and filed under the hour they were read;
  - TVA at both dams.

  Hours read before a catchment was added are refilled for it. NWPS's `-9999` and USGS's `-999999` missing values are dropped.
- **`hydrology/<slug>/latest.json`.**

Flow history in the record starts 2026-09-27; rain goes back 30 days. Where the record does not reach the scene, the loader reconstructs flow at the pass as follows:
- **Measured:** USGS IV at the pass ± 3 h. This worked for Sep 20: Town Creek 0.6 cfs, South Sauty 0.8.
- **Modeled:** reconstructable only as far back as NWPS's analysis series reaches. Beyond that it is "at the pass not reconstructable", stated as such.

**Flow provenance across 68 arms:**
- `measuredUSGS` 2 (Town Creek Marshall, South Sauty);
- `modeledNWM` 55;
- `unavailable` 11.

Two of the unavailable arms, `boshart-creek` and `short-creek`, have an NWM feature id from Stage 1, but the model carries no value for it, live or in 584 days of archive. The likely cause is that those reaches sit inside NWM's own reservoir routing. Stage 1 counted them as modeled; they are not.

---

## 5. Catchment completeness

| Basis | Arms | Completeness |
|---|---|---|
| NHDPlus basin at the mouth | 42 | complete |
| Basin above the embayment's head only | 22 (Browns, South Sauty, Big Spring, Mud, Short, Marshall Branch …) | partial: rain around the embayment itself is missing |
| No basin resolved | 4 (Baker Spring Branch …) | unavailable: rain unknown, never zero |
| Reservoir surface (main stem) | 1 | complete |

Completeness is carried into every state:
- It is a named confidence reason.
- A partial catchment costs one step, so Browns Creek never shows the confidence of a fully resolved arm.
- It appears in the limitations text.

---

## 5a. Does the satellite see storm water? (`plume_diagnostic.py`)

Before trusting "no response", I checked whether Sen2Cor or the read's gates drop muddy water. On the 2026-01-11 storm pass (1.5 in the day before), Sen2Cor still called 99.8% of Town Creek's interior water "water", as it did before and after. The small set of "land" pixels inside the lake is the same on every date: docks and structures.

The raw red-band signal rose modestly in Town Creek (median 2.7 → 3.6 FNU) and hugely in Short Creek (2.9 → 36, saturated at p90). **The production read kept the plume:** Short Creek read 23.9 FNU median, p75 200. So when the analysis below finds little response, that is not an artefact of the read.

---

## 6. Historical pass-pair analysis (`pass_pairs.py`)

**Data:**
- 164 candidate Sentinel-2 passes, 2025-03 to 2026-09, with a tile at or under 40% cloud. 147 were read and 17 rejected by the production gates.
- Each arm is read with the production pipeline, observed cells only (no fill).
- An arm counts on a pass when ≥ 30% of its lake cells and ≥ 30 cells were read.
- 1,366 consecutive pairs (≤ 12 days apart), and 1,024 *events* (a pass against the same arm's median over the prior 45 days' dry-week passes).

**Noise floor.** Two passes of unchanged water disagree by up to about ±0.14–0.18 log10 (×0.66–×1.38): atmosphere, glint, sensors A/B/C, and the tile aerosol. Pairs ≤ 6 days apart with no rain: p10 −0.185, p90 +0.141. Dry-week events: p10 −0.173, p90 +0.144. A real change has to beat that.

**Tributary arms: anomaly against the arm's own dry baseline, by rain in the 48 h before the pass** (catchment mean):

| Rain 48 h | Events | Median | p75 | Murkier beyond noise | Clearer beyond noise |
|---|---|---|---|---|---|
| < 0.1 in | 726 | ×0.93 | ×1.13 | 12% | 11% |
| 0.1–0.5 | 134 | ×0.98 | ×1.10 | 11% | 8% |
| 0.5–1.0 | 52 | ×0.84 | ×1.20 | 19% | 21% |
| ≥ 1.0 | 55 | ×0.86 | ×1.07 | 14% | 18% |

Fresh rain shows no effect at the pass. One likely reason is that a clear enough pass within 48 h of heavy rain is post-frontal, so selection is at work.

**By days since a ≥ 1 in day on the drainage:**

| Days | Events | Median | p75 | Murkier | Clearer |
|---|---|---|---|---|---|
| 0–1 | 44 | ×0.88 | ×1.20 | 18% | 14% |
| 2–3 | 65 | ×1.00 | ×1.66 | **34%** | 5% |
| 4–6 | 76 | ×0.99 | ×1.17 | 16% | 0% |
| 7–10 | 122 | ×0.96 | ×1.15 | 19% | 12% |

**Split by year, the timing does not replicate:**

| Days | 2025: n, median, murkier (p vs dry) | 2026: n, median, murkier (p) |
|---|---|---|
| 0–1 | 22, ×0.74, 5% (0.90) | 22, ×1.16, 14% (0.36) |
| 2–3 | 23, ×0.94, 13% (0.40) | 42, ×1.28, 26% (0.002) |
| 4–6 | 43, ×0.95, 16% (0.12) | 33, ×1.08, 12% (0.40) |
| 7–10 | 89, ×0.87, 6% (0.94) | 33, ×1.71, **45%** (< 0.001) |

2026's long tail is January's back-to-back storms. The 7–10 days after one inch-day is 2–3 days after the next.

**Other cuts:**
- **Arm size.** Small arms (< 3,000 cells, about 2.6 km²) respond more often and more strongly at 2–3 days (41%, p75 ×1.80) than large ones (27%, p75 ×1.55). The largest single responses against baseline, within 10 days of a ≥ 1 in day:
  - Crow Creek ×18 (large, 1 day after, 2026-02-12);
  - Boshart ×7.9;
  - Short ×7.4;
  - Archie ×7.3.
- **Antecedent wetness.** Consecutive pairs split by the 7 days before the first pass show no consistent difference. After ≥ 1 in, dry antecedent gives 19% murkier and wet gives 9%, the opposite of the physical expectation. Insufficient to call.
- **Recovery.** Clearer-than-baseline readings are rare 2–6 days after a storm (0–5%). The return to baseline cannot be timed: 2025 and 2026 disagree.
- **Main stem.** Only 3 events each at 0.5–1 in and ≥ 1 in of lake-surface rain: **insufficient evidence**.
- **Modeled (NWM-only) arms.** Where the model's own peak between passes was ≥ 3× its value at the first pass, 26% read murkier beyond noise (n = 82), against 12% for ≤ 1.5×. This is the one modeled-flow signal. It is relative to the model, never absolute.

**Conclusions**
- **Rain response magnitude:** not calibrated. The response is real and heavy-tailed (some arms ×3–8), but its arm-median size is within 1–2× the noise for most arms and events.
- **Wet vs dry antecedent:** insufficient evidence.
- **Recovery:** insufficient evidence for timing. The direction (clearing, not overshooting clear) holds.

---

## 7. Town Creek and South Sauty: the measured arms

Both are large embayments (7,569 and 13,960 lake cells).

| | Town Creek (03572900) | South Sauty (03572690) |
|---|---|---|
| Events with measured flow at pass ÷ baseline-pass flow < 1.5× | 29: ×0.92, murkier 17% | 13: ×1.03, murkier 15% |
| 1.5–3× | 16: ×0.99, 6% | 19: ×0.84, 0% |
| ≥ 3× | 16: ×0.98, **6%**, clearer 19% | 17: ×0.99, 12%, clearer 18% |
| Consecutive pairs, measured peak between passes ≥ 3× | 16: ×0.96, 0% murkier | 19: ×0.90, 5% |
| ≥ 1 in in the 48 h before a pass | 3 events: insufficient | 3 events: insufficient |

**Even at three or more times base flow, neither arm's median moved beyond noise more often than in dry weeks.** On 2026-01-11, Town Creek was running 488 cfs (peak 792, ×33 its pass value) and its median went 2.73 → 3.37 FNU, inside the noise. South Sauty on the same pass went 2.69 → 4.05 (beyond noise). These embayments are large enough that a creek's plume is local to the head. **An arm-median state cannot see it (a stated limitation of every state), and that is the case for Stage 3.** Compared with the NWM-only small arms (§6), the measured arms respond less often. That is a size effect, not a provenance effect: the two gauged creeks are the two largest arms.

---

## 8. NWM against USGS (`nwm_vs_usgs.py`, 584 days, 16Z daily)

| | Town Creek, reach 19649040 | South Sauty, reach 19648816 |
|---|---|---|
| Median NWM ÷ USGS | 1.18 | 2.89 |
| 10th–90th percentile | 0.70–3.24 | 1.56–17.3 |
| Within ±30% | 54% of days | 1.5% |
| Within 2× | 79% | 27% |
| Low flow (USGS lowest third) | ×1.84 | ×9.74 |
| High flow (highest third) | ×1.12 (79% within ±30%) | ×1.89 |
| Rank correlation | 0.895 | 0.913 |
| Gauge doubled day over day / model also | 43 / 27 (63%) | 44 / 22 (50%) |
| Model doubled / gauge also | 38 / 27 (71%) | 27 / 22 (81%) |

Stage 1's single snapshot (model 14.5 vs gauge 25.8 cfs at Town Creek, 0.56×) was unrepresentative: on most days the model reads high. **What the model gets right is the ordering of flows, not their size.** So Stage 2 uses a modeled series only relative to its own value at the pass, labels it `modeledNWM` everywhere, and lets a model rise alone indicate at most `moderateRunoff`. The hourly job now logs both values every hour at the two gauged arms, so this comparison keeps growing.

---

## 9. Main-stem state

**Inputs:**
- the main-stem scene (cells outside every arm);
- rain on the reservoir surface;
- Nickajack's release: the 24 h mean now, around the pass, and its trend;
- Guntersville's release: now and trend.

The release is TVA's hourly record (48 h) plus the hourly job's log from 2026-09-27 on. **No velocity and no plume travel time:** `currentVelocity` is stated as unknown, the limitations say so, and a test forbids speed or arrival fields. Rain over the Tennessee basin above Nickajack is not included; it arrives only through the release.

**History:** TVA publishes 48 h, and none of the four USGS main-stem discharge sites (03570525, 03571850, 03573500, 03575500) returns data. So release at historical passes is unavailable. The main stem's replay uses its scene and lake-surface rain only, and says so.

**Live, 2026-09-27:**
- scene 2026-09-20, 34% of the main stem read, moderate anchor, 4.2 FNU → ~4.4 ft (2.0–14.7);
- 0.31 in on the reservoir surface since the scene → `minorChange`, authority moderate, magnitude satellite-supported;
- Nickajack 17,521 cfs (24 h mean, steady);
- Guntersville 21,170 cfs (steady);
- release at the pass not in the record.

---

## 10. Historical replay (`ClarityReplay`, `ClarityHistory`)

**How it runs:**
- It uses the engine's own state logic.
- It reads the record as of one minute before each next well-read pass: scenes taken before then, rain intervals that had ended by then, and flow valid by then.
- Daily rain totals end at 17Z, so the ~23.5 h before each ~16:30Z pass are not visible. That cost is taken rather than letting the replay see after the pass.
- The expected direction is compared with what the next pass read (beyond the pair noise floor, ±0.14).
- 1,316 pairs.

| Expected | n | Next pass murkier | Same | Clearer |
|---|---|---|---|---|
| murkier than the scene | 392 | 57 (15%) | 267 (68%) | 68 (17%) |
| same | 786 | 88 (11%) | 611 (78%) | 87 (11%) |
| clearer (the scene caught runoff) | 53 | 4 (8%) | 34 (64%) | 15 (28%) |
| unknown | 85 | 5 (6%) | 69 (81%) | 11 (13%) |

**By authority** (does the scene still hold?):

| Authority | n | Same | Median change (\|Δlog10\|) |
|---|---|---|---|
| high | 544 | 79% | 0.069 |
| moderate | 199 | 74% | 0.084 |
| low | 384 | 73% | 0.095 |
| none | 189 | 65% | 0.096 |

The ordering is right, and the spread is small.

**Targets:**

| Arm | Pairs | Expected murkier → murkier | Expected same → same |
|---|---|---|---|
| Town Creek (measured) | 61 | 1 / 19 | 29 / 38 |
| South Sauty (measured, partial catchment) | 65 | 1 / 22 | 30 / 39 |
| Browns (modeled, partial) | 76 | 3 / 24 | 38 / 51 |
| Yellow Creek (small, modeled, complete) | 59 | 4 / 24 | 26 / 33 |
| Boshart (small, model gives no value) | 53 | 1 / 20 | 25 / 33 |
| Main stem | 69 | 3 / 20 | 38 / 49 |

**Pass → rain → flow → next pass (from `replay.json`):**
- **Town Creek, Jan 2026.**
  - Jan 1 scene: 2.73 FNU, strong.
  - Jan 8–10: 2.24 in on the drainage. The gauge went from 23.9 to 395 cfs on Jan 10, peaking at 792.
  - State on Jan 10: `majorRunoff`, authority none, murkier expected.
  - Jan 11 pass: 3.37 FNU, +0.09, inside the noise. *Direction not confirmed.*
  - Then Jan 13 → 16, stable with the gauge falling 186 → 101: +0.16. *Murkier while the state said "same"*, a late spread the arm state cannot anticipate.
- **South Sauty, same storm.**
  - Jan 1: 2.69 FNU.
  - 2.21 in (partial catchment). The gauge went from 8.8 to 162 cfs (×18). `majorRunoff`.
  - Jan 11: 4.05, +0.18. *Correct.*
- **Browns.**
  - Jan 1 → Jan 11: 2.78 in; NWM 0.35 → 9.9 cfs (×28, modeled); major. The next pass read +0.18. *Correct.*
  - Jan 21 → 28: 2.66 in, NWM peak ×192, `recovering`. The next pass read −0.04. *Missed.*
- **Yellow Creek.**
  - Mar 12 → 17, 2025: 2.82 in, NWM ×14, major. ×3.0. *Correct.*
  - Apr 8 → 13: the scene caught runoff, and the state said *clearer*. It read ×0.40. *Correct.*
  - Aug 31 → Sep 5: 1.24 in. ×2.2. *Correct.*
  - Oct 23 → Nov 4: 2.28 in, major. It read ×0.55 *clearer*. *Missed.*
- **Boshart (no flow).**
  - Jan 16 → 28: 2.53 in, major. 3.02 → 17.4 FNU (×5.8), the largest change in the record. *Correct.*
  - Jan 1 → 11: 2.38 in. +0.02. *Missed.*
- **Main stem.**
  - Jan 1 → 11: 2.38 in on the lake. +0.16. *Correct.*
  - Jan 21 → 28: 2.0 in. +0.16. *Correct.*
  - No release history.

**Reading it:** the state's hydrology is right about *what happened on the land*. Whether that shows in the arm's median at the next clear pass is close to a coin that lands "no change" most of the time. That is why the direction is a warning, not a forecast, and the feet never move.

---

## 11. Live provenance read-out (item 11)

`ClarityStateDebug.lines`, from `GET /clarity/states` against the live bucket, 2026-09-27 ~22Z (scene 2026-09-20; the Sep 21–23 storm since). **Town Creek:**

```
Town Creek (town-creek-marshall)
Satellite: 2026-09-20 · 72% observed, 28% filled (median 100 m from a reading) · anchor strong
At-pass visibility: ~5.1 ft (likely 2.2–16.9) from 3.4 FNU median
Rain since pass: 1.18 in over the complete catchment (record to 2026-09-27T20Z)
Flow: 25.8 cfs measured (USGS 03572900 TOWN CREEK NEAR GERALDINE AL), 0.6 cfs at the pass, rising
Antecedent: 0.25 in in the 7 days before the pass
Runoff state: majorRunoff (murkierThanPass, magnitude uncalibrated)
Satellite authority: none — major runoff since the scene: it no longer describes this water
Current magnitude: baseline ~4.0 ft, not adjusted (rain-decay-v0: /conditions at 34.6948, -85.9208: Rain-decay estimate from MRMS rain over the surrounding area, 0.00 in in 72 h.)
Warning: Runoff since the satellite scene: the water may be murkier than it showed. Historically this appeared at the next clear pass in a minority of cases; Sector has no calibrated size for it.
Confidence: low (major runoff: direction only)
Limitations: One state for the whole arm: a plume at the creek's head is not resolved from the rest of the arm. The runoff state is a hydrologic statement; its direction is not validated as a clarity change and it has no calibrated size.
```

**Browns Creek** (never Town Creek's gauge):

```
Browns Creek (browns-creek)
Satellite: 2026-09-20 · 86% observed, 14% filled (median 100 m from a reading) · anchor strong
At-pass visibility: ~4.1 ft (likely 1.8–13.7) from 4.7 FNU median
Rain since pass: 0.57 in over the partial catchment (record to 2026-09-27T20Z)
Flow: 0.3 cfs modeled NWM (NWM reach 19649500, analysis), at the pass not reconstructable, steady
Antecedent: 0.01 in in the 7 days before the pass
Runoff state: moderateRunoff (murkierThanPass, magnitude uncalibrated)
Satellite authority: low — runoff since the scene
Current magnitude: baseline ~4.0 ft, not adjusted (rain-decay-v0: /conditions at 34.6948, -85.9208: Rain-decay estimate from MRMS rain over the surrounding area, 0.00 in in 72 h.)
Warning: Runoff since the satellite scene: the water may be murkier than it showed. Historically this appeared at the next clear pass in a minority of cases; Sector has no calibrated size for it.
Confidence: low (runoff moderateRunoff: direction only; partial catchment: rain around the embayment itself is missing; flow is modeled (NWM), not measured)
Limitations: Rain is over the drainage above the embayment's head only; the land around the embayment is missing. Flow is the National Water Model's analysis, not a measurement. Flow: no modeledNWM value within 13 h of the pass. One state for the whole arm: a plume at the creek's head is not resolved from the rest of the arm. The runoff state is a hydrologic statement; its direction is not validated as a clarity change and it has no calibrated size.
```

**South Sauty, Baker Spring, main stem and every other arm:** in `stage2/states_live.2026-09-27.json`. Every arm is in the `debug` map of the response.

**All 68 arms at that moment:**

| | Counts |
|---|---|
| Runoff | stable 4, minorChange 14, moderateRunoff 8, majorRunoff 3, recovering 1, unknown 38 (no scene of the arm) |
| Authority | high 2, moderate 15, low 10, none 41 |
| Confidence | medium 5, low 19, veryLow 44 |
| Flow | measuredUSGS 2, modeledNWM 55, unavailable 11 |

A week after the Sep 21–23 storm, with a scene that read 36% of the lake, the honest answer for most arms is "low" or "very low". That is the state reporting what it knows, not a fault.

---

## 12. API

- `SectorEngineAPI.currentClarityState(lakeId:lat:lon:)`: coordinate → arm or main stem (`HydrologyArmGrid.membership`, through water) → state. It returns `outsideGraph` or `notWater` otherwise. The baseline is `/conditions` at that point.
- `SectorEngineAPI.clarityStates(lakeId:)`: every arm and the main stem. The baseline is the engine's number at the lake's centre (one render, not 69).
- Routes `GET /clarity/state?lake=&lat=&lon=` and `GET /clarity/states?lake=` are registered **only when `SECTOR_STAGE2_ROUTES=1`**. A deploy of this branch does not publish them. `SECTOR_LAKE_SURFACE_BASE` points the loader at a local copy of the bucket.
- **What goes live next needs your approval:** the daily clarity job writing `lakes/<slug>/clarity/arms/<date>.json` and `latest.json` (`arm_anchor.py` after each pass). Today the per-arm anchor file exists only locally.

---

## 13. Tests (`ClarityStateTests`, 16; engine suite 136/136)

| # | Requirement | Test |
|---|---|---|
| 1 | Dry, stable: strong authority retained, at 3, 12 and 28 days old | `testDryStableConditionsKeepStrongAuthorityLonger` |
| 2 | Town Creek rain → Town Creek, not South Sauty | `testRainInOneArmDoesNotReachItsNeighbour`, and `testTheCatchmentsBehindNeighbouringArmsAreSeparate` (the real MRMS weights: basins never overlap in a cell; rain on one basin's own cells gives the other exactly 0) |
| 3 | South Sauty rain → not Jagger Branch | the same weights test (South Sauty and Jagger) |
| 4 | Browns never borrows Town Creek's gauge | `testBrownsCreekNeverBorrowsTownCreeksGauge` (plus Stage 1's `ClarityGaugeTests`) |
| 5 | NWM never presents as measured | `testModeledFlowCannotPresentAsMeasured` (a stale gauge does not lend its label either) |
| 6 | Partial catchment lowers confidence | `testPartialCatchmentReducesConfidence` |
| 7 | No catchment → unknown, not zero | `testNoCatchmentMeansUnknownRainNotZero` (a gap in the record is unknown too) |
| 8 | A new scene resets authority | `testANewSceneResetsAuthority` |
| 9 | Large divergence lowers authority | `testLargeRainAndFlowDivergenceLowersAuthority` |
| 10 | An old stable scene outranks a new pre-storm scene | `testAnOldStableSceneOutranksANewSceneBeforeAStorm` |
| 11 | Main stem invents no velocity | `testMainStemInventsNoVelocity` |
| 12 | Uncalibrated runoff cannot move the feet | `testUncalibratedRunoffCannotMoveTheFeet` |
| 13 | Replay never reads the future | `testReplayNeverReadsTheFuture` (a future scene, storm and flood change nothing; a daily total ending after t is excluded whole) |
| 14 | Coordinate → arm follows the water | `testCoordinateLookupFollowsTheWater` (all 12 Stage 1 peninsula points: a few hundred metres over land, 10–15 km through water) |
| 15 | Production scoring unchanged | `testProductionScoringIgnoresTheArmState` (score identical; no scoring source or `SectorEngineAPI` refers to the state engine). Fish Attraction and Huntability are iOS, and no iOS code changed for Stage 2. |
| + | The scene that caught runoff reads "clearer" once flow falls | `testASceneThatCaughtRunoffIsMarkedClearerNowOnceFlowFalls` |

---

## 14. What is calibrated

- **Visibility conversion** (Stage 1, `secchi-power-v1`) and its 80% range; the fill error by distance.
- **The noise floor** between two passes of unchanged water: about ±0.14–0.18 log10.
- **NWM against USGS** at both gauged arms: bias, spread, rank skill and event hit rates, over 584 days.
- **That runoff does make arms murkier sometimes:** 34% of events 2–3 days after a ≥ 1 in day, against 10–12% in dry weeks (pooled). More often and more strongly in small arms.
- **The state's own skill** as measured by the replay (§10).

## 15. What remains qualitative

- Every runoff threshold (0.10 / 0.50 / 1.00 in; 1.5 / 2 / 5× flow; 1.5 / 2 / 3× release), the modeled cap, and the recovery rules.
- The anchor-strength rules (50% read, 500 m, 25 / 10 cells).
- The confidence ladder.
- **Magnitude:** no size is attached to any runoff state.
- **Timing:** when a storm shows, and when it has gone.
- Antecedent wetness.
- **The main stem's response to release changes:** no release history exists to test it.

---

## 16. What Stage 3 may safely spatialize

**Safe:**
- **The arm graph and membership:** the through-water lattice, 68 arms and 40 main-stem regions.
- **Each arm's inputs, with provenance:** catchment rain (complete, partial or unavailable), measured or modeled flow, and TVA releases.
- **The per-cell satellite evidence** already in the product (read, cloud-hidden, unreadable, grass; distance to a reading).
- **The authority rule's shape:** evidence, not age.

**Where the case for spatialising is strongest:**
- **Within big embayments.** Town Creek at ×33 flow moved its median inside the noise. The plume is at the head, and only a within-arm field can show it.
- **Small arms,** where the whole arm responds (×3–8).

**Not yet safe:**
- any storm-effect magnitude or timing (§6);
- any direction as a forecast (§10);
- anything about release-driven main-stem change (no history);
- anything from the two NWM ids with no model values (§4).

**Before Stage 3 builds a field from runoff**, the replay should be re-run with hourly MRMS, so the day before each pass is visible, and with the production fill distances for historical passes.

**STOP. Stage 3 not started.**
