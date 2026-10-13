# Lake Brain: the representative validation fleet (smallest useful set, 18 lakes)

This is a design document. It selects nothing in production, accepts no binding, changes no status, and starts no beta. It answers one question: **if five pilots are not five independent validations, what is the smallest set of lakes that exercises every distinct regime, operator type, region and failure mode the Lake Brain will meet, so that the validation evidence is not one Tennessee River chain and one Savannah River cascade?** No part of this proposes testing 621 lakes; the ledger already records every REVIEWED lake for free. This set is for the extra, human-audited attention.

Written 2026-10-13. Everything counted below was recomputed from `jobs/lake-brain/data/bindings.proposed.v1.json` (196 rows), `jobs/lake-brain/validation/results/holdout_v2_results*.{json,csv}`, and, from the research branch (`git show origin/docs/lake-brain-research:docs/research/lake-brain/data/...`), `lake_features.csv`, `transfer_slots.json`, `plan_flood_evidence.csv`, `verified_bindings_v2.csv`. The coverage metric is the research's own (`research/lake-brain/context_transfer.py`: distance from standardised log area, log residence time, log mean depth, log shoreline-development index, plus 0.5 for a different regime, 0.4 for a different region, 0.25 for a different operator family; "covered" = nearest chosen lake within 1.0), run read-only on this set.

## 1. Why five pilots are not five validations

| Fact | Evidence |
|---|---|
| Guntersville, Wheeler, Wilson, Pickwick are one hydraulic system | The same NLDI chain (`chain-CherokeeLake`); TVA RestApi 3-day average flows: downstream inflow equals upstream outflow plus 0 to 4 % tributary water; pool elevations move 0 to 0.14 ft per day together (research `LAKE_BRAIN_CONTEXT_RESEARCH.md` 2.4, fetched 2026-10-13). Same operator, same regime (R1 run-of-river), same region (SE). |
| Hartwell is the middle of a second cascade | Hartwell, Russell, Thurmond (USACE Savannah) plus Jocassee and Keowee (Duke); `chain-Burton`. |
| The pilots sit in 2 of 9 modelled classes and one region | Classes R1 (4 pilots) and R3 (1); region SE only; TVA and USACE. Research `transfer_slots.json`: the five pilots put **16.9 %** of the 597 classifiable fleet lakes within distance 1.0 of a pilot (9.7 % within 0.75, 25.0 % within 1.25). |
| The effective pilot count is two | One Tennessee system, one Savannah system. Everything the four TVA pilots agree on is one observation. |

Consequence for evidence: when a validation family is reported, the **unit is the cluster, not the lake**. The three other TN pilots stay published and stay in the ledger as within-system replicates; they do not add to a pass rate.

## 2. Selection rules (fixed here, before anything is scored)

1. **Population:** the 196 accepted-eligible lakes (`bindings.proposed.v1.json`: machine-verified strict bindings, no coordinate hold, no series hold, no provider-terms hold). A lake outside it cannot be a validation lake until its hold clears.
2. **History:** at least **10 complete years** (research `historyCompleteYears`, at least 329 daily values per year; the four TVA pilots use the 16 to 18 years now in the Brain archive). 109 of the 196 qualify.
3. **One lake per hydrologic cluster.** Cluster = shared `chainId` (NLDI main stem, 250 km), or the same river and operator program. Where a cluster has several candidates, take the one with more independent evidence (second origin, stage-area truth, plan and flood levels) and the better history.
4. **Span, by design:** every class present among the 109 (R1, R2, R3, R4, N2), every region present (SE, MW, GP, NE, W), every operator type (TVA, USACE, USBR, state or utility or irrigation district), every provider adapter (tva, cwms, a2w, rise, usgs, nwps), lakes with and without plan and flood levels, quiet and dynamic lakes, hourly and daily feeds.
5. **Failure modes from the spent hold-out are included on purpose:** lakes that sit in a problem pocket (quiet lakes for H-C, run-of-river for H-D, one H-A 0-of-5 lake, open-basin storage for tails). This is for coverage of failure shapes. It is not a way to re-test or re-tune H-C; the thresholds and the hold-out verdicts stay as they are.

