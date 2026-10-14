# Biological species scorecard (READ-ONLY AUDIT; not an official Sector score)

Generated 2026-10-14T17:43:15+00:00. Official Biological score is untouched. **Species Maturity Audit Score** is derived for this analysis only: weights {'knowledgeDepth': 55, 'evidenceQuality': 15, 'responseCoverage': 20, 'regionalTransfer': 10}; UNKNOWN components are excluded and re-weighted (completeness shown). Review and field validation are shown beside it, never inside it. Existing Sector labels are preserved exactly. Lake coverage is shown as status only (per-lake presence stays out of the public repo).

## Executive summary
CURRENT CANONICAL BIOLOGICAL SCORE: **4.6**

| FRESHWATER | |
|---|---|
| Total | 28 registry rows |
| Assessed | 26 |
| Unassessed | 2 (tilapia unresolved, grouped suckers row) |
| Average (audit score) | 1.8 |
| Median | 0.8 |
| Lowest | american_shad 0.0, blue_sucker 0.0, gizzard_shad 0.0 |
| Missing from Biological | none of the fish Sector already defines; 6 candidates it does not define or lumps into a group (see below) |

| SALTWATER | |
|---|---|
| Total | 1 (striped mullet, provisional: GROUPING_REVIEW_REQUIRED) |
| Assessed | 1 |
| Unassessed | 0 |
| Average / Median | 0.1 / 0.1 |
| Lowest | striped_mullet 0.1 |
| Missing | Sector defines no other saltwater fish; future roadmap list below |

| CURRENT SCORE SET | |
|---|---|
| Total rows in the registry | 29 |
| Rows entering knowledgeDepth (ASSESSED) | 27 |
| Freshwater / Saltwater primary | 28 / 1 |
| Cross-habitat flagged (anadromous, catadromous, brackish, cross) | 5 (alligator gar, longnose gar, American shad, striped mullet, tilapia) |
| Unrated: ASSESSED rows with knowledge < 1.0 | 14 (of which 7 are exactly 0.0) |
| NOT_ASSESSED rows (excluded from the median) | 2 |

