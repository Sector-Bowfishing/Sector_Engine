# Lake Brain binding review protocol (adoption work package A1)

Status: pack built 2026-10-13. **Binding review is NOT complete.** No binding is marked `REVIEWED` by this protocol's tooling; only the ingestion
of a human review result (below) can propose lake ids for that status, and the adoption work decides what to do with the proposal.

Purpose: let the product owner accept or reject the machine-verified level-source bindings (`binding-review-v1`, research thread `binding` +
`gaps`) with about an hour of checking instead of 300+ row reviews, while keeping the highest-risk rows under full review.
The rubric counts only REVIEWED bindings (`lake-brain-score-v1`), blocker `B-binding-001`, action `M-B02`.

Code: `jobs/lake-brain/review/` (`build_review_pack.py`, `ingest_review_result.py`, `review_stats.py`, `review_template.html`, `tests/`).
Pack output (not in Git; public-derived data only): `~/Desktop/Sector Handoffs/Sector Engine/Lake Brain Binding Review/`.

## 1. The canonical set (strict rows only)

Source table: `docs/research/lake-brain/data/verified_bindings_v2.csv` (research branch `docs/lake-brain-research`), joined to the wave-1 table
`Sector_Research_Data/lake-brain/binding/verified.csv`, the research probe records (`binding/candidates.csv`, `binding2/cand/*.jsonl`,
`binding2/probe_results_v2.json`), `binding/nid_links.csv`, the directory snapshot `directory_lakes_2026-10-13.json` and
`geometry/lake_geometry_flags.csv`.

| Step | Rule | Rows |
|---|---|---|
| Start | `wave` in {`w1`, `w2-v1`} and status `VERIFIED` or `VERIFIED_CORROBORATED` | 279 |
| Exclude (a) | Clinton Lake\|IL: its row relies on the v1.1 rule R8c | -1 |
| Exclude (b) | lakes whose only source is an undocumented operator web endpoint (`nipsco`, `njwsa`, `duke`, `wps-hydro`, `alliant`, `srp`, `cnppid`, `nppd`, `utahlake`, `aep`, `eccc`, `mncsg`); present in the strict set: Lake Shafer IN, Round Valley NJ, Lake Robinson SC, Castle Rock WI, Lake Wisconsin WI | -5 |
| Exclude (c) | any post-hoc promotion: the wave-1 row must itself be `VERIFIED`/`VERIFIED_CORROBORATED` in `verified.csv`. **Red Lake\|MN** was `VERIFIED_FLAG` in wave 1 and became `VERIFIED_CORROBORATED` only in wave 2 (second origin found later), so it is out of the strict set and is reviewed with the 57 flagged rows | -1 |
| Never used | the v1.1 extensions (`w2-v1.1`), `R7h` / `VERIFIED_ENVELOPE`, `STAGE_ONLY`, derived-stage rows | 0 |
| = strict | | 272 |
| Hold back | directory coordinate flagged `identity_risk` (6) or `off_water` (52) in `lake_geometry_flags.csv` (`point_flag`); listed in `held_back_coordinate_flags.csv` as "HELD - coordinate review pending"; **must not be promoted** | -58 |
| **Eligible** | | **214** |

Note: the strict count the research score used (273) still contained Red Lake; the 272 here excludes it as a post-hoc promotion.

## 2. Strata, allocation and the seeded draw

Stratum = provider x capability class (`DIRECT_OPERATOR_POOL` / `DIRECT_LAKE_GAUGE`). Allocation (`allocate()`): every stratum with <= 3 rows is taken
whole; larger strata get at least 2; the rest is proportional to size (largest remainder); the total is exactly 60. Draw: `random.Random(seed).sample` over
strata sorted by name and rows sorted by lake id, so the result does not depend on file order. **Seed 20261013.**

