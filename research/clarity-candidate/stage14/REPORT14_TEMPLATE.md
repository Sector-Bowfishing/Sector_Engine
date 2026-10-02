# Current Clarity Stage 14: Blind Certification

**Diagnostic and certification only.**
- Production is unchanged, and nothing was deployed.
- No Sector field observation was used, and Michael's Guntersville survey was not touched.
- The P2 fresh holdout was not touched: every certification site has no 2026 record.
- Water Temperature was not started.
- No spectral model was searched for or retuned. The engine is Stage 13's C-gbm, fitted once on development rows.

**Freeze order** (sha256 values in `FREEZE_STAGE14.json`):

{{T:freeze}}

{{X:addenda}}

## The answer

{{X:answer}}

## 1. The frozen production candidate

{{X:frozen_text}}

## 2. The product output: states built on retrieval resolution

{{T:states}}

**How the bands were set.** At each boundary, a logistic fit of "truth above the boundary" against the engine's
lake-held-out prediction places each edge where the odds reach 2:1. Each edge is at least ±0.05 log from the boundary
(the Stage 13 ±12% platform band):

{{T:bandfit}}

{{X:states_text}}

## 3. O2 against C-gbm (development data only)

{{T:compare}}

{{X:compare_text}}

## 4. Historical capability of the frozen candidate (development, lake-held-out)

{{T:hist}}

{{X:hist_text}}

## 5. Clear water: where the bias comes from (development, diagnostic only)

{{T:clear}}

{{X:clear_text}}

## 6. Tier 3: what the Sen2Cor fallback may say

{{T:tier3}}

{{X:tier3_text}}

## 7. The sealed WQP tier

{{X:wqp_text}}

{{T:pool}}

**Blind checks on the whole certification set, before unsealing:**

{{T:checks}}

## 8. Certification: the frozen engine, scored once (US core: NLA + WQP)

{{T:cert_class}}

{{X:cert_class_text}}

**How often each issued state was right:**

{{T:cert_states}}

**The three rubrics side by side:**

{{T:cert_caps}}

**The readiness lines:**

{{T:lines}}

{{X:cert_text}}

## 9. Where it holds and where it breaks

{{T:breakdown}}

{{X:breakdown_text}}

**Out of domain (reported apart):**

{{T:syke}}

{{X:syke_text}}

## 10. Readiness

{{X:readiness_text}}

## 11. Remaining work before Water Temperature

{{X:remaining}}

## Files

Everything is in `scratchpad/stage14/`:

| Path | Contents |
|---|---|
| `PREREGISTRATION_STAGE14.md`, `FREEZE_STAGE14.json` | The frozen plan and every hash, in order |
| `cert/CERT_PROTOCOL_STAGE14.md`, `cert/ADDENDUM_A1_io.md` | The sealed-tier protocol and its one I/O addendum |
| `cert/` | Value-blind index, development footprint, pool, draw, prescreen, matches, `wqp_sample.csv`, blind checks, ACOLITE runs (`res_ns/`, `res_wqp/`) |
| `engine/` | `engine14.py`, `frozen_engine.json`, `frozen_gbm.pkl`: the frozen candidate |
| `analysis/` | `lib14.py`, `dev14.py` (sections 3–6 on development rows), `cert14.py` (the one-shot score), JSON results |
| `unseal/` | `unseal14.py`, `truth14.json`, and the agency files fetched at unsealing |

---

FROZEN PRODUCTION CANDIDATE: {{X:l1}}
EXACT-FEET HISTORICAL CAPABILITY: {{X:l2}}
ORIGINAL HARD-CLASS HISTORICAL CAPABILITY: {{X:l3}}
BOUNDARY-AWARE PRODUCT CAPABILITY: {{X:l4}}
BLIND CERTIFICATION SAMPLE SIZE: {{X:l5}}
BLIND CERTIFICATION PASSED: {{X:l6}}
CLEAR FEET READY: {{X:l7}}
NORMAL READY: {{X:l8}}
STAINED READY: {{X:l9}}
LIMITED READY: {{X:l10}}
ALGAL READY: {{X:l11}}
SEDIMENT READY: {{X:l12}}
TIER-3 PRODUCT BEHAVIOR: {{X:l13}}
CURRENT CLARITY PRODUCT READINESS: {{X:l14}}
REMAINING WORK BEFORE WATER TEMPERATURE: {{X:l15}}