Universe: 29 registry rows = 27 in the score + 2 NOT_ASSESSED; 18 appear in the engine spawn table (all 18 have a Biological row); 12 are policy-assessed (the Lake Brain presence list); 9 have usable rules; 8 have at least one PROPOSED response band (9 species nodes carry a responseBands object; smallmouth buffalo's holds 0 bands); 0 reviewed; 0 validated; 10 DRAFT rules. Totals differ because the registry (29) is wider than the policy list (12), rules exist for 9, and two rows are intentionally NOT_ASSESSED. (The legacy `ruleCount` 48 on the common-carp row counts profile claims, not machine rules; machine rules = 11.)

## Freshwater species, highest to lowest score
| Sector Label | Scientific Name | Habitat Flag | In Sector registry | In Biological | In score | Presence / lake coverage | Resp. bands | Rules (usable/draft) | Evidence tier | Review | Validation | Regional transfer | Audit score | Species-v2 (canonical) | Score type | Biggest missing capability | Next action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Common carp | Cyprinus carpio | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 11/0 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 4.09/10 (0 transfer, 9 partial, 2 untested) | 6.9 | 7.0 | DERIVED_AUDIT | no human review | Reviewer decisions (packet ready), then first field validation |
| Spotted gar | Lepisosteus oculatus | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 7/1 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 4.29/10 (0 transfer, 6 partial, 1 untested) | 5.0 | 4.5 | DERIVED_AUDIT | response rules cover 3 of 5 condition families | Reviewer decisions; field validation (live-set candidate) |
| Grass carp | Ctenopharyngodon idella | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 7/1 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 0.71/10 (0 transfer, 1 partial, 6 untested) | 4.8 | 5.5 | DERIVED_AUDIT | response rules cover 3 of 5 condition families | Reviewer decisions; more Southeast evidence (transfer 0.7) |
| Alligator gar | Atractosteus spatula | BRACKISH_ESTUARINE | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 5/1 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 4.0/10 (0 transfer, 4 partial, 1 untested) | 4.7 | 5.0 | DERIVED_AUDIT | response rules cover 1 of 5 condition families | Keep research-only (policy REFUSE); no new work unless policy changes |
| Silver carp | Hypophthalmichthys molitrix | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 9/0 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 3.33/10 (0 transfer, 6 partial, 3 untested) | 4.6 | 4.5 | DERIVED_AUDIT | response rules cover 2 of 5 condition families | Reviewer decisions; field validation (live-set candidate) |
| Longnose gar | Lepisosteus osseus | BRACKISH_ESTUARINE | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 3/1 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 1.67/10 (0 transfer, 1 partial, 2 untested) | 3.9 | 4.5 | DERIVED_AUDIT | response rules cover 1 of 5 condition families | Reviewer decisions; add rules for more condition families |
| Bighead carp | Hypophthalmichthys nobilis | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 2/0 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 0.0/10 (0 transfer, 0 partial, 2 untested) | 3.3 | 3.0 | DERIVED_AUDIT | response rules cover 2 of 5 condition families | Separate its evidence from silver carp (2 rules, pooled); then review |
| Smallmouth buffalo | Ictiobus bubalus | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | PROPOSED (0 bands) | 1/3 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 5.0/10 (0 transfer, 1 partial, 0 untested) | 3.0 | 3.5 | DERIVED_AUDIT | no response bands | Resolve 3 DRAFT rules with evidence (1 usable); conditional policy |
| Bigmouth buffalo | Ictiobus cyprinellus | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 3/3 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 0.0/10 (0 transfer, 0 partial, 3 untested) | 2.9 | 3.5 | DERIVED_AUDIT | response rules cover 1 of 5 condition families | Hold (policy SUPPRESS); resolve spawn-temperature question only |
| Shortnose gar | Lepisosteus platostomus | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 1.5 | 2.0 | DERIVED_AUDIT | no usable machine rules | Hold (policy SUPPRESS; extirpated in AL) |
| Northern snakehead | Channa argus | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 1.4 | 2.0 | DERIVED_AUDIT | 5 knowledge domain(s) UNKNOWN (dayNightMovement, hydrologyRainInflowLevel, clarityLightWind...) | Research only where presence is confirmed (presence-gated) |
| Paddlefish | Polyodon spathula | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 1.2 | 1.5 | DERIVED_AUDIT | 3 knowledge domain(s) UNKNOWN (temperatureOxygen, clarityLightWind, foodFeedingLocation) | DO NOT research (protected; not a target) |
| Bowfin | Amia calva | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.9 | 1.5 | DERIVED_AUDIT | 4 knowledge domain(s) UNKNOWN (dayNightMovement, hydrologyRainInflowLevel, clarityLightWind...) | HIGH: policy decision first, then southern-reservoir evidence (1.3 now) |
| Black carp | Mylopharyngodon piceus | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.7 | 1.0 | DERIVED_AUDIT | 4 knowledge domain(s) UNKNOWN (temperatureOxygen, dayNightMovement, hydrologyRainInflowLevel...) | Hold (injurious; reporting only) |
| Black buffalo | Ictiobus niger | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.6 | 1.0 | DERIVED_AUDIT | 4 knowledge domain(s) UNKNOWN (temperatureOxygen, dayNightMovement, hydrologyRainInflowLevel...) | Hold (policy REFUSE) |
| Freshwater drum | Aplodinotus grunniens | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.3 | 0.5 | DERIVED_AUDIT | 6 knowledge domain(s) UNKNOWN (habitatDepthCover, dayNightMovement, hydrologyRainInflowLevel...) | Later (tier 3); assess narrowly if Michael wants it |
| Shorthead redhorse | Moxostoma macrolepidotum | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.1 | 0.0 | DERIVED_AUDIT | 7 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, dayNightMovement...) | Low: assess narrowly or mark NOT_ASSESSED |
| Channel catfish | Ictalurus punctatus | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.1 | 0.0 | DERIVED_AUDIT | 7 knowledge domain(s) UNKNOWN (seasonalLocationReproduction, habitatDepthCover, dayNightMovement...) | DO NOT research (not sight-shootable by Sector policy) |
| River carpsucker / quillback / other carpsuckers | Carpiodes spp. | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 7 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | Registry decision: split by species (quillback, river carpsucker...) before any research |
| American shad | Alosa sapidissima | ANADROMOUS | yes | yes | yes | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 8 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | DO NOT research now (managed gamefish; not legal by default) |
| Blue sucker | Cycleptus elongatus | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 8 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | Low: assess narrowly or mark NOT_ASSESSED |
| Gizzard shad | Dorosoma cepedianum | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 8 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | Modest: forage / food-web signal; policy stays not-assessed |
| Golden redhorse | Moxostoma erythrurum | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 8 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | Low: assess narrowly or mark NOT_ASSESSED |
| Goldfish | Carassius auratus | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 8 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | Low: assess narrowly or mark NOT_ASSESSED |
| River redhorse | Moxostoma carinatum | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 8 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | Low: assess narrowly or mark NOT_ASSESSED |
| Silver redhorse | Moxostoma anisurum | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 8 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | Low: assess narrowly or mark NOT_ASSESSED |
| Suckers / redhorse / carpsuckers (grouped row) | Catostomidae (grouped row) | FRESHWATER_ONLY | yes | yes | no (NOT_ASSESSED) | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | n/a | n/a | NOT_SCORED | species not assessed (NOT_ASSESSED row) | Registry artifact: leave NOT_ASSESSED (covered by species rows) |
| Tilapia (generic row) | Oreochromis spp. / Tilapia spp. (unresolved) | CROSS_HABITAT | yes | yes | no (NOT_ASSESSED) | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | n/a | n/a | NOT_SCORED | species not assessed (NOT_ASSESSED row) | HIGH: split to blue_tilapia (packet exists); needs Michael decision |

