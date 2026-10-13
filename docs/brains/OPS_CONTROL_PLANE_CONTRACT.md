# Sector Ops Control Plane — data contract v1

**Owner:** Sector Engine (platform writer `brain-platform`). **Version:** `control-plane-v1`, 2026-10-12
(consolidation Phase 10). Implementation: `sector_brain_platform/control.py`; publisher
`jobs/brain-scores/score_brains.py --write` (manual; the Orchestrator will own cadence).

Sector Ops is a **read-only presentation and control plane**. Everything below is computed by
Engine from published Brain facts; Ops renders it verbatim and computes none of it.

## What Ops reads

| Node | Content | Replaces (Ops today) |
|---|---|---|
| `/control/overview` | one document: `engine{score, scoreVersion, breakdown, blockers, strongestArea, weakestArea, serving{revision, lineageVerified}, dependencyCompleteness{consumed, total, consumedByCustomerPath, byBrain}, worstBrainHealth, brainsConformant}`, `brains{id → summary}`, `fleet{lakes, evaluatedByIntelligence, staleSlots, readinessBySlot}`, `sources{id → {owner, health, stale, lastFetchAt, latestObservationAt, failures24h?}}`, `workNext[]` | Overview tiles, System Health "worst of", Data Sources staleness, the "what to work on next" question |
| `/control/overview/brains/{id}` | `status` (lifecycle), `health`, `healthAt`, `lastSuccessfulRun`, `lastError`, **`stale` + `staleReason`** (Engine TIME rule), `staleAfterHours`, `stalenessModel`, `scheduled`, `version`, **`score{value, scale, basis, scoreVersion, completenessPct}`**, `nextOpportunity`, `coverage{directory, supported, evaluated, stale, readinessCounts, onLadder}`, `activeModel`, `candidateModel`, `validation{status, ref}`, `blockers[]`, `dependsOn` / `dependencyStatus`, `platform{conformant}` | brain header badges, score tile (`lib/brainScore.ts`), Models card, Validation badge, blockers list |
| `/control/fleet/{lakeKey}` | the Orchestrator rollup per lake: `lakeId, lastUpdatedAt (max over slots), stale (any slot), evidenceStale, issueCount (sum), slotsPublished, readiness{slot}, riverSystem, rolledUpAt` | `lakeFleet/{k}.lastUpdatedAt/stale/issueCount` (which brains no longer write) and browser-side derivations |
| `/brains/{id}`, `/health/*`, `/validation/*`, `/sources`, `/species`, `/lakes/{k}/*`, `/snapshots/{k}/latest`, `/activity` | detail, unchanged | detail pages |
| `/brains/{id}/score`, `/engine/score` | full score blocks with breakdown and blockers | score detail |

## What Ops must not compute (and where it still does today)

| Computation | Today (Ops main) | Contract |
|---|---|---|
| Brain score choice | `src/lib/brainScore.ts` picks `scores.windCertificationScore` or `candidateModel.researchScore` | read `/brains/{id}/score` (all six publish it) → `control.brains[id].score`; the old fields are fallbacks only |
| Engine score | none | `control.engine.score` (never averaged in Ops) |
| Brain stale / "last run x h ago" classification | `components/engineCards.tsx` uses `Date.now()` | `control.brains[id].stale` + `staleReason`; `timeAgo()` is display only |
| Source staleness | `pages/DataSources.tsx` compares `latestObservationAt` to the browser clock | `control.sources[id].stale` |
| Worst-of health | `lib/status.ts` rank (display only) + `SystemHealth.tsx` | `control.engine.worstBrainHealth` |
| Fleet counts / readiness counts | `Overview.tsx`, `LakeFleet.tsx` count rows client-side | `control.fleet.readinessBySlot`, `control.brains[id].coverage.readinessCounts` |
| Lake freshness | `lakeFleet.lastUpdatedAt` (no longer written by brains) | `/control/fleet/{k}.lastUpdatedAt` / `.stale` |
| Readiness, lifecycle vocabularies | hard-coded maps in `lib/status.ts` | render verbatim (contract §3); unknown strings pass through |

## Reconciliation of the known Ops branches (no Ops deploy in this phase)

| Ops branch | Needs | Engine provides now |
|---|---|---|
| `feat/biological-brain-species-first` (18b7c89) | `/species/*`, `/brains/biological-state{responsibilities, rubric, breakdowns}`, species-first lists | unchanged nodes; plus `control.brains["biological-state"]` (score 4.0, blockers: Biological State NOT_STARTED, no VALIDATED species). The 5-file conflict with Ops main is an Ops reconciliation (not done here). |
| `feat/sector-intelligence-brain` (80a01a6) | Brain exists / publishes / consumed / used-in-last-evaluation distinctions; dependency table | `/brains/sector-intelligence.dependencies[*]{exists, publishingStatus, connectionStatus, consumedByCustomerPath, consumedByPilotEvaluation, usedInLastEvaluation, lastEvaluationAt}`; `evaluation{version, pilotLakes, customerConsumes:false}`; pilot states at `/lakes/{k}/states/intelligence` (`kind: evaluated`) for 5 lakes; `control.engine.dependencyCompleteness`. The branch is 12 commits behind Ops main (Ops reconciliation). |
| `sector/lake-brain` (9132736) | `/lakes/{k}/brain`, `/lakes/{k}/speciesPresence`, `lakeState` in the snapshot, `slots.lake` | unchanged; plus `/control/fleet/{k}` rollups and `control.brains["lake-brain"]`. |
| Clarity / Wind / Temp views (Ops main) | score tile, candidate vs active, validation badge | `control.brains[id].{score, activeModel, candidateModel, validation}`; Wind's `scores{}` and Clarity's `candidateModel.researchScore` remain for compatibility. |

Catalog check: Ops `src/lib/brainCatalog.ts` ids/slots match contract §2. Its Biological question
("What are the fish likely doing?") differs from the Brain's ("What does Sector know about the
fish?"); the Brain's `displayName`/`question` in `/brains/{id}` are authoritative.

## Rules
- Ops never writes any of these nodes (`database.rules.json` already denies client writes).
- Ops renders unknown values as unknown (absent fields are "not published", never 0 or "OK").
- A Brain's `stale` in `control` is the Engine's TIME rule at publish time; a long-unpublished
  control node is itself stale — Ops shows `control.updatedAt` and treats an old overview as such
  (display rule, not science).
