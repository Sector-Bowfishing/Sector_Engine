# Lake Brain: dry-run gauge check of the accepted batch (2026-11-21)

Source: the Mac mini helper's report on Sector_Ops #51 (2026-11-21 03:11Z). Engine `66957c45`; `LakeBrainJob --dry-run --scope pilots --force`, no `--rtdb`, against a copy of Pulse's Lake archive; then `tools/ops/lake_binding_dryrun_check.py`. 194 lakes ran in 82.5 min, exit 0, health WARNING. Nothing was written to any database, bucket or Pulse config.

Result over the 189 accepted lakes: **133 pass, 53 fail, 3 hand review.**

## Moved from accepted to held (17), `held_lakes.json` → `dryrunCheck`
| Lake | Why |
|---|---|
| Deep Creek Lake\|MD | second source disagrees 1.79 ft |
| Sardis Lake\|MS | second source disagrees 1.19 ft |
| Grenada Lake\|MS | second source disagrees 1.03 ft |
| Jennings Randolph Lake\|MD | second source disagrees 0.94 ft |
| Smith (Lewis Smith)\|AL | second source disagrees 0.84 ft |
| Havasu\|AZ | second source disagrees 0.83 ft |
| Beltzville Lake\|PA | second source disagrees 0.67 ft |
| Badin Lake\|NC | no live reading (UNAVAILABLE) |
| High Rock Lake\|NC | no live reading (UNAVAILABLE) |
| Abiquiu Lake\|NM | seeded history vs live series −23.8 ft |
| Cochiti Lake\|NM | seeded history vs live series −20.2 ft |
| Don Pedro\|CA | seeded history vs live series +19.9 ft; 48.3 ft from full pool |
| Fern Ridge Reservoir\|OR | seeded history vs live series +16.1 ft |
| Summersville Lake\|WV | seeded history vs live series +35.8 ft; 53.9 ft from full pool |
| Sutton Lake\|WV | seeded history vs live series +18.5 ft |
| El Vado Lake\|NM | hand review: 87.0 ft from directory full pool |
| John Martin Reservoir\|CO | hand review: 40.5 ft from directory full pool |

Each needs its binding or history series resolved before it returns to the batch.

## Kept in the batch
- **Coeur d'Alene\|ID and Lake Gaston\|VA:** real gauges that were stale at check time (Coeur d'Alene agrees with its second source to 0.00 ft).
- **38 history-only fails:** today's level is more than 5 ft from the lake's own 365-day median, the normal November winter drawdown at flood-control, TVA and Corps reservoirs. Where a second source exists it agrees with the live value. The check's 5 ft history bar is tighter than Lake's own 15 ft `historyLiveMismatch` rule.
- **Ross Lake\|WA, Lake Cumberland\|KY, Douglas Lake\|TN:** more than 25 ft from directory full pool, but live and second source agree (Douglas 0.00 ft) and the gap is seasonal drawdown.

## Result
- Accepted batch 189 → **172**; Lake's reviewed set (5 pilots + batch) 194 → **177**; the customer Lake-level list follows it (`tools/ops/lake_level_eligible.py`).
- New knowledge release `lake-knowledge-2026-11-21.1`, approval **pending** (`docs/cortex/approvals/lake-knowledge-2026-11-21.1.md`).

## Other findings (not changed here)
- **Presence 403:** the read-only `lake-archive-read-token` gets 403 on `gs://sector-lake-brain/presence/releases/lake-presence-2026-10-12.1/presence.json`. Granting read is an IAM change: Michael's call.
- **History series unavailable (7):** USGS 395540082291600, 12393000 (datum offset note), 07226800 (Ute), 03351700, 02172000, 01314500; RISE 355.
- **Run time:** 82.5 min for 194 lakes on the first (full-pull) run, over the 45–60 min estimate; within the 3600 s limit only because history was pre-warmed. Keep the warmed archive (`~/Sector/lake-rollout-66957c45/warmed-archive` on the Mac mini) for the real first run.