## Freshwater species, lowest to highest score
| Sector Label | Scientific Name | Habitat Flag | In Sector registry | In Biological | In score | Presence / lake coverage | Resp. bands | Rules (usable/draft) | Evidence tier | Review | Validation | Regional transfer | Audit score | Species-v2 (canonical) | Score type | Biggest missing capability | Next action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| American shad | Alosa sapidissima | ANADROMOUS | yes | yes | yes | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 8 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | DO NOT research now (managed gamefish; not legal by default) |
| Blue sucker | Cycleptus elongatus | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 8 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | Low: assess narrowly or mark NOT_ASSESSED |
| Gizzard shad | Dorosoma cepedianum | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 8 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | Modest: forage / food-web signal; policy stays not-assessed |
| Golden redhorse | Moxostoma erythrurum | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 8 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | Low: assess narrowly or mark NOT_ASSESSED |
| Goldfish | Carassius auratus | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 8 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | Low: assess narrowly or mark NOT_ASSESSED |
| River redhorse | Moxostoma carinatum | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 8 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | Low: assess narrowly or mark NOT_ASSESSED |
| Silver redhorse | Moxostoma anisurum | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 8 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | Low: assess narrowly or mark NOT_ASSESSED |
| River carpsucker / quillback / other carpsuckers | Carpiodes spp. | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.0 | 0.0 | DERIVED_AUDIT | 7 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, habitatDepthCover...) | Registry decision: split by species (quillback, river carpsucker...) before any research |
| Channel catfish | Ictalurus punctatus | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.1 | 0.0 | DERIVED_AUDIT | 7 knowledge domain(s) UNKNOWN (seasonalLocationReproduction, habitatDepthCover, dayNightMovement...) | DO NOT research (not sight-shootable by Sector policy) |
| Shorthead redhorse | Moxostoma macrolepidotum | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.1 | 0.0 | DERIVED_AUDIT | 7 knowledge domain(s) UNKNOWN (temperatureOxygen, seasonalLocationReproduction, dayNightMovement...) | Low: assess narrowly or mark NOT_ASSESSED |
| Freshwater drum | Aplodinotus grunniens | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.3 | 0.5 | DERIVED_AUDIT | 6 knowledge domain(s) UNKNOWN (habitatDepthCover, dayNightMovement, hydrologyRainInflowLevel...) | Later (tier 3); assess narrowly if Michael wants it |
| Black buffalo | Ictiobus niger | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.6 | 1.0 | DERIVED_AUDIT | 4 knowledge domain(s) UNKNOWN (temperatureOxygen, dayNightMovement, hydrologyRainInflowLevel...) | Hold (policy REFUSE) |
| Black carp | Mylopharyngodon piceus | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.7 | 1.0 | DERIVED_AUDIT | 4 knowledge domain(s) UNKNOWN (temperatureOxygen, dayNightMovement, hydrologyRainInflowLevel...) | Hold (injurious; reporting only) |
| Bowfin | Amia calva | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.9 | 1.5 | DERIVED_AUDIT | 4 knowledge domain(s) UNKNOWN (dayNightMovement, hydrologyRainInflowLevel, clarityLightWind...) | HIGH: policy decision first, then southern-reservoir evidence (1.3 now) |
| Paddlefish | Polyodon spathula | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 1.2 | 1.5 | DERIVED_AUDIT | 3 knowledge domain(s) UNKNOWN (temperatureOxygen, clarityLightWind, foodFeedingLocation) | DO NOT research (protected; not a target) |
| Northern snakehead | Channa argus | FRESHWATER_ONLY | yes | yes | yes | NONE | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 1.4 | 2.0 | DERIVED_AUDIT | 5 knowledge domain(s) UNKNOWN (dayNightMovement, hydrologyRainInflowLevel, clarityLightWind...) | Research only where presence is confirmed (presence-gated) |
| Shortnose gar | Lepisosteus platostomus | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 1.5 | 2.0 | DERIVED_AUDIT | no usable machine rules | Hold (policy SUPPRESS; extirpated in AL) |
| Bigmouth buffalo | Ictiobus cyprinellus | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 3/3 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 0.0/10 (0 transfer, 0 partial, 3 untested) | 2.9 | 3.5 | DERIVED_AUDIT | response rules cover 1 of 5 condition families | Hold (policy SUPPRESS); resolve spawn-temperature question only |
| Smallmouth buffalo | Ictiobus bubalus | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | PROPOSED (0 bands) | 1/3 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 5.0/10 (0 transfer, 1 partial, 0 untested) | 3.0 | 3.5 | DERIVED_AUDIT | no response bands | Resolve 3 DRAFT rules with evidence (1 usable); conditional policy |
| Bighead carp | Hypophthalmichthys nobilis | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 2/0 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 0.0/10 (0 transfer, 0 partial, 2 untested) | 3.3 | 3.0 | DERIVED_AUDIT | response rules cover 2 of 5 condition families | Separate its evidence from silver carp (2 rules, pooled); then review |
| Longnose gar | Lepisosteus osseus | BRACKISH_ESTUARINE | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 3/1 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 1.67/10 (0 transfer, 1 partial, 2 untested) | 3.9 | 4.5 | DERIVED_AUDIT | response rules cover 1 of 5 condition families | Reviewer decisions; add rules for more condition families |
| Silver carp | Hypophthalmichthys molitrix | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 9/0 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 3.33/10 (0 transfer, 6 partial, 3 untested) | 4.6 | 4.5 | DERIVED_AUDIT | response rules cover 2 of 5 condition families | Reviewer decisions; field validation (live-set candidate) |
| Alligator gar | Atractosteus spatula | BRACKISH_ESTUARINE | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 5/1 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 4.0/10 (0 transfer, 4 partial, 1 untested) | 4.7 | 5.0 | DERIVED_AUDIT | response rules cover 1 of 5 condition families | Keep research-only (policy REFUSE); no new work unless policy changes |
| Grass carp | Ctenopharyngodon idella | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 7/1 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 0.71/10 (0 transfer, 1 partial, 6 untested) | 4.8 | 5.5 | DERIVED_AUDIT | response rules cover 3 of 5 condition families | Reviewer decisions; more Southeast evidence (transfer 0.7) |
| Spotted gar | Lepisosteus oculatus | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 7/1 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 4.29/10 (0 transfer, 6 partial, 1 untested) | 5.0 | 4.5 | DERIVED_AUDIT | response rules cover 3 of 5 condition families | Reviewer decisions; field validation (live-set candidate) |
| Common carp | Cyprinus carpio | FRESHWATER_ONLY | yes | yes | yes | PILOT_PUBLISHED | PROPOSED | 11/0 | T1 desk literature | NONE (0 reviewed) | NOT_VALIDATED | 4.09/10 (0 transfer, 9 partial, 2 untested) | 6.9 | 7.0 | DERIVED_AUDIT | no human review | Reviewer decisions (packet ready), then first field validation |
| Suckers / redhorse / carpsuckers (grouped row) | Catostomidae (grouped row) | FRESHWATER_ONLY | yes | yes | no (NOT_ASSESSED) | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | n/a | n/a | NOT_SCORED | species not assessed (NOT_ASSESSED row) | Registry artifact: leave NOT_ASSESSED (covered by species rows) |
| Tilapia (generic row) | Oreochromis spp. / Tilapia spp. (unresolved) | CROSS_HABITAT | yes | yes | no (NOT_ASSESSED) | NONE | no | 0/0 | none | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | n/a | n/a | NOT_SCORED | species not assessed (NOT_ASSESSED row) | HIGH: split to blue_tilapia (packet exists); needs Michael decision |

