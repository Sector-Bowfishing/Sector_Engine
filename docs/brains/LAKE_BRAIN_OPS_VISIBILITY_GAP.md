# Lake Brain — Ops visibility gap (Engine truth vs what Sector Ops can show)

Rule: **the Engine owns truth, Ops owns presentation.** This document lists what the Engine publishes for Lake Brain, whether the Sector Ops code
(`/Users/mcather/Desktop/Development/Web/Sector-Ops`, `main` @ `1742187`, read-only audit) reads it, and whether it exposes it. Nothing here asks Ops to compute
or duplicate a Lake score. Ops was **not modified** by this work.

Audited 2026-10-13 (UTC) against the live Brain RTDB `https://sector-brain.firebaseio.com` (read-only) and the Ops source tree.

## 1. Why Ops looked unchanged
Verified, not guessed:

| Reported "no change" | What is true |
|---|---|
| Score still 3.0 | Correct and expected: the **coverage gate caps the displayed score at 3.0** (5 of 621 lakes profiled, 1 % < 10 %). Nothing the Brain gained this campaign can lift that gate without human-accepted bindings. |
| Maturity improved 4.3 → 6.3 | Real, and **published** at `/scores/lake-brain.uncapped = 6.3`. Ops **never reads `/scores/{id}`** (its approved path list is `/brains`, `/control/overview`, `/engine/score`, …; there is no `scores` key in `src/data/brainPaths.ts`). |
| Control plane refreshed? | Yes: `/control/overview.updatedAt` and `brains.lake-brain.score.scoreUpdatedAt` are current; `activeModel` now says `lake-level-rules-v2`; health `HEALTHY`; `stale: false`. These changes exist but are small text/badge changes. |
| Dimensions/gates | Published only at `/scores/lake-brain` (`scoreBreakdown`, `scoreBlockers`). The control-plane builder (`jobs/brain_platform/sector_brain_platform/control.py`) copied **only** `value, scale, basis, scoreVersion, completenessPct, scoreUpdatedAt` into `/control/overview.brains[id].score`, dropping the uncapped score, the cap amounts and the per-dimension values. |
| Candidates / ledger / geometry | Not published anywhere Ops reads (see table). |

So: the canonical Engine state *was* being refreshed correctly; **the control-plane summary was lossy** (an Engine gap, now fixed on branch `feat/lake-fleet-opsvis`, pending deploy) and **Ops has no reader for `/scores/{id}`** (an Ops gap).

## 2. Field-by-field

Status (updated 2026-10-14): the control-plane mirror, `fleetBindingStatus` and `predictionLedger` are LIVE and read back from the Brain RTDB (`/control/overview.brains.lake-brain.score` carries `uncapped` 6.3, `gates` with caps, and all eight `dimensions`). **SUPPORTED** (Engine publishes, Ops reads and shows) · **OPS GAP** (Engine publishes, Ops does not consume/show) · **ENGINE GAP** (Engine does not publish) · **FIXED-PENDING-DEPLOY** (Engine change committed, not yet live).

