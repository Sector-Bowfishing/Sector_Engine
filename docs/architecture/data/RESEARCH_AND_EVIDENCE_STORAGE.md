# Research and Evidence Storage (D2, D3, D8)

## 1. Finding
Every Brain's raw research lives in `~/Desktop/Development/Sector_Research_Data` (3.6 GB: depth 1.4 GB, lake 1.0 GB, water-temp 578 MB, vegetation 522 MB, wind 52 MB, biological 13 MB). **It is not a git repository, has no remote and no backup was found.** `BIOLOGICAL_BRAIN_INTEGRATION.md` §2 refers to "Sector's private research repository" — it does not exist. Elsewhere research is scattered: public research branches (Lake ledgers, Water Temp data, Depth canonical data), a local-only unpushed Clarity branch with ~200 MB of committed artifacts, a 29 GB Clarity bucket, and a third copy of Biological profiles in the handoffs folder. The Engine repo is **public**.

## 2. Recommendation (smallest durable architecture)

| Store | Holds | Why this store |
|---|---|---|
| **Private git repo `Sector-Bowfishing/Sector_Research`** | per-Brain dirs of authored text/JSON/JSONL/scripts: packets, cards, verification records, dispositions (incl. rejected claims), contradiction reviews, candidate rule sets, review packets, research ledgers, manifests pointing at bulk objects | diffable, reviewable, history for free, works with the existing Claude/agent workflow; small (Biological 13 MB total; text parts of others are small) |
| **Versioned private bucket `gs://sector-research-private/{brain}/…`** | bulk/binary/raw: PDFs, agency downloads, rasters, extracts, rebuildable datasets, licensed material | git is wrong for multi-GB binaries; object versioning + no public access + soft delete gives durability; cheap (≈ 4 GB ≈ $0.10/month Standard) |
| Each Brain's **release bucket** (existing for Biological/Lake; to create for Depth/Vegetation) | canonical knowledge releases (immutable, hash-pinned) | already proven by Biological; manifests make releases diffable and reproducible |

**ALTERNATIVE:** Git LFS for bulk in the same repo. **WHY NOT:** LFS bandwidth/storage quotas, poor fit for 1.4 GB rasters, and agents handle bucket paths more reliably than LFS pointers.
**ALTERNATIVE:** Firestore for research records. **WHY NOT:** no diff/review history, adds a database, research is file-shaped.
**ALTERNATIVE:** keep research in the public Engine repo on research branches. **WHY NOT:** public; licensed text and per-lake presence cannot go there; it mixes research with production code lineage.

### Immediate step (P0, Michael-approved, campaign C1)
`gsutil -m rsync -r ~/…/Sector_Research_Data gs://sector-research-private/snapshot-2026-10-XX/` into a new private bucket with versioning, uniform access, public-access prevention. Then initialise the private repo with the text portion and a `BULK_MANIFEST.jsonl` (path, sha256, bytes, gs:// location) per Brain (Lake already has `MANIFEST.jsonl` — reuse its format). Nothing is deleted locally.

## 3. Boundary: what may cross into production

| Kind | Research store | Release (canonical) | `sector-brain` (serving) |
|---|---|---|---|
| Raw source text, PDFs, extracts | ✔ | ✘ | ✘ |
| Source identity (id, publisher, title, year, URL/DOI) | ✔ | ✔ `sources.json` | only inside `speciesProfiles/{id}.evidenceSummary` |
| Evidence strength, verification **level** (READ-FULL / READ-ABSTRACT / SNIPPET-ONLY) | ✔ | ✔ | ✔ as a level |
| Verification **workflow** (which agent read it, session notes) | ✔ | ✘ | ✘ |
| Claim ↔ source links | ✔ | ✔ | ✔ as ids (`claimIds` → `evidenceSummary.claims`) |
| Candidate / DRAFT rules | ✔ | ✔ if the release policy uses them (labelled) | only as labelled profile content |
| Rejected claims, dispositions, contradictions prose | ✔ | ✔ (`discrepancies.json` — counts only leave the release) | counts only (`openDiscrepancyCount`) |
| Temporary leads, gaps | ✔ | gap list ✔ | gap *count* + priority in profile |
| Licensed / restricted text | ✔ (bucket, flagged `licensed: true`) | ✘ | ✘ |
| Per-lake species presence | Lake research store | Lake presence bucket | `/lakes/{k}/speciesPresence` only — never `/species`, never public repo |

## 4. `/sources` (D8)
Live `/sources` is a **data-feed registry** (NBM, RTMA, METAR, USGS, CWMS, Sentinel-2, MRMS…) with health — not literature. Keep it exactly that: `{sourceId, publisher, kind, owner (one Brain), status, lastSuccessAt, brains{}}`. Fix: every source id gets one declared owner (three are last-writer-wins today) and non-owners write membership via a merge, not a whole-record write. Literature sources never become `/sources` entries.

## 5. Immutability classes

| Class | Examples | Rule |
|---|---|---|
| **IMMUTABLE** | captured raw sources; releases (`releases/{id}/…`); prediction ledgers & preregistrations; field observations; publish manifests in history | write-once (bucket: `ifGenerationMatch=0` / no-clobber), versioning on, no lifecycle delete |
| **APPEND-ONLY** | review ledger; research ledgers (JSONL); handoffs folder; dispositions; score history; request submissions | new lines/records only; corrections are new records that reference old ones |
| **MUTABLE** | authoring dirs (DRAFT rules, notes) — in git; `latest.json` pointers; RTDB runtime | history provided by git / object versioning / history bucket |
| **DERIVED / REBUILDABLE** | profiles, coverage matrices, RTDB states, scores, `/control/*`, extracts regenerated from raw | may be regenerated; never the only copy of anything above |

**No cleanup policy may target IMMUTABLE or APPEND-ONLY classes.** Cleanup plans (e.g. `CLEANUP_PLAN.md`, `LAKE_BRAIN_ARTIFACT_HYGIENE.md`) must state the class of every artifact they touch.
