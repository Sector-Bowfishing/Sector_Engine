# Biological Adoption Reconciliation

**Nothing in this document has been applied.** `Sources/SectorEngine/Engine/Config/SpeciesDatabase.swift` is **unchanged** (it drives customer-facing spawn-run windows and "where to look" copy, so every change needs Michael's approval). Evidence is cited by source identifier; the full ledger is private (`Sector_Research_Data/biological-brain/packets/` and `adoption/verification/`). Classification vocabulary: WRONG · TOO BROAD · UNSUPPORTED · REGIONALLY LIMITED · STILL DEFENSIBLE. Temperatures: 15 C = 59 F, 18 C = 64.4 F, 20 C = 68 F, 21.1 C = 70 F, 30 C = 86 F.

## A. Production table (`SpeciesDatabase.swift`)

### A1. Longnose gar: temperature (lines 187-191) → **PENDING REVIEW**
| | |
|---|---|
| CURRENT | `spawnMinF 68 / PeakF 72 / MaxF 77` (20.0 / 22.2 / 25.0 C); window south Apr-May, mid-north May-Jun |
| PROPOSED | min **64**, peak **67**, max unchanged 77 (single-peak struct; the literature gives a range 64-70 F). Windows unchanged |
| CLASS | Lower bound and peak TOO WARM; upper bound UNSUPPORTED either way |
| WHY | Literature spawn range is 17.8-21.1 C (64-70 F); production's whole band sits ~2-3 C warmer and its peak (72 F) is above the top of the literature range |
| EVIDENCE | Fishes of Texas compilation (citing Dean 1895; Netsch & Witt 1962) read in full; Outdoor Alabama account (May aggregations, lower Coosa River; quoting *Fishes of Alabama and the Mobile Basin*); McGrath et al. 2012 (York R., VA: spawn ~1 month, ended late June; two fish left the spawning ground at 29 C, n=2). No modern Southeast temperature measurement |
| CONFIDENCE | LOW-MEDIUM (old compilation is the only temperature source) |
| CUSTOMER IMPACT | spawn-run signal for longnose gar would start ~4 F cooler (earlier in spring) |
| INTELLIGENCE IMPACT | none: rule `LG-SPN-01` already carries the range 17.8-21.1 C |

### A2. Smallmouth buffalo: habitat wording (line 169) → **PROPOSE CORRECTION**
| | |
|---|---|
| CURRENT | "submerged vegetation in slightly faster water" |
| PROPOSED | "tailrace and slack pockets below dams, creek and tributary mouths, and shallow backwaters during the spring run" |
| CLASS | vegetation clause UNSUPPORTED; "faster water" PARTLY DEFENSIBLE; temperature band 57/63/70 F STILL DEFENSIBLE (gonad-inferred, never observed) |
| WHY | No source found ties spawning or staging to vegetation. Spring telemetry shows fish staging in low-velocity tailrace pockets; run to creek mouths after large rains |
| EVIDENCE | McKee 2019 (Claiborne L&D, 165 smallmouth, READ-ABSTRACT; spillway-inundation claim *unconfirmed*); Citico Creek counts and Wrenn 1968 (Guntersville/Wheeler gonad data) are profile-carried and not re-opened |
| CONFIDENCE | MEDIUM that vegetation is unsupported; LOW-MEDIUM for the replacement wording |
| CUSTOMER IMPACT | where-to-look copy for smallmouth buffalo on lakes where it is present |
| INTELLIGENCE IMPACT | rule `SB-HAB-01` (tailwater) is the only usable smallmouth rule; the rest are DRAFT |

### A3. Silver carp: habitat wording (line 220) → **PROPOSE CORRECTION**
| | |
|---|---|
| CURRENT | "warm slow backwaters where they surface-school" |
| PROPOSED | "river mouths, tributary approaches and tailwater edges on rising warm water; backwaters when the water is high" |
| CLASS | TOO BROAD (backwaters are conditional); spawn habitat UNSUPPORTED (spawning is in flowing river reaches); "surface-school" is anecdote |
| WHY | Backwater use rises with discharge and warmth; at low summer flow Illinois fish selected channel borders and avoided backwaters; spawn in 0.6-2.3 m/s current; Tennessee/Cumberland fish were found more at river mouths than dam faces |
| EVIDENCE | DeGrandchamp 2008 / Coulter 2017 (one Illinois 2004-05 program, counted as **one** stream); LaBrie & Wesner (James R., preprint); Milde 2025; Coulter & Goforth 2013 (Wabash); Belanger 2023 (lower Tennessee/Cumberland); USGS UMESC tailwater imagery; Gibson-Reinemer 2017 (spawn). Temperatures 64/72/86 F STILL DEFENSIBLE (≥18 C Illinois; NAS 18-30 C) |
| CONFIDENCE | MEDIUM |
| CUSTOMER IMPACT | where-to-look copy for silver carp |
| INTELLIGENCE IMPACT | rules `SC-HAB-01..04`, `SC-HYD-01/02`, all conditional on rising stage/discharge |
| ALSO | **Spawn timing on TVA pools is UNTESTED**: TVA/Southeast reservoirs show little or no reproduction. The window (Apr-Jul) describes river behaviour, not an expectation for Guntersville |

### A4. Bighead carp: habitat wording (line 225) → **PROPOSE CORRECTION (low priority)**
| | |
|---|---|
| CURRENT | "warm slow backwaters and side channels where they stage" |
| PROPOSED | same as A3 or remove the species-specific claim |
| CLASS | UNSUPPORTED at species level (evidence is pooled with silver carp); bighead are rare in Kentucky Lake (10 vs 737 silver) and absent from Barkley |
| EVIDENCE | Coulter 2017 (the only species-separated behaviour: evening backwater passages, one site); pooled Illinois studies; Ridgway & Bettoli 2017 |
| CONFIDENCE | LOW |
| CUSTOMER / INTELLIGENCE IMPACT | minimal / rules `BH-*` are LOW confidence |

### A5. Grass carp: habitat wording (line 216) → **PROPOSE CORRECTION**
| | |
|---|---|
| CURRENT | "warm (>70°F) slow backwaters and side channels where they stage" |
| PROPOSED | "submerged vegetation in coves, shoals and creek arms; tributary mouths on rising water from about 60 F in spring" |
| CLASS | ">70°F" UNSUPPORTED; backwaters PARTLY DEFENSIBLE (day-rest in one river); temperature min 56 F STILL DEFENSIBLE (ripe fish at 12.3 C); max 86 F TOO BROAD (observed 15.1-27.8 C) but evidence is insufficient to change it |
| WHY | Truman telemetry: run onset ~15 C (59 F), peak probability 16-24 C (61-75 F), 54% of movements on rising stage; strong vegetation association; winter fish stay in littoral water ≤3 m and feed |
| EVIDENCE | Hessler et al. 2023 (PLoS ONE; NAJFM winter, same 86-fish cohort, one stream); Weberg 2013 (Claytor); Bonjour et al. 2025 (Sandusky); ERDC 2012 synthesis. All verified at abstract or full-text level |
| CONFIDENCE | MEDIUM for vegetation; LOW for the run threshold (one reservoir cohort) |
| CUSTOMER IMPACT | where-to-look copy for grass carp |
| INTELLIGENCE IMPACT | rules `GC-HAB-01..03`, `GC-HYD-01`, `GC-TMP-01` |

### A6. Bowfin: southern spawn start (lines 192-196) → **PENDING REVIEW**
| | |
|---|---|
| CURRENT | `61 / 64 / 66` F (16 / 18 / 19 C); south Mar-May |
| PROPOSED | south window **Feb-May**; `spawnMinF` **57** |
| CLASS | REGIONALLY LIMITED: the band matches northern accounts; Gulf-state spawning begins earlier |
| EVIDENCE | Vermont F&W and Fishes of Texas compilation (16-19 C, northern); Alabama River male running milt at 14 C (57 F) in February 1990 (a single observation); southeastern Louisiana spawning late Feb-early Mar (Davis 2006, via compilation) |
| CONFIDENCE | LOW-MEDIUM (compilation + one observation) |
| CUSTOMER / INTELLIGENCE IMPACT | earlier southern spawn-run window for bowfin / no bowfin rules exist (bowfin is outside the Lake Brain's 12 assessed species) |

### A7. Channel catfish: temperature (lines 203-206) → **PROPOSE NARROW CORRECTION; earlier concern overstated**
| | |
|---|---|
| CURRENT | `75 / 80 / 85` F (24 / 27 / 29 C), south window May-Jul |
| PROPOSED | `70 / 77 / 80` F |
| CLASS | min and peak STILL DEFENSIBLE (slightly high); max 85 F TOO BROAD (a growth/feeding optimum, not a spawning temperature) |
| WHY | Independent verification found agency spawning figures: Missouri 75-80 F, South Carolina 70-80 F, Illinois 75 F, Kansas 74 F, Indiana mid-70s, New Jersey ~80 F; HSI onset ~21 C. 85 F is above every agency spawning figure found. The research campaign's statement that production "exceeds the research-supported range" was **overstated**: only the upper bound is off |
| CONFIDENCE | MEDIUM |
| CUSTOMER IMPACT | **none in practice**: `sightShootableSpawn:false` and `legalByDefault:.check` mean catfish never drives a spawn run |
| INTELLIGENCE IMPACT | none |

### A8. Spotted gar: temperature band (lines 182-186) → **PENDING REVIEW (new finding)**
| | |
|---|---|
| CURRENT | `70 / 75 / 79` F (21.1 / 23.9 / 26.1 C) |
| PROPOSED | min **68**, max **86** (20-30 C); peak unchanged |
| CLASS | upper bound TOO NARROW |
| EVIDENCE | Echelle & Riggs 1972 and Snedden et al. 1999 spawn range 20-30 C via Fishes of Texas / MNFI compilations; DFO 21-26 C is a Canadian figure not applicable to the Southeast |
| CONFIDENCE | LOW-MEDIUM |

### Checked, no change recommended
Alligator gar `68/73/86` F (20-30 C) STILL DEFENSIBLE; bigmouth buffalo `60/65/75` F consistent with unconfirmed 17-19 C (hold); freshwater drum `64/70/79` F consistent with ~18-26 C; common carp `59/65/77` F consistent with 15-28 C (upper bound 3 C narrow: minor, not proposed).

## B. Machine-side Biological claims (private bundle / research outputs)
| # | Claim | Finding | Action taken |
|---|---|---|---|
| B1 | Grass carp "feeding onset 10-16 C" (profile basis) | CONTRADICTED by Truman winter telemetry (full guts, littoral ≤3 m, three winters) | rule `GC-TMP-01` encodes winter feeding; profile text unchanged (private bundle, pending approval) |
| B2 | Channel catfish "feeding heaviest 75-85 F" (v1 basis) | UNSUPPORTED by any opened peer-reviewed source | no rules built for catfish |
| B3 | Spotted gar "a rise at ~15 C is needed; cold rises do not move fish" | the 15 C qualifier and cold-rise null are **not confirmed at abstract level** (Snedden 1999 abstract supports floodplain use in the flood pulse and rising activity with temperature and stage) | rule `SG-FLO-02` is DRAFT; `SG-FLO-01` carries no temperature qualifier |
| B4 | Bigmouth buffalo "17-19 C, 0.3-0.9 m, spawned in ~16% of years, 7.2 cm/d recession" | abstract confirms only the rapid-recession recruitment failure; all four numbers are full-text-unconfirmed | spawn and habitat rules are DRAFT; only `BM-FLO-01` (rapid recession) is usable |
| B5 | "Four independent silver carp flow datasets" (research summary) | the Illinois (DeGrandchamp 2008) and Swan Lake (Coulter 2017) papers come from the same 2004-05 tagged program | counted as **one** stream; three independent streams plus Wabash; rule confidence MEDIUM |
| B6 | Silver carp "TVA warm coves" winter claim | the quote is ADCNR (D. Armstrong), about electrofishing catch, not TVA; snippet-only | rule `SC-HAB-05` is DRAFT; attribute to ADCNR only |
| B7 | Longnose gar riffle-spawning "Mettee et al. 1996" | cited as Outdoor Alabama quoting the book; riffle spawning is the lower Coosa River | evidence entry reworded |
| B8 | Smallmouth buffalo "spillway passage when inundated" | inundation not confirmed | rule claims tailwater staging only |
| B9 | **Starting Biological score "≈3.46"** (research branch docs) | the live canonical score is **4.0**: my recomputation omitted the Intelligence-connection dimension (+0.5) | corrected below; correction note added to the research docs |
| B10 | tilapia TAFS 147(2):278 | VERIFIED: Henson, Aday & Rice 2018, *Trans. Am. Fish. Soc.* 147(2):278-286, doi 10.1002/tafs.10023 | cite with authors/DOI |
| B11 | Minor-species packets (9 packets) | 28 of 33 spot-checked source items VERIFIED; 5 PARTIAL (Stauffer 1988 mortality table detail; blue sucker "Feb-May" unsupported by its source; HSI record has no text; catfish spawn temp (A7); drum growth direction) | no minor-species rules built; corrections recorded in the private ledger |

## C. Corrected score baseline
| | Value | Basis |
|---|---:|---|
| **PUBLISHED** | **4.0** | live `/scores/biological-state`; Biological State NOT_STARTED gate cap 4.0 is exactly met (uncapped 4.0): registry 1.00 + coverage 1.40 + knowledgeDepth 0.20 + evidence 0.20 + contradictions 0.66 + **integration 0.50** |
| **IMPLEMENTATION-SUPPORTED** | **4.6** | candidate bundle `2026-10-13.1`: State derived IN_PROGRESS (+0.60); State gate lifted; 6.0 species-validation gate still binds |
| RESEARCH POTENTIAL (proposed species rows only) | uncapped 4.3, **capped 4.0** | median 1.0 → 2.5 (+0.30), but the State NOT_STARTED gate hides it |
| RESEARCH POTENTIAL + IMPLEMENTATION | 4.9 | |

The earlier "starting 3.46 / research-supported 3.76 / ceiling ≈4.0" figures were wrong by the omitted +0.5; the "ceiling" was already reached by the published score.
