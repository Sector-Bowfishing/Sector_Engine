# Lake Brain research, Track 8: species presence (bowfishing)

Thread `species`, 2026-10-13. Research only: no deploy, no write to any RTDB or bucket, GET-only. Public-safe: aggregates and method only. No presence row, lake-by-species cell or private file content is copied here. Customer fish labels are unchanged (Sector species ids, freshwater only).

Machine-readable twin: `docs/research/lake-brain/data/presence_sources_summary.json`. Reproduce with `research/lake-brain/presence_evidence_probe.py`. Ledger: `docs/research/lake-brain/ledger/species.jsonl` (sources S-species-001..038, blockers B-species-001..007, actions M-species-01..04). Bulk data lives only in `Sector_Research_Data/lake-brain/species/` (about 930 MB, nothing in Git).

## 1. Answers in one page

| Question | Answer |
|---|---|
| What does production say today? | 12 species (5 carp, 3 buffalo, 4 gar), 621 lakes, 7,452 rows, release `lake-presence-2026-10-12.1`. 68 % of rows are `unknown` and are not written. 529 lakes have at least one species with a state, 287 have at least one `established`/`reported`/`stocked`, 92 have nothing. |
| Is it observed or inferred? | Both. 897 of 2,349 stated rows are tier T2 (lake-level record), 71 are T3/T4, and 1,381 (59 %) are T5 `inRangeUnconfirmed`, a state-level range prior ("range is state-level only" on 1,030 rows). |
| Can public machine-readable sources add lake-level evidence? | Yes. NAS + GBIF (iNaturalist, museums, NAS, MARIS) + WQP + MidFish give at least one in-waterbody record of a target species for 387 of 621 lakes (62 %) for the 12 species, 398 (64 %) when bowfin and drum are included; 297 lakes have one from 2010 on. |
| What is left? | 126 lakes have only a HUC8-level occurrence, 108 have nothing. For gars and buffalo the HUC8 prior is weak (only buffalo, grass, bighead and silver carp are in the USGS coarse-range table). |
| State agencies? | Only Minnesota (LakeFinder JSON) and Indiana (Data Hub CSV) publish per-waterbody species tables. 15 of 17 bowfishing states do not (verdicts in section 5). They are not needed for coverage: 189 of 214 lakes in the 17 states already have a public in-waterbody record. |
| Does the current release agree with independent records? | Mostly, but it under-uses them. Of 956 (lake, species) pairs with an independent in-waterbody record, 43 are `unknown` and 158 are only `inRangeUnconfirmed`. 113 pairs labelled `historical` have an independent record from 2015 on. |
| Does better presence move the Lake Brain score? | No, not directly (section 8). It improves Sector Intelligence input quality and the beta-readiness `NO_SPECIES_PRESENCE` warning. |

## 2. Audit of current presence

### 2.1 Contract and flow
- Data is private: built in the private research repo, stored at `gs://sector-lake-brain/presence/` (`latest.json` pointer: version `lake-presence-2026-10-12.1`, 7,452 rows, FNV-1a fingerprint, release file 2.5 MB).
- `Sources/SectorEngine/LakeBrain/LakeSpeciesPresence.swift` only validates the bundle (schema, snake_case species, directory lake ids, no duplicates, vocabulary, fingerprint) and publishes `/lakes/{k}/speciesPresence/{speciesId}`. `unknown` rows are not written ("absent means unknown or not assessed").
- Vocabulary (`LakePresenceState`, verbatim from research): `established`, `reported`, `stocked`, `inRangeUnconfirmed`, `historical`, `failed/eradicated`, `unknown`.
- Record fields: `presenceState`, `confidence` (high/medium/low/none), `nativeStatus` (native, native-state, introduced, extirpated-state, unknown), `sourceTier` (T2, T3, T4, T5), `latestRecord` (year), `dataGaps`, `discrepancyIds`, `researchVersion`.
- Source artifacts: carp, buffalo and gar presence matrices (phases 2, 3, 4) plus the Biological Brain canonical lake overrides.
- Surfacing: profile `speciesPresenceSummary` = `{assessedSpecies:12, recordCount, byState (with unknown counted), researchVersion, ref}`. Sector Intelligence (`jobs/sector-intelligence-brain/evaluation.py::normalize_biological`) reads all published rows for the pilot lakes, joins `/species/{id}` knowledge, and reports `speciesCount`, `knowledgeMedian`, and a degraded flag when knowledge is missing or immature.
- The "which states count as relevant" policy is still an open decision (Biological Brain integration section 10). Today every written state, including `historical` and `inRangeUnconfirmed`, is counted as a "present species" by Intelligence.

