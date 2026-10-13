# Vegetation Brain — Maturity re-evaluation (2026-10-14)

**RESEARCH maturity, NOT an official score.** Vegetation has no `/scores/vegetation`; displayed score is **not established**. Computed by `python -m vegetation_brain report` (`maturity.py`; judgment inputs cite evidence files and `check_increase` refused any increase without new existing evidence).

## 1. Score report
| | Value |
|---|---|
| **Starting (research campaign)** | 2.4 (hand estimate); **2.32** as recomputed by the code with strict computed coverage (coverage 0) |
| **Ending (this cycle)** | **2.70** |
| Displayed (official) | **none** (`scoreStatus: NOT_ESTABLISHED`) |
| Underlying / computed | 2.70 |
| Production policy | overall ≥ 8.0 and critical ≥ 7.5: **not met**. Critical below 7.5: authority, spatial, presence, validation, provenance |
| Active gates / caps | `NOT_VALIDATED` cap 3.0 (proposed Score v1); no validation gate PASSED |

## 2. Dimensions that moved
| Dimension | Before → After | Why (evidence) |
|---|---|---|
| Source authority | 3.5 → **4.0** | UMN Minnesota CC0 dataset obtained (1,520 lakes); SFWMD littoral polygons open; UMRS 2020 schema confirmed (`validation/09`, `10`) |
| Spatial accuracy | 2.0 → **2.5** | canonical registry geometry adopted (no private polygon library); shore band measured (≈30 % of cells SHORE_ADJACENT; 49–54 % of mapped beds sit there); but registry polygon excludes ≈80 % of Okeechobee's mapped marsh and duplicates Toho (`validation/06`, `10`, fleet observability) |
| Presence accuracy | 3.0 → **2.5 (down)** | the shipped V1/v0.2 module failed every lake-level gate on held-out lakes: NLA AUC 0.72–0.77, Spearman ≤ 0.24, Keystone false flags 11–12 %, UMN recall 4–14 %, FWC recall 0.11 (`validation/11`, `12`) |
| Seasonality | 2.0 → **2.5** | 8-lake multi-year back-test: lake climatology 0.56 vs calendar 0.18, but only +6 over a most-common-state guess → gate (A2) **not passed**; observability by month measured (`validation/08`) |
| Validation | 3.0 → **4.0** | pre-registration frozen with amendments A1–A5; gates coded and pinned to the document; 5 independent truth families scored with a dev/test split and a one-shot TEST; failures kept on record |
| Confidence & provenance | 3.0 → **5.0** | state contract implemented and tested: evidence kind, scene ids, age, refusal reasons, potentialOnly, validation cap on confidence; confidence still uncalibrated (`VEGETATION_STATE_CONTRACT.md`) |

## 3. Did not move
Coverage (0 lakes observed in a fleet shadow run) · Density (1.0, gate not exposed) · Submerged (1.0, not observable) · Scalability (4.0: cost finding offsets the gain — a 5 km window read costs ≈ 7.6 MB/scene because COGs are tiled 1024², and only 30–52 % of clear scenes pass acceptance).

## 4. Capability that improved without a score change
Observer reachability: accepted passes on Snohomish went 0/5 → 5/5 lakes and NLA lakes with an accepted pass 29 → 38 of 47 (V1 → v0.2); the dark-water refusal fell from 40–58 % of cells to 0.1 %. This is real capability but the lake-level gates did not move, so the score does not credit it.

## 5. Next legitimate score movers
1. Fresh truth lakes with ≥ 30 interior floating-leaf/emergent positives (EXTERNAL SOURCE: TVA/TPWD/WI/FWC BioVolume) → unlocks gates (a), (e) and honest presence scoring.
2. Co-located truth for gate (c) (NLA station-level, or agency observations) → VALIDATION.
3. v0.3 BLOOM_AMBIGUOUS fix needs a fresh holdout before it earns anything.
4. Truth-backed coverage: a fleet shadow run on the pilot lakes (IMPLEMENTATION, cheap) → coverage 0 → >0.

