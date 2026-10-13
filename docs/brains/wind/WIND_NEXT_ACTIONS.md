# Wind — next actions (what is waiting on what)

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