## Saltwater species
| Sector Label | Scientific Name | Habitat Flag | In Sector registry | In Biological | In score | Presence / lake coverage | Resp. bands | Rules (usable/draft) | Evidence tier | Review | Validation | Regional transfer | Audit score | Species-v2 (canonical) | Score type | Biggest missing capability | Next action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Striped mullet | Mugil cephalus | CATADROMOUS ⚑GROUPING_REVIEW_REQUIRED | yes | yes | yes | NONE | no | 0/0 | desk research only | NONE (0 reviewed) | NOT_VALIDATED | UNKNOWN | 0.1 | 0.0 | DERIVED_AUDIT | 7 knowledge domain(s) UNKNOWN (temperatureOxygen, habitatDepthCover, dayNightMovement...) | Wait for saltwater phase; grouping review |

## Cross-habitat species (primary group still counts once)
| Species | Primary group | Flag | Rationale / source | Grouping |
|---|---|---|---|---|
| Alligator gar | FRESHWATER | BRACKISH_ESTUARINE | packet alligator_gar: Gulf-slope rivers, floodplain lakes and estuaries | settled |
| American shad | FRESHWATER | ANADROMOUS | packet american_shad: anadromous clupeid; Sector relevance is freshwater runs only (packet title) | settled |
| Longnose gar | FRESHWATER | BRACKISH_ESTUARINE | packet longnose_gar: fresh to brackish | settled |
| Striped mullet | SALTWATER | CATADROMOUS | packet striped_mullet: marine/estuarine fish that ascends coastal rivers, no obligate freshwater phase; one source calls it mostly freshwater and was discounted; Sector treats it as an unassessed freshwater-policy fish | GROUPING_REVIEW_REQUIRED |
| Tilapia (generic row) | FRESHWATER | CROSS_HABITAT | packet tilapia: introduced warm freshwater fish, tolerant of brackish water | settled |

