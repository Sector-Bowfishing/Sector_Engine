# Depth field-validation packets for beta testers (READY; no field data exists yet)

Thresholds and class bins are **frozen** in `jobs/depth-brain/depth_brain/data/field_validation_prereg.json` (sha256 `b73f528c...fa0`, pinned in `depth_brain/field_validation.py`). Do not change them once observations begin: shift MAE <= 0.5 ft; class accuracy >= 80%; 0 observed-DRY predicted SHOOTABLE/GOOD; 68% +/- 15% of observations within 1 sigma. Not every lake is required; each lake that reports counts.

## 1. What we are testing (read this first)
Depth does **not** map this lake and does **not** know a spot's depth. It says: "the water is X ft below/above normal pool (+/- sigma)". If you know a flat's depth at one pool level, Depth predicts its depth at another: `d_pred = d_reference + (pool_now - pool_reference)`. We are checking whether that is right, and whether Depth would have called a flat DRY / TOO_SHALLOW / SHOOTABLE / GOOD / DEEP correctly. Nothing here is customer-visible.

## 2. Selected lakes
| Lake | Why | Reference pool (ft, datum) | Level source today | Expected pool movement | Notes for the visit |
|---|---|---|---|---|---|
| **Lake Hartwell (SC/GA)** | largest drawdowns; strongest test of "known flat now dry?" | 660 NGVD29 (summer top of conservation; winter guide 656) | live Lake Brain state, shift -10.6 +/- 0.3 ft on 2026-10-14 | 5-95% range 10.7 ft; seasonal 656 <-> 660 plus droughts | record **both** shift vs 660 and vs the operator guide (Depth carries `guideFt`) |
| **Guntersville (AL)** | big shallow flats; small designed range; partial IENC 9 ft contour | 595 (TVA system; summer; winter pool 593) | live, -1.4 +/- 0.3 ft | about 2 ft designed winter drawdown | IENC "shallow" is not measured 0-9 ft; do not use it as truth |
| **Wheeler (AL)** | TVA pilot | 556 | live, -2.4 +/- 0.3 | winter drawdown | |
| **Wilson (AL)** | TVA pilot, steepest shores | 507.7 | live, -0.9 +/- 0.3 | small | negative-ish control inside TVA |
| **Pickwick (TN)** | TVA pilot | 414 | live, -2.9 +/- 0.3 | winter drawdown | |
| **Lake Fork (TX)** | TWDB 2 ft contours; verified survey pool 403.0 NGVD29; effective zones validated on paper | 403.0 NGVD29 | no live Lake state (validation harness reads the verified series offline) | 5-95% range 6.5 ft | shallow-zone shares can be spot-checked against the TWDB survey |
| **Cedar Creek (TX)** | TWDB 1 ft contours; verified pool 322.0 | 322.0 NGVD29 | same as Fork | range 4.1 ft | |
| **Gull Lake (MN)** (northern control) | tiny operating range: the shift should read about 0 and the engine must not claim change | CWMS-matched pool, NGVD29 | no live Lake state (offline harness) | 5-95% range 0.8 ft | a control: a flat should read the same depth on every date |

(TWDB and Minnesota harness note: the Brain itself only consumes Lake Brain states; for non-pilot lakes the *offline validation harness* supplies the level from the reviewed binding series so the engine can be scored. The Brain never reads raw level feeds.)

## 3. Protocol (per lake)
1. **Name 3-5 flats** you actually shoot (shallow areas): GPS point, a one-line description, and which direction the bank is. Prefer flats you fish at different pool levels.
2. **Visit on 2-4 dates**, ideally with the pool differing by **>= 2 ft** between visits (use the operator's published level that day). One reference visit near a normal level; later visits at other levels.
3. **At each flat, each visit:** measure depth at the GPS point (sonar or a marked pole / hand reading; say which), note **DRY** if there is no water over the point, take one photo of the water line, and record the **time (UTC)**.
4. **Classify** what you saw with the fixed bins: DRY (no water), TOO_SHALLOW (< 1 ft), SHOOTABLE (1-< 3 ft), GOOD (3-5 ft), DEEP (> 5 ft). These are measurement bins, not fish advice.
5. **Record the pool elevation** from the operator (TVA, USACE, etc.) for that hour. Engineering will attach Depth's predicted depth and uncertainty from the Depth state generated for that time (its `inputFingerprint` is recorded).
6. Exclusions (sonar failure, wrong point) need a reason written **before** anyone looks at the prediction error.

## 4. Record sheet (CSV; one row per flat per visit)
`lake,flat,obsAt,observedDepthFt,poolFt,predictedDepthFt,sigmaFt,excluded,excludeReason` - the last four are filled by engineering from the Depth state; testers fill `lake,flat,obsAt,observedDepthFt,poolFt` + photo name. Analysis: `python -c "from depth_brain import field_validation as F; print(F.analyze(F.read_obs('obs.csv')))"` (refuses to run if the preregistration changed).

## 5. Per-lake checklist (copy for each tester)
- [ ] lake and tester; operator source for the daily level: ________
- [ ] flats named (3-5) with GPS: ________
- [ ] reference visit date and pool: ________
- [ ] visit 2 (target pool >= 2 ft different): ________ ; visit 3/4 (optional): ________
- [ ] CSV + photos returned to engineering
- [ ] any datum/gauge oddity noticed (staff gauge reading vs operator elevation): ________

## 6. What counts as a pass (the lake does not need to pass individually, the pooled test does)
Pooled over all reporting lakes (>= 5 lakes, >= 20 shift pairs, >= 60 observations): shift MAE <= 0.5 ft, class accuracy >= 80%, **zero** DRY observed-vs-SHOOTABLE/GOOD predicted, and 53-83% of observations within 1 sigma. Any failure means effective depth is **not** field-validated, whatever else passes. Failures are reported with the passes.
