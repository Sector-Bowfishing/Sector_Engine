# Vegetation Brain — Small shadow pilot (2026-10-14)

**SHADOW / internal. Dry-run store only; no live write, no customer layer, no new schedule, no Sentinel read.** Data: `vegetation_shadow_pilot_2026-10-14.json` (compact per-lake results). Runner: `jobs/vegetation-brain/tools/shared_pilot.py` (read-only `gcloud storage` GETs of Clarity's existing per-pass files; temp files deleted on exit).

## Design: one ingestion path, many consumers
Vegetation consumes the **shared Clarity lake-surface pass evidence** (`gs://sector-lake-surface/lakes/<lake>/clarity/<date>.json` ≈ 4 KB and `<date>.measured.png` ≈ 75 KB: grass class share, measured share, scene ids, bed-to-bank strip, PNG class codes 255/3/2/1). It reads no Sentinel-2 scene, runs no poller, and adds no schedule. The module is `vegetation_brain/shared.py`; rules mirror the pixel observer (window ±21 d, acceptance = known share ≥ 50 % with a ≥ 25 % flagged fallback, burst check, median persistence over ≥ 3 accepted passes, no max composite, single un-accepted pass never published). The painted **bed-to-bank strip is removed** from the observed share.
*Limit:* Clarity stores results, not raw bands, so the pixel observer v0.3 (NIR floor, cell guards) cannot run on shared data. The shared grass class is Clarity's **production rule (unvalidated)**; this pilot therefore tests plumbing, cost and honesty, not accuracy.

## Pilot lakes and results (37 passes from 8 lakes, last 60 days)
| Lake | Area km² | Passes (accepted) | Evidence | Accepted scenes | Observed grass km² (share) | Status | Confidence | Dominant refusals (mean share of lake cells) |
|---|---:|---|---|---:|---|---|---|---|
| Guntersville AL | 267 | 16 (16) | persistence | 8 | 40.8 (15.3 %) | PRESENT, "Likely surface vegetation" | LOW 0.45 | unreadable 28 %, cloud/haze 10 % |
| Sam Rayburn TX | 454 | 3 (3) | persistence | 3 | 55.8 (12.3 %) | PRESENT | LOW 0.45 | unreadable 18 %, cloud/haze 15 % |
| Istokpoga FL | 97 | 1 (1) | accepted pass | 1 | 5.9 (6.1 %) | PRESENT | LOW 0.42 | cloud/haze 26 % |
| Toledo Bend TX | 672 | 3 (2) | accepted pass | 2 | 27.5 (4.1 %) | PRESENT | LOW 0.41 | unreadable 21 %, cloud/haze 15 % |
| Hartwell SC | 219 | 4 (0) | fallback pass | 1 | 7.0 (3.2 %) | PRESENT (fallback) | LOW 0.27 | **unreadable 66 %** |
| Lake Pepin MN | 103 | 4 (3) | accepted pass | 2 | 2.9 (2.8 %) | PRESENT | LOW 0.45 | unreadable 17 % |
| Leech Lake MN | 418 | 4 (4) | persistence | 4 | 8.8 (2.1 %) | PRESENT | LOW 0.45 | unreadable 11 %, cloud/haze 9 % |
| Okeechobee FL | 1,376 | 2 (2) | accepted pass | 2 | 23.4 (1.7 %) | PRESENT | LOW 0.37 | **cloud/haze 34 %** |

## The seven pilot questions
1. **Can the observer run cheaply from shared scenes?** Yes. 8 lakes: **2.24 MB** read (37 small JSON + PNG files), **1.85 s CPU** (observe + build 8 states + two publishes), wall time 194 s was almost entirely `gcloud` process start-up for ≈ 76 CLI calls, not compute. No scene was downloaded.
2. **Does fingerprinting SKIP unchanged inputs?** Yes. Second publish: `skippedUnchanged 8/8`, **no lake state rewritten** (only the registry/validation/health nodes, which carry timestamps). A new pass, wind flag, Clarity Secchi or Depth tier changes the fingerprint (unit-tested).
3. **Does the state remain compact?** Yes: **54 KB for 8 states (≈ 6.8 KB each)**; no raster or imagery in state.
4. **Are refusal states honest?** Yes where they exist: Hartwell's only passes are fallback (34 % known, 66 % unreadable) so it is flagged `lowCoverageFallback`, `persistence INSUFFICIENT`, confidence 0.27; lakes with < 3 accepted passes are never labelled persistence; `UNKNOWN` was not needed because no lake lacked a usable pass. Shared PNG codes map to `CLOUD_OR_HAZE` and `UNREADABLE_WATER` (Clarity bundles cloud+haze, so Vegetation cannot separate them).
5. **Does "Likely surface vegetation" look useful?** **Not as a lake-level yes/no — and that is the main finding.** All 8 lakes are PRESENT, including lakes where earlier research expected little surface vegetation (Hartwell, 3.2 % from a fallback pass with 66 % unreadable; Leech 2.1 %). The `>= 1 ha` presence rule is a pre-set placeholder that a large lake clears easily, so the binary carries almost no information. What does look informative is the *ordering of observed share*: Guntersville 15 %, Sam Rayburn 12 %, Istokpoga 6 %, Toledo Bend 4 %, then ≈ 2–3 % for Hartwell/Pepin/Leech/Okeechobee — Guntersville and Sam Rayburn are the lakes known for heavy surface vegetation. Density stays `NOT_CALIBRATED`, so that ordering is **not exposed** as a claim. I did **not** retune the threshold on these lakes.
6. **Share of pilot passes that are usable:** **31 of 37 (84 %)** passes meet the ≥ 50 % known-share acceptance; 3 of 8 lakes reach persistence (≥ 3 accepted); 1 lake (Hartwell) has only fallback passes. *Survivorship caveat:* Clarity only publishes passes it could use for clarity, so this overstates raw scene yield (the research measured 30–52 % of clear-enough scenes passing a stricter pixel-level acceptance).
7. **Dominant refusal reasons:** `UNREADABLE_WATER` (bank band, docks/bridges, narrow creeks; 66 % at Hartwell's dendritic arms) and `CLOUD_OR_HAZE` (34 % at Okeechobee, 26 % at Istokpoga).

## Claim status (unchanged by the pilot)
Level 1 agency observation `NOT_ASSESSED`; Level 2 geometry tier and observation age `VERIFIED`; Level 3 surface presence `NOT_VALIDATED` (shadow), type/density `NOT_ASSESSED`, seasonal `NOT_VALIDATED` (UNKNOWN), potential habitat `NOT_ASSESSED` (`NOT_EVALUATED`), submerged `NOT_OBSERVABLE`.

## What this does and does not show
* It shows the shared-evidence path is cheap, compact, idempotent and honest about coverage.
* It does **not** show accuracy, and its lake-level presence flag is not yet decision-useful.
* The product-relevant output is **where** (zones/cells), not "somewhere on a 400 km² lake". The Clarity PNG already holds per-cell grass classes with a fixed frame (`grid.json`), so a zone summary (persistent grass cells, clusters, centroids) is a small *implementation* step. It is recommended, not built: it needs Michael's go-ahead because it extends Vegetation from a lake-level flag to zone output, and the cell class still includes Clarity's bank painting.
* A cleaner Vegetation signal needs Clarity (the owner of the scene reads) to emit a compact per-cell plant-fraction raster alongside its turbidity outputs — an **UPSTREAM BRAIN** request, so the V0.3 pixel logic can run without a second scene read.
