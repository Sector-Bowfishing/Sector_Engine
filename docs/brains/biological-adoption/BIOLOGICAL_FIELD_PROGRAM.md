# Biological field program (Guntersville + Hartwell): ready to start, no app required

Purpose: produce honest field evidence for the preregistered criterion (`BIOLOGICAL_VALIDATION_PREREGISTRATION_v1.md`, frozen). Primary outcome: **shootable encounters per effort-hour** in favoured vs other zones, within the same trips, **including hours with nothing**. Minimum 30 independent trips per (species, system) before any verdict.

## Systems and why
| System | Why |
|---|---|
| **Guntersville (AL)** | Tennessee River run-of-river pool; the internal pilot; first predictions already logged |
| **Lake Hartwell (SC)** | Savannah basin Corps storage reservoir: a different basin and pool type, so a rule frozen before its data is a genuine transfer test. A dry run has already produced a non-UNKNOWN band |
Species per lake come from the Lake Brain's private presence data: only fish present there can be tested. Focus species (confirmatory): common carp, spotted gar, silver carp, longnose gar.

## Roles
* **Michael:** names the testers per lake, sets expected trips per week, ratifies this program. (Not yet decided: how many testers, which dates.)
* **Testers:** fish normally, record every spot with its effort, fish at least one favoured and one non-favoured zone when practical. Identified only by a code (`observerId`), never a name, email or phone number.
* **Engine/Biological:** issues the pre-trip prediction before the outing, ingests the logs, reports counts weekly. Never edits an entry.

## One outing, step by step
1. **Before leaving:** Biological runs the pilot state for the lake and logs the activated predictions (append-only, hash-chained, time-stamped). The tester receives a short card: which habitat classes are favoured tonight for the focus species, how sure (LOW/MEDIUM), and the limits. If nothing is activated, the card says so honestly and the trip is still logged (useful baseline).
2. **On the water:** use the trip-log guide (`BIOLOGICAL_OBSERVATION_TRIP_LOG.md`). One line per spot: lake, local time, effort minutes, zone, fish seen yes/no, how many, **how many shootable**, species and how sure. Optional: depth band, vegetation, water temperature, level, wind, notes.
3. **After:** fill the spreadsheet (columns match `tools/observations.py from-csv`), send it. The Engine converts local time to UTC with the lake's timezone, validates, and appends all-or-nothing.
4. **Weekly:** summary (observations, independent trips, non-encounters, effort-hours, group-level-only share). No verdicts below the preregistered minimum.

## Bias controls that are built in
* Predictions are logged before the trip; an observation is matched only to a prior prediction.
* Every zone fished is recorded, including the empty ones.
* One trip = one evidence stream; ten fish at one spot are one observation.
* Species ID is a stated confidence; buffalo/gar-type uncertainty is recorded at group level and never scores a species rule.
* Testers will know the prediction; that cannot be removed. The paired design (favoured and non-favoured zones on the same night) is the mitigation.

## Spreadsheet columns (`from-csv`)
`tripId, observerId, lakeId, localDateTime (YYYY-MM-DD HH:MM), species, speciesIdConfidence, speciesGroup, encountered (yes/no), count, shootableCount, effortMinutes, zone, depthClass, vegetation, waterTempF, clarityBand, windBand, levelContext, spawnBehaviorObserved, observerConfidence, notes`. Blank optional cells stay blank. Lakes' timezones: Guntersville America/Chicago, Hartwell America/New_York.

## Calendar reality
Most focus-species rules activate in spring-early summer (rising warm water, spawn windows), some in the cool season; only a few trigger in October. Expect the first confirmatory comparisons in **spring 2027** unless testers log through the fall and winter (still valuable: the cool-season rules and non-activated baselines). Elapsed seasons, not code, are the limiting factor.

## What this program does not do
No app, no customer feature, no per-lake publication, no species promotion. It does not require Hartwell predictions to be logged until a tester is actually fishing there (an unobserved prediction is just noise).

## Needed from Michael
Testers and expected trips per week per lake; confirmation that the preregistered criterion stands; whether Hartwell has an observer yet (that is when its predictions start being logged).
