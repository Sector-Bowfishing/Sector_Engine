Standards: Rehtac Cortex 3.1.6 @ a785035, pack sector/engine

# Lake Brain lease halt, scheduler resume, and the level-gauge candidates (2026-11-27)

Michael's approvals this day were given in chat: clear the latch, switch lake-brain off, resume the scheduler, and run read-only networked gauge checks from his MacBook.

## What happened
- 2026-11-27 03:50Z: the Orchestrator granted lake-brain's first automatic cycle to Pulse (`lake-brain-20261127T0350Z`, 20-minute lease).
- From 03:07Z Pulse held all new work because free disk on the Mac mini was under its 20 GB minimum. The job was queued at 03:50:49Z and started at 04:09:15Z.
- The lease expired at 04:10:25Z. Pulse renews only from inside a running job, and its first renew comes 5 minutes after the job starts. The only renew came at 04:14:16Z and was refused (`LEASE_RENEWAL_REFUSED`).
- 04:50Z: the cycle watchdog read the runner fault, latched a halt (RUNNER_FAULT) and paused the scheduler. No Brain cycle ran for about 14 hours.
- 2026-11-27 20:09Z: Michael cleared the latch; lake-brain was disabled in execution control (`brain --disable`; water-clarity, water-temp and sector-intelligence stay enabled); the scheduler was resumed with `resume-orchestrator.sh` after a dry cycle (20:16Z, `50 * * * *`).
- Cause of the low disk was very likely the Mac mini session's own Swift test run starting at 03:06Z (mini report, Sector_Ops #51).

## Not changed
Pulse is not in this repository. The smallest fix (renew once as soon as a job starts) is a Pulse change, asked of the Mac mini on #51. lake-brain stays off until it is made. The watchdog fix (#257) is merged but not deployed (an Orchestrator image rebuild is a gated step).

## Level-gauge candidates (read-only)
A USGS scan of the 354 lakes with no level source found 50 lakes with an active gauge within 0.2°; 24 are the same lake. Thirty-day and full-record daily checks, with complete years counted by the `holdout_data.complete_years` rule, are on Sector_Ops #51 (comment 7234571814). Nothing is bound: R1 to R9 of the binding review protocol have not been run, and a binding, a table rebuild and a knowledge release stay Michael's.

## Open decisions (Michael)
Lake health `OwnershipError`: Cortex registry row only (follows the 2026-11-04 decision, option (a)) or also an Engine guard. Wind switch-over: its own plan needs a 7-day shadow window and 3 clean days, so it cannot finish by 2026-11-30 unless a window has already started. Clarity H1: end the shadow and approve as the rule, or not. Satellite clarity jobs: cost money.
