# Clarity Fusion Stage 5: production cutover

2026-09-28. Guntersville only.

**Verdict: NOT READY. The blockers are listed at the end.** The engineering is done and verified in the cloud. What remains is your review of the A/Bs, a TestFlight beta in your hands, two production approvals, and one device measurement.

**Production is unchanged:**
- Public traffic is 100% on `sector-engine-00044-b6m` (`be1d893`).
- No shipped app reads the new routes.
- Nothing scores from them for anyone but the beta.

What runs now:

| Piece | State |
|---|---|
| Review revision | `sector-engine-00067-vol`, tag **`clarity`**, 0% traffic, `SECTOR_CURRENT_CLARITY_ROUTES=1`, commit `19b7fa0` |
| Daily job `lake-surface-daily` | redeployed (image `1e2c41a5…`, commit `0a086e5`); publishes per-scene cells, arm anchors and history |
| Hourly job `hydrology-hourly` | unchanged code; 45-day backfill done; schedule resumed |
| **New** hourly job `clarity-current-hourly` | prepares the world at :40 UTC from the review image (`25cecd31…`) |
| Bucket | 11 Guntersville scenes with cells and anchors; `clarity/current/Guntersville_AL/` prepared world |
| iOS | beta for master accounts on `feat/clarity-production` (not yet in a TestFlight build) |
| Dev RTDB | shared-report rules deployed (dev only) |

---

## 1. Commits

**Stage 4 (recorded before any deploy):**
- Engine `d52b7ac` (code `8e3980b` / `7480998` / `bc55527`), PR Sector-Bowfishing/Sector_Engine#14.
- iOS `d88efd4c`, merged to Michael-Master via Sector-Bowfishing/iOS_Sector#213 (`afc0095e`).
- Stage 4 tests: engine 160/160; Linux smoke passed; iOS 736 run, 1 skipped, 0 failed.
- **Production rollback:** `sector-engine-00044-b6m` = `be1d893` (tag `deployed/sector-engine-00044-b6m`).

**Stage 5, engine** (`Sector_Engine-fusion`, branch `feat/clarity-production`, pushed):

| Commit | What |
|---|---|
| `27b08af` | job: `--pass-dates` history backfill; the index stays whole with `--lakes` |
| `c5a8604` | grass beds have no supported magnitude; stricter High, **frozen before the replay** |
| `fe69121` | job: arm anchors name the lake and the product's bucket path |
| `ecec8e6` | prepared worlds, the precompute job, gzip delivery, lake overview, two user-facing tiers |
| `0a086e5` | fixes: the hourly record always reads today; a failed read never empties a history |
| `19b7fa0` | cloud check (map and tap agree) — **the review revision's source** |
| `7067c9b`, `49f3944` | docs, data, screens, the hourly job's deploy script |

**Stage 5, iOS** (`Sector-mapbox`, branch `feat/clarity-production`, pushed; not merged):

| Commit | What |
|---|---|
| `928aa134` | the beta gate, two tiers, grass, lake overview on the clarity surfaces, opt-in sharing, rules, the formula guard |
| `aada7eaa` | Sector Intelligence A/B test; composite load-time log |
| `d9490e01` | canonical Huntability on for the beta; the shipped pass is never drawn as current |

No deployed service runs uncommitted source.

## 2. The daily data product

**Redeployed** three times. Each deploy fixed something the live runs found:
- the index was cut down to the one lake when a run used `--lakes`;
- temp-path provenance in the arm anchors;
- a read error could empty the history.

**Byte-for-byte check against the Stage 4 mirror, pass 2026-09-20.** The cloud job ran its whole pipeline on that pass:
- `2026-09-20.cells.bin`: **identical** (sha256 `89102b7e…`).
- The product PNG is identical to what was published before, and the metadata differs only in `generatedOn`.
- The arm anchors differed only in `lakeId` (null) and `source` (a temp path). Both are fixed in `fe69121`.

