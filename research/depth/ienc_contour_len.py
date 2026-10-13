import os,geopandas as gpd,pandas as pd
A=os.path.expanduser('~/Desktop/Development/Sector_Research_Data/depth-brain/adoption/')
d=pd.concat([gpd.read_file(A+f'{c}_DEPTH_CONTOUR_LINE.geojson').assign(cell=c) for c in ['U37TN306','U37TN361','U37TN391']]).set_crs(4326,allow_override=True).to_crs(5070)
d['km']=d.length/1000; d['yr']=d.Source_Date.astype(str).str[:4]
print(d.groupby(['cell','yr']).km.agg(['count','sum']).round(1)); print('total km',round(d.km.sum(),1)); print(d.groupby('yr').km.sum().round(1))
