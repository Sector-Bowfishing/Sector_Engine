"""For one lake: search STAC for scenes in the +-21 d windows around every survey reference (exact year) and its labelled substitute years,
cache lean DN windows (B04,B8A,B11,SCL; same-date same-CRS tiles mosaicked), then run the IMPORTED production s2_pass on every scene (50 m cells).
usage: d_fetch_run.py LAKEKEY [fetch|run|both]   cwd = umn_sfwmd/   Output: out/s2cache/{lake}_{date}.npz, out/cells50_{lake}.npz"""
import sys; sys.dont_write_bytecode=True
sys.path.insert(0,'scripts'); sys.path.insert(0,'{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness')
sys.path.insert(0,'{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/scripts')
import json,datetime as dt,collections,os,warnings,numpy as np,rasterio
warnings.filterwarnings('ignore')
from pathlib import Path
from shapely.geometry import shape
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from concurrent.futures import ThreadPoolExecutor
import s2lib
from lakes_cfg import *
lk=sys.argv[1]; mode=sys.argv[2] if len(sys.argv)>2 else 'both'
CACHE=Path('out/s2cache'); CACHE.mkdir(exist_ok=True)
g=json.load(open(f'out/geom/{lk}.geojson')); g=shape(g['features'][0]['geometry'] if 'features' in g else g)
b=g.bounds; bbox=[b[0]-.003,b[1]-.003,b[2]+.003,b[3]+.003]
BANDS={'B04':'red','B8A':'nir08','B11':'swir16'}
def need_dates():
    need=set()
    for d in (FL_CFG[lk]['refs'] if lk in FL_CFG else refs(lk)):
        for sy,t in ([(y,'S') for y in FL_CFG[lk]['years']] if lk in FL_CFG else scene_years(int(d[:4]))):
            r=shift(d,sy)
            for k in range(-21,22): need.add(r+dt.timedelta(days=k))
    return need
def search():
    from pystac_client import Client
    cat=Client.open(s2lib.STAC); need=need_dates(); items=[]
    for sy in sorted({d.year for d in need}):
        ds=[d for d in need if d.year==sy]; coll='sentinel-2-l2a' if sy==2017 else 'sentinel-2-c1-l2a'
        its=list(cat.search(collections=[coll],bbox=bbox,datetime=f"{min(ds)}/{max(ds)}",query={"eo:cloud_cover":{"lt":FL_CFG[lk]['cloud'] if lk in FL_CFG else 80}}).item_collection())
        items+=[i for i in its if i.datetime.date() in set(ds)]
    by=collections.defaultdict(list)
    items=[i for i in items if all(i.assets[a].href.endswith('.tif') for a in ('red','nir08','swir16','scl'))]
    for i in items: by[i.datetime.date()].append(i)
    if lk in FL_CFG:
        keep={}
        for sy in FL_CFG[lk]['years']:
            r=shift(FL_CFG[lk]['refs'][0],sy); ds=sorted([d for d in by if d.year==sy],key=lambda d:abs((d-r).days))[:FL_CFG[lk]['maxdates']]
            for d in ds: keep[d]=by[d]
        by=keep
    return by
def read_date(date,its):
    try: return _read_date(date,its)
    except Exception as e: return str(date),'ERR '+repr(e)[:150]
def _read_date(date,its):
    f=CACHE/f"{lk}_{date}.npz"
    if f.exists(): return f.name,'cached'
    with rasterio.Env(**s2lib.ENV):
        red0=rasterio.open(s2lib.http(its[0].assets['red'].href)); crs=red0.crs
        l,bb,r,t=transform_bounds('EPSG:4326',crs,*bbox)
        win=from_bounds(l,bb,r,t,red0.transform).round_offsets().round_lengths(); tr=red0.window_transform(win); H,W=int(win.height),int(win.width)
        wb=rasterio.windows.bounds(win,red0.transform)
        out={}; 
        for it in its:
            if it.collection_id!=its[0].collection_id: continue
            ro=rasterio.open(s2lib.http(it.assets['red'].href))
            if ro.crs!=crs: continue
            for bn,an in list(BANDS.items())+[('SCL','scl')]:
                src=rasterio.open(s2lib.http(it.assets[an].href)); w_=from_bounds(*wb,src.transform)
                a=src.read(1,window=w_,out_shape=(H,W),resampling=rasterio.enums.Resampling.nearest,boundless=True,fill_value=0)
                if bn not in out: out[bn]=a.astype('uint16' if bn!='SCL' else 'uint8')
                else:
                    z=(out[bn]==0); out[bn][z]=a[z]
        off=-0.1 if its[0].collection_id=='sentinel-2-c1-l2a' else 0.0
    np.savez_compressed(f,**out,transform=np.array(tr)[:6],crs=str(crs),off=off,date=date.isoformat(),ids=np.array([i.id for i in its]))
    return f.name,f.stat().st_size
if mode in('fetch','both'):
    by=search(); print(lk,'dates to read',len(by),flush=True)
    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(lambda kv: read_date(*kv),sorted(by.items())): print(r,flush=True)
if mode in('run','both'):
    import prod_import as P
    dws=P.dws
    fs=sorted(CACHE.glob(f'{lk}_*.npz')); scs=[]
    for f in fs:
        z=np.load(f,allow_pickle=True); off=float(z['off']); tr=rasterio.Affine(*z['transform']); crs=rasterio.crs.CRS.from_string(str(z['crs']))
        scs.append(dict(date=str(z['date']),id=f.stem,tile=P.build_tile(P.raw_to_dn(z['B04'],off),P.raw_to_dn(z['B8A'],off),P.raw_to_dn(z['B11'],off),z['SCL'],tr,crs),crs=crs,coll='l2a' if off==0.0 else 'c1'))
    utm=scs[0]['crs'].to_string(); dws.UTM=utm
    fr=dws.Frame(g,cell=50.0); m=dws.lake_masks(g,fr)
    FIELDS=["read","grass_prod","gfrac","hidden","near","seen_share","nodata_share","cloudscl_share","gfrac_v1","dark_share","glare_share"]
    S=len(scs); out={f:np.zeros((S,fr.height,fr.width),"float32" if f not in("read","grass_prod") else bool) for f in FIELDS}
    rej=np.array([""]*S,dtype=object); err=np.array([""]*S,dtype=object)
    for i,s in enumerate(scs):
        if s['crs'].to_string()!=utm: err[i]='other UTM zone'; continue
        try:
            try: r=P.run_scene(s['id'],s['tile'],fr,m,utm)
            except dws.PassRejected as e: rej[i]=str(e); r=P.run_scene(s['id'],s['tile'],fr,m,utm,gate=False)
            for f in FIELDS: out[f][i]=r[f]
        except Exception as e: err[i]=repr(e)[:200]
        print(lk,s['date'],'rej' if rej[i] else '',err[i],flush=True)
    ok=(err=='')
    np.savez_compressed(f'out/cells50_{lk}.npz',**out,ok=ok,rejected=rej.astype(str),error=err.astype(str),dates=np.array([s['date'] for s in scs]),lake=m['lake'],clarity=m['clarity'],ground_m=fr.cell_ground_m(),cell=50,utm=utm,
        frame=np.array([fr.left,fr.top,fr.width,fr.height,50.0]),collections=np.array([s['coll'] for s in scs]))
