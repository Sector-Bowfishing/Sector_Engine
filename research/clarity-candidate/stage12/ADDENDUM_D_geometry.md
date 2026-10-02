# Addendum D to PREREGISTRATION_STAGE12.md: viewing geometry on older L1C baselines

Recorded during the corpus run, before any corpus reflectance or visibility metric was computed. The only thing seen
was the count and text of processing errors.

**Found.** ACOLITE's default `geometry_type=grids_footprint` reads the per-detector footprints. Older L1C baselines on
the Google bucket store those as GML, which needs GDAL's `ogr`. The GDAL stand-in used here (Stage 11 caveat) does not
implement it. Those crops failed with `NotImplementedError: osgeo shim: ogr.Open not implemented`: 38 of the first
roughly 540 crops.

**Change.** When, and only when, that error occurs, the crop is rerun with `geometry_type=grids`. That is ACOLITE's
angle-grid geometry without per-detector footprints; the view angles differ by about a degree at most. It sits beside the
existing `tiled` → `fixed` aerosol fallback, and each affected row records it. Crops that already failed are rerun
after the main pass. Nothing else changes.
