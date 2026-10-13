"""Build docs/brains/depth/DEPTH_POOL_DATUM_DOCUMENT_SWEEP.md from datum_pairings_2.json + the sweep CSV."""
import json, csv, os, collections
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
d = json.load(open(R + '/jobs/depth-brain/depth_brain/data/proposals/datum_pairings_2.json'))['lakes']
grp = {r['lakeId']: r['group'] for r in csv.DictReader(open(R + '/docs/brains/depth/data/depth_datum_unlock_queue.csv'))}
grp['Lake Texoma|TX'] = 'texoma (extra)'
cnt = collections.defaultdict(collections.Counter)
for k, v in d.items(): cnt[grp[k]][v['decision']] += 1
L = []
L.append("""# Depth pool-datum document sweep

Date 2026-10-14. Evidence work only: nothing deployed, no production change, nothing sent. Machine form: `jobs/depth-brain/depth_brain/data/proposals/datum_pairings_2.json` (schema `depth-datum-proposals-v1`). Per-lake CSV: `docs/brains/depth/data/datum_doc_sweep_results.csv`. Scripts: `research/depth/datum_doc_texoma.py`, `datum_doc_merge.py`, `datum_doc_report.py`. Downloads (outside git): `~/Desktop/Development/Sector_Research_Data/depth-brain/datum4/`.

Target: the 58 plausible lakes in `depth_datum_unlock_queue.csv` whose only gap is the datum of the pool figure (RISE, NWPS, Duke excluded). The level side is already fixed (USGS 62614 NGVD29, 62615 NAVD88, CWMS/A2W location stamp). The question per lake was: does a fetched document state the vertical datum of THAT pool figure (or an unambiguous elevation-datum statement covering it)? Four parallel searchers each took about 14 lakes; the lead re-checked conflicts.

Note: the task brief counted about 66 lakes (other-operator 17); the CSV has only 9 plausible `other-operator` rows (37 blocked, 9 plausible), so the target set is 58.

## 1. Result

| Group | Lakes | SAME_DATUM | SAME_SOURCE | INCOMPATIBLE | UNKNOWN |
|---|---|---|---|---|---|""")
tot = collections.Counter()
for g in ['usgs-pairing', 'cwms-pool-datum-unstated', 'a2w-pool-datum-unstated', 'a2w-local-or-blank', 'other-operator', 'conversion-disabled', 'texoma (extra)']:
    c = cnt[g]; n = sum(c.values()); tot.update(c)
    L.append(f"| {g} | {n} | {c['SAME_DATUM']} | {c['SAME_SOURCE']} | {c['INCOMPATIBLE']} | {c['UNKNOWN']} |")
