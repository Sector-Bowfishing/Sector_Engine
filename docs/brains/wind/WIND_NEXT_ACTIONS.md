# Wind — next actions (what is waiting on what) — updated 2026-10-13 (continuous-validation phase)

Rule for this phase: do not invent desk work. Everything below is either **technically complete** or **blocked on time, people, a decision, or a merge**.

## Technically complete (on `feat/wind-brain-adoption`, tested)
Tonight block + `simple()` words + withheld claims · bank vocabulary (AUDITED three-way, ESTIMATED EXPOSED/PROTECTED) with conservative PROTECTED rules · geometry-tier manifest with hard blockers 522 label-eligible lake IDs · estimated-geometry builder · fleet NBM point sampler (validated against production interpolation) · one-shot gated H2 runner and frozen criteria · field record schema, validator and pair concordance · provider shadow comparison (historical) · strong-wind mechanism validation · matched bank validation · fleet readiness · live-reliability audit tool · Intelligence contract proposal with pinned fixtures · rubric v2 proposal · readiness matrix · 104 tests.

## Waiting on TIME
| Item | Date |
|---|---|
| Archive 30 valid live days | ≈ **2026-11-07 03:00Z** (needs every day 10-13 → 11-06 valid) |
| Brain-publish 30 valid live days | ≈ **2026-11-12 03:00Z** |
| H2 holdout (run `python -m sector_wind.h2 …` once) | **2027-01-01** — Michael decided: no early look |
Re-run the reliability audit weekly (`research/live_reliability.py`); a redeploy day must be audited before it counts.

## Waiting on FIELD EVIDENCE (people)
- Bank-pair sessions: ≥ 40 scored pairs, ≥ 2 independent lakes, ≥ 3 wind quadrants (Addendum v1 volumes); first programme in the field pack (Guntersville, Hartwell, one open natural/plains lake, Toledo Bend).
- Over-water wind: ≥ 30 portable sessions on 2–3 lakes, ≥ 10 with land wind ≥ 8 mph.
- Single-bank tester records for the agreement matrix.

## Waiting on MICHAEL
1. Customer provider: staged NBM move (gates in `WIND_PROVIDER_DECISION.md`, incl. risk-aware gauge input). Not executed.
2. Whether/when ESTIMATED bank exposure becomes customer-visible (recommend: only EXPOSED/PROTECTED, only after pairs on Hartwell/Toledo Bend).
3. Portable (then maybe fixed) anemometer; hosts/TVA 26a for any fixed unit.
4. Rubric review: v2 proposal; keep v1 canonical meanwhile.
5. Lake-identity resolution for the six blocked audited lakes (Lake Brain) and AK/HI NBM domains.

## Waiting on `feat/cost-efficient-scheduling` to merge
- Reconcile/rebase this branch, open the PR chain, and only then: wire `fleet_sampling` into `wind-hourly`, publish the new state fields (needs Sector_Ops schema/rules), deploy, and start Engine-side dual-wind shadow logging.

## Not to do
More provider shopping, gust or lay-down claims, numeric speed corrections, DIRECT-vs-CROSS on ESTIMATED lakes, any H2 read, any early customer exposure of modeled banks as measured.


---
## Update 2026-10-13 (continuous-validation phase) — exhaustion check
Technically complete in this phase: weekly reliability cycle runner (`research/run_cycle.py`: metadata refresh → reliability → canonical rescore → Ops summary) · canonical rescore (3.3 computed vs 3.1 published) · provider shadow + strong-wind formulation (CAL+H1) · frozen rule set v2 + independent validation v2 pre-registration (+ clarification; lake draw and pair set pinned) · field programme plan · instrument spec · fleet readiness from the published Lake Registry v1 (592 polygons recomputed) and audited-vs-registry cross-check · AK/HI decode/sampling check · fleet sampler edge hardening and partial-cycle object · dual-wind log record + plan · Ops summary builder + visibility audit · Intelligence compatibility report · rubric v2 review · readiness matrix with the ≥ 8.0 / ≥ 7.5 policy table · cost model · 130 tests.

Not done on purpose (judgment, not blockage): a regional AK/HI skill study (21 lakes, no bank geometry; low value until the product is anywhere near customers there); building fresh audited tables for Part A (needs NHD staging, heavy; field Part B is the real test); renaming `tonight.confidence` (contract-v2 decision); any change to H2 or the frozen rules.

Waiting on **TIME** (30 live days ≈ 2026-11-07 / 11-12; H2 2027-01-01; weekly cycle) · **FIELD** (pairs, over-water) · **PREREQUISITE BRANCH** (wiring, publication, deploy, dual logging, Ops schema) · **MICHAEL** (#1, #8–#12) · **LAKE IDENTITY** (15 audited lakes; 40 identity-risk lakes overall) · **VALIDATION** (independent v2 Parts A/B need data above).
