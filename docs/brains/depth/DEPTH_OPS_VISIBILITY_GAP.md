# Depth Brain - Ops visibility gap (Engine truth vs what Sector Ops can show)

Rule: **the Engine owns truth, Ops owns presentation.** Audited 2026-10-14 against: the Engine platform on this branch (`jobs/brain_platform`, `jobs/depth-brain`), the live Brain RTDB (GET-only), and the Sector Ops source (`/Users/mcather/Desktop/Development/Web/Sector-Ops`, `main` @ `562966c`, read-only). Ops was **not modified**; nothing was written to RTDB.

## 1. Bottom line - why Ops shows nothing about Depth today

| Question | Answer (verified) |
|---|---|
| Is Depth registered live? | **No.** Live `/brains/depth` = null; `/lakes/*/states/depth` absent; `/lakeFleet/*/readiness/depth` absent. No live Depth write is authorized (`--yes-write-shadow` never used). |
| Would Ops show it if Depth were registered? | **No**, for two independent reasons below. |
| Reason A (Engine) | `jobs/brain_platform/sector_brain_platform/control.py` builds `/control/overview` from `ALL_BRAINS = UPSTREAM + ("sector-intelligence",)`; `depth` is not in that tuple, so no Depth control entry, health roll-up, readiness count or score slot would ever appear. `scoring.py` `ALL_BRAINS` also excludes depth, so no `/scores/depth` could be published even if a scorer existed. |
| Reason B (Ops) | `src/lib/brainCatalog.ts` defines Depth with `future: true` and the question "What does the underwater structure look like?"; `BrainPage.tsx` returns `<FutureBrain>` ("Not built yet", badge "Coming", outputs Bathymetry / Depth contours / Shallow flats / Channels / Ledges / Structural zones) for any `future` brain **regardless of registry data**; the Registry list shows it dimmed "(coming)"; `ACTIVE_BRAINS` (Overview cards) and `jobs.ts` filter it out. The FutureBrain copy promises Ops "will render this brain as soon as Sector Engine registers it at /brains/depth" - the code does not (the flag must be flipped in Ops source). |
| Scope text mismatch | Ops' Depth promise (bathymetry, contours, flats, channels, ledges) is exactly what the research decided Depth must **not** claim. This is a presentation/scope gap that matters before anyone flips the flag. |

## 2. Field-by-field

Statuses: **ENGINE PUBLISHES** (live RTDB) - **ENGINE READY** (implemented in the Depth dry-run shape, not live) - **ENGINE GAP** (nothing computes it) - **OPS CONSUMES** - **OPS GAP** (Ops has no reader/type) - **OPS DISPLAYS** - **OPS PRESENTATION GAP** (Ops reads but shows nothing/misleads).

| # | Field | Canonical path (dry-run shape; `depth_brain/publish.py`, `ops_summary.py`) | Engine | Ops consumes | Ops displays | Gap |
|---|---|---|---|---|---|---|
| 1 | Brain registered | `/brains/depth` | ENGINE READY (live: null) | Ops reads `/brains` generically | NO: catalog `future:true` -> FutureBrain | **OPS PRESENTATION GAP** (flag) + approval needed to write |
| 2 | Readiness / status | `/brains/depth.status` (PROFILED), `readinessCounts`, `/lakeFleet/{k}/readiness/depth` | ENGINE READY | `BrainRegistryEntry.status/readinessCounts` typed | NO (FutureBrain) | OPS PRESENTATION GAP |
| 3 | Pilot count | `fleet.pilotVerified` (5) and readinessCounts.CALIBRATION | ENGINE READY (`fleet` is additive, untyped in Ops) | **OPS GAP** (no type for `fleet`) | no | OPS GAP |
| 4 | Candidate count | `fleet.shiftPossible`, `supportedLakeCount` (92) | ENGINE READY | `supportedLakeCount` typed | no | OPS PRESENTATION GAP |
| 5 | Verified datum count | `fleet.verifiedDatum` (76), `inferredOperatorSystem` (16), `breakdowns.datumStatus` | ENGINE READY | `breakdowns` typed as `Record<string, Record<string, number>>` - renders generic tables | no | OPS PRESENTATION GAP |
| 6 | HIGH / MEDIUM / BLOCKED | `breakdowns.rollout` | ENGINE READY | generic `breakdowns` | no | OPS PRESENTATION GAP |
| 7 | Validation state | `/validation/depth` + `/brains/depth.validation` = NOT_VALIDATED | ENGINE READY | `validation` typed | no | OPS PRESENTATION GAP |
| 8 | Research maturity | `/brains/depth.research.maturity` (4.5) with `official:false` | ENGINE READY | **OPS GAP** (no field; Ops must not infer it as a score) | no | OPS GAP |
| 9 | Official score available? | `scoreStatus: NOT_ESTABLISHED`; `/scores/depth` absent; no `score` key | ENGINE READY (negative is explicit) | Ops reads `/control/overview.brains[id].score` | no | **ENGINE GAP**: control plane excludes depth (Reason A) |
| 10 | Last dry run | `lastDryRun {evaluated, unavailable}`, `health/brains/depth.lastRun` | ENGINE READY (a live run records only when written) | `healthAt`, `lastSuccessfulRun` typed | no | OPS PRESENTATION GAP |
| 11 | Contract version | `contractVersion` (`sector-brain-depth-state-v1`), `/brains/depth.version` | ENGINE READY | `version` typed | no | OPS PRESENTATION GAP |
| 12 | Field validation state | `fieldValidation.status` (NOT_STARTED) | ENGINE READY | OPS GAP | no | OPS GAP |
| 13 | Licensing blockers | `breakdowns.contourLicence`, `blockers[]` line | ENGINE READY | `blockers` typed (string[]) | would show on brain page | OPS PRESENTATION GAP (only once registered + un-futured) |
| 14 | Lake dependency | `lakeDependency {liveLakeStates, awaitingLakeBrain}` + `dependsOn:['lake-brain']` | ENGINE READY | `dependsOn` typed on ControlBrain | no | OPS GAP for the counts |
| 15 | Orchestration status | `orchestration {status:NOT_STARTED, registered:false, scheduled:false}`; `schedule.jobId` is advisory | ENGINE READY | Ops jobs view reads `/jobs` (platform manifest) | no (Depth not in `/jobs`; `jobs.ts` filters `future`) | **ENGINE GAP**: `/jobs` manifest has no Depth row (correct today: not deployed) + OPS GAP |
| 16 | Primary blocker | `primaryBlocker` + `blockers[0]` | ENGINE READY | `blockers` typed | no | OPS PRESENTATION GAP |
| 17 | Status basis prose | `statusBasis` | ENGINE READY | `statusBasis` typed | no | OPS PRESENTATION GAP |
| 18 | Stale / freshness | FINGERPRINT brain: never stale by age; `evidenceStale` per lake | ENGINE READY | `staleAfterHours` null OK | no | - |
| 19 | Lake-state lakes with a Depth shift | `/lakes/{k}/states/depth` (5 in dry run) | ENGINE READY | per-lake slot `depth` in catalog | no | OPS PRESENTATION GAP |

