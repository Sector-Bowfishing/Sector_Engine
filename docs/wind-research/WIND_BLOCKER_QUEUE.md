# Wind Brain — blocker queue (bowfishing value first)

| # | Blocker | Bowfishing impact | Unblocked by | Owner |
|---|---|---|---|---|
| 1 | **Production wind ≠ Brain wind.** Customers see Open-Meteo Best Match (HRRR→GFS, direction 0.62, night bias +1.13) from a single point; Brain NBM is shadow. | Everything built here is invisible | Michael's decision: Engine serves NBM wind (or `ncep_nbm_conus` on paid plan); also fixes the non-commercial licence | Michael |
| 2 | **Windy nights are under-forecast** (obs 10–15 mph read 4.6–6 mph low; 0 of 20 windy nights called) | Misses exactly the nights that wreck boat control | Ship the P90 breezy-risk flag; re-test on sealed H2 after 2027-01-01 | Wind research |
| 3 | **No over-water wind** (all stations land) | Unknown speed bias over a big reservoir; caps certification at 7 | One on-lake anemometer (also the only proven nowcast gain, −16% at +1 h) | Michael (hardware) |
| 4 | **No bank-pair truth** (BWIS B3+D2 = 17 pts) | "Bank A calmer than B" never confirmed in the field | Two-lake bank network (≈ 2–4 months after install) | Michael |
| 5 | **Fleet coverage 4 live / 74 audited / 544 estimable** | Most lakes have no bank answer | Adopt polygon fetch as ESTIMATED tier; run a matched per-bank comparison to resolve G2 failure | Wind research + Lake Brain |
| 6 | **Texture floor ignores shelter** (tree-lined cove in 15 mph shows "Light chop") | The cove question ("is this sheltered?") over-states chop in lee | Evaluate shelter via upwind land-cover/height within 200 m (simple), validate with the network | Wind research |
| 7 | **Lay-down/trend prediction has no skill** (POD 0.07) | "Will it lay down after dark?" can't be promised | Nowcast sensor; or a pre-registered diurnal NBM-error correction | Wind research |
| 8 | **Rubric doesn't value bowfishing-relevant skill** (event ≥15 mph gates, all-hours direction) | Score can't register this campaign's gains | Independent rubric review (Michael + reviewer) | Michael |
| 9 | Station 8A1 direction 0.44; 4A6 n=28 | Per-lake direction trust | Per-lake check on each new lake; more stations | Wind research |
| 10 | AK/HI forecast domains, 22 lakes with no polygon (Great Lakes etc.) | up to 43 lakes (overlapping sets) with no bank or forecast path | NBM AK/HI domains; Lake Brain polygons | Engine |
| 11 | Sealed H2 until 2027-01-01 | Cannot claim live skill | Wait | — |
