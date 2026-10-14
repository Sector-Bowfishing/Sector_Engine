# Wind production readiness matrix (2026-10-13)

Status words: PASS · PARTIAL · FAIL · WAITING (blocked on time, humans or a decision) · NOT_REQUIRED. "Production" here means customer-serving Wind; nothing is promoted, the canonical score is **3.1 / 10**. Evidence references are to files in `docs/brains/wind/` unless noted.

| Row | Status | Evidence | What is missing |
|---|---|---|---|
| **Direction** | PARTIAL | Night, forecast ≥ 5 mph, ≤ 12 h: within 22.5° 0.81 (5–10 mph), 0.97 (≥ 10); suppressed < 5 mph (research V1; code `tonight.py`). Provider shadow: 0.78 vs 0.70 for current provider. | Land stations only; one weak station (8A1 0.44); H2 sealed; other regions untested |
| **Speed** | PARTIAL | Calm/light correct; bias −0.4 mph overall; observed ≥ 10 mph under-forecast 4.6–6 mph (V2, provider shadow) | Windy-tail bias handled by wording/flag only; no over-water speed |
| **Tonight forecast** | PARTIAL | Category exact 0.79 vs 0.77 baseline, within-one 0.99 (V3); `simple()` contract + scenario tests | Skill is calm-vs-light; H2 pending (frozen criteria `WIND_H2_PREREG.md`) |
| **Stronger-wind risk** | PARTIAL | P90 ≥ 10 mph flag: 33% vs 3.4% breezy nights, POD 0.51 (night level); 49% hours caught (`WIND_STRONG_WIND_RISK_VALIDATION.md`) | Misses half; P90 not a ceiling (covers 32% of ≥ 10 mph hours); ≥ 15 mph 70% missed |
| **Trend** | PARTIAL | "Easing" precision 0.65 vs 0.57 for current provider; accuracy 0.55 vs 0.42 baseline | Rising and lay-down withheld (no skill) |
| **Bank exposure** | PARTIAL | Vocabulary + tests; matched vs audited: label agreement 0.96 (audited facing), PROTECTED precision 0.95, false-PROTECTED ≈ 1% | MODELED only; no field truth; ESTIMATED shows EXPOSED/PROTECTED only |
| **Fetch** | PARTIAL | Frozen 9-ray CEM; audited tables QA'd; matched polygon fetch ρ 0.93, HIGH FETCH P/R 0.89/0.95 | ESTIMATED dominant-direction line failed (58% vs 80%); identity-risk lakes blocked |
| **Fleet coverage** | PARTIAL | 4 live; 74 audited; 522 label-eligible IDs (517 distinct waters); 621 manifest (`WIND_FLEET_EXPOSURE_READINESS.md`); fleet sampler validated on 600 lakes | Live archive still 4 lakes; sampler not wired; AK/HI untested; 21 no-polygon lakes |
| **Freshness** | PASS | 3 h stale rule; archive median 1.14 h after init (NBM posting floor); 0 stale of 156 logged states (`WIND_LIVE_RELIABILITY.md`) | Only 7 days of history |
| **Confidence** | PARTIAL | Frozen rule; H2-C1/C2 pre-registered; scenario tests | Label does not rank strong-wind risk; ordering unproven until H2 |
| **Provider reliability** | PARTIAL | 164 executions, 0 failed; 744 NBM cycles complete; transient RTMA failures 0.15% recovered | NOAA S3 is a single upstream; 7 days |
| **30-day live reliability** | WAITING | 5 valid days (10-08…10-12); archive gate ≈ **2026-11-07 03:00Z**; Brain-publish gate ≈ **2026-11-12 03:00Z** | Time; any invalid day or redeploy moves it |
| **Observed truth** | PARTIAL | 140k station-hours METAR (land) | Over-water and bank truth |
| **Bank-pair validation** | WAITING | Field pack (99 candidates, 9 lakes), protocol, schema, concordance code | Field observations (humans, ≥ 40 pairs, ≥ 2 independent lakes, ≥ 3 quadrants for credit) |
| **Over-water truth** | WAITING | Recommendation: portable first, ≥ 30 sessions, 2–3 lakes | Instrument + sessions; Michael decision |
| **Cost** | PASS | Public NOAA data; one CONUS decode/cycle already running; fleet sampling adds 0 reads/calls, 24 objects/day | Confirm Cloud Run memory/runtime with 621-lake sampling |
| **Orchestration** | WAITING | `/jobs` contract + early-exit exist on `feat/cost-efficient-scheduling` (unmerged); adoption branch is based on it | Merge of that branch, then reconcile |
| **Fallback** | PARTIAL | Brain marks stale (> 3 h) and DEGRADED; staleness reasons published | Automatic customer fallback to the current provider is not built (needed only at migration) |
| **Customer-provider migration** | WAITING | Staged recommendation + 8 gates (`WIND_PROVIDER_DECISION.md`); shadow comparison (`WIND_PROVIDER_SHADOW_COMPARISON.md`) | Michael approval; 30 live days; fleet sampling; risk-aware gauge input |
| **Rollback** | PARTIAL | Brain publishing: remove `SECTOR_WIND_BRAIN_RTDB_URL`, archive unaffected (documented, exercised by the 401 incident) | Migration rollback (switch back to Open-Meteo) undefined until a migration path exists |
| **Intelligence contract** | PARTIAL | Final proposal, fixtures, tests that pin the fixtures (`WIND_INTELLIGENCE_CONTRACT_FINAL_PROPOSAL.md`) | Intelligence reader; Ops schema/rules; publish path for bank detail |
| **Ops visibility** | PARTIAL | `WIND_OPS_VISIBILITY_GAP.md`: Ops shows score/BWIS/lifecycle/validation/models/health; cannot show live days, gate date, tiers, field progress, categorised blockers; builder + sample exist (`ops_summary.py`) | Engine publication (blocked by the prerequisite branch) and Ops rendering |
| **Lake identity (6 audited lakes)** | WAITING | `WIND_IDENTITY_RISK_LAKES.md`: 3 audited tables are the wrong water body, 3 have a 4–5 km coordinate error; all blocked | Lake Brain resolution |
| **AK / HI** | PARTIAL | `WIND_AK_HI_STATUS.md`: NBM AK/HI products decode and the sampler matches (≤ 0.005 m/s); skill untested; exposure BLOCKED | station-based regional check; per-domain ingest |
| **Dual-wind logging** | WAITING | record builder, H2-safe truth attachment, growth model (≈ 12 MB/month gz, +240 calls/day) tested; not wired | prerequisite branch; Engine request-path hook |
| **Independent bank validation v2** | WAITING | rules frozen (fingerprint), pre-registration frozen with lake draw and pair set; Part A needs fresh audited tables, Part B needs field pairs | field sessions; NHD staging for Part A |
| **Strong-wind formulation** | PARTIAL | flag ladder explored (1.9% / 27.6% / 52.7%); proposal to split forecastConfidence from windRisk | pre-registration and fresh data before any change |
| Gust claims | NOT_REQUIRED | Withheld (NBM gust POD 0.04; HRRR 0.19, FAR > 0.9) | — |
| H2 holdout | WAITING | Sealed; criteria frozen; runner gated | 2027-01-01 |

