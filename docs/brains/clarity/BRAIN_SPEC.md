# Water Clarity Brain — BRAIN_SPEC

**Brain ID** `water-clarity` · **Slot** `waterClarity` · **Owner** Water Clarity · **Spec date** 2026-10-13
**Status** Conforms to Sector Brain Model v1 *concepts*; field names follow the shipped Brain Platform v1.0 contract and may migrate when the platform standardises.
Public-safe: status-level facts only. Detailed research results stay in the private overlay (`CLARITY_PRIVATE_CATALOG`).

## 1. Mission and decision
Tell a bowfisher **what the water looks like, where it is better, how current that answer is, and how much Sector trusts it** — for the decision *"can I likely see and shoot here tonight?"*

Questions the Brain must be able to answer, or refuse:

| Question | Answer shape |
|---|---|
| Can I likely see/shoot here tonight? | visibility estimate (ft, Secchi-equivalent) + range if validated + readiness |
| Which part of the lake is clearer? | map layer reference + coverage + age (never a raster in state) |
| Better or worse than before? | `trend` with basis; `UNKNOWN` when no basis |
| How confident is Sector? | reason codes (§8), not one number |
| Is the observation too old/cloudy/unreliable? | `satellite.status` + `reasonCode`; refusal states (§9) |

## 2. Owns / does not own
**Owns:** clarity evidence, clarity state, confidence, provenance, freshness, refusal logic, clarity-specific derived intelligence (visibility estimate, scene qualification, clarity layers).
**Does not own:** lake identity/geometry (Lake), water temperature, wind, depth, vegetation, species biology, recommendations (Sector Intelligence), Ops labels (Sector Ops).

## 3. Dependencies and consumers
| Upstream | Level | Use |
|---|---|---|
| Lake Brain / lake directory (`/lakes`, outlines) | consumed contract | canonical ID, outline for scene reads |
| USGS turbidity gauges (via Engine `/conditions`) | L1 provider truth | in-situ turbidity → visibility (L2 deterministic conversion, `secchi-power-v1`) |
| NOAA MRMS / Open-Meteo precipitation | L1 provider truth | rain input to `rain-decay-v0` (L3 heuristic) |
| Sentinel-2 L2A via STAC (`lake-surface-dispatch` → `lake-surface-daily`) | L1 provider imagery → L2 processing | satellite turbidity evidence |
| USGS Aquatic Reflectance (AQR) | L1 provider product | input path of the R3.1 candidate (not yet consumed in production) |

| Downstream | Reads | Must not need |
|---|---|---|
| Sector Ops | `/brains/water-clarity`, health, scores, validation | — |
| Sector Intelligence | compact state (§12) | raw imagery, private research, scoring internals |
| Customer apps | *not enabled* — see §20 | — |
| Vegetation (future) | scene-metadata contract (§13) | — |

## 4. Claims by level
Claim level and validation maturity are independent.

| Level | Claim | Source | Validation needed |
|---|---|---|---|
| 1 | Satellite scene id, platform, acquisition time, cloud/coverage | provider metadata | source, date, units, provenance |
| 1 | Gauge turbidity value / site / time | USGS | same |
| 1 | Rainfall amount | MRMS / Open-Meteo | same |
| 2 | Scene qualification, age, cloud/refusal rules, FNU→ft conversion, fingerprints | deterministic | formula, gates, cloud/geometry handling |
| 3 | Estimated Secchi-equivalent visibility (`rain-decay-v0`, R3.1 candidate, satellite-observed estimates) | Sector-derived | independent truth, holdout, prospective, regional transfer |
| 3 | Clarity class, spatial "where is clearer" interpretation, shootability | Sector-derived | same |

## 5. Canonical runtime state (`/lakes/{k}/states/waterClarity`)
Compact; one object per lake. Fields: `stateType` (GAUGE_OBSERVED · RAINFALL_MODELED · FALLBACK_NEUTRAL · UNAVAILABLE), `kind`, `readiness`, `clarityFt/lowFt/highFt`, `trend`+`trendBasis`, `engine{model,source,confidenceLabel,limitations}`, `satellite{status,date,platform,sceneIds,ageHours,coveragePct,reasonCode}`, `layers[]` (URL references), `strong`, `freshness`, `provenance{sources,qualityFlags,validationRef}`, **`inputFingerprint`**, **`checkedAt`**, `brainVersion`.
Never in state: rasters, scenes, validation tables, research archives. Target size ≤ 16 KB/lake (measured ≈ 15.7 KB with layer metadata).

## 6. Confidence and reason codes
Confidence is *explained*, not a bare number (no percentages are published). Codes live in `provenance.qualityFlags` and `limitationCodes`:
`uncalibratedModel:rain-decay-v0` · `rainfallFallback:open-meteo-48h` · `noMeasurement` · `noValidatedRange:algal` · `satelliteStale:<n>d>14d` · `satelliteNone` · `satelliteUnsupported` · `satelliteInvalid:<OBSERVATION_IN_FUTURE|UNPARSEABLE_OBSERVATION_TIME|TURBIDITY_OUT_OF_RANGE>` · `resolvedLakeMismatch:<id>` · `engineUnavailable` · `SINGLE_POINT_ESTIMATE` · `SATELLITE_NOT_IN_CUSTOMER_ESTIMATE`.
Planned (needs the R3.1 path): `cloudContaminated`, `spatialMismatch`, `weakGroundTruth`, `outsideValidatedDomain`, `regionalTransfer`.

