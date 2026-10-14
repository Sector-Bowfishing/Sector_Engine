# Wind continuous-validation cycle — summary (2026-10-13)

Branch `feat/wind-brain-adoption` (still based on the unmerged `feat/cost-efficient-scheduling` @ 48168baa; `origin/main` @ e596a6bb; nothing merged, rebased, deployed, wired or published). H2 untouched: every skill number is CAL+H1; reliability and rescoring used operational metadata and a ledger-derived mirror only. Customer wind unchanged (Open-Meteo).

## The seven end-of-cycle questions
**1. What changed in Wind truth?**
- *Provider evidence:* NBM beats the current provider on calm/light, direction, category and easing, but the current provider's point value finds windy hours better (43% vs 15% of ≥ 10 mph hours); NBM + P90 flag reaches parity (49%) — so any customer move needs a risk-aware wind input (`WIND_PROVIDER_SHADOW_COMPARISON.md`).
- *Strong wind:* clean risk ladder (no flag 1.9% → P90 10–12: 27.6% → P90 ≥ 12: 52.7% breezy hours); half of breezy hours remain unflagged; confidence is a direction-reliability label, not a risk label (`WIND_STRONG_WIND_RISK_FORMULATION.md`).
- *Geometry reality check:* the published Lake Registry v1 replaced the local polygon copy; the audited tables disagree with it for 15 lakes (2 are demonstrably a different water body); the manifest now blocks them.
- *Rules:* bank-label rule set v2 frozen (fingerprint pinned); post-hoc status stated; independent validation v2 pre-registered with a frozen lake draw and pair set.

**2. What changed in the canonical score?** Certification **3.1 → 3.3** (scorer, frozen rubric v1, dimension 8 = 1.33/8 for 5/30 valid days); BWIS 5.4 → 5.4 (54.06 → 54.16). Published Engine block remains FROZEN 3.1 (decision #8). Caps 6.0 and 7.0 active, not binding. Nothing else can move without field truth, over-water reference or H2.

**3. What changed in validation?** Matched bank validation (earlier) stays "M1 pass / M2 fail on dominant direction"; its post-hoc fix is frozen as rules v2 and **not** treated as validated. New: fleet sampler validated on CONUS + AK + HI grids; edge/partial/NaN/outside-domain hardening; dual-log record (H2-safe); 130 tests.

**4. What changed in fleet readiness?** Recomputed from Registry v1: AUDITED 59 · ESTIMATED_HIGH 337 · ESTIMATED_MEDIUM 126 · LOW 37 · POINT_ONLY 9 · NO_GEOMETRY 28 · BLOCKED 25; **522 label-eligible IDs (517 distinct waters)**, down from the earlier 528 because of the registry cross-check. AK/HI: decode and sampling SUPPORTED on one cycle; skill UNTESTED; exposure BLOCKED.

**5. What can Ops now see?** Unchanged: Ops can see the frozen 3.1, BWIS 5.4, lifecycle, validation PARTIAL with seven gate strings, models strip, health/stale, H2 text. Engine-side, a tested `wind-ops-summary-v1` builder + sample now exists (certification 3.3 vs published 3.1, 5/30 days, gate dates, coverage, providers, field status, H2, categorised blockers) — **unpublished**.

**6. What is still hidden from Ops?** Live-day count and gate date; computed-vs-published score; AUDITED/ESTIMATED/BLOCKED counts and 522 eligible; field-validation progress; tonight contract version; dual-logging/customer-switch state; categorised blockers; critical-dimension designation (so Ops' ≥ 8.0 / ≥ 7.5 guardrail cannot evaluate Wind) — `WIND_OPS_VISIBILITY_GAP.md`.

**7. Next actionable blocker?** Nothing left that Wind can advance alone. The next unblockers are people/time: (a) field pair sessions (Guntersville + Hartwell, afternoons), (b) the weekly reliability cycle, (c) Michael's decisions #1, #8–#12, (d) Lake Brain's ruling on 15 audited lakes, (e) `feat/cost-efficient-scheduling` to merge.

## Cycle log
| Cycle (UTC) | Valid archive / Brain days | Certification (prev→new) | BWIS | Moved | Registry | Tests |
|---|---|---|---|---|---|---|
| 2026-10-13 20:47 | 5 / 0 | 3.1 → 3.3 | 5.4 → 5.4 | dim 8 | v1 @ 20:20Z | 130 |
Re-run: `python research/run_cycle.py` (weekly at minimum; the next due ≈ 2026-10-20).
