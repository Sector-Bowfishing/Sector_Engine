# Reclamation datum chain: what public data settled (2026-10-14)

Research only. Scripts: `research/depth/{tsc_tables_parse,tsc_equations_parse,rise_storage_link,resaloc_pairs,reclamation_pool_frame,rise_diagram_link,rise_link_proposals,rise_diagram_proposals}.py`; data `docs/brains/depth/data/{rise_storage_link,rise_diagram_link,reclamation_pool_frame}.json`. Earlier position (`DEPTH_RISE_DATUM_RULES.md`): the datum documents exist but one link is undocumented, that the RISE daily elevation is the gage record the survey and allocation pages describe; it needed Reclamation's confirmation. **That link can be tested with Reclamation's own data**, because RISE also publishes daily storage, which Reclamation computes from the elevation through its capacity table.

## Test 1: storage consistency against the survey table
RISE daily elevation reproduces RISE daily storage through the TSC area-capacity table when both are in one frame; a frame offset d shows as `storage(E) = table(E + d)`. d is fitted on a 0.01 ft grid over -3..+3 ft over the last ~400 days. **Rule:** pass when |best d| <= 0.10 ft and the relative RMS at the best d <= 0.005 (the numeric limits were set after the first six fits were read; the cases below that fail would also fail a stricter limit except Jamestown).

| Reservoir | Table form | Table | Days | Best d (ft) | Rel. RMS | Pass | Datum status now |
|---|---|---|---|---|---|---|---|
| Cheney Reservoir | equations | CheneyReservoir2015AreaCapacityTables_Final508 | 399 | -0.00 | 0.0 | **yes** | SAME_DATUM |
| Bighorn Lake | equations | BighornReservoirAreaCapacityTables2017_Final508 | 399 | -0.00 | 0.0 | **yes** | SAME_SOURCE |
| El Vado Lake | equations | ElVado2018_tables | 399 | -0.00 | 0.00012 | **yes** | SAME_SOURCE |
| Elephant Butte Reservoir | equations | Elephant_Butte_Reservoir_2017_&_2019_Area_and_Capacity_Tables | 398 | -0.00 | 0.00016 | **yes** | SAME_SOURCE |
| Flaming Gorge Reservoir | 1-ft table | FlamingGorgeRes2019AreaCapacityTables_final508 | 399 | -1.20 | 0.00056 | no | UNKNOWN |
| Heron Lake | equations | Heron_Reservoir_2010_Capacity_Tables | 399 | -0.00 | 1e-05 | **yes** | SAME_SOURCE |
| Jamestown Reservoir | 1-ft table | Jamestown_Reservoir_2009_Capacity_Tables | 399 | +0.04 | 0.00678 | no | UNKNOWN |
| Navajo Reservoir | equations | NavajoReservoir2019AreaCapacityTables_final508VI | 399 | -0.00 | 0.0 | **yes** | SAME_SOURCE |
| Fresno Reservoir | equations | Fresno_Reservoir_2010_Area_and_Capatity_Tables | 399 | -0.27 | 0.01503 | no | SAME_SOURCE |
| Swanson Reservoir | 1-ft table | Swanson_Reservoir_2011_Capacity_Tables | 396 | -0.00 | 0.00099 | **yes** | SAME_SOURCE |
| Blue Mesa Reservoir | equations | BlueMesaReservoir2019AreaAndCapacityTables_Final508 | 399 | -3.00 | 0.27128 | no | UNKNOWN |
| Patterson Lake | equations | Edward_Arthur_Patterson_CapacityTable_2013 | 398 | -0.00 | 4e-05 | **yes** | SAME_SOURCE |
| Lake Tschida | equations | Lake_Tschida_2013_Capacity_Tables | 399 | -0.00 | 1e-05 | **yes** | SAME_SOURCE |
| Calamus Reservoir | equations | Calamus_2012_Area-Capacity_table_final | 399 | -0.00 | 3e-05 | **yes** | SAME_SOURCE |

Failures are not evidence of a different datum: Flaming Gorge and Fresno (2010 table) fit a table about 1.2 / 0.27 ft away, which means RISE storage comes from a different table version; Blue Mesa's RISE storage differs by about a third (it is not total storage); Jamestown is within 0.04 ft but at 0.7% RMS. None of them is promoted.

