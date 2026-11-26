Standards: Rehtac Cortex 3.1.6 @ a785035, pack sector/engine

# Water Temp v6 runner: WQP rate-limit retry and resume (2026-11-25)

Michael approved in chat on 2026-11-25 ("I approve all your recommendations"; Morning summary item 4).

## Why
Step 6 (`fetch-wqp`) stopped four times on HTTP 429 (Sector_Ops #51 Batch 2): about 150 requests per run, and each retry restarted at the first lake, so spacing alone could not finish 180 files.

## Change (`tools/research/water_temp_protected_truth_v6.py`)
- `_get_bytes` waits and retries the SAME request on 429/502/503/504 (Retry-After, else 30 s doubling to 5 min, 6 tries). Other errors raise as before.
- `fetch-wqp` records each file in `wqp.provenance.partial.json` as it lands and, on a restart, reuses a file only if it is on disk with the recorded sha256, url and parameters. The final provenance is the same as an uninterrupted run's; the partial file is removed on completion.
- No request, parameter, whitelist, window or analysis changed; the protocol file and its sha256 are untouched.
- Tests: retry waits, last attempt raises, resumed run equals an uninterrupted run (42 pass).

## For the ledger
Step 6 resumes under the same anchor (7152902646). The Mac mini notes this change and its reason in its Run start comment.
