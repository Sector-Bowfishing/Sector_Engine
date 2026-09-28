# Android: retiring the local clarity formula

Clarity Fusion Stage 5, item 18. **A plan; nothing on Android has changed.** It does not block the iOS beta, but Android must not stay a second clarity system.

Paths are in `SectorAndroid`, relative to `app/src/main/java/io/sector/co`, on trunk `origin/Michael-Master`. The audit ran on `feat/new-tournament-wizard`, one commit behind.

## What Android has today

**No local clarity score.** The score's clarity factor already comes from the server's `/conditions`. What Android has locally is **display**, and it invents values in three places.

### The independent formula: `conditions/ClarityModel.kt`
- **Constants (lines 26–46):**
  - base 4.0 ft;
  - decay 0.9 for tailwaters, 0.4 for reservoirs;
  - reservoir floor 0.9 ft (the engine's is 1.1);
  - the curve `[(0,0),(1,.15),(2,.45),(3,.75),(4,.92),(8,1.0)]`;
  - `ESTIMATED_CLARITY_CAP = 0.70` (`BowfishingConditions.kt:73`).
- **Functions:** `visibilityFt` :52, `score` :66, `label` :76 (`"~%.1f ft viz"`).
- **Inputs:**
  - Tailwater comes from `GenerationWiring.isTailwater`, which is a dam within 3 mi (`generation/GenerationWiring.kt:32,48-51`).
  - Rain comes from `recentRainfall` in the engine response.

### Where it shows
| Surface | Place | Problem |
|---|---|---|
| Clarity sheet | `WeatherMetricDetail.kt:1104-1173` `ClarityDetailSheet` | `rain48 ?: 0.0` (:1109) renders **"~4.0 ft · Clear" with no data**; "Baseline ~4.0 ft clear" (:1150); `clarityWord` 70/45/20 (:1262-1267). The chart never draws (the forecast is emptied at `ShootingConditionsCache.kt:352`). |
| Tonight's Window factor card | `ConditionsPremiumSections.kt:444-451` | "~X ft of sightline (est.)", a Clear/Murky chip at 0.45; no unknown state |
| Dashboard tile strip / Conditions rows | `ConditionsDetailScreen.kt:1354-1362` `rowData` | `clarityFactor?.score ?: 0.5` shows **"Fair"** when the factor is missing |
| Score-card driver words | `DashboardScoreCard.kt:239` | "clear water" / "murky water" |
| Limiter / verdict | `ConditionsDtoMapping.kt:52-53` → `LakeConditionsScreen.kt:256`, `ConditionsDetailScreen.kt:734` | can headline the clarity factor's `why` |
| Where To Go | `WhereToGoScreen.kt:69` | passes a hard-coded target clarity **"Fair"** into `TripRecall.rankSpots`, at weight 0.20 (`TripRecall.kt:195-199`) |

- **No map, Fish Intel, Huntability or Priority Areas on Android.** There is nothing to migrate there. A Water Clarity layer would be new work.
- Trips store a user-picked Clear/Fair/Stained. That isn't a formula, but it defaults to "Fair" (`LogTripScreen.kt:133`, `TripConditionsCapture.kt:26`, `TripComponents.kt:131`).

### What to build on
- **Engine client:** `conditions/EngineApiClient.kt` (`BASE_URL` :28, OkHttp :33, `conditions()` :142, `parse()` :211, 10-minute memo :284).
  - It ignores `resolvedLake {id,name,state}` from `/conditions`, although that id format (`"Guntersville|AL"`) already matches `DirectoryLake.id` (`LakeDirectory.kt:59`).
- **Unmerged `fix/engine-client-resilience`** (worktree `SectorAndroid-engine-client`):
  - adds `EngineCore.kt` (`EngineGate`, `EngineFetch`, `MemoTable`) and `EngineCopy.CLARITY_UNAVAILABLE`;
  - already makes the `rowData` clarity row honest about a missing factor;
  - needs a rebase onto #46.
- **Gating:**
  - `MASTER_ROLE = "master"` (`subscription/SubscriptionPlan.kt:29`) via `user.auth`;
  - a master-only Diagnostics screen (`admin/DiagnosticsScreen.kt:74`);
  - the only remote switch is the RTDB `appConfig/android` read (`utils/AppUpdateGate.kt:52-57`).

## Order

0. **Prerequisites.**
   - Rebase and merge `fix/engine-client-resilience`.
   - The engine's clarity routes must be on the service Android calls. Until the cutover, the beta reads the review tag URL, like iOS.
1. **Flag.** `conditions/clarity/ClarityFlags.kt`:
   - a SharedPreferences `currentClarityBeta`, effective for masters only, **on by default for them** (the iOS rule);
   - a kill switch at `appConfig/android/currentClarity`;
   - the toggle in `DiagnosticsScreen`.
2. **DTOs and client.**
   - `conditions/clarity/CurrentClarityDto.kt`: the estimate, lake summary (with `overview`, `confidenceLabels`, `freshness`) and change types. Unknown enum strings decode to "none".
   - `CurrentClarityClient.kt` for the four routes, reusing the engine gate and client, with a 15-minute memo and the composite's ETag.
   - A 404 or parse failure is **Unknown**, never a `ClarityModel` fallback.
   - Parse `resolvedLake`, falling back to the nearest directory lake, then the lake whose frame holds the point.
3. **Domain.**
   - A sealed `ClarityReading`: Supported / Unknown(reason) / Loading / Unavailable.
   - A presenter that only words the server's strings: no thresholds, no defaults, two tiers ("Moderate" / "Low").
   - Tests: E, F or grass produces no number and no category word.
   - A source-scan guard (like iOS `testNoNewIndependentClarityFormula`) so `ClarityModel` can only be referenced from a `legacy` package.
4. **Loading.** A `clarity` StateFlow on `ShootingConditionsCache`, filled after `/conditions` names the lake and cleared on a location change. The same on the lake-detail load.
5. **Surfaces**, each behind the flag, with the legacy path intact:
   - (a) A `CurrentClaritySheet`: the lake overview (share with a current estimate, "3–6 ft where known", "20% has changed since its last clear view", Sentinel-2 date). Open it from `ConditionsDetailScreen.kt:269` and `ConditionsPremiumSections.kt:462,683`. Rename the old sheet `LegacyClarityDetailSheet`.
   - (b) `rowData`: drop `?: 0.5`; unknown shows "—" with no word.
   - (c) The factor card row :444-451, and (d) the subtitle :763.
   - (e) Where the canonical answer has no supported magnitude, suppress the "clear/murky water" driver words and the clarity limiter.
   - (f) `WhereToGoScreen.kt:69`: pass null, not "Fair" (`TripRecall` already skips a null). Add a "Not recorded" trip option that still reads old records.
6. **Observation.** Log one analytics event per clarity fetch (supported / unknown / 404 / error, plus the evidence letter). Masters first, then everyone via `appConfig`, for a set period.
7. **Cutover and delete.** Remove:
   - `ClarityModel.kt` and its test, `ClarityDay`, `_clarityForecast`, `_isTailwater`;
   - `GenerationWiring.isTailwater`, `ESTIMATED_CLARITY_CAP`;
   - `WeatherMetricDetail.kt:1089-1285`, `ConditionsTile.CLARITY`;
   - then the flag.

   Until this step, turning the flag off is the rollback.
8. **Water Clarity map layer.** Separate, new work. Decode `/clarity/current/cells` (gzip, ETag; format in the engine's `ClarityCells.swift`) into a layer, with the same presence rule as iOS.

## Parity with the iOS beta

Two confidence tiers. No lake-wide category word. Grass and changed water get no current number. The dashboard shows the lake overview, never a land point. Shared reports are opt-in, zone and hour only.