| Stratum | Eligible | Sampled |
|---|---|---|
| a2w \| DIRECT_OPERATOR_POOL | 78 | 20 |
| cwms \| DIRECT_OPERATOR_POOL | 44 | 11 |
| cwms-saw \| DIRECT_OPERATOR_POOL | 1 | 1 |
| nhdes \| DIRECT_LAKE_GAUGE | 1 | 1 |
| nwps \| DIRECT_LAKE_GAUGE | 22 | 6 |
| rise \| DIRECT_OPERATOR_POOL | 25 | 7 |
| sjrwmd \| DIRECT_LAKE_GAUGE | 3 | 3 |
| tva \| DIRECT_OPERATOR_POOL | 11 | 3 |
| usgs \| DIRECT_LAKE_GAUGE | 28 | 7 |
| usgs \| DIRECT_OPERATOR_POOL | 1 | 1 |
| **Total** | **214** | **60** |

Reproduce: `python jobs/lake-brain/review/build_review_pack.py --research-docs <research checkout>/docs/research/lake-brain --data-dir <Sector_Research_Data/lake-brain> --out <dir> --seed 20261013`.
`pack_manifest.json` records counts, strata, the seed and the SHA-256 of every input file.

## 3. What the reviewer sees (every row)

Lake name and state; proposed source in plain words (for example "USACE Access2Water - Kinzua") and source id (station / series / tsid); a link to the source's own
public page or data query; distance from the gauge to the lake outline (km; measured to the centre point where a lake has no outline polygon); lake name and
station name side by side with the similarity; the level read at the 2026-10-13 probe, its observation time and age, and the 30-day median; the directory full
pool with its confidence, the level now minus full pool and the 30-day median minus full pool (the figure rule R7 tested); the independent second source (provider
and id, its level, the difference in ft) when one exists, plus other copies that agree but are not independent; R1 to R9 as PASS / FAIL / FLAG / n-a with a one-line
plain-English meaning; NID dam id and name (a weak candidate is labelled as such); years of public history; the lake's latitude/longitude with map links
(and the gauge's); and the computer's PASS / FLAG recommendation with its reasons.

R1 position (<= 1.5 km of the outline), R2 identity (name similarity >= 0.5, or inside the outline), R3 not a trap (no tailwater/river/well gauge), R4 state, R5
unique (no better-matching lake claims the gauge), R6 live (< 72 h, daily feeds < 192 h), R7 level (30-day median within -25..+8 ft of full pool; the flagged tier
allows deep drawdown or an uncertain full pool), R8 datum identified, R9 an independent origin agrees within 2 ft. R9 is `n-a` when no second origin exists (most lakes).

### Recommendation heuristic (conservative; a hint, never a decision)

FLAG when any hard concern holds, or two or more smaller ones:
- hard: a rule fails; the names differ (similarity < 0.5 and no station-name containment) with no independent source; the level (now or 30-day median, worst case) is >= 10 ft
  from the directory full pool, or more than 3 ft above it, with no independent source; for the flagged-57 rows, a level more than 3 ft from full pool or a name/position match that
  is not strong (similarity < 0.6 or > 500 m).
- smaller: partial name match (0.5-0.7); gauge > 300 m from the outline; river/creek/outlet-sounding station name (not for NWPS, whose names always read "River at Lake"); NOAA/NWS
  relay gauge; short or no history with no corroboration; level 5-10 ft from full pool with no corroboration; last reading > 24 h old (RISE excluded: documented ~2 day lag);
  directory full-pool confidence below high; no outline polygon.
- A station name that contains every word of the lake name (after expanding abbreviations such as Fk -> Fork) is treated as a name match; the note says so.
Single agency only is always shown as a note, never a flag by itself (159 of the 214 eligible rows have one agency).
Result on this pack: sample 48 PASS / 12 FLAG; flagged-57 10 PASS / 47 FLAG.

## 4. How to review

1. Open `binding_review_sample.html` (double-click; self-contained, no network, works in Safari and Chrome; progress is kept in the browser's localStorage, so use the same browser).
2. For each card open the gauge link and decide **Accept** (the gauge is this lake's level and the number is plausible), **Reject** (wrong gauge, wrong lake or a nonsense level), or **Unsure**.
   Unsure rows must be resolved before the batch can be accepted.
3. The sticky bar shows "N of 60 reviewed", rejects out of reviewed, the exact one-sided 95 % upper bound on the error rate (binomial; n = 60: 0 errors 4.9 %, 1 error 7.7 %, 2 errors 10.1 %)
   and the verdict.
4. Press **Download my review (CSV)** and hand over the file (columns: pack_id, lake_id, lake_name, stratum, computer_recommendation, decision, notes, decided_at_utc, reviewer, exported_at_utc).
5. Review the 57 flagged rows the same way in `binding_review_flagged57.html` (full review, no sampling; Accept / Reject / Unsure, summary counts only).

**Acceptance rule (from `LAKE_BRAIN_VALIDATION_STRATEGY` section 4):** accept the batch when there is at most 1 error in the 60 (95 % upper bound <= 7.7 %), every row decided.
Two or more rejects: the batch is not accepted and every stratum with a reject is reviewed in full. **Stratum rule:** a stratum containing any reject is flagged for full review and none of its
rows enter the proposed batch, even when the batch rule is met with exactly one reject.

## 5. The wave-1 flagged rows (57)

All 57 rows with `bindingStatus == VERIFIED_FLAG` in the wave-1 table (deep drawdown or low-confidence full pool, single origin) are reviewed in full. Each card also shows what later waves did,
labelled **"post-hoc, not counted"**: 44 promoted by the post-hoc R7h history-envelope rule, 1 (Red Lake) promoted by a second origin found later, 12 still flagged; where later waves re-pointed the lake to a
different gauge that is stated. This is background only; it never makes a row acceptable. The directory-coordinate flag is shown on each card where it applies.

## 6. Ingestion

`python jobs/lake-brain/review/ingest_review_result.py --review-csv <export.csv> [--flagged-csv <export57.csv>] --pack-dir <pack dir>` (dry run) and the same with `--write`.

- Validates the header, the `pack_id` (an export from another pack is refused), every lake id against the pack, duplicates and decision values; any error aborts with exit code 2 and writes nothing.
- Computes reviewed count (accept + reject), rejects, the exact upper bound, the verdict (`ACCEPT_BATCH`, `REJECT_BATCH`, `INCOMPLETE`) and the per-stratum table with full-review flags.
- With `--write`: `jobs/lake-brain/data/binding_review_result.json` (always) and `jobs/lake-brain/data/accepted_batch.json` (a JSON list of lake ids: **empty unless the rule is met**). When met, the list is the
  eligible strict population in strata without a reject, minus rejected rows; it never contains held-back coordinate-flagged lakes, the flagged-57, or any post-hoc row (enforced in code and tested).
- `accepted_batch.json` must not be committed with ids until the review is actually done; the repository currently has none.
- The flagged-57 export is summarised in the result (accepted / rejected / unsure / pending ids) and never enters the batch.
- Nothing is written to a production system and nothing is marked REVIEWED by the script.

Tests: `python -m pytest jobs/lake-brain/review` (synthetic pack and exports: pass, 1 reject, 2 rejects, unsure/pending, missing rows, wrong pack, unknown / held / duplicate ids, tampered population,
flagged export, allocation rules, seed determinism, exact bound reference values).

## 7. Limits

- Levels are a one-day snapshot (2026-10-13); links open live data. A reviewer judges identity and plausibility, not the exact number.
- Machine-verified is not reviewed; 0 errors in 60 is "no error found", with a 95 % upper bound of 4.9 %, not a measured 0 %.
- The 58 held-back lakes (52 off-water, 6 identity-risk directory points) and the 57 flagged rows are outside the batch whatever the sample says.
- The recommendation is a triage hint written before the review; it must not be tuned after seeing decisions.
