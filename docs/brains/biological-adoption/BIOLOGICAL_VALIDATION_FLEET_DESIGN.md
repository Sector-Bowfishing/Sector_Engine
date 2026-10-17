# Biological validation fleet: the minimum useful design

Nothing here is published or enabled. The internal pilot runs on Guntersville; Lake Hartwell has been run once as an internal dry run (not in any bundle, no predictions logged). **Validation needs people logging trips; the Engine cannot create observations.**

## 1. Presence is private
Which species the Lake Brain reports at which lake (established / reported / stocked / in-range-unconfirmed / historical) is private research and is **not** reproduced in this public document. The species-by-lake matrix used for this design is in the private research store (`adoption/VALIDATION_FLEET_PRESENCE_MATRIX.md`). The design rule is public: **a rule can only be validated on a lake where its species is present with at least reported/established status**; species whose presence is unconfirmed or historical there cannot be tested and must be dropped from that lake's plan.

## 2. Recommended minimum fleet
| Phase | Lakes | Why |
|---|---|---|
| **A (now)** | the Guntersville pilot + **Lake Hartwell** | two independent systems: Tennessee River run-of-river pool vs Savannah-basin Corps storage reservoir. A rule frozen before the data and tested on a different system is the T2 regional-holdout design; the only way to test transfer. Species with rules at both are the Tier-A set |
| B | + a same-basin TVA lake with established presence of the stocked/invasive carp species | same-basin control for silver and grass carp rules |
| C | + a TVA lake with a tailwater and established invasive-carp presence | tailwater and bighead rules |
Not recommended yet: more lakes (observation capacity, not lake count, is the limit). Species whose presence is only "in-range-unconfirmed" everywhere (alligator gar) cannot be tested until presence is confirmed.

## 3. When rules can actually be tested
Rules activate only under their triggers, so validation arrives in seasonal bursts: rising-water and warm-rise rules (carp, gars, silver carp) mostly Mar-Jul; spawn-window rules Apr-Jul; winter rules (<10 C) Dec-Feb; night rules on any night but at LOW confidence. October gives only the fall rising-pool cases (Hartwell and Pickwick are rising today). **Elapsed time is a blocker**: expect the first meaningful comparisons in spring 2027 unless Michael has trip capacity now.

## 4. Unit, independence and bias control (existing code, unchanged)
* The unit is the **trip** (`tripId`); many fish in one trip are one stream.
* **Non-encounters with effort are required**; a rule cannot be validated from successful trips only.
* Species-ID confidence gates scoring (`CONFIRMED`/`LIKELY` only); buffalo and gar are scored at group level when ID is unreliable.
* Each observation is scored against the single latest prior prediction (no double scoring).
* No verdict below **30 independent trips**; this threshold is not changed by this campaign.

## 5. Success criterion: PROPOSED for preregistration (must be fixed by Michael BEFORE any outcome is examined)
* Primary endpoint: **shootable encounters per effort-hour** in habitat classes the rule favoured vs classes it did not, **paired within trip**.
* Analysis: lift of favoured over not-favoured encounters per effort-hour with a trip-level bootstrap interval; per rule family and per system.
* Proposed (not adopted) decision rule: a rule family is a candidate for VALIDATED only if, on ≥30 independent trips in ≥2 systems, the lower bound of the interval exceeds 1.0 and non-encounters are included. Thresholds are Michael's to set; they must not be edited after results exist.
* Everything else (night, depth, vegetation) is exploratory until the Depth and Vegetation Brains publish.

## 6. Per-trip data actually needed (schema exists)
lake, date/time, effort minutes, zone (habitat class), species with ID confidence, encounter/non-encounter and count, optional depth class, vegetation, water temperature, level context, wind band, notes (≤280 chars), pseudonymous observer. Optional fields are optional; the app/Ops collection UI is out of scope.

## 7. What is needed from Michael
How many trusted testers, at which lakes, and how many trips per week (this sets the calendar); whether Hartwell has an observer; ratification of the endpoint above before logging begins in earnest.