### 2.2 Aggregates (all 621 lakes)
Rows: unknown 5,103; inRangeUnconfirmed 1,381; historical 433; established 424; reported 79; stocked 22; failed/eradicated 10.

| Tier | Rows | Meaning inferred from state mix |
|---|---|---|
| T2 | 897 | lake-level record (established 402, historical 420, reported 48, stocked 21, failed 6) |
| T3 | 27 | lake-level, other source class |
| T4 | 44 | lake-level, other source class |
| T5 | 1,381 | all `inRangeUnconfirmed`, state-level range |
| none | 5,103 | `unknown` |

The tier legend lives in the private repo and could not be read (B-species-001); meanings above are inferred.

`latestRecord` is present on 941 rows: min 1905, median 2010, max 2026; 373 rows are 2015 or later and 205 are before 1990. 27 stated non-range rows have no year. The release is one day old (built 2026-10-12), but 60 % of the dated evidence is older than 2015.

Data-gap phrases on stated rows: no abundance (2,349), single or no independent source (1,894), species ID unverified (1,557), no lake-level species record (1,122), range is state-level only (1,030).

Per species (rows):

| species | established | reported | stocked | historical | failed/erad | inRangeUnconfirmed | unknown |
|---|---|---|---|---|---|---|---|
| common_carp | 213 | 25 | 0 | 87 | 1 | 133 | 162 |
| grass_carp | 30 | 19 | 22 | 29 | 4 | 77 | 440 |
| bighead_carp | 25 | 7 | 0 | 18 | 2 | 20 | 549 |
| silver_carp | 17 | 13 | 0 | 12 | 0 | 23 | 556 |
| black_carp | 6 | 1 | 0 | 2 | 0 | 6 | 606 |
| smallmouth_buffalo | 19 | 2 | 0 | 56 | 1 | 140 | 403 |
| bigmouth_buffalo | 16 | 4 | 0 | 55 | 0 | 101 | 445 |
| black_buffalo | 6 | 0 | 0 | 31 | 1 | 95 | 488 |
| alligator_gar | 7 | 0 | 0 | 9 | 1 | 138 | 466 |
| longnose_gar | 44 | 5 | 0 | 72 | 0 | 283 | 217 |
| shortnose_gar | 9 | 1 | 0 | 26 | 0 | 211 | 374 |
| spotted_gar | 32 | 2 | 0 | 36 | 0 | 154 | 397 |

### 2.3 Pilot lakes (published `/lakes/*/speciesPresence`, aggregate)
Non-unknown species per pilot lake, by state:

| Lake | established | reported | stocked | historical | inRangeUnconfirmed |
|---|---|---|---|---|---|
| Guntersville, AL | 3 | 2 | 0 | 4 | 1 |
| Wheeler, AL | 4 | 0 | 1 | 3 | 1 |
| Wilson, AL | 1 | 2 | 0 | 4 | 3 |
| Pickwick Lake, TN | 3 | 1 | 0 | 4 | 3 |
| Lake Hartwell, SC | 2 | 0 | 0 | 0 | 1 |

Qualitatively: the Alabama and Tennessee reservoirs carry established carp and gar and a long `historical` tail for buffalo; on Guntersville bighead and silver carp are `reported` at T4. Hartwell has only 3 stated species, which reflects thin public data (section 7 shows only 2 species with an independent record there). On Guntersville the Biological Brain discrepancies DISC-001/002/003 (grass carp, smallmouth buffalo, bigmouth/black buffalo) all concern `historical` labels versus the shipping app.

