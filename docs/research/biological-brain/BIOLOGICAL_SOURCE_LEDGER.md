# Biological Source Ledger (public-safe index; per-source citations are private)

Per-source ledgers (author, year, venue, URL/DOI, study type, region, n, strength, READ status) live inside each packet under `SOURCE LEDGER`. Counts below are **label mentions in the packet text, not unique sources** (a source can be mentioned several times).

| Packet | READ-FULL | READ-ABSTRACT | SNIPPET-ONLY | LEAD-NOT-OPENED | PROFILE-carried | words |
|---|---:|---:|---:|---:|---:|---:|
| alligator_gar | 7 | 5 | 11 | 4 | 14 | 1671 |
| american_shad | 2 | 4 | 13 | 2 | 0 | 1208 |
| bighead_carp | 12 | 8 | 8 | 1 | 7 | 1539 |
| bigmouth_buffalo | 0 | 3 | 11 | 0 | 8 | 1115 |
| black_buffalo | 2 | 0 | 2 | 1 | 1 | 735 |
| black_carp | 2 | 11 | 0 | 1 | 1 | 1033 |
| blue_sucker | 0 | 7 | 4 | 3 | 0 | 785 |
| bowfin | 6 | 1 | 13 | 1 | 0 | 1638 |
| carpsuckers_group | 3 | 2 | 6 | 0 | 1 | 1147 |
| channel_catfish | 1 | 4 | 10 | 1 | 0 | 1433 |
| common_carp_extension | 22 | 8 | 5 | 3 | 0 | 2451 |
| freshwater_drum | 1 | 10 | 7 | 2 | 0 | 1727 |
| gizzard_shad | 4 | 0 | 8 | 3 | 0 | 980 |
| goldfish | 13 | 8 | 6 | 6 | 0 | 2074 |
| grass_carp | 7 | 6 | 14 | 2 | 0 | 2593 |
| longnose_gar | 6 | 1 | 6 | 5 | 19 | 1326 |
| northern_snakehead | 5 | 9 | 14 | 1 | 0 | 1526 |
| paddlefish | 0 | 8 | 11 | 0 | 0 | 1278 |
| redhorses | 3 | 7 | 28 | 3 | 0 | 3059 |
| shortnose_gar | 4 | 1 | 4 | 2 | 19 | 878 |
| silver_carp | 15 | 22 | 23 | 3 | 15 | 3122 |
| smallmouth_buffalo | 1 | 6 | 9 | 2 | 11 | 1448 |
| spotted_gar | 6 | 2 | 4 | 2 | 29 | 1554 |
| striped_mullet | 6 | 0 | 10 | 2 | 0 | 1103 |
| tilapia | 9 | 5 | 8 | 3 | 0 | 1683 |
| **total mentions** | **137** | **138** | **235** | **53** | **125** | |

## Rules applied
- A source counts as evidence only if READ-FULL or READ-ABSTRACT; SNIPPET-ONLY and LEAD-NOT-OPENED earn no score credit, as the rubric requires.
- Profile-carried sources (from the 2026-10-12.1 bundle) were not re-opened this campaign unless labelled.
- Repeated reports of one telemetry cohort are counted once (e.g. Sandusky grass carp).

## Known weak provenance
- Minor-species packets (drum, shad, catfish, paddlefish, blue sucker, redhorses, American shad, mullet, tilapia) were produced by a delegated agent that used four sub-agents; the delegating agent did not review contents. Treat as unreviewed until spot-checked.
- Tilapia TAFS 147(2):278 abstract came from a mirror host; verify DOI.
- TVA 'warm coves' silver carp claim is snippet-only.
- Several PDFs were scanned/blocked (see blocker queue #7).

## Total
25 packets, 39106 words.