Standards: Rehtac Cortex 3.1.1 (pin per CLAUDE.md)

# Session record: Water Clarity R3.1 production-readiness review (Sector_Ops #40)

Owner-approved review, 2026-10-31. Part A (review) and Part B (plan) only. The findings, numbers and plan are on Sector_Ops #40; private research
detail stays in the private archive and the private research branch, not in this repository.

| Item | Outcome |
|---|---|
| Part A: review of the R3.1 certification | Done, read-only. R3.1 stays a certified research candidate (frozen score unchanged). |
| Blockers found | (1) None of R3.1's production inputs exist in the Engine today (per-scene aquatic reflectance feed, serve-time Secchi prior and station history, lake context table). (2) The certification population is not Sector's lake population, and the reservoir subset does not meet every frozen accuracy bar. (3) Its Strong share depends on a temporary sensor extension. (4) No comparison with the production clarity models exists. |
| Sector_Ops #25 | Not answered by R3.1: its validation covers R3.1 only, with no season, night or turbidity component. #25 stays open. |
| Part B: promotion plan | Gated plan G0–G6 (Sector-domain validation, input feasibility, release record, shadow integration, comparison period, live re-certification, lifecycle) plus rollback, on #40. |
| Part C: shadow code | Not written: the issue allows it only if Part A finds no blocker. |

Nothing was deployed, run or written to any database; no IAM, rules or schedule change. Decisions batched for the owner on #40.
