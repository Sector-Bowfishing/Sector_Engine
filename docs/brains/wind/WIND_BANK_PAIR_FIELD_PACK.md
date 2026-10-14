# Bank-pair field pack (candidate pairs from the pilot and contrast lakes)

Purpose: obtain the **physical truth** Wind lacks (BWIS B3 + D2; certification dims 6/7) with observations a tester can do in about a minute per bank (`WIND_FIELD_OBSERVATION_PROTOCOL.md`; programme `WIND_FIELD_PROGRAM_PLAN.md`). Pairs were selected by geometry alone (`jobs/wind-hourly/research/field_pairs.py`; no forecasts, no H2): all 99 candidates are in `data/field_pairs_candidates.json` (sha256 pinned by the v2 pre-registration). **ESTIMATED lakes (Hartwell, Toledo Bend) use the published Lake Registry v1 polygons** (an earlier draft built from older engine polygons placed most banks > 300 m from the registry shoreline and was discarded before any session). **Access and safety are not verified** — check public ramps, hazards and permission before any visit; coordinates are shoreline anchors, not launch points.

## Independence warning
Guntersville, Wheeler, Wilson and Pickwick are four reaches of the Tennessee River system with similar wind climate and fetch geometry; **they count as one environment** for generalisation (and the same 8 METAR stations back all four). Lake Hartwell (SC/GA, ESTIMATED geometry), Mille Lacs (open natural lake), Lake McConaughy (plains reservoir), Toledo Bend (large southern reservoir, ESTIMATED) and Lake Maurepas (shallow coastal) are added for independence and to test the ESTIMATED tier. Smith Mountain Lake VA (dendritic, max p90 fetch 0.75 km) is a useful *negative control* (everything should read protected/low) but has no strong pairs.

## Pair types
- **Mirror pair:** opposite shores of one open-water run. Wind from θ → A (downwind shore) DIRECT/HIGH FETCH, B (upwind shore) PROTECTED. **Reverse the wind and the roles swap**, so the same two banks test the model in both directions.
- **Cove vs point:** ≤ 1.5 km apart, one exposed point, one true cove (the "is this cove sheltered?" question).
- **Subtle ordering:** two exposed banks ≤ 3 km apart, predicted waves 1.25–2.5× different (tests fetch *ordering*, not just land vs water).
ESTIMATED lakes publish only EXPOSED / PROTECTED; the DIRECT/CROSS words below are internal for those two lakes.

## Conditions that make a session count (all pairs)
- Wind from the stated direction ±25°, **8–15 mph sustained** (a forecast ≥ 5 mph with the NBM breezy-risk flag is ideal), steady ≥ 3 h; evening or night (7 pm–1 am local) preferred, **afternoons are the practical volume** (`WIND_FIELD_PROGRAM_PLAN.md`).
- Visit both banks within **60 minutes** (same device, same height, 60-s average).
- Skip: < 5 mph (direction unreliable), thunderstorms, wind shifting > 45° during the session.

## What to record (per bank)
Water: calm / light / choppy / rough · bank: EXPOSED / PROTECTED / UNSURE (optional DIRECT/CROSS on audited lakes) · boat control: easy / noticeable / difficult · wind direction and speed (handheld if available) · confidence 1–3 · one photo looking upwind. **The observer does not see the model's prediction** until after submitting.

## What would falsify the model (proposed; the canonical scorer owns real thresholds; see `WIND_BANK_VALIDATION_V2_PREREG.md`)
- Predicted-rougher bank observed **rougher by at least one step** = concordant; equal = half; calmer = discordant. After **≥ 20 qualifying sessions on ≥ 2 independent lakes** concordance < 0.70 ⇒ not supported as a bank ranking.
- **False-PROTECTED:** a PROTECTED call recorded choppy/rough (or boat control difficult) with wind ≥ 8 mph from the stated direction in more than **1 in 10** such calls (≥ 15 calls) ⇒ ESTIMATED labels stay withheld.
- ESTIMATED and AUDITED lakes are scored separately. Evidence Addendum v1 volumes for certification credit: ≥ 40 holdout pairs, ≥ 2 lakes, ≥ 3 quadrants; concordance ≥ 80% earns full credit.

