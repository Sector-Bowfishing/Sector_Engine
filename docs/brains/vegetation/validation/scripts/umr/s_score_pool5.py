"""Score production-style surface observer (derive_water_surface.py cell rule) against UMRS 2015 Pool 5 drawdown LCU polygons.
Scene year is a LABELLED SUBSTITUTE (no S2 L2A exists in Earth Search for Jun-Sep 2015). Research only."""
import sys,json,math,numpy as np,rasterio,warnings,collections
from rasterio.windows import from_bounds,Window
from rasterio.features import rasterize
from rasterio import Affine
from scipy import ndimage
from shapely import wkb
from pyogrio.raw import read
from pystac_client import Client
warnings.filterwarnings('ignore')
YEAR=int(sys.argv[1]) if len(sys.argv)>1 else 2018
REF=f"{YEAR}-08-12"; import datetime as dt
refd=dt.date.fromisoformat(REF)
OUT='experiments/adoption/umr/out/'
meta,fid,geom,fields=read('sources/umrs_landcover/pool5_dd_2015/x/lc_2015_p5dd/lc_2015_p5dd.shp')
F=dict(zip(meta['fields'],fields)); geoms=[wkb.loads(g) for g in geom]
cls=np.array(F['CLASS_31_C'],dtype=object); lw=np.array(F['LAND_WATER'],dtype=object)
minx=min(g.bounds[0] for g in geoms);miny=min(g.bounds[1] for g in geoms);maxx=max(g.bounds[2] for g in geoms);maxy=max(g.bounds[3] for g in geoms)
L=math.floor(minx/100)*100;B=math.floor(miny/100)*100;R=math.ceil(maxx/100)*100;T=math.ceil(maxy/100)*100
W10=int((R-L)/10);H10=int((T-B)/10); tr10=Affine(10,0,L,0,-10,T)
codes={c:i+1 for i,c in enumerate(sorted(set(cls)))}
shapes=[(g,codes[c]) for g,c in zip(geoms,cls)]
lab10=rasterize(shapes,out_shape=(H10,W10),transform=tr10,fill=0,dtype='uint8',all_touched=False)
inv={v:k for k,v in codes.items()}
isc=lambda *cs: np.isin(lab10,[codes[c] for c in cs if c in codes])
water_cls=set(c for c,l in zip(cls,lw) if l=='Water')
print('Water classes',sorted(water_cls))
# 50 m cell fractions
def cellfrac(m): return m.reshape(H10//5,5,W10//5,5).mean(axis=(1,3))
cov=cellfrac(lab10>0)
f_rf=cellfrac(isc('Rf')); f_dm=cellfrac(isc('Dma','Dmp')); f_sm=cellfrac(isc('Sma','Smp')); f_ow=cellfrac(isc('Ow')); f_sv=cellfrac(isc('Sv'))
f_water=cellfrac(np.isin(lab10,[codes[c] for c in water_cls]))
# shore distance (m) from non-water within coverage or outside coverage, computed at 10 m
nonwater=~np.isin(lab10,[codes[c] for c in water_cls])
dist10=ndimage.distance_transform_edt(~nonwater)*10  # for water px distance to nearest non-water
dist_cell=cellfrac(dist10)  # mean
shore_d=np.where(f_water>=0.9,dist_cell,np.nan)
pos_all=(f_rf+f_dm)>=0.5
pos_rf=f_rf>=0.5
neg_ow=(f_ow>=0.9)
neg_owsv=((f_ow+f_sv)>=0.9)
# --- S2 ---
cat=Client.open("https://earth-search.aws.element84.com/v1")
d0=(refd-dt.timedelta(days=21)).isoformat();d1=(refd+dt.timedelta(days=21)).isoformat()
coll='sentinel-2-c1-l2a' if YEAR>=2018 else 'sentinel-2-l2a'
bbox_ll=[-91.96,44.17,-91.82,44.31]
items=sorted(cat.search(collections=[coll],bbox=bbox_ll,datetime=f"{d0}/{d1}").item_collection(),key=lambda i:i.datetime)
print(coll,len(items),'items')
ENV=dict(AWS_NO_SIGN_REQUEST="YES",GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",GDAL_HTTP_MAX_RETRY="4",GDAL_HTTP_RETRY_DELAY="2")
def http(h):
    if h.startswith('s3://'):
        b,k=h[5:].split('/',1); return f"/vsicurl/https://{b}.s3.us-west-2.amazonaws.com/{k}"
    return '/vsicurl/'+h
def rho(a,item,asset):
    sc=item.assets[asset].extra_fields.get('raster:bands',[{}])[0]
    scale=sc.get('scale',1e-4); off=sc.get('offset',-0.1 if item.collection_id=='sentinel-2-c1-l2a' else 0.0)
    if item.collection_id=='sentinel-2-l2a': off=0.0
    r=a.astype('float32')*scale+off; r[a==0]=np.nan; return r
def edge_dist(mask,px): return ndimage.distance_transform_edt(~mask)*px if mask.any() else np.full(mask.shape,1e6)
scenes=[]
with rasterio.Env(**ENV):
    for it in items:
        try:
            s=rasterio.open(http(it.assets['scl'].href))
            if str(s.crs).upper() not in('EPSG:32615',): continue
            win=from_bounds(L,B,R,T,s.transform).round_offsets().round_lengths()
            scl=s.read(1,window=win,boundless=True,fill_value=0)
            n8=rasterio.open(http(it.assets['nir08'].href)); nir=n8.read(1,window=win,boundless=True,fill_value=0)
            rs=rasterio.open(http(it.assets['red'].href))
            w10=Window(2*win.col_off,2*win.row_off,2*win.width,2*win.height)
            red=rs.read(1,window=w10,boundless=True,fill_value=0)
        except Exception as e:
            print('skip',it.id,e); continue
        up=lambda x: np.repeat(np.repeat(x,2,0),2,1)[:H10,:W10]
        scl10=up(scl); r_red=rho(red,it,'red')[:H10,:W10]; r_nir=up(rho(nir,it,'nir08'))
        with np.errstate(invalid='ignore',divide='ignore'):
            ndvi=(r_nir-r_red)/np.maximum(1e-6,r_nir+r_red)
        cloudy=np.isin(scl,[3,8,9,10,11,1])  # no-data(0) excluded as in production
        clear=edge_dist(cloudy,20)>=60
        clear10=up(clear)
        seen=(scl10>0)&clear10&~np.isnan(r_red)
        # dark water unstable pixel rule (prereg)
        dark=(r_red<0.01)&(r_nir<0.01)
        seen&=~dark
        plant=(ndvi>=0.30)&seen
        # cell stats
        seen_f=cellfrac(seen.astype(float)); pl_sum=cellfrac(plant.astype(float))
        pf=np.where(seen_f>0,pl_sum/np.maximum(seen_f,1e-9),np.nan)
        pf[seen_f<0.5]=np.nan   # UNKNOWN
        wmask=f_water>=0.9
        nonplant=wmask&(pf<0.5)
        lake_cells=wmask.sum()
        scenes.append(dict(id=it.id,date=it.datetime.date(),pf=pf,seen_lake=np.mean(~np.isnan(pf[wmask])),
          cloud_scl_share=float(np.isin(scl,[3,8,9]).mean())))
        print(it.id,it.datetime.date(),'lake cells seen %.2f'%scenes[-1]['seen_lake'],flush=True)
# merge same-date scenes (same CRS) : first non-nan
bydate=collections.OrderedDict()
for s in scenes:
    if s['date'] in bydate: bydate[s['date']]['pf']=np.where(np.isnan(bydate[s['date']]['pf']),s['pf'],bydate[s['date']]['pf']); bydate[s['date']]['seen_lake']=float(np.mean(~np.isnan(bydate[s['date']]['pf'][f_water>=0.9])))
    else: bydate[s['date']]=s
sc=list(bydate.values())
for s in sc: s['gap']=abs((s['date']-refd).days)
# observers
wm=f_water>=0.9
def accepted(s):
    pf=s['pf']; seen=~np.isnan(pf)
    # A: reads >=50% of non-plant lake water. approx: seen share of lake cells among cells not flagged
    nonplant=wm&((pf<0.5)|np.isnan(pf))
    return float(np.mean(seen[wm]))
obs={}
cand=sorted(sc,key=lambda s:s['gap'])
S=[s for s in cand if s['seen_lake']>=0.75]
obs['S']=S[0]['pf'] if S else None; sinfo=(S[0]['date'].isoformat(),S[0]['gap']) if S else None
A_=[s for s in cand if s['seen_lake']>=0.5]
obs['A']=A_[0]['pf'] if A_ else None; ainfo=(A_[0]['date'].isoformat(),A_[0]['gap']) if A_ else None
acc=[s for s in sc if s['seen_lake']>=0.5 and s['gap']<=21]
if len(acc)>=3:
    stack=np.stack([s['pf'] for s in acc]); import warnings as _w
    with _w.catch_warnings(): _w.simplefilter('ignore'); obs['P']=np.nanmedian(stack,axis=0)
    pinfo=(len(acc),[s['date'].isoformat() for s in acc])
else: obs['P']=obs['A']; pinfo=('INSUFFICIENT',len(acc))
print('S',sinfo,'A',ainfo,'P',pinfo)
bins=[0,15,30,45,60,90,150,300,1e9]
def metrics(flag,pos,neg,sd,label):
    ok=~np.isnan(flag)  # seen
    res={}
    P=pos&ok; N=neg&ok&(sd>=10) if False else neg&ok
    # shore-adjacent excluded: cells within one S2 pixel (10 m) -> shore_d mean <10
    shore_ok=(sd>=10)|np.isnan(sd)
    P=P&shore_ok;N=N&shore_ok
    fl=flag>=0.5
    tp=(fl&P).sum();fn=(~fl&P).sum();fp=(fl&N).sum();tn=(~fl&N).sum()
    # shore-matched reweighting of negatives to positives' histogram
    pd_=sd[P];nd=sd[N];hp,_=np.histogram(np.clip(pd_,0,299.9),bins);hn,_=np.histogram(np.clip(nd,0,299.9),bins)
    w_bin=np.where(hn>0,hp/np.maximum(hn,1),0)/max(1,hp.sum())*hn.sum() if hp.sum() else np.zeros_like(hp,float)
    # weights per negative cell
    idx=np.digitize(np.clip(nd,0,299.9),bins)-1
    wts=np.where(hn[idx]>0,(hp/np.maximum(hp.sum(),1))[idx]/np.maximum(hn/np.maximum(hn.sum(),1),1e-12)[idx],0)
    wfp=float((wts*(fl[N])).sum());wtn=float((wts*(~fl[N])).sum())
    # matched negative count scaled so weights sum to N count
    scale=N.sum()/max(wts.sum(),1e-9); wfp*=scale;wtn*=scale
    prec=tp/max(tp+fp,1);rec=tp/max(tp+fn,1);f1=2*prec*rec/max(prec+rec,1e-9);iou=tp/max(tp+fp+fn,1)
    mprec=tp/max(tp+wfp,1e-9);mf1=2*mprec*rec/max(mprec+rec,1e-9);miou=tp/max(tp+wfp+fn,1e-9)
    fpr=fp/max(fp+tn,1);mfpr=wfp/max(wfp+wtn,1e-9)
    binfo=dict(pos_hist=hp.tolist(),neg_hist=hn.tolist())
    return dict(label=label,bins=binfo,n_pos=int(P.sum()),n_neg=int(N.sum()),tp=int(tp),fn=int(fn),fp=int(fp),tn=int(tn),recall=round(float(rec),3),
      precision_raw=round(float(prec),3),F1_raw=round(float(f1),3),IoU_raw=round(float(iou),3),FPR_raw=round(float(fpr),4),
      precision_matched=round(float(mprec),3),F1_matched=round(float(mf1),3),IoU_matched=round(float(miou),3),FPR_matched=round(float(mfpr),4),
      balanced_acc_matched=round(float((rec+(1-mfpr))/2),3))
res=[]
for oname,fl in obs.items():
    if fl is None: continue
    for tname,(pos,neg) in {'pos=Rf+deep-marsh vs neg=Ow':(pos_all,neg_ow),'pos=Rf only vs neg=Ow':(pos_rf,neg_ow),'pos=Rf+deep-marsh vs neg=Ow+Sv':(pos_all,neg_owsv)}.items():
        m=metrics(fl,pos,neg,shore_d,f'{oname} | {tname}'); res.append(m); print(m)
# Fleet-style: share of open-water cells flagged
json.dump(dict(year=YEAR,ref=REF,collection=coll,S=sinfo,A=ainfo,P=pinfo,n_scenes=len(sc),scene_gaps={s['date'].isoformat():(s['gap'],round(s['seen_lake'],2)) for s in sc},
   truth_cells=dict(pos_all=int(pos_all.sum()),pos_rf=int(pos_rf.sum()),neg_ow=int(neg_ow.sum()),neg_owsv=int(neg_owsv.sum())),results=res),open(OUT+f'pool5_score_{YEAR}.json','w'),indent=1)