L.append(f"| Total | {sum(tot.values())} | {tot['SAME_DATUM']} | {tot['SAME_SOURCE']} | {tot['INCOMPATIBLE']} | {tot['UNKNOWN']} |")
L.append("""
Texoma is outside the 58 (it is not in the unlock queue). INCOMPATIBLE lakes are not failures: the documents prove the pool and the level are on different datums, and conversion is disabled, so they stay blocked until a conversion rule is adopted or a level on the pool's datum is found.

## 2. Method

1. Re-fetch the manifest `referencePoolSource` and read it for datum words (NGVD, NAVD, "plant datum", "msl").
2. Look for a document that states the datum for the same figure: USGS Water Data Report station entries (datum of gage plus the pool elevation in one entry), FERC notices and licence orders, USACE water control plans and pertinent-data sheets, state reports with datum footnotes, operator pages.
3. For USACE lakes also query CWMS: pool-like level equal to the figure within 0.06 ft, and the stamped `vertical-datum` of that level's location versus the series location.
4. Accept only: explicit datum for the figure; or "all elevations NGVD29" style statements in the same document; or the CWMS value match. Not accepted: "msl", "mean sea level", "above sea level", derived closeness.
5. Level datum vs pool datum differ (NGVD29 vs NAVD88, local datum) -> INCOMPATIBLE, no conversion.

## 3. Document types that worked (SAME_* proposals)

| Document type | Resolved |
|---|---|
| USGS Water Data Report station entry ("datum of gage is ... NGVD of 1929" plus the pool in the same entry) | Great Sacandaga, Wanaque, C.J. Strike, Jordan Lake NC, Bluewater, Billy Chinook, Henrys (derived: gage datum + gage height) |
| CWMS location vertical-datum plus value-matched pool level | Rend Lake, Columbus, Roosevelt, Kissimmee, East Toho (plus SFWMD memo) |
| USACE water control plan / pertinent data stating NGVD29 | Kerr (both lake records), Seminole |
| FERC notices stating "NGVD" for the figure | Cheat Lake, Claytor, Istokpoga (SFWMD MFL report) |
| Operator page with datum on the figure | Smith Mountain, Round Valley (NJWSA, NAVD88) |
| State report with datum footnote | Geist (NAVD88), Eagle Creek and Toledo Bend (incompatible) |
| USGS scientific investigations report | Pend Oreille |

Low yield: USBR project pages, ODNR fishing maps, NRC environmental documents, FERC EAs and most operator pages, which give "msl" or no datum. Wayback was offline during part of the run and several FERC/state PDFs returned 403 (logged per lake in `deadEnds` in the JSON).

## 4. Traps found

* T23 "msl" is not a datum. Hebgen, Greenwood, Chelan, Palisades, Hoover, Ross Barnett, Jackson, Taneycomo, Clinton, Hopatcong, Jordan (AL) are only "msl"/"above sea level".
* T24 Local datums look like elevations: Murray ("plant datum"), Almanor ("PG&E datum"), Coeur d'Alene ("Avista datum"), McConaughy (CNPPD Central datum = 3,266.4 ft NAVD88, so 1.4 ft off), Tahoe (USBR datum 6,229.1 = 6,227.96 ft above sea level, 1.14 ft off the NGVD29 CWMS series). A local datum is SAME_SOURCE at best.
* T25 CWMS stamp vs Corps wording conflict. Mark Twain: CWMS series location is stamped NAVD88 and holds 606.0, but a 2021 Corps update (relayed by the Hannibal Courier-Post) says "Normal lake elevation is 606.0 NGVD". The agent's SAME_DATUM was demoted to UNKNOWN by the lead. Rend Lake has the same structure (project location unstamped, series stamped NAVD88) but no contradicting document was found; it stays SAME_DATUM at medium confidence.
* T26 Manifest figure typo candidate: Lake Wisconsin stored 774.4 while the FERC notice says normal pool 744.4 ft NGVD. Left UNKNOWN; correcting the figure would likely resolve it.
* T27 Missouri mainstem projects are on local project datum / NGVD29 and not converted to NAVD88 (Master Manual), while the USGS 62615 series for Francis Case is NAVD88: INCOMPATIBLE.
* T28 NJWSA switched its reported elevations from NGVD29 to NAVD88 on 2025-11-19. Round Valley (level series NAVD88) is consistent; Spruce Run's pool is NAVD88 while the USGS 62614 series is NGVD29: INCOMPATIBLE.
* T29 Kissimmee's 53 ft is a regulation-schedule zone value (series `Elev-Zone ZoneB1_NGVD`), not a conservation pool; East Toho's level series name points at the Lake Tohopekaliga location (both NGVD29). Medium.
* T30 Derived figures: Henrys Lake 6473.86 is the sum of the WDR gage datum 6457.16 and gage height 16.7, not a printed number.
* T31 The Indiana drought report footnotes differ per reservoir: footnote 3 (NAVD88) sits on Eagle Creek and Geist, footnote 1 (NGVD29) on others; read footnote placement from the table, not the page header.

## 5. Texoma

The TWDB 2002 survey (`Texoma2002_FinalReport.pdf`) states: the vertical datum is that of the USACE lake elevation gauge at Denison Dam, "USCE 07331500 USCOE Lk Texoma nr Denison, TX", "reported as mean sea level (msl)". It does not name NGVD29. The 620.0 ft figure is the survey boundary (USGS quad contour), conservation pool is 617.0 ft. The Brain level is the same gauge (CWMS SWT:DENI, project location stamped NGVD29; levels Top of Constant Conservation 617.0). So the survey elevations are on the gauge scale of the Brain level: SAME_SOURCE, medium, sigma 0.1, re-base to 617.0 (shift 3.0 ft from 620.0). What no document states: that the gauge datum in 2002 was NGVD29 (USGS site record lists NGVD29 only with placeholder altitude 0). Needed to raise to high: a USACE Tulsa pertinent-data sheet for Denison Dam stating NGVD29.

## 6. Per-lake outcome
""")
order = {'SAME_DATUM': 0, 'SAME_SOURCE': 1, 'INCOMPATIBLE': 2, 'UNKNOWN': 3}
L.append("| Lake | Group | Decision | Level / pool datum | Conf | Doc type | Still needed (UNKNOWN) |\n|---|---|---|---|---|---|---|")
for k, v in sorted(d.items(), key=lambda kv: (order[kv[1]['decision']], kv[0])):
    L.append(f"| {k} | {grp[k]} | {v['decision']} | {v.get('levelDatum')} / {v.get('referenceDatum')} | {v.get('confidence')} | {v.get('docType')} | {(v.get('stillNeeds') or '').replace('|','/')[:260]} |")
L.append("""
## 7. What remains blocked, and the resolver

* Operator datum statement needed (USACE districts): Jackson, Palisades, Anderson Ranch, Jordan AL, Lay (APCO), Percy Priest, Bistineau (state/USACE Vicksburg), Ross Barnett (Pearl River Valley WSD), Coeur d'Alene (Avista: offset of Avista datum to NGVD29), Mark Twain (USACE St. Louis: datum of the CWMS series).
* State/operator pages with only "msl": Hebgen, Greenwood, Marion, Murray (Dominion/Santee Cooper plant datum offset), Indian, Buckeye, Hoover, Grand Lake St. Marys (ODNR), D'Arbonne (LDWF), Hopatcong, Clinton, Taneycomo, Rye Patch, Berryessa, Almanor, Cushman, Chelan.
* Monticello: pool is NAVD88 per FERC notice but the USGS 00062 scale is undocumented (USGS Water Science Center or Dominion).
* Lake Wisconsin: correct the manifest figure then re-run.
* INCOMPATIBLE (need a conversion rule or a same-datum level): Tahoe, Spruce Run, Eagle Creek, Toledo Bend, Francis Case.
""")
open(R + '/docs/brains/depth/DEPTH_POOL_DATUM_DOCUMENT_SWEEP.md', 'w').write('\n'.join(L))
