# Fish score reconciliation (Fish Structural Certification V1)

**Certification never moves a score.** Result: **BEFORE = AFTER**, no component changed.

## Identity of the Fish score (audit, not redesign)
| Field | Fish today | Source |
|---|---|---|
| `scoreType` | `ENGINE_READINESS_SCORE` (concept label; the node does not stamp it — `brain.json` `score.type` now declares it) | `brains/fish/brain.json`, `verification/integration/score_baseline.py` |
| `scoreValue` | **4.0 / 10** — last verified live value (Fish handoff 2026-10-14; `HANDOFF_2026-10-12.md`). *The live node was NOT re-read in this session*: the production read was declined by the session's permission policy, and a stale-by-days number is reported as such, not refreshed from memory. | prior sessions |
| `scoreVersion` | `biological-state-score-v1` | `scoring.score_biological` |
| `scoreRubric` | `docs/brains/scoring/biological-state-score-v1.json` (sha256 pinned in `verification/fixtures/scores/score_baseline.json`; **unchanged — `score_baseline.py --check` OK**) | |
| `scoreRunId` | not a field of the score block (none exists to report; the scorer stamps `scoreUpdatedAt` = generation time) | `scoring.finish` |
| `scoreGeneratedAt` | `scoreUpdatedAt`, set by `jobs/brain-scores` at each run | |
| `scoreScope` | the rubric's own statement: "NOT an average of species scores; knowledge depth is one dimension" | rubric `scope` |
| `scoreStatus` | `COMPUTED` (`basis`) — computed from the live published facts, not frozen | `control_contract` |

## Why nothing changes
1. The score is a pure function of **published RTDB facts** (`/brains/biological-state`, `/validation/biological-state`, `/species/*`, Sector Intelligence's dependency record). This branch publishes nothing and deploys nothing, so no input fact can change.
2. The facts the Brain *would* publish are byte-identical to the pre-change tree: the science golden (`tests/golden/fish_science_baseline.json`, produced by the pre-move tree) matches for registry, species, validation and health payloads.
3. Feeding the same synthetic facts to `score_biological` with the pre-change platform and with this branch's platform yields an identical result (value, `scoreBlockers`, every dimension). Probe output: `value` and all nine dimensions equal; gates `biologicalState` (cap 4.0) and `speciesValidation` (cap 6.0) fire identically.
4. The rubric file and the scorer code are untouched by this phase (the only `scoring.py` delta on this branch is the merged adoption commit `9ea894a0`, which changes `nextScoreOpportunity` wording only; no value or gate).

**BEFORE:** 4.0 (gates: `biologicalState` NOT_STARTED ⇒ ≤ 4.0; `speciesValidation` none VALIDATED ⇒ ≤ 6.0). **AFTER:** 4.0. **Components changed:** none. **Why:** nothing the rubric reads changed.

## Does structural work *deserve* score credit under the existing rubric?
No dimension rewards structure (registry completeness, assessed coverage, knowledge depth, evidence quality, contradiction load, regional transfer, Biological State implementation / validation, Intelligence connection). The cap is dominated by `biologicalState = NOT_STARTED` — a **product/science** state, not an architecture one.

## Architecture-vs-science mixing (documented, not fixed)
The one Fish number conflates "is the Brain built and wired" (e.g. `productionIntegration`, `registryCompleteness`) with "how much do we know about fish" (`knowledgeDepth`, `evidenceQuality`) and "is the per-lake product built" (`biologicalStateImpl`). After this phase Fish is **architecture-certifiable while its score stays 4.0**; those two facts are currently indistinguishable on the one score. The isolated proposal `feat/biological-score-v2` (target-scoped; not wired) is the natural place to separate them — it is a global score-system decision and out of scope here (input for Architecture Audit #1).
