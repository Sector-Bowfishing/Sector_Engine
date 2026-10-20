# Freshness Model

Builds on the per-state envelope in `BRAIN_PLATFORM_CONTRACT.md` §4 (`generatedAt, sourceObservationAt, freshUntil, nextCheckAt, stale, evidenceStale, staleReasons, refreshReason`). That envelope is unchanged; this doc adds the **authority rule**.

## Authority rule
> **The owning Brain is the primary authority for the freshness of its own source.**

A downstream Brain consumes the owner's verdict (`freshness.stale`, `freshness.evidenceStale`) and reports it verbatim. It may impose a **stricter** requirement only when its specific derived claim needs newer evidence, and only with an explicit, documented reason (`stricterMaxAgeHours` + `stricterReason` in the dependency entry; `dependencies.validate_dependency` refuses a stricter rule without a reason).

Example: Lake says a level observation is fresh (20 h old, within its gauge cadence). Depth must not independently label that input stale. If Depth's *effective-depth* claim genuinely needs same-day level, it declares `stricterMaxAgeHours: 6, stricterReason: "…"` and its output says *why* ("consumer rule: age 20 h > 6 h (…)"), so the two statements are never contradictory — the owner's still says "fresh", the consumer's says "this claim needs newer than that".

## Two flags, never inferred from each other
- `stale` — the **TIME** rule only (`now − generatedAt > staleAfterHours`) at write time.
- `evidenceStale` — the Brain's **own evidence** rule (sensor missing, forecast cycle old…).
VERSION/FINGERPRINT Brains write `stale:false` and omit `freshUntil`.

## Rules
1. A reader never recomputes another Brain's freshness from raw timestamps.
2. `sourceObservationAt` is the newest *observation* behind the state, not the run time.
3. Unknown freshness is absent, not `false`. An unpublished upstream is `UNSATISFIED/DEGRADED` per the dependency's fallback, not "stale".
4. Ops shows `control.updatedAt`; an old overview is itself stale (display rule).
5. Client-clock staleness is display only (`timeAgo`), never a classification.

## Dependency freshness at execution time (added 2026-10-16, Orchestrator G1/G2)
`sector_brain_platform.dependency_health` applies the authority rule generically for every dependency type (Brain, environmental signal, provider data, platform registry): owner verdict → owner rule (`expiresAt`, `staleAfter`, `staleAfterHours` × evidence/generated time) → `UNKNOWN`; a consumer's declared `freshness {maxAgeHours, reason}` (brain.json) can only be stricter. A record that offers only `lastSuccessfulRun` is `UNKNOWN` ("process history, not evidence freshness"). Vocabulary: `enums.FRESHNESS_STATUS` = the Publisher's `FRESH STALE EXPIRED UNAVAILABLE UNKNOWN`. Contract: `ORCHESTRATOR_HEALTH_V1.md`.

## Brain run freshness on the control planes (added 2026-10-20)
Separate from the per-state envelope above: one verdict per Brain from the effective operating policy (Orchestrator manifest, Brain's declared rule reported beside it). Both control planes compute it with `operational_truth`; see `BRAIN_OPERATIONAL_TRUTH_V1.md`.