## Guntersville|AL — pilot · geometry AUDITED (HIGH)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** GT-005719 (34.5346, -86.1217) · **B** GT-001172 (34.4906, -86.1707) | from **SW** (225°) | A DIRECT + HIGH FETCH, 7.8 km, ~8.8 in · B PROTECTED, 31 m, ~0.6 in; reversed (NE) A PROTECTED, B DIRECT (6.3 km) | 252× fetch, 14.7× wave | 6.6 km |
| 2 | Mirror | **A** GT-005212 (34.4231, -86.3213) · **B** GT-000393 (34.3592, -86.3146) | from **S** (180°) | A DIRECT + HIGH FETCH, 6.6 km, ~8.1 in · B PROTECTED, 31 m, ~0.6 in; reversed (N) A PROTECTED, B DIRECT (4.6 km) | 212× fetch, 13.5× wave | 7.1 km |
| 3 | Cove Vs Point | **A** GT-005626 (34.5277, -86.1459) · **B** GT-004651 (34.5328, -86.1473) | from **SW** (225°) | A CROSS + HIGH FETCH, 6.6 km, ~8.1 in · B PROTECTED, 31 m, ~0.6 in | 214× fetch, 13.5× wave | 0.6 km |
| 4 | Subtle Ordering | **A** GT-001039 (34.4221, -86.1978) · **B** GT-001025 (34.4350, -86.1814) | from **SW** (225°) | A DIRECT + HIGH FETCH, 6.0 km, ~7.7 in · B DIRECT, 2381 m, ~4.9 in | 3× fetch, 1.6× wave | 2.1 km |

6217 usable banks; strong-fetch threshold 1200 m. Audited geometry (modeled exposure, no field truth).

## Wheeler|AL — pilot · geometry AUDITED (HIGH)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** WH-W000328 (34.7777, -87.2230) · **B** WH-W003903 (34.7376, -87.2716) | from **SW** (225°) | A DIRECT + HIGH FETCH, 6.3 km, ~7.9 in · B PROTECTED, 28 m, ~0.5 in; reversed (NE) A PROTECTED, B DIRECT (6.2 km) | 225× fetch, 15.8× wave | 6.3 km |
| 2 | Mirror | **A** WH-W000495 (34.6935, -87.0614) · **B** WH-W003544 (34.6519, -87.0618) | from **S** (180°) | A DIRECT + HIGH FETCH, 4.4 km, ~6.7 in · B PROTECTED, 26 m, ~0.5 in; reversed (N) A PROTECTED, B DIRECT (4.3 km) | 171× fetch, 13.4× wave | 4.6 km |
| 3 | Cove Vs Point | **A** WH-W000333 (34.7775, -87.2186) · **B** WH-W000343 (34.7778, -87.2043) | from **SW** (225°) | A DIRECT + HIGH FETCH, 6.0 km, ~7.7 in · B PROTECTED, 31 m, ~0.6 in | 194× fetch, 12.8× wave | 1.3 km |
| 4 | Subtle Ordering | **A** WH-W000337 (34.7761, -87.2103) · **B** WH-W000367 (34.7629, -87.1821) | from **SW** (225°) | A DIRECT + HIGH FETCH, 4.7 km, ~6.8 in · B DIRECT, 2964 m, ~5.4 in | 2× fetch, 1.3× wave | 3.0 km |

4462 usable banks; strong-fetch threshold 1259 m. Audited geometry (modeled exposure, no field truth).

