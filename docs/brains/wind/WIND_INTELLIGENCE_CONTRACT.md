# Wind → Intelligence contract (Wind side)

Wind owns: wind direction, wind strength, wind forecast, bank exposure, fetch-derived exposure. Intelligence consumes the Wind state read-only and must not recompute wind science or thresholds. This file describes what the Wind Brain publishes (additively, in the shadow state); the active Intelligence branch is **not** edited.

## What Intelligence may read (`/lakes/{k}/states/wind`)
| Need | Field | Notes |
|---|---|---|
| Direction | `tonight.direction.{shown,fromDeg,fromCardinal,maxSpreadDeg}` | meteorological FROM; `shown=false` below 5 mph tonight mean; never invent a direction |
| Speed / category | `tonight.speed.{meanMph,category,ifItBlowsMph,ifItBlowsCategory}` and `sustainedMph`/`kind` for "now" | category is a floor for stronger winds (observed wind > 10 mph ran 4.6–6 mph above forecast) |
| Trend | `tonight.trend.label` ∈ `easing | steady | null` | `null` = no claim; never rising, never lay-down |
| Risk | `tonight.breezyRisk.{flag,p90MaxMph}` | `flag=null` = unknown (no recent percentile cycle) |
| Bank exposure | `exposure.bankImpact.{directPct,crossPct,protectedPct,highFetchPct,unknownPct}`, `tonight.exposure.{atMean,ifItBlows}`; per-bank rows in `bankDetailRef` (`bankImpact`, `highFetch`, `windAngleDeg`, `effectiveFetchM`, `exposureRank`, `confidence`, `geometryTier`) | MODELED; not measured |
| Fetch / exposure tier | `exposure.geometryTier` ∈ `AUDITED | ESTIMATED` (POINT_ONLY lakes publish no exposure) and `estimated`, `validated:false` | ESTIMATED must be shown as an estimate |
| Confidence | `tonight.confidence.{label,reasons}` ∈ HIGH / MEDIUM / LOW | frozen rule (H2 pre-reg); words only, no percentages |
| Freshness | `tonight.freshness.{forecastInit,forecastAgeHours,stale,percentileInit}`, `stale`, `staleReasons`, `provenance.generatedAt` | treat `stale=true` as "do not use for tonight" |
| Provenance | `provenance.{modelVersion,sources,qualityFlags,readiness}` | candidate model is SHADOW |

## Rules for consumers
1. Unknown stays unknown: `null` direction/risk/trend means no claim. UNKNOWN banks are never PROTECTED.
2. Do not combine Wind labels with other Brains inside Wind. Example for Intelligence (not Wind's job): bank DIRECT + HIGH FETCH (Wind) × shallow flat (Depth) × high resuspension sensitivity (Clarity) may be penalised by Intelligence. Wind does not say the water becomes muddy.
3. Do not present MODELED exposure as measured. Do not promote ESTIMATED geometry to validated.
4. Use `withheld` keys (`layDown`, `rising`, `gust`, `overWaterSpeed`, `directionBelow5mph`) as the list of claims Wind refuses to make.
5. `trend` (legacy field, ±2 mph at +3 h, includes `rising`) stays for compatibility and is **not validated**; use `tonight.trend`.

## Versioning
`tonight.schema = sector-wind-tonight-v1`. The state schema id (`sector-brain-wind-state-v1`) is unchanged because the block is additive; consumers must ignore unknown fields. Any rename or semantic change needs a v2 id.
