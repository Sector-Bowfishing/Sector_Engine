# Wind Brain: research preservation plan (Phase 2, Part A)

**Status: PLAN ONLY. Nothing was moved, copied, stopped, deleted or uploaded.** No private backup destination is approved or exists, so this phase stops here for Michael's decisions (§5). Exact local paths, per-file hashes and the draft manifest are in the private handoff folder, not in this repo.

## 1. Re-check of the local state (2026-10-15 ~03:10Z)
| Check | Result |
|---|---|
| `Sector Research/wind-brain`, `shared` | still **empty** |
| Legacy research directory (`Sector_Research_Data/wind-brain`) | 4,598 files, 38,481,056 B; mtimes 2026-10-07..10-14; no file written in the last 30 min |
| Local cache directory (the 2.1 GB macOS cache) | present; bake-off 937,325,497 B (2,151 files, dated 2026-10-09..10-15); live-mirror 37.65 MB; archive 16.18 MB; derived 166.2 MB |
| **Active Wind research writer** | **YES. The provider bake-off collector is still running** (same process as at the first audit, up ~3 days) and logs a collection of 228 samples every hour at :20. It was **not** stopped, repointed or touched |
| Remote backup now? | **No.** No research-backup or artifact/history bucket exists in the project; `sector-wind-candidate` still has versioning off and 196 ledger objects (the local copy holds 173) |
| Hashing | every file in the five trees was read-only SHA-256 hashed (zero errors). None of the at-risk files was changed. Pickles were hashed as bytes only, never loaded |

