# Vegetation Brain — Ops visibility gap (Engine truth vs what Sector Ops can show)

Rule: **the Engine owns truth, Ops owns presentation.** Audited 2026-10-14 against: the Engine on this branch (`jobs/brain_platform`, `jobs/vegetation-brain`), the Sector Ops source (`/Users/mcather/Desktop/Development/Web/Sector-Ops`, `main` @ `562966c`, read-only), and the live Brain RTDB. **Ops was not modified. Nothing was written to RTDB.** The live RTDB answers unauthenticated reads with `401 Permission denied`, so live `/brains/vegetation` was **not** read; there is no Vegetation writer anywhere, so it is expected to be absent (not verified).

## 1. Bottom line
| Question | Answer |
|---|---|
| Is Vegetation registered live? | **No** (no live writer exists; dry-run only). |
| Would Ops show it if it were registered? | **No**, for two independent reasons. |
| Reason A (Engine) | `control.py` builds `/control/overview` from `ALL_BRAINS = UPSTREAM + ("sector-intelligence",)` with `UPSTREAM = (lake-brain, water-temp, water-clarity, wind, biological-state)`; `scoring.py` `ALL_BRAINS` likewise excludes `vegetation`. No control entry, health roll-up, readiness count or score slot could appear. |
| Reason B (Ops) | `src/lib/brainCatalog.ts:30` defines Vegetation with `future: true`; `BrainPage.tsx:389` hard-codes the promise **"Vegetation coverage · Density · Seasonal state · Mapped polygons · Confidence / provenance · Imagery date · Vegetation type"**. Several of those are exactly what V1 must **not** claim yet (density, mapped polygons, vegetation type, submerged). `src/test/realShapes.test.tsx:331` expects the text "Planned, not yet Brains: Depth · Vegetation". `lakePanels.tsx:318` lists a per-lake "Vegetation" flag (`!!s.vegetation`) but `LAKE_TAB_BY_BRAIN.vegetation = ''` (no tab). |
| Scope mismatch | Ops' output list promises capabilities the research decided Vegetation cannot support (density, polygons, type, submerged). Fix the copy before flipping `future`. |

## 2. Field-by-field (statuses as in the Depth audit)
**ENGINE READY** = implemented in the Vegetation dry-run shape (`publish.py`, `ops_summary.py`), not live. **ENGINE GAP** = nothing computes it / platform excludes it. **OPS GAP** = Ops has no reader/type. **OPS PRESENTATION GAP** = Ops reads but shows nothing (future flag).

| # | Field | Canonical path (dry-run) | Engine | Ops |
|---|---|---|---|---|
| 1 | Registered? | `/brains/vegetation` | ENGINE READY (live: not written) | OPS PRESENTATION GAP (`future:true`) |
| 2 | Research maturity | `/brains/vegetation.research.maturity` (`official:false`) | ENGINE READY | OPS GAP (no field; must not be read as a score) |
| 3 | Official score available? | `scoreStatus: NOT_ESTABLISHED`; no `/scores/vegetation` | ENGINE READY (explicit negative) | **ENGINE GAP**: `ALL_BRAINS` excludes vegetation |
| 4 | Readiness | `/brains/vegetation.status` (PROFILED), `readinessCounts`, `/lakeFleet/{k}/readiness/vegetation` | ENGINE READY | typed generically; hidden by `future` |
| 5 | Pilot count / observed lakes | `fleet.observedLakes` | ENGINE READY (additive `fleet`) | OPS GAP (untyped) |
| 6 | Fleet observability | `breakdowns.observability` HIGH/MEDIUM/LOW/UNKNOWN; `fleet.observableLakes` | ENGINE READY | generic `breakdowns` tables |
| 7 | Validation state | `/validation/vegetation` + `validationLadder.state` | ENGINE READY | `validation` typed; hidden |
| 8 | Independent truth lakes | `fleet.withIndependentTruth` | ENGINE READY | OPS GAP |
| 9 | Scene freshness | per lake `states/vegetation.surfaceVegetation.ageDays`, `freshness`; brain-level `staleLakeCount` | ENGINE READY | OPS PRESENTATION GAP |
| 10 | Surface observer state | `scope`, `observation.evidenceKind`, `readinessCounts` | ENGINE READY | OPS GAP |
| 11 | Coverage | `readinessCounts.CALIBRATION` vs `fleet.totalLakes` | ENGINE READY | generic |
| 12 | Blockers | `blockers[]`, `primaryBlocker` | ENGINE READY | `blockers` typed (string[]) — would render once visible |
| 13 | Rules / model version | `version`, `contractVersion`, `models.candidates` | ENGINE READY | `version` typed |
| 14 | Orchestration | `orchestration {NOT_STARTED}` | ENGINE READY | `/jobs` has no vegetation row (correct: nothing deployed) |
| 15 | Dependencies | `dependsOn`, `context.consumed` per lake | ENGINE READY | OPS GAP for counts |

Every ENGINE READY number is computed from the fleet manifest, the maturity inputs and the run — **none is hardcoded for Ops to echo** (test: `test_registry_extras_computed_not_hardcoded`).

## 3. What Michael would see once exposed (intent; example numbers are the current dry-run)
```
Vegetation Brain                       PROFILED · shadow
Official score:   Not yet established             Research maturity: ~2.3 / 10 (research rubric, not a score)
Scope:            surface-reaching vegetation only · submerged NOT observable
Fleet:            621 lakes · 559 observable (476 high, 83 medium) · 33 low · 29 no geometry
Validation:       NOT_VALIDATED (pre-registered gates; see ladder)
Truth:            independent truth lakes: <n>
Primary blocker:  validation …
```

## 4. Exact follow-ups (none done here)
**Engine (needs Michael's approval because it touches the shared control plane):**
1. `control.py`/`scoring.py`: admit `vegetation` as a *shadow* Brain that does not affect `worstBrainHealth`, `brainsConformant` or the Engine score (same follow-up as Depth).
2. A shadow registry write (`/brains/vegetation`) needs a live writer, which does not exist by design; build only after approval.
3. `requiredDimensions` once the critical set in `VEGETATION_SCORE_V1_PROPOSAL.md` is ratified.
4. Add to the `/jobs` manifest only when a job is deployed.

**Ops (separate repo, not touched):**
1. `brainCatalog.ts`: keep `future:true` until registered, and **rewrite** the Vegetation question/outputs to "Where is surface-reaching aquatic vegetation, and how sure are we?" with outputs Surface vegetation (presence), Observation age, Evidence kind, Confidence/limitations, Validation state, Potential habitat (labelled potential). Remove Density, Mapped polygons, Vegetation type, Seasonal state until their gates pass.
2. Type the additive `fleet`, `research`, `scoreStatus`, `validationLadder`, `scope`, `orchestration` fields, or render generic `breakdowns` + `blockers` first.
3. Render "Official score: Not yet established" with research maturity clearly labelled research-only.
4. Per-lake: show `headline`, `surfaceVegetation.status/ageDays/confidence`, refusal reasons; always show `submergedVegetation: not observable` and `potentialOnly`.