## Per-fish score breakdown
| Species | knowledgeDepth | evidenceQuality | responseCoverage | regionalTransfer | habitat / seasonal / night (domain) | review | fieldValidation | AUDIT SCORE (completeness) |
|---|---|---|---|---|---|---|---|---|
| Common carp | 6.8 | 7.6 | 8.0 | 4.1 | 7 / 8 / 7 | none | NOT_VALIDATED | **6.9** (100%) |
| Spotted gar | 4.3 | 6.2 | 6.0 | 4.3 | 5 / 5 / 4 | none | NOT_VALIDATED | **5.0** (100%) |
| Grass carp | 5.3 | 3.8 | 6.0 | 0.7 | 7 / 6 / 3 | none | NOT_VALIDATED | **4.8** (100%) |
| Alligator gar | 5.0 | 7.3 | 2.0 | 4.0 | 5 / 7 / 1 | none | NOT_VALIDATED | **4.7** (100%) |
| Silver carp | 4.5 | 6.7 | 4.0 | 3.3 | 6 / 5 / 4 | none | NOT_VALIDATED | **4.6** (100%) |
| Longnose gar | 4.5 | 5.6 | 2.0 | 1.7 | 5 / 5 / 4 | none | NOT_VALIDATED | **3.9** (100%) |
| Bighead carp | 3.1 | 5.0 | 4.0 | 0.0 | 4 / 3 / 2 | none | NOT_VALIDATED | **3.3** (100%) |
| Smallmouth buffalo | 3.6 | 3.3 | 0.0 | 5.0 | 3 / 5 / 3 | none | NOT_VALIDATED | **3.0** (100%) |
| Bigmouth buffalo | 3.2 | 4.4 | 2.0 | 0.0 | 3 / 4 / 1 | none | NOT_VALIDATED | **2.9** (100%) |
| Shortnose gar | 2.0 | UNKNOWN | 0.0 | UNKNOWN | 3 / 2 / 2 | none | NOT_VALIDATED | **1.5** (75%) |
| Northern snakehead | 1.9 | UNKNOWN | 0.0 | UNKNOWN | 4 / 4 / UNKNOWN | none | NOT_VALIDATED | **1.4** (75%) |
| Paddlefish | 1.6 | UNKNOWN | 0.0 | UNKNOWN | 4 / 1 / 4 | none | NOT_VALIDATED | **1.2** (75%) |
| Bowfin | 1.3 | UNKNOWN | 0.0 | UNKNOWN | 3 / 2 / UNKNOWN | none | NOT_VALIDATED | **0.9** (75%) |
| Black carp | 0.9 | UNKNOWN | 0.0 | UNKNOWN | 2 / 1 / UNKNOWN | none | NOT_VALIDATED | **0.7** (75%) |
| Black buffalo | 0.8 | UNKNOWN | 0.0 | UNKNOWN | 1 / 2 / UNKNOWN | none | NOT_VALIDATED | **0.6** (75%) |
| Freshwater drum | 0.3 | UNKNOWN | 0.0 | UNKNOWN | UNKNOWN / 1 / UNKNOWN | none | NOT_VALIDATED | **0.3** (75%) |
| Shorthead redhorse | 0.2 | UNKNOWN | 0.0 | UNKNOWN | 1 / UNKNOWN / UNKNOWN | none | NOT_VALIDATED | **0.1** (75%) |
| Channel catfish | 0.1 | UNKNOWN | 0.0 | UNKNOWN | UNKNOWN / UNKNOWN / UNKNOWN | none | NOT_VALIDATED | **0.1** (75%) |
| River carpsucker / quillback / other carpsuckers | 0.1 | UNKNOWN | 0.0 | UNKNOWN | UNKNOWN / UNKNOWN / UNKNOWN | none | NOT_VALIDATED | **0.0** (75%) |
| American shad | 0.0 | UNKNOWN | 0.0 | UNKNOWN | UNKNOWN / UNKNOWN / UNKNOWN | none | NOT_VALIDATED | **0.0** (75%) |
| Blue sucker | 0.0 | UNKNOWN | 0.0 | UNKNOWN | UNKNOWN / UNKNOWN / UNKNOWN | none | NOT_VALIDATED | **0.0** (75%) |
| Gizzard shad | 0.0 | UNKNOWN | 0.0 | UNKNOWN | UNKNOWN / UNKNOWN / UNKNOWN | none | NOT_VALIDATED | **0.0** (75%) |
| Golden redhorse | 0.0 | UNKNOWN | 0.0 | UNKNOWN | UNKNOWN / UNKNOWN / UNKNOWN | none | NOT_VALIDATED | **0.0** (75%) |
| Goldfish | 0.0 | UNKNOWN | 0.0 | UNKNOWN | UNKNOWN / UNKNOWN / UNKNOWN | none | NOT_VALIDATED | **0.0** (75%) |
| River redhorse | 0.0 | UNKNOWN | 0.0 | UNKNOWN | UNKNOWN / UNKNOWN / UNKNOWN | none | NOT_VALIDATED | **0.0** (75%) |
| Silver redhorse | 0.0 | UNKNOWN | 0.0 | UNKNOWN | UNKNOWN / UNKNOWN / UNKNOWN | none | NOT_VALIDATED | **0.0** (75%) |
| Suckers / redhorse / carpsuckers (grouped row) | n/a | UNKNOWN | n/a | UNKNOWN | - / - / - | none | NOT_VALIDATED | **n/a** (0%) |
| Tilapia (generic row) | n/a | UNKNOWN | n/a | UNKNOWN | - / - / - | none | NOT_VALIDATED | **n/a** (0%) |
| Striped mullet | 0.2 | UNKNOWN | 0.0 | UNKNOWN | UNKNOWN / 1 / UNKNOWN | none | NOT_VALIDATED | **0.1** (75%) |