## Summary
PASS 2 · PARTIAL 17 · WAITING 9 · NOT_REQUIRED 1 · FAIL 0. There is no FAIL because nothing is yet claimed that has failed; blockers are time (30 live days, H2), humans (bank pairs, over-water), a decision (customer provider; ESTIMATED visibility), Lake Brain (identity) and a merge (`feat/cost-efficient-scheduling`).

## Production policy check (Sector policy: Brain score ≥ 8.0 AND every critical dimension ≥ 7.5)
**Overall:** canonical Wind Certification **3.3** (computed 2026-10-13; Engine-published frozen block 3.1) vs floor **8.0** → gap **4.7**. BWIS 5.4 (separate). Engine has not named Wind's critical dimensions (Ops' guardrail only evaluates them when Engine does). Proposed critical set below; each is judged on its v1 credit × 10 (a dimension is "met" at ≥ 7.5).

| Critical capability | v1 dimension | Current state | Score now (credit × 10) | Floor | Gap | Next action | Blocking dependency |
|---|---|---|---|---|---|---|---|
| Direction | 2 | within 22.5° 0.758 all hours (0.81–0.97 at night when forecast ≥ 5 mph) | 5.4 | 7.5 | 2.1 | decide rubric scope (night/speed-weighted direction, v2) — **no tuning** | rubric review (Michael); H2 for any new claim |
| Useful speed / tonight forecast | 1 | MAE/bias pass; the ≥ 15 mph event condition fails (NBM forecasts none) | 0.0 | 7.5 | 7.5 | rubric v2 replaces the extreme-event gate by tonight-category + risk-flag skill | rubric decision; H2 |
| Stronger-wind risk | 1 / 3 (events) | flag 33% vs 3.4% nights; misses half | unscored (no v1 dimension) | 7.5 | n/a | pre-register ladder test on fresh data | dual-wind logging (prerequisite branch) |
| Trend | 4 (lead) | easing precision 0.65; rising/lay-down withheld | 10.0 (lead dimension only) | 7.5 | 0 | none | — |
| Bank exposure validated | 6 | no field data | 0.0 | 7.5 | 7.5 | bank-pair programme (≥ 40 pairs, ≥ 2 lakes, ≥ 3 quadrants) | FIELD |
| Surface / roughness validated | 7 | no field data | 0.0 | 7.5 | 7.5 | same sessions record roughness | FIELD |
| Fetch method | 5 | audited method QA pass | 10.0 | 7.5 | 0 | keep; ESTIMATED tier remains outside | — |
| Reliability (30 valid live days) | 8 | 5 / 30 | 1.7 | 7.5 | 5.8 | accumulate; weekly audit | TIME (≈ 2026-11-07) |
| Provenance / Unknown | 10 | pass | 10.0 | 7.5 | 0 | keep | — |
| Coverage | 9 | 4/4 dev lakes + 50 audited QA lakes | 10.0 | 7.5 | 0 | note: coverage does not count ESTIMATED/blocked | — |
| Gust | 3 | NBM gust POD 0.04 | 0.0 | 7.5 if critical | 7.5 | **recommend not critical**; withhold gust claims | rubric decision |
| Over-water reference | cap 7 (no dimension) | none | n/a | gate | gate | portable instrument sessions | FIELD / Michael |
| Fleet exposure coverage | none | 522 label-eligible IDs (517 distinct waters), 0 validated | unscored | — | n/a | v2 coverage dimension capped by validation tier | rubric decision |
| Confidence | none | rule frozen, ordering unproven | unscored | — | n/a | H2-C1/C2 on 2027-01-01 | H2 |
| Intelligence contract | none | proposal + fixtures | unscored | — | n/a | reconcile (`WIND_INTELLIGENCE_COMPATIBILITY.md`) | prerequisite branch |

**Reading:** even if the unscorable capabilities were excluded, three critical v1 dimensions are at 0 (speed event gate, exposure, surface) and one at 1.7 (reliability). Production eligibility needs field truth, 30 valid days and a rubric decision; no engineering change inside Wind closes those gaps.
