Standards: Rehtac Cortex 3.1.6 @ a785035, pack sector/engine

# Watchdog: a timed-out grants listing no longer trips the artifact comparison (2026-11-25)

Michael approved this in the 2026-11-25 Morning summary (item 2, "yes, as its own Engine PR", approved in chat 23:22 CT).

## What happened
At 2026-11-25 00:51:42Z the grants listing timed out part-way. `artifacts_check` then compared the full artifact counts with the partial grant counts and latched three MORE_ARTIFACTS_THAN_GRANTS trips (sector-intelligence 17 vs 12, water-clarity 17 vs 0, water-temp 28 vs 0). Real counts were within grants. The latch held every Brain cycle for about 22 hours.

## Change
`cycle_watchdog.py`: the artifact-versus-grant comparison runs only when the grants check read the whole listing. A failed grants check still reports CHECK_FAILED (the cycle holds, no latch), so it stays fail-closed. Regression test added; it fails without the fix.

## Not done
Takes effect only after the Orchestrator image is rebuilt and deployed (a separate, gated step).
