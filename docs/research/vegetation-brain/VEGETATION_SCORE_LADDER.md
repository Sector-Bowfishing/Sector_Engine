# Vegetation Brain — Score Ladder (0 → 10)

**RESEARCH-ONLY maturity ladder. This is NOT an official Sector score. Nothing here is published, registered, or shown to customers.** There is no Vegetation Brain score today. Companion: `VEGETATION_RUBRIC_PROPOSAL.md`.

**Production philosophy (given):** overall ≥ **8.0** *and* every critical dimension ≥ **7.5**.

## Ladder

| Level | Name | What is true at this level | Evidence required to claim it |
|---|---|---|---|
| **0** | Nothing | No vegetation data, no design | — |
| **1** | Awareness | Question defined; assets audited; slot reserved; no external data pulled | Audit document |
| **2** | Source map | Authoritative sources and ground-truth datasets identified and graded; some downloaded; honest gap list | Source matrix + ledger + manifest |
| **3** | Design + first measurement | Architecture, class/density scheme, provenance model written; one independent, reproducible measurement of a satellite observer against real survey data on ≥2 lakes | Reproducible report with metrics |
| **4** | Offline prototype | Surface-reaching observer runs offline on a stratified lake sample (≥30 lakes, ≥4 regions); metrics vs survey on ≥10 lakes; known failure modes catalogued | Metrics table, per-region failure notes |
| **5** | Validated surface-reaching classes | Emergent/floating presence & density validated against independent survey on ≥25 lakes across ≥5 regions (precision/recall/F1/IoU thresholds pre-registered); unread cells refused; confidence calibrated | Pre-registered validation report |
| **6** | Fleet shadow | Observer runs on all lakes with polygons in shadow (no customer exposure); cloud/ice/bloom refusals measured; seasonal prior back-tested vs naive climatology | Shadow run logs; back-test report |
| **7** | Seasonal + level aware | Seasonal prior beats naive climatology (pre-registered margin) by regime; level/depth interaction wired to real Lake/Depth state; potential-habitat zone validated against survey; submerged claims limited to validated clarity/depth regimes | Back-test + cross-Brain integration tests |
| **8** | Production-grade (gate) | Meets **overall ≥ 8.0 and every critical dimension ≥ 7.5**; platform contract passed; health/freshness monitoring; provenance on every cell; regression tests; documented refusal behaviour | Gate checklist signed with metrics |
| **9** | Survey-fused | Agency survey ingestion (FWC, MN, WI, TVA, TPWD…) refreshing calibration per region; user sonar/field feedback loop; multi-year change detection validated | Calibration logs, feedback validation |
| **10** | Reference | Independent audit; sub-pixel density calibrated per regime; deep-SAV via sonar/crowd; sustained accuracy across seasons | Multi-season audit |

## Gating rules
1. A level cannot be claimed on any dimension without the listed evidence artifact in the repo or ledger.
2. **No self-validation:** validation must use an independent source (survey, NLA, field) — never another satellite classification.
3. **A refusal-capable design is required for ≥6.** A Brain that fills unread cells with lake means is capped at 4.
4. **Submerged claims:** a Brain that does not claim observed submerged vegetation can still reach 8 on the dimensions it covers, but the `submerged` output must be limited to `POTENTIAL_HABITAT` and the submerged-detection dimension is scored as built (see rubric): a missing capability is not a high score.
5. Scores are produced by a script from artifacts, not by hand (as for other Brains' score history).

## Where each dimension sits today (research-only; see rubric doc for detail)
The Brain as a whole sits at **ladder level 3** at best (design plus one measurement pending/complete in `VEGETATION_VALIDATION_STRATEGY.md`), nowhere near the 8.0 gate.