## 6. SCORE DIMENSION EXHAUSTION MATRIX (every dimension < 7.5)
| Dimension | Score | Product value | Work this session | Result | More desk work? | Real blocker (category) |
|---|---:|---|---|---|---|---|
| Source authority | 4.0 | High: a bowfisher trusts agency maps more than a satellite guess | Mapped sources; downloaded NLA, FWC, UMN, UMR CSV; found SFWMD open polygons; drafted requests | 5 truth families in hand; big-reservoir truth (TVA, TPWD) still request-only | **No** (requests are drafted; sending is Michael's) | EXTERNAL SOURCE; MICHAEL DECISION (send requests) |
| Spatial accuracy | 2.5 | High: "which area/bank" | Canonical registry tiers (476/83/33/29); measured shore band; found registry polygon issues | Interior-only claims; shore-band beds (≈half of mapped beds) unclaimed; Okeechobee marsh outside polygon | **No** (geometry is Lake Brain's) | UPSTREAM BRAIN (Lake geometry: Okeechobee littoral, Toho duplicate); VALIDATION (registration test) |
| Presence accuracy | 2.5 | High | Production-code scoring, V1, v0.2 dev/test, NLA, UMN, SFWMD, UMR Pool 5 | V0.2 fails lake-level gates; recall low on thin/shore/presence-only truth | **Limited**: v0.3 fix is implemented but its real-data test needs fresh holdout lakes | VALIDATION (no fresh holdout); EXTERNAL SOURCE (more floating-leaf truth) |
| Density usefulness | 1.0 | Medium: "how thick" | Gate coded (kappa ≥ 0.40, within-one ≥ 0.90); density withheld | Not exposed; counts only | **No** (no density truth) | VALIDATION; EXTERNAL SOURCE |
| Seasonality | 2.5 | Medium–High: "when" | 8-lake back-test; baselines strengthened (A2) | Gate not passed; observability gaps up to 100+ days in winter | **No** (more lakes = more imagery cost; TX/Plains/West uncovered) | TIME / SEASON; VALIDATION |
| Submerged detection | 1.0 | High but unattainable by satellite | Tested indices, ML, sonar lake-level, clarity; potentialOnly design | Not observable; FWC BioVolume rasters unavailable | **No** | EXTERNAL SOURCE (FWC rasters); UPSTREAM BRAIN (Depth, Clarity) |
| Validation | 4.0 | High | Pre-registration, amendments, code gates, dev/test split, 7 scoring runs | Honest failures; no gate PASS except literal (b) | **No** | VALIDATION (truth); FIELD (bowfisher/sonar truth) |
| Confidence & provenance | 5.0 | High: "how confident Sector is" | State contract, refusals, evidence kinds, validation cap | Implemented in shadow; confidence uncalibrated | **Yes (small)**: confidence reliability needs truth; nothing else | VALIDATION |
| Coverage (computed) | 0 | Medium | Fleet manifest tiers; no shadow run | 0 lakes with observation | **Yes**: run the offline observer on pilot lakes (cache-only/cheap) | IMPLEMENTATION (orchestration not built; cost review) |
| Scalability | 4.0 | Medium: cost | Measured COG read cost; pure offline observer; dry-run publisher | Per-scene read cost and 30–52 % acceptance make a fleet daily run expensive | **No** until Clarity's existing scene reads can be shared | UPSTREAM BRAIN (Clarity pipeline reuse); IMPLEMENTATION |

**Is independent desk work exhausted?** For the *rubric dimensions*, yes: each remaining path needs truth data (EXTERNAL SOURCE/FIELD), an upstream Brain, or Michael's decision. Two cheap implementation items remain and are listed in the handoff (pilot shadow run; contract fixtures), but neither moves a critical dimension.

## 7. Rubric/product mismatch (proposal only; rubric NOT changed)
See `VEGETATION_PRODUCTION_READINESS_MATRIX.md` §4.