## Current score set (rows that affect the 4.6)
Median of species-v2 `overallRounded` over the 27 ASSESSED rows = **0.95**. Rows sorted lowest first.
| Species | Group | Row status | knowledgeDepth (species-v2 exact) | Bands | Usable rules | Effectively empty (<1.0) | Policy |
|---|---|---|---|---|---|---|---|
| Tilapia (generic row) | FRESHWATER | NOT_ASSESSED | n/a | no | 0 | no | policyNotAssessed |
| Suckers / redhorse / carpsuckers (grouped row) | FRESHWATER | NOT_ASSESSED | n/a | no | 0 | no | policyNotAssessed |
| American shad | FRESHWATER | ASSESSED | 0.0 | no | 0 | **yes** | policyNotAssessed |
| River redhorse | FRESHWATER | ASSESSED | 0.0 | no | 0 | **yes** | policyNotAssessed |
| Golden redhorse | FRESHWATER | ASSESSED | 0.0 | no | 0 | **yes** | policyNotAssessed |
| Silver redhorse | FRESHWATER | ASSESSED | 0.0 | no | 0 | **yes** | policyNotAssessed |
| Goldfish | FRESHWATER | ASSESSED | 0.0 | no | 0 | **yes** | policyNotAssessed |
| Gizzard shad | FRESHWATER | ASSESSED | 0.0 | no | 0 | **yes** | policyNotAssessed |
| Blue sucker | FRESHWATER | ASSESSED | 0.0 | no | 0 | **yes** | policyNotAssessed |
| River carpsucker / quillback / other carpsuckers | FRESHWATER | ASSESSED | 0.1 | no | 0 | **yes** | policyNotAssessed |
| Channel catfish | FRESHWATER | ASSESSED | 0.1 | no | 0 | **yes** | policyNotAssessed |
| Striped mullet | SALTWATER | ASSESSED | 0.2 | no | 0 | **yes** | policyNotAssessed |
| Shorthead redhorse | FRESHWATER | ASSESSED | 0.2 | no | 0 | **yes** | policyNotAssessed |
| Freshwater drum | FRESHWATER | ASSESSED | 0.3 | no | 0 | **yes** | policyNotAssessed |
| Black buffalo | FRESHWATER | ASSESSED | 0.8 | no | 0 | **yes** | POLICY_ASSESSED |
| Black carp | FRESHWATER | ASSESSED | 0.9 | no | 0 | **yes** | POLICY_ASSESSED |
| Bowfin | FRESHWATER | ASSESSED | 1.3 | no | 0 | no | policyNotAssessed |
| Paddlefish | FRESHWATER | ASSESSED | 1.6 | no | 0 | no | policyNotAssessed |
| Northern snakehead | FRESHWATER | ASSESSED | 1.9 | no | 0 | no | policyNotAssessed |
| Shortnose gar | FRESHWATER | ASSESSED | 2.0 | no | 0 | no | POLICY_ASSESSED |
| Bighead carp | FRESHWATER | ASSESSED | 3.1 | PROPOSED | 2 | no | POLICY_ASSESSED |
| Bigmouth buffalo | FRESHWATER | ASSESSED | 3.2 | PROPOSED | 3 | no | POLICY_ASSESSED |
| Smallmouth buffalo | FRESHWATER | ASSESSED | 3.6 | no | 1 | no | POLICY_ASSESSED |
| Spotted gar | FRESHWATER | ASSESSED | 4.3 | PROPOSED | 7 | no | POLICY_ASSESSED |
| Silver carp | FRESHWATER | ASSESSED | 4.5 | PROPOSED | 9 | no | POLICY_ASSESSED |
| Longnose gar | FRESHWATER | ASSESSED | 4.5 | PROPOSED | 3 | no | POLICY_ASSESSED |
| Alligator gar | FRESHWATER | ASSESSED | 5.0 | PROPOSED | 5 | no | POLICY_ASSESSED |
| Grass carp | FRESHWATER | ASSESSED | 5.3 | PROPOSED | 7 | no | POLICY_ASSESSED |
| Common carp | FRESHWATER | ASSESSED | 6.8 | PROPOSED | 11 | no | POLICY_ASSESSED |

## Unrated / near-empty rows: why they are in the score
| Species | Value | Why it is in the score (A real FW target not researched · B future saltwater · C policyNotAssessed · D insufficient evidence · E registry artifact · F intentionally unsupported) |
|---|---|---|
| American shad | 0.0 | C+F |
| River redhorse | 0.0 | A (low) |
| Golden redhorse | 0.0 | A (low) |
| Silver redhorse | 0.0 | A (low) |
| Goldfish | 0.0 | A (low) |
| Gizzard shad | 0.0 | A (forage)+C |
| Blue sucker | 0.0 | A (low) |
| River carpsucker / quillback / other carpsuckers | 0.1 | A+E |
| Channel catfish | 0.1 | C+F |
| Striped mullet | 0.2 | B+C |
| Shorthead redhorse | 0.2 | A (low) |
| Freshwater drum | 0.3 | A (medium-low)+C |
| Black buffalo | 0.8 | D+F |
| Black carp | 0.9 | D+F |

