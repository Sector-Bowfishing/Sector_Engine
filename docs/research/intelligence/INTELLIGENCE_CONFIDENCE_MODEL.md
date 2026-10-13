# Confidence model: simple propagation, no fake certainty

## 1. Problem (measured)
Production confidence is `100 − 20 (no gage) − 15 (estimated temp) − 15 (tailwater, no gen forecast) − 10/day (cap 50) − 10 (unknown turbidity near gate)`. Probe results: a guessed clarity still reads confidence 80 (**High** band); wind, level, pressure and weather staleness never matter; two lake points differing only by gauge distance get the same confidence; the score itself is unaffected by confidence. The Brains publish no calibrated confidence either (Water Temp: "none is calibrated"; Wind: "no confidence percentages are emitted", only `firm | boundary | unknown` per bank; Clarity: `medium | low`; Biological: SCORED/UNKNOWN; Depth/Vegetation: nothing yet).

So the design cannot "combine probabilities"; none exist. It can only combine **evidence quality labels honestly**.

## 2. Vocabulary (reused, not invented)
Per factor, Intelligence reads the Brain's own labels and caps, never raises:
- **kind:** `measured | observed | modeled | forecast | proxy | none` (the platform's state-kind vocabulary).
- **support:** `BANK_AREA | LAKE | POINT | NONE`.
- **age / staleAfter / horizon:** from `provenance` / `freshness`.
- **brainConfidence:** the Brain's own label if it has one (Clarity medium/low; Wind firm/boundary mapped to HIGH/MEDIUM; unknown → INSUFFICIENT).
Output confidence ∈ `HIGH | MEDIUM | LOW | INSUFFICIENT`.

## 3. The propagation rule (implemented, `prototype/synth.py`)

Factor level (0–3):
```
base = {measured:3, observed:3, modeled:2, forecast:2, proxy:1, none:0}[kind]
if stale:                       base -= 1
if area decision and support in {LAKE, POINT}:  base = min(base, 2)
if lead_h > 0:                  base = min(base, 2)       # forecast statements never exceed MEDIUM
if brainConfidence present:     base = min(base, level(brainConfidence))
if not known (None, or beyond horizon): 0
```
Overall = **min over the species' deciding factors**. Then rule R9: the top rating class requires overall ≥ MEDIUM.

Properties, each tested: adding supporting or agreeing evidence never raises confidence (R5); five weak signals (all PROXY, lake-level, 40 h old) give LOW or INSUFFICIENT; staleness lowers by exactly one level; lake-level support caps at MEDIUM; beyond-horizon factors are unknown.

## 4. Worked mixed-evidence cases (prototype output, synthetic)
| Depth | Vegetation | Clarity | Temp | Wind | Rating / confidence |
|---|---|---|---|---|---|
| modeled, brain LOW | stale 400 h | measured | observed (lake-level) | forecast | all FAVORABLE → **WORTH_A_LOOK / LOW** (weakest factor depth; "too uncertain to top-rate") |
| modeled, brain MEDIUM | fresh observed | measured | observed (lake) | forecast | START_HERE / MEDIUM |
| measured sounding | fresh observed | measured | observed at the zone | forecast | START_HERE / MEDIUM (forecast statements cap MEDIUM) — HIGH only for non-forecast checkpoints |
| all proxy, lake, aged | | | | | favourable but LOW/INSUFFICIENT |

## 5. Why min, not a weighted mean
A bowfisher's decision fails if *any* deciding factor is wrong; a mean lets a measured clarity hide a guessed depth. Min matches how the decision fails and is trivial to explain ("limited by depth"). Weights would need calibration data that does not exist.

## 6. Two kinds of "how sure": do not merge them
1. **Evidence confidence** (above): are the inputs good and fresh for this place and time.
2. **Validation status:** has Sector ever checked that ratings of this kind find fish. Today `NOT_VALIDATED`. This is not folded into the confidence word; it is a separate fixed line ("Sector hasn't yet verified this ranking against outcomes") until `VALIDATION_STRATEGY` stage 3 passes. Folding it in would make every answer LOW for the wrong reason and train users to ignore the label.

## 7. Calibration path
Confidence labels become meaningful when each level is tied to a measured hit rate: e.g. "among zones rated START_HERE/HIGH, ≥X% of paired visits out-saw the lower-ranked zone". That needs the paired-visit data and ~150–300 paired visits per claim level at modest lift (`VALIDATION_STRATEGY` §5). Until then labels are **ordinal evidence-quality words, not probabilities**, and the UI must not show percentages.

## 8. Upstream asks (so min() has something better than kind labels)
Each Brain should publish per-state: `confidence ∈ {HIGH, MEDIUM, LOW, UNKNOWN}` with a stated basis (calibrated interval where one exists), `support`, `staleAfter`, and `horizon`. Water Temp's planned 80% residual interval, Clarity's `lowFt/highFt`, and Wind's `firm|boundary` are already the right shape; mapping tables belong in `UPSTREAM_CONTRACTS`.

## 9. Anti-patterns avoided
Percent confidence; summing deductions; confidence that depends on the score; agreement bonuses; "High" for a guessed input; confidence hidden from the output.