### 2.4 Methodological weaknesses
1. State-level range prior is 59 % of stated rows. `inRangeUnconfirmed` says "the species occurs somewhere in this state", not that it is in this lake. For gars and buffalo it is the dominant state (e.g. longnose gar 283 of 404 stated rows).
2. `historical` mixes "old record only" with "gone". 433 rows; 347 have an independent in-waterbody record, 113 of them from 2015 on. Without a recency rule, `historical` mislabels species that are being photographed in the lake today.
3. `unknown` is 68 % and indistinguishable from "not looked at". There is no `notDetected` evidence even where an agency survey exists.
4. Bowfin and freshwater drum are bowfishing targets and exist in the Biological Brain (`/species` has 29 entries including both), but are not among the 12 assessed presence species. Independent records exist in 79 and 146 lakes (B-species-003, M-species-01).
5. Duplicated evidence: NAS, MARIS and museum records reach GBIF as well, so "single or no independent source" is hard to judge without tracking source families.
6. No abundance anywhere (2,349 of 2,349 stated rows), so presence cannot tell a bowfisher whether shooting is worthwhile, only whether the species is on the list.
7. The Intelligence consumer counts every state as "present" and takes the knowledge median over all rows, so `historical` and range-only species dilute the median.

## 3. Sources tested live (2026-10-13)

| Source | Result | Per-lake use |
|---|---|---|
| USGS NAS API v2 `/occurrence/search` | works, 5,000 per page, no key. Downloaded 85,739 records for 13 speciesIDs (common carp 62,026; silver 11,155; grass 6,168; bighead 3,448; black 1,474; smallmouth buffalo 590; bigmouth 362; black buffalo 13; alligator gar 17; shortnose gar 44; spotted gar 21; bowfin 118; drum 303). Longnose gar has no NAS species (no non-native record). Fields carry `status` (established, stocked, failed, ...), `latLongAccuracy`, HUC8/10/12. | 300 lakes have a record in or within 500 m of the polygon. |
| GBIF occurrence API | works, one bbox request per lake with 14 `taxonKey` values, 26,120 records over 621 lakes. Datasets: iNaturalist research grade (CC BY-NC), USGS NAS (CC0), MARIS fish (CC BY), Fishes of Texas, UMMZ and other museums (CC0/CC BY). 93 % of records have no coordinate uncertainty or <=100 m. | iNaturalist 282 lakes, museum 181, MARIS 73, other 21. |
| EPA/USGS Water Quality Portal | Station query per taxon works. Lake/reservoir sites with fish results: common carp 824, smallmouth buffalo 99, drum 75, bigmouth buffalo 30, bowfin 30, spotted gar 5, grass carp 5, longnose gar 4. | 122 lakes (common carp 100). |
| MidFish (USGS P1337ZQC, 280 MB parquet, 7 states) | IL and MI files hold only 8 gamefish; IA, IN, MN, SD, WI carry carp, buffalo, gar, bowfin, drum. | 74 directory lakes matched to a surveyed lake; 50 with a target species. |
| USGS coarse range maps HUC8 v2.0 (257 species) | usable, but only for buffalo x3, grass, bighead and silver carp. Excludes common and black carp, all gars, bowfin, drum. | HUC8 prior for 6 of 14 species. |
| Native Ranges of Freshwater Fishes of N. America (Daniel and Neilson) | would fill the gaps, but is a 10.3 GB `Data.zip` behind the ScienceBase manager (no HTTP range, HTML returned). Not obtained. | LEAD (B-species-002). |
| NatureServe Explorer API | works without a key (POST `speciesSearch`), returns state-level native/exotic and ranks. | State-level prior only (equals current T5). |
| USGS WBD ArcGIS layer 4 | resolved HUC8 for 621 of 621 lakes. | Join key. |
| IUCN API v4 | 403 without a token; no added value (all Least Concern). DEAD_END. | none |
| FishNet2, iDigBio, FishBase mirror, direct iNaturalist API | FishNet2 is a JS portal, iDigBio probe returned 0, FishBase mirror unreachable, iNaturalist direct duplicates GBIF. DEAD_END. | none |
| LAGOS-US, StreamCat/LakeCat | no fish-presence module; covariates only. | none |

