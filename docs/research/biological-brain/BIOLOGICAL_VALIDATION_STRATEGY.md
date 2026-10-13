# Biological Validation Strategy

Goal: move species rules from RESEARCH to REVIEWED to VALIDATED honestly. Rules are directional location hypotheses for a lake, season and condition set, so validation tests *those predictions*, not "the biology is true".

## Principles
1. **Independence.** Several papers from one telemetry cohort are one study. Reviews that cite a primary study are not corroboration. A claim counts as corroborated only with ≥2 datasets from different waterbodies/teams. (This campaign found e.g. grass carp Sandusky night behaviour reported in two papers = one cohort; silver carp flow response in four independent datasets = corroborated.)
2. **Transfer is scored separately.** Every rule is tagged TRANSFERS / PARTIAL / UNTESTED to Southeast reservoirs (TVA-type, run-of-river). The campaign tag distribution: nearly all principal-species night and summer rules are UNTESTED.
3. **Unknown stays unknown.** No rule is promoted by absence of contradiction.

## Four tiers of validation evidence
| Tier | Evidence | Independence rule | Counts toward |
|---|---|---|---|
| T1 | Independent peer-reviewed/agency studies in other regions | different cohorts, different authors | REVIEWED (with independent reviewer sign-off) |
| T2 | Regional holdout: study or agency survey in the target region withheld from the rule's creation | rule frozen before looking | REVIEWED → VALIDATED candidate |
| T3 | State survey / tournament / harvest records (season, water temp, location) | not used to build the rule | regional plausibility, seasonal-occurrence checks |
| T4 | Sector field observations | structured, geo-time-stamped, conditions captured, rule frozen before comparison | VALIDATED |

## Realistic validation system
1. **Rule register with freeze dates.** Each rule: id, species, season, trigger condition, predicted habitat class, evidence tier, transfer tag, and a `frozenAt` date.
2. **Prediction log.** For a lake-night, Intelligence emits which habitat classes the rule favours; the observation then records where fish were actually seen. Score hit rate against a naïve baseline (all shallow habitat equal).
3. **Observation schema (minimum):** date/time, lake, species (with *ID confidence*: buffalo and gar ID is unreliable at night), count, habitat class (backwater/cove/tributary mouth/tailwater/main channel/flat), vegetation present (Y/N, type), water depth band, shore distance band, water temp, stage/trend, clarity band, wind, shot or sight-only. Photos optional.
4. **Seasonal occurrence checks (T3).** For each species × lake, compare rule-predicted windows with state tournament/harvest dates (e.g. April grass carp tournaments on Guntersville support the spring window as a capture fact but not a habitat rule).
5. **Holdout.** Keep ≥1 lake-region per species out of rule construction. First candidates: a second TVA pool for any Guntersville-derived rule.
6. **Trusted-bowfisher panel.** Treat as T4 only after structured logging; informal reports are hypotheses.
7. **Promotion gates.** REVIEWED needs independent reviewer sign-off *and* T1 corroboration for the rule's key claim. VALIDATED needs prediction hit rate beating baseline on ≥N frozen-rule nights in ≥2 lakes (N to be set by Michael/analyst; suggestion ≥100 species-nights).
8. **Species-ID gating.** Where field ID is unreliable (smallmouth/bigmouth/black buffalo; spotted/shortnose gar), validate at group level, not species level.

## What the campaign found about current validation status
- Zero rules have T3 or T4 evidence.
- Strongest T1-type corroboration: silver carp flow response (4 datasets), grass carp tributary-run response to rising stage (2 rivers), spotted gar night movement (1 study plus second-hand), alligator gar warm+discharge response (2 rivers meta-analysis).
- No species has a Southeast reservoir T2 holdout.