| # | Field | Canonical Engine path | Live value (2026-10-13) | Ops reads? | Ops shows? | Status | Severity |
|---|---|---|---|---|---|---|---|
| 1 | Displayed score | `/control/overview.brains.lake-brain.score.value` | 3.0 / 10 | yes | yes (Brain card, Overview) | SUPPORTED | – |
| 2 | Uncapped score | `/scores/lake-brain.uncapped` (+ `/control/overview.brains.lake-brain.score.uncapped` after deploy) | 6.3 | no (control field only after deploy; `ControlBrain.score` type has no `uncapped`) | no | **LIVE 2026-10-14T04:51Z** (Engine) + **OPS GAP** (type + UI) | High |
| 3 | Score dimensions | `/scores/lake-brain.scoreBreakdown` (+ `/control/overview.brains.lake-brain.dimensions` after deploy) | coverage 1.0, floodDroughtContext 2.0, validation 0.0, others 10.0 | `ControlBrain.dimensions` is declared as a "future contract" and only consumed by the production-policy evaluator when `requiredDimensions` is also published; no dimension table is rendered | no | LIVE 2026-10-14T04:51Z (Engine) + **OPS GAP** (render) | High |
| 4 | Active gates and caps | `/scores/lake-brain.scoreBlockers` (+ `…score.gates[]` after deploy) | coverage cap 3.0; validation cap 5.0 | no | `blockers[]` strings are shown but **without the cap amount** | FIXED-PENDING-DEPLOY + **OPS GAP** | High |
| 5 | Blockers (text) | `/control/overview.brains.lake-brain.blockers[]` | 3 strings | yes | yes | SUPPORTED | – |
| 6 | Next opportunity | `…brains.lake-brain.nextOpportunity` | "review source bindings for more lakes (coverage gate)…" | yes | yes | SUPPORTED | – |
| 7 | Lifecycle | `…brains.lake-brain.status` | CALIBRATION | yes | yes | SUPPORTED | – |
| 8 | Validation state | `/validation/lake-brain`, `…brains.lake-brain.validation.status` | NOT_VALIDATED | yes | yes | SUPPORTED | – |
| 9 | Validation clock / prediction-ledger status | `/brains/lake-brain.predictionLedger` `{status, startedAt, lastObject, lastRecords, warning, rulesVersion, note}` (**new**) | before deploy: not published (start `2026-10-13T18:53:14Z` lived only in `gs://sector-lake-brain/predictions/` and a repo doc) | no | no | **LIVE 2026-10-14T04:51Z** (Engine) + **OPS GAP** | Medium |
| 10 | Rules version | `…brains.lake-brain.activeModel.modelId` / `…validation.modelVersion` | `1.0.0 · lake-level-rules-v2` | yes | model label shown | SUPPORTED (baseline method `doy15-percentile-v2` is in `/brains/lake-brain.baselineMethod`; not shown) | Low |
| 11 | Bindings version | `/brains/lake-brain.bindingVersion` | `bindings-2026-10-13.1` | typed on the per-lake profile only | only inside the lake detail view | **OPS GAP** (brain-level) | Low |
| 12 | Reviewed fleet count | `/brains/lake-brain.supportedLakeCount`; `…coverage.supported`; `breakdowns.fleetBindingStatus.REVIEWED` (after deploy) | 5 | yes (supported/onLadder) | "5 of 621" in blockers | SUPPORTED | – |
| 13 | Candidate fleet count | `/brains/lake-brain.breakdowns.fleetBindingStatus.CANDIDATE` (**new**) | `{REVIEWED: 5, CANDIDATE: 191}` (the 196-row generated table includes the 5 pilots) | no (`breakdowns` is typed `Record<string, Record<string, number>>` and shown only for water-temp-style tables) | no | **LIVE 2026-10-14T04:51Z** (Engine) + **OPS GAP** | High |
| 14 | Coverage | `…coverage.{directory,supported,onLadder,readinessCounts}` | 621 / 5 / 5 / BETA 5 | yes | yes | SUPPORTED | – |
| 15 | Freshness / stale | `…brains.lake-brain.stale`, `staleReason`, `staleAfterHours` | false, 3 h | yes | yes | SUPPORTED | – |
| 16 | Health | `…health`, `healthAt` | HEALTHY, 2026-10-13T18:53:14Z | yes | yes | SUPPORTED | – |
| 17 | Last successful job | `…lastSuccessfulRun` | 2026-10-13T18:53:19Z | yes | yes | SUPPORTED | – |
| 18 | Last score evaluation | `…score.scoreUpdatedAt` | 2026-10-13T19:51:44Z | yes | yes ("scored x ago") | SUPPORTED | – |
| 19 | Last score *change* | none (`scoreUpdatedAt` is the evaluation time, not the time the value changed) | – | no | no | **ENGINE GAP** (score events exist in `/activity`; not summarised per Brain) | Low |
| 20 | Geometry registry state | public static `gs://sector-lake-registry/registry/lakes.v1.json` | see `LAKE_REGISTRY_GEOMETRY_CONTRACT.md` | Ops does not read the registry | no | **OPS GAP** (consumption designed in the contract) | Medium |
| 22 | Claim-level maturity | `/brains/lake-brain.claimMaturity{claim: {level, maturity, note}}` (**new**) | 7 claims: currentLevel L1 PROVIDER_VERIFIED … rapidChange L3 NOT_VALIDATED | no | no | **LIVE 2026-10-14T05:25Z** (Engine) + **OPS GAP** | Medium |
| 21 | Production-readiness (≥ 8.0 overall, every critical dimension ≥ 7.5) | Ops uses its own `src/lib/productionPolicy.ts`; Engine publishes no `productionPolicy` and no `requiredDimensions` | – | the evaluator is wired but starves for `requiredDimensions` | shows a policy chip without critical-dimension detail | **ENGINE GAP** (needs Michael to ratify which dimensions are critical — a proposal is in `LAKE_BRAIN_PRODUCTION_READINESS_MATRIX.md`) | Medium |

