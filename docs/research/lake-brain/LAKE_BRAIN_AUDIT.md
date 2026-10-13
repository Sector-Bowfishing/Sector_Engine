# Lake Brain — baseline audit and score decomposition (2026-10-13)

Base commit: `feat/cost-efficient-scheduling` @ `48168baa323897681219f81480ad4accba08ef07` (not yet merged into `main` e596a6bb).
Facts below were read from the repository and from read-only GETs of the Brain RTDB on 2026-10-13 ~05:40 UTC.

## 1. What Lake Brain is today

| Item | Value |
|---|---|
| Brain id / slot / snapshot field | `lake-brain` / `lake` / `lakeState` |
| Version / model | `1.0.0` / `lake-level-rules-v1`; baseline `doy15-percentile-v1`; bindings `bindings-2026-10-12.1` |
| Status (lifecycle) | `CALIBRATION` (brain status); readiness counts `BETA 1` (Hartwell), `CALIBRATION 4` (the TVA chain) |
| Health | `WARNING` (baselines INSUFFICIENT, Hartwell on a documented fallback chain) |
| Coverage | **5 of 621** directory lakes profiled/published (0.8 %); 616 lakes have no `lake` slot at all (implicitly `DISCOVERED`) |
| Validation | `/validation/lake-brain` = `NOT_VALIDATED`, `holdoutType: none`, `sampleCount: 0` |
| Score | **3.0 / 10** (`lake-brain-score-v1`, COMPUTED); uncapped 4.3; two gates fire (coverage cap 3.0, validation cap 5.0) |
| Cadence | not scheduled by itself; since 2026-10-13 `lake-brain` is a scale-to-zero Cloud Run job started by `brain-orchestrator` when stale (`staleAfterHours` 3); per-state `nextCheckAt` (e.g. "scheduled: stable lake, 2 h") |
| Storage | RTDB `/lakes/{k}/brain` (profile), `/lakes/{k}/states/lake`, `/lakeFleet/{k}/slots/lake`, snapshot `lakeState`; history + baselines + presence in `gs://sector-lake-brain` (≈ 5 MB) |

### Pilot lakes
Guntersville|AL (TVA `GVDA1`), Wheeler|AL (`WHLA1`), Wilson|AL (`WLSA1`), Pickwick Lake|TN (`PICT1`) — TVA hourly pool elevation (`observed-data-48-hours`, ~60 min lag), TVA operating guide (guide curve + zone; Wilson has a zone only); Lake Hartwell|SC — USACE Savannah CWMS pool (`Hartwell.Elev-Pool.Inst.1Hour…`) with USGS `02187010`/`00062` as the reviewed fallback; CWMS guide curve (top of conservation) + drought levels L1–L3 as the zone; 60 years of daily pool.

### What each published layer contains (Guntersville example)
- **Profile** (`profileVersion`, `profileHash`): `identity`, `characteristics` (controlled, hydropower with quality+source), `hydrology`, `operatingPools` (guide curve ref, operating-zone source, `topOfGatesFt`, `normalFullPoolRef` = the directory `fullPoolFt`), `sourceCapability` (binding status REVIEWED, class, primary series with cadence/lag, history refs), `historicalCoverage` (baselineMethod, baselineStatus, years covered, observationCount, historyStart/End, history ref), `trustedSources`, `speciesPresenceSummary`, `readiness`.
- **State** (`kind` observed|proxy|…): `currentElevationFt`, `change` (1 h/6 h/24 h/3 d), `differenceFromGuideFt`, `differenceFromNormalPoolFt`, `levelState` (IN_ZONE/ABOVE_ZONE/BELOW_ZONE/FLOOD_POOL/UNKNOWN), `trendState`, `historicalState`, `floodPoolState`, `rapidChangeThresholdFt`, `rateOfChangePercentile`, `operatingZone`, `facts[]` (customer-readable sentences), `freshness` (`sourceObservationAt`, `generatedAt`, `freshUntil`, `nextCheckAt`, `refreshReason`, `stale`), `provenance` (sources with `lastObservationAt`, `qualityFlags`, `validationRef`).
- **Geometry: none.** The Lake profile carries no boundary, only the directory's `lat/lon` centre point. See `LAKE_BRAIN_GEOMETRY_RESEARCH.md`.
- **Species presence:** owned by Lake Brain, stored privately; the profile exposes only `speciesPresenceSummary`. See `LAKE_BRAIN_SPECIES_PRESENCE_RESEARCH.md`.

