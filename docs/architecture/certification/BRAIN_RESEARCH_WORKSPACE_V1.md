# Brain Research Workspace V1

## 1. Locked paths
| Purpose | Path |
|---|---|
| Development root | `<development root>` (the research operator's local development directory; resolved locally, never recorded in this public repo) |
| **Standard Brain research root** | `<development root>/Sector Research` (resolved via `SECTOR_RESEARCH_ROOT`/local config) |
| Shared research/reference (exists; keep the name `shared`, not `_shared`) | `Sector Research/shared` |
| **Wind canonical LOCAL research workspace, going forward** | `Sector Research/wind-brain` (logical workspace id `wind-brain`) |

Brain folders under the root (all exist and were **empty** as of 2026-10-14):

| Folder | Brain (brainId) |
|---|---|
| `shared/` | cross-domain reference (owned per dataset) |
| `wind-brain/` | `wind` |
| `fish-brain/` | `biological-state` (Fish Brain) |
| `water-clarity/` | `water-clarity` |
| `lake-brain/` | `lake-brain` |
| `water-temperature/` | `water-temp` |
| `depth/` | `depth` |
| `vegetation/` | `vegetation` |
| `sector-intelligence/` | `sector-intelligence` |

Folder names are human-facing and need not equal brainIds. The mapping above is fixed and is recorded in each workspace's `manifest.json`.

**Existing research is NOT yet under this root.** As of 2026-10-14 it is spread across, at least:
- `Development/Sector_Research_Data/{wind-brain,biological-brain,lake-brain,water-temp-brain,depth-brain,vegetation-brain}` (≈3.6 GB);
- research directories and branches inside the Engine repo and its worktrees (`research/`, `docs/research/`, `jobs/*/research`);
- private and candidate buckets;
- the handoffs folder.

Nothing has been moved. Each Brain's certification inventories and adopts its own.

## 2. Standard internal layout (target; work toward it during certification)
```
Sector Research/<brain>/
  manifest.json      # brainId, owner, classification index, backup locations, sources of adopted material, last inventory
  sources/           # captured raw sources (RESEARCH, immutable once captured; licence noted)
  datasets/          # raw or prepared datasets (RESEARCH or DERIVED; large ones referenced by manifest, stored in private backup)
  research/          # notes, packets, cards, candidate findings, rejected hypotheses (RESEARCH)
  analysis/          # analysis code outputs, experiments (RESEARCH / DERIVED)
  candidates/        # candidate rules/models/bundles not yet released (RESEARCH)
  validation/        # observations, ledgers, preregistrations, holdouts (OBSERVATION_VALIDATION; append-only)
  releases/          # local copies of CANONICAL releases (immutable; the private versioned copy is authoritative for durability)
```
`manifest.json` minimum: `{brainId, folder, owner, updatedAt, entries: [{path, class, bytes, sha256?, licence, adoptedFrom, backup}], backups: [{location, kind, verifiedAt}]}`.

## 3. Rules
1. Brain-specific research belongs in that Brain's folder.
2. A Brain does not rummage through another Brain's research folder.
3. If one Brain needs another Brain's truth, it consumes that Brain's **published contract** (e.g. Fish Brain reads published Water Temperature state, never the Water Temperature workspace).
4. Shared immutable/reference/provider data may live in `shared/`, used deliberately (§4).
5. No duplicate copies of a large common dataset in multiple Brain folders when one shared immutable copy is appropriate.
6. Shared data still has explicit ownership and provenance.
7. **The local Mac is never the only durable copy** of anything classified RESEARCH, CANONICAL, OBSERVATION_VALIDATION or HISTORY.
8. Important research gets a private, versioned backup (location chosen and approved during certification; candidates include a private versioned research bucket).
9. Raw research never goes into production `sector-brain`.
10. Workspaces are local/private; they are never committed to the public Engine repo. Research code that belongs to the product stays in the repo; research **data** does not.

## 4. `shared/` rules
Before anything goes into `shared/`, record: authoritative owner, acquisition owner, consumers, mutability, versioning, licence/use restrictions. Candidates: common geographic reference data, provider documentation, immutable reference datasets, shared schemas/reference definitions, and common lake geometry if the architecture assigns it there (lake geometry is Lake Brain truth; a shared copy would be a published reference export, not a second authority).
**Shared does not mean ownerless.** Two Brains happening to hold copies of the same file is not by itself a reason to move it to `shared/`.

## 5. Existing research migration policy (per Brain, during its certification)
1. Search all of `Development/` for that Brain's research (names, aliases, old folder names, worktrees, branches, `Sector_Research_Data`).
2. Inventory every relevant artifact (`BRAIN_DATA_CLASSIFICATION_V1.md` inventory record).
3. Determine what it is, who owns it, whether it is still used, canonical, duplicated, rebuildable or historical evidence, and whether it should be adopted.
4. Preserve provenance (record `adoptedFrom`).
5. Preserve source history.
6. Preserve validation truth.
7. Preserve accepted review decisions.
8. Never delete merely because something appears old.
9. Avoid duplicate copies when adopting (move-and-reference or reference-in-place; never copy-and-forget).
10. Move content into the new workspace only after classification, and only with the session's explicit approval for moves.
