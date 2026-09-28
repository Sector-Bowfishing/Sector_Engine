# /conditions clarity: the transition to Current Clarity

Clarity Fusion Stage 5, item 15. **This is a design. Nothing here is switched on.**

It waits on the Huntability beta validating the unknown-handling path.

## Today

`/conditions` always produces a clarity number, from `ClarityFactor`, model `rain-decay-v0`.

| Situation | Visibility | Where |
|---|---|---|
| USGS turbidity gauge within 10 mi, reading ≤ 6 h old | 11.123 · FNU^−0.637 (secchi-power-v1), overrides everything | `ClarityFactor.swift:23-29` |
| No rain data | 2.2 ft | `:38-40` |
| Tailwater | 4.0 · e^(−0.9 · rain) | `:43` |
| Reservoir | 4.0 · e^(−0.4 · rain) − up to 25% when the arm's creek is rising, floor 1.1 ft | `:45-56` |

- The base is `fallbackBaseClearFt = 4.0` (`ConditionsConfig.swift:101`).
- A dry, ungauged coordinate anywhere reads **~4.0 ft**, sub-score capped at **70**, with the words "Clear water — full sightline". This is the universal "~4.0 ft Clear" on the phones.

## Everything that assumes a number

### Engine

| # | Consumer | If clarity is unknown |
|---|---|---|
| 1 | Factor list, `ConditionsAggregator.swift:30` | Must become an optional insert, like water temp (`:55`) |
| 2 | Weighted blend, `:78-88` (clarity 0.26 / 0.20 spawn / 0.22 tailwater) | Weight goes to the others. **Dropping a sub-score capped at 70 raises the score whenever the rest average above 70**, so the ceiling (4) must bound it. |
| 3 | Breakdown rows / `weightPct`, `:116-129`, `:177-191` | Row leaves; percentages still sum to 100 |
| 4 | Seeability ceiling, `:198-215` (no gauge ⇒ component ≤ 0.85) | Needs an explicit unknown rule: `unknownClarityComponent = 0.85` keeps today's no-gauge ceiling |
| 5 | "Held back by clarity — ~X ft", `:139-153` | Needs "unknown" wording; never feet |
| 6 | Blown-out gate (< 1.0 ft), `ConditionsGates.swift:21-25` | Does not fire |
| 7 | Confidence (−20 with no gauge), `:239`, `:245-248` | Same penalty for unknown |
| 8 | Top reasons, `:282-298` (a dry 70 can headline "Clear water") | Leaves both lists |
| 9 | Where-to-look card, `WhereToLookEngine.swift:83-94` | No card |
| 10 | 7-night outlook, `ConditionsForecast.swift:547-632` (future nights re-project rain-decay) | Canonical clarity has no forecast (Stage 3B), so future nights are unknown |
| 11 | Hourly ribbon and Tonight curve, `:371-379`, `:684-731` | Follow the night's value automatically |
| 12 | `score()` / `batch` (My Lakes rings), `SectorEngineAPI.swift:481-519`, and the forecast base `ConditionsForecast.swift:267` | **Must read the same resolved clarity**, or the rings and tonight stop matching the gauge |
| 13 | `clarityVisibilityDTO.centralFt` is non-optional, `SectorEngineAPI.swift:448-476` | Becomes "what the score used"; nil when unknown |
| 14 | Stage 2 baseline, `ClarityStateAPI.swift:56-60` | Points at the explicit legacy field |
| 15 | `currentClarity(withLegacy:)` calls `conditions()` | If `/conditions` used canonical clarity through this function it would recurse. `/conditions` must call `world.estimate` directly. |

### Clients

