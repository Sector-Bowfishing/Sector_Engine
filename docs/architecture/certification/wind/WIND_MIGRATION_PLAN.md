# Wind Brain: migration plan

> Phase 1 outline. The exact, gated cutover sequence is `WIND_CUTOVER_PLAN.md`; snapshot retirement is `WIND_SNAPSHOT_MIGRATION_PLAN.md`; research protection is `WIND_RESEARCH_PRESERVATION_PLAN.md`.

Each step needs its own session-level approval where it changes anything live. **Steps 0-1 are done or doc-only; nothing from step 2 on is authorized yet.**

| # | Step | Changes | Gate / approval | Rollback |
|---|---|---|---|---|
| 0 | Read-only phases 1-7 (this session) | docs on local branch | done | — |
| 1 | Michael decisions (list in `WIND_CERTIFICATION_STATUS.md` §4) | none | Michael | — |
| 2 | **Protect irreplaceable evidence first**: create the private versioned research-backup bucket (CERT-4) and the artifact/history bucket (CERT-3); enable versioning for / back up `gs://sector-wind-candidate`; snapshot `live-meta/{executions,brainlogs}.json`, the provider bake-off archive, `cycles/`, score trail | new buckets, copy only | approval (create buckets) | delete copies only if never referenced |
| 3 | Stop or repoint the running local bake-off loop, then adopt research into `Sector Research/wind-brain` (`validation/` first), repoint hard-coded script paths via config/env, write `manifest.json` with `adoptedFrom` | local moves | approval (research moves) | originals retained until backup verified; move-and-reference |
| 4 | Define `wind-model-v1` release + manifest; fix doc drift (BRAIN.md, `CERT=3.1`) | docs/code, no live | approval for code | git |
| 5 | **Wind artifact producer** (Wind side): compute the §1 artifact, write to artifact store, fingerprints, freshness fields, explicit removals; dry-run only, **no RTDB write** | Wind code (additive) | approval; needs CERT-3 bucket for storage (can start with a local file output) | git |
| 6 | **Publisher V1 shadow** (separate platform task, CERT-2): dry-run diff Publisher output vs what `wind-hourly` actually wrote; zero diff required | none live | Publisher exists | n/a |
| 7 | Security: Wind identity loses database write; Publisher identity authorized; rules/IAM verified by tested denials; cross-domain test (`wind` → `/speciesProfiles/common_carp` rejected) | IAM/rules (private) | approval | restore prior bindings (recorded privately) |
| 8 | **Cutover**: Publisher publishes Wind (incl. snapshot copy in the same atomic publish); `wind-hourly` direct publish disabled after the shadow zero-diff period; exercise rollback in shadow first | scheduler/job config | approval; rollback package ready | redeploy prior image / restore from published history |
| 9 | Reader migration: Ops → `/lakes/{k}/states/wind` and `/scores/wind`; Sector Intelligence → `states/wind`; monitor | reader code (other lanes) | per reader | keep snapshot |
| 10 | Score identity cleanup: BWIS out of `/scores/wind`, drop registry/validation score mirrors, add `scoreType` | schema | approval | revert |
| 11 | Retire `/snapshots/{k}/latest/wind` via the 14-step procedure (zero readers/writers, history export, approval) | deletion | Michael | history export |

## Rollback today (before any change)
`deploy/wind-internal-validation` @ `413bbbae` holds a **never-exercised** internal deploy package for the *newer* publisher on the adoption lineage, not a restore of the current deployed code. The current job can be restored by redeploying image `e6a5026f5d0f`'s digest (recorded privately). Target rollback: restore the previously Publisher-published artifact from history and redeploy the prior image, then verify the output fingerprint.

## What must not happen
Do not "fix" the single-writer problem by restoring direct writes as the final design. Do not merge `feat/wind-brain-adoption` as part of certification; its newer publisher changes writes (fleet only on change) and must go through the artifact path instead. Customer `/conditions` is untouched at every step; regression diff before and after steps 7-9.