### The 621-lake directory (source of truth for scaling)
Generated from `docs/data/Sector_Lakes_APIs_2.xlsx` → `LakeDirectory.swift` → `GET /lakes`. Per lake: name, state(s), lat/lon, `hasDam` (401 yes / 220 no), `operatorName`, `apiLevel` (272 dedicated / 184 usgsOnly / 165 none), `usgsGage` (310 yes / 191 likely / 120 no), `cwmsOffice` (177 lakes), `fullPoolFt` (608) with `poolBasis` (414 fullPool / 194 naturalSurface) and `poolConfidence` (353 high, 34 med, 221 low). Operator families: USACE 198, USBR 61, TVA 18, 101 natural/none, 243 other operators (utilities, states, municipal). 16 duplicated names (distinct lakes).
Unverified candidate classes derived from those hints (what `LakeSourceBindings.candidateCapability` yields): `DIRECT_OPERATOR_POOL` 274, `NEARBY_GAUGE_PROXY` 169, `NO_SOURCE` 164, `DIRECT_LAKE_GAUGE` 14. **None of these publishes a state or counts toward the score** (rubric `cannotCount`).

### Readiness ladder (`lake-brain-readiness-v1`)
`DISCOVERED` (directory lake, no reviewed binding) → `PROFILED` (binding reviewed as NO_SOURCE) → `CALIBRATION` (current level from a reviewed source; history < 5 y or no guide) → `BETA` (OBSERVED + operator guide + SUFFICIENT baseline; not validated) → `VALIDATED` / `PRODUCTION` (unused until classification checks exist).

### Existing validation evidence
None that satisfies the rubric. One *method cross-check* (not a validation): Hartwell's computed 30-year band p10/p50/p90 = 649.89/655.58/660.54 ft vs the CWMS-published period-of-record percentiles 649.09/655.90/660.90 ft (≤ 0.8 ft; expected basis difference). Hartwell USGS-vs-CWMS agreement 0.03 ft over 2026-10-01..08. 30+ unit/fixture tests exist for the classification rules; they test code, not the world.

## 2. Why the score is 3.0 — dimension by dimension

`score = Σ(weight × value)/100`, then `min(uncapped, lowest fired gate)`. Max points per dimension = weight/10.

| Dimension | Weight | Value (0–10) | Points (max) | Evidence present | Evidence missing | Evidence quality | Coverage of the evidence | Ceiling imposed |
|---|---|---|---|---|---|---|---|---|
| sourceAuthority | 15 | 10.0 | 1.50 (1.50) | all 5 profiled lakes on operator pool / own gauge | n/a for the 616 unprofiled | high (operator feeds, probed) | 5/5 profiled; **5/621 fleet** | none per se; denominator is only profiled lakes |
| operatorPlan | 10 | 10.0 | 1.00 (1.00) | TVA guide curve/zone (4), CWMS GC + L1–L3 (Hartwell) | – | high | 5/5 profiled | none |
| historyQuality | 15 | 2.0 | 0.30 (1.50) | Hartwell 60 y daily (SUFFICIENT) | the 4 TVA lakes have 651 days (1 y) → INSUFFICIENT | TVA history source limited to the guide's 2-y window | 1/5 | **TVA history source** (needs a deeper authoritative series) |
| seasonalBaseline | 10 | 2.0 | 0.20 (1.00) | Hartwell baseline | TVA lakes need ≥ 2 complete years for LIMITED, ≥ 5 for SUFFICIENT | same | 1/5 | same |
| trendQuality | 10 | 10.0 | 1.00 (1.00) | 5/5 states OBSERVED | – | high | 5/5 | none |
| floodDroughtContext | 5 | 2.0 | 0.10 (0.50) | Hartwell only (CWMS "bottom of flood control") | TVA publishes no flood-pool bottom in the feeds read; Wilson/Guntersville etc. UNKNOWN | gap is *applicability + source* | 1/5 | operator flood-level publication |
| validation | 15 | 0.0 | 0.00 (1.50) | none | any classification check against an independent truth | – | 0 samples | fleet validation status → **gate cap 5.0** |
| coverage | 20 | 1.0 | 0.20 (2.00) | 5 profiled | 616 lakes | – | 0.8 % → ladder pts 1 | **gate cap 3.0 while < 10 % profiled** |
| **Total** | 100 | | **4.30 uncapped → 3.0** | | | | | coverage gate |

Therefore: the dominating constraints are (1) coverage < 10 % (gate 3.0 *and* 2.0 points of weight), (2) no validation (gate 5.0 *and* 1.5 points), (3) TVA history depth (1.8 points), (4) flood context (0.4 points). Source authority, operator plan and trend quality are already maxed — but only over 5 lakes.

## 3. Score ladder — what must become true