A hard finding from rule 2: **among the 109, no lake is a true natural lake.** The classes present are R1 8, R2 28, R3 29, R4 37, N2 (regulated natural) 7; the only machine-verified strict natural deep lake with at least ten years is Apopka FL (17 years, held for SJRWMD provider terms). Natural lakes N1a and N1b, small ponds N3 and small impoundments R5 (130 of the 597 classifiable lakes in the metric) cannot be validated from the accepted fleet at all today. That is a documented gap (section 6), not a thing to paper over by relabelling N2 lakes.

## 3. The 18 lakes

"Years" are complete years. "HO" is that lake's pre-registered hold-out result, carried unchanged: H-A = years passing out of tested (a lake passes at 4 of 5), RAPID = share of days beyond the effective RAPID threshold (H-C unit), chg = share of consecutive-day pairs whose trend label changes, sim = share of STABLE days inside a 3-day move of at least 0.5 ft (H-D unit). The pooled hold-out values are RAPID 0.035, chg 0.132, sim 0.075.

| # | Lake | Class / region | Operator, provider | Years | Plan / flood levels | Other series carried / independent corroboration | HO H-A | HO RAPID | HO chg / sim |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Guntersville\|AL** (TN cluster) | R1 / SE | TVA, `tva` | 17 | guide + zone / **none** (TVA publishes no flood-pool bottom) | NWPS relay only | 4/5 | 0.028 | 0.286 / 0.183 |
| 2 | **Lake Hartwell\|SC** (Savannah cluster) | R3 / SE | USACE Savannah, `usgs` + CWMS | 64 | zone + flood | NWPS relay; stage-area truth exists | 5/5 | 0.041 | 0.250 / 0.099 |
| 3 | **Bankhead\|AL** | R1 / SE | Alabama Power (non-federal), `cwms` | 62 | zone / none | A2W (same origin) | 5/5 | 0.044 | 0.319 / 0.101 |
| 4 | **West Point\|GA** (Chattahoochee cluster) | R2 / SE | USACE Mobile, `a2w` | 18 | zone + flood | USGS corroborated | 4/5 | 0.064 | 0.312 / 0.271 |
| 5 | **Lake Murray (SC)\|SC** | R3 / SE | Dominion Energy (investor-owned utility), `usgs` | 96 | none / none | NWPS relay | 5/5 | 0.029 | 0.082 / 0.040 |
| 6 | **Grenada Lake\|MS** (Yazoo cluster) | R4 / SE | USACE Vicksburg, `cwms` | 27 | zone + flood | NWPS relay; stage-area truth exists | 5/5 | 0.056 | 0.213 / 0.199 |
| 7 | **Bluestone Lake\|WV** | R2 / SE | USACE Huntington, `cwms` | **13** | zone + flood | USGS corroborated | 3/3 | **0.000** | 0.011 / 0.017 |
| 8 | **Carlyle Lake\|IL** | R2 / MW | USACE St. Louis, `cwms` | 60 | zone + flood | NWPS relay | 4/5 | 0.053 | 0.146 / 0.095 |
| 9 | **Table Rock Lake\|MO** (White River cluster) | R3 / MW | USACE Little Rock, `a2w` | 69 | zone + flood | CWMS and NWPS | 5/5 | 0.056 | 0.177 / 0.097 |
| 10 | **Lake Winnebago\|WI** | N2 / MW | outlet-regulated natural lake, `usgs` | 126 | none / none | none | no hold-out series | n/a | n/a |
| 11 | **Indian Lake\|NY** | R4 / NE | state-regulated (Hudson River-Black River Regulating District), `nwps` | 123 | none / none | none (single NWPS gauge) | 5/5 | 0.053 | 0.137 / 0.071 |
| 12 | **Lake Livingston\|TX** | R2 / GP | Trinity River Authority, `usgs` | 27 | none (TWDB tier 2 exists) / none | NWPS relay | 5/5 | 0.063 | 0.156 / 0.067 |
| 13 | **Cheney Reservoir\|KS** (Arkansas plains cluster) | R4 / GP | USBR, `rise` (daily) | 33 | zone + flood | NWPS relay | **0/5** | 0.012 | 0.031 / 0.009 |
| 14 | **Pueblo Reservoir\|CO** (Arkansas headwaters cluster) | R4 / W | USBR, `cwms` | 48 | zone + flood | USBR corroborated | 5/5 | 0.005 | 0.104 / 0.032 |
| 15 | **Don Pedro\|CA** | R3 / W | public utility (NID), `cwms` | 25 | none / flood | none; stage-area truth exists | 5/5 | 0.062 | 0.117 / 0.183 |
| 16 | **Abiquiu Lake\|NM** (Rio Chama cluster) | R4 / W | USACE Albuquerque, `a2w` | 15 | zone + flood | CWMS and NWPS | 4/5 | **0.080** | 0.119 / 0.075 |
| 17 | **Keyhole Reservoir\|WY** | R4 / W | USBR, `rise` (daily) | 74 | none / flood | USACE corroborated | 5/5 | **0.001** | **0.003** / 0.000 |
| 18 | **Flathead Lake\|MT** (Flathead cluster) | N2 / W | Energy Keepers Inc. (Kerr Dam), `a2w` | 86 | none / none | USGS corroborated | 5/5 | 0.009 | 0.043 / 0.015 |

