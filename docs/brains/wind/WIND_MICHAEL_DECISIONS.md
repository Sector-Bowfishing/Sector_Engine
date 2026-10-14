# Wind — decisions for Michael (2026-10-13)

State: Wind Certification **3.1/10** (unchanged), BWIS 5.4. Customer wind is still Open-Meteo Best Match; the Brain is SHADOW. Nothing deployed or changed.

1. **Move customer wind from Open-Meteo to the Brain's NBM pipeline?** *Recommend yes, staged* (`WIND_PROVIDER_DECISION.md`): night MAE 1.38 → 0.82 m/s, bias +1.13 → ≈ 0, direction 0.62 → 0.72–0.76, and the shown wind finally matches the exposure model. Gates: 30 live days ≥ 99% (≈ 2026-11-07), fleet sampling built, automatic fallback, gust-penalty review, a logged side-by-side shadow period. Not executed.
2. **Run real bank-pair field validation?** *Recommend yes.* It is the only way to move certification (dims 6/7 = 40 pts) and to test the vocabulary and the ESTIMATED tier. Design is ready (`WIND_FIELD_VALIDATION.md`); start with Guntersville, 2 minutes per bank, handheld wind meter, blind to predictions.
3. **Anemometer / portable setup?** *Recommend yes:* handheld/boat-mounted now (enough for pairs); one continuous end-of-fetch over-water anemometer at Guntersville next (lifts the 7 cap, quantifies over-water speed, gives the nowcast gain). Budget and hosts are yours; no purchase made.
4. **Revise the Wind Certification rubric toward bowfishing usefulness?** *Recommend a separate, versioned review* (`WIND_RUBRIC_REVIEW.md`): ≥ 15 mph/≥ 20 kt event gates and all-hours direction reward cases bowfishing rarely uses. Keep v1 as the strict score; consider BWIS v2 or a v2 certification. No change made.
5. **When should ESTIMATED bank exposure be customer-visible?** *Recommend: not until a matched per-bank comparison passes on a shared polygon and at least one paired-bank programme confirms the labels on an ESTIMATED lake.* Until then show AUDITED lakes' labels as "modeled", and for ESTIMATED lakes show only the lake-level direction/tonight block, or a clearly labelled estimate if you want an earlier beta.
6. **H2 early look?** The runner refused (sealed until 2027-01-01; only ~6 of 86 days exist). If you want an early read anyway, say so explicitly: it needs a new pre-registration with a minimum sample, and it uses up the one-shot. *Recommend waiting.*
7. **Merge/base:** the adoption branch is based on the unmerged `feat/cost-efficient-scheduling` (it carries the jobs contract and the wind early-exit). It cannot merge before that branch does. No PR opened.

---
## Added 2026-10-13 (continuous-validation phase) — decisions that are now concrete
8. **Refresh the published Wind score?** The canonical scorer (frozen rubric v1, run today on ledger metadata only) returns **3.3** because dimension 8 earns 1.33/8 for 5/30 valid live days; the Engine's published Wind block is a **FROZEN 3.1** (`frozen-scores.json`: "re-scoring for consistency is forbidden"), so Ops still shows 3.1. Options: (a) keep frozen until field evidence, (b) publish the computed value beside the frozen one (Ops shows "published 3.1 · computed 3.3 as of …"), (c) refresh the frozen block on a cadence. *Recommend (b) now, (c) once the prerequisite branch lands.* No score was changed.
9. **Lake Brain / lake identity:** 15 audited lakes are blocked: 6 with a lake-identity flag (Andrews and Griffith are demonstrably different water bodies; Hiwassee is ambiguous; Eagle, Long, Sherman have a 4–5 km directory-coordinate error) and 8 whose audited feature disagrees with the registry polygon area (Bowdish, Watchaug, Norris, Texoma, Roosevelt, Neely Henry, …). Evidence in `WIND_IDENTITY_RISK_LAKES.md`. *Ask Lake Brain to rule; nothing is fixed in Wind.*
10. **Dual-wind logging terms:** the designed pilot lookups add ≈ 240 Open-Meteo calls/day. *Approve (or reject) before wiring; the request-path variant adds none.*
11. **Name Wind's critical dimensions** for the production policy (≥ 8.0 and critical ≥ 7.5): proposed set in the readiness matrix (direction, useful speed/tonight, exposure, surface/roughness, reliability, provenance; gust *not* critical). Engine does not publish the set today, so Ops' guardrail cannot evaluate it.
12. **Evening vs afternoon pair sessions:** evenings ≥ 8 mph occur only ≈ 3–4 times a month at Huntsville; afternoons ≈ 16. *Confirm daytime pairs are acceptable for the physics test (Evidence Addendum owner), otherwise the field programme takes a year.*

---
## Status after Michael's 2026-10-13/14 answers
1. Provider: Open-Meteo stays customer-facing; NBM candidate; any move must be risk-aware — **closed**.
2. Dual-wind logging: approved in principle, internal only, bounded cost, **not wired** until the prerequisite branch resolves (pilot lookups + request-path design only; never the 14,904-call fleet-hourly design) — **prepared**.
3. ESTIMATED visibility: internal/Ops with EXPOSED / PROTECTED / UNKNOWN only (never DIRECT/CROSS as validated truth); the false-PROTECTED improvement stays "not independently validated" — **adopted in code and docs**.
4. Daytime field pairs approved (Guntersville + Hartwell first; ≥ 40 pairs, ≥ 2 independent systems, ≥ 3 quadrants) — **packets generated for any lake** (`field_packet.py`).
5. Portable anemometer plan approved (≥ 30 sessions, 2–3 lakes, ≥ 10 with land wind ≥ 8 mph; ±0.3 m/s or 3%); no purchase.
6. Critical dimensions: **proposal written, awaiting approval** (`WIND_CRITICAL_DIMENSIONS_PROPOSAL.md`).
7. **Published score refresh: approved → generated, committed, awaiting the orchestrator lineage.** Canonical scorer = 3.3 (raw 3.27); the generated `frozen-scores.json` is on `feat/wind-brain-adoption`; the deployed orchestrator still republishes 3.1 until its image carries the file (`WIND_SCORE_PUBLICATION_HANDOFF.md`). No one-off write, no orchestrator redeploy from Wind.