Exact requirements from the unmodified rubric (`research/lake-brain/tools/research_score.py ladder`; `data/score_ladder.json`). "Quality share" = the same share of **profiled** lakes meeting sourceAuthority, operatorPlan, historyQuality (SUFFICIENT), seasonalBaseline (≥ LIMITED) and floodDroughtContext; trendQuality held at 100 % observed. These are the *minimum* uniform shares; real fleets are not uniform (flood context in particular cannot reach high shares for lakes without flood control).

| Step | What must become true (the cheapest paths) |
|---|---|
| **3 → 4** | Lift the coverage gate: ≥ **63** profiled lakes (≥ 10 %, reviewed bindings, real level evidence) **and** keep quality shares ≥ **0.42** (NOT_VALIDATED) — or ≥ 0.29 if validation becomes PARTIAL. Today's 4.3 is uncapped; 63 lakes at pilot-like quality would score 5.0 (validation cap). |
| **4 → 5** | 63+ profiled lakes at quality ≥ 0.61 (NOT_VALIDATED, capped at exactly 5.0) or 156 lakes (25 %) at ≥ 0.54; with PARTIAL validation 63 lakes need only 0.47. |
| **5 → 6** | **Validation must leave NOT_VALIDATED** (gate cap 5.0 blocks everything above): PARTIAL + 63 lakes at quality ≥ 0.66, or PARTIAL + 156 lakes at ≥ 0.59, or VALIDATED + 63 lakes at ≥ 0.52. |
| **6 → 7** | PARTIAL + 156 lakes at ≥ 0.77, or PARTIAL + 311 lakes (50 %) at ≥ 0.70, or VALIDATED + 156 lakes at ≥ 0.62 / + 311 at ≥ 0.56. |
| **7 → 8** | PARTIAL needs ≥ 156 lakes at ≥ 0.95 (or 311 at ≥ 0.88, 466 at ≥ 0.80); VALIDATED needs 63 lakes at ≥ 0.88, 156 at ≥ 0.80, 311 at ≥ 0.73, 466 at ≥ 0.66. **8.0 is effectively unreachable without VALIDATED status or near-perfect quality over a quarter of the fleet.** |
| **8 → 9** | VALIDATED + ≥ 311 lakes at ≥ 0.92 (or 466 at ≥ 0.84, 559 at ≥ 0.80); PARTIAL only with ≥ 466 lakes at ≥ 0.99. |
| **9 → 10** | VALIDATED, ≥ 90 % coverage (ladder 10), and ≥ 0.9 quality across all five share dimensions — i.e. an operator guide, SUFFICIENT history, SUFFICIENT baseline and flood context for almost every lake. Not a realistic goal for natural lakes without a flood pool. |

Production policy (separate from the research score): overall ≥ 8.0 **and** every required/critical condition ≥ 7.5. Lifecycle, validation status and customer deployment are not changed by anything in this campaign.

## 4. Rubric observations (documented separately — the rubric was NOT changed to raise any number)

1. **Denominator effect.** Five quality dimensions are shares of *profiled* lakes while coverage is scored separately. Adding weaker lakes lowers sourceAuthority/operatorPlan/etc.: the score can *fall* as the fleet grows if new lakes have no guide curve or flood level. A research score must therefore be reported with its quality shares, not just a profiled count.
2. **Reviewing `NO_SOURCE` lakes raises the coverage ladder cheaply** (a published `PROFILED` binding counts in `len(profiles)`), while contributing zero quality. That is a gaming vector; the research score counts only lakes with real, probed level evidence and the campaign will not recommend padding coverage with NO_SOURCE reviews.
3. **floodDroughtContext is not applicability-aware.** Run-of-river lakes, natural lakes and many storage lakes without a defined flood pool can never leave `UNKNOWN`, capping the dimension (0.5 pt) permanently and, if added as profiled lakes, dragging the share down. A fairer fact is "flood state known **where a flood pool exists**".
4. **Validation is one fleet-wide ternary** (15 % weight + gate 5.0). Evidence naturally supports dimension-specific validation (source binding, baseline calibration, trend calibration, state classification); the rubric cannot represent it. See `LAKE_BRAIN_VALIDATION_STRATEGY.md`.
5. **No dimension for geometry, identity, or species presence**, although Lake Brain owns presence and is expected to anchor the canonical lake identity. Improving these will not move the score under `lake-brain-score-v1`; they matter for Ops, Sector Intelligence confidence and onboarding. A rubric v2 would be a versioned decision for Michael, not part of this campaign.
6. **Fresh hourly state ≠ validated knowledge.** `trendQuality` (observed vs proxy) rewards source type, not correctness.
