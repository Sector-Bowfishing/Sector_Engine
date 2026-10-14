# Wind H2 holdout — result status (2026-10-13)

**Status: NOT RUN. No H2 row was read.**

- Criteria were committed and hash-frozen first (`WIND_H2_PREREG.md`, `WIND_H2_PREREG.freeze.json`, commit `3687f2be`).
- The runner `python -m sector_wind.h2` was executed once on 2026-10-13 and refused: `H2 is sealed until 2027-01-01T00:00:00Z; no H2 row was read` (exit 2). It wrote no ledger and no result, so the one shot is intact.
- **Why not run it anyway:** the holdout was sealed until 2027-01-01 by the earlier campaigns and by code (`H2_SEALED_UNTIL`), and on 2026-10-13 only six of its ~86 days exist (mostly calm weather; every test would be INSUFFICIENT). Spending the one-shot now would burn the holdout for no information. This is a deviation from the instruction to run H2 in this session; the alternative needs Michael's explicit decision (see `WIND_MICHAEL_DECISIONS.md`, item 6).
- **What was run instead:** the product and the test share one code path (`tonight.py` ↔ `h2.py`), and `tests/test_adoption.py` verifies the runner's gate, the one-shot ledger, tamper detection of the pre-registration, INSUFFICIENT-not-PASS behaviour, and the frozen thresholds on synthetic rows.
- **Expected outcome (not a result):** the research on CAL+H1 gives D1 0.81, D2 0.97, S1 exact 0.79 vs 0.77 baseline, T1 accuracy 0.55 vs 0.42, B1 19× lift / POD 0.49. H2-T2 (lay-down) and H2-T3 (rising) are expected to fail and the product makes neither claim.

When the window opens: `python -m sector_wind.h2 --store local:<mirror> --ledger <path> --out <path>`; record the output here without editing the criteria.