## Wilson|AL — pilot · geometry AUDITED (HIGH)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** WI-W000424 (34.8417, -87.5334) · **B** WI-W001002 (34.8037, -87.5824) | from **SW** (225°) | A DIRECT + HIGH FETCH, 6.1 km, ~7.8 in · B PROTECTED, 71 m, ~0.8 in; reversed (NE) A PROTECTED, B CROSS (5.8 km) | 86× fetch, 9.8× wave | 6.2 km |
| 2 | Mirror | **A** WI-W000554 (34.8118, -87.4365) · **B** WI-W000791 (34.7858, -87.4382) | from **S** (180°) | A DIRECT, 3.1 km, ~5.6 in · B PROTECTED, 20 m, ~0.4 in; reversed (N) A PROTECTED, B DIRECT (3.0 km) | 155× fetch, 14.0× wave | 2.9 km |
| 3 | Cove Vs Point | **A** WI-W000418 (34.8432, -87.5412) · **B** WI-W000406 (34.8422, -87.5523) | from **SW** (225°) | A CROSS + HIGH FETCH, 6.7 km, ~8.2 in · B PROTECTED, 28 m, ~0.5 in | 241× fetch, 16.4× wave | 1.0 km |
| 4 | Subtle Ordering | **A** WI-W000426 (34.8422, -87.5315) · **B** WI-W000460 (34.8382, -87.5206) | from **SW** (225°) | A DIRECT + HIGH FETCH, 6.0 km, ~7.7 in · B DIRECT, 3712 m, ~6.1 in | 2× fetch, 1.3× wave | 1.1 km |

1046 usable banks; strong-fetch threshold 1699 m. Audited geometry (modeled exposure, no field truth).

## Pickwick Lake|TN — pilot · geometry AUDITED (HIGH)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** PK-W000682 (34.9179, -88.0436) · **B** PK-W001582 (34.8890, -88.0778) | from **SW** (225°) | A DIRECT + HIGH FETCH, 4.3 km, ~6.5 in · B PROTECTED, 31 m, ~0.6 in; reversed (NE) A PROTECTED, B CROSS (4.4 km) | 138× fetch, 10.8× wave | 4.5 km |
| 2 | Mirror | **A** PK-W000787 (34.8570, -87.9320) · **B** PK-W001440 (34.8168, -87.9331) | from **S** (180°) | A DIRECT + HIGH FETCH, 4.4 km, ~6.7 in · B PROTECTED, 31 m, ~0.6 in; reversed (N) A PROTECTED, B DIRECT (4.8 km) | 143× fetch, 11.2× wave | 4.5 km |
| 3 | Cove Vs Point | **A** PK-W000681 (34.9178, -88.0457) · **B** PK-W000604 (34.9164, -88.0612) | from **SW** (225°) | A CROSS + HIGH FETCH, 4.3 km, ~6.6 in · B PROTECTED, 28 m, ~0.5 in | 155× fetch, 13.2× wave | 1.4 km |
| 4 | Subtle Ordering | **A** PK-W000687 (34.9170, -88.0328) · **B** PK-W000647 (34.9398, -88.0391) | from **SW** (225°) | A DIRECT, 3.4 km, ~5.9 in · B DIRECT, 2116 m, ~4.6 in | 2× fetch, 1.3× wave | 2.6 km |

2490 usable banks; strong-fetch threshold 1454 m. Audited geometry (modeled exposure, no field truth).

## Lake Hartwell|SC — pilot (ESTIMATED geometry) · geometry ESTIMATED (HIGH)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** E-0334 (34.4341, -82.8423) · **B** E-0348 (34.4141, -82.8602) | from **SW** (225°) | A DIRECT, 2.3 km, ~4.8 in · B PROTECTED, 20 m, ~0.4 in; reversed (NE) A PROTECTED, B CROSS (1.8 km) | 114× fetch, 12.0× wave | 2.8 km |
| 2 | Mirror | **A** E-0183 (34.5333, -82.8158) · **B** E-0254 (34.4866, -82.8118) | from **S** (180°) | A DIRECT + HIGH FETCH, 4.1 km, ~6.4 in · B PROTECTED, 20 m, ~0.4 in; reversed (N) A PROTECTED, B DIRECT (3.8 km) | 205× fetch, 16.0× wave | 5.2 km |
| 3 | Cove Vs Point | **A** E-0175 (34.5409, -82.7750) · **B** E-0169 (34.5461, -82.7754) | from **SW** (225°) | A CROSS, 3.2 km, ~5.7 in · B PROTECTED, 20 m, ~0.4 in | 162× fetch, 14.2× wave | 0.6 km |
| 4 | Subtle Ordering | **A** E-0275 (34.4784, -83.0107) · **B** E-0261 (34.4841, -83.0178) | from **SW** (225°) | A DIRECT, 1.5 km, ~3.9 in · B DIRECT, 907 m, ~3.0 in | 2× fetch, 1.3× wave | 0.9 km |