## 3. What the Engine changed (this campaign, on `feat/lake-fleet-opsvis`; live after the next brain-jobs image deploy + score publish)
- `/control/overview.brains[id].score.uncapped`, `…score.gates[] = {gate, cap, why}`, `…dimensions = {name: {value, scale, weight, status}}` — additive, generic for every Brain that publishes a `/scores/{id}`; nothing is invented when the score record lacks them (unit test). Evidence prose stays on `/scores/{id}` to keep the ~12 KB overview small (growth ≈ 2–3 KB for six Brains).
- `/brains/lake-brain.breakdowns.fleetBindingStatus = {REVIEWED, CANDIDATE}` — counts every binding in the compiled table, unlike `bindingStatus`, which counts only the lakes a run published.

## 4. Desired Ops presentation (intent only; consume Engine fields, hardcode nothing)
```
Lake Brain                         CALIBRATION · HEALTHY
Displayed score   3.0 / 10      Uncapped maturity 6.3 / 10
Held down by:  coverage gate (cap 3.0) · validation gate (cap 5.0)
Dimensions:    coverage 1.0 · validation 0.0 · floodDroughtContext 2.0 · … (10.0 ×5)
Fleet:         5 reviewed · 196 candidates (review pending)
Validation:    NOT_VALIDATED · prediction ledger running since 2026-10-13 (when published)
Rules v2 · bindings bindings-2026-10-13.1 · scored <time> · last run <time>
```

## 5. Exact Ops follow-up (not done here)
1. `src/types/brain.ts`: add `score.uncapped`, `score.gates[]` to `ControlBrain`; type `dimensions` as already declared.
2. Overview `BrainCard` / Lake Brain page: render uncapped beside displayed; list gates with caps; render the dimension table from `ControlBrain.dimensions` (no scoring in Ops).
3. Read `/brains/lake-brain.breakdowns.fleetBindingStatus` and `bindingVersion`; show "N reviewed · M candidates".
4. After Michael ratifies critical dimensions and the Engine publishes `requiredDimensions`/`productionPolicy`, delete the Ops fallback policy.
5. Optional: read the public geometry registry per the geometry contract for map layers.

## 6. Engine follow-ups (this repo)
- Row 9 now publishes `predictionLedger` from the Lake Brain registry entry (status reflects `--no-ledger`). Cumulative object/run counts would need a bucket listing per run; deliberately not done (cost) — the monthly scorer reports them.
- Publish a per-Brain "last score change" (row 19) from the existing score publisher, which already knows when `value`/`uncapped` changed.
