# Validation strategy: practical bowfishing validation

**Why this is the hardest blocker:** nothing in Intelligence has ever been checked against what a bowfisher actually saw. The Conditions Score is `NOT_VALIDATED`; on-device FishIntel's own handoff says it "has not been validated, because there is no data"; the pilot evaluation is `NOT_VALIDATED`. Every upstream Brain is also weak on field truth (Wind: no bank-scale surface validation, hold-out sealed to 2027-01-01; Water Temp: protected-truth gate failed; Depth/Vegetation: do not exist). Intelligence validation sits on top of that and must not pretend otherwise.

## 1. What to measure (outcome definition)
**Primary outcome:** *species-specific shootable encounters per effort-hour at a named zone*: fish of a named target species seen within range and in a state where a shot was possible, per hour of time spent actively looking in that zone. Not harvest, not "fish caught", not trip total.
Why: catch mixes skill, gear, shot choice, regulations and effort; sightings-in-range per hour is the quantity the recommendation is actually about ("is there a shootable fish here tonight"). It is still affected by clarity and wind (detectability), which is correct: the bowfisher needs fish *they can see*.
**Secondary:** species mix observed; zone usability (could not fish it because of chop/obstruction); user-judged "worth the move"; presence of each factor as observed (depth, vegetation, clarity, chop) to validate Brains.

## 2. Confounds, and the explicit rule
**Rule: more fish caught does not mean the environment prediction was right.** Toy simulation (`research/intelligence/validation/power_sim.py`, P3): with a ranking that has **zero** true effect, people who follow the top recommendation fish longer (3.5 h vs 2.5 h assumed), so raw catch per trip shows an apparent **1.39× lift**; per effort-hour it is **1.00×**. The model is a toy, but the mechanism is generic.
Confounds to control: effort hours; skill and gear; light and boat setup; targeting choice; zone access and pressure; time of night; user's prior belief (people go where they expect fish); reporting bias (successful trips get logged); survivorship (no-show nights); species regulations and season closures; non-independence (same lake, same night, same person).

## 3. Evidence ladder
| Stage | Evidence | What it can support | What it cannot |
|---|---|---|---|
| 0 | Synthetic/property tests (exist: prototype, 15 tests) | logic is monotone, deterministic, traceable | anything about fish |
| 1 | Input audits: do Brain states match what testers see (depth, vegetation, chop, clarity)? | validates Brains, finds contradictions | whether ratings find fish |
| 2 | **Blind expert ranking:** local experts rank zones for a night from a map and nothing else; compare with Intelligence's ranking, then with sightings | face validity, catches absurd rankings cheaply | calibration |
| 3 | **Paired blind-area field study** (below) | whether the top-ranked zone out-sees a lower-ranked one | species-wide generalisation beyond studied lakes |
| 4 | Opt-in trip logs with effort, conditions, species | lift estimates at scale, calibration of confidence labels, drift | causal claims without design controls |
| 5 | Tournament results | species presence/season sanity checks on a few lakes only | environment ranking (catch-weighted, effort fixed per team but sites chosen from prior knowledge, no non-detects, few lakes, regulations) |

## 4. Paired blind-area design (the core study)
- Trusted beta testers on pilot lakes. For a planned night the app shows nothing beyond the lake; the *server* selects a pair of zones: **A** = rated higher for the species, **B** = a lower-rated zone that is physically reachable, with similar access and boat-run distance (matching removes the "easy zone" bias).
- Tester fishes both for a **fixed time (e.g. 45 min each)**, order randomised by the app, rating hidden until both are logged (blinding).
- Recorded: species sightings in range, shots, time actively looking, observed chop/clarity/vegetation/depth cue, legal status. Nothing else is required.
- Also record **negative control pairs**: two zones the model rates the same. Expected difference ≈ 0; a large one means a missing factor or a design leak.
- Sample size is set by the simulation (below), after a pilot of ~20 pairs estimates the real base rate and dispersion.

