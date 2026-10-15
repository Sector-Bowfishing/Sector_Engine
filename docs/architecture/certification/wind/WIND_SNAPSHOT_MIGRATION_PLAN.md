# Wind Brain: snapshot duplicate migration plan (Part G)

> **Update (Publisher V2):** Wind no longer authors `/snapshots/{k}/latest/wind` or `brainVersions/wind`. The Publisher derives them as `DERIVED_COMPATIBILITY_PROJECTION`s (`wind-snapshot-copy-v1`, `wind-snapshot-brainversion-v1`) from the authorised `/lakes/{k}/states/wind` and `/brains/wind/version` in the same atomic plan, with this plan's S2-S7 as the retirement gate. The reader-migration steps below are unchanged.

**Nothing is retired. `/snapshots/{k}/latest/wind` keeps being written until its readers have moved and the 14-step procedure completes.**

## 1. Facts (verified)
- `/lakes/{k}/states/wind` and `/snapshots/{k}/latest/wind` are **byte-identical for all 4 live lakes** (re-verified live, 2026-10-15). `wind-hourly` writes the same object twice, in one PATCH per lake.
- The snapshot node is a multi-Brain row (`/snapshots/{k}/latest/{lakeId, waterClarity, waterTemperature, lakeState, sectorIntelligence, wind, depth, brainVersions}`); only the `wind` child and `brainVersions.wind` are Wind's.
- **Readers of the snapshot copy:** Sector Ops (whole-row listener `/snapshots/{k}/latest`: lake wind detail, Wind state card, Brain page Wind tab) and Sector Intelligence (`snapshots/{k}/latest` → `.wind`; evaluation extracts sustained/gust/observation/forecast time). Intelligence is PARKED (pilot only; Wind dependency optional, 6 h).
- **Readers of `states/wind`: none found** in Ops, Intelligence, orchestrator or customer apps. (Research/diagnostic scripts may read it; none are in production paths.)
- **Writers:** only `wind-hourly` (and the manual CLI). The Publisher's Wind schema authorises `/snapshots/{k}/latest/wind` as `LEGACY_READER_PRESENT`, same atomic plan as its source (the artifact builder puts both in the `lake-live` scope so they cannot diverge).

## 2. Target canonical state
**`/lakes/{k}/states/wind`** is the canonical Wind runtime state. `/lakeFleet/{k}/slots/wind` stays a `DERIVED_PROJECTION` (compact summary: readiness, stale, kind). `/snapshots/{k}/latest/wind` is a **compatibility projection, never a second truth**: it carries the same bytes by construction in the same plan, and nothing may write it independently.

## 3. Migration order
| Step | Action | Gate |
|---|---|---|
| S0 | Classify the snapshot path `LEGACY_READER_PRESENT` (done in the ownership matrix and the Publisher schema) | — |
| S1 | Publisher publishes both paths in one plan (shadow-proven here) | cutover step 9 |
| S2 | **Sector Ops** moves its Wind views to `/lakes/{k}/states/wind` (listener on the one child, not the row); behind a feature switch, old path still available | Ops lane; field-level equality test old vs new for the 4 lakes |
| S3 | **Sector Intelligence** moves `wind` reads to `states/wind` (parked; do before it is unparked) | Intelligence lane |
| S4 | Compatibility window: both paths written; length is a decision for Michael (proposed: ≥ 30 days after the last reader change). RTDB gives no per-path read telemetry, so "zero readers" is proven by code search in all repos plus review of Ops listener paths | Michael |
| S5 | Prove writer count = 0 for any non-Publisher writer | after cutover and IAM hardening |
| S6 | Export `/snapshots/{k}/latest/wind` to private history (rollback copy) | Publisher history bucket |
| S7 | Michael approves; remove `/snapshots/{k}/latest/wind` from Wind's authorised families, then delete the Wind child per-lake (not the whole snapshot row, which other Brains use) | explicit approval |

## 4. Rollback
Until S7 nothing is removed, so rollback = switch the reader back (feature switch) to the snapshot path. After S7: restore from the S6 export through the Publisher (an explicit rollback mechanism, Publisher requirement P5).

## 5. Required proofs before retirement
Zero readers (all repos: Engine, Ops incl. worktrees, iOS, Android, Web, scripts), zero non-Publisher writers, field-level equality demonstrated over the compatibility window, rollback export verified, Michael's approval. Duplication alone is not a reason to delete.

## 6. Cost note
The snapshot copy is ~32 % of the database across all Brains. For Wind it is 4 × 5.4 KB today; it only matters when the fleet grows. Its removal is a database-wide decision made Brain by Brain, not here.
