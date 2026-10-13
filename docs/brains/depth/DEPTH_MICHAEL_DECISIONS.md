# Decisions and actions for Michael (Depth Brain) - generated 2026-10-13

Everything below is blocked on a human or external party, not on more Depth analysis. Current state: 198 of 621 lakes have a defensible shift (181 verified datum, 17 TVA inferred); only 5 can publish because Lake Brain publishes 5 states; 91 HIGH / 102 MEDIUM / 423 BLOCKED. Research maturity is a research number, not a score.

## A. Decisions (yes/no)

| # | Decision | Recommendation | What it unlocks | Doc |
|---|---|---|---|---|
| 1 | Approve a **shadow write** of Depth for the 5 pilots (`--yes-write-shadow`; creates `/brains/depth` and `/lakes/*/states/depth`) | Yes, after #2 below, pilots only, watch two cycles | Depth appears in the Brain RTDB (still invisible in Ops until #3) | DEPTH_ORCHESTRATION_PLAN.md |
| 2 | Add `depth` to the platform control plane as a **shadow Brain** that cannot move health/conformance roll-ups | Yes | Depth in `/control/overview` | DEPTH_OPS_VISIBILITY_GAP.md |
| 3 | Ops catalog: flip `future:false` for Depth **and rewrite its question/outputs** (shift, datum, reference, tier; not bathymetry/channels/ledges) | Yes, with the rewrite | Ops can show Depth | DEPTH_OPS_VISIBILITY_GAP.md |
| 4 | Ratify `depth-brain-score-v1` (denominator, inferred-datum weight 0.5, critical dimensions: datumCorrectness, effectiveDepthCorrectness, fleetCoverage, validation) | Review first; no score until live coverage exists | an official score path | DEPTH_SCORE_V1_PROPOSAL.md |
| 5 | **Minnesota DNR**: accept the licence reading (derived numbers allowed, no raw geometry/map layer) | Yes after a courtesy note to MN DNR | 10 tier A/B lakes incl. Mille Lacs, Leech, Winnibigoshish, Vermilion | DEPTH_LICENSING_UNLOCK_QUEUE.md |
| 6 | Orchestration: register Depth as an in-process Brain in `brain-orchestrator` | After #1 succeeds | automatic hourly shadow runs | DEPTH_ORCHESTRATION_PLAN.md |
| 7 | Merge order: `feat/cost-efficient-scheduling` (Depth's base) is still unmerged | Merge it before any Depth branch | Depth can go to main | git |

## B. Actions (people / outbound)

| # | Action | Detail | Unlocks |
|---|---|---|---|
| 1 | Send the **source requests** (TVA first) | 12 ready drafts; none sent | Southeast bathymetry; TVA datum name |
| 2 | Send **datum confirmations** (Reclamation first) | 11 asks, one-line replies suffice | 19 RISE lakes, 7 Duke, McConaughy, TVA verified |
| 3 | **Field validation**: 5-10 lakes with beta testers + sonar | preregistered, hash-frozen thresholds; tooling ready | `validation` and `effectiveDepthCorrectness` can finally be scored; removes the 5.0/6.0 caps |
| 4 | Ask the survey owners for the **water level on the survey date** | MN, OH, NE, ND, OK, KS contours | effective zones for the non-Texas contour lakes (currently all withheld; validation failed or ungradable) | 
| 5 | iOS owner: fix the Guntersville IENC numbers (62% / 2,445 -> 67.2% / 2,133) | exact lines listed | correct customer-visible coverage | 

## C. Lake Brain (separate Brain, separate session)

| # | Item | Why Depth cares |
|---|---|---|
| 1 | Adopt fleet bindings (`feat/lake-brain-adoption`) | 193 defensible Depth lakes have no live Lake state |
| 2 | Publish `datum` / `datumAuthority` / `datumConfidence` on `states/lake` (TVA publishes null today) | moves TVA from inferred to verified without manifest edits |
| 3 | Rebind 7 NWPS lakes to the CWMS/USGS series | 7 lakes resolve (numerically identical series) |