## policyNotAssessed fish
| Species | Group | Why not assessed | Should it stay? | Depressing the score? | Bowfishing case for research |
|---|---|---|---|---|---|
| Bowfin | FRESHWATER | no ratified policy (fails closed); thin evidence | No: tier-1 target, assess after southern evidence | yes: 1.3 row in the median | HIGH |
| Tilapia (generic row) | FRESHWATER | taxon unresolved (NOT_ASSESSED row) | Until the blue_tilapia split is decided | no (excluded from median; costs ~0.35 coverage) | HIGH in AZ/CA/FL/NV/NC/TX (Sector table) |
| Freshwater drum | FRESHWATER | no ratified policy | Yes for now | yes: 0.35 row | Medium-low (tier 3) |
| Gizzard shad | FRESHWATER | forage; no ratified policy | Yes as a target; value is as a food-web signal | yes: 0.0 row | Modest |
| Striped mullet | SALTWATER | no ratified policy; saltwater-primary | Yes | yes: 0.2 row | None until saltwater phase |
| Channel catfish | FRESHWATER | not sight-shootable; no ratified policy | Yes (keep) | yes: 0.15 row | None |
| Paddlefish | FRESHWATER | protected / not legal by default | Yes (keep) | yes: 1.6 row (not near-empty) | None |
| American shad | FRESHWATER | not legal by default; anadromous run species | Yes (keep) | yes: 0.0 row | None |

Also outside the 12 policy-assessed species (not on the historic list, same status today): northern snakehead, goldfish, blue sucker, carpsuckers group, golden/river/shorthead/silver redhorse.

## Freshwater fish missing from Biological
| Sector Label | Scientific Name | Where it exists in Sector today | Bowfishing relevance | Lake presence coverage | Current Biological status | Reason missing | Priority |
|---|---|---|---|---|---|---|---|
| Quillback | Carpiodes cyprinus | not defined (covered only by the grouped `carpsuckers_group` row) | commonly shot rough fish in the Midwest/Ohio basin | none published | grouped row, 0.05 | registry splits carpsuckers by genus, not species | MEDIUM (split first) |
| River carpsucker | Carpiodes carpio | not defined (same group row) | rough fish, moderate | none published | grouped row | same | MEDIUM (split first) |
| Highfin carpsucker | Carpiodes velifer | not defined (same group row) | low | none published | grouped row | same | LOW |
| Florida gar | Lepisosteus platyrhincus | not in registry, engine table, policy registry or Lake Brain list | Florida-peninsula gar target; Sector fleet has 13 FL lakes | none | absent | never added | MEDIUM (only if FL launches) |
| Spotted sucker | Minytrema melanops | not defined | low | none | absent | never added | LOW |
| Blue / flathead catfish | Ictalurus furcatus / Pylodictis olivaris | not defined | cavity-nesting catfish: same reasoning as Sector's own channel-catfish policy note (unverified here) | none | absent | never added | DO_NOT_ADD |
| `suckers_redhorse_carpsuckers_group` row | Catostomidae (grouped) | in the Biological registry (NOT_ASSESSED) | n/a | none | NOT_ASSESSED, already excluded | registry artifact | DO_NOT_ADD (keep excluded) |

## Saltwater / future species gap
| Species (Sector Label if known) | Scientific | Status | Wait? |
|---|---|---|---|
| Striped mullet | Mugil cephalus | defined in Sector (engine table + registry); Biological packet exists; 0.2 row, 0 rules | wait for saltwater phase; grouping review |
| American shad (anadromous) | Alosa sapidissima | defined; packet exists; 0.0 row | wait; freshwater-run relevance only |
| Tilapia (brackish-tolerant) | Oreochromis spp. | defined; packet exists; NOT_ASSESSED | freshwater-first; split decision pending |
| Redfish, snook, tarpon, black drum, sheepshead, flounder, rays, mullet-adjacent species | various | **not defined anywhere in Sector** (registry, engine table, policy registry, Lake Brain list) | future saltwater roadmap only; no Biological research, no registry row |

## Freshwater group maturity (read-only view)
| species | 28 |
|---|---|
| assessed | 26 |
| not assessed | 2 |
| with usable rules | 9 |
| with response bands | 8 |
| reviewed | 0 |
| validated | 0 |
| average audit score | 1.8 |
| median audit score | 0.8 |
| lowest five | american_shad 0.0, blue_sucker 0.0, gizzard_shad 0.0, golden_redhorse 0.0, goldfish 0.0 |
| highest five | common_carp 6.91, spotted_gar 4.95, grass_carp 4.78, alligator_gar 4.65, silver_carp 4.61 |
| coverage completeness (known weight) | 0.8 |

## Saltwater group maturity (read-only view)
| species | 1 |
|---|---|
| assessed | 1 |
| not assessed | 0 |
| with usable rules | 0 |
| with response bands | 0 |
| reviewed | 0 |
| validated | 0 |
| average audit score | 0.1 |
| median audit score | 0.1 |
| lowest five | striped_mullet 0.15 |
| highest five | striped_mullet 0.15 |
| coverage completeness (known weight) | 0.8 |

