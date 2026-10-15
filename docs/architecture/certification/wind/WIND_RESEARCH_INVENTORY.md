# Wind Brain: research inventory (steps 2-3, exit B/C) — public-safe summary

Read-only. **Nothing was moved, copied or deleted.** `OBSOLETE_CANDIDATE` never means delete. Private absolute paths, byte-level file tables and the per-file record sheet are in the private handoff (outside the repo). Research *data* is never committed to this public repo.

## 1. Headline
1. `Sector Research/wind-brain` and `shared/` are **empty** (confirmed; so are the other seven Brain folders).
2. Existing Wind research data directory (`Sector_Research_Data/wind-brain`): **4,598 files, 38.5 MB logical (52 MB on disk), not a git repo, no backup.** Mostly rebuildable; exceptions below.
3. The largest local-only mass is a **2.1 GB macOS cache directory** (~76k files, not in git, the OS may purge it). It holds the historical forcing corpora, evaluation join tables, a provider bake-off archive (937 MB) and a live-archive mirror. Many research scripts hard-code its path. (The earlier closeout figure of 5.8 GB is not current.)
4. A **provider bake-off collection loop is still running locally** and writing into that cache. Its observation and shadow-forecast snapshots are partly irreplaceable (source retention is limited). It must not be moved while it runs. Not touched by this session.
5. All Wind **code, preregistrations, reports, frozen evidence, ledgers and decisions are in git and pushed** (Engine branches and the private iOS repo). Risk there is branch deletion or force-push, not local loss. Only the ~85-file `jobs/wind-hourly` core is in `main`'s lineage; the rest is spread over unmerged branches.
6. **No field observations exist yet** (only EXAMPLE packets/templates). Wind's OBSERVATION_VALIDATION today = preregistrations + freeze files, frozen CAL/H1 evidence, holdout/nowcast ledgers, the score change log, reliability-gate history, and the sealed live archive.
7. **No Wind PDFs or licence documents exist anywhere**; licence terms live only inside markdown (Open-Meteo free tier is non-commercial; NOAA/IEM/MADIS/NDBC public; NASA ICESat-2 requires Earthdata login). No licence text captured as a source document.

## 2. Inventory by location (classification and proposed action)
| Location | Size | Class | In git / remote? | Backup | Proposed action |
|---|---:|---|---|---|---|
| `jobs/wind-hourly/**` in this repo (85 files) | 0.55 MB | CANONICAL (product code) | yes (repo lineage) | origin | KEEP |
| Engine branches `feat/wind-brain-adoption`, `deploy/wind-internal-validation` (≈ adoption + deploy package), `brain/wind` (⊂ adoption code; core already in repo), `intelligence/wind` (⊂ `brain/wind`), `docs/wind-brain-research` | 0.43-1.6 MB each | CANONICAL candidate code, RESEARCH reports, HISTORY (rollback package = `deploy/…`) | yes, pushed, 0/0 vs origin | origin | REFERENCE_IN_PLACE; **no merge, no deletion**; RECLASSIFY `brain/wind` and `intelligence/wind` as HISTORY |
| Private iOS repo `docs/intelligence/wind/**` (145 files) | 2.2 MB | RESEARCH, OBSERVATION_VALIDATION (freeze files, ledgers, evidence, score change log), DERIVED | yes (private repo) | origin | ADOPT_INTO_WORKSPACE (copies of prereg/freeze/evidence/ledgers into `validation/`, reports into `research/`); keep originals; repoint hard-coded script paths first |
| iOS `scripts/wind`, `tools/wind-candidate-tests`, `FishIntel/Wind/*` (incl. `WindSurfacePhysics.swift`), frozen 4-lake snapshot assets | ~0.2 MB | CANONICAL (shipped candidate code, build tooling, test oracle) | yes | origin | REFERENCE_IN_PLACE |
| `sector-wind-prodfix` (iOS) | — | not research (production defect fixes) | yes | origin | KEEP |
| `Sector_Research_Data/wind-brain/live-meta/{executions,brainlogs}.json` | ~0.8 MB | **HISTORY, not rebuildable** (cloud execution/log history ages out after ~30 days) | **no** | **none** | ADOPT + private backup: **highest priority** of this directory |
| same dir: `live-meta/ledger`, `live-meta/runs` | 0.76 MB | OBSERVATION_VALIDATION (reliability-gate input) | bucket is the origin | bucket (unversioned) | ADOPT into `validation/` + private backup |
| same dir: `cycles/` (4), `out/score_refresh_*`, `canonical_rescore_*`, `live_reliability_*` | ~0.2 MB | HISTORY (score/reliability refresh trail) | partly | none | ADOPT into `validation/` |
| same dir: `out/*` analysis results (15 byte-identical copies exist in git) | 2.2 MB | DERIVED | duplicates in git; local-only variants of `fleet_fetch`, `field_pairs`, `readiness/`, `live_reliability_latest` | none | ADOPT local-only variants; reference the rest by sha256 |
| same dir: `live-meta-mirror/` | 0.29 MB | DERIVED (rebuild from live-meta) | n/a | n/a | RECLASSIFY DERIVED; no backup |
| same dir: `registry/` (592 lake polygons) | 21.7 MB | DERIVED copy of the public Lake Registry (Lake Brain owns) | public bucket | public | consume the published registry; at most one immutable reference copy in `shared/` (owner Lake Brain) |
| same dir: `rows_v50.pkl` (12 MB), `rows_tonight_p10p50.pkl` (0.7 MB) | 12.7 MB | DERIVED, **provenance undocumented** (no committed generator) | no | none | RECLASSIFY; adopt into `datasets/` with a provenance note; never trust-load pickles |
| same dir: `atl13_raw_manifest.txt` | 2.7 KB | RESEARCH (source record; raw granules deleted 2026-10-14, public, re-derivable) | no | none | ADOPT into `sources/` |
| cache dir: `wind-validation/provider-bakeoff/` | 937 MB (growing) | RESEARCH + OBSERVATION_VALIDATION | no | **none** | **ADOPT + private backup; top priority**; stop or repoint the loop first |
| cache dir: `historical/` (NBM v5.0 corpora) | 365 MB | RESEARCH (raw, public NOAA, re-downloadable) | no | none | KEEP in place; manifest by sha256 |
| cache dir: `wind-validation/derived/` (`rows.pkl` is a hard dependency of ~8 scripts and the canonical rescore) | 166 MB | DERIVED (hours to rebuild) | no | none | ADOPT into `datasets/` or keep with manifest |
| cache dir: `live-mirror/`, `archive/` (copies of the bucket archive, includes sealed-H2 values) | 54 MB | HISTORY / sealed OBSERVATION_VALIDATION | bucket | bucket | KEEP; verify bucket completeness before treating as redundant. H2 stays sealed |
| cache dir: `windninja/`, `swan/` (negative results) | 55 MB | RESEARCH | no | none | ADOPT or KEEP (low priority) |
| cache dir: `venv/` | ~535 MB | RUNTIME, `OBSOLETE_CANDIDATE` | n/a | n/a | never delete without approval |
| Handoffs (`Sector Handoffs/Sector Engine/Wind Brain/`, 3 files + 1 orchestrator durability handoff) | 24 KB | HISTORY | local only | none | KEEP, never delete |
| Ops `windBrain.tsx` (consumer, 2 identical copies) | 15 KB | RUNTIME consumer | yes | origin | not research |
| ~35 sibling worktrees carrying `jobs/wind-hourly` | — | duplicates | yes | — | no action |

