"""Merge the per-chunk document-sweep results (work dir, outside git) into
datum_pairings_2.json and docs/brains/depth/data/datum_doc_sweep_results.csv with strict validation."""
import csv, glob, json, os, re, sys
W = os.path.expanduser('~/Desktop/Development/Sector_Research_Data/depth-brain/datum4/')
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
targets = {t['lakeId']: t for t in json.load(open(W + 'targets.json'))}
lakes, problems = {}, []
for f in sorted(glob.glob(W + 'part_*.json')):
    lakes.update(json.load(open(f))['lakes'])
for k, v in lakes.items():
    d = v['decision']
    if d not in ('SAME_DATUM', 'SAME_SOURCE', 'UNKNOWN', 'INCOMPATIBLE'): problems.append((k, 'bad decision'))
    if d == 'SAME_DATUM' and (v.get('sigmaFt') is None or v['sigmaFt'] < 0.15): v['sigmaFt'] = 0.15
    if d in ('SAME_DATUM', 'SAME_SOURCE'):
        if not v.get('evidence'): problems.append((k, 'no evidence'))
        if str(v.get('levelDatum', '')).upper().startswith('LOCAL') and d == 'SAME_DATUM': problems.append((k, 'LOCAL as SAME_DATUM'))
        if v.get('levelDatum') in ('NGVD29', 'NAVD88') and v.get('referenceDatum') in ('NGVD29', 'NAVD88') and v['levelDatum'] != v['referenceDatum'] and d != 'INCOMPATIBLE':
            problems.append((k, 'datum mismatch not INCOMPATIBLE'))
    for e in v.get('evidence', []):
        if not re.match(r'https?://', e.get('url', '')): problems.append((k, 'bad url ' + e.get('url', '')))
# Lead-level overrides after cross-checking agent results
mt = lakes.get('Mark Twain Lake|MO')
if mt:
    mt.update({'decision': 'UNKNOWN', 'sigmaFt': None, 'referenceDatum': None, 'confidence': 'medium', 'docType': 'cwms-level (conflict)',
      'summary': 'CWMS stamps the series location Mark Twain Lk-Salt NAVD88 and holds 606.0 there, but a Corps lake-level update relayed by the Hannibal Courier-Post states "Normal lake elevation is 606.0 NGVD", so the stamp and the Corps wording conflict for the same 606.0 figure.',
      'stillNeeds': 'USACE St. Louis District (Mark Twain Lake project office / Water Control) statement of the vertical datum of the CWMS Mark Twain Lk-Salt elevation series and of the 606.0 ft conservation pool'})
    mt['evidence'].append({'url': 'https://www.hannibal.net/news/local/mark-twain-lake-level-update/article_dda071bc-f610-11eb-8816-176d34fe72ea.html', 'says': 'Aug 5 2021 Corps update: "The Mark Twain Lake level on Thursday, Aug. 5, was 619.2 NGVD. Normal lake elevation is 606.0 NGVD."'})
    mt['caveat'] = 'Not downgraded for lack of a CWMS match (606.0 matches the project Top of Conservation) but for the NAVD88-vs-NGVD wording conflict; the same check found no such conflict for Rend Lake.'
kl = lakes.get('Kissimmee|FL')
if kl: kl['confidence'] = 'medium'
missing = [k for k in targets if k not in lakes]
out = {"schema": "depth-datum-proposals-v1", "generatedAt": "2026-10-14", "lakes": lakes}
json.dump(out, open(R + '/jobs/depth-brain/depth_brain/data/proposals/datum_pairings_2.json', 'w'), indent=1)
with open(R + '/docs/brains/depth/data/datum_doc_sweep_results.csv', 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['lakeId', 'group', 'decision', 'levelDatum', 'referenceDatum', 'sigmaFt', 'confidence', 'docType', 'evidenceUrls', 'stillNeeds'])
    for k, v in lakes.items():
        w.writerow([k, targets.get(k, {}).get('group', 'texoma-extra'), v['decision'], v.get('levelDatum'), v.get('referenceDatum'), v.get('sigmaFt'), v.get('confidence'), v.get('docType'), ' | '.join(e['url'] for e in v.get('evidence', [])), v.get('stillNeeds', '')])
from collections import Counter
c = Counter((targets.get(k, {}).get('group', 'texoma-extra'), v['decision']) for k, v in lakes.items())
for k in sorted(c): print(k, c[k])
print('problems', problems, 'missing', missing)
