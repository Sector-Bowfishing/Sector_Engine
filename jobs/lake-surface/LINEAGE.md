# jobs/lake-surface — lineage

**Status after the D4 runtime-source reconciliation:** the code in this directory is the
`feat/clarity-algal-warning` @ `03937913` lineage, merged into `main` with history. It is the source the
live `lake-surface-daily` job (image of 2026-09-29) was built from. That image was built by
`gcloud --source` from an uploaded working tree, so no build records a commit; the provenance and its
confidence are in `docs/architecture/certification/water-clarity/D4_RUNTIME_SOURCE_RECONCILIATION.md`.

It carries the Clarity Fusion Stage 4 additions (per-scene `.cells.bin`, per-arm anchors under
`clarity/arms/`, the NDCI algal product, `--pass-dates` history backfill, a publish lock and a safer
history read). `deploy-job.sh` also copies in `scripts/hydrology/{current_cells,arm_anchor}.py` and
`docs/data/hydrology/guntersville/guntersville.{current_regions.bin,current_regions.json,arm_cells.json}`.

**Not changed by the reconciliation:** the deployed job. Nothing was redeployed and the schedulers stay
paused (cost freeze). Rebuilding from `main` is a separate, approved task; byte-equivalence of the
deployed image with this tree has not been verified.

See `jobs/README.md` and `docs/consolidation/STABILIZATION_LOG.md`.
