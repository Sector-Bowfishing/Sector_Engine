# Canonical Wind rescore — 2026-10-13 (cycle 1 of this phase)

**What was run:** the real scorers, unmodified: `sector_wind.scoreboard.compute` (Wind Certification, frozen rubric v1, frozen evidence dir) and `sector_wind.bowfishing_score` (BWIS v1, frozen definition sha 21e2a326…), through `research/canonical_rescore.py`. Reliability inputs (dimension 8 / BWIS E2) were read from a **ledger-derived metadata mirror** (`live_metadata_mirror.py`: cycle status and timestamps only; no live NBM/RTMA/METAR/state value was opened), so H2 stays sealed. The scorer's skill dimensions 1–4 still use the frozen CAL+H1 evidence file (`wind_skill_source.json` → `v50_corpus_validation.json`); the note in that file that "live milestone windows are appended when complete" must **not** be triggered before 2027-01-01 (it would score H2). Nothing was appended to the private score log, and the Engine's published (FROZEN) block was not touched.

| | Previous | New (computed 2026-10-13 20:36Z) |
|---|---|---|
| **Wind Certification** | **3.1** (raw 3.13; log entry 2026-10-07 23:36Z; Engine frozen block 2026-10-12) | **3.3** (raw 3.27 = 32.65 / 100) |
| **BWIS v1** | 5.4 (54.06 / 100) | **5.4** (54.16 / 100) |

**Dimension moved:** only **8 Freshness/reliability**: 0 → **1.33 / 8** — "5/30 complete days (2026-10-08…10-12), worst completeness 1.0000, median age 68 min, catch-up runs 20" (credit = days/30 × completeness; median-age and fallback-exercised conditions pass). BWIS: **E Operational Integrity** 2.4 → 2.5 (E2 = 3 × 5/30 = 0.5).
**Unchanged:** 1 Speed 0/12 (≥ 15 mph events: NBM forecast none), 2 Direction 4.32/8 (0.758 within 22.5°), 3 Gust 0/5, 4 Lead 5/5, 5 Fetch method 10/10, 6 Exposure (field) 0/20, 7 Surface (field) 0/20, 9 Coverage 4/4, 10 Provenance 8/8.
**Active caps:** 6.0 (exposure and surface never field-validated) and 7.0 (land-only, no over-water reference). Neither binds at 3.3.

## Why it moved (and why the Engine still shows 3.1)
The reliability dimension is *designed* to grow automatically with valid live days (prior planning: "+8 automatic ≈ 2026-11-07"). Nothing else changed canonically: the new capabilities of the last days (tonight block, bank vocabulary, rule set v2, tiers, sampler, schema) have **no rubric dimension** that can score them, and the evidence they need (bank pairs, over-water reference, H2) does not exist. The Engine's published Wind score is a **FROZEN block** (`docs/brains/scoring/frozen-scores.json`, basis FROZEN, "re-scoring for consistency is forbidden"), so Ops still shows 3.1 while the scorer says 3.3. That divergence is an Engine decision (refresh the frozen block from the scorer on a cadence, or keep frozen and publish the computed value beside it) — flagged in `WIND_OPS_VISIBILITY_GAP.md`; not changed here.

## Trajectory (derived, not promised)
Dimension 8 = 8 × days/30 at full completeness: 6 days → 1.6 → score 3.3; 15 days → 4.0 → ≈ 3.6; **30 valid days (≈ 2026-11-07 if no day is lost) → 8.0 → raw 39.3 → 3.9**. Beyond 3.9 the only movers are field evidence (dims 6/7: +40) and over-water (cap 7), then H2-dependent dimensions.

## Cycle log
| Cycle (UTC) | Valid archive days | Certification | BWIS | Moved |
|---|---|---|---|---|
| 2026-10-13 20:36 | 5 | 3.1 → **3.3** | 5.4 → 5.4 | dim 8 |