Counts: classes R1 2, R2 4, R3 4, R4 6, N2 2. Regions SE 7, W 5, MW 3, GP 2, NE 1. Operator families USACE 8, USBR 3, TVA 1, other (utility, state, district, private) 6. Providers cwms 6, a2w 4 (West Point, Table Rock, Abiquiu, Flathead), usgs 4 (Hartwell, Murray, Winnebago, Livingston), rise 2, nwps 1, tva 1. Plan levels on 11, flood levels on 11, neither on 5 (Murray, Winnebago, Indian Lake, Livingston, Flathead). Feed cadence: 16 hourly or sub-hourly, 2 daily (RISE: Cheney, Keyhole, median source age 48 h). Tier: 17 are `FULL` (at least 15 years); Bluestone (13 years) is `STANDARD`, the one lake that tests the tier-gate path.

Reserve (swap if a lake fails its own precondition, same cluster rule): Wheeler\|AL, Wilson\|AL and Pickwick Lake\|TN (TN replicates, kept as pilots), Canyon Ferry Lake\|MT (USBR, A2W, flood levels, 72 years; the Missouri/Montana snowmelt reservoir the set lacks), Great Sacandaga Lake\|NY (State, USGS, two origins, 96 years; NE substitute for Indian Lake), Neely Henry\|AL or Allatoona\|GA (Coosa cluster, not otherwise represented), Topaz Lake\|NV (nwps, 25 years, extreme residence time).

**Preconditions per lake before it counts** (state, not assume): the binding is in the reviewed batch; its history is loaded in the Brain archive and reaches the tier the table assumes (the research counts for 16 of these lakes are not yet in the Brain archive: only Guntersville, from the TVA pilots, and Hartwell are); Winnebago needs its USGS daily series loaded and checked first (no series was located for the hold-out harness, so it has no hold-out numbers above); its directory coordinate is flagged `ok`; its source feed was fresh at the most recent probe.

## 4. One-system clusters that were collapsed

Each row is one validation unit. Lakes after the arrow are in the 109 and are **not** added.

