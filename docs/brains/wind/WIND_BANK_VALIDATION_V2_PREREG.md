# Independent bank-exposure validation v2 — pre-registration (frozen 2026-10-13, before any outcome is read)

Applies to rule set **wind-exposure-rules-v2**, fingerprint `221a36470bbd58a54122bdeb65ee570e8c60e7898fcd8310c15300405d75f03c` (`WIND_EXPOSURE_RULES_V2.freeze.json`, pinned by a test). Those rules (PROTECTED needs modelled chop ≤ 2; ESTIMATED PROTECTED must survive 1.5× fetch; ESTIMATED customer vocabulary EXPOSED / PROTECTED / HIGH FETCH; bank labels need ≥ 5 mph) were changed **post-hoc** after the first matched validation exposed a false-PROTECTED defect on the M1/M2 sample. **That sample (the 74 audited lakes, 7 NHD-matched lakes) is consumed and may not be reused as evidence for v2.** Any change to a v2 parameter creates v3 and a new validation.

No H2 data are involved: this is geometry plus physical observations.

## Part A — fresh audited tables (computational; runs only if the audited pipeline can be executed)
- **Eligible lakes:** manifest tier ESTIMATED, no hard blocker, Lake Brain confidence HIGH, CONUS, area 5–500 km², **not** among the 74 audited lakes (256 lakes qualify).
- **Selection (frozen):** three strata by estimated max p90 fetch — S1 < 1.5 km, S2 1.5–4 km, S3 ≥ 4 km; within each, order by SHA-256 of `wind-bank-v2|<lakeId>`; take the first 4. Drawn list in `data/bank_validation_v2_lake_draw.json` (12 lakes: S1 Sinclair GA, Cheat Lake WV, Spruce Run NJ, Lake Owyhee OR; S2 Rye Patch NV, Cranberry Lake NY, Oologah OK, Alcova WY; S3 Upper Klamath OR, Mullett MI, Lake George FL, Lake Waccamaw NC). A lake whose audited NHD pipeline cannot be built is replaced by the next lake in its stratum order; replacements are logged, never chosen.
- **Truth for Part A is the freshly built AUDITED table (same method as the existing 74).** It is a geometry-method check, not physical truth.
- **Comparison:** at the audited banks' standoff coordinates, 16 wind directions, 12 mph, estimated pipeline using its **own** facing and the shipped v2 policy (as published to customers).
- **Metrics and pass lines (pooled over banks and lakes; per-lake max):**
  | Metric | Pass |
  |---|---|
  | EXPOSED/PROTECTED agreement with audited (DIRECT+CROSS = EXPOSED) | ≥ 0.85 |
  | PROTECTED precision | ≥ 0.93 |
  | False-PROTECTED: estimate PROTECTED where audited chop ≥ 3 in (pooled) | ≤ 2% pooled and ≤ 3% in every lake with ≥ 100 exposed cells |
  | HIGH FETCH precision and recall (audited chop ≥ 4) | ≥ 0.85 each |
  | Per-direction Spearman of effective fetch (median) | ≥ 0.80 |
  | Unplaceable standoff points reported as UNKNOWN, never PROTECTED | must hold (count reported) |
  | Lake-level dominant exposure direction | **reported only**; the product makes no such claim. (It failed the first validation at 58% vs 80%; if a dominant-direction claim is ever made, the ≥ 80%-of-lakes line applies.) |
- **Fail:** any pass line missed ⇒ ESTIMATED customer exposure words stay withheld and the v2 rules are reopened as v3 (never tuned on this sample).

## Part B — physical bank pairs (the real test)
- **Lakes:** Lake Guntersville (AUDITED) and Lake Hartwell (ESTIMATED) are the first two independent systems (the other Tennessee River reaches add sessions but not independence); a third independent system from {Mille Lacs, McConaughy, Toledo Bend, Maurepas} when a tester exists. ESTIMATED and AUDITED lakes are scored separately.
- **Bank/pair selection (frozen):** from `data/field_pairs_candidates.json` (sha256 recorded in the freeze file): use the pairs listed per lake in file order, axis priority SW-NE, W-E, S-N, NW-SE; mirror pairs first, then cove-vs-point, then subtle ordering. A session may use a pair only if the forecast wind-FROM is within ±25° of the pair's axis or its reverse and ≥ 8 mph sustained.
- **Eligibility of a session:** wind ≥ 8 mph (measured or forecast-confirmed), both banks observed within 60 minutes, observer blind to the prediction, record valid under `field_schema` (no repairs).
- **Volume:** ≥ 40 scored pairs, ≥ 2 independent lakes, ≥ 3 wind-FROM quadrants (N/E/S/W by session mean), at least 8 sessions on the ESTIMATED lake. Daytime and night sessions are both recorded and reported separately.
- **Pass lines:**
  | Metric | AUDITED lakes | ESTIMATED lakes |
  |---|---|---|
  | Pair concordance (ties 0.5; model ties/UNKNOWN excluded) | ≥ 0.80 with bootstrap 95% lower bound ≥ 0.65 | same |
  | False-PROTECTED observed: PROTECTED call but bank recorded choppy/rough or boat control difficult while wind ≥ 8 mph (≥ 15 calls) | ≤ 10% | ≤ 10% |
  | Tester EXPOSED/PROTECTED agreement with the Brain label (UNSURE excluded) | ≥ 0.80 | ≥ 0.80 |
  | DIRECT/CROSS agreement (AUDITED only, informational) | reported | not claimed |
- **Fail:** missing a line ⇒ the corresponding customer claim stays withheld; failures are recorded and not re-run on the same sessions.

## Rules of conduct
Outcomes are read only after the dataset is closed (volume met or program ended). No pair, session or lake is dropped after seeing its outcome; excluded sessions are listed with reasons decided from the record alone. Scores for certification are the canonical scorer's job (Evidence Addendum v1); this file only fixes how Wind's own claims are accepted or withheld.
