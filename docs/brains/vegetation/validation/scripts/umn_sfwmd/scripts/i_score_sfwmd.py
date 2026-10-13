"""Score S/A/P observers against SFWMD littoral polygons (historical substitute truth). cwd = umn_sfwmd/
usage: i_score_sfwmd.py MODE(v1|v1fix) -> out/sfwmd_scores_{MODE}.json"""
import sys; sys.dont_write_bytecode=True
sys.path.insert(0,'scripts'); sys.path.insert(0,'{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness')
import json,math,datetime as dt,collections,numpy as np,warnings,pyproj
warnings.filterwarnings('ignore')
from scipy import ndimage
from shapely.geometry import shape
from shapely.ops import transform as sh_transform
from rasterio.features import rasterize
from rasterio import Affine
import score_lib as SL
from lakes_cfg import *
MODE=sys.argv[1]
T=pyproj.Transformer.from_crs(4326,3857,always_xy=True).transform
SS=5   # supersample factor (10 m merc sub-cells per 50 m cell)
# ---- class groups ----------------------------------------------------------------------------------------------------------------
OKE_FLOAT={'MFF','MFFe','MFFh','MFFli'}; OKE_CAT={'MFGtD','MFGtM','MFGtS','MFGtDT'}
OKE_HERB={'MFGe','MFH','MFG','MFGc','MFGh','MFGhT','MFB','MFBt','MFBp','MFBs','MFHp','MFGr','MFGsc','MFGs','MFGa','MFGpa','MSGs','EpD','EpDT','EG','Eo','Eal'}
OKE_WOODY={'CSs','SS','SSm','SSa','SSl','SSc','SSb','SSh','Ssam','CSsH','CSsE','FS','EsD','TV'}
def oke_group(p):
    c=p.get('VEGLABEL1_CODE')
    if c=='OW': return 'OW'
    if c in OKE_FLOAT: return 'FLOAT'
    if c in OKE_CAT: return 'CATTAIL'
    if c in OKE_HERB: return 'HERB'
    if c in OKE_WOODY: return 'WOODY'
    if c=='SAV': return 'SAV'
    return 'OTHER'            # MFO open-water marsh, TREATED, canal, levee, spoil, residential, sand ... excluded from both pos and neg
KC_FLOAT={'6440','6442','6445'}; KC_EMERG={'6410','6412','6414','6420','6421','6423','6424'}; KC_WOODY={'6181','6301','6417','1000'}
def kc_group(p):
    c=str(p.get('FLUCCS_CODE')).split('-')[0].strip()
    if c=='5200': return 'OW'
    if c in KC_FLOAT: return 'FLOAT'
    if c=='6412': return 'CATTAIL'
    if c in KC_EMERG: return 'HERB'
    if c in KC_WOODY: return 'WOODY'
    if c=='6450': return 'SAV'
    return 'OTHER'
GROUPS=['OW','FLOAT','CATTAIL','HERB','WOODY','SAV','OTHER']
CFG={'Okeechobee_FL':dict(files=['VEG_OKE_2015','VEG_OKE_2016'],grp=oke_group,assumed_neg=False,label='Lake Okeechobee marsh (2015 NW + 2016 Moore Haven/south islands, 1 ha dominant-type grid)'),
     'Kissimmee_FL':dict(files=['VEG_KCOL_2015'],grp=kc_group,assumed_neg=False,label='Lake Kissimmee littoral (June 2015)'),
     'Tohopekaliga_Toho_FL':dict(files=['VEG_KCOL_2016'],grp=kc_group,assumed_neg=False,label='Lake Tohopekaliga littoral (April 2016; registry key holds the same polygon as East_Lake_Tohopekaliga_FL)')}
