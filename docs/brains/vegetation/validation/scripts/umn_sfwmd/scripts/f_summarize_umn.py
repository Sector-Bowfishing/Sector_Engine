"""usage: f_summarize_umn.py v1|v1fix -> out/umn_tables_{mode}.md , out/umn_summary_{mode}.json"""
import csv,collections,json,sys,statistics
MODE=sys.argv[1]
NAMES={0:'OFF',2:'FLAG',1:'CLEAR',10:'SHORE_ADJACENT',11:'NO_DATA',12:'CLOUD_SHADOW',13:'HAZE',14:'DARK_WATER',20:'NO_SCENE',21:'PASS_NOT_ACCEPTED'}
R=list(csv.DictReader(open(f'out/umn_point_results_{MODE}.csv')))
for r in R: r['g']=r['groups'].split('|'); r['st']=NAMES[int(r['state'])]; r['gap_i']=None if r['gap'] in('','None') else int(float(r['gap']))
f=lambda x:'n/a' if x is None else f'{x:.2f}'
def agg(rows,cells=False):
    rows=[r for r in rows if r['in_lake']=='True']
    if cells:
        d={}
        for r in rows: d.setdefault((r['lake'],r['date'],r['row'],r['col'],r['sy']),r)
        rows=list(d.values())
    n=len(rows); c=collections.Counter(r['st'] for r in rows); fl=c['FLAG']; cl=c['CLEAR']
    return dict(n=n,flag=fl,clear=cl,recall_known=fl/(fl+cl) if fl+cl else None,recall_all=fl/n if n else None,shore=c['SHORE_ADJACENT']/n if n else None,
      cloud=(c['CLOUD_SHADOW']+c['HAZE']+c['NO_DATA'])/n if n else None,dark=c['DARK_WATER']/n if n else None,noscene=(c['NO_SCENE']+c['PASS_NOT_ACCEPTED'])/n if n else None,
      known=(fl+cl)/n if n else None)
def sel(g,**kw):
    out=[r for r in R if g in r['g']]
    for k,v in kw.items(): out=[r for r in out if r[k]==v]
    return out
L=[]; P=lambda s='':L.append(s); J={}
short=lambda s:s.replace('_MN','').replace('Lake_','').replace('_Lake','')
for g in ['surface_strict','surface_inclusive']:
    P(f'#### {g}: per lake x survey year x scene tier (mode {MODE})'); P()
    P('| lake | survey yr | tier | scene yr | obs | points | recall known (cells FLAG / known) | recall all (unknown+shore = miss) | SHORE_ADJ | cloud/haze/nodata | dark | no scene / not accepted | FLAG/CLEAR | scene gap d (median, max) | persistence |'); P('|'+'---|'*15)
    for lk in sorted({r['lake'] for r in R}):
        for y in sorted({r['date'][:4] for r in R if r['lake']==lk}):
            for tier,sy in sorted({(r['tier'],r['sy']) for r in R if r['lake']==lk and r['date'][:4]==y}):
                for on in 'SAP':
                    rows=[r for r in sel(g,lake=lk,obs=on,tier=tier,sy=sy) if r['date'][:4]==y]
                    a=agg(rows)
                    if a['n']<1: continue
                    gp=[r['gap_i'] for r in rows if r['gap_i'] is not None]
                    gs=f"{statistics.median(gp):.0f}, {max(gp)}" if gp else 'n/a'
                    pers=collections.Counter(r['persist'] for r in rows if on=='P'); 
                    J[f'{g}|{lk}|{y}|{tier}|{sy}|{on}']=a
                    P(f"| {short(lk)} | {y} | {tier} | {sy} | {on} | {a['n']} | {f(a['recall_known'])} ({a['flag']}/{a['flag']+a['clear']}) | {f(a['recall_all'])} | {f(a['shore'])} | {f(a['cloud'])} | {f(a['dark'])} | {f(a['noscene'])} | {a['flag']}/{a['clear']} | {gs} | {dict(pers) if pers else ''} |")
    P()