395 usable banks; strong-fetch threshold 1200 m. **Validates the ESTIMATED tier** — priority for field time.

## Mille Lacs Lake|MN — open natural lake · geometry AUDITED (HIGH)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** N-B06BD2-W000431 (46.1999, -93.4930) · **B** N-B06BD2-W000617 (46.1317, -93.5974) | from **SW** (225°) | A DIRECT + HIGH FETCH, 11.5 km, ~10.7 in · B PROTECTED, 278 m, ~1.7 in; reversed (NE) A PROTECTED, B CROSS (10.8 km) | 41× fetch, 6.3× wave | 11.0 km |
| 2 | Mirror | **A** N-B06BD2-W000196 (46.3265, -93.7816) · **B** N-B06BD2-W000095 (46.2262, -93.7832) | from **S** (180°) | A DIRECT + HIGH FETCH, 12.3 km, ~11.1 in · B PROTECTED, 76 m, ~0.9 in; reversed (N) A PROTECTED, B CROSS (11.0 km) | 161× fetch, 12.3× wave | 11.2 km |
| 3 | Cove Vs Point | **A** N-B06BD2-W000442 (46.1843, -93.4928) · **B** N-B06BD2-W000457 (46.1753, -93.4811) | from **SW** (225°) | A CROSS + HIGH FETCH, 8.3 km, ~9.1 in · B PROTECTED, 46 m, ~0.7 in | 181× fetch, 13.0× wave | 1.4 km |
| 4 | Subtle Ordering | **A** N-B06BD2-W000459 (46.1733, -93.4816) · **B** N-B06BD2-W000470 (46.1670, -93.4730) | from **SW** (225°) | A DIRECT + HIGH FETCH, 5.0 km, ~7.1 in · B DIRECT, 3214 m, ~5.7 in | 2× fetch, 1.2× wave | 1.0 km |

741 usable banks; strong-fetch threshold 3000 m. Audited geometry (modeled exposure, no field truth).

## Lake McConaughy|NE — plains reservoir · geometry AUDITED (HIGH)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** N-E0790D-W000290 (41.2476, -101.7019) · **B** N-E0790D-W000444 (41.2076, -101.7539) | from **SW** (225°) | A DIRECT + HIGH FETCH, 6.1 km, ~7.8 in · B PROTECTED, 28 m, ~0.5 in; reversed (NE) A PROTECTED, B DIRECT (5.8 km) | 217× fetch, 15.6× wave | 6.2 km |
| 2 | Mirror | **A** N-E0790D-W000242 (41.2548, -101.7620) · **B** N-E0790D-W000449 (41.2097, -101.7609) | from **S** (180°) | A DIRECT + HIGH FETCH, 5.0 km, ~7.1 in · B PROTECTED, 184 m, ~1.4 in; reversed (N) A PROTECTED, B CROSS (4.9 km) | 27× fetch, 5.1× wave | 5.0 km |
| 3 | Cove Vs Point | **A** N-E0790D-W000290 (41.2476, -101.7019) · **B** N-E0790D-W000275 (41.2486, -101.7154) | from **SW** (225°) | A DIRECT + HIGH FETCH, 6.1 km, ~7.8 in · B PROTECTED, 28 m, ~0.5 in | 217× fetch, 15.6× wave | 1.1 km |
| 4 | Subtle Ordering | **A** N-E0790D-W000326 (41.2378, -101.6767) · **B** N-E0790D-W000332 (41.2276, -101.6729) | from **SW** (225°) | A DIRECT + HIGH FETCH, 4.9 km, ~7.0 in · B DIRECT, 3002 m, ~5.5 in | 2× fetch, 1.3× wave | 1.2 km |

