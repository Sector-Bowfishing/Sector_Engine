"""Observer S/A/P recall on UMN taxon-classed points. cwd = umn_sfwmd/. Output out/umn_point_results_{MODE}.csv   usage: e_score_umn.py v1|v1fix"""
import sys; sys.dont_write_bytecode=True
sys.path.insert(0,'scripts'); sys.path.insert(0,'{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness')
import csv,json,math,datetime as dt,collections,numpy as np,warnings,pyproj
warnings.filterwarnings('ignore')
import score_lib as SL
from lakes_cfg import *
MODE=sys.argv[1] if len(sys.argv)>1 else 'v1'
WM=pyproj.Transformer.from_crs("EPSG:4326","EPSG:3857",always_xy=True).transform
pts=list(csv.DictReader(open('out/umn_fleet_points.csv')))
res=[]; 
GROUPS={'surface_strict':lambda p:p['strict']=='1','surface_inclusive':lambda p:p['incl']=='1',
        'submersed_only':lambda p:p['sub']=='1' and p['incl']=='0' and p['other']=='0',
        'submersed_noncanopy_only':lambda p:p['sub']=='1' and p['canopy']=='0' and p['incl']=='0' and p['other']=='0',
        'submersed_canopy_capable_only':lambda p:p['canopy']=='1' and p['subnc']=='0' and p['incl']=='0' and p['other']=='0',
        'no_veg_recorded':lambda p:p['noveg'] in('TRUE','True','1') and p['ntax']=='0'}
for lk in LAKES:
    try: z=np.load(f'out/cells50_{lk}.npz',allow_pickle=True)
    except FileNotFoundError: continue
    z={k:z[k] for k in z.files}; z['ok']=z['ok']
    sc=SL.prep(z,MODE,False)
    left,top,W,H,cell=z['frame']; W=int(W);H=int(H)
    cache={}
    def obs(ref,on):
        k=(ref,on)
        if k not in cache: cache[k]=SL.OBS[on](z,sc,ref)
        return cache[k]
    for p in [p for p in pts if p['lake']==lk]:
        x,y=WM(float(p['lon']),float(p['lat'])); r=int((top-y)//cell); c=int((x-left)//cell)
        if not(0<=r<H and 0<=c<W): continue
        grp=[g for g,f in GROUPS.items() if f(p)]
        if not grp: continue
        y0=int(p['date'][:4])
        for sy,tier in scene_years(y0):
            ref=shift(p['date'],sy)
            for on in 'SAP':
                st,info=obs(ref,on)
                s=int(st[r,c])
                rec=dict(lake=lk,survey=p['survey'],point=p['point'],date=p['date'],sy=sy,tier=tier,obs=on,row=r,col=c,in_lake=bool(z['lake'][r,c]),state=s,
                         gap=info.get('gap'),kind=info.get('kind'),persist=info.get('persistence',''),n_acc=info.get('n_accepted',''),groups='|'.join(grp))
                res.append(rec)
print(len(res))
with open(f'out/umn_point_results_{MODE}.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(res[0])); w.writeheader(); w.writerows(res)