Politeness: 0.25 to 1.5 s between requests, one worker, descriptive User-Agent.

## 4. Coverage estimate for the 621 lakes

Lakes with an independent in-waterbody record (polygon +500 m; 22 lakes without a polygon use a 1 km radius), counted by distinct source family (NAS, MARIS, iNaturalist, museum, WQP, MidFish):

| Species group | in-waterbody record | 2010 or later | HUC8 occurrence only | no evidence |
|---|---|---|---|---|
| 12 assessed species | 387 (62 %) | 297 | 126 | 108 |
| 12 + bowfin + drum | 398 (64 %) | 315 | 118 | 105 |
| 5 carp | 363 | 257 | 142 | 116 |
| 3 buffalo | 118 | 76 | 118 | 385 |
| 4 gar | 162 | 129 | 5 | 454 |
| bowfin + drum | 193 | 146 | 48 | 380 |

Distinct source families per lake (any of the 14 species): 0 families 223 lakes, 1 family 80, 2 families 112, 3 or more 206.

Per species:

| species | in-waterbody lakes | HUC-only lakes | main sources (lakes) |
|---|---|---|---|
| common_carp | 347 | 139 | NAS 267, iNat 197, museum 111, WQP 100, MARIS 70, MidFish 43 |
| grass_carp | 79 | 172 | NAS 72, museum 27, iNat 19 |
| bighead_carp | 37 | 36 | NAS 36, iNat 7, museum 6 |
| silver_carp | 35 | 44 | NAS 34, iNat 12, museum 5 |
| black_carp | 5 | 9 | NAS 5 |
| smallmouth_buffalo | 89 | 126 | museum 59, iNat 37, WQP 12, MidFish 11, NAS 10 |
| bigmouth_buffalo | 79 | 99 | museum 41, iNat 28, MidFish 23, MARIS 11, NAS 9 |
| black_buffalo | 33 | 93 | museum 22, iNat 8, NAS 3 |
| alligator_gar | 13 | 0 | museum 11, iNat 6 |
| longnose_gar | 129 | 0 | iNat 85, museum 69, MARIS 22, MidFish 12 |
| shortnose_gar | 41 | 7 | iNat 21, museum 20, MidFish 11 |
| spotted_gar | 69 | 0 | museum 43, iNat 40, MARIS 8 |
| bowfin | 79 | 38 | museum 36, iNat 30, MARIS 21, MidFish 17 |
| freshwater_drum | 146 | 20 | iNat 108, museum 69, MidFish 26, WQP 16 |

Caveats: (a) a polygon +500 m catches tailwater and adjacent river records; (b) GBIF text and iNaturalist coordinates can be obscured, a 1 km uncertainty cap was applied; (c) NAS "established" literature records are older than iNaturalist; (d) HUC-only counts are zero for gars because no machine-readable HUC8 prior was obtained for them (B-species-002); (e) these numbers are the ceiling of what these public sources can add, not what the private release already contains.

Bowfishing states (TX OK AR AL TN KY MO IL IN IA WI MN MS LA GA SC NC): 214 of 621 lakes, 189 (88 %) have an in-waterbody record of at least one of the 12 species. Weakest: MN 8 of 14, WI 10 of 13, SC 10 of 12, NC 10 of 12.

## 5. State agencies (17 bowfishing states)

All endpoints were tested live (HTTP status, field names). Samples in `species/other/states/<ST>/`.

