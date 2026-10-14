# Scoring Semantics

## 1. Six things that were all called "score"
| Canonical field | What it is | Today's name | Owner |
|---|---|---|---|
| `researchMaturity` | how far the science/evidence has progressed (owner-assessed, rubric-defined) | Biological `researchMaturity`; Vegetation "maturity 2.70" | specialist |
| `underlyingScore` | computed capability **before** any gate cap | `uncapped` | specialist rubric |
| `canonicalScore` | the published truth at `/scores/{brainId}` | `value` | platform publishes, specialist computes |
| `displayedScore` | what Ops shows: canonical after any documented display cap; **never above `canonicalScore`** | `control.brains[id].score.value` | platform |
| `claimMaturity` | per-claim summary (counts by maturity) | Vegetation `claimMaturity` | specialist |
| `customerReadiness` | `NONE | INTERNAL | PILOT | CUSTOMER` — do customers consume it? | not published | platform from lifecycle + consumers |

No shared code, contract or Ops field may use bare `score` for a *new* field. Existing `score{value, uncapped, …}` blocks stay as-is for compatibility; `control_contract.from_control_summary` maps them to the v1 names and `validate_control` rejects a bare `score` in a v1 summary. `scoreStatus ∈ COMPUTED | FROZEN | UNSCORED | WITHHELD` (today's `basis`, plus the two states `basis` lacks).

## 2. Unknown
An unscored Brain has **no** score fields (`test_unscored_brain_has_no_score_fields_not_zero`); it is never `0`. Missing dimension evidence is `NOT_ASSESSED`/`UNAVAILABLE`, not a zero contribution unless the owner's rubric defines it so explicitly.

## 3. Production policy (unchanged)
`overall ≥ 8.0` **and** every required critical dimension ≥ 7.5 (`model_v1.production_ready`). Model v1 may improve *how* capability is measured; it must not game readiness. Unknown never passes.

## 4. Ownership
- **Specialist** owns evidence, domain rubric inputs, domain score calculation.
- **Platform** owns safe durable publication, stale protection, cross-Brain integrity, control-plane mirroring.
- A specialist branch carries **no authority** to overwrite another Brain's current score with a stale generated artifact (§6).

## 5. The hazard (observed 2026-10-13)
An orchestrator image bakes `frozen-scores.json`. Wind legitimately moved 3.1 → 3.3 on its branch; the deployed image still held 3.1, and the publisher re-applies it whenever any Brain state changes (hourly). Newer truth was silently reverted. Separately, a deploy from an older lineage would regress *any* Brain.

## 6. Solution: durable store + monotonic guard (simplest robust)
**Chosen:** treat RTDB `/scores/{id}` — already the canonical, platform-owned, durable node — as the source of truth, and treat every artifact (baked file, worktree, specialist branch) as a *proposal*. `publication.judge(candidate, published)`:

| Verdict | Condition | Action |
|---|---|---|
| NEW | nothing published | write |
| SAME | content equal ignoring `scoreUpdatedAt`/`updatedAt` and RTDB-dropped empties | no write |
| ADVANCE | `candidate.scoreUpdatedAt` > published, content differs | write |
| STALE | candidate older | **hold** published |
| CONFLICT | same timestamp, content differs | **hold** (human) |
| UNDATED | candidate lacks `scoreUpdatedAt`, published has one | **hold** |

`apply_guard` returns the *effective* score set (held Brains keep their published block), and `score_brains.py` computes the Engine score, control overview and write plan **from the effective set**, so a stale artifact for Brain X cannot move X, any other Brain, or the Engine score. Held items print as `HELD` and appear in the report (`held[]`); an overridden regression prints `OVERRIDDEN`. A deliberate lower correction needs a recorded decision: `SCORE_GUARD_ALLOW=<brainId>[,…]` for that run.

Why this, not more:
| Option | Verdict |
|---|---|
| A. pre-deploy checklist + `check_score_artifacts.py` | **kept** as the second layer (catches drift before deploy); human-dependent alone |
| B. one authoritative shared artifact branch | cross-lane merge ordering; still baked |
| C. runtime artifact store (GCS object per Brain) | new moving part; **not needed** now that the guard makes the existing RTDB node the authority. Becomes worthwhile only when Brains should refresh a score with no orchestrator redeploy at all (Wind's live-day growth) → `DECISION_QUEUE` D-2 |
| D. CI cross-ref check | needs Brain refs in CI; optional |
No new infrastructure was added.

**Verified live (read-only dry runs, 2026-10-14):** real publisher against `/scores`: current tree → 0 changes, nothing held. With `FROZEN_SCORES` pointing at `main`'s old file (Wind 3.1): `HELD wind: STALE … published 3.3`, Wind stays 3.3, Engine unchanged 7.1. With `SCORE_GUARD_ALLOW=wind` it would write 3.1 (proving the override is the only path).

## 7. Remaining gap (honest)
The guard protects against an *older* proposal. It cannot detect a **newer-looking wrong** proposal (a mis-stamped future `scoreUpdatedAt`) or a lower score generated *later* from a bad rubric change; that is validated by the owner's scorer tests and the pre-deploy dry-run diff (checklist step 5). It also cannot refresh Wind between deploys — that is option C.