471 usable banks; strong-fetch threshold 3000 m. Audited geometry (modeled exposure, no field truth).

## Toledo Bend Reservoir|TX — large southern reservoir (ESTIMATED geometry) · geometry ESTIMATED (HIGH)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** E-0116 (31.6450, -93.7685) · **B** E-0142 (31.5962, -93.8395) | from **SW** (225°) | A DIRECT + HIGH FETCH, 9.2 km, ~9.6 in · B PROTECTED, 160 m, ~1.3 in; reversed (NE) A PROTECTED, B CROSS (9.4 km) | 58× fetch, 7.4× wave | 8.6 km |
| 2 | Mirror | **A** E-0295 (31.3471, -93.6800) · **B** E-0340 (31.2581, -93.6787) | from **S** (180°) | A DIRECT + HIGH FETCH, 9.7 km, ~9.9 in · B PROTECTED, 30 m, ~0.5 in; reversed (N) A PROTECTED, B CROSS (9.9 km) | 324× fetch, 19.8× wave | 9.9 km |
| 3 | Cove Vs Point | **A** E-0116 (31.6450, -93.7685) · **B** E-0115 (31.6466, -93.7647) | from **SW** (225°) | A DIRECT + HIGH FETCH, 9.2 km, ~9.6 in · B PROTECTED, 30 m, ~0.5 in | 307× fetch, 19.2× wave | 0.4 km |
| 4 | Subtle Ordering | **A** E-0326 (31.2841, -93.5904) · **B** E-0328 (31.2809, -93.6107) | from **SW** (225°) | A DIRECT + HIGH FETCH, 5.3 km, ~7.3 in · B DIRECT, 2822 m, ~5.3 in | 2× fetch, 1.4× wave | 2.0 km |

390 usable banks; strong-fetch threshold 2518 m. **Validates the ESTIMATED tier** — priority for field time.

## Lake Maurepas|LA — shallow coastal lake · geometry AUDITED (HIGH)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** N-043DCB-W000357 (30.2399, -90.4291) · **B** N-043DCB-W000064 (30.1719, -90.5096) | from **SW** (225°) | A DIRECT + HIGH FETCH, 11.0 km, ~10.5 in · B PROTECTED, 34 m, ~0.6 in; reversed (NE) A PROTECTED, B CROSS (11.1 km) | 324× fetch, 17.5× wave | 10.8 km |
| 2 | Mirror | **A** N-043DCB-W000273 (30.3241, -90.4370) · **B** N-043DCB-W000370 (30.2186, -90.4379) | from **S** (180°) | A DIRECT + HIGH FETCH, 11.8 km, ~10.9 in · B PROTECTED, 32 m, ~0.6 in; reversed (N) A PROTECTED, B DIRECT (10.9 km) | 369× fetch, 18.2× wave | 11.7 km |
| 3 | Cove Vs Point | **A** N-043DCB-W000312 (30.2891, -90.4012) · **B** N-043DCB-W000320 (30.2849, -90.3881) | from **SW** (225°) | A DIRECT + HIGH FETCH, 17.5 km, ~13.2 in · B PROTECTED, 151 m, ~1.2 in | 116× fetch, 11.0× wave | 1.3 km |
| 4 | Subtle Ordering | **A** N-043DCB-W000129 (30.2099, -90.5831) · **B** N-043DCB-W000124 (30.2114, -90.5926) | from **SW** (225°) | A DIRECT, 1.5 km, ~3.9 in · B DIRECT, 402 m, ~2.0 in | 4× fetch, 1.9× wave | 0.9 km |

355 usable banks; strong-fetch threshold 3000 m. Audited geometry (modeled exposure, no field truth).

## Suggested first programme
Guntersville (home water, 20 pairs) + Lake Hartwell (ESTIMATED, 16–20 pairs, ≥ 8 mandatory) satisfy ≥ 40 pairs / ≥ 2 independent lakes; add a third system (Mille Lacs, McConaughy, Toledo Bend) via a local tester when available. Single-bank tester records feed the agreement matrix but only paired sessions count toward concordance.