P('#### Pooled over lakes by scene tier (surface_strict; point-weighted, not lake-weighted; E = scene within +-21 d same year, A = adjacent-year substitute for a 2017/18 survey, N = 2014-16 survey with 2017/2018 scenes, F = pre-2014 survey with 2018 scenes)'); P()
P('| tier | gap | obs | points | recall known | recall all | SHORE_ADJ | cloud/haze/nodata | dark | no scene / not accepted | unique-cell recall known | lakes |'); P('|'+'---|'*12)
for tier,sy_ in [('E','2017'),('E','2018'),('E','*'),('A','2018'),('A','2019'),('N','2017'),('N','2018'),('F','2018')]:
    for gapname,cond in (('<=7 d',lambda r:r['gap_i'] is not None and r['gap_i']<=7),('8-21 d',lambda r:r['gap_i'] is not None and 8<=r['gap_i']<=21),('all',lambda r:True)) if (tier=='E' and sy_=='*') else (('all',lambda r:True),):
        for on in 'SAP':
            rows=[r for r in sel('surface_strict',tier=tier,obs=on) if cond(r) and (sy_=='*' or r['sy']==sy_)]
            a=agg(rows); ac=agg(rows,True)
            if a['n']==0: continue
            J[f'POOL|surface_strict|{tier}|{sy_}|{gapname}|{on}']=a
            P(f"| {tier}/{sy_} | {gapname} | {on} | {a['n']} | {f(a['recall_known'])} ({a['flag']}/{a['flag']+a['clear']}) | {f(a['recall_all'])} | {f(a['shore'])} | {f(a['cloud'])} | {f(a['dark'])} | {f(a['noscene'])} | {f(ac['recall_known'])} ({ac['flag']}/{ac['flag']+ac['clear']}) | {len({r['lake'] for r in rows})} |")
P()
P('#### Submersed-only points (recall of the observer; should be near zero). Groups: all submersed-only; non-canopy-capable-only (e.g. Najas, Vallisneria-excl, small pondweeds); canopy-capable-only (milfoil, coontail, curlyleaf, large pondweeds, elodea)'); P()
P('| group | lake | survey yr | tier | scene yr | obs | points | recall known | recall all | SHORE_ADJ | cloud/haze/nodata | dark | no scene / not accepted | FLAG/CLEAR |'); P('|'+'---|'*14)
for g in ['submersed_only','submersed_noncanopy_only','submersed_canopy_capable_only']:
    for lk in sorted({r['lake'] for r in R}):
        for y in sorted({r['date'][:4] for r in R if r['lake']==lk}):
            for tier,sy in sorted({(r['tier'],r['sy']) for r in R if r['lake']==lk and r['date'][:4]==y}):
                if tier in('A','F') : continue
                for on in 'AP' if False else 'A':
                    rows=[r for r in sel(g,lake=lk,obs=on,tier=tier,sy=sy) if r['date'][:4]==y]; a=agg(rows)
                    if a['n']<20: continue
                    J[f'{g}|{lk}|{y}|{tier}|{sy}|{on}']=a
                    P(f"| {g} | {short(lk)} | {y} | {tier} | {sy} | {on} | {a['n']} | {f(a['recall_known'])} | {f(a['recall_all'])} | {f(a['shore'])} | {f(a['cloud'])} | {f(a['dark'])} | {f(a['noscene'])} | {a['flag']}/{a['clear']} |")
P()
P('#### Submersed-only pooled by lake (observer A and P, all tiers E/N/A; F tier excluded)'); P()
P('| group | lake | obs | points | recall known | recall all | FLAG/CLEAR |'); P('|'+'---|'*7)
for g in ['submersed_only','submersed_noncanopy_only','submersed_canopy_capable_only']:
    for lk in sorted({r['lake'] for r in R}):
        for on in 'AP':
            rows=[r for r in sel(g,lake=lk,obs=on) if r['tier'] in 'ENA']; a=agg(rows)
            if a['n']<20: continue
            J[f'POOLLAKE|{g}|{lk}|{on}']=a
            P(f"| {g} | {short(lk)} | {on} | {a['n']} | {f(a['recall_known'])} | {f(a['recall_all'])} | {a['flag']}/{a['clear']} |")
P()
P('#### Flag share at NO_VEG_FOUND points (INFORMATIONAL absence check; NOT precision/FPR: a rake-null does not rule out floating mats; points near shore are in the SHORE band)'); P()
P('| lake | tier | obs | points | flagged / known | flagged share of known | SHORE_ADJ |'); P('|'+'---|'*7)
for lk in sorted({r['lake'] for r in R}):
    for tier in 'ENA':
        for on in 'AP':
            rows=sel('no_veg_recorded',lake=lk,obs=on,tier=tier); a=agg(rows)
            if a['n']<20: continue
            J[f'NOVEG|{lk}|{tier}|{on}']=a
            P(f"| {short(lk)} | {tier} | {on} | {a['n']} | {a['flag']}/{a['flag']+a['clear']} | {f(a['flag']/(a['flag']+a['clear']) if a['flag']+a['clear'] else None)} | {f(a['shore'])} |")
open(f'out/umn_tables_{MODE}.md','w').write('\n'.join(L)); json.dump(J,open(f'out/umn_summary_{MODE}.json','w'),indent=1)
print('\n'.join(L))
