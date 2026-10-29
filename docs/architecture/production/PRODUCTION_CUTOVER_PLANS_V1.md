# PRODUCTION CUTOVER PLANS V1 (Wind, Fish, Water Clarity)

**Nothing here is authorised.** Each plan is a draft runbook skeleton; each live step needs Michael's explicit approval for that exact step. Common prerequisites for ALL plans: Publisher LIVE V1 built and merged (P1-P6, P12, P2 adapter), baseline reconciled from a PRIVATE read-only live capture (P4), write-security gate designed and approved, `PRODUCTION_EXIT_GATE_V1` runbook staged, deployed-image lineage verified (shared-orchestrator rule), pre-cutover RTDB export and previous image digest recorded privately, scorer publication trigger (S1) landed.
Authoritative order (machine-readable, enforced: `jobs/brain_platform/sector_brain_platform/cutover_order.json`): **Water Clarity -> Wind -> Water Temp -> Lake -> Sector Intelligence**; the **Fish** step of PL-10 is performed by the target Brains `fish-knowledge` then `fish-behavior` AFTER the approved M01-M03 split. The legacy combined `biological-state` is NEVER published as a combined unit: it stays on its direct writer, unchanged, and no Fish/Biological production data is changed by any cutover before the split. (Corrected 2026-10-29 from the earlier 'Water Clarity -> Fish -> Wind', which treated the combined package as the Fish Brain.) Depth and Vegetation are BLOCKED.

**Health ownership (Cortex 3.1, owner decision 2026-10-29):** the Publisher never writes `/health/*`. Wherever a plan below lists `/health/brains/...` or `/health/sources/...` in a Publisher write set, that is superseded: the Orchestrator derives those from the published `/brains/{id}/...` and `/sources/{id}` (`health_mirror.py`).

## Water Clarity (pilot)
| Item | Plan |
|---|---|
| BEFORE | `run.py` (C1, manual) writes batches then whole-node `/brains/water-clarity` and `/health/brains/water-clarity`, `/health/jobs/..`; Publisher SHADOW; score 8.0 FROZEN; jobs paused |
| write owner | Publisher (after cutover) for the approved `/brains/water-clarity/{child}`, `/validation/water-clarity`, `/sources/{id}`, lake/fleet/snapshot families in its registration (NO `/health/*`: Orchestrator-derived); Orchestrator for process health/`/jobs`; scorer for `/scores` |
| dry run | `run.py` builds the sealed bundle (already done in memory); evaluate against live read (GET only); equivalence diff plan vs live; zero unexplained diffs; check artifact size vs `max_bytes` for the 621-lake fleet (split by scope or manifest-last) |
| artifact | `clarity-publication-v1`, one run = one artifact |
| expected write set | child-level only; `publication` in the same atomic update; typed DELETE for `lastError`; no whole-node keys |
| legacy writer state | **disabled in the same change as go-live**: the PR flips `cutoverStatus`, removes the two `run.py` RTDB write sites and their AST pin; `--dry-run` remains |
| production mutation | exactly one Publisher publish after approval |
| readback | independent GET of every planned path = artifact content (X15); `publication` record (X10) |
| score | `/scores/water-clarity` still 8.0 under the same scoreType/version (X12); scorer runs via S1 trigger, not by the Publisher |
| health | healthV1 not blanked (G1 compat or accepted UNKNOWN for a manual CALIBRATION Brain); no Brain-authored process fields (X11) |
| rollback | republish the pre-cutover artifact through the P5 path, or restore from the pre-cutover export; rehearse first in a non-prod database (X13). GCS C2-C4 untouched |
| post-cutover guard | invariant 10 + AST pin (zero write sites) + `cutover_guard` + `/brains/water-clarity` whole-node key rejected by Publisher path ownership; IAM narrowing + denial test (X16) is a later separately approved step |

