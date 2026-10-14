# Vegetation Brain — Fleet shadow run on shared Clarity evidence (2026-10-14)

**SHADOW, dry-run store only. No live write, no new schedule, no Sentinel read, no customer surface.** Data: `vegetation_fleet_shadow_2026-10-14.json` (compact summary; no per-lake raster). Runner: `jobs/vegetation-brain/tools/shared_fleet.py` (read-only `gcloud storage cat` of the small per-pass JSON of every lake, plus the `measured.png` of the accepted passes of PRESENT lakes only; temp files deleted).

## Cost and shape (621-lake registry)
| | |
|---|---|
| Lakes with a Clarity pass in the last 30 days | **561** (547 observable; 42 BLOCKED by geometry; 1 with no usable pass) |
| Pass documents streamed | 1,795 (**7.2 MB**) |
| Class rasters fetched for zones | 275 PRESENT lakes, **12.5 MB** of PNG, deleted after use |
| CPU | 21.7 s for 589 states + zones + two publishes (wall 1,000 s, dominated by `gcloud` calls) |
| Idempotence | second publish **skipped 589/589**; no lake state rewritten |
| State size | **3.8 MB total, max 8.6 KB, mean ≈ 6.5 KB** |
| Storage added to the research data dir | 0 (temp dirs removed) |

## What the shadow signal says (observer on shared evidence, rule A6)
| Status | Lakes |
|---|---:|
| `PRESENT` (observed grass > 2 % of the lake, ≥ 1 ha, bed-to-bank strip removed) | **275** |
| `NOT_OBSERVED` (real look, ≤ 0.5 %) | **117** |
| `UNKNOWN` (incl. `BELOW_NOISE_TOLERANCE` 0.5–2 %, fallback-only, too little looked at) | **155** |
Before A6 the same data gave 492 / 45 / 10 — the first rule (≥ 1 ha) did not discriminate. Evidence reach: persistence (≥ 3 accepted passes) **212** lakes, accepted single pass 334, fallback-only 81. Newest pass age: median 9 d, p90 17 d. Observed-share quantiles (all observed lakes): p10 0.1 %, median 2.1 %, p90 19.3 %, max 85.8 %.
**Persistent zones** (where): 487 zones reported for 275 lakes (top 5 per lake, ≥ 0.05 km², grass in ≥ 50 % of ≥ 2 looks); 1 lake refused for frame mismatch. Example (8-lake pilot): Guntersville's largest persistent zone ≈ 17 km² (−85.908, 34.750), Sam Rayburn's ≈ 33 km² (−94.554, 31.425).

## Honest limits
* The grass class is Clarity's **production rule — unvalidated**; Hartwell-type dendritic lakes lose up to two-thirds of the surface to `UNREADABLE_WATER`.
* Zones inherit Clarity's painted bed-to-bank margin, so area near shore is an upper bound.
* No truth lake exists for these numbers; nothing here is validation. `UNKNOWN` (155 lakes) is a legitimate output.
* Coverage maturity is credited only for **truth-backed** lakes (9 with a Level-1 FWC record), not for the 392 determinate shadow lakes.

## Zone georeferencing check (Level 2, deterministic)
The pixel → lon/lat conversion was checked against the canonical registry geometry for the 8 pilot lakes (30 reported zones): each zone's **anchor** (the zone block nearest its centroid, always on the zone) lies **inside the registry polygon for 20 of 30 zones and within 100 m (max 97 m) for the other 10**. No georeferencing error exists (an error would be kilometres). The edge misses are what the evidence predicts: persistent grass sits at the shoreline and Clarity paints a bed-to-bank margin, while the NHD polygon carries a 25 m tolerance. Centroids of large concave zones can fall off the vegetation (11 of 30 outside the polygon, up to 402 m), which is why the state also carries `anchor`.
