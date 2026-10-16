# Decision Queue (Brain Platform campaign)

Cost-freeze items (C-1…C-5) are in `cost-freeze/COST_FREEZE_DECISION_QUEUE.md`. Note for **D-1**: a redeploy now leaves the orchestrator scheduler PAUSED by default (`SCHEDULE_STATE=enabled` to override).

Items that need Michael (authorisation) or a specialist owner. Everything else was done. Newest decisions last; resolved items move to the bottom with the outcome.

| ID | Decision | Why it is queued | Recommendation | Blocks |
|---|---|---|---|---|
| **D-1** | **Deploy the platform branch as the shared orchestrator** (`feat/brain-platform-model-v1`: runtime stale-score guard, lineage preflight, Model v1 code). Not deployed; replacing the shared orchestrator is outside this campaign's authority. | production change | Yes. Additive; dry-run against live shows 0 score changes. Steps in the handoff "Deployment plan"; verify across a full :50 cycle. | runtime protection against stale artifacts (until then only the deploy-time guard protects) |
| **D-2** | Durable *runtime* artifact store (GCS object per Brain written by the Brain's own scorer) so a score like Wind's can refresh without redeploying the orchestrator. | new moving part, new write ownership | Not now. Revisit when Wind's live-day growth makes redeploy-per-score painful; the guard already makes it safe to add later. | none |
| **D-3** | Land Model v1 docs/code on `main` (and merge order relative to the specialist adoption branches: Wind, Biological, Depth, Vegetation, Intelligence, Water Temp). | merging to main is not authorised here | Merge platform branch first (additive, no behaviour change besides the guard), then specialists rebase. | specialists adopting v1 fields |
| **D-4** | Control-plane write cost: stop rewriting `/control/fleet/*` rollups when only `lastUpdatedAt` drifted (observed 627/628 paths per cycle, ~620 small writes/hour). | changes what Ops can infer about freshness | Make `lastUpdatedAt` quantised to the staleness granularity or recompute only when `stale`/`slotsPublished` flips; needs Ops freshness-display decision. Small saving, not urgent. | none |
| **D-5** | Migrate live registry `lifecycle` values (add `lifecycle`/`executionType` beside `status`) per Brain. | each Brain's owner confirms ambiguous mappings (Clarity `BETA`, Intelligence, Depth/Biological stage) | Owners follow `BRAIN_MIGRATION_CHECKLIST.md` §2 when they next touch their registry. Nothing live changes until then. | Ops adopting v1 names |
| **D-6** | Ops UI verification: Overview load/reload/multi-tab produces 0 Engine API calls; Wind tile 3.3 vs registry duplicate. | Ops is behind a login | Michael: check Diagnostics in Ops after a hard reload. | confirming OPS hot path in practice |
| **D-7** | Wind lane: emit RTDB-safe dimension names; replace registry `scores.windCertificationScore` with `scores.canonicalRef` on next Wind deploy (Wind deployment currently blocked per its handoff). | Wind owner | follow-up in Wind lane | removing the 3.1-vs-3.3 duplicate |
| **D-8** | Water Temp (Swift runner) zero-concurrency audit. | Water Temp owner session | owner runs the §4 audit | none |
| **D-9** | Publish `held[]` from the score publisher into `control/orchestrator.scores` so Ops can show "score held: stale artifact". | needs D-1 deploy; small | bundle with D-1 | visibility only |

## Orchestrator control plane (2026-10-14)
| ID | Decision | Recommendation |
|---|---|---|
| **O-1** | Deploy the orchestrator with the control plane (`feat/brain-platform-model-v1`). Its scheduler stays PAUSED, so a deploy changes no recurring behaviour; verify with `--dry-run` then one real manual cycle. Rollback in `orchestrator/ORCHESTRATOR_CONTROL_V1.md` §12. | Approve (supersedes D-1; same branch). |
| **O-2** | Ops integration: render `/control/orchestratorV1/*` (Ops lane). | Ops session. |
| **O-3** | Control-request channel: Ops cannot write `/controlRequests/pending` under today's rules. Options: (a) narrow rules write for opsUsers with `.validate` on the request shape, (b) an authenticated callable. With the orchestrator paused, requests wait for a manual cycle. | (a) when Ops builds the buttons; keep orchestrator manual until then. |
| **O-4** | Confirm provisional dependency freshness tolerances in the manifest (e.g. Biological ← water-temp 48 h) with each Brain owner. | Owners, when they next touch their Brain. |
| **O-5** | Clarity scoped `RUN_NOW` needs `roles/run.developer` for `brain-writer` (args override). Until granted the request returns the manual command. | Do not grant until a Clarity validation window is approved. |
| **O-6** | Stage 3 (orchestrator takes over a schedule): only after an approved recurring exception; Wind last, with overlap and a no-missing-hour proof. | Not now. |

## Resolved
_None yet._
