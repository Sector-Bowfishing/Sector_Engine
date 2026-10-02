# Current Clarity Stage 12: Water Reflectance Engine

**Diagnostic only.**
- Production Current Clarity is unchanged, and nothing was deployed.
- No Sector field observation was used, and the P2 fresh holdout was not touched.
- Water Temperature was not started.
- Michael's Guntersville survey stays an independent acceptance test.

**Erratum (reissued 2026-09-30).**
- **The bug.** In the first issue, the clear-water row and the CLEAR WATER ERROR line reported the in-situ "clear"
  water type (low turbidity and chlorophyll, 268 rows). A key collision in `models12.py` had overwritten the Secchi
  class clear ≥ 6 ft.
- **The corrected Secchi-clear figures** (574 rows at 412 lakes): ×1.56 and −3.3 ft for the engine, against ×1.97 and
  −5.2 ft for production.
- **Nothing else changed:** the engine, every fit and every other row are the same.

**Freeze.** The pre-registration was hashed at **2026-09-30T14:45:17Z** (sha256 `474a8cd1…`), before any Stage 12 value
existed. The certification protocol was hashed at 15:04:45Z (`1e8040b9…`), before any certification site or visit
file was fetched. Five addenda, A–D and B2, were each hashed before the data they govern was examined (section 2).

## The answer

{{X:answer}}

## 1. What was done

| | |
|---|---|
| Interface experiment | 5 frozen ACOLITE configurations against **46 AERONET-OC matchups** at 5 sites, with a 60-lake inland-turbidity guard (Guntersville excluded) |
| Harmonisation | Derived from the 12 Stage 11 Sentinel-2A/2C tandem pairs only, and validated leave-one-pair-out on both paths (Sen2Cor production and ACOLITE) |
| Corpus | {{X:corpus_line}} |
| Models | 9 candidates, fitted on training lake-folds only (5 whole-lake folds), with Guntersville excluded from every fit and selection |
| Capabilities | Exact feet and clarity class, scored separately on historical lake-held-out rows |
| Certification | A blind external protocol and sample, built without reading any Secchi value |
| Not pursued | C2RCC, C2X, P1-NIR, routing for its own sake, Landsat and OLCI fusion, temporal replacement, and public depth. No Stage 12 evidence reopened them. |

## 2. Deviations and addenda

- **A (harmonisation, 15:04Z).** A technical check on one pair showed that TOA harmonisation does not carry through
  ACOLITE's dark-spectrum aerosol step. The addendum added a water-reflectance-level method (V-ρw). It also made the
  ACOLITE-path verdict use the method that would be adopted operationally, not the V-full emulation.
- **B and B2 (certification matching, 15:31Z and 16:32Z).**
  - Earth Search's production collection has **no scenes at all for 2017 or 2022**, which are the two NLA survey years.
  - Matching for those years uses Earth Search's older `sentinel-2-l2a` collection.
  - B's first reading of that collection's offset flag was wrong: it double-subtracted 0.1 from 2022. B2 corrected it
    before any match was counted.
- **C (surface pressure, 15:59Z).**
  - At a 2,318 m lake, every pixel was flagged negative, because ACOLITE had used sea-level pressure.
  - Every corpus crop now sets its elevation from USGS 3DEP. ACOLITE converts it to pressure.
  - The 59 rows already processed were discarded.
  - AERONET sites sit at 0–174 m, so Part 1 is unaffected. At Lake Erie, B04 changes by +2% and the pooled error by
    +0.013.
- **D (viewing geometry, 17:23Z).** Older L1C baselines keep detector footprints as GML, which the GDAL stand-in cannot
  read. Those crops fall back to ACOLITE's angle-grid geometry.
- **Smaller notes.**
  - The NLA 2022 site file writes the sampled flag as `YES`, not `Y`.
  - SYKE was queried in bulk rather than lake by lake, under the same rules.
  - A candidate that "fails to run" means an ACOLITE error or an all-NaN output. Losing valid station pixels is judged
    by criterion 3, not as a failure to run.

## 3. Part 1: ACOLITE's air–water interface options

{{T:p1}}

Each cell reads median |log10 error| (median bias) against AERONET-OC Level 2.0.

**Paired against K0** (matchup-block bootstrap):

{{T:p1_paired}}

{{X:p1_text}}

## 4. Part 2: harmonising Sentinel-2C

**Coefficients** (all 12 pairs; S2C → S2A-equivalent; k is the B05 band-shape term on B06 − B04):

{{T:p2_coef}}

**P2 route flips on identical water, held-out pairs:**

{{T:p2_flips}}

**Residual band differences** (median over held-out pairs):

{{T:p2_resid}}

{{X:p2_text}}

## 5. Part 3: the corpus through the new reflectance

{{X:p3_text}}

## 6. Part 4: the simplest clarity engine

{{X:p4_text}}

## 7. Part 5: exact feet against clarity class

{{X:p5_text}}

## 8. Part 6: the blind external certification set

{{X:p6_text}}

## 9. The path to 9/10

{{X:path}}

## Files

Everything is in `scratchpad/stage12/`:

| Path | Contents |
|---|---|
| `PREREGISTRATION_STAGE12.md`, `FREEZE_STAGE12.json`, `ADDENDUM_*.md` | The frozen plan, its hashes and the addenda |
| `exp1/` | The interface experiment: guard sample, runner, per-scene results, `score.json` |
| `harm/` | The harmonisation fit, leave-one-pair-out validation, ACOLITE tandem runs, `score_tandem.json` |
| `corpus/` | The corpus driver, elevations, per-scene ACOLITE samples |
| `analysis/` | `reflectance.py`, `models12.py`, `classes12.py`, tables and JSON |
| `cert/` | The certification protocol, candidate builders, matching, `blind_sample.csv` and its hash |
| `tools/` | The ACOLITE runner with overrides, and the L1R harmoniser |

---

BEST WATER-REFLECTANCE CONFIGURATION: {{X:l1}}
RED-BAND RESIDUAL FIXED: {{X:l2}}
S2C HARMONIZED: {{X:l3}}
S2A/B/C PLATFORM-INVARIANT ENOUGH FOR CLARITY: {{X:l4}}
BEST CLARITY ENGINE AFTER CORRECTION: {{X:l5}}
CLEAR WATER ERROR: {{X:l6}}
NORMAL WATER ERROR: {{X:l7}}
STAINED WATER ERROR: {{X:l8}}
LIMITED WATER ERROR: {{X:l9}}
ALGAL WATER ERROR: {{X:l10}}
SEDIMENT WATER ERROR: {{X:l11}}
EXACT-FEET CAPABILITY: {{X:l12}}
CLARITY-CLASS CAPABILITY: {{X:l13}}
BLIND EXTERNAL CERTIFICATION SET READY WITHOUT USER SURVEY: {{X:l14}}
CURRENT PATH TO 9/10: {{X:l15}}
