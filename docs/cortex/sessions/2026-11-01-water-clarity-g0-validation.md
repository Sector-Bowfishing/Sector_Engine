Standards: Rehtac Cortex 3.1.1 (pin per CLAUDE.md)

# Session record: Water Clarity G0 Sector-domain validation (Sector_Ops #40, closes #25)

Owner-approved research run, 2026-10-31 to 2026-11-01. The numbers are on Sector_Ops #40 and #25. Private research detail stays in the private
research workspace and its backup, not in this repository.

| Item | Outcome |
|---|---|
| G0-0 coverage, G0-3 Brain bias check | Done earlier (posted on #40). |
| G0-2 visibility bands and pass bars | Owner-approved, then **frozen** together with a G0-1 analysis protocol; both hashes were posted on #40 before any scoring. |
| Research environment | Restored from the private 2026-10-12 closeout. The frozen R3.1 model files verified against their freeze hashes; the LAGOS tables were re-fetched and verified. |
| G0-1 scoring | Done. The frozen R3.1 and R2 models and a replay of the production clarity models were scored on public Secchi observations at Sector lakes, by stratum and season. |
| R3.1 | **Not promotable.** The home stratum abstains (no admitted satellite matchups on the one eligible home lake), and the South/mid-South reservoir stratum fails the frozen reservoir bars. R3.1 stays CANDIDATE / NOT_DEPLOYED, and the frozen score is unchanged. |
| Production clarity (#25) | **Not validated.** It fails the pre-registered bars in every stratum. #25 was closed with the numbers. |
| Leakage control | The R1 training population overlaps the Sector registry, so R3.1 / R2 training lakes were excluded at lake level for those models. |

Nothing was deployed, run in the cloud or written to any database. There was no IAM, rules, schedule, score or production change.
Decisions are batched for the owner on #40.