## Fish (DEFERRED: not part of any current cutover; applies to `fish-knowledge`/`fish-behavior` after the split, never to the combined package)
| Item | Plan |
|---|---|
| BEFORE | orchestrator in-process `run.py --write` (single `rtdb.update`, 33 Fish-owned paths for the 2026-10-17.1 release); live release 2026-10-17.1, Fish score 5.1; Publisher SHADOW |
| write owner | Publisher for `/species/*` summaries, `/brains/biological-state/{children}`, `/validation/biological-state`, `/health/brains/biological-state/{status,staleLakeCount}`; Orchestrator exec records for process health; scorer for `/scores` |
| dry run | `run.py --dry-run` on the real private bundle (never run yet): outputFingerprint recorded; plan vs live GET; expected diffs only process-health fields and volatile `updatedAt`; forced re-run parallel comparison |
| artifact | `fish-publication-v1`, emitted create-only to the Brain's artifact prefix and signalled by the Orchestrator (P8); new `run.py` artifact path added beside `--write` first |
| expected write set | same logical set as today minus process-health fields; species removals only as typed DELETE `SPECIES_REMOVED_FROM_REGISTRY`; `plan()` input children (`researchVersion`, `manifestSha256`, `version`, `health`) MUST be preserved or `--plan` loops PUBLISH |
| legacy writer state | `--write` retired in one PR with `cutoverStatus`, orchestrator step changed to artifact emission, `fish_cert_spec` allowed site removed; `--plan` stays read-only |
| production mutation | one Publisher publish of the already-live release after approval (state-neutral), then the next real release flows through the Publisher |
| readback | published `researchVersion`/`manifestSha256` == release pointer; field-level equality of species/registry/validation vs pre-cutover export |
| score | Fish score computed from live facts must stay 5.1 (golden baseline + X12); scorer triggered by S1 |
| health | exec records cover process fields for in-process runs (X11) |
| rollback | repoint release pointer (object-versioned) -> `--plan` PUBLISH -> republish through the P5 rollback path (otherwise `ARTIFACT_OLDER_THAN_BASELINE`); species added in the newer release are removed on republish (known, documented) |
| post-cutover guard | invariant 10 + AST pin; shared writer identity split before X16; scorer unchanged |
| open decisions | D-1, D-3; species identity boundary (parked) |

## Wind
| Item | Plan |
|---|---|
| BEFORE | hourly scheduled job (validation exception) -> `safe_publish` -> one PATCH per call across lake state/profile/validation, snapshot copies, fleet rows, whole-node `brains/wind`, `validation/wind`, `sources`, `health/*`, activity + prune |
| write owner | Publisher for the artifact families; Orchestrator for process health/`/jobs`/execution freshness (G1/G2); Platform for activity retention (G3), `lakeId` (G4), scores |
| dry run | wire `artifact.py` additively after `safe_publish` (shadow only, no exit-code change); >= 7 days of Publisher plan vs the legacy writer's stored values (equivalence evaluator); zero unexplained diffs; reconcile baseline |
| artifact | one `wind-publication-v1` artifact per run; size handled by scope split or manifest-last |
| expected write set | per Wind's Gate P hardening: no `snapshots/*/latest/lakeId`, `lakeFleet/*/lakeId`, `/health/jobs/*`, process-health fields; `snapshots/*/latest/wind` + `brainVersions/wind` as Publisher-derived projections in the same atomic update |
| legacy writer state | `publish.publish` RTDB call and `RtdbWriter` removed from the job path in the same PR as `cutoverStatus` (GCS archive stays) |
| production mutation | scheduled hourly publishes through the Publisher only after approval and a rollback rehearsal |
| readback | equality vs pre-cutover export; `/conditions` diff = none; Ops views, healthV1, SI snapshot read unchanged |
| score | `/scores/wind` unchanged (frozen); no BWIS nesting change in this step |
| health | G1 compat records exist so Ops keeps the job card; G2 supplies execution freshness so SKIP does not look stale |
| rollback | republish prior artifact (P5) / restore export / redeploy prior image (recorded digest) |
| post-cutover guard | invariant 10 + AST pin; IAM narrowing and denial test (X16); snapshot retirement stays a separate 14-step reader-migration procedure |