**History:** the job published all 11 August–September scenes in 1,251 s, each with cells and anchors.
- `history.json` kept only 3 of the 11. The job's store turned any failed read into "no history" and wrote over it.
- The file was rebuilt from the scenes' own metadata; the 3 surviving entries matched the rebuild exactly.
- The store now raises on anything but a missing file.

**The bucket now holds everything `CurrentClarityResolver` reads:**
- `history.json` (11 passes);
- `arms/<date>.json` and `<date>.cells.bin` ×11;
- the 45-day hourly record;
- `catchments.json`.

The review revision serves from it (§8). The first *scheduled* daily run on the new image is tonight at 3 AM CT; not yet observed.

## 3. Hydrology backfill

Run as one execution with `BACKFILL_HOURS=1110`, with the hourly schedule paused so the two couldn't race; it filled 368 hours in about 7 minutes.

| | |
|---|---|
| Window | 1,110 h, 2026-08-13T14 → 2026-09-28T19 UTC |
| Rain | **complete for all 65 catchments** except the newest hour (MRMS hadn't published it), which stays unknown and fills next run |
| Missing hours | recorded as `null`, never 0 (`hourly_rain` returns None; the loader treats None as unknown) |
| Measured flow at a pass | read on demand from the USGS IV archive, so no backfill needed |
| Modeled NWM flow at a pass | only from 2026-09-27 (the hourly record's start); NWM-only arms have **unknown** flow change for older scenes, capped at moderate. This is the conservative direction. |

Data: `docs/data/hydrology/guntersville/stage5/hydrology_completeness.json`.

**A bug the backfill exposed:** the loader listed the hourly day files oldest first and stopped at 45. With a scene 46 days back, it dropped **today's** file, so rain ended a day early ("hydrology through Sep 27 23Z"). Fixed in `0a086e5` (newest first, capped at 47), with a test; the prepared world now reads "through 2026-09-28T19Z".

## 4. The precomputed world

- **`ClarityPrecompute`** is a second binary in the engine image. The hourly job `clarity-current-hourly` (:40 UTC) runs the routes' *own* live build, where no one waits for it, and publishes to `gs://sector-lake-surface/clarity/current/Guntersville_AL/`:
  - `composite-<etag>.bin` and `.bin.gz`: immutable, named by content, so a reader never pairs a new world with an old composite;
  - `changes.json`: each arm's hydrologic change since each of the last 13 whole hours (report freshness);
  - `world.json`, written last:
    - builtAt, index hash, ETag;
    - the scenes and each region's scene;
    - every region's hydrologic state, change since its scene and caps;
    - the outcome table as built;
    - notes;
    - provenance (hydrology-through, newest and oldest scene, engine commit, build seconds).
- **The routes** read `world.json` (re-checked every 60 s) and the composite. They **resolve each request at its own time**, so scene ages, the table and the 72 h boundary are the request's own. Nothing heavy runs per request.
- **Staleness, explicit:**

  | World age | Behaviour |
  |---|---|
  | ≤ 2 h | `freshness: current`, served as built |
  | 2–12 h | `stale`: every stable or minor drainage becomes **unknown** (caps at moderate, so nothing reads High), and each region says "Drainage last checked … the hourly update is late" |
  | > 12 h | **expired**: not served; the route falls back to a live build (`freshness: live`) |

- `/clarity/current/change` answers from the prepared marks, measured from the whole hour at or before the report (never less rain than the truth). Older than 13 h, it reads live.
- Tests: `PreparedClarityTests` (7) covers:
  - the composite round trip, and refusing a mismatched world;
  - the freshness thresholds and the stale downgrade;
  - the JSON round trip;
  - change marks;
  - the overview;
  - the hourly record reading today.
- **Linux smoke** runs the job from the image, and a second server on its output (checks freshness `current`, gzip served, tap and change on the prepared path).
- The job's builds took **4–44 s** in the cloud (live gauges vary). No user waits for that now.

## 5. Delivery

| | Size | Notes |
|---|---|---|
| Composite (SCCC) | 2,928,487 B | unchanged format; no value altered |
| gzip -9 (served) | **265,410 B (−91%)** | `Content-Encoding: gzip`, its own ETag `"<etag>-gz"`, `Vary: Accept-Encoding` |
| brotli 11 (not used) | 219,438 B | no server-side brotli; 17% more saving wasn't worth a dependency |
| static region/zone part alone, gz | 31 KB | not split out: too small to matter |

**Latency.** Cloud times are from this Mac to Cloud Run.

| Measure | Measured | Target | |
|---|---|---|---|
| `/clarity/current` tap, warm | p50 **0.079 s**, max 0.28 (n 48) | < 0.3 s | ✓ |
| `/clarity/current/lake`, warm | p50 0.245 s, max 0.44 | < 0.5 s | ✓ |
| composite gzip, warm | p50 0.162 s | < 0.5 s | ✓ |
| composite revalidation (304) | p50 0.080 s | < 0.2 s | ✓ |
| composite at ~10 Mbit/s (`curl --limit-rate`) | **0.17 s** gzip vs 2.21 s uncompressed | < 1 s | ✓ |
| first request on a fresh revision (loads the prepared world) | 0.87 s, then 0.23 s | < 2 s | ✓ |
| container cold start → first lake answer (Docker, same image) | health 0.13–2.1 s; prepared 0.33–0.75 s; **old live build 8.4–18.0 s** | < 3 s | ✓ |
| phone: summary + composite decode (sim, Debug) | 0.15 s; all 6,504 bank lookups 5 ms | < 0.5 s | ✓ |
| phone: fetch + decode in the app (sim, Debug) | 0.58–0.81 s | < 2 s | ✓ |
| **phone: paint (grid + 30 m lake image + PNG), sim, Debug** | **14.1 s** (twice) | < 3 s | **✗ unmeasured on device** |

- **Memory:** the decoded composite is 7 bytes × 415,214 cells ≈ 2.9 MB, plus the painted image. Not profiled.
- **The paint is the open latency item.** It is the same `AnswerField` pipeline the shipped layer uses, measured in an unoptimised Debug build on the simulator. It needs a Release or device measurement. It runs detached, at utility priority, and blocks nothing. Meanwhile the beta shows "Loading the latest usable observations…" rather than the old pass (§9).

## 6. Grass beds

Your call is adopted (`c5a8604`):
- `evidenceCap(.grassBed) = none`, so a bed cell resolves at level F: `magnitudeSupported=false`, no `centralFt`, no `lastSupported`.
- Card text: "Grass bed: the satellite reads the plants, not the water, so no visibility is supported here."
- The carried value survives only as a `rejected` composition item, for audit.
- Nothing grass-derived reaches Huntability: an unsupported magnitude becomes `.unknown`.
- The map draws beds as uncertain water, neutral grey, so the lake doesn't break apart. The Vegetation layer still shows the beds themselves. A report is the only way a bed can get clarity evidence.
- **29.4% of Guntersville's water is grass** on the chosen scenes. That is most of the 31.8% unsupported.
- On the untouched years, level F (which now includes grass) erred **0.177 log10 (1.31 ft)**, the worst of any group if it had been shown.

## 7. Confidence tiers: preregistered replay → two tiers

The candidate was frozen in `docs/clarity/stage5/CONFIDENCE_TIERS_PREREGISTRATION.md` and committed (`c5a8604`) **before** the replay ran.

**Stricter High:**
- a direct read, **scene ≤ 72 h**;
- a stable drainage;
- a complete catchment record;
- a usable flow record.

The replay used the same 225 validation and 141 discovery targets as Stage 4.

| Tier | Validation 2020–24 | Discovery 2025–26 |
|---|---|---|
| High (stricter) | 0.104 (25 targets, 40,907 cells) | 0.089 |
| Moderate | 0.127 | 0.103 |
| Low | 0.151 | 0.127 |

| Frozen check | Result |
|---|---|
| Sample (≥ 20 targets, ≥ 10k cells) | pass |
| 95% paired interval of Moderate − High above 0 | **fail**: −0.001 to 0.045 |
| High ≤ 0.80 × Moderate | **fail**: 0.817 |
| Feet agree | pass: 0.75 vs 0.80 ft |
| Replicates on discovery | pass |

**Decision: two user-facing tiers.**
- **Moderate** covers internal high and moderate; **Low** is low.
- The API keeps `confidence` with the value `high` internally, plus `authority` and the level. The lake summary sends `confidenceLabels`, and nothing shows "High".
- The iOS meter has two bars. On the map, Moderate is full colour and Low is half.
- Stricter High *is* better in both sets, but it missed the margin set in advance. A later replay with more short-gap scene pairs can reopen this without a schema change.

## 8. Review deploy

- `gcloud run deploy --no-traffic --tag clarity`, same scaling as production (4 CPU, 2 GiB, concurrency 1, min 1, max 30). It was **not** `deploy.sh`, which relies on traffic staying pinned.
- The Linux smoke passed on `ecec8e6` before the first deploy, and on the final head `49f3944` after the second.
- Traffic after each deploy: `00044-b6m 100% (fusion)`, review revision 0% (`clarity`).

**Cloud check** (`scripts/hydrology/current_cloud_check.py`, output in `stage5/cloud_check_00067.json`): **all passed**.
- Summary freshness `current`; two tiers; overview present.
- Composite served gzip; 304 on revalidation; the identity form still served; the composite matches the index (415,214 cells).
- **Map and tap agree on 48 of 48 sampled cells.** These are 3 of every outcome kind that occurs, plus Town Creek, South Sauty and Browns Creek.
- Grass: never a number. E: the number is hidden and "last supported" is shown. Land (Guntersville town) and outside the lake: no number.
- Report change on the prepared path: 0.24 s.

**Named creeks (live):**
- **Town Creek:** "Last supported estimate ~5.0 ft · Not current · Major hydrologic change since observation · Town Creek flow substantially above its level at the observation (×48.5, measured, USGS 03572900) · 1.18 in of rain on its drainage since".
- **South Sauty head:** grass bed, no supported estimate.
- **Browns Creek:** direct read, changed since, last supported ~4.1 ft.

**Rollback drill:**
- The `clarity` tag was moved `00067 → 00066 → 00067`, about 2 minutes per move.
- The tag URL answered 200 after each move, and production traffic never moved.
- **Production rollback command:** `gcloud run services update-traffic sector-engine --region us-central1 --to-revisions sector-engine-00044-b6m=100`.
- **Job rollback:** `gcloud run jobs update lake-surface-daily --image …@sha256:e7281b40…`, the pre-Stage-5 image.

## 9. The beta gate (iOS)

- **Who:** master accounts (`CurrentUser.isMaster`), and every Debug build. `CurrentUser` records it on each account change, and signing out or a non-master account removes the device from the beta. Everyone else keeps exactly what shipped.
- **Default:** on for the beta, with a **Beta** section in the layer picker (Basemaps tab), visible in Release too:
  - Current Clarity: on;
  - Clarity run: opt-in;
  - Clarity in Huntability: on, after §12.
- **Endpoint:** the beta reads the review tag URL `https://clarity---sector-engine-e43utajroa-uc.a.run.app`. At cutover this becomes the service URL.
- **Beta users get:**
  - the canonical Water Clarity map and tap cards (source and confidence on each);
  - creek-head reports, with opt-in sharing;
  - the lake overview on the dashboard, Clarity sheet, night sheets and lake tile;
  - canonical Huntability.
- **No legacy presented as current:** in the beta the shipped Sep 20 pass is only the composite's template.
  - While the composite paints, the key reads "Loading the latest usable observations…" and a tap reads nothing.
  - If the composite can't be had: "Current Clarity is unavailable right now."
  - This applies only to lakes with a world (Guntersville).
- **Not yet in a build:** reaching a master's phone needs a TestFlight build with the build number bumped (`/ios-release`). That wasn't done.

## 10. Map acceptance: live screenshots

iPhone 17 Pro simulator, Debug build, against the review revision's live world (11 scenes, hydrology through Sep 28 19Z). All in `docs/clarity/stage5_screens/`.

| File | Shows |
|---|---|
| `00_lake_mid_reach.jpg` | whole mid-lake reach: vivid main river, faded Sauty arms |
| `06_upper_lake.jpg` | upper lake (Scottsboro): the clear main channel, uncertain water faded |
| `04_map_town_reach.jpg` | Guntersville town reach, with the compact legend |
| `12_town_creek_arm_changed.jpg` | large creek arm: Town Creek faded after the Sep 28 storm |
| `13_tap_town_creek_major_change.jpg` | Town Creek card: last supported ~5.0 ft, not current, ×48.5 measured USGS, 1.18 in |
| `07_tap_direct_stable_historical.jpg` | directly observed, stable historical: ~4.8 ft, likely 2.1–15.9, **Moderate**, observed 8 days ago |
| `11_tap_creek_back_filled.jpg` | creek back, nearby filled (100 m): ~4.9 ft, Moderate, "the satellite cannot read this water" |
| `08_tap_changed_E.jpg` | changed water: last supported ~4.6 ft, 0.57 in since, "not yet calibrated" |
| `09_tap_grass_bed.jpg` | grass bed: no supported estimate, why, and Report clarity |
| `10_unsupported_beyond_5km.jpg` | water > 5 km from a reading: uncoloured grey |
| `05_loading_no_shipped_pass.jpg` | while painting: "Loading the latest usable observations…", no old pass |
| `03_beta_section.jpg` | the Beta section |
| `01_dashboard_lake_overview_tile.jpg` | the dashboard tile: **4–6 ft · 49% known** |
| `02_clarity_sheet_lake_overview.jpg` | the Clarity sheet: 4–6 ft where it's known; 49% current, 20% changed since, last seen Sep 20 |

**Legend:** "Water Clarity · Clear ─── Muddy · Sentinel-2 · latest usable observations. Faded water is less certain." There's no large legend.

- Taps inside a BAA redzone open the redzone, not the clarity card. That's existing precedence, so I didn't change it. Those cells' cards were checked through the API instead (§8).

## 11. The dashboard: a lake, not a land point

- **The engine** adds `overview` to `/clarity/current/lake`: the lake cell by cell through the table.
  - Right now: **49% of the water has a current estimate** (Moderate 37.6%, Low 10.9%).
  - 3.7–5.6 ft where known (p10–p90; median 4.4).
  - **20% has changed since its last clear view.** 32% is unsupported, grass 29%.
  - Observations run Aug 21 – Sep 20.
- **iOS** `CanonicalLakeClarity` finds the lake for the dashboard's coordinate: the nearest directory lake, or the lake whose frame holds the point (a long reservoir's upper towns sit far from its directory point). The model publishes `canonicalClarity`.
- **In the beta:**
  - **Tile:** "4–6 ft · 49% known", a neutral colour, no Clear/Murky word.
  - **Clarity sheet:** range, share current, share changed, last seen, why. No rain chart.
  - **Night sheet:** clarity's score driver is named "Rain model, as the score reads it". The swing row says "not forecast" instead of an invented feet range.
  - **Lake tile:** the overview, no rain sparkline.
  - **Lake headline:** no longer leads with the rain model's number.
- The **score itself** still reads clarity from `/conditions` (rain-decay). §15 is that transition, and it isn't cut over.

## 12. The A/Bs

Live artifacts from the review revision. `stage5/ab_huntability_live.json.gz`, `stage5/ab_intelligence_live.json`, `stage5/current_lake_live_2026-09-28.json.gz`.

**Canonical vs legacy clarity (the lake):**
- Legacy gives **~4.0 ft "Clear" at every dry, ungauged point** on every lake.
- Canonical gives Guntersville:
  - 48.5% of the water a current number (3.7–5.6 ft, p10–p90);
  - 19.7% a last supported number only (drainage changed);
  - 31.8% no number (29.4% grass, the rest beyond 5 km or unread).
- Of 48 sampled cells, stratified by kind: 15 have a number (3.9–5.4 ft), and 33 are E or F.

**Huntability, 6,504 banks:**
- **4,333 (67%) have unsupported clarity**, so the factor is `.unknown` and reweighted, never muddy, clear or a neutral number. Stage 4 had 2,320; today's storm and the grass decision raise it.
- Score change on the calm test night: median 0, p10 −2, **max 0**, min −9. Unknown never raised a bank.
- Confidence: moderate everywhere before; with canonical clarity, low 666, moderate 5,838.
- **Tonight's conditions** (1 mph, 94% moon, 80°F): Prime 4,544 → 3,691, Good 323 → 1,175, Fair 0 → 1, Poor 1,637 → 1,637. The fake 4.0 ft had been lifting every bank's clarity factor to its maximum.

**Sector Intelligence and Priority Areas** (tonight's conditions):
- Recommendations 6,504 → 6,504; **0 recommendation-class changes** (startHere 1,452; secondaryOption 1,451; …).
- Priority Areas 22 → 22; bank runs 51 → 51.
- **Top Areas Tonight: identical, in the same order**: Main channel (13% of its banks unknown clarity), South Sauty Creek (100%), North Sauty Creek (100%).
- Unknown clarity lowered confidence and did not disqualify strong water. The areas stay three and lake-scale, not thousands of markers.

**Decision:** behaviourally sane and no invariant failed. **Canonical clarity in Huntability is on for the beta** (`d9490e01`). Fish Attraction is untouched.

## 13. Sector Intelligence

It receives clarity **only through `HuntabilityEngine.waterClarity`**. Verified by the code audit:
- attraction models, BiologicalState and `PriorityZoneBuilder` don't read clarity;
- the three rebuild paths (engines, conditions-only, wind scrub) all end in `PriorityZoneBuilder.build`.

The A/B above confirms it behaviourally.

**Remaining:** Learning's `RecommendationSession` still records the legacy `clarityFt` as `modelledClarityFt`, even with canonical clarity on. That is evaluation-only, but it should record the canonical bank value before observations accumulate.

## 14. iOS legacy clarity

In the beta, for Guntersville, these are **bypassed**:
- `MetricSheets` (the rain-decay chart, label parse, qualifier, ladder);
- `MyLakes` (tile and sparkline);
- `NightDetailSheet` (the invented feet range);
- `FavoriteConditions` (the tile's Clear/Fair/Murky);
- `LakeWhy` (the headline);
- `DashboardSheets` (the Tonight row);
- the map's shipped pass;
- Huntability's label-parsed clarity, replaced by the per-bank canonical value.

**Kept for rollback** until the cutover survives its observation period.

**Guard:** `testNoNewIndependentClarityFormula` fails if any other file gains a clarity-formula signature, or a listed one disappears without updating the list:
- the secchi-power coefficients;
- the rain-decay constants;
- label-to-feet parsers;
- score-to-clarity.

**Still legacy, outside the beta:**
- `ScoreBreakdownSheet.clarity01` colours the plan-view water from the clarity sub-score.
- `FishIntelMapStyle.visibilityFeet` is a hand copy of 11.123·FNU^−0.637 (legacy layer only).
- `defaultNight`'s 2.1 ft placeholder.
- The score breakdown's "~4.0 ft" row, which is the score's actual input until §15.

## 15. /conditions transition

A design and a full audit of every gate that assumes a number: `docs/clarity/stage5/CONDITIONS_TRANSITION.md`.
- **Flag:** `SECTOR_CANONICAL_CLARITY_CONDITIONS`.
- One resolver at all three build sites: gauge first, then the lake's world (an on-land coordinate takes the lake overview), else **unknown**.
- Unknown means the factor is **absent**, never `null`. iOS would fail to decode a `null`.
- Its weight is redistributed; a fixed ceiling of 0.85; the no-gauge confidence penalty; no feet in reasons; future nights unknown.
- `rain-decay-v0` survives only as the labelled `clarityLegacy`.
- **Must be A/B'd across all 621 lakes first:** every other ungauged lake goes unknown, and scores can rise.

**Not cut over, as specified.**

## 16. Reports

**Beta:** the existing workflow is on for beta users:
- private and local;
- intervals, method kept;
- the precise position is the owner's only;
- cell-local evidence;
- freshness from the prepared change marks.

**Shared backend, built and tested; in production it is off:**
- **Rules** (`database.rules.json`):
  - `clarityReports/{id}` holds the payload and nothing else: zone or region unit, hour-only time, interval, method, lights, source. No coordinate, note, photo or account.
  - `clarityReportOwners/{id}` records who sent it; masters only, for moderation.
  - `clarityReportThrottle/{uid}` allows one report a minute.
  - The rules check all three **in one write**, so an owner-less or unthrottled report is refused.
  - Masters can read, hide and delete; owners can delete their own.
  - Field validation: unit and hour formats, 0–30 ft, `low < high`, night/day methods only.
- **Emulator tests: 24/24** (`scratchpad` harness; run with JDK 21 and `firebase emulators:exec`).
- **Deployed to dev only.**
  - Live dev and prod rules were the Michael-Master file minus `fishIntelTrips` and `learningObservations` (merged today, never deployed), so dev now has those too.
  - Prod needs your approval, and the Web repo's copy must be mirrored (ADR 0002).
- **Client:**
  - explicit opt-in per report ("Share with Sector", default off, with the exact words of what leaves the phone);
  - `SharedClarityReportUploader`, multi-path, server timestamps;
  - `sharedAt` recorded so nothing is sent twice.
- No shared report has been written anywhere. Shared reports stay learning-only: no one else sees them.

## 17. Creek-head validation

`docs/clarity/stage5/CREEK_HEAD_VALIDATION_PROTOCOL.md` covers:
- Town Creek, South Sauty, Browns Creek, a vegetated head, and an open-water control;
- the Clarity run once per ~250 m and at the head;
- repeat pairs whatever the weather, and rain taken as it comes;
- counts required before any look;
- preregistered analyses only.

**Gap:** there's no export of the private reports yet.

## 18. Android

`docs/clarity/stage5/ANDROID_MIGRATION_PLAN.md` found **no local clarity score**: the factor comes from `/conditions`. There is a display-only formula (`ClarityModel.kt`), and **three places that invent a value**:
- "~4.0 ft · Clear" with no data;
- "Fair" at `?: 0.5`;
- Where To Go's hard-coded "Fair".

The plan has 9 ordered steps, from the flag (master, on by default) through DTOs and client, a presenter that only words server strings, a source-scan guard, the surfaces behind the flag, observation, and deletion. The map layer is separate new work.

## Tests

| Suite | Result |
|---|---|
| Engine `swift test` | **168/168** |
| Engine Linux smoke (image, every route; the job from the image; a server on its output) | **passed**, 24 checks, on the final head `49f3944` (same source as `19b7fa0` plus docs) |
| Engine cloud check vs `00067-vol` | all passed (48/48 map = tap) |
| Rules emulator | 24/24 |
| iOS full suite (live A/B artifacts) | 743 run, 741 passed, 1 skipped (pre-existing), 1 failed: the new Intelligence A/B's test night had no water temperature. Fixed. |
| iOS `CurrentClarityTests` after the fix | 16/16 |
| iOS full suite, final (iOS `d9490e01`, live A/B artifacts) | **743 run, 742 passed, 1 skipped (pre-existing), 0 failed** |

---

## 19. Production acceptance checklist

| Requirement | Status | Evidence / what's missing |
|---|---|---|
| All engine tests green | **PASS** | 168/168 |
| Full iOS suite green | **PASS** | 743 run, 742 passed, 1 skipped (pre-existing), 0 failed |
| Mandatory Linux smoke green | **PASS** | 24 checks on `49f3944`, including the job and the prepared path |
| Daily job healthy | **PENDING** | three manual runs OK; the first scheduled run on the new image is tonight 3 AM CT |
| Hourly job healthy | **PASS** | `hydrology-hourly` 21:17 and 22:18 after resume; `clarity-current-hourly` first scheduled run 22:41 OK (4.4 s build), picked up by the review revision |
| 45-day history complete enough | **PASS** (rain) / partial (NWM flow) | rain 1,110 h, all 65 catchments; NWM-at-pass only from Sep 27 (unknown, conservative) |
| Live composite generated | **PASS** | 11 scenes; 6 chosen; ETag 224d5f70 |
| Acceptable latency / payload | **FAIL (unmeasured)** | server and transfer pass every target; **phone paint 14 s in a Debug sim** needs a Release or device measurement |
| No stale world presented as current | **PASS** | freshness rules and tests; the beta never draws the shipped pass; stale worlds downgrade and say so |
| Direct / filled / E / F / grass verified | **PASS** | cloud check 48/48 plus screens |
| Confidence presentation validated | **PASS** | preregistered replay → two tiers; UI shows Moderate / Low only |
| Huntability A/B reviewed | **PENDING (you)** | produced (§12); needs your review |
| Priority Area changes reviewed | **PENDING (you)** | produced: none changed; needs your review |
| Dashboard no longer uses land-point clarity | **PASS (beta)** | tile, sheet, night sheets, lake tile; production users see it at cutover |
| Rollback tested | **PASS** | tag drill both ways; production pinned to 00044; job rollback image recorded |

## Remaining blockers (exact)

1. **Your review** of the Huntability and Priority Area A/Bs (§12).
2. **A TestFlight build** with the beta: bump the build number, `/ios-release`. Then **beta acceptance** on your phone, against the review tag.
3. **Paint time on a device or Release build.** It must be under about 3 s; if not, precompute the painted image in the job too.
4. **Tonight's scheduled daily run** on the new image must succeed. Check `lake-surface-daily` after 3 AM CT.
5. **Engine code to production:**
   - merge the stack (#10 → #14 → this branch; main is 15+ commits behind production);
   - route traffic to a revision built from it: canary, then 100%, with 00044 as rollback;
   - move the beta's URL from the tag to the service.
6. **Shared reports in production** (optional for launch): approve the prod rules deploy, and mirror `database.rules.json` to the Web repo.
7. **The observation period** after cutover, before deleting any legacy code. Watch:
   - endpoint errors;
   - job freshness (`world.json` `builtAt`);
   - payload and load latency;
   - the E/F share (high can be right);
   - Huntability and Priority Area shifts.
8. **Not blocking the Guntersville cutover**, but open:
   - the `/conditions` transition (§15), after the 621-lake A/B;
   - the Android plan (§18);
   - Learning records the legacy `clarityFt` (§13);
   - no report export (§17).

**Found and fixed in passing:**
- the loader dropped today's hydrology file;
- a failed job read emptied a history;
- temp-path provenance in anchors;
- the index was cut down by `--lakes`;
- the shipped pass was drawn in the beta while the composite painted;
- the Water clarity layer was hidden when the beta had no image at check time.

**Flagged, not fixed:** the forecast base doesn't pass `severeWarningLabel`, so tonight's curve isn't capped during an NWS warning (a task chip was created).

---

## NOT READY — BLOCKERS

- Huntability and Priority Area A/Bs await your review.
- No TestFlight beta yet, so no beta acceptance.
- Phone paint time is unmeasured outside a Debug simulator (14 s there).
- Tonight's scheduled daily run on the new image is not yet observed.
- The engine stack is not merged or routed to production traffic.
