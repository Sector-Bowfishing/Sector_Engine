# Wind fleet exposure readiness — all 621 lakes (recomputed 2026-10-13 from the PUBLISHED Lake Registry v1)

**Current geometry asset:** Lake Registry v1 index `gs://sector-lake-registry/registry/lakes.v1.json` (generated 2026-10-13T20:20:54Z, sha256 prefix 8ae465ab2e39; 621 lakes, 592 with NHD-HR shoreline geometry, 29 without) plus its 592 analysis polygons (25 m tolerance). **This replaced the earlier local research copy** (HIGH 351 / MEDIUM 195 / LOW 53 / MISSING 22): the registry's repairs moved 50 lakes MEDIUM→HIGH, 7 lakes to MISSING (large water held back: 16 lakes; no NHD: 13). Polygon fetch was recomputed on all 592 registry polygons (592 of 592 ok; `research/registry_fleet.py`), the audited tables were cross-checked against the registry (`research/audited_vs_registry.py`, `data/audited_vs_registry.json`), and the manifest rebuilt (`python -m sector_wind.brain.fleet build --registry … --audited-check …`). Machine-readable: `data/fleet_exposure_readiness.csv`. Older counts (AUDITED 65 / ESTIMATED 296+167 / 528 eligible) are **superseded**.

## Counts
| Category | Lakes | Meaning |
|---|---:|---|
| AUDITED | 59 | frozen NHD fetch table, SHA-256 verified, QA'd, **and** consistent with the registry polygon |
| ESTIMATED_HIGH_GEOMETRY | 337 | polygon fetch on a HIGH-confidence registry polygon |
| ESTIMATED_MEDIUM_GEOMETRY | 126 | same, MEDIUM confidence |
| LOW_GEOMETRY | 37 | registry polygon with confidence LOW (no bank labels) |
| POINT_ONLY | 9 | HIGH/MEDIUM polygon but fetch not computable at ≤ 40 m raster (very long lakes) |
| NO_GEOMETRY | 28 | registry has no geometry (16 held-large-water incl. Great Lakes; 13 no NHD) |
| BLOCKED | 25 | would be AUDITED/ESTIMATED but a hard blocker withholds all Wind customer output |
Before the BLOCKED overlay: AUDITED 74, ESTIMATED_HIGH 344, ESTIMATED_MEDIUM 129. **Lake IDs that may carry conservative bank wording: 522** (`exposure_allowed`; 59 audited + 463 estimated) — **517 distinct waters**, because 7 groups of directory IDs are the same water (Kentucky Lake KY/TN, Flaming Gorge UT/WY, Clarks Hill GA/SC, Eufaula/W.F. George AL/GA, East Lake Tohopekaliga, …; registry `memberIds`). 614 distinct waters in total.
Blockers among the 25 blocked: nbmAKDomainNotTested ×10, auditedGeometryAreaMismatch ×8, lakeIdentityRisk ×6, nbmHIDomainNotTested ×3, registryGeometryMissing ×1.

## What changed versus the previous recount
1. **Audited lakes now need to agree with the registry.** 15 audited lakes are blocked: 8 by `auditedGeometryAreaMismatch` (registry polygon area / audited feature area outside 0.8–1.25: Andrews DE 0.36, Griffith DE 0.50, Bowdish RI 0.68, Watchaug RI 1.36, Norris TN 1.40, Texoma TX 1.45, Roosevelt AZ 1.53, Neely Henry AL 1.25 marginal), by `lakeIdentityRisk` (6: Andrews, Griffith, Hiwassee, Eagle, Long, Sherman) and by an untested AK/HI domain (Aleknagik, Lake Clark, Waimaluhia, which also has no registry geometry). See `WIND_IDENTITY_RISK_LAKES.md`.
2. Registry geometry **raised** confidence for 50 lakes (more ESTIMATED_HIGH) and **withheld** 7 more (large water).
3. Pilot lakes unaffected: Guntersville, Wheeler, Wilson, Pickwick (AUDITED), Hartwell and Toledo Bend (ESTIMATED_HIGH) remain eligible; so do all 12 lakes of the frozen independent-validation draw.

