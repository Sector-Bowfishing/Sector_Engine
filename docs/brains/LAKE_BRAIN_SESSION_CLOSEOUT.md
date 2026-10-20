# Lake Brain — session closeout (2026-10-12)

**What this note is:** a short freeze note for branch `sector/lake-brain`. The full contract is `LAKE_BRAIN_INTEGRATION.md` in this folder.

## Status

**Running for 5 pilot lakes** in the Brain RTDB (`sector-brain`):
- First write 2026-10-12 23:46Z, approved by Michael ("option A").
- Registry `/brains/lake-brain`: status `CALIBRATION`, health `WARNING`. The warning is because Hartwell is on its USGS fallback; the USACE hourly feed has been silent since 2026-10-08.
- Sector Ops shows the brain as connected.

**Not merged or deployed:** no Cloud Run job, no scheduler. Refreshes are manual runs of `LakeBrainJob`.

**No customer behaviour changed:**
- `/conditions`, `/lakes` and `/hydrology` are untouched.
- The apps and the app RTDBs are untouched.

## Branch

**Base:** tag `deployed/sector-engine-00072-way`, the live engine's code lineage. `origin/main` is 12 commits behind that tag; do not rebase onto it.

**Unique commits:**

| Commit | What it is |
|---|---|
| `dea63e39` | `BrainPlatform.swift` and `BrainRTDBStore.swift`, byte-identical to `brain/water-temp` `fb2cfd2b` |
| `bb6759bd` | The runtime: `Sources/SectorEngine/LakeBrain/` (10 files) + `Sources/LakeBrainJob` |
| `b747418a` | 19 synthetic tests + the read-through dry run |
| `9b396372` | The contract doc |
| `a7c5a605` | `activeIssues` aligned to the Ops `Issue` shape |

**Tests:** `swift test`: 173/0, including `LakeBrainTests` (19).

## Dependencies and related branches

| Branch | Relationship | Pushed |
|---|---|---|
| `brain/water-temp` | The two platform files are copied verbatim. Identical content, so they merge cleanly in either order | yes |
| `brain/biological` | Owns species knowledge; the presence record shape comes from its §10 | yes |
| Sector_Ops `sector/lake-brain` | Docs and types only (`LakeState`, `LakeSpeciesPresence`); no UI change | yes (private) |
| iOS_Sector `sector/lake-brain` | Private research: the audit, the presence-bundle builder and release, the phase report | yes (private) |

**Storage:**
- `gs://sector-lake-brain` (private, versioned): history, baselines, presence.
- `gs://sector-water-temp-archive` is read-only for this brain.

## Ownership notes for the Engine Brain Ownership Audit

| Area | Current location | Possible owner | Severity | Production? |
|---|---|---|---|---|
| Brain publisher | Swift `BrainPlatform` (here + water-temp) vs Python `brain_platform.py` (clarity, biological) | one shared platform | medium | no |
| Lake-level judgement | `WaterLevelFactor` (Conditions Score: generic thresholds) vs Lake Brain (operator zone + seasonal bands) | Lake Brain facts → Intelligence interpretation | medium | yes (Factor is live) |
| Water "level" in `/conditions.water` | the nearest USGS gage height, shown as water | Lake Brain `lakeState` | medium | yes |
| TVA polling | per-request Conditions + `water-temp-tva-archive` + `hydrology-hourly` | one shared TVA archive | low | yes |
| Lake → species presence | Lake Brain `speciesPresence` vs iOS `WaterbodySpecies.swift` (DISC-001/002/003) | Lake Brain (lake context) | medium | yes (iOS) |
| Shared fleet fields `stale` / `issueCount` / `hasObservations` | no owner; each brain writes `slots.*` | Brain Platform rule | low | no |

## Open items (each needs Michael's approval)

- Fleet scope (all 621 lakes)
- A scheduled refresh (owned by the future Brain Orchestrator)
- An Ops UI for `lakeState` / `speciesPresence`
- Sector Intelligence wiring to `resolveLakeSpecies`
- Production fix for TVA Midnight rows, which `TVAGenerationService.date` places 24 h early. A separate task is queued
- More reviewed bindings, starting with the 13 other TVA lakes

**Decision still with Michael:** one open presence discrepancy (private register; named there, not in this public file).

**Choice made during the build:** the STABLE threshold, ≤ max(0.10 ft, seasonal median |Δ24h|). It is versioned and easy to change.
