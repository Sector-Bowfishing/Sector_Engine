# Lake Brain: accepted bindings, 2026-11-20 (owner direction)

**Decision.** Michael, 2026-11-20 (Sector_Ops #51 comment 7049169954): every Brain covers every lake; nothing blank. On that direction this batch accepts
every MACHINE_VERIFIED binding in `jobs/lake-brain/data/bindings.proposed.v1.json` (196 rows) into `jobs/lake-brain/data/accepted_batch.json`, except:

- the 5 hand-written pilots (already REVIEWED; hand-written rows take precedence);
- Brookville Lake|IN and Sumner Lake|NM (failed the two-gauge comparison, Sector_Ops #34; stay CANDIDATE);
- every lake in `jobs/lake-brain/review/held_lakes.json` and `bindings.proposed.v1.excluded.json` (none of them is in the proposed table).

**189 lakes accepted.** With the pilots, Lake publishes 194 lakes after the next LakeBrainJob rebuild on Pulse (`--scope pilots` = every REVIEWED binding).

**What this skips.** The pre-registered acceptance rule (`ingest_review_result.py`: a stratified 60-row sample reviewed by Michael, at most 1 error) was
not run. Every row passed the machine checks (binding-review-v1: {'VERIFIED': 192, 'VERIFIED_CORROBORATED': 4}), all
coordinate flags are `ok`, and every provider has an adapter. Accepting means Lake publishes a level STATE for the lake; it does not put the lake on the
customer Lake-level list (`customer_lake_level_eligible.json`), which still gates the customer copy.

**Labels.** Nothing new is claimed. Lake's state carries the binding's capability (DIRECT_OPERATOR_POOL / DIRECT_LAKE_GAUGE), history class and plan
availability exactly as for the pilots; lakes with LIMITED or NONE history get the existing reduced classifications (no VERY_UNUSUAL below 15 years).

**Counts.** Providers: {'a2w': 74, 'rise': 19, 'cwms': 41, 'nwps': 21, 'usgs': 27, 'tva': 7}. History: {'SUFFICIENT': 173, 'NONE': 10, 'LIMITED': 6}. On the customer Lake-level list today: 16 of 189.

| Lake | Live source (provider: station) | Capability | Dam operator (NID) | History years (class) | Guide | On customer list |
|---|---|---|---|---|---|---|
| Abiquiu Lake|NM | a2w: SPA:Abiquiu | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 15 (SUFFICIENT) | zones | no |
| Alcova Reservoir|WY | rise: 114 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 80 (SUFFICIENT) | none | no |
| Allatoona|GA | a2w: SAM:Allatoona | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 20 (SUFFICIENT) | curve | no |
| Alum Creek Lake|OH | a2w: LRH:AlumCr | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 5 (SUFFICIENT) | flood only | no |
| Angostura Reservoir|SD | rise: 106 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 74 (SUFFICIENT) | none | no |
| Arkabutla Lake|MS | cwms: MVK | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 27 (SUFFICIENT) | curve | no |
| Badin Lake|NC | nwps: BADN7 | DIRECT_LAKE_GAUGE | Private | 9 (SUFFICIENT) | none | no |
| Bankhead|AL | cwms: SAM | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 62 (SUFFICIENT) | zones | no |
| Barren River Lake|KY | a2w: LRL:Barren | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Beltzville Lake|PA | a2w: NAP:Beltzville | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| Berlin Lake|OH | a2w: LRP:Berlin | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 9 (SUFFICIENT) | flood only | yes |
| Bighorn Lake|WY | rise: 164 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 60 (SUFFICIENT) | none | yes |
| Bluestone Lake|WV | cwms: LRH | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 13 (SUFFICIENT) | zones | no |
| Box Butte Reservoir|NE | rise: 142 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 28 (SUFFICIENT) | none | no |
| Boysen Reservoir|WY | rise: 196 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 74 (SUFFICIENT) | flood only | yes |
| Branched Oak Lake|NE | cwms: NWDM | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Broken Bow Lake|OK | cwms: SWL | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Buckeye Lake|OH | usgs: 395540082291600 | DIRECT_LAKE_GAUGE | State | 6 (SUFFICIENT) | none | no |
| Burnsville Lake|WV | cwms: LRH | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 13 (SUFFICIENT) | zones | no |
| Caesar Creek Lake|OH | a2w: LRL:CaesarCreek | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Canton Lake|OK | nwps: CNLO2 | DIRECT_LAKE_GAUGE | US Army Corps of Engineers | 15 (SUFFICIENT) | zones | no |
| Canyon Ferry Lake|MT | a2w: NWO:CAFE | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 72 (SUFFICIENT) | flood only | no |
| Carlyle Lake|IL | cwms: MVS | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 60 (SUFFICIENT) | curve | no |
| Carters|GA | a2w: SAM:Carters | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 18 (SUFFICIENT) | flood only | no |
| Cave Run Lake|KY | a2w: LRL:CaveRun | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Cedar Creek Reservoir|TX | a2w: SWF:TRNT2 | DIRECT_OPERATOR_POOL | State | 29 (SUFFICIENT) | flood only | yes |
| Center Hill Lake|TN | a2w: LRN:CEHT1 | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| Chatfield Reservoir|CO | a2w: NWO:CHFI | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 40 (SUFFICIENT) | flood only | no |
| Cheat Lake|WV | usgs: 03071590 | DIRECT_LAKE_GAUGE | Private | 8 (SUFFICIENT) | none | no |
| Cheney Reservoir|KS | rise: 133978 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 33 (SUFFICIENT) | zones | no |
| Cherry Creek Reservoir|CO | a2w: NWO:CHCR | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| Clarks Hill / J.S. Thurmond|GA | usgs: 02193900 | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 68 (SUFFICIENT) | none | no |
| Claytor Lake|VA | cwms: LRH | DIRECT_OPERATOR_POOL | Public Utility | 5 (SUFFICIENT) | none | no |
| Clinton Lake|KS | a2w: NWK:CLIN | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Cochiti Lake|NM | a2w: SPA:Cochiti | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 33 (SUFFICIENT) | zones | no |
| Coeur d'Alene|ID | a2w: NWS:COEI | DIRECT_OPERATOR_POOL | unknown | 8 (SUFFICIENT) | none | no |
| Columbus Lake|MS | usgs: 02441390 | DIRECT_LAKE_GAUGE | US Army Corps of Engineers | 0 (NONE) | none | no |
| Conchas Lake|NM | a2w: SPA:Conchas | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 15 (SUFFICIENT) | zones | no |
| Coralville Lake|IA | a2w: MVR:CRVI4 | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| Crab Orchard Lake|IL | nwps: CODI2 | DIRECT_LAKE_GAUGE | Fish and Wildlife Service | 11 (SUFFICIENT) | none | no |
| Cross Lake|LA | cwms: MVK | DIRECT_OPERATOR_POOL | Local Government | 5 (SUFFICIENT) | none | no |
| Dale Hollow Lake|TN | a2w: LRN:DLHT1 | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| DeGray|AR | a2w: MVK:Degray Lake | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 28 (SUFFICIENT) | flood only | no |
| Deep Creek Lake|MD | usgs: 03075871 | DIRECT_LAKE_GAUGE | Private | 5 (SUFFICIENT) | none | no |
| Don Pedro|CA | cwms: SPK | DIRECT_OPERATOR_POOL | Public Utility | 25 (SUFFICIENT) | flood only | yes |
| Douglas Lake|TN | tva: DUGT1 | DIRECT_OPERATOR_POOL | Tennessee Valley Authority | 0 (NONE) | curve | no |
| Eagle Creek Reservoir|IN | usgs: 03353450 | DIRECT_LAKE_GAUGE | Local Government | 33 (SUFFICIENT) | none | no |
| El Dorado Lake|KS | a2w: SWT:ELDR | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| El Vado Lake|NM | rise: 336 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 51 (SUFFICIENT) | none | no |
| Enid Lake|MS | cwms: MVK | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 27 (SUFFICIENT) | curve | no |
| Eufaula / W.F. George|AL | usgs: 0234296910 | DIRECT_LAKE_GAUGE | US Army Corps of Engineers | 6 (SUFFICIENT) | none | no |
| Falls Lake|NC | a2w: SAW:NEU FLP | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 17 (SUFFICIENT) | flood only | no |
| Fern Ridge Reservoir|OR | a2w: NWP:FRN | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 40 (SUFFICIENT) | zones | no |
| Flannagan Reservoir|VA | nwps: FLAV2 | DIRECT_LAKE_GAUGE | US Army Corps of Engineers | 13 (SUFFICIENT) | zones | no |
| Flathead Lake|MT | a2w: NWS:KER | DIRECT_OPERATOR_POOL | unknown | 86 (SUFFICIENT) | none | yes |
| Fontenelle Reservoir|WY | rise: 349 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 60 (SUFFICIENT) | none | no |
| Fort Gibson Lake|OK | cwms: SWT | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Fort Loudoun Lake|TN | tva: FLDT1 | DIRECT_OPERATOR_POOL | Tennessee Valley Authority | 0 (NONE) | curve | no |
| Fresno Reservoir|MT | rise: 355 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 78 (SUFFICIENT) | none | no |
| Geist Reservoir|IN | usgs: 03351700 | DIRECT_LAKE_GAUGE | Public Utility | 5 (SUFFICIENT) | none | no |
| Grand Lake St. Marys|OH | usgs: 403204084342601 | DIRECT_LAKE_GAUGE | State | 2 (LIMITED) | none | no |
| Grand Lake o' the Cherokees|OK | cwms: SWT | DIRECT_OPERATOR_POOL | State | 8 (SUFFICIENT) | flood only | no |
| Great Sacandaga Lake|NY | usgs: 01323500 | DIRECT_LAKE_GAUGE | State | 96 (SUFFICIENT) | none | no |
| Green River Lake|KY | a2w: LRL:Green | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Greers Ferry|AR | a2w: SWL:GreersFerry_Dam | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 64 (SUFFICIENT) | zones | no |
| Grenada Lake|MS | cwms: MVK | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 27 (SUFFICIENT) | curve | no |
| Gull Lake|MN | a2w: MVP:MissHW_Gull | DIRECT_OPERATOR_POOL | unknown | 8 (SUFFICIENT) | zones | no |
| Havasu|AZ | rise: 6128 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 76 (SUFFICIENT) | none | no |
| Hebgen Lake|MT | usgs: 06038000 | DIRECT_LAKE_GAUGE | Private | 2 (LIMITED) | none | no |
| Herrington Lake|KY | nwps: DIXK2 | DIRECT_LAKE_GAUGE | Private | 15 (SUFFICIENT) | none | no |
| High Rock Lake|NC | nwps: HGRN7 | DIRECT_LAKE_GAUGE | Private | 9 (SUFFICIENT) | none | no |
| Hoover Reservoir|OH | usgs: 03228400 | DIRECT_LAKE_GAUGE | Local Government | 16 (SUFFICIENT) | none | no |
| Hungry Horse Reservoir|MT | a2w: NWS:HGH | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 74 (SUFFICIENT) | flood only | yes |
| Indian Lake|NY | nwps: INDN6 | DIRECT_LAKE_GAUGE | State | 123 (SUFFICIENT) | none | no |
| Indian Lake|OH | usgs: 03260500 | DIRECT_LAKE_GAUGE | State | 2 (LIMITED) | none | no |
| Istokpoga|FL | a2w: SAJ:Lake Istokpoga | DIRECT_OPERATOR_POOL | unknown | 3 (LIMITED) | none | no |
| Jennings Randolph Lake|MD | a2w: NAB:Randolph | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| John Martin Reservoir|CO | a2w: SPA:John Martin | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 27 (SUFFICIENT) | zones | no |
| John Redmond Reservoir|KS | nwps: JRLK1 | DIRECT_LAKE_GAUGE | US Army Corps of Engineers | 15 (SUFFICIENT) | zones | no |
| Jordan Lake|NC | cwms: SAW | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 30 (SUFFICIENT) | none | no |
| Jordan|AL | cwms: SAM | DIRECT_OPERATOR_POOL | Public Utility | 8 (SUFFICIENT) | none | no |
| Kanopolis Lake|KS | a2w: NWK:KANS | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Kaw Lake|OK | nwps: KAWO2 | DIRECT_LAKE_GAUGE | US Army Corps of Engineers | 15 (SUFFICIENT) | zones | no |
| Kerr Lake (John H. Kerr)|NC | cwms: SAW | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 20 (SUFFICIENT) | none | no |
| Kerr Reservoir (Buggs Island)|VA | usgs: 02079490 | DIRECT_LAKE_GAUGE | US Army Corps of Engineers | 15 (SUFFICIENT) | none | no |
| Keyhole Reservoir|WY | rise: 478 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 74 (SUFFICIENT) | flood only | yes |
| Keystone Lake|OK | a2w: SWT:KEYS | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Kissimmee|FL | cwms: SAJ | DIRECT_OPERATOR_POOL | unknown | 4 (LIMITED) | none | no |
| Lake Ashtabula|ND | a2w: MVP:Baldhill_Dam | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 21 (SUFFICIENT) | zones | no |
| Lake Billy Chinook|OR | usgs: 14087520 | DIRECT_LAKE_GAUGE | Private | 20 (SUFFICIENT) | none | no |
| Lake Bistineau|LA | cwms: MVK | DIRECT_OPERATOR_POOL | Local Government | 6 (SUFFICIENT) | none | no |
| Lake Buchanan|TX | cwms: SWF | DIRECT_OPERATOR_POOL | Local Government | 8 (SUFFICIENT) | flood only | no |
| Lake Chelan|WA | a2w: NWS:CHL | DIRECT_OPERATOR_POOL | unknown | 56 (SUFFICIENT) | none | no |
| Lake Conroe|TX | usgs: 08067600 | DIRECT_LAKE_GAUGE | Local Government | 29 (SUFFICIENT) | none | no |
| Lake Cumberland|KY | cwms: LRN | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| Lake Eufaula|OK | a2w: SWT:EUFA | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Lake Fork Reservoir|TX | usgs: 08018800 | DIRECT_LAKE_GAUGE | State | 35 (SUFFICIENT) | none | no |
| Lake Gaston|VA | nwps: GASN7 | DIRECT_LAKE_GAUGE | Public Utility | 0 (NONE) | none | no |
| Lake Greenwood|SC | usgs: 02166500 | DIRECT_LAKE_GAUGE | Local Government | 31 (SUFFICIENT) | none | no |
| Lake Livingston|TX | usgs: 08066190 | DIRECT_LAKE_GAUGE | Public Utility | 27 (SUFFICIENT) | none | no |
| Lake Marion|SC | usgs: 02171000 | DIRECT_LAKE_GAUGE | State | 38 (SUFFICIENT) | none | no |
| Lake Martin|AL | cwms: SAM | DIRECT_OPERATOR_POOL | Public Utility | 8 (SUFFICIENT) | curve | no |
| Lake Milton|OH | cwms: LRP | DIRECT_OPERATOR_POOL | State | 9 (SUFFICIENT) | flood only | yes |
| Lake Mohave|NV | rise: 6133 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 76 (SUFFICIENT) | none | no |
| Lake Monticello|SC | usgs: 02160900 | DIRECT_LAKE_GAUGE | Public Utility | 2 (LIMITED) | none | no |
| Lake Moomaw|VA | nwps: MOOV2 | DIRECT_LAKE_GAUGE | US Army Corps of Engineers | 14 (SUFFICIENT) | flood only | no |
| Lake Moultrie|SC | usgs: 02172000 | DIRECT_LAKE_GAUGE | State | 84 (SUFFICIENT) | none | no |
| Lake Murray (SC)|SC | usgs: 02168500 | DIRECT_LAKE_GAUGE | Public Utility | 96 (SUFFICIENT) | none | no |
| Lake Oahe|SD | cwms: NWDM | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| Lake Pend Oreille|ID | a2w: NWS:HOPI | DIRECT_OPERATOR_POOL | unknown | 27 (SUFFICIENT) | zones | no |
| Lake Red Rock|IA | cwms: MVR | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| Lake Tahoe|NV | cwms: SPK | DIRECT_OPERATOR_POOL | unknown | 11 (SUFFICIENT) | none | no |
| Lake Tawakoni|TX | usgs: 08017400 | DIRECT_LAKE_GAUGE | State | 30 (SUFFICIENT) | none | no |
| Lake Texoma|TX | a2w: SWT:DENI | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Lake Travis|TX | a2w: SWF:MSDT2 | DIRECT_OPERATOR_POOL | Local Government | 8 (SUFFICIENT) | flood only | no |
| Lake Winnebago|WI | usgs: 04082500 | DIRECT_LAKE_GAUGE | unknown | 126 (SUFFICIENT) | none | no |
| Lake Winnibigoshish|MN | a2w: MVP:MissHW_Winni | DIRECT_OPERATOR_POOL | unknown | 8 (SUFFICIENT) | zones | no |
| Lake of the Ozarks|MO | nwps: LKSM7 | DIRECT_LAKE_GAUGE | Private | 15 (SUFFICIENT) | none | no |
| Lanier (Sidney Lanier)|GA | a2w: SAM:Buford | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 20 (SUFFICIENT) | curve | no |
| Laurel River Lake|KY | a2w: LRN:LAPK2 | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| Lay|AL | cwms: SAM | DIRECT_OPERATOR_POOL | Public Utility | 8 (SUFFICIENT) | none | no |
| Leech Lake|MN | a2w: MVP:MissHW_Leech | DIRECT_OPERATOR_POOL | unknown | 8 (SUFFICIENT) | zones | no |
| Lewis and Clark Lake|SD | nwps: GPDN1 | DIRECT_LAKE_GAUGE | US Army Corps of Engineers | 6 (SUFFICIENT) | none | no |
| Liberty Reservoir|MD | nwps: MFEM2 | DIRECT_LAKE_GAUGE | Local Government | 10 (SUFFICIENT) | none | no |
| Melvern Lake|KS | a2w: NWK:MELN | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Merritt Reservoir|NE | rise: 599 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 31 (SUFFICIENT) | none | no |
| Milford Lake|KS | a2w: NWK:MILD | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Moses Lake|WA | cwms: NWDP | DIRECT_OPERATOR_POOL | unknown | 46 (SUFFICIENT) | none | no |
| Mosquito Creek Lake|OH | a2w: LRP:Mosquito | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| Neely Henry|AL | nwps: RGLA1 | DIRECT_LAKE_GAUGE | Public Utility | 15 (SUFFICIENT) | curve | no |
| Nickajack Lake|TN | tva: NKJT1 | DIRECT_OPERATOR_POOL | Tennessee Valley Authority | 0 (NONE) | curve | no |
| Nimrod|AR | a2w: SWL:Nimrod_Dam | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 82 (SUFFICIENT) | zones | no |
| Norfork|AR | a2w: SWL:Norfork_Dam | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 81 (SUFFICIENT) | zones | no |
| Norris Lake|TN | tva: NRST1 | DIRECT_OPERATOR_POOL | Tennessee Valley Authority | 0 (NONE) | curve | no |
| Oconee|GA | nwps: WDMG1 | DIRECT_LAKE_GAUGE | Private | 15 (SUFFICIENT) | none | no |
| Okatibbee Lake|MS | a2w: SAM:Okatibbee | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 14 (SUFFICIENT) | flood only | no |
| Old Hickory Lake|TN | a2w: LRN:OHHT1 | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| Ouachita (L. Ouachita)|AR | cwms: MVK | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 28 (SUFFICIENT) | flood only | no |
| Pactola Reservoir|SD | rise: 675 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 70 (SUFFICIENT) | flood only | yes |
| Patoka Lake|IN | a2w: LRL:Patoka | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | yes |
| Patterson Lake|ND | rise: 305 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 74 (SUFFICIENT) | none | no |
| Percy Priest Lake|TN | a2w: LRN:JPHT1 | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| Perry Lake|KS | a2w: NWK:PERY | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Philpott Lake|VA | a2w: SAW:ROA PLP | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 16 (SUFFICIENT) | flood only | no |
| Pomme de Terre Lake|MO | a2w: NWK:PODT | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Pomona Lake|KS | a2w: NWK:POMA | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Possum Kingdom Lake|TX | cwms: SWF | DIRECT_OPERATOR_POOL | Local Government | 35 (SUFFICIENT) | flood only | yes |
| Priest Lake|ID | nwps: PSLI1 | DIRECT_LAKE_GAUGE | unknown | 81 (SUFFICIENT) | none | no |
| Pueblo Reservoir|CO | cwms: SPA | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 48 (SUFFICIENT) | zones | yes |
| R.D. Bailey Lake|WV | cwms: LRH | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 13 (SUFFICIENT) | zones | no |
| Rathbun Lake|IA | a2w: NWK:RATN | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Raystown Lake|PA | a2w: NAB:Raystown | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| Ross Barnett Reservoir|MS | cwms: MVK | DIRECT_OPERATOR_POOL | State | 8 (SUFFICIENT) | none | no |
| Ross Lake|WA | a2w: NWS:ROS | DIRECT_OPERATOR_POOL | Local Government | 0 (NONE) | zones | no |
| Rough River Lake|KY | a2w: LRL:Rough | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Sam Rayburn Reservoir|TX | a2w: SWF:JSPT2 | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 60 (SUFFICIENT) | flood only | yes |
| Santa Rosa Lake|NM | a2w: SPA:Santa Rosa | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 43 (SUFFICIENT) | zones | no |
| Sardis Lake|MS | cwms: MVK | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 27 (SUFFICIENT) | curve | no |
| Sardis Lake|OK | a2w: SWT:SARD | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Saylorville Lake|IA | a2w: MVR:SAYI4 | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| Scituate Reservoir|RI | nwps: SCIR1 | DIRECT_LAKE_GAUGE | Local Government | 11 (SUFFICIENT) | none | no |
| Seminole|GA | cwms: SAM | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 18 (SUFFICIENT) | zones | no |
| Senecaville Lake|OH | cwms: LRH | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 13 (SUFFICIENT) | zones | no |
| Shadow Mountain Reservoir|CO | rise: 738 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 62 (SUFFICIENT) | none | no |
| Shenango River Lake|PA | a2w: LRP:Shenango | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | flood only | no |
| Skiatook Lake|OK | nwps: SKLO2 | DIRECT_LAKE_GAUGE | US Army Corps of Engineers | 14 (SUFFICIENT) | zones | no |
| Smith (Lewis Smith)|AL | cwms: SAM | DIRECT_OPERATOR_POOL | Public Utility | 8 (SUFFICIENT) | flood only | no |
| South Holston Lake|VA | tva: SHDT1 | DIRECT_OPERATOR_POOL | Tennessee Valley Authority | 0 (NONE) | curve | no |
| Spruce Run Reservoir|NJ | usgs: 01396790 | DIRECT_LAKE_GAUGE | State | 12 (SUFFICIENT) | none | no |
| Stockton Lake|MO | a2w: NWK:STON | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Strawberry Reservoir|UT | rise: 782 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 36 (SUFFICIENT) | none | no |
| Summersville Lake|WV | a2w: LRH:Summersville | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 5 (SUFFICIENT) | zones | no |
| Sutton Lake|WV | cwms: LRH | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 13 (SUFFICIENT) | zones | no |
| Table Rock Lake|MO | a2w: SWL:Table_Rock_Dam | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 69 (SUFFICIENT) | zones | no |
| Tappan Lake|OH | cwms: LRH | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 13 (SUFFICIENT) | zones | no |
| Taylorsville Lake|KY | a2w: LRL:Taylorsville | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Tiber Reservoir (Lake Elwell)|MT | a2w: NWO:TIBR | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 70 (SUFFICIENT) | flood only | yes |
| Tims Ford Lake|TN | tva: TMFT1 | DIRECT_OPERATOR_POOL | Tennessee Valley Authority | 0 (NONE) | curve | no |
| Tohopekaliga (Toho)|FL | cwms: SAJ | DIRECT_OPERATOR_POOL | unknown | 5 (SUFFICIENT) | none | no |
| Topaz Lake|NV | nwps: TOPN2 | DIRECT_LAKE_GAUGE | Public Utility | 25 (SUFFICIENT) | none | no |
| Truman Lake|MO | a2w: NWK:HAST | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
| Ute Lake|NM | nwps: UTEN5 | DIRECT_LAKE_GAUGE | State | 17 (SUFFICIENT) | none | no |
| Waconda Lake|KS | rise: 841 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 58 (SUFFICIENT) | zones | yes |
| Wanaque Reservoir|NJ | usgs: 01386990 | DIRECT_LAKE_GAUGE | State | 21 (SUFFICIENT) | none | no |
| Wappapello Lake|MO | cwms: MVS | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 84 (SUFFICIENT) | zones | no |
| Watts Bar Lake|TN | tva: WBOT1 | DIRECT_OPERATOR_POOL | Tennessee Valley Authority | 0 (NONE) | curve | no |
| West Point|GA | a2w: SAM:WestPoint | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 18 (SUFFICIENT) | curve | no |
| Willard Bay Reservoir|UT | rise: 869 | DIRECT_OPERATOR_POOL | Bureau of Reclamation | 27 (SUFFICIENT) | none | no |
| Wilson Lake|KS | a2w: NWK:WILN | DIRECT_OPERATOR_POOL | US Army Corps of Engineers | 8 (SUFFICIENT) | zones | no |
