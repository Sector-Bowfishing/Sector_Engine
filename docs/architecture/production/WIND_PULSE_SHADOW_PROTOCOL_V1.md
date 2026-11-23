# Wind 7-day shadow on Pulse: pre-registered protocol (`wind-pulse-shadow-v1`)

**Status: pre-registered 2026-11-23, before any shadow run.** Nothing in this document has run. It implements decision **D4** (Sector_Ops #51 comment 6889677881: "Wind's 7-day comparison runs on Pulse, in shadow, with the pre-registered criteria in #176") and replaces the cloud design of Sector_Ops #49 for Wind. The runner is `tools/ops/wind_pulse_shadow.py`; its thresholds are pinned to this text by `brains/wind/tests/test_pulse_shadow.py`. The runner prints this file's SHA-256 in every report, so a result is tied to the exact protocol it was scored under. Changing a threshold after a window starts makes that window void: write `wind-pulse-shadow-v2` and start again.

## Why a redesign

The cloud plan compared what the Publisher *would* write against what the legacy `wind-hourly` writer *did* write, read back from the database. On Pulse that comparison is impossible: there is no legacy write (and restarting the cloud writer contradicts "no cloud runs until Pulse works"). So the shadow checks what can be checked without a second writer: that Pulse seals on time, that a seal is reproducible from its own archive, that the sealed wind is as good as Wind's recorded validation, that every write stays inside Wind's bounds, and that the Mac mini stays awake and inside the retention rule.

## Setup

- **Shadow run (hourly, Pulse):** `brains/wind/runtime/artifact_entry.py --store local:<the wind-central archive> --artifact-dir <shadow folder> --read-rtdb`, **without `--emit`**. No lease, no hand-off, no upload, no Publisher: nothing reaches a database or bucket. `--read-rtdb` reads the previous state GET-only with the existing read token, exactly as `wind-central` will. It is **required**: a seal that takes its previous state from the local bookkeeping advances that file, so it can never be re-sealed reproducibly (C2); the runner's re-seal refuses that mode. It needs a Pulse catalog entry (off by default) and the owner's OK to schedule it.
- **Archive:** the same local archive `wind-central` will use, seeded once from the Wind candidate archive (D5) and checked by `tools/ops/wind_archive_continuity.py` (result `CONTINUOUS`) **before** the window starts.
- **No other live Wind writer during the window:** the cloud `wind-hourly` job (and its scheduler) stays paused, Wind stays disabled in the execution control, and nothing hands a Wind artifact to the Publisher. A live Wind write during the window changes the previous state the shadow reads and voids the window (restart it).
- **Window:** **7 consecutive days** (168 hours), starting at the top of a UTC hour named in advance on Sector_Ops #51 (`--start`).
- **Re-seal (C2), once per UTC day:** right after an hourly seal and **before the next run**, `wind_pulse_shadow.py reseal --store … --artifact <that seal> --out <new record> --read-rtdb`. The runner refuses if a later run is already in the archive. The re-seal runs Wind's unchanged build over a copy-on-write view of the archive (every write stays in memory), with the run's own stored ingest summary.
- **At the end:** save `pmset -g log` to a file and run `wind_pulse_shadow.py report --artifacts <shadow folder> --store … --start … --reseals <records> --pmset-log <file> [--explanations <file>]`.

## Pass criteria (all must PASS)

| # | Criterion | Rule |
|---|---|---|
| C1 | Completeness | At least **95%** of the 168 hours have a Wind artifact sealed within **20 min** of the top of the hour (`lineage.generatedAt`). Every missed hour has a written explanation in the explanations file. A source outage is an acceptable explanation only if the sealed artifacts around it report it honestly (stale or degraded lakes, ingest errors). |
| C2 | Determinism | At least one re-seal record for every UTC day the window touches, each naming the `artifactId` of a shadow artifact found in the window, and every record `equal`; the report recomputes the original write-set hash from that stored artifact and fails a record whose `originalWritesetSha256` differs: the write-set hash (sorted `op`, `path`, `value`, with only the wall-clock `durationMs` removed; lineage is not part of it) of the re-seal equals the original's. A missing day is a failure, not a gap. |
| C3 | Skill | At the 4 live lakes, sealed `analysis` states at the top of the hour vs METAR at that lake's frozen stations (the report nearest the hour, within 10 min, from the archive): pooled speed MAE no more than **1.10** × the recorded validation MAE (`validation_evidence.json` `metrics.speedMaeMph` = 2.189 mph, so the bar is 2.408 mph), on at least **200 pairs**. Fewer pairs is NOT_EVALUATED (the window is INCOMPLETE). Per-lake MAE is reported, not gated. |
| C4 | Bounds | Every mutation path is one Wind may write (`ownership.path_allowed("wind", …)`, the Publisher's table) and every lake key under `lakes|lakeFleet|snapshots/<k>/` is on the staged W-H3 list (`tools/ops/hybrid-stage/wind.json`, the whole directory). Note: with the whole-directory list, C4 does **not** check that `lakes/{k}/states/wind` is written only for the 4 live lakes; the report lists every lake that received a Wind state (`stateLakes`) for review. |
| C5 | Mac mini | No `Sleep` entry in `pmset -g log` inside the window, and at the window's end the archive holds no raw cutout older than **30 days** that the retention rule (`sector_wind/retention.py`, newest of each series kept) would prune. |

**Verdict:** PASS only if all five PASS. Any FAIL is FAIL. Otherwise (a criterion NOT_EVALUATED) INCOMPLETE. Exit codes 0 / 1 / 3.

**If any criterion fails:** stop, explain it on Sector_Ops #51, fix it, and restart the 7 days. No criterion is re-scored with a different rule.

## Known limits (stated before any data)

- **C2 is reproducibility, not equivalence to a legacy writer.** It proves a seal depends only on the archive, the live previous state and the code. During the window Wind is not publishing, so the live previous state does not change; C2 does not exercise a changing previous state (the W-H2 tests do).
- **C3 compares a lake-point value with airport METARs.** The sealed analysis is RTMA-RU at the lake's directory coordinate; the stations are up to tens of km away. That representativeness gap can only raise the MAE, so a PASS is conservative; a FAIL may be representativeness rather than regression, and is still a FAIL under this protocol. RTMA-RU assimilates these METARs, so C3 is consistency, not independent skill (as the evidence file already says).
- **C5 needs the retention job to have run.** Without it, an archive seeded from October holds raw cutouts older than 30 days and C5 fails.

## What remains Michael's call

1. Scheduling the shadow job on Pulse (a new hourly local schedule) and naming the window start.
2. Scheduling the retention job (or a one-off `main.py retention --apply` on the Mac mini) before the window ends (C5).
3. Whether the flip (Engine #177) waits for a PASS, or merges once the code blockers are cleared with the 7-day shadow running in parallel and the first publish (M6/M8) held until PASS. The cutover plan's order puts the shadow before the flip.
4. Any change to this protocol, which must happen before a window starts and gets a new protocol id.
