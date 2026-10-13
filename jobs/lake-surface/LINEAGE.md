# jobs/lake-surface — lineage warning

**The code in this directory on `main` is NOT what the live `lake-surface-daily` job runs.**

The live job (image of 2026-09-29) was built from `feat/clarity-algal-warning` @ `03937913`,
whose `daily.py` and `derive_water_surface.py` carry Clarity Fusion Stage 4 additions
(per-scene `.cells.bin`, per-arm anchors under `clarity/arms/`, the NDCI algal product,
`--pass-dates` history backfill, a publish lock and a safer history read). Its
`deploy-job.sh` also copies in `scripts/hydrology/{current_cells,arm_anchor}.py` and
`docs/data/hydrology/guntersville/guntersville.{current_regions.bin,current_regions.json,arm_cells.json}`;
`current_cells.py` and `current_regions.bin` are not on `main`.

Do not redeploy this job from `main` until decision D4 (Clarity Stage 3–5) lands that code
here or retires the Stage 4 outputs. Redeploy, if needed, from the pushed branch
`feat/clarity-algal-warning`. See `jobs/README.md` and `docs/consolidation/STABILIZATION_LOG.md`.
