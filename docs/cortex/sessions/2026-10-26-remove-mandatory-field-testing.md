# Session record 2026-10-26: remove mandatory field testing

Standards: Cortex 2.7.0 @ ebc7fb9 (pin). Branch `cortex/remove-mandatory-field-testing-2026-10-26`.

**Directive.** Owner-collected field tests, trip logs, handheld measurements, sonar transects and observation quotas are optional evidence, never mandatory, in the eight Brains, the research automation, scoring, internal readiness and Cortex.

**Done.** Evidence policy (`tools/research/evidence_policy.{py,json}`, `docs/research/EVIDENCE_POLICY_V1.md` with the eight-Brain audit); all `GAPS.json` and the template reworded, schema extended; ledger/owner-action/agent-brief changes with in-place migration; Fish `predictionFitness` now measurable from historical LTRM tests; Wind scoreboard rubric v2 (v1 default unchanged) with 5 tests; Depth proposal and Fish readiness gate reworded; 4 existing owner-action records marked OPTIONAL_OWNER_DATA (preserved); new agent-research tasks for WIND-EVI-001, WIND-VAL-001, DEPTH-VAL-001.

**Not done (needs approved release / owner).** Fish runtime status strings and `fieldValidationStatus` schema field; authoritative frozen score wording for Wind dims 6-7; promotion of rubric v2; Cortex standard (requested from the Cortex session).

**Tests.** tools/research 74, tools/architecture 184, Fish 400, Depth 280, Wind research 39, brain_certification 32 passed.