| Representative | Collapsed with it (same chain or operator program) | Reason |
|---|---|---|
| Guntersville\|AL | Wheeler, Wilson, Pickwick (the other three pilots) | `chain-CherokeeLake`; flows and levels move together; same TVA operations |
| Lake Hartwell\|SC | Clarks Hill / J.S. Thurmond\|GA (`chain-Burton`; Russell is not in the 196) | Savannah cascade, USACE SAS |
| West Point\|GA | Lanier, Seminole (`chain-Blackshear`) | Chattahoochee-Flint, USACE Mobile |
| Grenada Lake\|MS | Sardis, Enid, Arkabutla | USACE Vicksburg Yazoo flood-control program; one regime and one operator; hold-out H-A Grenada 5/5, Sardis 5/5, Enid 5/5, Arkabutla 1/5, a within-program spread worth reading in the Grenada report |
| Cheney Reservoir\|KS | Kaw Lake\|OK (`chain-CheneyReservoi`) | Arkansas plains reservoirs |
| Pueblo Reservoir\|CO | John Martin Reservoir (`chain-JohnMartinRese`) | Arkansas headwaters |
| Abiquiu Lake\|NM | Cochiti Lake, El Vado Lake (`chain-AbiquiuLake`); Conchas / Ute are a neighbouring chain | Rio Chama / Rio Grande |
| Flathead Lake\|MT | Hungry Horse Reservoir (`chain-FlatheadLake`) | one drainage; the lake is the natural-lake representative |
| Carlyle Lake\|IL | none | `chain-CarlyleLake` stands alone |
| Table Rock Lake\|MO | none in the 109 (Beaver, Taneycomo elsewhere) | `chain-Beaver` |
| Not chosen, collapsed among themselves | Kerr Lake (John H. Kerr)\|NC and Kerr Reservoir (Buggs Island)\|VA are two directory rows for **one lake**; Neely Henry, Allatoona, Carters (`chain-Allatoona`); Boysen and Bighorn (`chain-BighornLake`); Havasu and Mohave (`chain-Alamo`); Pend Oreille and Priest (`chain-LakeKoocanusa`); Santa Rosa and Sumner (`chain-SantaRosaLake`); Marion and Moultrie (Santee Cooper) | Same logic; none is needed to cover a class or region the 18 already cover |

No two of the 18 share a `chainId`.

## 5. What the set adds, family by family

| Validation family | What the 18 add that the five pilots did not | Honest limit |
|---|---|---|
| **Binding identity** (V1) | Five of the 18 carry an independent-origin corroboration (West Point, Bluestone, Pueblo, Keyhole, Flathead). Thirteen are single-origin or relay-only: that is where a human operator-page check earns its time. Includes datum-different gauges (Hartwell on USGS 02187010 with CWMS pool as the other source, USGS lake gauges at Murray, Winnebago, Livingston) and two daily RISE feeds. | An audit of 18 identities is a spot check beside the n = 60 random sample, not a substitute. |
| **H-A band calibration** | Reaches FULL, STANDARD (Bluestone) and the lower boundary of FULL (Abiquiu, 15 years); R4 and N2 (the groups where the hold-out was weakest: coverage 0.754 and 0.746, tails 8.0 % and 7.9 %); Cheney (0 of 5 in the hold-out) as the one clear stress case. | 2 N2 lakes and 6 R4 lakes: per-class pass rates are not estimable; the value is in per-lake traces, not rates. |
| **H-B tail** | Lakes with long drought and refill cycles (Pueblo, Keyhole, Abiquiu, Indian Lake, Flathead). | Same. |
| **H-C rapid-change rate** | Spans the whole range of the failed criterion: quiet lakes at 0.0 to 1.2 % (Bluestone, Keyhole, Pueblo, Flathead, Cheney), mid lakes at 2.8 to 5.6 %, and lakes at or near the top of the band (Abiquiu 8.0 %, West Point 6.4 %, Livingston 6.3 %, Don Pedro 6.2 %). Gives the prospective revised H-C evidence from the right lakes early. | Does not repair H-C; the failure stays as recorded. |
| **H-D trend stability** | The three kinds of pocket (run-of-river: Guntersville, Bankhead; managed reservoirs with daily swings: West Point, Don Pedro; calm storage: Keyhole, Bluestone, Cheney, Flathead). | TVA daily series carried NWS RVD 0.1 ft quantisation; Guntersville stands for one TVA cluster only. |
| **Operating-zone and flood semantics** | 11 lakes with a plan (CWMS, A2W, TVA levels) and 11 with a flood-pool bottom whose level names can be checked against the operator's own page, including USBR-owned flood space in a CWMS feed (Pueblo); 7 lakes with no operator flood level, where a flood state must stay `UNKNOWN` unless evidence appears (TVA Guntersville, run-of-river Bankhead, Murray, Winnebago, Indian Lake, Flathead; Livingston has a TWDB tier-2 level that is not in the table). | Meaning review is by a person, lake by lake. |
| **Source freshness** | Hourly operator feeds, hourly USGS and NWPS, and daily RISE with its documented lag; the set will show the staleness model on each cadence class. | Needs fleet runs in the ledger. |
| **Stage-area truth (shoreline context, not depth)** | Hartwell, Grenada and Don Pedro have CWMS stage-area slope fits from the research; shoreline slope is cached for those three plus Guntersville and West Point (`LAKE_BRAIN_SHORELINE_SLOPE_NOTE.md`). | 13 of the 18 have no shoreline slope yet. |
| **Transfer** (V-K) | Distance coverage of the 597-lake fleet within 1.0: **55.1 %** (mean nearest distance 1.02), against 16.9 % for the five pilots. By class: R2 93 %, R3 90 %, R4 82 %, R1 67 %, N2 15 %, other natural 0 %. By region: SE 76 %, W 62 %, GP 62 %, MW 47 %, NE 35 %. | See below. |

