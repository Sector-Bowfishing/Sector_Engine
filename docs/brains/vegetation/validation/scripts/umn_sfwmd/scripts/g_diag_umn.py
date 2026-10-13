"""Diagnostics: recall (known) of strict-surface points by life form and by recorded depth; tiers E,A,N, observer A, mode v1fix. -> out/umn_diag.md"""
import csv,collections
LK={r['taxon'].strip().lower():r for r in csv.DictReader(open('out/umn_taxon_lifeform_lookup.csv'))}
pt={}
for r in csv.DictReader(open('out/umn_fleet_points.csv')):
    ts=[t.strip().lower() for t in r['taxa'].split(';') if t.strip()]
    lf={LK[t]['life_form'] for t in ts if t in LK and LK[t]['surface_tier']=='STRICT'}
    r['lf']='FLOAT(+/-emerg)' if lf&{'FLOATING_LEAVED','FREE_FLOATING'} else ('EMERGENT-only' if lf else '')
    pt[(r['lake'],r['survey'],r['point'])]=r
R=list(csv.DictReader(open('out/umn_point_results_v1fix.csv')))
def bin_d(d):
    try: d=float(d)
    except: return 'depth n/a'
    return '<=2 ft' if d<=2 else '2-4 ft' if d<=4 else '4-6 ft' if d<=6 else '>6 ft'
out=collections.defaultdict(lambda:collections.Counter())
for r in R:
    if 'surface_strict' not in r['groups'].split('|') or r['obs']!='A' or r['tier'] not in 'ENA' or r['in_lake']!='True': continue
    p=pt[(r['lake'],r['survey'],r['point'])]; st=int(r['state'])
    for key in (('lifeform',p['lf']),('depth',bin_d(p['depth_ft'])),('lake',r['lake'].replace('_MN',''))):
        c=out[key]; c['n']+=1; c['flag']+=st==2; c['clear']+=st==1; c['shore']+=st==10
L=['| split | class | points | recall known | FLAG/known | SHORE_ADJ share |','|---|---|---|---|---|---|']
for (k,v),c in sorted(out.items()):
    kn=c['flag']+c['clear']; L.append(f"| {k} | {v} | {c['n']} | {c['flag']/kn if kn else float('nan'):.2f} | {c['flag']}/{kn} | {c['shore']/c['n']:.2f} |")
open('out/umn_diag.md','w').write('\n'.join(L)); print('\n'.join(L))