BINS=SL.BINS
def truth_fracs(lk,z):
    left,top,W,H,cell=z['frame']; W=int(W);H=int(H); tr=Affine(cell/SS,0,left,0,-cell/SS,top)
    c=CFG[lk]; shapes=[]
    for fn in c['files']:
        d=json.load(open(f'out/sfwmd/{fn}.geojson'))
        if lk=='Tohopekaliga_Toho_FL': feats=[f for f in d['features'] if f['properties'].get('AREA_NAME')=='LAKE TOHOPEKALIGA']
        else: feats=d['features']
        for f in feats:
            g=f['geometry']
            if not g: continue
            gm=sh_transform(T,shape(g))
            if gm.bounds[2]<left or gm.bounds[0]>left+W*cell or gm.bounds[3]<top-H*cell or gm.bounds[1]>top: continue
            shapes.append((gm,1+GROUPS.index(c['grp'](f['properties']))))
    lab=rasterize(shapes,out_shape=(H*SS,W*SS),transform=tr,fill=0,dtype='uint8')
    fr={}
    for i,gn in enumerate(GROUPS): fr[gn]=(lab==i+1).reshape(H,SS,W,SS).mean(axis=(1,3)).astype('float32')
    fr['mapped']=(lab>0).reshape(H,SS,W,SS).mean(axis=(1,3)).astype('float32')
    return fr
def counts(st,pos,neg,w):
    flag=st==SL.FLAG; known=(st==SL.CLEAR)|flag
    return dict(tp=int((flag&pos).sum()),fn_known=int((~flag&known&pos).sum()),pos_unknown=int((~known&pos).sum()),npos=int(pos.sum()),fp=int((flag&neg).sum()),tn=int((~flag&known&neg).sum()),
        neg_unknown=int((~known&neg).sum()),nneg=int(neg.sum()),fpw=float((w*(flag&neg)).sum()),tnw=float((w*(~flag&known&neg)).sum()))
def metrics(d):
    tp,fp=d['tp'],d['fp']; fn_all=d['npos']-tp; kn=tp+d['fn_known']
    P=tp/(tp+fp) if tp+fp else None; R_all=tp/d['npos'] if d['npos'] else None; R_kn=tp/kn if kn else None
    F=2*P*R_all/(P+R_all) if P and R_all and P+R_all>0 else None; I=tp/(tp+fp+fn_all) if tp+fp+fn_all else None
    Pm=tp/(tp+d['fpw']) if tp+d['fpw']>0 else None
    Fm=2*Pm*R_all/(Pm+R_all) if Pm and R_all and Pm+R_all>0 else None
    Im=tp/(tp+d['fpw']+fn_all) if tp+d['fpw']+fn_all>0 else None
    # F1/IoU on known cells only (UNKNOWN positives dropped, not counted as misses)
    Fk=2*Pm*R_kn/(Pm+R_kn) if Pm and R_kn and Pm+R_kn>0 else None
    return dict(precision_raw=P,precision_matched_50prev=Pm,recall_known=R_kn,recall_all=R_all,F1_matched_unknown_as_miss=Fm,F1_matched_known_only=Fk,IoU_matched=Im,F1_raw=F,IoU_raw=I,
                FPR_raw_known=fp/(fp+d['tn']) if fp+d['tn'] else None,pos_unknown_share=d['pos_unknown']/d['npos'] if d['npos'] else None,neg_unknown_share=d['neg_unknown']/d['nneg'] if d['nneg'] else None)