Worktrees `Sector_Engine-wind`, `-wind-adoption`, `-wind-research`, `-wind-deploy` are clean (only `.DS_Store`/pytest caches ignored); nothing unique is untracked.

## 3. What belongs in `shared/`
Nothing yet. Candidates, each with owner / acquisition owner / consumers recorded **before** any move:
- Lake Registry geometry reference: owner = Lake Brain; Wind only consumes the published registry.
- NOAA NBM/RTMA/IEM/NDBC history: owner and acquirer = Wind; move only if another Brain (Depth waves, Water Temp, Fish) actually needs it.
- Provider licence captures (Open-Meteo, NOAA, NASA, IEM): acquisition owner = Wind.
Shared does not mean ownerless.

## 4. Remote storage (step 3) — `gs://sector-wind-candidate/wind/v1`
4,409 objects, 50,755,133 bytes. Single-region, uniform access, public access prevention enforced. **Versioning off; soft delete 7 days; no lifecycle rules; no retention policy.**

| Prefix | Objects | Bytes | Class | Notes |
|---|---:|---:|---|---|
| `nbm/{lake}` | 772 | 28.4 MB | OBSERVATION_VALIDATION (forecast archive; H2 sealed) / HISTORY | public source, but time-bounded retention at NOAA |
| `rtma/{lake}` | 3,076 | 10.4 MB | same | |
| `fetch/national`, `fetch/dev` | 75 | 10.1 MB | CANONICAL candidate (frozen fetch tables) / DERIVED from iOS generator | one `MANIFEST.json` (the only manifest in the bucket) |
| `ledger/runs`, `runs` | 390 | 0.86 MB | OBSERVATION_VALIDATION (reliability-gate evidence) | origin of local `live-meta` copies |
| `grids/*`, `metar`, `latest` | 21 | 0.9 MB | DERIVED / RUNTIME-ish | `latest/{lake}.json.gz` is overwritten each run |
| `brain/wind/` (`last_publish.json`, `latest/`, `profile_cache/`) | 75 | 0.12 MB | RUNTIME (Wind's private publish memory) | `last_publish.json` is a **second source of truth** to be replaced by the Publisher's publication record |

**Findings:** (1) the bucket holds irreplaceable-class evidence with **no versioning and no backup** (exit B/C risk); (2) no release manifest or hashes except the fetch-table manifest (hashes not verified here beyond existence); (3) Artifact Registry image retention for the rollback package was not verified (no read access exercised); (4) other buckets in the project belong to other Brains and were not inspected.

## 5. Gaps against exit evidence B / C
- B (local research backup): **FAIL** today. No private versioned research backup exists; the research bucket from CERT-4 does not exist yet and creating it needs approval.
- C (remote inventory): inventory done; manifest/hash verification and image-retention check **open**.