- **iOS** would fail to decode a `null` clarity score. `Factor.score` and `NightFactor.sub` are non-optional `Int`, so a `null` sinks the **whole** response to the cache. Unknown must mean the factor is **absent**, never `null`.
- **iOS** shows made-up stand-ins where the factor is missing: "Fair" at score 50 (`FavoriteConditions`), 3.0 ft (`MetricSheets.clarityFeet`), 0.6 (`ScoreBreakdownSheet.clarity01`). The Stage 5 beta already replaces the first two for Guntersville.
- **Android:** `rowData` has a `?: 0.5` default, so a missing factor shows "Fair". See the Android plan.

A mechanism already exists for a missing factor: `presentKeys` plus weight redistribution (`ConditionsAggregator.swift:78-88`). Water temp, level, current and spawn use it. `dormantFactors` (a DTO that iOS already reads as optional) is a ready slot for "Clarity: unknown".

## The design

**Flag:** `SECTOR_CANONICAL_CLARITY_CONDITIONS=1`, per revision like the other clarity routes, so it can be A/B'd on a tagged revision. An optional Remote Config kill switch can sit beside `seeabilityEnabled`.

**One resolver, called from all three `build` sites** (`SectorEngineAPI.swift:371`, `:485`, `ConditionsForecast.swift:267`). It sets `ConditionsInput.clarity`, either *known* (feet, range, source, model) or *unknown* (reason), in this order:
1. **Turbidity gauge:** within 10 mi and 6 h, secchi-power-v1, nationwide. Unchanged.
2. **A lake with a Current Clarity world:** `world.estimate` at the coordinate.
   - Levels A–D give feet. E and F give unknown.
   - A coordinate on land (a town) takes its **lake's overview**, not the nearest pixel. With a current share below ½, it is unknown.
3. **Anything else:** unknown. Rain-decay is never scored again.

**Scoring when unknown:**
- `ClarityFactor.score` returns nil. The factor leaves `factors` and is listed in `dormantFactors` as "Clarity: unknown — why".
- Its weight is redistributed.
- No blown-out gate. The ceiling uses `unknownClarityComponent` (0.85).
- Confidence takes the no-gauge penalty.
- No "ft" in any reason. No where-to-look card. No `null` numbers.

**Future nights:** unknown under the flag. Tonight stays `evaluate(base)`, so every surface shows one number.

**Response:**
- `clarityVisibility` becomes what the score used; it is nil when unknown (already optional).
- New optional fields:
  - `clarityStatus`: measured / satellite / unknown.
  - `clarityCurrent`: the `CurrentClarityEstimate`.
  - `clarityLegacy`: `ClarityVisibilityDTO`, **always labelled rain-decay-v0, never scored**, kept for the migration period only.
- The `withLegacy` A/B and Stage 2's baseline repoint to `clarityLegacy`.

**Tests:**
- flag off: byte-for-byte unchanged;
- flag on, unknown: factor absent, percentages sum to 100, no gate, the fixed ceiling, the penalty, no "ft" in reasons;
- the gauge, batch and tonight all match;
- deliberate updates to `CurrentClarityTests:192` and `ClarityStateTests:314`, the review gates for adoption.

## Order

1. The Huntability beta validates unknown = renormalised (Stage 5 item 12).
2. iOS stops showing stand-ins for a missing clarity factor (3 sites above) and Android does the same (plan step 5b).
3. The engine lands the flag above, off.
4. **A/B across all 621 lakes on a tagged revision.** Only Guntersville has a world. Nearly every other ungauged lake goes to unknown with its 26% redistributed, and **scores can rise, not only fall.** Review the distribution before any traffic.
5. Canary, then cutover, then observe. `rain-decay-v0` stays as `clarityLegacy` until the observation period ends.

## Seen in passing (not changed)

- The forecast base does not pass `severeWarningLabel` (`ConditionsForecast.swift:267-282` against `SectorEngineAPI.swift:377`). During an NWS warning, the Tonight curve and tonight's row in the 7-night outlook are not capped at 25, while the main gauge is.
- `clarityGauges[].driving` checks distance only (`SectorEngineAPI.swift:426-427`). A gauge within range but more than 6 h old shows as driving while rain-decay ran.
