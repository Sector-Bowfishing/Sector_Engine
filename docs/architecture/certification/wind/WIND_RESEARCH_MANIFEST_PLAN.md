# Wind Brain: workspace manifest plan (Phase 2, Part A)

A draft `manifest.json` and a full per-file SHA-256 catalog were generated **read-only** and stored in the private handoff folder. **They were not placed in the workspace** (no move or adoption is approved yet). This document defines the contract and the decisions per artifact group.

## 1. Manifest contract (`BRAIN_RESEARCH_WORKSPACE_V1.md` §2, restated)
`{brainId, folder, owner, updatedAt, entries: [{path, class, bytes, sha256?, licence, adoptedFrom, backup}], backups: [{location, kind, verifiedAt}]}` at `Sector Research/wind-brain/manifest.json`. Draft additions (proposed, not yet a standard): `decision`, `backupRequired`, `notes`, `sealed` (for H2). `adoptedFrom` is mandatory for anything moved or copied in. Large datasets are referenced by manifest + hash; bytes live in the private backup.

## 2. Decision vocabulary
`ADOPT` (bring into the workspace, then back up) · `REFERENCE_IN_PLACE` (leave where it is, record location + hash/commit) · `DERIVED_REBUILDABLE` (rebuild from a named script and inputs; manifest only) · `SHARED_REFERENCE` (one immutable reference copy in `shared/`, owner named) · `HISTORY` (immutable, preserve) · `OBSOLETE_CANDIDATE` (never deleted on this basis).

## 3. Decisions by group (from the draft manifest; paths in the private handoff)
| Group | Files | Bytes | Class | Decision | Backup required |
|---|---:|---:|---|---|---|
| Execution list + log history (`live-meta/executions`, `brainlogs`) | 2 | 783,747 | HISTORY | ADOPT → `validation/history/` | **yes, first** |
| Live run ledgers | 173 | 577,311 | OBSERVATION_VALIDATION | ADOPT → `validation/ledger/` | yes |
| Run summaries | 173 | 181,278 | OBSERVATION_VALIDATION | ADOPT → `validation/runs/` | yes |
| Cycle results | 16 | 72,187 | HISTORY | ADOPT → `validation/cycles/` | yes |
| Analysis outputs incl. score-refresh trail and local-only variants | 47 | 2,213,811 | DERIVED / HISTORY | ADOPT → `analysis/`, `validation/score-history/`; dedupe the 15 byte-identical git copies by sha256 reference | yes |
| `live-meta-mirror` | 3,585 | 289,272 | DERIVED | DERIVED_REBUILDABLE | no |
| Lake Registry copy | 596 | 21,691,491 | DERIVED copy of a Lake-owned publication | SHARED_REFERENCE (one copy, owner Lake Brain) or consume the published registry | no |
| `rows_v50.pkl`, `rows_tonight_p10p50.pkl` | 2 | 12,663,136 | DERIVED, provenance unknown | ADOPT → `datasets/unverified-provenance/` with a note | yes |
| ICESat-2 granule manifest | 1 | 2,675 | RESEARCH (source record) | ADOPT → `sources/` | yes |
| Provider bake-off archive | 2,151 | 937,325,497 | RESEARCH + OBSERVATION_VALIDATION | ADOPT after the collector decision → `validation/provider-bakeoff/` | **yes** |
| Live mirror / early archive | 5,622 | 53,829,682 | HISTORY | REFERENCE_IN_PLACE until the bucket is versioned | yes (via the bucket) |
| `derived/` join tables | 46 | 166,205,714 | DERIVED | DERIVED_REBUILDABLE; keep in place until scripts are repointed | no |
| Git-tracked preregistrations, freeze files, ledgers, reports (private iOS repo and Engine branches) | — | ~4 MB | OBSERVATION_VALIDATION / RESEARCH | REFERENCE_IN_PLACE by commit + sha256; copy into `validation/` and `research/` after backup exists | yes (copy) |
| Historical NOAA corpora (365 MB), WindNinja/SWAN (55 MB), local Python env (535 MB) | — | — | RESEARCH / RESEARCH / RUNTIME | REFERENCE_IN_PLACE / ADOPT (low priority) / `OBSOLETE_CANDIDATE` | corpora no; WindNinja/SWAN yes |

## 4. Hash and verification method
1. Read-only SHA-256 of every file (done for 12,417 files across the five trees). The catalog records size, mtime and hash, and flags any file modified in the last 30 minutes as "hot" (none were).
2. At copy time, re-hash source and destination; mismatch = stop.
3. For the bake-off, the copy is a point-in-time snapshot: files older than the current collection hour are immutable; the manifest records the snapshot time and the file list; files written afterwards belong to the next snapshot.
4. For pickles: hash bytes only. They are not opened with any Python loader.
5. The manifest is regenerated and diffed after every adoption step; a changed hash for a source-class artifact is an incident.

## 5. `shared/` candidates (none to be moved now)
Lake Registry geometry (owner Lake Brain; prefer the published contract); NOAA reference history (owner and acquirer Wind; move only if another Brain needs it); provider licence captures (acquirer Wind). Each needs owner, acquirer, consumers, mutability, versioning and licence recorded before anything is placed there.