## 7. UNKNOWN / refusal model
A clarity number is **withheld** (state `UNAVAILABLE`/`FALLBACK_NEUTRAL`, last good state kept and aged) rather than guessed. Vocabulary: `UNKNOWN`, `NO_USABLE_SCENE` (`satellite.status=NONE`), `CLOUD_OBSCURED`, `STALE`, `INSUFFICIENT_GEOMETRY` (`UNSUPPORTED`/`NO_LAKE_OUTLINE`), `OUTSIDE_VALIDATED_DOMAIN`, `SOURCE_UNAVAILABLE`, `NOT_EVALUATED` (`strong`). Invalid provider data (future timestamp, bad units) is `INVALID`, never fresh.

## 8. Freshness policy (clarity-specific)
Distinct clocks, never merged:
1. **Scene acquisition time** (`satellite.observedAt`).
2. **Provider delivery lag** (measured: USGS AQR median ≈ 8 h, p90 ≈ 3 d, 2026).
3. **State generated/checked** (`generatedAt` = content changed; `checkedAt` = inputs re-verified).
4. **Valid-until** (`freshness.freshUntil`, state TTL 26 h after the last check).

Satellite evidence is `FRESH` ≤ 14 days, otherwise `STALE`. A 14-day-old scene does **not** describe tonight after rain; consumers must show age and must not present it as current. Clarity moves with rain/runoff, so a scene older than the latest significant rain event is flagged `evidenceStale` once the R3.1 path ships (design item; not yet implemented).

## 9. Execution model
Input-driven, not hourly-forever.
`lake-surface-dispatch` (daily, metadata-only STAC query) → starts `lake-surface-daily` **only** for lakes with a newer usable pass → compact state is rebuilt by the Brain publisher when the **input fingerprint** changes. Unchanged fingerprint ⇒ `noop_writes` (verification stamp + freshness only, ≈ 1 KB/lake instead of ≈ 16 KB). Heavy satellite work is never triggered by a customer, Ops, or Intelligence request.

## 10. Fingerprint
`sha256` of: Brain version, model catalog ids, engine revision, state type, clarity ft/range, trend, rain value+source, model/source/confidence, driving gauges, satellite {status, date, platform, scene ids, coverage, FNU p50, pass count, reason}, layer URLs. Excludes clocks (ages, timestamps). Satellite *status* is included, so a scene aging past 14 days changes the fingerprint (a decision, not drift).

## 11. Score dimensions and critical dimensions
Canonical score today: **frozen research certification of the R3.1 candidate (8/10, not deployed)**; production models are unscored. A readiness rubric (`clarity-readiness-v1`) is **proposed, not ratified** — see `CLARITY_READINESS_RUBRIC_PROPOSAL.md`. It is not used to change the canonical score.

## 12. Intelligence contract (what may be consumed)
`stateType`, `kind`, `readiness`, `clarityFt` (+range when present), `trend`, `satellite.status/ageHours/date`, `freshness.{stale,evidenceStale,freshUntil}`, `provenance.qualityFlags`, `engine.model`, `claim level`, `inputFingerprint`. Must treat `FALLBACK_NEUTRAL`/`UNAVAILABLE`/`RAINFALL_MODELED` as non-observational. Not wired to customer recommendations.

## 13. Shared scene contract (for future Vegetation reuse; no Vegetation dependency)
Per lake `lakes/{slug}/clarity/latest.json` and `…/{date}.json` in `gs://sector-lake-surface` (public-read): `date, platform, sceneIds, coverage, grassPct, openWaterReadPct, measuredPct`. Owned by Clarity; read-only to others; additive changes only.

## 14. Lifecycle, gates, customer exposure
Lifecycle: **SHADOW (internal)**. Customer exposure policy: **none**. Production gates: see readiness proposal. No lifecycle change, deploy, merge-to-live, or customer enablement without Michael's explicit approval.

## 15. Budgets
- **Storage (RTDB):** ≤ 16 KB/lake state; ≤ 10 MB/full publish; no-op publish ≈ 0.6 MB fleet-wide.
- **Runtime:** customer path = compact reads only. Publisher full run ≈ 40 min at concurrency 2 (621 `/conditions` calls) — this is a research/ops cadence, not a request path.
- **Cost:** see campaign handoff (private).

## 16. Ops summary
Registry `/brains/water-clarity`: lifecycle, readiness counts, stateType/model/satellite breakdowns, stale count, health, `lakeSurfaceRun`. Proposed additions: last usable scene per pilot, next expected scene, no-op ratio.

## 17. Research stop conditions
Stop researching when a remaining deficiency needs: field data, a new season, a licensed/external source, an upstream Brain's change, or Michael's authorization. Do not pursue optical-property research that does not change one of the §1 answers.