## 4.6 score impact simulations (diagnostic only; scorer v1; nothing published)
| Simulation | Species | Assessed | Score | knowledgeDepth | assessedCoverage | contradictionsGaps |
|---|---|---|---|---|---|---|
| A. CURRENT OFFICIAL SPECIES SET | 29 | 27 | **4.6** | 1.0 | 9.3 | 6.6 |
| B. FRESHWATER-PRIMARY ONLY | 28 | 26 | **4.6** | 1.2 | 9.3 | 6.5 |
| C. ASSESSED FRESHWATER ONLY | 26 | 26 | **4.7** | 1.2 | 10.0 | 6.5 |
| D. FRESHWATER + policyNotAssessed rows exactly as currently treated (assessed rows kept) | 28 | 26 | **4.6** | 1.2 | 9.3 | 6.5 |
| E. SALTWATER + CROSS-HABITAT ROWS REMOVED (striped mullet, American shad, tilapia) | 26 | 25 | **4.7** | 1.5 | 9.6 | 6.3 |
| F. (extra) near-empty rows (knowledge < 1.0) treated as NOT_ASSESSED | 29 | 13 | **4.0** | 3.5 | 4.5 | 3.7 |
| G. (extra) ONLY the 12 policy-assessed species | 12 | 12 | **4.8** | 4.0 | 10.0 | 2.3 |
| H. (hypothetical) every freshwater assessed row lifted to at least 3.0 | 28 | 26 | **4.9** | 3.0 | 9.3 | 6.5 |
| I. (hypothetical) ... at least 4.0 | 28 | 26 | **5.1** | 4.0 | 9.3 | 6.5 |
| J. (hypothetical) ... at least 5.0 | 28 | 26 | **5.3** | 5.0 | 9.3 | 6.5 |

## Fairness questions
1. **Are saltwater/future species lowering a freshwater-first score?** Barely. Only striped mullet is saltwater-primary. Removing it leaves 4.6 (sim B); removing all three saltwater/cross-habitat rows gives 4.7 (sim E).
2. **Are policyNotAssessed fish lowering the score?** Partly. They hold knowledgeDepth at 1.0 (the 12 policy-assessed species alone have a median of 4.0, sim G), but removing them would hurt contradictionsGaps and net only 4.8. They are not the main cause.
3. **Are completely unrated fish treated as zero?** Yes. An ASSESSED row with UNKNOWN domains scores those domains 0 inside species-v2 (e.g. bowfin 4 UNKNOWN domains = 1.3), and 7 rows are exactly 0.0. Only NOT_ASSESSED rows are excluded from the median. Marking the near-empty rows NOT_ASSESSED would raise knowledgeDepth to 3.5 but **lower** the score to 4.0, because assessedCoverage falls (sim F).
4. **Is the median knowledgeDepth of 1.0 caused by unresearched rows?** Yes: 14 of 27 assessed rows are under 1.0 exact, so the 14th-ranked row (the median) is one of them.
5. **How far can legitimate freshwater research move the score before field validation?** About +0.3 to +0.7: lifting every freshwater assessed row to at least 3.0 / 4.0 / 5.0 gives 4.9 / 5.1 / 5.3 (hypothetical; the principal species are evidence-capped at 3-4). Add roughly +0.1 for regionalTransfer. Nothing reaches 6.0 without a VALIDATED species.
6. **How many freshwater species actually need more research?** 17 of 26 assessed freshwater rows are under 3.0; but only about 5 are worth it now (list below); the rest are policy-held or low value.
7. **Five species with the highest next value:** bowfin, tilapia (blue), smallmouth buffalo, bighead carp, northern snakehead.
8. **Do not research now:** Channel catfish, paddlefish, American shad (policy: not targets); alligator gar, black buffalo, black carp, shortnose gar, bigmouth buffalo (policy REFUSE/SUPPRESS, research-only); redhorses, goldfish, blue sucker (low value); striped mullet and all saltwater (future phase); species-v2 for common carp / spotted gar / silver carp / longnose gar needs REVIEW and FIELD data, not more desk research.
**Is the 4.6 fair?** Mostly yes. The scoring universe is not the problem (freshwater-only gives 4.6-4.7); the number is held down by weak/absent freshwater knowledge, no human review, and no field validation.

## Top 5 freshwater fish to work next (audit judgement; Michael decides)
| # | Fish | Why now | Pre-field limit |
|---|---|---|---|
| 1 | Bowfin | engine tier 1 target, row 1.3 with 4 UNKNOWN domains, no rules | policy decision first; southern telemetry is an external source |
| 2 | Tilapia -> blue_tilapia | tier 1 in six states, packet already researched, currently NOT_ASSESSED | needs the split decision; cold-lethal evidence only |
| 3 | Smallmouth buffalo | tier 1, conditional policy, 1 usable + 3 DRAFT rules, 0 condition families | rules are the gap, evidence mostly exists |
| 4 | Bighead carp | tier 2, only 2 rules, evidence pooled with silver carp | needs its own evidence |
| 5 | Northern snakehead | invasive, row 1.9 with 5 UNKNOWN domains | presence-gated: research only where present |
Next after those: gizzard shad (food-web signal), quillback / river carpsucker (after the registry split).

## Fish that should wait
Channel catfish, paddlefish, American shad (policy: not targets); alligator gar, black buffalo, black carp, shortnose gar, bigmouth buffalo (policy REFUSE/SUPPRESS, research-only); redhorses, goldfish, blue sucker (low value); striped mullet and all saltwater (future phase); species-v2 for common carp / spotted gar / silver carp / longnose gar needs REVIEW and FIELD data, not more desk research.
