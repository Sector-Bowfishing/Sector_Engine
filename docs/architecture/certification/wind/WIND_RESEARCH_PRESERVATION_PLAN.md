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