## Customer eligibility (recommendation; nothing is customer-visible)
- **AUDITED (59):** labels only after paired-bank field validation (modeled).
- **ESTIMATED (463):** tonight wind block only; EXPOSED/PROTECTED words stay internal until independent validation (rule set v2) passes.
- **LOW / NO_GEOMETRY / POINT_ONLY (74):** tonight wind block only, never a bank word, never "Protected".
- **BLOCKED (25):** nothing until the blocker is cleared (Lake Brain owns identity; AK/HI need a regional check).

Legend: A = audited geometry, exposure modeled; E = polygon estimate (matched bank-level checks vs audited passed on the *previous* polygons; independent validation v2 pending); FV = field-validation candidate.

## All lakes
| lakeId | category | geometry (registry) | conf. | fetch | bank labels | tier | eligibility |
|---|---|---|---|---|---|---|---|
| Abiquiu Lake|NM | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Alamo|AZ | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only |
| Alcova Reservoir|WY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Aleknagik|AK | BLOCKED | usgs-nhd-hr/engine-overlap | HIGH | audited | modeled but blocked | none | none until unblocked (nbmAKDomainNotTested) |
| Allatoona|GA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Allegheny Reservoir|PA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Almanor|CA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Alum Creek Lake|OH | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| American Falls Reservoir|ID | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Amistad Reservoir|TX | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Anderson Ranch Reservoir|ID | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Andrews Lake|DE | BLOCKED | usgs-nhd-hr/engine-overlap | LOW | audited | modeled but blocked | none | none until unblocked (lakeIdentityRisk; auditedGeometryAreaMismatch) |
| Angostura Reservoir|SD | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Apache|AZ | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Apopka|FL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Arkabutla Lake|MS | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Assawompset Pond|MA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Badin Lake|NC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Bankhead|AL | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Banks Lake|WA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Bantam Lake|CT | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Barkhamsted Reservoir|CT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Barren River Lake|KY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Bartlett|AZ | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Bay Springs Lake|MS | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Bear Lake|UT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Beaver|AR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Becharof|AK | BLOCKED | usgs-nhd-hr/engine-overlap | HIGH | estimated | modeled but blocked | none | none until unblocked (nbmAKDomainNotTested) |
| Becks Pond|DE | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Beech Fork Lake|WV | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Beltzville Lake|PA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Berlin Lake|OH | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Berryessa|CA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Big Creek Lake|IA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Big Green Lake|WI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Big Lake|AK | BLOCKED | usgs-nhd-hr/engine-overlap | HIGH | estimated | modeled but blocked | none | none until unblocked (nbmAKDomainNotTested) |
| Big Stone Lake|SD | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Bighorn Lake|WY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Bitter Lake|SD | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Black Hawk Lake|IA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Blackshear|GA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Blue Marsh Lake|PA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Blue Mesa Reservoir|CO | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Bluestone Lake|WV | AUDITED | usgs-nhd-hr/engine-overlap | MEDIUM | audited | yes (modeled) | A | FV-candidate |
| Bluewater Lake|NM | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Bowdish Reservoir|RI | BLOCKED | usgs-nhd-hr/engine-overlap | MEDIUM | audited | modeled but blocked | none | none until unblocked (auditedGeometryAreaMismatch) |
| Bowman-Haley Reservoir|ND | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Box Butte Reservoir|NE | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Boysen Reservoir|WY | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Branched Oak Lake|NE | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Broken Bow Lake|OK | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Brookville Lake|IN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Buckeye Lake|OH | AUDITED | usgs-nhd-hr/point-area-fallback | MEDIUM | audited | yes (modeled) | A | FV-candidate |
| Buckhorn Lake|KY | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Budd Lake|NJ | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Buffalo Bill Reservoir|WY | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Bull Shoals Lake|AR | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Burnsville Lake|WV | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Burt Lake|MI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Burton|GA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| C.J. Strike Reservoir|ID | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Caballo Lake|NM | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Caddo Lake|TX | AUDITED | usgs-nhd-hr/engine-overlap | MEDIUM | audited | yes (modeled) | A | FV-candidate |
| Caesar Creek Lake|OH | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Cagles Mill Lake|IN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Calamus Reservoir|NE | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Calcasieu Lake|LA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Canandaigua Lake|NY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Candlewood Lake|CT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Canton Lake|OK | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Canyon Ferry Lake|MT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Canyon Lake|TX | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Canyon|AZ | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Carlyle Lake|IL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Carters|GA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Caspian Lake|VT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Castle Rock Lake|WI | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Catahoula Lake|LA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Catherine|AR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Cave Run Lake|KY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Cayuga Lake|NY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Cecil M. Harden Lake|IN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Cedar Bluff Reservoir|KS | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Cedar Creek Reservoir|TX | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Center Hill Lake|TN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Chain O'Lakes|IL | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Chamberlain Lake|ME | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Chatfield Reservoir|CO | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Chautauqua Lake|NY | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Cheat Lake|WV | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Cheney Reservoir|KS | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Cherokee Lake|TN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Cherry Creek Reservoir|CO | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Chesuncook Lake|ME | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Chickahominy Lake|VA | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Chickamauga Lake|TN | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Chicot|AR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| China Lake|ME | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Chippewa Flowage|WI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Clarks Hill / J.S. Thurmond|GA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Claytor Lake|VA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Clear Lake|CA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Clear Lake|IA | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Clearwater Lake|MO | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Clinton Lake|IL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Clinton Lake|KS | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Cochiti Lake|NM | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Coeur d'Alene|ID | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Columbus Lake|MS | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Conchas Lake|NM | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Concord Pond|DE | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Congamond Lakes|MA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Conneaut Lake|PA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Conowingo Reservoir|MD | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Coralville Lake|IA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Coventry Lake (Wangumbaug)|CT | AUDITED | usgs-nhd-hr/engine-overlap | MEDIUM | audited | yes (modeled) | A | FV-candidate |
| Crab Orchard Lake|IL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Cranberry Lake|NY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Crater Lake|OR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Crescent Lake|FL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Crescent Lake|OR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Cross Lake|LA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Crystal Lake|VT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Culvers Lake|NJ | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Dale Hollow Lake|TN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Damariscotta Lake|ME | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Dardanelle|AR | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| DeGray|AR | AUDITED | usgs-nhd-hr/engine-overlap | MEDIUM | audited | yes (modeled) | A | FV-candidate |
| Deep Creek Lake|MD | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Deer Creek Reservoir|UT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Detroit Lake|OR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Devil's Kitchen Lake|IL | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Devils Lake|ND | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Diamond Lake|OR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Dillon Reservoir|CO | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Don Pedro|CA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Douglas Lake|TN | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Douthat Lake|VA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Dworshak Reservoir|ID | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Eagle Creek Reservoir|IN | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Eagle Lake|CA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Eagle Lake|MS | BLOCKED | usgs-nhd-hr/engine-overlap | LOW | audited | modeled but blocked | none | none until unblocked (lakeIdentityRisk) |
| Eagle Nest Lake|NM | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| East Lake Tohopekaliga|FL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| East Lynn Lake|WV | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| East Okoboji|IA | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| El Dorado Lake|KS | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| El Vado Lake|NM | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Elephant Butte Reservoir|NM | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Eleven Mile Reservoir|CO | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Elk Lake|MI | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Enemy Swim Lake|SD | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Enid Lake|MS | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Eufaula / W.F. George|AL | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Falcon Lake|TX | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Falls Lake|NC | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| False River|LA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Fern Ridge Reservoir|OR | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| First Connecticut Lake|NH | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Fish Lake|UT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Flagstaff Lake|ME | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Flaming Gorge Reservoir|UT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Flaming Gorge Reservoir|WY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Flannagan Reservoir|VA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Flat River Res. (Johnson's Pond)|RI | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Flathead Lake|MT | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Folsom|CA | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Fontana Lake|NC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Fontenelle Reservoir|WY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Fort Gibson Lake|OK | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Fort Loudoun Lake|TN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Fort Peck Lake|MT | POINT_ONLY | usgs-nhd-hr/engine-overlap | HIGH | no | no | none | tonight only |
| Fox Lake|IL | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Fresno Reservoir|MT | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Gardner Lake|CT | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Garrisons Lake|DE | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Geist Reservoir|IN | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Georgetown Lake|MT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Glendo Reservoir|WY | AUDITED | usgs-nhd-hr/engine-overlap | MEDIUM | audited | yes (modeled) | A | FV-candidate |
| Grand Lake St. Marys|OH | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Grand Lake o' the Cherokees|OK | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Grand Lake|CO | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Grand Lake|LA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Great East Lake|NH | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Great Pond (Belgrade)|ME | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Great Sacandaga Lake|NY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Great Salt Lake|UT | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Green Bay|WI | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Green River Lake|KY | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Greenwood Lake|NJ | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Greers Ferry|AR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Grenada Lake|MS | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Griffin|FL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Griffith Lake|DE | BLOCKED | usgs-nhd-hr/engine-overlap | LOW | audited | modeled but blocked | none | none until unblocked (lakeIdentityRisk; auditedGeometryAreaMismatch) |
| Gull Lake|MI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Gull Lake|MN | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Guntersville|AL | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Halulu Lake (Niihau)|HI | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (nbmHIDomainNotTested; lakeIdentityRisk) |
| Hamilton|AR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Harding|AK | BLOCKED | usgs-nhd-hr/engine-overlap | HIGH | estimated | modeled but blocked | none | none until unblocked (nbmAKDomainNotTested) |
| Harlan County Lake|NE | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Harriman Reservoir (Whitingham)|VT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Harris|FL | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Harveys Lake|PA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Havasu|AZ | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Hebgen Lake|MT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Henderson Lake|LA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Henrys Lake|ID | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Heron Lake|NM | AUDITED | usgs-nhd-hr/engine-overlap | MEDIUM | audited | yes (modeled) | A | FV-candidate |
| Herrington Lake|KY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Higgins Lake|MI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| High Rock Lake|NC | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Highland Lake|CT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Hiwassee Lake|NC | BLOCKED | usgs-nhd-hr/engine-overlap | LOW | audited | modeled but blocked | none | none until unblocked (lakeIdentityRisk) |
| Holter Lake|MT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Hoover Reservoir|OH | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Horsetooth Reservoir|CO | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Houghton Lake|MI | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Hungry Horse Reservoir|MT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Iliamna|AK | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only (nbmAKDomainNotTested) |
| Indian Lake|NY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Indian Lake|OH | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Isabella|CA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Istokpoga|FL | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Jackson Lake|WY | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Jamestown Reservoir|ND | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Jennings Randolph Lake|MD | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Jenny Lake|WY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Jesup|FL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| John Martin Reservoir|CO | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| John Redmond Reservoir|KS | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Johnson Lake|NE | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Jordan Lake|NC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Jordanelle Reservoir|UT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Jordan|AL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Kanopolis Lake|KS | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Kaw Lake|OK | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Kenai|AK | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (nbmAKDomainNotTested; lakeIdentityRisk) |
| Kentucky Lake|KY | POINT_ONLY | usgs-nhd-hr/engine-overlap | HIGH | no | no | none | tonight only |
| Kentucky Lake|TN | POINT_ONLY | usgs-nhd-hr/engine-overlap | HIGH | no | no | none | tonight only |
| Kerr Lake (John H. Kerr)|NC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Kerr Reservoir (Buggs Island)|VA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Keuka Lake|NY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Keyhole Reservoir|WY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Keystone Lake|OK | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Killens Pond|DE | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Kissimmee|FL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Koele ponds (Lanai)|HI | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only (nbmHIDomainNotTested) |
| Kvichak / Ugashik|AK | BLOCKED | usgs-nhd-hr/engine-overlap | HIGH | estimated | modeled but blocked | none | none until unblocked (nbmAKDomainNotTested) |
| Lac Courte Oreilles|WI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lahontan Reservoir|NV | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Absegami|NJ | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Lake Anna|VA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Arthur|PA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Ashtabula|ND | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Barkley|KY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Bemidji|MN | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Billy Chinook|OR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Bistineau|LA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Bomoseen|VT | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Lake Buchanan|TX | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Carmi|VT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Cascade|ID | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Champlain|VT | POINT_ONLY | usgs-nhd-hr/engine-overlap | HIGH | no | no | none | tonight only |
| Lake Charlevoix|MI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Chelan|WA | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Lake Chesdin|VA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Clark|AK | BLOCKED | usgs-nhd-hr/engine-overlap | HIGH | audited | modeled but blocked | none | none until unblocked (nbmAKDomainNotTested) |
| Lake Cochituate|MA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Conroe|TX | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Crescent|WA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Cumberland|KY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Cushman|WA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake D'Arbonne|LA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Darling|ND | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Dunmore|VT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Erie|MI | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Lake Erie|NY | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Lake Erie|OH | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Lake Erie|PA | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Lake Eufaula|OK | AUDITED | usgs-nhd-hr/engine-overlap | MEDIUM | audited | yes (modeled) | A | FV-candidate |
| Lake Fork Reservoir|TX | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Francis Case|SD | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Freeman|IN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Gaston|VA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Geneva|WI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake George|FL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake George|NY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Gogebic|MI | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Lake Granby|CO | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Greenwood|SC | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Habeeb (Rocky Gap)|MD | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Hartwell|SC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Hickory|NC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Hopatcong|NJ | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Hudson|OK | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Huron|MI | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Lake James|NC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Jocassee|SC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Keowee|SC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Koocanusa|MT | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Lillinonah|CT | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Lake Livingston|TX | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Macbride|IA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Marburg|PA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Marion|SC | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Lake Martin|AL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Mary|AZ | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Lake Mattamuskeet|NC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Maurepas|LA | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Lake McConaughy|NE | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Lake Mead|NV | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Lake Memphremagog|VT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Mendota|WI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Metigoshe|ND | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Michigan|IN | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Lake Michigan|MI | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Lake Michigan|WI | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Lake Milton|OH | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Minnetonka|MN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Mohave|NV | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Monona|WI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Monticello|SC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Moomaw|VA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Moultrie|SC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Murray (OK)|OK | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Lake Murray (SC)|SC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Nockamixon|PA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Norman|NC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Oahe|ND | POINT_ONLY | usgs-nhd-hr/engine-overlap | HIGH | no | no | none | tonight only |
| Lake Oahe|SD | POINT_ONLY | usgs-nhd-hr/engine-overlap | HIGH | no | no | none | tonight only |
| Lake Ogallala|NE | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Lake Ontario|NY | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Lake Owyhee|OR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Pend Oreille|ID | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Pepin|MN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Petenwell|WI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Poinsett|SD | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Pontchartrain|LA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Powell|UT | POINT_ONLY | usgs-nhd-hr/engine-overlap | HIGH | no | no | none | tonight only |
| Lake Quinault|WA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Quinsigamond|MA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Red Rock|IA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Robinson|SC | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Lake Roosevelt (FDR)|WA | POINT_ONLY | usgs-nhd-hr/engine-overlap | HIGH | no | no | none | tonight only |
| Lake Russell (R.B. Russell)|GA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Sakakawea|ND | POINT_ONLY | usgs-nhd-hr/engine-overlap | HIGH | no | no | none | tonight only |
| Lake Sammamish|WA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Seymour|VT | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Lake Shafer|IN | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Lake Sharpe|SD | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Shelbyville|IL | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Lake Springfield|IL | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake St. Catherine|VT | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake St. Clair|MI | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Strom Thurmond (Clarks Hill)|SC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Superior|MI | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Lake Superior|MN | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Lake Superior|WI | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Lake Tahoe|NV | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Taneycomo|MO | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Tawakoni|TX | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Tenkiller|OK | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Texoma|TX | BLOCKED | usgs-nhd-hr/engine-overlap | MEDIUM | audited | modeled but blocked | none | none until unblocked (auditedGeometryAreaMismatch) |
| Lake Thompson|SD | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Travis|TX | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Tschida|ND | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Lake Union|WA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Vermilion|MN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Waccamaw|NC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Waiau|HI | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only (nbmHIDomainNotTested) |
| Lake Wallenpaupack|PA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Waramaug|CT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Washington|MS | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Lake Washington|WA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Wateree|SC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Wawasee|IN | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Lake Wentworth|NH | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Willoughby|VT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Winnebago|WI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Winnibigoshish|MN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Winnipesaukee|NH | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Winnisquam|NH | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Wisconsin|WI | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Lake Wylie|SC | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake Zoar|CT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lake of Egypt|IL | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Lake of the Ozarks|MO | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Lake of the Woods|MN | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Lanier (Sidney Lanier)|GA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Laurel River Lake|KY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lay|AL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Leech Lake|MN | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Lewis and Clark Lake|SD | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Liberty Reservoir|MD | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Loch Raven Reservoir|MD | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lochloosa|FL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Logan Martin|AL | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Long Lake|ME | BLOCKED | usgs-nhd-hr/engine-overlap | LOW | audited | modeled but blocked | none | none until unblocked (lakeIdentityRisk) |
| Long Pond (Lakeville)|MA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Longview Lake|MO | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Lucky Peak Lake|ID | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Lums Pond|DE | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Malheur Lake|OR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Manasquan Reservoir|NJ | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Mansfield Hollow Lake|CT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Marion Reservoir|KS | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Mark Twain Lake|MO | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Massabesic Lake|NH | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Melvern Lake|KS | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Merrill Creek Reservoir|NJ | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Merritt Reservoir|NE | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Merrymeeting Lake|NH | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Milford Lake|KS | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Mille Lacs Lake|MN | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Millwood|AR | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Mississinewa Lake|IN | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Monksville Reservoir|NJ | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Mono|CA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Monroe Lake|IN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Moon Lake|MS | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Moosehead Lake|ME | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Mooselookmeguntic Lake|ME | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Moses Lake|WA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Mosquito Creek Lake|OH | AUDITED | usgs-nhd-hr/engine-overlap | MEDIUM | audited | yes (modeled) | A | FV-candidate |
| Mount Storm Lake|WV | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Mullett Lake|MI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Naknek|AK | BLOCKED | usgs-nhd-hr/engine-overlap | HIGH | estimated | modeled but blocked | none | none until unblocked (nbmAKDomainNotTested) |
| Navajo Reservoir|NM | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Neely Henry|AL | BLOCKED | usgs-nhd-hr/engine-overlap | HIGH | audited | modeled but blocked | none | none until unblocked (auditedGeometryAreaMismatch) |
| Nelson Lake|ND | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Newfound Lake|NH | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Nickajack Lake|TN | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Nimrod|AR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Ninigret Pond|RI | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Nolin River Lake|KY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Norfork|AR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Norris Lake|TN | BLOCKED | usgs-nhd-hr/engine-overlap | HIGH | audited | modeled but blocked | none | none until unblocked (auditedGeometryAreaMismatch) |
| Nuuanu Reservoir|HI | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only (nbmHIDomainNotTested) |
| Oconee|GA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Odell Lake|OR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Okatibbee Lake|MS | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Okeechobee|FL | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Old Hickory Lake|TN | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Oneida Lake|NY | AUDITED | usgs-nhd-hr/engine-overlap | MEDIUM | audited | yes (modeled) | A | FV-candidate |
| Onota Lake|MA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Oologah Lake|OK | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Orange Lake|FL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Oroville|CA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Ossipee Lake|NH | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Otis Reservoir|MA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Otter Tail Lake|MN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Ouachita (L. Ouachita)|AR | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Owasco Lake|NY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Pachaug Pond|CT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Pactola Reservoir|SD | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Palisades Reservoir|ID | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Pascoag Reservoir|RI | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Pathfinder Reservoir|WY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Patoka Lake|IN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Patterson Lake|ND | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Payette Lake|ID | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Percy Priest Lake|TN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Perry Lake|KS | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Philpott Lake|VA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Pickwick Lake|TN | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Pineview Reservoir|UT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Piney Run Lake|MD | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Pleasant|AZ | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Point Judith Pond|RI | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only |
| Pomme de Terre Lake|MO | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Pomona Lake|KS | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Pontoosuc Lake|MA | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Possum Kingdom Lake|TX | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Potholes Reservoir|WA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Prettyboy Reservoir|MD | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Priest Lake|ID | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Pueblo Reservoir|CO | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Puu Loa Reservoir|HI | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only (nbmHIDomainNotTested) |
| Pymatuning Reservoir|PA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Pyramid Lake|NV | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Quabbin Reservoir|MA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| R.D. Bailey Lake|WV | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Rainy Lake|MN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Rangeley Lake|ME | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Rathbun Lake|IA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Raystown Lake|PA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Records Pond|DE | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Red Lake|MN | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Red Mill Pond|DE | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Redfish Lake|ID | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Reelfoot Lake|TN | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Rend Lake|IL | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Rice Lake|IL | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Riffe Lake|WA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Rocky Gorge Reservoir|MD | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Roosevelt|AZ | BLOCKED | usgs-nhd-hr/engine-overlap | MEDIUM | audited | modeled but blocked | none | none until unblocked (auditedGeometryAreaMismatch) |
| Ross Barnett Reservoir|MS | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Ross Lake|WA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Rough River Lake|KY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Round Valley Reservoir|NJ | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Ruby Lake|NV | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only |
| Ruedi Reservoir|CO | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Rye Patch Reservoir|NV | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Sabine Lake|LA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Saguaro|AZ | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Salamonie Lake|IN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Salt Fork Lake|OH | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Salton Sea|CA | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Sam Rayburn Reservoir|TX | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| San Carlos|AZ | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Sangchris Lake|IL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Santa Rosa Lake|NM | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only |
| Sardis Lake|MS | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Sardis Lake|OK | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Savage River Reservoir|MD | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Saylorville Lake|IA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Schoodic Lake|ME | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Scituate Reservoir|RI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Sebago Lake|ME | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Sebec Lake|ME | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Seminoe Reservoir|WY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Seminole|GA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Seneca Lake|NY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Senecaville Lake|OH | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Sevier Lake|UT | AUDITED | usgs-nhd-hr/engine-overlap | LOW | audited | yes (modeled) | A | FV-candidate |
| Shadow Mountain Reservoir|CO | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Shasta|CA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Shenango River Lake|PA | AUDITED | usgs-nhd-hr/engine-overlap | MEDIUM | audited | yes (modeled) | A | FV-candidate |
| Sheridan Lake|SD | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Sherman Reservoir|NE | BLOCKED | usgs-nhd-hr/engine-overlap | LOW | audited | modeled but blocked | none | none until unblocked (lakeIdentityRisk) |
| Silver Lake (Dover)|DE | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Sinclair|GA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Skaneateles Lake|NY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Skiatook Lake|OK | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Skilak|AK | BLOCKED | usgs-nhd-hr/point-name-fallback | MEDIUM | estimated | modeled but blocked | none | none until unblocked (nbmAKDomainNotTested) |
| Smith (Lewis Smith)|AL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Smith Mountain Lake|VA | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Smithville Lake|MO | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Somerset Reservoir|VT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| South Holston Lake|VA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Spirit Lake|IA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Spruce Run Reservoir|NJ | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Squam Lake|NH | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Squantz Pond|CT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Stafford Pond|RI | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Starvation Reservoir|UT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Stockton Lake|MO | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Stonewall Jackson Lake|WV | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Storm Lake|IA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Strawberry Reservoir|UT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Stump Lake|ND | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Summersville Lake|WV | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Sumner Lake|NM | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Sunapee Lake|NH | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Sutherland Reservoir|NE | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Suttle Lake|OR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Sutton Lake|WV | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Swanson Reservoir|NE | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Swartswood Lake|NJ | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Table Rock Lake|MO | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Tappan Lake|OH | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Taylorsville Lake|KY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Teshekpuk|AK | BLOCKED | usgs-nhd-hr/engine-overlap | HIGH | estimated | modeled but blocked | none | none until unblocked (nbmAKDomainNotTested) |
| Tiber Reservoir (Lake Elwell)|MT | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Timothy Lake|OR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Tims Ford Lake|TN | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Tiogue Lake|RI | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Tippecanoe Lake|IN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Tohopekaliga (Toho)|FL | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Toledo Bend Reservoir|TX | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Topaz Lake|NV | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Torch Lake|MI | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Trap Pond|DE | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Triadelphia Reservoir|MD | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Trinity|CA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Truman Lake|MO | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Tustumena|AK | BLOCKED | usgs-nhd-hr/engine-overlap | HIGH | estimated | modeled but blocked | none | none until unblocked (nbmAKDomainNotTested) |
| Tuttle Creek Lake|KS | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Tygart Lake|WV | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Umbagog Lake|NH | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Upper Klamath Lake|OR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Utah Lake|UT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Ute Lake|NM | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Wachusett Reservoir|MA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Waconda Lake|KS | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Wagamons Pond|DE | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Waiakea Pond|HI | NO_GEOMETRY | none/- | MISSING | no | no | none | tonight only (nbmHIDomainNotTested) |
| Waimaluhia Reservoir|HI | BLOCKED | none/- | MISSING | audited | modeled but blocked | none | none until unblocked (nbmHIDomainNotTested; registryGeometryMissing) |
| Waita Reservoir|HI | BLOCKED | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | modeled but blocked | none | none until unblocked (nbmHIDomainNotTested) |
| Waldo Lake|OR | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Walker Lake|NV | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Wallowa Lake|OR | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Wallum Lake|RI | LOW_GEOMETRY | usgs-nhd-hr/engine-overlap | LOW | estimated | no | none | tonight only (lakeIdentityRisk) |
| Walter F. George / Eufaula|GA | AUDITED | usgs-nhd-hr/engine-overlap | MEDIUM | audited | yes (modeled) | A | FV-candidate |
| Wanaque Reservoir|NJ | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Wappapello Lake|MO | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Washoe Lake|NV | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Watchaug Pond|RI | BLOCKED | usgs-nhd-hr/engine-overlap | HIGH | audited | modeled but blocked | none | none until unblocked (auditedGeometryAreaMismatch) |
| Watts Bar Lake|TN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Watuppa Ponds|MA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Waubay Lake|SD | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Webster Lake|MA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Weiss|AL | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| West Grand Lake|ME | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| West Okoboji|IA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| West Point|GA | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Wheeler|AL | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| White Bear Lake|MN | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| White Lake|LA | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Whitefish Lake|MT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Wild Horse Reservoir|NV | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Willard Bay Reservoir|UT | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Wilson Lake / Kaelepulu Pond|HI | BLOCKED | usgs-nhd-hr/point-name-fallback | MEDIUM | estimated | modeled but blocked | none | none until unblocked (nbmHIDomainNotTested) |
| Wilson Lake|KS | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Wilson|AL | AUDITED | usgs-nhd-hr/engine-overlap | HIGH | audited | yes (modeled) | A | FV-candidate |
| Winnapaug Pond|RI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Worden Pond|RI | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Yellow Creek Lake|PA | ESTIMATED_MEDIUM_GEOMETRY | usgs-nhd-hr/engine-overlap | MEDIUM | estimated | yes (modeled) | E | tonight only; labels internal |
| Yellowstone Lake|WY | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
| Youghiogheny River Lake|MD | ESTIMATED_HIGH_GEOMETRY | usgs-nhd-hr/engine-overlap | HIGH | estimated | yes (modeled) | E | tonight only; labels internal |
