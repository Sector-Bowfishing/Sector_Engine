# Evidence policy V1: owner-collected field data is optional (owner directive 2026-10-26)

**Rule.** New owner-collected field tests, bowfishing trip logs, handheld measurements, sonar transects and field-observation quotas are **optional evidence, never mandatory**. They never block research completion, a capability dimension, candidate scoring, readiness or internal app testing. Existing scientific observations (agency surveys, historical measurements, public datasets, literature) remain evidence. Machine-readable form: `tools/research/evidence_policy.json`; recogniser: `tools/research/evidence_policy.py`.

**Accepted validation methods** (pre-declared tests, reproducible from hashed evidence): independent historical holdout; public-dataset comparison; cross-site (leave-lakes/years-out) transfer; model intercomparison; literature synthesis (graded by directness, never validation by itself); reproducible analysis; retrospective outcome replay (including owner-supplied logs if they exist). No accuracy is fabricated: an unvalidated item stays visibly unvalidated, ABSTAIN is still counted, and protected sealed holdouts and approval gates are unchanged.

## What changed

| Layer | Before | After |
|---|---|---|
| Gap lists (8 Brains + `brains/_template`) | `humanOrFieldValidationRequired.required: true` for field items; stop conditions "when the owner declines the field campaign" | `required: false`, `fieldDataRole: OPTIONAL_EVIDENCE` (schema `contracts/schemas/research-gaps.schema.json`); stop conditions end on evidence, never on owner field work |
| FISH-VAL-001 | "no species rule compared with a field outcome" | graded by independent historical/public evidence (LTRM electrofishing, ichthyoplankton, literature); capability `predictionFitness` is measured from decisive historical tests |
| WIND-VAL-001/002 | 24 site-nights / 36 observer classes at real banks | pre-declared concordance against public historical wind/wave records (>= 40 / >= 60 records); no owner observations |
| WIND-EVI-001 | owner dock anemometer | land-to-water factor from public over-water series and literature |
| DEPTH-VAL-001 | on-water depth observations | comparison with dated USACE eHydro soundings and gauge records; old field plan kept as an optional extension |
| Wind candidate scoreboard | dimensions 6-7 (40 pts) only from field holdout certification | **rubric v2** (`scoreboard.py --rubric v2`): same weights and curves, credited by any pre-declared accepted method; v1 stays the default and the frozen score log is untouched |
| Research automation | field needs became `BLOCKED_EXTERNAL` owner actions | such blockers are recorded as `optionalData` / `OPTIONAL_OWNER_DATA` and never change a gap status; existing ledgers are migrated in place, records preserved; agent briefs forbid proposing field collection |
| Depth score proposal, Fish readiness gate | "field validation" gates | worded as validation by an accepted evidence method (Fish gate renamed `independentEvidenceValidation`) |

## Audit of the eight Brains (equivalent dependencies)

| Brain | Field dependency found | Disposition |
|---|---|---|
| Fish | FISH-VAL-001; readiness gate `fieldValidation`; `NEEDS_FIELD_OBSERVATIONS` blocker class and `*_NOT_FIELD_VALIDATED` confidence statuses in `capability_eval.py`; `validation_log.py` (ingests structured observations) | gap + gate reworded; ingestion kept as optional evidence; confidence status strings are descriptive and are a **runtime contract change left for an approved release** (listed below) |
| Wind | WIND-VAL-001/002, WIND-EVI-001, scoreboard dims 6-7 and cap rules, field tooling (`field_run`, `fieldops`, `field_qa`) | gaps reworded, rubric v2 added; field tooling kept as an optional evidence path |
| Depth | DEPTH-VAL-001, `field_validation.py` prereg, score-proposal `fieldTruth` gate | gap reworded, prereg kept as optional, gate wording changed |
| Water Clarity | CLARITY-VAL-001 "field clarity observations" | stop condition ends on a promotion decision and historical Secchi/turbidity records |
| Lake, Water Temperature, Vegetation, Sector Intelligence | stop conditions mentioning field outcomes; VEG-VAL-001 "fresh truth ... or field observations" | reworded to agency surveys / public records; the **sealed holdout guard and Level-4 protected truth are protected restrictions, not field testing, and are unchanged** |
| Template (future Brains) | `required: true, what: "Field confirmation by bowfishers"` | now `required: false`, `fieldDataRole: OPTIONAL_EVIDENCE`; charter note updated; a test requires every `brains/*/research/GAPS*.json` to comply |

## Still open (not field testing)
Runtime contract wording in Fish (`*_NOT_FIELD_VALIDATED` statuses, `fieldValidationStatus` schema field), the Wind certification dimensions 6-7 wording in the frozen authoritative score files (`docs/brains/scoring/frozen-scores.json`), and any promotion of rubric v2 to an official score all change authoritative contracts and need an approved release. Cortex standards: see `docs/cortex/CORTEX_GAPS.md` (proposed rule for Cortex, recorded here because Cortex is read-only from this repository).
