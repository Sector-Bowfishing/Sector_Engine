# Biological Brain Score Ladder (biological-state-score-v1)

> **CORRECTION (2026-10-13, adoption pass).** The baseline in this document is wrong. The live canonical score (`/scores/biological-state`) is **4.0**, not 3.46: the local recomputation omitted the `productionIntegration` dimension (+0.5; Intelligence's dependency on the Biological Brain is CONNECTED). Corrected figures: published **4.0** (State-NOT_STARTED gate cap 4.0 not reducing it); research-supported rows would add +0.3 but stay hidden behind that gate until a Biological State exists. Also: "four independent silver-carp flow datasets" is **three** (the Illinois 2004-05 and Swan Lake papers share one tagged program), and the channel-catfish production-temperature concern was overstated (only the 85 F upper bound is above agency spawning figures). See `docs/brains/biological-adoption/` on `feat/biological-brain-adoption`.


Score = Σ(weight × dimension value 0-10) / 100. Gates: State NOT_STARTED caps at 4.0; no species VALIDATED caps at 6.0. Starting point **3.46**. Contributions below are in score points.

| Dimension | Weight | Now (value → pts) | Max pts | What moves it | Who can move it |
|---|---:|---|---:|---|---|
| registryCompleteness | 10 | 10 → 1.00 | 1.00 | done | n/a |
| assessedCoverage | 15 | 9.3 → 1.40 | 1.50 | assess the 2 NOT_ASSESSED rows | Michael (policy) |
| knowledgeDepth (median species) | 20 | 1.0 → 0.20 | 2.00 | raise the median; **median is driven by minor species** | research (this campaign: → 2.5 = 0.50) |
| evidenceQuality | 10 | RESEARCH → 0.20 | 1.00 | REVIEWED share ×7, VALIDATED share ×10 | independent review, then field data |
| contradictionsGaps | 10 | 6.6 → 0.66 | 1.00 | resolve contradictions *in the bundle* | research |
| regionalTransfer | 5 | UNKNOWN → 0 | 0.50 | publish a region-tag fact | Engine |
| biologicalStateImpl | 15 | NOT_STARTED → 0 | 1.50 | build per-lake state: IN_PROGRESS 0.6, LIVE 1.2, VALIDATED 1.5 | Michael approval + build |
| biologicalStateValidation | 10 | NOT_STARTED → 0 | 1.00 | PARTIAL 0.5, VALIDATED 1.0 | field data |
| productionIntegration | 5 | 0 | 0.50 | Intelligence consumes species rules | Engine |

## The ladder

| Target | What it takes | Realistic with desk research? |
|---|---|---|
| **3.46 → 3.76** | median 2.5 (this campaign's proposals adopted) | yes (proposed) |
| **4.0** | + resolve open contradictions (≈+0.14), + Intelligence consumes species rules (+0.5) → raw ≈4.4 but **gate caps at 4.0** | yes, needs Engine/Intelligence work |
| **5** | lift the 4.0 cap: Biological State **IN_PROGRESS** (+0.6, raw ≈5.0) | no; needs Michael to approve starting State and an actual build |
| **6** | State LIVE (+1.2) with partial validation (+0.5), regionalTransfer published (+0.25 at 5/10), median 3.5, reviewed species | no; engineering + review; cap 6.0 binds until a species is VALIDATED |
| **7** | lift the 6.0 cap: ≥1 species **VALIDATED** with field data; most principal species REVIEWED; median ≈5 | no; needs field-observation pipeline (months) |
| **8** | State LIVE and validated for ≥1 lake; principal species VALIDATED (≥50% share) | no |
| **9-10** | VALIDATED state across lakes, VALIDATED species broadly, median ≥7 (needs southern reservoir telemetry for principal species), regional transfer published | no; multi-quarter |

**Max reachable by research alone: ≈4.0 (gated)**. Reaching 3.9 requires bundle changes (resolved contradictions) not just docs.

## Rubric observations for Michael (decisions, not changes)
1. **knowledgeDepth = median over all 27 assessed species** rewards covering minor fish. For bowfishing impact, a weighted mean by customer importance (carp, buffalo, gar, Asian carps) would be more faithful. Not applied; the campaign did not chase the median.
2. The 7 empty `ASSESSED/NOT_STARTED` rows depress both coverage logic and the median. Either assess them narrowly (goldfish, shad, redhorses) or mark them NOT_ASSESSED. Policy call.
3. `regionalTransfer` is permanently UNKNOWN until Engine publishes region tags; the biggest research uncertainty (southeastern transfer) has no scoring home.
4. `evidenceQuality` cannot move without independent review, which is "a separate decision". Without a reviewer role, the dimension and the 6.0 cap are frozen.
