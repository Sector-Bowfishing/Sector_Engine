# Current Clarity Stage 13: Low-Visibility Engine

**Diagnostic only.**
- Production is unchanged, and nothing was deployed.
- No Sector field observation was used, the P2 fresh holdout was not touched, and Water Temperature was not started.
- Michael's Guntersville survey stays an acceptance test.

**Freeze.** The pre-registration was hashed at **2026-09-30T20:39:59Z** (sha256 `d44874fb…`), before any Stage 13 feature
or metric was computed. Certification addendum 2 was frozen with it; the only later addendum, CERT-3 (21:07Z), sets
the SYKE extraction budget (section 11).

**Stage 12 erratum.** Stage 12's clear-water line had reported the in-situ "clear" water type (268 rows), not Secchi
≥ 6 ft (574 rows). A key collision in `models12.py` caused it.
- **Corrected:** C3 on ACOLITE ×1.56 and −3.3 ft, against production ×1.97 and −5.2 ft.
- **The Stage 12 hand-off was reissued** with the correction. Nothing else in Stage 12 changes.

## The answer

{{X:answer}}

## 1. What was done

| | |
|---|---|
| Foundation (unchanged) | ACOLITE K4, lake-elevation pressure, S2C V-ρw, and C3 on ACOLITE as benchmark A (identical to Stage 12: maximum difference 0.0 ft). Whole-lake folds; Guntersville excluded from every fit |
| Rows | **1,206 station-days at 792 lakes** with a valid ACOLITE disk (E13); coverage judged on all 1,582 processed rows |
| Mechanism | Same-day in-situ turbidity and chlorophyll (509 rows), plus colour and dissolved/total organic carbon fetched for corpus sites only (true colour 131 rows, DOC 190, TOC 212) |
| Features | Seven, pre-registered: red, NDCI, blue/green, green/red, 740/665, brightness, and QAA Kd(492) |
| Candidates | A; the QAA-switch Secchi model (pure and calibrated); C-lin; C-gbm (constrained boosting); O1 ordinal logit; O2 cut-points; and the Dogliotti red/NIR switch |
| Coverage | Relaxed ACOLITE masks rerun on the 313 scenes with a lost station; Sen2Cor-C3 as a lower-authority fallback |
| Footprint | The 12 tandem pairs rerun keeping the grids; 60 m disks on a 300 m grid |
| Certification | SYKE expanded from 400 to all 3,705 eligible lakes, value-blind |

## 2. Deviations and notes

{{X:deviations}}

## 3. What limits stained and limited water

**Held-out R² of log Secchi, split by component (Shapley):**

{{T:mech}}

**How much class recall is even reachable:**

{{T:ceiling}}

{{X:mech_text}}

## 4. The candidates

{{T:models}}

R / P is recall / precision; κ is quadratic-weighted.

**Gains against A:**

{{T:vs_A}}

**The pre-registered success criteria:**

{{T:success}}

**Region-held-out** (success criterion 5, for BEST and A):

{{T:region}}

{{X:models_text}}

## 5. The red/NIR turbidity switch

{{T:switch}}

{{X:switch_text}}

## 6. The direct attenuation model

{{T:qaa}}

{{X:qaa_text}}

## 7. The dissolved-colour (CDOM) signal

{{T:cdom}}

{{X:cdom_text}}

## 8. Coverage

{{T:variants}}

{{T:tiers}}

{{X:coverage_text}}

## 9. Class boundaries at the product footprint

{{T:footprint}}

{{X:footprint_text}}

## 10. Capability (historical, lake-held-out; not readiness)

{{T:shares}}

{{T:caps}}

{{X:caps_text}}

## 11. The blind certification set

{{T:cert}}

{{X:cert_text}}

## 12. Guntersville (historical agency rows, reported apart)

{{T:gunt}}

{{X:gunt_text}}

## 13. What still stands between this and 9/10

{{X:blockers}}

## Files

Everything is in `scratchpad/stage13/`:

| Path | Contents |
|---|---|
| `PREREGISTRATION_STAGE13.md`, `FREEZE_STAGE13.json`, `cert/CERT_ADDENDUM_2.md`, `cert/CERT_ADDENDUM_3.md` | The frozen plan, its hashes and the addenda |
| `insitu/` | The colour/DOC fetch for corpus sites, and the same-day matches |
| `analysis/` | `common13.py` (features, QAA-switch, switch, metrics), `models13.py`, `mechanism13.py`, `coverage13.py`, `capscore13.py`, JSON results |
| `coverage/` | The relaxed-mask reruns (313 scenes) |
| `tandem/` | The footprint disks and `footprint13.json` |
| `cert/` | The SYKE pool, prescreen, extraction, `blind_sample13.csv` and its checks |

---

PRIMARY CAUSE OF STAINED/LIMITED FAILURE: {{X:l1}}
CDOM/ABSORPTION SIGNAL USEFUL: {{X:l2}}
RED/NIR TURBIDITY SWITCH USEFUL: {{X:l3}}
DIRECT ATTENUATION MODEL USEFUL: {{X:l4}}
BEST ENGINE: {{X:l5}}
CLEAR RECALL / PRECISION: {{X:l6}}
NORMAL RECALL / PRECISION: {{X:l7}}
STAINED RECALL / PRECISION: {{X:l8}}
LIMITED RECALL / PRECISION: {{X:l9}}
COVERAGE: {{X:l10}}
S2A/B/C PLATFORM-INVARIANT AT PRODUCT FOOTPRINT: {{X:l11}}
BLIND CERTIFICATION SET READY: {{X:l12}}
CLARITY-CLASS CAPABILITY: {{X:l13}}
EXACT-FEET CAPABILITY: {{X:l14}}
REMAINING BLOCKERS TO 9/10: {{X:l15}}
