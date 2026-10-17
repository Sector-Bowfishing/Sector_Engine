# Parallel lanes readiness

**Decision: YES_WITH_CONDITIONS — `PARALLEL_LANES_AUTHORIZED` by Michael, 2026-10-17** (condition 2 approved: push the three Clarity refs at the start of Lane B after re-verifying them; condition 1: D4 is a hard *adoption* blocker, not a discovery blocker; Fish structure is locked at `STRUCTURALLY_CERTIFIED_V1`) — Lane A (Fish Brain Research) and Lane B (Water Clarity Structural Certification V1) may run in parallel. Neither was started by this audit.

## Why parallel is safe
- Lane A changes **content** (workspace, private bundle/release, `research/GAPS.json`); Lane B changes **structure** of a different Brain (`brains/water-clarity`, its Publisher registration, its tests). Their file sets are disjoint except for five shared platform files (below) that Lane A has no reason to touch.
- The factory generalizes: Fish research needs no structural change (report §8); Clarity is a Cloud Run job, so it takes the Wind path and needs no Orchestrator path code (report §5-A).
- Neither lane deploys. The deployed-Orchestrator drift (report §5-G) is irrelevant to both.

## Conditions (all must hold; each is checkable)
1. **D4 gates Clarity *adoption*, not Clarity *discovery*.** Lane B starts with the gap audit and the branch/lineage inventory (read-only). It writes no `brains/water-clarity/` code until Michael records the D4 decision (live job source off-main; `REPOSITORY_AUDIT_DECISIONS.md` RA-18 — a pre-recorded *hard Clarity-phase blocker*). This is a Clarity adoption decision, not a platform gap.
2. **Back up Clarity's local-only branches first.** `feat/clarity-candidate-shadow` (51 commits), `research/clarity-candidate` (111) and `campaign/clarity-readiness` (2) exist on this machine only (`git ls-remote origin` returns none). With Michael's approval, push them (no force) before Lane B edits anything. (Debt D-17.)
3. **Shared-file discipline.** Only Lane B may edit `publisher/registry.py`, `control_manifest.json`, `ownership.py`, `keys.py`/`scoring.py`/`jobs.py` entries for Clarity, `ownership_map.json`, and the CI workflow. Lane A edits none of them. If Fish research needs any of them (new registry child, new path family, Species Intelligence Profile publication, Biological State graduation, any freshness change) it **stops and escalates** — that is a structural change, not research.
4. **No deploy, no scheduler, no Publisher mode change, no production write from either lane.** The Orchestrator deploy gate in report §5-G is the only route and is a separate task.
5. **Fish species identity rule.** Research adds species knowledge but does not widen identity fields beyond what the bundle carries today, and per-lake species presence stays out of the public repo (existing test `test_no_per_lake_species_presence_labels…` must stay green).
6. **Merge order.** Each lane opens its own draft PR from its own branch off then-current `origin/main`; before merge, rebase/merge main and re-run `report.py --legacy --baseline` (NEW must be 0). Lane B must not edit anything under `brains/fish/` or `brains/wind/`.
7. **Wording.** Lane B's closeout uses `STRUCTURALLY_CERTIFIED_V1` (or the long form), never bare "certified" (debt D-12).

## Known debt per lane (not blockers)
- **Lane A (Fish):** species identity in bundle (D-6); pilot graduation and legacy research adoption are Fish decisions D-1/D-4 in the Fish report; score stays gated at 4.0 by `biologicalState NOT_STARTED` — research may raise *legitimate* components, so record BEFORE/AFTER with timestamps.
- **Lane B (Clarity-specific, separate from platform debt):** D4; fragmented history across ≈ 9 branches (main holds only the v0 publisher `jobs/water-clarity-brain`, 894 lines, 35 tests); depends on the customer API (RA-20, `/conditions`, `/lakes`) — an invariant-11 candidate once code moves; 12 MB evidence + 7.5 MB polygon blob needing the large-file policy; research scripts with iOS paths; `MANUAL by decision` execution (`NOT_STARTED_HERE`); manifest entry exists with `staleAfterHours: 26` and `dependencies: []`. Lane B should expect the Fish-style **"Decision A"** (which branch becomes the baseline) as its first human decision.
- **Platform debt Lane B will feel:** hand-copying the Fish certification suite and `describe_contract.py` (D-7b) — it is the third copy, which is the trigger to extract afterwards, not before.

## Why not NO or unconditional YES
Not NO: no platform blocker. Not unconditional: conditions 1–3 prevent two real failure modes — adopting Clarity code from an unreviewed live-source question, and losing local-only commits — and condition 3 prevents silent structural change hiding inside "research".