| State | Verdict | What exists |
|---|---|---|
| MN | ACCEPTED | DNR LakeFinder `by_id`/`by_point` JSON with `fishSpecies` from the latest DNR lake survey (comma-joined string). Enumerate DOW ids via the `env_lakes_surveyed_by_mndnr` layer (4,383 polygons). Undocumented API, no terms found; `by_name` returns 403. On the 14 directory lakes: 11 resolved, 9 species lists (common carp 4, bowfin 7). |
| IN | ACCEPTED | Data Hub CKAN CSVs: `Fish_Surveys` (961 surveys, 373 waterbodies, 2010-2025), `Batch_Fish_Records` (species rows for 48 waterbodies), `Fish_Records` (aged fish, 54 MB). Licence blank. Directory: 4 of 14 lakes have species rows, 1 has a bowfishing target. |
| TX | LEAD | Per-waterbody stocking HTML (grass, bighead, common carp tracked), alligator gar harvest FeatureServer by waterbody (bowfishing is a harvest method), survey PDFs. No species feed. |
| IL | LEAD | iFish Illinois: 469 lake pages (sitemap, robots allow), narrative HTML, no data. |
| WI | LEAD | ArcGIS layers are gamefish, regulation and stocking only; lake pages list gamefish. MARIS (inside GBIF) is the only bulk fish source. |
| OK | LEAD | ODWC record-fish lakes layer (33 records) and survey PDFs. |
| KY | LEAD | Annual survey PDFs; lake layers have no species. |
| MO | LEAD | Narrative "fishing prospects" HTML; polygons only. |
| IA | DEAD_END | Power BI dashboard only. |
| AR, AL, TN, MS, LA, GA, SC, NC | DEAD_END | geometry/access points/gamefish narrative; AL host unresolvable; TN stocking PDFs 404. |

Cross-state: no state publishes absence or a machine-readable stocking list with grass carp. Stocking evidence (grass carp is the only bowfishing target that is stocked) needs per-state scraping (TX) or permits data; treat as a later enrichment.

## 6. Evidence-tier model

Principle: keep Sector's existing seven presence states and the customer labels verbatim. Add evidence families and a recency rule beneath them; never emit `absent`.

