# Wind Brain: Architecture Certification V1 status

**Status (2026-10-15, Phase 2): `SHADOW_INTEGRATION_READY`, i.e. `PARTIAL — LIVE CUTOVER PENDING`.** Not `ARCHITECTURE_CERTIFIED_V1`. Phase 1 status was `BLOCKED: PUBLISHER`; that blocker is now lifted for **shadow** integration only (Publisher V1 Shadow `d090c428` exists and Wind's artifacts pass it), but the live Publisher, backup resources, security enforcement and cutover do not exist and need separate approvals.
Standard: `brain-certification-v1`. Local branch `cert/wind-architecture-v1` (not pushed). Nothing live was changed in either phase.

## 0. Phase 2 summary
- **Research preservation:** plan and draft manifest complete; **nothing moved**. The provider bake-off collector is **still running** (not touched); no backup destination exists; ≈ 1.01 GB local + 50.8 MB bucket must get a private versioned copy. Approvals needed: `WIND_RESEARCH_PRESERVATION_PLAN.md` §5.
- **Publisher shadow integration:** Wind's artifact builder (5 artifacts: 3 baseline scopes of the lake-state schema + registry + sources) passes all 20 required proofs; 90 Wind tests and 251 Publisher tests pass. Findings F-1..F-9 for the platform lane: `WIND_PUBLISHER_SHADOW_INTEGRATION_REPORT.md`.
- **Snapshot duplicate:** migration plan written; `/snapshots/{k}/latest/wind` stays (`LEGACY_READER_PRESENT`).
- **Score:** unchanged and stable (3.3 / 3.1 mirror / BWIS 5.4).
- **Cutover:** 15-step plan prepared, not executed (`WIND_CUTOVER_PLAN.md`).

## 1. Exit evidence A-J
| | Evidence | Result |
|---|---|---|
| A | Identity | **PASS**: `wind`, "Wind Brain", domain `condition`, CALIBRATION; unchanged |
| B | Local research inventory + backup | **INVENTORY DONE, hashes + draft manifest done / BACKUP FAIL (plan ready; approvals pending)**: no private versioned copy of RESEARCH/OBSERVATION_VALIDATION/HISTORY exists (bake-off archive 937 MB, execution/log history, score trail, unversioned bucket). Local Mac and an OS-purgeable cache are the only copies of some data |
| C | Remote storage | **PARTIAL**: inventory done (4,409 objects, 50.76 MB); one manifest; hashes unverified; no versioning; image retention unverified |
| D | RTDB ownership matrix | **PASS** (`WIND_RTDB_OWNERSHIP_MATRIX.md`); findings listed |
| E | Code trace | **PASS**: no untraced writer; one specialist writer plus platform projections. Note: the newer adoption-lineage publisher is not deployed |
| F | Security | **FAIL** (live enforcement not done; Publisher-side path denial is proven in shadow only); specialist write capability exists; server-side path enforcement absent. Detail private |
| G | Publication tests | **SHADOW PASS** (20/20 proofs: valid, SKIP, SHADOW, rejections, null-safety, determinism, older-than-baseline); **live atomic publish and rollback NOT run**. Known defects: partial publication, null-on-miss, second source of truth |
| H | Score baseline | **BEFORE recorded** (3.3 `ENGINE_READINESS_SCORE`, `wind-certification-rubric-v1`); AFTER pending; no score changed |
| I | Downstream regression | **BEFORE recorded** (customer `/conditions` = Open-Meteo, no Wind Brain read, verified by code). No change made, so no diff to run; must be re-demonstrated at cutover |
| J | Final status | this document; Michael to review |

## 2. Findings (architecture)
1. `wind-hourly` is the only specialist writer; ~168 write requests/day; 7 non-atomic PATCHes per run; ~1,260 paths rewritten unconditionally.
2. `/snapshots/{k}/latest/wind` is an exact duplicate of `/lakes/{k}/states/wind` (4/4 byte-equal), and it is the path Ops and Sector Intelligence actually read; `states/wind` has no reader. Status `LEGACY_READER_PRESENT`; not retired.
3. Score identity violations: BWIS nested in `/scores/wind`; stale 3.1 mirrored in the registry and validation nodes (Ops shows 3.1); no `scoreType`.
4. Freshness lacks `staleAfter/expiresAt/freshnessStatus`; `lastSuccessfulRun` is the only registry-level time.
5. No canonical Wind release/manifest; evidence JSON is baked into the job image.
6. `/jobs/wind-hourly` declaration is a subset of true outputs; BRAIN.md has drifted from code.
7. Source records lack `authorizedConsumers`.
8. Customer boundary verified unchanged.

## 3. Blockers (for live cutover and certification)
1. **Production Publisher** (P1-P11: live sink, bucket adapter, atomic live update, baseline reconciliation, rollback execution, API service).
2. **Backup targets** (CERT-3 artifact/history bucket and CERT-4 research-backup bucket) do not exist; creating them needs approval.
3. Wind identity hardening (CERT-9) requires private IAM/rules work with approval.
4. Reader migration (Ops, Sector Intelligence) is in other lanes.

## 4. Decisions Michael must make
0. (Phase 2) Collector: stop / repoint / snapshot-only; research moves; bucket creation; the Publisher-lane items F-1..F-8; ownership of the four unauthorised paths (`lakeId` ×2, `brainVersions/wind`, `health/jobs/wind-hourly`); stale-child/delete policy (F-4).
1. Approve creating the CERT-3/CERT-4 buckets and enabling versioning/backup for `sector-wind-candidate` (**recommended first action**: it protects irreplaceable evidence and carries no behaviour change).
2. Stop or repoint the running local bake-off loop so it can be adopted and backed up (it is still collecting).
3. Approve adopting Wind research into `Sector Research/wind-brain` (and path repointing in research scripts).
4. Wind release definition (`WIND_PUBLISH_ARTIFACT_V1.md` §4) and whether hourly `observationTime`-only changes are material (§3).
5. Freshness: confirm `staleAfter` derivation and whether `expiresAt` is defined.
6. Authorize the relabel/move of BWIS and the stale 3.1 mirror (and the Ops reader change) as a separate scoring-identity change.
7. Lineage: keep `feat/wind-brain-adoption` and `deploy/wind-internal-validation` as distinct lineages, and when to bring the adoption publisher onto the artifact path.
8. Open-Meteo commercial licence (flagged by research; outside architecture).

## 5. Not done / not changed
No deploy, no live write, no rules/IAM change, no bucket creation, no scheduler change (`wind-hourly` untouched and ENABLED), no research moved, no score changed, no branch merged or pushed, Fish Brain not started.
