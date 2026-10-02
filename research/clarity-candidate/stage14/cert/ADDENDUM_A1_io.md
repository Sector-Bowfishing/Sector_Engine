# Certification addendum A1: L1C fetch without the TCI preview (I/O only)

Recorded 2026-10-01, before any certification Secchi, chlorophyll or turbidity value was read.

**Why.** The ACOLITE run downloads every L1C SAFE in full, and the link is saturated at about 80 MB/s. The TCI true-colour
preview is about 19% of each product, and ACOLITE never reads it:
- `sentinel2/safe_test` only indexes it;
- `l1_convert` uses the sensor bands and the `MSK_DETFOO` masks.

**Change.** `run_cert_aco_a1.py` runs `run_cert_aco.py` unchanged, except that the fetch skips `*_TCI.jp2`.

**Check.** The six development validation scenes were re-run through it. All 264 sampled values (M0–M3, every band, 7
stations) are identical to the first validation run (maximum difference 0).

**Scope.** Items already processed are not re-run. Results are unaffected.