res={}
for lk in CFG:
    try: z=dict(np.load(f'out/cells50_{lk}.npz',allow_pickle=True))
    except FileNotFoundError: print('missing',lk); continue
    import os
    if not all(os.path.exists(f'out/sfwmd/{x}.geojson') for x in CFG[lk]['files']): print('truth missing',lk); continue
    fr=truth_fracs(lk,z); lake=z['lake']; cl=z['clarity']; gm=float(z['ground_m'])
    pos_frac=fr['FLOAT']+fr['CATTAIL']+fr['HERB']
    pos=(pos_frac>=0.5)&lake
    if CFG[lk]['assumed_neg']:
        near=ndimage.distance_transform_edt(~((fr['mapped']>0.02)))*gm        # distance to any mapped community (m)
        neg=lake&(fr['mapped']<0.02)&(near>100)&(near<=600)                   # ASSUMED open water within the surveyed littoral reach
    else:
        neg=(fr['OW']>=0.9)&lake
    dist=ndimage.distance_transform_edt(lake)*gm; bins=np.digitize(dist,BINS[1:-1])
    sc=SL.prep(z,MODE,False)
    info=dict(label=CFG[lk]['label'],cells_lake=int(lake.sum()),cells_clarity=int(cl.sum()),pos_cells_in_lake=int(pos.sum()),pos_cells_reachable=int((pos&cl).sum()),
        pos_in_shore_band=int((pos&~cl).sum()),neg_cells=int((neg&cl).sum()),cell_ground_m=gm,ha_per_cell=gm*gm/1e4,
        truth_ha={g:float(fr[g].sum()*gm*gm/1e4) for g in GROUPS}, pos_ha_in_lake=float(pos.sum()*gm*gm/1e4),
        pos_veg_ha_all_mapped=float(((fr['FLOAT']+fr['CATTAIL']+fr['HERB']).sum())*gm*gm/1e4),
        float_pos=int(((fr['FLOAT']>=0.5)&lake).sum()),cattail_pos=int(((fr['CATTAIL']>=0.5)&lake).sum()))
    # positives by distance-to-edge bin
    info['pos_by_bin']=np.bincount(bins[pos],minlength=len(BINS)-1)[:len(BINS)-1].tolist(); info['neg_by_bin_reach']=np.bincount(bins[neg&cl],minlength=len(BINS)-1)[:len(BINS)-1].tolist()
    nb=len(BINS)-1; ph=np.bincount(bins[pos&cl],minlength=nb)[:nb].astype(float); nh=np.bincount(bins[neg&cl],minlength=nb)[:nb].astype(float)
    wb=np.where(nh>0,ph/np.maximum(nh,1),0.0); w=wb[bins]
    info['matchable_pos_share']=float(ph[nh>0].sum()/max(ph.sum(),1))
    info['scenes']=[]
    ref0=CFG_REF=None
    cfgref=FL_CFG[lk]['refs'][0]; out={}
    for sy in FL_CFG[lk]['years']:
        ref=shift(cfgref,sy)
        for on,fn in SL.OBS.items():
            st,inf=fn(z,sc,ref)
            subs={'ALL':pos&cl,'FLOAT':((fr['FLOAT']>=0.5)&lake&cl),'CATTAIL':((fr['CATTAIL']>=0.5)&lake&cl)}
            d=counts(st,pos&cl,neg&cl,w); m=metrics(d)
            m['counts']=d; m['scene']={k:v for k,v in inf.items() if k!='A'}
            m['refusal_pos_reach']={SL.NAMES[c]:int(((st==c)&pos&cl).sum()) for c in SL.NAMES}
            m['refusal_neg_reach']={SL.NAMES[c]:int(((st==c)&neg&cl).sum()) for c in SL.NAMES}
            # whole-lake recall: shore-band positives count as misses
            m['recall_wholelake']=d['tp']/max(1,int(pos.sum()))
            m['sub_recall']={}
            for sn,sm in subs.items():
                f=(st==SL.FLAG)&sm; k=sm&((st==SL.CLEAR)|(st==SL.FLAG)); m['sub_recall'][sn]=dict(n=int(sm.sum()),flag=int(f.sum()),recall_known=float(f.sum()/max(1,k.sum())),recall_all=float(f.sum()/max(1,sm.sum())))
            # unmatched-by-bin recall for reachable positives
            m['recall_by_bin']=[dict(bin=f'{BINS[i]}-{BINS[i+1] if i<nb-1 else "inf"}',n=int(((bins==i)&pos&cl).sum()),flag=int(((bins==i)&pos&cl&(st==SL.FLAG)).sum())) for i in range(nb)]
            # open-water flag share: ALL neg cells
            out[f'{sy}|{on}']=m
    info['results']=out; res[lk]=info
json.dump(res,open(f'out/sfwmd_scores_{MODE}.json','w'),indent=1,default=float)
f=lambda x:'n/a' if x is None else f'{x:.2f}'
for lk,i in res.items():
    print(lk,{k:i[k] for k in ['cells_lake','pos_cells_in_lake','pos_cells_reachable','pos_in_shore_band','neg_cells','float_pos','cattail_pos','matchable_pos_share']})
    for k,m in i['results'].items(): print('  ',k,'P_m',f(m['precision_matched_50prev']),'P_raw',f(m['precision_raw']),'R_known',f(m['recall_known']),'R_all',f(m['recall_all']),'F1m',f(m['F1_matched_unknown_as_miss']),'IoUm',f(m['IoU_matched']),'FPRraw',f(m['FPR_raw_known']),'posUNK',f(m['pos_unknown_share']),m['scene'].get('kind'),m['scene'].get('gap'))
