# Biological validation: preregistered criterion v1 (FROZEN)

**Frozen at:** 2026-10-13T21:32:38Z (before any field observation exists: 0 observations, 0 independent trips at this moment).
**Authority:** Michael instructed that a validation criterion be prepared and frozen before real observations begin, keeping the 30-independent-trip minimum and centring on shootable encounters per effort-hour. This text is protected by a SHA-256 recorded in `BIOLOGICAL_VALIDATION_PREREGISTRATION_v1.sha256` and a test that fails if the text changes. **It is never edited after outcomes exist.** A different design is a new file (`…_v2.md`) that explicitly supersedes this one and is dated before further data is analysed under it; results already seen under v1 stay reported under v1.

## 1. What is being tested
A Biological rule family is a set of frozen rule versions for one species that predicts WHERE (habitat classes) a fish is more likely to be found under stated conditions. **H1:** during outings matched to an activated prediction, **shootable encounters per effort-hour are higher in the habitat classes the prediction favoured than in the classes it did not**, within the same trips.
Out of scope for the confirmatory test: night vs day, depth, vegetation and flow effects as separate claims (exploratory until the Depth, Vegetation and discharge inputs exist), spawn timing, and anything about customers.

## 2. Unit, outcome and matching
* **Unit of independence: the trip** (`tripId`). Many fish or many stops in one trip are one stream. Observations from the same trip are never counted as separate validations.
* **Observation:** one habitat zone on one trip with its effort (`effortMinutes`), species ID and confidence, encounter/non-encounter, `shootableCount`.
* **Primary outcome:** shootable encounters per effort-hour = sum(`shootableCount`) / (sum(`effortMinutes`)/60), computed separately for FAVOURED and OTHER zones.
* **Favoured / other:** each observation is matched to the single latest prior prediction (made no more than 36 h before it) for the same lake and species. Its zone is FAVOURED if it is in that prediction's expected habitat classes, otherwise OTHER.
* **Non-encounters are effort.** A zone with nothing seen contributes its hours and zero encounters. A rate with any encounter lacking `shootableCount` is not computed (never imputed).
* **Species-level scoring** uses only CONFIRMED or LIKELY species IDs. GROUP_ONLY/UNCERTAIN observations are analysed at group level (buffalo, gar, Asian carp) and never score a species-level prediction.
* Predictions are logged and hash-chained BEFORE the trip; an observation is never matched to a prediction made after it.

## 3. Sample size and design (fixed now)
* **No verdict of any kind below 30 independent trips** for the (species, system) being judged. Descriptive counts may be reported earlier; they are labelled exploratory.
* A confirmatory comparison for a (species, system) additionally requires **at least 10 effort-hours in each of FAVOURED and OTHER** and **at least 10 trips that contain both** (paired within trip).
* **Systems:** the first two are Guntersville and Hartwell (different basins and pool types). VALIDATED for a species requires the criterion to be met in **at least two independent systems**, with the second system's rules frozen before its data.
* **Confirmatory set:** the internal focus species only: common carp, spotted gar, silver carp, longnose gar. All other species are exploratory.
* **Tester behaviour:** testers are asked to fish at least one favoured and one non-favoured zone on a trip when practical, record every zone they fish with its effort, and not change a logged zone afterwards.

## 4. Analysis (fixed now)
* Estimate = ratio of rates, FAVOURED / OTHER, per (species, system).
* Uncertainty = **trip-level bootstrap**: resample trips with replacement, 10,000 resamples, fixed seed 20261014, 95% interval of the ratio (adjusted interval `1 - 0.05/k` where k = number of confirmatory (species, system) comparisons that have reached their minimum sample at the time of analysis).
* **Criterion met** for a (species, system) if the **lower bound of the adjusted interval is above 1.0 AND the point estimate is at least 1.5**.
* **A species is a candidate for VALIDATED** if the criterion is met in at least two independent systems and no third system shows the reverse (upper bound below 1.0). The candidate then needs independent reviewer sign-off; promotion is a human decision recorded separately, and no code promotes a species.
* **If the criterion is not met** after the minimum sample, the rule family is reported as NOT VALIDATED with its interval. Revising a rule creates a new frozen version; the new version's trips are counted from zero, and the old version's results stay reported.

## 5. Discipline
* The thresholds above (1.0, 1.5, 30 trips, 10 hours, 10 paired trips, 36 h, adjustment, seed) are not changed after any outcome is examined.
* Interim looks are descriptive only. They may not stop, start, filter or reweight the analysis.
* Data are entered through the append-only, hash-chained observation store. Entries made more than 7 days after the trip are flagged and analysed with and without them.
* Exclusions are allowed only for invalid records (schema failures) and are listed. No post-hoc exclusion of outcomes, trips or lakes.
* Everything is reported: every (species, system) comparison, including failures and those below the minimum sample.
