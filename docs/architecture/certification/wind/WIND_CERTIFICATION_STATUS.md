# Wind Brain: Architecture Certification V1 status

**Status: `BLOCKED: PUBLISHER`** (with `PARTIAL` exit evidence). Reason: Publisher V1 (CERT-2, separate shadow-only platform task) does not exist, so exits F, G and the cutover cannot be demonstrated; and exit B (private versioned backup of irreplaceable Wind research/evidence) fails today and needs approval-gated resource creation.
Standard: `brain-certification-v1` (foundation approved 2026-10-14, CERT-1..9). Base `fab115e9`, branch `cert/wind-architecture-v1` (local, not pushed). Evidence date 2026-10-15.

## 1. Exit evidence A-J
| | Evidence | Result |
|---|---|---|
| A | Identity | **PASS**: `wind`, "Wind Brain", domain `condition`, CALIBRATION; unchanged |
| B | Local research inventory + backup | **INVENTORY DONE / BACKUP FAIL**: no private versioned copy of RESEARCH/OBSERVATION_VALIDATION/HISTORY exists (bake-off archive 937 MB, execution/log history, score trail, unversioned bucket). Local Mac and an OS-purgeable cache are the only copies of some data |
| C | Remote storage | **PARTIAL**: inventory done (4,409 objects, 50.76 MB); one manifest; hashes unverified; no versioning; image retention unverified |
| D | RTDB ownership matrix | **PASS** (`WIND_RTDB_OWNERSHIP_MATRIX.md`); findings listed |
| E | Code trace | **PASS**: no untraced writer; one specialist writer plus platform projections. Note: the newer adoption-lineage publisher is not deployed |
| F | Security | **FAIL / not testable** without Publisher; specialist write capability exists; server-side path enforcement absent. Detail private |
| G | Publication tests | **NOT RUN** (Publisher absent). Known defects: partial publication, null-on-miss, second source of truth |
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

## 3. Blockers
1. **Publisher V1** (CERT-2).
2. **Backup targets** (CERT-3 artifact/history bucket and CERT-4 research-backup bucket) do not exist; creating them needs approval.
3. Wind identity hardening (CERT-9) requires private IAM/rules work with approval.
4. Reader migration (Ops, Sector Intelligence) is in other lanes.

## 4. Decisions Michael must make
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
