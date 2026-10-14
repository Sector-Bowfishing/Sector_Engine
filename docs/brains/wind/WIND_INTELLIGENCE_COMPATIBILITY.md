# Wind final proposal vs Intelligence evidence-layer expectations

Compared read-only: Wind `WIND_INTELLIGENCE_CONTRACT_FINAL_PROPOSAL.md` + code on `feat/wind-brain-adoption` **vs** Intelligence `origin/feat/intelligence-evidence-layer` @ `e9e5e571` (`docs/brains/SECTOR_INTELLIGENCE_EVIDENCE_LAYER.md`, `jobs/sector-intelligence-brain/{evidence,evaluation}.py`). **Neither Intelligence nor Wind code was changed to make them match.** This is the reconciliation list for after the prerequisite branch resolves.

## Exact matches
| Topic | Intelligence expects | Wind provides | Result |
|---|---|---|---|
| Restate, never recompute | "Values are restated from the published state, never recomputed" | Wind owns direction/category/flag/exposure; contract says restate-or-combine | MATCH |
| UNKNOWN handling | UNKNOWN never improves a rating (E1); unknown deciding factor ⇒ UNRANKED | `null` = no claim; UNKNOWN banks never PROTECTED; `None` in `simple()` | MATCH (semantics aligned) |
| Value kinds | `kind` (analysis/modeled/forecast/…) sets base confidence (analysis/modeled/forecast = MEDIUM, proxy = LOW) | state `kind` ∈ analysis/forecast/unavailable; tonight `kind: forecast`; `evidence.kind MODELED_FORECAST` | MATCH |
| Current wind | factor `windSustainedMph` from `analysis.sustainedMph` (+ `gustMph`, `observation.*`) | all still published, unchanged | MATCH |
| Staleness | `stale` / `evidenceStale` / age vs `staleAfterHours` | `stale`, `staleReasons`, `tonight.freshness.stale` | MATCH (`evidenceStale` is not published by Wind) |
| Exposure not a factor value | `windExposure` is always UNKNOWN; lake-wide summary restated as `detail` only | Wind still publishes bank-scale detail only in storage | MATCH on purpose; this is the known gap |

## Field-name mismatches
1. **Brain confidence key.** Intelligence reads `state.confidence` (a string) or `state.engine.confidenceLabel` as `brainConfidence`. Wind has **no top-level `confidence`**; its label is `tonight.confidence.label`. Result today: `brainConfidence` is absent for Wind (no cap applied).
2. `exposure.protectedPct` / `exposedPct` (restated by Intelligence as `lakeSummaryRestated`) are the **frozen-CEM** shares (modelled Hm0 < 1 in / ≥ 6 in). Wind's new `exposure.bankImpact.protectedPct` uses a different definition (label PROTECTED = lee-facing or short fetch, chop ≤ 2). Same word, two meanings, in neighbouring objects.
3. Intelligence has no factor ids for Wind's new outputs: `tonight.speed.category`, `tonight.trend`, `tonight.breezyRisk`, `exposure.bankImpact`, `geometryTier`. They are simply ignored (additive fields), which is safe but unused.
4. `forecastHorizon`: Intelligence passes `horizons[factorId]` per factor (e.g. `windSustainedMph`); Wind publishes `forecast.horizonHours` (≤ 48 h) and `tonight.forecastHorizonHours`; the mapping is not specified on either side.

## Semantic mismatches (the important ones)
1. **Confidence means different things.** Intelligence's factor confidence is a 4-level product of kind, staleness, lead time and support level; if it ever consumed Wind's `HIGH/MEDIUM/LOW` as `brainConfidence` it would cap to that level — but Wind's label answers "how reliable is the direction / light-vs-calm call", **not** "how likely is strong wind" (HIGH nights are 3× likelier to reach 10 mph than MEDIUM-without-flag; `WIND_STRONG_WIND_RISK_FORMULATION.md`). Mapping it onto the `windSustainedMph` factor would be wrong; it should attach only to direction/category factors, and risk needs its own factor.
2. **"Now" vs "tonight".** Intelligence's wind factor is the **current analysis value** (RTMA-RU). Wind's tonight outputs are forecasts for 19:00–01:00 local. `lead_hours`/horizon logic in Intelligence treats a statement beyond the Brain's horizon as UNKNOWN; Wind's tonight block is inside horizon but is a *forecast*, which Intelligence caps at MEDIUM ("forecast statement: capped at MEDIUM") — consistent, but the factor needs a distinct id so "now" never stands in for "tonight".
3. **Numeric vs category.** Biological `responseBands` for wind are numeric cutpoints on `sustainedMph`. Wind's tonight speed is a **floor category** (observed wind > 10 mph ran 4.6–6 mph above forecast; `ifItBlows` is not a ceiling). Numeric bands applied to the NBM mean would systematically under-warn; bands for tonight should be categorical (calm/light/breezy/windy) plus the risk flag.
4. **Tier/vocabulary.** ESTIMATED geometry may only say EXPOSED/PROTECTED; Intelligence has no notion of tier, so a categorical `windBankExposure` band would see DIRECT/CROSS (AUDITED) and EXPOSED (ESTIMATED) as different vocabularies unless the factor defines both.
5. **Support level.** Intelligence treats every pilot state as `LAKE` support and caps area decisions at MEDIUM. Bank-scale Wind (zones) would be the first `ZONE`-support Brain; the shape of a zone query (bank ids vs polygons vs a Wind-owned zone service) is undefined.
6. **Evidence stale.** Intelligence honours `evidenceStale`; Wind has no equivalent for "validation frozen/ESTIMATED"; `validationTier` would be the natural carrier.

## Confidence handling — proposed reconciliation (future work, after the prerequisite branch)
- Wind adds **separate** fields rather than overloading one: `forecastConfidence` (today's tonight.confidence) and `windRisk` (null/ELEVATED/HIGH). Intelligence attaches `forecastConfidence` as `brainConfidence` only to direction/category factors.
- Intelligence adds factors: `windTonightCategory` (categorical), `windBreezyRisk` (categorical), `windTrend` (categorical: easing/steady/none), `windBankExposure` (categorical per zone; vocabulary by tier), with `kind: forecast`/`modeled` and the validation tier as an additional confidence cap (ESTIMATED ⇒ at most LOW/MEDIUM).
- Keep E1 intact: absent flag/`null` ⇒ UNKNOWN factor, never "no risk".

## UNKNOWN handling check
| Wind output | Intelligence mapping | Safe? |
|---|---|---|
| `tonight.direction.shown=false` | direction UNKNOWN | yes |
| `breezyRisk.flag=null/false` | no statement | yes — but must not become "low risk" |
| bank `UNKNOWN` | `windExposure` UNKNOWN | yes |
| lake blocked/POINT_ONLY | no exposure object | yes |
| `tonight.available=false` | tonight factors UNKNOWN | yes |

## Future reconciliation work (owners)
1. Wind: publish the new fields (blocked on the prerequisite branch), add `forecastConfidence`/`windRisk` naming decision, rename or document the two `protectedPct`s.
2. Intelligence (not edited here): new factor ids and band schemas, `brainConfidence` source for Wind, `ZONE` support contract.
3. Both: one versioned fixture set (`docs/brains/wind/fixtures/*`) used by tests on both sides; Ops schema/rules for the new nodes.