Reading the transfer number honestly: a random draw of 18 lakes from the same pool of 109 covers 52.7 % on average (5th to 95th percentile 47.1 % to 57.8 %), and the geometric optimum (greedy k-medoid from the 109) reaches 63 %. The set is chosen for **validation function first**, so its geometric coverage is that of a random 18 of the pool, not better. What it adds over a random draw is that every class, region, operator type and provider is present and that the failure pockets are covered on purpose. What nothing in the pool can fix is the natural-lake side of the fleet.

## 6. What the set cannot do, and what is still missing

- **Natural lakes.** Nothing in the 109 is an N1 lake. A natural slot is **RESERVED, WAITING**: Apopka FL (N1a, 17 years, SJRWMD terms unconfirmed) is the only strict candidate; the research's N1/N3 slot picks (Mendota, Yellowstone, Eagle Lake MS, Highland Lake CT) are not strictly bound yet. Until one qualifies, say "regulated natural lakes only" wherever results are described.
- **Small impoundments and ponds (R5, N3):** 40 lakes in the metric, no eligible lake.
- **Northeast and Midwest are thin** (1 and 3 lakes; NE coverage 35 %, MW 47 %).
- **Rates.** 18 clusters give no per-class pass rates. The set supports failure-mode reports and cluster-level consistency, not statistics. Rates come from the whole 196-lake ledger, scored once under a pre-registration.
- **Hold-out numbers are retrospective** and were produced on research history series; 16 of the 18 are not yet in the Brain archive.
- **Not beta testing.** None of this implies a customer rollout for any lake.

## 7. How the set is used (all read-only until Michael approves otherwise)

1. After the batch is accepted and the history job has run for these 18, publish a per-lake report for each: identity audit (gauge page, datum), history tier, plan and flood level names against the operator page, the ledger's first scored months.
2. Report validation results per cluster and per class, with the pilots' replicates reported separately.
3. Pre-register any prospective criterion (including a revised H-C) before reading ledger months; apply it once. Use the set to check sensitivity, not to choose thresholds.
4. Optional premium tier: a field or operator-contact check on three lakes chosen from this set (for example Guntersville, Keyhole, Pueblo). It is not a prerequisite for anything.
