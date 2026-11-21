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
- New knowledge release `lake-knowledge-2026-11-21.2`, approval **pending** (`docs/cortex/approvals/lake-knowledge-2026-11-21.2.md`).

## Other findings (not changed here)
- **Presence 403:** the read-only `lake-archive-read-token` gets 403 on `gs://sector-lake-brain/presence/releases/lake-presence-2026-10-12.1/presence.json`. Granting read is an IAM change: Michael's call.
- **History series unavailable (7):** USGS 395540082291600, 12393000 (datum offset note), 07226800 (Ute), 03351700, 02172000, 01314500; RISE 355.
- **Run time:** 82.5 min for 194 lakes on the first (full-pull) run, over the 45–60 min estimate; within the 3600 s limit only because history was pre-warmed. Keep the warmed archive (`~/Sector/lake-rollout-66957c45/warmed-archive` on the Mac mini) for the real first run.

## Research follow-up (2026-11-21): 15 of the 17 return

Read-only research against the operators' own series (CWMS data API, Access2Water, NWPS, USGS waterservices, USBR release 5329). Result: 8 lakes had binding or history errors (fixed here), 7 are real operator drawdown or fill (returned unchanged), 2 have no live source (still held).

**Live series was a rule/guide curve, not the lake** (the cause of the >0.5 ft disagreements):

| Lake | Was | Now |
|---|---|---|
| Sardis MS | `Sardis Lake.Elev.Inst.1Hour.0.Guide Curve` (238.18, future-stamped) | `…1Hour.0.DCP-rev` (239.37; NWPS SRDM6 239.38) |
| Grenada MS | `…Guide Curve` (194.96) | `…DCP-rev` (196.32; matches GRNM6) |
| Arkabutla MS (not held, same bug: published the rule curve ~6 ft off) | `…Guide Curve` (211.55) | `…DCP-rev` (observed ~205.5) |
| Enid MS (not held, same bug) | `…Guide Curve` | `…DCP-rev` |
| Smith (Lewis Smith) AL | `Smith.Elev.Inst.1Hour.0.GC-APCO` (Alabama Power guide curve) | `…Raw-APCO` (497.78; history was already Raw-APCO) |

**Datum alignment:** Jennings Randolph cwms fallback drops `;88` (NAVD88 = project datum − 0.85 ft) to match the primary and plan; Beltzville cwms fallback and history move to NAVD88 `Rev-DCP-88` (NGVD29 = NAVD88 + 0.66), matching the primary and plan; Deep Creek keeps live USGS 00062 (2462 spillway datum, the operator's rule-band datum), history 62615 dv shifted −1.82 ft and NWPS THYM2 fallback −1.82 ft; Havasu NWPS LKHC1 fallback −0.65 ft (inferred from USBR end-of-month vs USGS gage+400; to confirm).

**History was a rule curve (`…1Day.0.RUL`), now the observed series used live (`<Lake>-Lake.Elev.Inst.15Minutes.0.OBS`):** Sutton (verified: RUL held exactly 922.00 then fell exactly 0.55 ft/day), Bluestone, Burnsville, R.D. Bailey, Senecaville, Tappan (same LRH pattern; OBS record depth from ~2021 for Sutton, to confirm for the others). Flannagan's history is also `JWFlannagan-Lake.Elev.Inst.1Day.0.RUL` but it has no CWMS OBS series bound live, so it is a follow-up.

**Real, returned unchanged:** Abiquiu (+24 ft late-October inflow on the operator's own series), Cochiti (temporary flood storage), Don Pedro (normal irrigation and flood-space drawdown; no flood-pool-bottom plan), Fern Ridge (fall drawdown to conservation bottom), Summersville (annual drawdown toward winter pool ~1575), El Vado (Reclamation's interim maximum operating elevation 6,820.5 ft pending Safety of Dams work; recorded in its notes, not bound as a plan, since a plan zone needs both edges), John Martin (low conservation storage all year).

**Still held:** Badin NC and High Rock NC: NWPS BADN7/HGRN7 dead since 2026-10-30 / ~09-30, RAH RVD discontinued 2023, no USGS lake gauge. Next: check the operator (Cube Carolinas) page or feed.

**Check tool changed** (`tools/ops/lake_binding_dryrun_check.py`): (c) now compares with the lake's last 7 daily values, not a 365-day median, and (d) uses the lake's guide curve or operating zone before the directory full pool, so normal seasonal drawdown no longer fails.

Counts: accepted batch 187 (189 − Badin − High Rock); Lake reviewed set and customer Lake-level list 192. Release `lake-knowledge-2026-11-21.2` (replaces the unshipped draft `.1`), approval pending Michael.