Everything marked ENGINE READY is computed from the candidate manifest, the research-maturity inputs and the run - **no number is hardcoded for Ops to echo** (tests: `test_registry_carries_computed_ops_summary_not_hardcoded_numbers`).

## 3. Desired Ops presentation (intent only; Ops must read Engine fields, hardcode nothing)

```
Depth Brain                         PROFILED · shadow · HEALTHY
Official score:   Not yet established            Research maturity: 4.5 / 10 (research rubric, not a score)
Fleet:            5 pilot verified · 65 high · 22 medium · 529 blocked (shift defensible: 92 of 621)
Datum:            76 verified · 16 inferred (TVA) · 233 plausible lakes blocked
Primary blocker:  datum coverage
Contours:         103 tier A/B lakes · 94 with reference shares · effective zones withheld (survey reference pool unverified)
Lake dependency:  5 live Lake states · 87 awaiting Lake Brain
Validation:       NOT_VALIDATED · field validation NOT_STARTED
Licensing:        59 of 103 contour lakes allow customer-derived numbers
Orchestration:    NOT STARTED
(numbers above are the CURRENT dry-run values, example presentation only)
```

## 4. Exact follow-ups (none done here)

**Engine (needs Michael's approval because it touches the shared platform and live control plane):**
1. `control.py`/`scoring.py`: include `depth` in the brain set **without** letting a shadow Brain affect `worstBrainHealth`, `brainsConformant` or the Engine score (add a `participatesInRollups` flag or a separate `shadowBrains` list). Add tests.
2. Publish `/brains/depth` (shadow write, `--yes-write-shadow`) so the registry node exists. Only after approval.
3. Optionally add a `requiredDimensions` list for Depth once Michael ratifies critical dimensions (see `DEPTH_SCORE_V1_PROPOSAL.md`).
4. Add Depth to the `/jobs` manifest only when a job is actually deployed (`DEPTH_ORCHESTRATION_PLAN.md`).

**Ops (separate repo, not touched):**
1. `brainCatalog.ts`: set `future:false` for Depth **and rewrite its `question` and outputs**: "How has the depth of the water we care about shifted from its reference condition?" - outputs: Level shift, Datum status, Reference pool, Evidence tier, Contour coverage (where measured), Provenance. Remove Bathymetry/Channels/Ledges/Structural zones.
2. `types/brain.ts`: type the additive `fleet`, `research`, `scoreStatus`, `lakeDependency`, `orchestration`, `fieldValidation` fields (or render generic `breakdowns` + `blockers` first).
3. Render "Official score: Not yet established" explicitly when `scoreStatus = NOT_ESTABLISHED`, with research maturity labelled as research-only.
4. Per-lake: show `states/depth.effectiveDepth` (shift, +/- sigma, confidence, reasons when unknown).