## Test 2: allocation-diagram frame (no table needed)
Great Plains allocation diagrams print `Elev. E (C Acre-Feet)` pairs, and **the Depth reference pool is itself one of the printed elevations** (the pool source is that diagram). Where RISE's (elevation, storage) cloud passes through a printed capacity, the RISE elevation at that capacity should equal E. dE below is that difference on the most recent 60 nearby days (and only days after the diagram's revision). **Rule:** at least one printed pair inside the observed range, every such pair within 0.10 ft. Controls (Calamus, Tschida, Patterson, whose frame the survey tables already settled) reproduce to <= 0.003 ft.

| Reservoir | Diagram revised | dE at printed pairs inside the RISE range | Pass | Datum status now |
|---|---|---|---|---|
| Angostura Reservoir | 10/04/2012 | 3187.2 ft: -0.001 | **yes** | SAME_SOURCE |
| Box Butte Reservoir | 10/16/2012 | no printed capacity inside the observed RISE range | no | UNKNOWN |
| Boysen Reservoir | - | 4717.0 ft: -0.003 | **yes** | SAME_SOURCE |
| Buffalo Bill Reservoir | - | no printed capacity inside the observed RISE range | no | UNKNOWN |
| Fresno Reservoir | 6/28/2016 | 2567.0 ft: +0.036, 2575.0 ft: -0.001 | **yes** | SAME_SOURCE |
| Glendo Reservoir | - | no printed capacity inside the observed RISE range | no | UNKNOWN |
| Horsetooth Reservoir | 10/04/2012 | no printed capacity inside the observed RISE range | no | UNKNOWN |
| Jamestown Reservoir | 4/10/2015 | 1428.0 ft: -0.001, 1431.0 ft: -0.145 | no | UNKNOWN |
| Keyhole Reservoir | 10/04/2012 | 4099.3 ft: -0.001 | **yes** | SAME_SOURCE |
| Lake Granby | 10/04/2012 | no printed capacity inside the observed RISE range | no | UNKNOWN |
| Merritt Reservoir | 10/16/2012 | 2946.0 ft: +0.001 | **yes** | SAME_SOURCE |
| Pactola Reservoir | 10/04/2012 | 4580.2 ft: +0.000 | **yes** | SAME_SOURCE |
| Pathfinder Reservoir | 5/19/16 | 5852.49 ft: -0.003 | **yes** | SAME_SOURCE |
| Ruedi Reservoir | 10/04/2012 | no printed capacity inside the observed RISE range | no | UNKNOWN |
| Calamus Reservoir (control) | 6/23/2015 | 2244.0 ft: -0.001 | **yes** | SAME_SOURCE |
| Swanson Reservoir (control) | 10/19/2012 | no printed capacity inside the observed RISE range | no | SAME_SOURCE |
| Lake Tschida (control) | 8/28/2015 | 2064.5 ft: -0.002 | **yes** | SAME_SOURCE |
| Patterson Lake (control) | 7/28/2015 | 2420.0 ft: -0.000 | **yes** | SAME_SOURCE |

Pairs outside the observed range are not extrapolated: Box Butte, Buffalo Bill, Glendo, Horsetooth, Granby and Ruedi have not been at any printed capacity since their diagram was revised. That re-runs by itself whenever they refill (no new data source needed).

## Pool figure in the table frame
Where the diagram prints elevation/capacity pairs and the survey table is parsed, the table's capacity at those elevations equals the printed capacity exactly (Calamus 2244.0 ft = 119,469 af; Swanson 2752.0 ft = 110,175 af; Tschida 2064.5 ft = 65,091 af; Patterson 2420.0 ft = 8,479 af). So the pool figure Depth uses is on the table's frame, whatever that frame is called.

## Result and what it means
* Reclamation rows now defensible from public data: **16 lakes** (plus Cheney via an independent USGS 62614 pairing and the same storage fit). Their datum is a Reclamation **project vertical frame**: shift only, never converted, never named NGVD29/NAVD88 (`SAME_SOURCE`, sigma 0.1 ft).
* The request to Reclamation (`DEPTH_RECLAMATION_DATUM_REQUEST.md`) is narrowed to what this could not settle.
* Method limits: it proves RISE elevation and the pool share a frame to about 0.1 ft; it does not say the frame equals NGVD29. Tier-A survey statements already say that for most of these project datums. Results are time-dependent (drought leaves some printed pairs out of range).
