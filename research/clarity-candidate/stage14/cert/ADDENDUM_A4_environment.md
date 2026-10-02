# Certification addendum A4: an environment incident, and the re-run (no method change)

Recorded 2026-10-01, before any certification Secchi, chlorophyll or turbidity value was read.

**What happened.**
- **The deletion.** At 00:00 local time, the operating system's temporary-file cleanup deleted files under
  `/private/tmp` that had not been accessed for three days. The scratchpad lives there.
- **What it took.** Package files in the `geo` Python environment (numpy, scipy, rasterio, pyproj, shapely and others)
  and its `pyvenv.cfg`. Those files are imported through cached bytecode, so their access times were stale.
- **What it did not take.** The data files, ACOLITE's source tree (`git status` clean) and ACOLITE's own environment all
  survived.
- **The effect.** Every ACOLITE run after 00:00 failed explicitly (`numpy has no attribute ndarray`) and wrote no
  samples. Nothing produced before midnight was affected:
  - the WQP extraction (finished 23:29), finalize and A3;
  - NLA (finished 22:57);
  - about half of SYKE.

**Repair.**
- `pyvenv.cfg` was recreated.
- The 20 packages were reinstalled at their recorded versions (`stage14/geo_requirements.txt`); `pip check` is clean.
- Every scratchpad file's access time was refreshed.

**Verification.**
- **The engine.** A C-gbm refit on the repaired environment reproduces `frozen_gbm.pkl` exactly (max difference 0 over
  1,397 development rows).
- **ACOLITE.** The six development validation scenes reproduce the original validation exactly (264 values, max
  difference 0).

**Re-run.** Every certification item with a failed station is re-run unchanged with `run_cert_aco_a1.py`: WQP 537, SYKE
426, NLA 12. Items that failed on "no L1C" (a catalogue lookup) are not re-run. Results already written are not re-run.
