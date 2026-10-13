"""Read DSID/DSPM header + meta objects of the three cached Guntersville S-57 base cells (updates NOT applied and applied)."""
import os,sys,pyogrio,glob
R=os.path.expanduser('~/Desktop/Development/Sector_Research_Data/depth-brain/adoption/s57')
for c in ['U37TN306','U37TN361','U37TN391']:
    p=f'{R}/{c}/{c}/{c}.000'
    for upd in ['APPLY','IGNORE']:
        try:
            lyr=[l[0] for l in pyogrio.list_layers(p)] if upd=='APPLY' else None
        except Exception as e: print('err',e)
        print('=====',c,'UPDATES',upd)
        for name in ['DSID','M_COVR','M_QUAL','M_SDAT','M_VDAT','M_NSYS','M_CSCL','M_HOPA','M_NPUB']:
            try:
                df=pyogrio.read_dataframe(p,layer=name,open_options={'UPDATES':upd},use_arrow=False)
            except Exception as e:
                print(name,'-> not readable/absent:',str(e)[:80]); continue
            print(name,len(df))
            if len(df):
                with __import__('pandas').option_context('display.max_columns',None,'display.width',250):
                    print(df.drop(columns='geometry',errors='ignore').T.to_string()[:3500])
