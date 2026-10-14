# Vegetation Brain — Blockers by category (2026-10-14)

Categories: FIELD · TIME / SEASON · EXTERNAL SOURCE · LICENSING · MICHAEL DECISION · UPSTREAM BRAIN · IMPLEMENTATION · VALIDATION · PREREQUISITE BRANCH · OPS PRESENTATION.

| # | Blocker | Category | Moves | Exact next action | Owner |
|---|---|---|---|---|---|
| 1 | No fresh holdout truth lakes with ≥ 30 interior surface positives (TEST consumed; Snohomish TEST lakes have 0) | EXTERNAL SOURCE | presence, validation, gates (a)(e) | Send/answer TVA, TPWD, WI DNR, FWC requests (`VEGETATION_EXTERNAL_REQUEST_DRAFTS.md`); score new lakes once with frozen v0.3 | Michael → next session |
| 2 | Sending the request drafts | MICHAEL DECISION | #1 | Read, edit, send (nothing sent) | Michael |
| 3 | NLA belt statistic is not co-located with the truth (gate c design) | VALIDATION | validation | Michael approves a rubric proposal: station-level comparison or agency-observation truth (`READINESS_MATRIX` §4); no change made | Michael |
| 4 | Pixel-level sonar truth: FWC BioVolume ImageServers hang | EXTERNAL SOURCE | submerged | Ask FWC (draft §5) | Michael |
| 5 | Okeechobee marsh ≈ 80 % outside the registry polygon; `East_Lake_Tohopekaliga_FL` and `Tohopekaliga_Toho_FL` hold the same polygon | UPSTREAM BRAIN (Lake geometry) | spatial | Report to Lake Brain owner (not edited here) | Lake Brain |
| 6 | 29 lakes without geometry; 44 with LOW confidence | UPSTREAM BRAIN (Lake geometry) | coverage, spatial | Lake geometry work | Lake Brain |
| 7 | Potential habitat needs live Depth (tier A/B/C measured/contour) and Clarity Secchi | UPSTREAM BRAIN (Depth, Clarity) | submerged potential | Wait; contract tests exist | Depth, Clarity |
| 8 | Wind has no `surfaceDisturbed` flag; GLARE guard inactive | UPSTREAM BRAIN (Wind) | presence quality | Wind owner to publish a flag; consumed by reference | Wind |
| 9 | Seasonal gate not passed; Texas/Plains/Southwest/California uncovered; winter observations > 100 days apart | TIME / SEASON; EXTERNAL SOURCE | seasonality | More years + lakes only if cheap; otherwise publish age + lake-history frequency instead of a state (proposal #3) | Michael |
| 10 | ~~No fleet shadow run~~ **done 2026-10-14** (547 lakes observed from shared Clarity evidence, 7.2 MB + 12.5 MB PNG for zones; 275 PRESENT / 117 NOT_OBSERVED / 155 UNKNOWN). Remaining: scheduling is dependency-driven only when Clarity's pass event is wired (no Vegetation cron) | IMPLEMENTATION | scalability | Wire Clarity's new-pass event to `plan()` under the shared orchestrator (needs Michael + platform owner) | Michael / platform |
| 10b | Truth-backed coverage is 9 lakes (FWC) | EXTERNAL SOURCE | coverage | TVA / TPWD / WI DNR agency data (requests unsent) | Michael |
| 10c | No FWC survey after 2023 exists in the layer → no fresh holdout for v0.3 | TIME / SEASON; EXTERNAL SOURCE | validation | wait for FWC 2024+ publication or new agency data | — |
| 11 | v0.3 bloom-tail fix is unit-tested only | VALIDATION | presence | Evaluate once on fresh truth (#1) | next session |
| 12 | Registered/visible in Ops: `future:true`, overpromising copy; `ALL_BRAINS` excludes vegetation; no live writer | OPS PRESENTATION; MICHAEL DECISION | visibility | `VEGETATION_OPS_VISIBILITY_GAP.md` follow-ups | Michael / Ops |
| 13 | Data licences: UMN CC0 (clear); FWC/SFWMD/TVA/TPWD/WI terms for a commercial product unknown | LICENSING | authority | Ask in each request; record answers before any derived number is shown | Michael |
| 14 | Merge/deploy/live writes | MICHAEL DECISION | — | Not authorised; none attempted | Michael |
| 15 | Bowfisher/field truth (what density is "too thick to shoot"; sonar logs) | FIELD | density, product value | Field validation plan after Level-1 slice | Michael |
| 16 | Prerequisite branch: Depth foundation (`feat/depth-brain-foundation`) is not merged | PREREQUISITE BRANCH | potential habitat | wait | Depth |