## 5. Power (simulation, synthetic parameters, sign test, α = 0.05 one-sided, 80% power)
Pairs needed (night-to-night variance sd 0.6 on a log scale; negative-binomial counts):
| mean sightings per visit | lift 1.25 | 1.5 | 2.0 | 3.0 |
|---|---|---|---|---|
| 2 (k=1, noisy) | >400 | 240 | 80 | 40 |
| 2 (k=4) | 400 | 120 | 40 | 15 |
| 5 (k=1) | >400 | 240 | 80 | 30 |
| 5 (k=4) | 240 | 60 | 30 | 15 |
| 10 (k=4) | 160 | 60 | 20 | 15 |
Design comparison (base 5, k=1, lift 2.0): paired 80 pairs vs unpaired 80 trips/arm at night sd 0.6; with strong night variance (sd 1.2): paired 80 vs unpaired 160. **Pairing mainly earns its keep by removing selection bias and, when nights differ a lot, variance.** Full output: `research/intelligence/validation/power_sim_output.txt`.
Reading: a claim of "the top zone has twice the sightings" is checkable with 30–80 pairs per lake-season-species stratum; "25% better" is not checkable by a field study of this kind at any realistic size. Intelligence should therefore make coarse, large-effect claims (START_HERE vs LOW_PRIORITY) and avoid fine ranking claims. These numbers come from assumed distributions and must be redone with the pilot's real dispersion.

## 6. Pre-registration (write before the first pair is logged)
Primary hypothesis: for species S in stratum (lake, season band), the top-rated zone has higher sightings per effort-hour than the paired lower-rated zone. Analysis: one-sided paired test (sign test primary; paired log-ratio of (count+0.5)/hours as sensitivity). Success bars for the validation dimension: **PARTIAL** = ≥30 blind pairs in a stratum, ≥65% of pairs A>B (ties excluded), median rate ratio ≥1.5, negative controls show no difference; **VALIDATED** = the same with the pre-registered size from the pilot's dispersion on ≥2 lakes and ≥2 seasons, plus confidence-label calibration (START_HERE/MEDIUM+ pairs win more often than LOW_PRIORITY pairs). Report failures.

## 7. Using opt-in trip data (stage 4) without fooling ourselves
- Log effort hours, zone, species seen, conditions. Analyse **rate per effort-hour**, never totals.
- Compare against the model's rating *at the time of the trip* (stored with a version), not re-computed later.
- Adjust for user (random effect), lake, night, time-of-night. Treat users who follow recommendations as a different population; use the app's randomised "second zone" prompt as an instrument where possible.
- Never train or tune on the same trips used to claim validation; hold out by lake or by season. Log the Intelligence version so replays are possible.
- Consent: opt-in only, no precise location shared to other users. The iOS Learning module already has consent, sync queue and privacy policy but its transport is not configured (private-repo audit).

## 8. Species and input validation tracks (so Intelligence is not blamed for upstream)
- Species presence/season: stage-1 checks with species observations (what was seen, not caught).
- Water temperature: handheld loggers at zone depth (Water Temp's own blocker: shallow validation).
- Clarity: Secchi/photos per zone. Wind: anemometer + chop class at banks (Wind's field-validation gap). Depth/Vegetation: soundings and photo transects.

## 9. What not to do
Count catches; tune weights on app logs; claim accuracy from tournaments; show a validation-sounding number before stage 3; let testers see ratings before logging; skip null pairs; forget that the first trips are a pilot for the design itself.

## 10. Staffing and calendar realism
Pilot (stage 2 + 20 pairs) is a few weekends with Michael-class experts on Guntersville/Wheeler/Wilson/Pickwick. Stage 3 at 30–80 pairs per stratum needs a testers roster across a season; the Wind hold-out opens 2027-01-01, which aligns with a spring 2027 field season. Nothing here can be accelerated by computation.