| Tier | Evidence class | Typical sources | Feeds state |
|---|---|---|---|
| E1 | Agency survey in the waterbody (standardized catch or species list) | MN LakeFinder, IN Data Hub, MidFish, MARIS, WQP/NLA | `established` if detected in a survey within 10 years or on two surveys; otherwise `reported`; older only -> `historical` |
| E2 | Stocking record | state stocking tables, NAS status `stocked` | `stocked` (a failed or eradicated stocking -> `failed/eradicated`) |
| E3 | Observed record in the waterbody | NAS (status established/collected), iNaturalist research grade, museum specimens | `established` if NAS status is established or three or more records over two or more years including one in 10 years; `reported` for a single recent record; `historical` if the newest record is older than 25 years |
| E4 | HUC8 occurrence (not in the waterbody) | NAS HUC8 field, USGS coarse range / Native Ranges tables | `inRangeUnconfirmed`, confidence low, `dataGaps` says "watershed occurrence only" |
| E5 | State or range prior | NatureServe state native/exotic, Page and Burr | `inRangeUnconfirmed`, confidence low (today's T5) |
| E6 | nothing | | `unknown` (not written) |

Confidence rule: high needs two source families and one record from the last 10 years; medium one family within 10 years or two older families; low for single old records and E4/E5. Source families (NAS, MARIS, iNaturalist, museum, WQP, MidFish, agency) are tracked as `evidenceFamilies` so GBIF-republished data is not counted twice. Thresholds (10 and 25 years, 3 records) are proposals to be validated, not facts.

Applied to the current release (public tiers computed here, not the private T-codes):

| Current state | none | HUC8 only | in-waterbody, older/undated | in-waterbody 2015+ |
|---|---|---|---|---|
| unknown (5,103) | 4,933 | 127 | 20 | 23 |
| inRangeUnconfirmed (1,381) | 734 | 489 | 39 | 119 |
| historical (433) | 55 | 31 | 234 | 113 |
| established (424) | 32 | 60 | 80 | 252 |
| reported (79) | 11 | 12 | 0 | 56 |
| stocked (22) | 0 | 2 | 16 | 4 |
| failed/eradicated (10) | 6 | 4 | 0 | 0 |

Reading: 119 + 23 + 20 pairs (162) could move up from range-only or unknown, and 113 `historical` pairs would flip to `reported`/`established`. About 55 `historical` and 32 `established` pairs have no public in-waterbody or HUC8 evidence, so they rest on the private matrix (literature) and should be reviewed, not removed.

## 7. Validation without field trips

### 7.1 Design
1. Independent-record check (run below): compare private states to in-waterbody records from sources that the private build did not necessarily use (current GBIF/iNaturalist, MARIS, WQP, MidFish). Metrics per species: recall of independent records (state in established/reported/stocked/historical/failed), corroboration rate of private observed states, `unknown`-with-record count, `historical`-with-recent-record count, independent record newer than private `latestRecord`.
2. Temporal hold-out (for the future pipeline): freeze records up to 2019, derive states, score against 2020-2026 detections. Report per species: share of later detections already `established`/`reported`/`inRangeUnconfirmed` (recall) and the `unknown` miss rate. Needs the build code, so only the design exists today.
3. Agency-survey truth: in states with survey tables (MN, IN, MidFish states), treat a surveyed lake as the denominator. Detection in survey = positive; non-detection = "not detected" only. Report recall and the count of private positives that a survey in the last 10 years failed to detect (a flag, not a false positive).
4. Spatial hold-out: remove one source family at a time (ablation) and measure how many states change; the families that change most are single points of failure.
5. Limits: all sources are presence-only, so precision of `unknown` and any absence claim cannot be tested. Public sources are partly the same inputs as the private build, so agreement overstates independence (B-species-005, B-species-006).

### 7.2 Results (aggregate, 7,452 pairs; 956 pairs have an independent in-waterbody record)
Private state for the 956 pairs: established 332, historical 347, inRangeUnconfirmed 158, reported 56, stocked 20, unknown 43.
- Recall of independent records (state in the evidence group): carp 84 to 100 %, gars 63 to 77 %, buffalo 65 to 76 %.
- Corroboration of private observed states (established/reported/stocked) by a public in-waterbody record: 408 of 525 (T2 361 of 471, T3 25 of 26, T4 22 of 28). The rest are literature-based and cannot be checked from public data.
- Independent record newer than the private `latestRecord` on a stated row: 256 pairs.

| species | independent pairs | had evidence state | range only | unknown | recall | private observed | corroborated |
|---|---|---|---|---|---|---|---|
| common_carp | 347 | 290 | 39 | 18 | 0.84 | 238 | 215 |
| grass_carp | 79 | 73 | 1 | 5 | 0.92 | 71 | 48 |
| bighead_carp | 37 | 33 | 3 | 1 | 0.89 | 32 | 24 |
| silver_carp | 35 | 33 | 1 | 1 | 0.94 | 30 | 22 |
| black_carp | 5 | 5 | 0 | 0 | 1.00 | 7 | 4 |
| smallmouth_buffalo | 89 | 58 | 26 | 5 | 0.65 | 21 | 11 |
| bigmouth_buffalo | 79 | 60 | 14 | 5 | 0.76 | 20 | 11 |
| black_buffalo | 33 | 22 | 5 | 6 | 0.67 | 6 | 1 |
| alligator_gar | 13 | 10 | 3 | 0 | 0.77 | 7 | 6 |
| longnose_gar | 129 | 96 | 33 | 0 | 0.74 | 49 | 37 |
| shortnose_gar | 41 | 26 | 14 | 1 | 0.63 | 10 | 6 |
| spotted_gar | 69 | 49 | 19 | 1 | 0.71 | 34 | 23 |

Pilot lakes (species with an independent in-waterbody record, and how the private release labels them): Guntersville 7 (3 established, 2 reported, 2 historical); Wheeler 8 (4 established, 1 stocked, 3 historical); Wilson 7 (1 established, 2 reported, 4 historical); Pickwick 8 (3 established, 1 reported, 3 historical, 1 range-only); Hartwell 2 (2 established). No pilot lake had an independent record for a species the private release labels `unknown`.

Agency cross-check, Minnesota (9 lakes with a LakeFinder species list), common carp: agency lists it on 4 lakes, all 4 are `established` in the private release; on the 5 lakes where the agency does not list it, the private release says `unknown` (2) or `inRangeUnconfirmed` (3), so no private positive is contradicted. The sample is small.

Conclusion: the private release is sound on its stated positives and weak where it is a range prior or `historical`. The measurable gain is for buffalo and gars (where 24 to 37 % of independent records are not reflected) and for recency.

## 8. Rubric relevance (`lake-brain-score-v1`)
`score_lake` (jobs/brain_platform/sector_brain_platform/scoring.py) has eight dimensions: sourceAuthority, operatorPlan, historyQuality, seasonalBaseline, trendQuality, floodDroughtContext, validation, coverage. None reads `speciesPresence`. Presence is not part of Lake Brain readiness (DISCOVERED/PROFILED/CALIBRATION) either. The Biological Brain rubric lists "lake presence (Lake Brain's)" under `cannotCount`. So presence improvements do not move the Lake Brain score, today or after any change in this document.

Indirect effects, none score-bearing:
- `beta-readiness-v1` warning `NO_SPECIES_PRESENCE` appears when Intelligence reports no presence for a lake. 92 lakes currently have no stated species; only 4 of them have any public in-waterbody record of the 12 species, so the warning would barely change (the rest are mostly lakes outside these species' ranges). It would affect beta readiness reporting only.
- Sector Intelligence: better states and `evidenceFamilies` allow confidence-weighted filtering ("present", "likely", "range only") instead of treating all rows as present species, and fix the knowledge median. Adding bowfin and drum would fill the `/species` entries that Intelligence currently never joins.
- If the team wants presence to count, a new dimension needs a pre-registered rubric version (not proposed here).

## 9. Recommendations
1. Adopt the E1-E6 model as an evidence layer in the private builder; keep Sector vocabulary and labels. Refresh monthly (GBIF per-lake, NAS incremental by year), annually for agency tables.
2. Add bowfin and freshwater drum to the assessed species (M-species-01).
3. Fix `historical`: only when the newest in-waterbody record is older than 25 years; recent records move it to `reported`/`established`.
4. Add the Intelligence presence policy (which states count) before using presence for customer-facing logic.
5. Get the Native Ranges HUC8 table or accept GBIF-derived HUC8 priors for gars (M-species-04).
6. Clear licensing: iNaturalist is CC BY-NC; keep only derived lake-by-species facts with source family, never raw rows, in product (M-species-03).

## 10. Blockers and Michael actions
| Id | Item | Priority |
|---|---|---|
| B-species-001 / M-species-02 | Private repo tier legend T2-T5 and state-derivation rules unreadable | medium |
| B-species-002 / M-species-04 | Native Ranges Data.zip (10.3 GB) not obtainable by API | low |
| B-species-003 / M-species-01 | Bowfin and drum not assessed | high |
| B-species-004 / M-species-03 | iNaturalist CC BY-NC and NAS/MN/IN terms | medium |
| B-species-005 | No absence data anywhere | medium |
| B-species-006 | Independence of validation | medium |
| B-species-007 | 15 of 17 states have no machine-readable species data | low |

## 11. Reproduce
```
cd research/lake-brain
python presence_evidence_probe.py audit | nas | gbif | wbd | wqp | midfish | coverage | validate | states | summary
```
`audit`, `validate` and `states` read the private release into memory with `gcloud storage cat` (needs read access) and write aggregates only. Outputs go to `Sector_Research_Data/lake-brain/species/`. `summary` writes the committed JSON. Add `--refresh` to `nas` to re-pull from the API (about 35 minutes because of common carp).