## 2. What must be preserved, in priority order
| # | Item | Class | Size | Why at risk | Method |
|---|---|---|---:|---|---|
| 1 | `live-meta/executions.json`, `brainlogs.json` | HISTORY | 0.78 MB | Cloud Run executions and Cloud Logging age out (~30 d); the **only** copy of older reliability-gate evidence | immediate private versioned copy; hashes recorded |
| 2 | Provider bake-off archive (MADIS / Open-Meteo / NOAA snapshots + normalized + loop log) | RESEARCH + OBSERVATION_VALIDATION | 937 MB (growing) | partly **not reconstructable** (source retention is limited); sits in an OS-purgeable cache; **actively written** | needs a collector decision (§3), then versioned copy |
| 3 | Validation ledgers and run summaries (`live-meta/ledger`, `live-meta/runs`), `cycles/`, score-refresh and canonical-rescore outputs, `live_reliability_*` | OBSERVATION_VALIDATION / HISTORY | ~3 MB | gate evidence; origin (bucket) is unversioned; some local variants differ from git | private versioned copy |
| 4 | Preregistrations, freeze files, holdout and nowcast ledgers, score change log | OBSERVATION_VALIDATION | ~2.2 MB | in git (private iOS repo, pushed). Risk = branch loss | **no copy needed now**; reference by commit + file sha256; include in the backup manifest; mirror when the research bucket exists |
| 5 | Local-only variants: `fleet_fetch.json`, `field_pairs.json`, `readiness/`, `live_reliability_latest.json` | DERIVED (differ from committed copies) | ~0.75 MB | not in git | copy with the batch above |
| 6 | Provenance-uncertain pickles `rows_v50.pkl`, `rows_tonight_p10p50.pkl` | DERIVED, provenance unknown | 12.7 MB | no committed generator | preserve bytes + hash + provenance-uncertainty note; **never load or execute**; do not delete even if "rebuildable" is unproven |
| 7 | `sector-wind-candidate/wind/v1` (live forecast/analysis archive, ledger, fetch tables) | OBSERVATION_VALIDATION / CANONICAL candidate | 50.76 MB | unversioned; 7-day soft delete only; hourly writer | enable object versioning (approval) or copy to the versioned bucket; H2 values stay sealed |
| 8 | Local live-mirror and archive (copies of #7 including sealed H2 values) | HISTORY | 54 MB | OS-purgeable cache | keep until #7 is backed up and the mirror is verified complete |

**Total that must have a private versioned copy: ≈ 1.01 GB local + 50.8 MB bucket.** Rebuildable and not requiring a backup: `live-meta-mirror` (rebuild script), `derived/` (hours to rebuild, but a hard dependency of ~8 scripts, so keep in place until they are repointed), historical NOAA corpora (re-downloadable), the Lake Registry copy (consume the published registry), the 535 MB local Python environment (`OBSOLETE_CANDIDATE`, never deleted on that basis).

## 3. The active collector (decision needed, not taken)
A directory with a running writer must not be moved. Options:
- **A. Stop after Michael approves**, snapshot-copy, then restart it pointing at the workspace. Cleanest history; creates a short gap in the hourly sample series.
- **B. Repoint future writes** into the workspace without stopping: needs a code/config change to the collector's output path and a restart anyway, so it is A with a smaller gap.
- **C. Leave it running, copy a consistent point-in-time snapshot** (read-only copy; files older than the current hour are immutable) to the backup destination now, and migrate later. Lowest risk; **recommended first** because it protects the data without interrupting collection. The collector itself is an existing research process that belongs to the same decision as the research move.

## 4. Backup design (prepared, not executed)
- **Destination (CERT-4, approved design, not created):** one private, versioned research-backup bucket with a prefix per Brain workspace (`wind-brain/`). Public-access prevention on; no delete rights for any ordinary identity; object versioning on; no lifecycle rule on RESEARCH/OBSERVATION_VALIDATION/HISTORY classes.
- **Interim, if bucket creation is not approved:** none. A second local disk copy does not satisfy BRAIN_RESEARCH_WORKSPACE_V1 §3.7 ("the Mac is never the only durable copy").
- **Procedure:** (1) freeze list = draft manifest entries marked `backupRequired`; (2) re-hash at copy time and compare with the recorded SHA-256; (3) upload create-only; (4) verify remote object hashes; (5) record `backups[{location, kind, verifiedAt}]` in the workspace manifest; (6) only then may any move happen, as move-and-reference with `adoptedFrom`.
- **Never** unseal or recompute H2; the sealed archive values are copied byte-for-byte and the H2 sealing date (2027-01-01) is recorded in the manifest.
- **Licence:** per-source notes (Open-Meteo free-tier non-commercial; NOAA/MADIS/IEM public; NASA Earthdata login). Nothing restricted is placed in `shared/`.

## 5. Approvals needed (nothing proceeds without them)
1. Create the private versioned research-backup bucket (CERT-4) and, separately, the artifact/history bucket (CERT-3).
2. Enable versioning on `sector-wind-candidate` (or copy it into the new bucket).
3. Collector decision: A, B or C above.
4. Approve adopting research into the workspace (moves) after the backup is verified.
5. Approve repointing the hard-coded script paths (cache directory, legacy research directory, the iOS evidence directory).

## 6. Execution record: durability pass (2026-10-15) — status `WIND_RESEARCH_PRESERVATION_BLOCKED_ON_STORAGE_APPROVAL`
**What was done (all read-only on sources; collector untouched):** a verified, byte-identical, point-in-time **snapshot** of every preservable high-priority Wind artifact was written to a read-only staging directory on the same machine (outside any Brain workspace; no move, no copy-and-forget, no relocation into the workspace). **It is SNAPSHOTTED, not BACKED_UP: it is not durable against loss of the Mac.**
| Item | Result |
|---|---|
| Method | per file: stat → stream copy while hashing (SHA-256) → stat; identical stat = STABLE. Active collector files copied in the quiet window between hourly collections (earliest :31, latest :19); append-only logs would have been kept as prefix snapshots and anything else unstable as `ACTIVE_NOT_SNAPSHOTTED` (none occurred) |
| Research trees | 15,326 files, 1,177,294,300 B, all STABLE; destination re-hashed and source re-hashed afterwards: **0 destination mismatches, 0 source mismatches, 0 source changes, 0 missing, 0 errors** |
| Active provider bake-off | 2,281 files, 1,019,971,312 B, all STABLE (snapshot taken in a 3 s window); files written after the snapshot are intentionally not in it |
| Candidate bucket (private archive) | 4,673 objects, 53,253,890 B downloaded; every object's MD5 and size equal to the listing taken before; none changed during the download; no new objects appeared |
| Whole staging set | 20,013 files, 1,233,751,656 B; an independent full re-hash of the staging tree equals the per-file records (0 differences); made read-only |
| Pickles | treated as opaque bytes (never loaded); provenance `UNKNOWN/UNVERIFIED` recorded |
| Private equivalence evidence | preserved in the same staging set (SNAPSHOTTED); digests: capture `8d4f8b16…`, result `8a552258…` (evaluator `wind-shadow-equivalence-v1`, captured 2026-10-15T13:55:20Z, class OBSERVATION_VALIDATION/HISTORY, retention: never delete). Not committed |
| Git-held research | Engine wind branches and the private iOS branch: local HEAD equals the hosted ref (`git ls-remote`): REMOTE_VERIFIED; no copy needed; do not delete branches |
| Not snapshotted (by policy) | public re-downloadable NOAA corpora (365 MB), rebuildable derived join tables (166 MB), NHD inputs, the local Python environment in use by the collector, docker images |

**Why it stops here — storage:** no approved remote destination exists. The only existing Wind store (`sector-wind-candidate`) is **not appropriate** as the backup: versioning is off; soft delete (7 days) is not archival; the producing job's identity holds object-admin there (it could overwrite or delete a backup); it also carries overwritten runtime objects. Enabling versioning on it would be a bucket configuration change (separate approval) and still would not stop deletion by that identity. The approved design (CERT-4: one private, versioned research-backup bucket, prefix per Brain) requires an explicit creation approval, which has not been given. **No bucket was created and nothing was uploaded.**

**Exact creation plan (prepared, not executed; `NOT-EXECUTED` script is in the private handoff folder):** private bucket in the project's region, uniform access, public-access prevention, object versioning on, soft delete 30 days, **no lifecycle delete rule** on these classes, no grant to the Wind job identity; upload create-only (`--no-clobber`) under `wind-brain/snapshots/2026-10-15/`; verify every remote object's MD5 against the pre-computed list, then re-run the SHA-256 comparison; only then do manifest statuses move SNAPSHOTTED → BACKED_UP → VERIFIED. Estimated size 1.23 GB (negligible storage cost).

**Approvals still needed:** (1) create the CERT-4 research-backup bucket and upload the staged snapshot; (2) separately: enable versioning on the candidate archive bucket (recommended defence-in-depth, not a substitute); (3) collector decision for continuing preservation of new bake-off data (stop / repoint / periodic snapshot); (4) later: the research relocation into the workspace.

## 7. Remote backup executed and verified (2026-10-15) — status `WIND_RESEARCH_PRESERVATION_READY_FOR_REPO_MIGRATION`
Michael approved CERT-4 implementation (research-backup bucket only; not CERT-3, not the Publisher, not Wind runtime). The blocker in §6 is removed.
- **Bucket:** `sector-research-backup` (the single logical reference for the CERT-4 research backup; per-Brain prefixes, Wind uses `wind-brain/`). Private, region `us-central1`, class STANDARD, **object versioning ON**, **soft delete 30 days**, uniform bucket-level access, public access prevention enforced, **no lifecycle rules, no retention lock**. The Wind runtime job identity has no access to it (an independent durability boundary). The bucket is research backup only: not runtime, not Publisher storage, not customer-facing. The candidate archive bucket was not touched and is not the backup.
- **Uploaded:** the frozen, previously verified staging snapshot, unchanged, to the immutable prefix `wind-brain/snapshots/2026-10-15/` (create-only, no overwrite, no `latest` alias). 20,013 objects, 1,233,751,656 bytes. The first pass stored 20,009; four larger files timed out and were stored in a second create-only pass; nothing was overwritten.
- **Verification:** remote inventory = expected (0 missing, 0 unexpected, 0 MD5 or size mismatches; the 4 zero-byte objects are real empty source files). **SHA-256:** every remote object was downloaded to a separate scratch area and re-hashed; 20,013 of 20,013 equal the staging SHA-256 list (**0 mismatches**), MD5 also equal. The bucket holds exactly 20,013 object versions and no others.
- **Manifest:** 31 entries moved SNAPSHOTTED → BACKED_UP → **VERIFIED**; 7 git-held entries remain REMOTE_VERIFIED (hosted refs match local HEADs). Pickles uploaded as opaque bytes (never opened); provenance remains UNKNOWN/UNVERIFIED. The private equivalence evidence is in the backup and stays private.
- **Unchanged:** original research, the active collector, the local staging snapshot, scripts, Wind runtime, IAM and Publisher. Cleanup of local copies is a separate future decision.
- **Open (not blocking the repo move):** data collected after 14:13Z on 2026-10-15 is not in this snapshot (a repeatable snapshot or collector decision is still pending); versioning on the candidate bucket is optional defence-in-depth; inherited project-level administrator roles can modify the backup bucket (private note; a hardening decision, not a Wind blocker).
