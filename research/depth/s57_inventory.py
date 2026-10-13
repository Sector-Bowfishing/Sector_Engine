"""Compact DSID/DSPM + feature-class inventory + DEPARE/DEPCNT attribute census from the cached S-57 base cells + updates (GDAL S57, UPDATES=APPLY)."""
import os,warnings,collections,pyogrio,pandas as pd,json
warnings.filterwarnings('ignore')
R=os.path.expanduser('~/Desktop/Development/Sector_Research_Data/depth-brain/adoption/s57')
out={}
for c in ['U37TN306','U37TN361','U37TN391']:
    p=f'{R}/{c}/{c}/{c}.000'
    oo={'UPDATES':'APPLY'}
    d=pyogrio.read_dataframe(p,layer='DSID',open_options=oo).iloc[0]
    print('=====',c,{k:d[k] for k in d.index if k.startswith(('DSID_','DSPM_')) and k not in('DSID_COMT','DSPM_COMT','DSID_PSDN')})
    lays=pyogrio.list_layers(p,)
    inv={}
    for name,_ in lays:
        try: n=pyogrio.read_info(p,layer=name,open_options=oo)['features']
        except Exception: n=None
        if n: inv[name]=n
    print('layers with features:',inv)
    for name in ['DEPARE','DEPCNT','SOUNDG','UNSARE','DRGARE','OBSTRN','WRECKS','WATGAUGE','M_SREL','M_ACCY','M_CSCL','SLCONS','LAKARE','RIVERS']:
        if name not in inv: continue
        df=pyogrio.read_dataframe(p,layer=name,open_options=oo)
        cols=[x for x in ['DRVAL1','DRVAL2','VALDCO','QUASOU','SORDAT','SORIND','VERDAT','TECSOU','SOUACC','CATWAT','OBJNAM'] if x in df.columns]
        cnt=collections.Counter(tuple(str(r[x]) for x in cols) for _,r in df.iterrows())
        print('--',name,len(df),cols)
        for k,v in cnt.most_common(12): print('    ',v,k)
