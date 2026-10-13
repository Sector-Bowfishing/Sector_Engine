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
| **Fleet coverage** | PARTIAL | 4 live; 74 audited; 528 label-eligible; 621 manifest (`WIND_FLEET_EXPOSURE_READINESS.md`); fleet sampler validated on 600 lakes | Live archive still 4 lakes; sampler not wired; AK/HI untested; 21 no-polygon lakes |
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
| Gust claims | NOT_REQUIRED | Withheld (NBM gust POD 0.04; HRRR 0.19, FAR > 0.9) | — |
| H2 holdout | WAITING | Sealed; criteria frozen; runner gated | 2027-01-01 |

## Summary
PASS 2 · PARTIAL 14 · WAITING 6 · NOT_REQUIRED 1 · FAIL 0. There is **no FAIL** because nothing is yet claimed that has failed; the blockers are time (30 live days, H2), humans (bank-pair and over-water observations), a decision (customer provider; ESTIMATED visibility) and a merge (`feat/cost-efficient-scheduling`).
