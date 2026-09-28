# Clarity Fusion Stage 5: confidence tiers, preregistered

Written 2026-09-28, before the replay below was run. Nothing in this file may change after the replay has run. If it did, say so here.

## Why

Stage 4's replay put High and Moderate at the same error:
- untouched years 2020–24: High 0.117, Moderate 0.127 (mean |log10 FNU|);
- discovery years 2025–26: 0.100 and 0.102.

Stage 4's High was a direct cell under a stable, fully recorded drainage, whatever the scene's age. So a read made ten days ago under dry weather counted as High.

## The candidate: a stricter High

A cell is **High** only if all of these hold:
1. **The satellite read this cell directly.** Filled and grass cells are never High.
2. **The scene is no older than 72 hours.** That is evidence level B, `Rules.currentSceneMaxAgeHours`.
3. **The drainage is stable since the scene.** The hydrologic cap is `high`; minor change and unknown are not enough.
4. **The rain record covers the whole catchment**, where a catchment applies.
5. **A flow or change record exists.** Flow provenance is not `unavailable`.

Items 3–5 are Stage 4's rules, unchanged. Item 2 is the only new condition.

Every cell that Stage 4 called High and that fails item 2 becomes **Moderate**. Nothing else moves.

The same build also carries the Stage 5 grass-bed decision: a grass cell gets no supported magnitude. Grass cells were never High, so this does not affect the High/Moderate comparison.

## The replay

- **Code:** `ClarityReplay --current`, the Stage 4 replay, with no change except the resolver rule above.
- **Inputs:** the same, with the same targets and stride:
  - validation targets 2020-10-01 to 2024-12-31;
  - discovery targets 2025-03-01 to 2026-09-30;
  - every fifth observed cell.
- **Metric:** mean |log10 predicted FNU − log10 observed FNU| per cell, as in Stage 4. Feet by secchi-power-v1.

## The decision rule

Keep three user-facing tiers (**High / Moderate / Low**) only if **all five** hold:
1. **Sample.** On validation, High has at least 20 target passes and 10,000 cells.
2. **Separation.** On validation, the 95% paired cluster bootstrap of (Moderate − High) mean |log10| lies entirely above 0. The bootstrap resamples target passes jointly: 2,000 draws, seed 5.
3. **Size.** On validation, High's mean |log10| is at most 0.80 × Moderate's. A tier should be at least 20% more accurate than the next one to be worth a word; Low vs Moderate was 31% in Stage 4.
4. **Feet agree.** On validation, High's mean |ft| is below Moderate's.
5. **Replicates.** On discovery, High's mean |log10| is below Moderate's.

If any fails, collapse the **user-facing** presentation to two supported levels:

| Internal confidence | Shown as |
|---|---|
| high, moderate | **Moderate confidence** |
| low | **Low confidence** |
| none | not supported (no number) |

The API keeps `confidence` (high / moderate / low / none), `authority` and the evidence level exactly as they are. Only the words and the map's certainty cue collapse. A merged top tier is called Moderate, not High, because its error (about 0.12 log10, about 0.8 ft) is not what "high" suggests.

---

## Result (added after the replay; nothing above was changed)

The replay ran at commit `c5a8604` with the same 225 validation and 141 discovery targets as Stage 4. `scripts/hydrology/confidence_tiers.py` applied the rule; the output is in `docs/data/hydrology/guntersville/stage5/confidence_tiers.json`.

| Check | Result | Value |
|---|---|---|
| 1. Sample | pass | 25 target passes, 40,907 cells |
| 2. Separation | **fail** | Moderate − High = 0.023; 95% interval −0.001 to 0.045 |
| 3. Size | **fail** | High is 0.817 × Moderate (needed ≤ 0.80) |
| 4. Feet agree | pass | High 0.75 ft, Moderate 0.80 ft |
| 5. Replicates | pass | discovery: High 0.089, Moderate 0.103 |

Mean error |log10 FNU|:

| Tier | Validation | Discovery |
|---|---|---|
| High (stricter) | 0.104 | 0.089 |
| Moderate | 0.127 | 0.103 |
| Low | 0.151 | 0.127 |

**Decision: collapse the user-facing presentation to Moderate / Low.**

The stricter High is better in both sets, but not separable at the margin set in advance. The gap's interval touches zero, and the ratio misses by 0.017. The internal `confidence` keeps `high`, so a later replay with more short-gap pairs can reopen this without a schema change.
