# Sector Ops consumer handoff — Firebase remediation (Cortex 2.2, 2026-10-21)

Standards: Rehtac Cortex 2.2.0 @ ae59e2d, pack sector/engine.

**Purpose.** This is what the Sector Ops session must change so that the Engine can retire its legacy copies. Sector Ops reads only and never writes Brain data (FD-04). Every Engine change listed is additive: Ops keeps working, unchanged, against both today's production and the Engine after this branch deploys.

**Source:** Engine branch `cortex/firebase-data-audit-2026-10-21`. Session record: `docs/cortex/sessions/2026-10-21-cortex-2-2-firebase-data-audit.md`.

## Required order

1. Ops lands the reader changes below (OPS-1 to OPS-4). Each reads the new source and falls back to the old one.
2. Engine PR #40, then this branch, merge (approval A-1). The orchestrator and Wind deploy from main (approval A-2 class).
3. Only after Ops has deployed: the owner approves switching off the legacy writers:
   - Wind `PUBLISH_LEGACY_SCORE_COPY=False`;
   - scorer `WRITE_ENGINE_SCORE_ALIAS=False`.
4. Gated production cleanup, with a baseline export, typed deletes and read-back (session record §10).

## OPS-1 Wind scores (C-1)

| Read | Path | Shape |
|---|---|---|
| **Use** | `/scores/wind` | `value` (3.3), `scale`, `basis`, `scoreVersion` (`wind-certification-rubric-v1`), `scoreUpdatedAt`; `measurements` = {`windCapability`, `bwisV1`, `scientificConfidence`, `productionReadiness`, `certification`, `presentation`, `schema`, `authority`, `evaluatedAt`} |
| Stop using | `/brains/wind/scores` and `/validation/wind/scores` (`windBrain.tsx` `entry?.scores ?? v?.scores`) | frozen validation evidence (3.1 / BWIS 5.4, frozen 2026-10-12) |

- From this branch on, the legacy copy carries `measurement: "FROZEN_VALIDATION_EVIDENCE"`, `authoritative: false`, `authoritativeScorePath: "/scores/wind"`, `measuredAt` and `status: "LEGACY_COMPATIBILITY"`.
- If Ops still shows it anywhere, it must label it as frozen evidence with `measuredAt`, never as the Wind score.
- BWIS: `/scores/wind/measurements/bwisV1.value`.

## OPS-2 Engine score (C-2)

| Read | Path |
|---|---|
| **Use** | `/scores/engine` (`engineScore`, `engineScoreVersion` `engine-score-v1`, same object) |
| Stop using | `/engine/score` (`brainPaths.ts` `case 'engineScore'`) |

The two nodes are identical: the same object, written in the same update. The switch is a path change only.

## OPS-3 Freshness and health (C-5, E-6)

**Never treat a persisted `stale: false` or `HEALTHY` as proof of current freshness.** Brains set these when they run, and a paused Brain keeps its last value.

| Need | Read | Notes |
|---|---|---|
| Per-lake staleness | `/control/fleet/{k}` `stale`, `staleSlots` {slot: `FLAG` \| `AGE`}, `staleRule` | `staleRule: "SLOT_FLAG_OR_POLICY_AGE"` means policy age is applied. If `staleRule` is absent or `SLOT_FLAG`, the rollup comes from an older orchestrator: show "freshness from Brain flag only". |
| Projection age | `/control/fleet/{k}.rolledUpAt` | The orchestrator is PAUSED, so rollups stop. Show the age of `rolledUpAt`. |
| Fleet totals | `/control/overview.fleet` `staleSlots`, `staleSlotsByAge`, `staleRule` | |
| Brain health | `/control/overview.brains[*]` `health`, `healthBasis` (`RECORDED_AT_LAST_EXECUTION`), `healthCurrent`, `healthAt`, `stale`, `staleReason` | When `healthCurrent` is false, show the health as "last recorded", not current |
| Do not read | slot `stale` alone (`lakeBrain.tsx:169,212`), `/lakeFleet/{k}/lastUpdatedAt`, `/snapshots/{k}/latest/{generatedAt, snapshotVersion}` | The last three are deprecated: frozen since 2026-10-12/13 and deletion candidates |

Ops displays these values and never computes a substitute classification (FD-04). Showing the age of a timestamp is display.

## OPS-4 Private species presence (C-6): only if the owner approves the rules change

**Proposed rules** (emulator-tested: `verification/firebase/rules_emulator_check.py --proposed`):
- The `/lakes` read grant moves to `/lakes/$k/{brain, states, profiles, validation}`.
- `/lakes/$k/speciesPresence` becomes readable only by users with `/access/privateResearchUsers/{uid} === true` (who must also be ops users).
- Users may read their own flag.

**Before the rules deploy,** Ops must:
- handle `PERMISSION_DENIED` on `/lakes/{k}/speciesPresence` (`lakePanels.tsx:228`) as "restricted", not as an error;
- keep showing the sanitized `/lakes/{k}/brain/speciesPresenceSummary` (counts only) to every ops user;
- never read `/lakes/{k}` as a whole node (Ops does not today).

## OPS-5 `/jobs`

`/jobs/lake-brain-ledger-daily` gains `owner: "lake-brain"`, `kind: "Cloud Scheduler job"`, `triggers: ["lake-brain"]` and no "unmanifested workload" warning. This takes effect after the orchestrator syncs `/jobs` again. Additive.

## Compatibility rules

- All new fields are additive. Ignore unknown fields.
- Ops PRs #8, #9 and #10 all carry the three old reads (`windBrain.tsx`, `brainPaths.ts` `engineScore`, `lakeBrain.tsx` slot `stale`). The change belongs in whichever of those merges first, or in a separate Ops PR. The Engine does not depend on which.
- `/control/engineeringStatusV1` stays absent (O-1 off). That is unchanged.
