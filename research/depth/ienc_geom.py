"""Areas of Guntersville IENC depth/coverage polygons vs lake polygon. Research only."""
import json, gzip, os, geopandas as gpd, pandas as pd
R=os.path.expanduser('~/Desktop/Development/Sector_Research_Data')
A=R+'/depth-brain/adoption/'
def load(c,l):
    g=gpd.read_file(A+f'{c}_{l}.geojson'); g['cell']=c; return g.set_crs(4326,allow_override=True)
cells=['U37TN306','U37TN361','U37TN391']
da=pd.concat([load(c,'DEPTH_AREA') for c in cells]); da=gpd.GeoDataFrame(da,crs=4326).to_crs(5070)
da['km2']=da.area/1e6
da['cls']=da.Depth_Area_Value_1.astype(str)+'-'+da.Depth_Area_Value_2.astype(str)+' '+da.Source_Indication.str.slice(-30)
print(da.groupby(['cell','cls']).km2.agg(['count','sum']).round(3))
cv=pd.concat([load(c,'DATA_COVERAGE_AREA') for c in cells]); cv=gpd.GeoDataFrame(cv,crs=4326).to_crs(5070); cv['km2']=cv.area/1e6
print(cv.groupby(['cell','Category_of_Data_Coverage']).km2.agg(['count','sum']).round(2))
polys=gpd.read_file(gzip.open(R+'/lake-brain/geometry/engine_polygons_599.geojson.gz'))
idc='id' if 'id' in polys.columns else polys.columns[0]
lake=polys[polys[idc]=='Guntersville|AL'].set_crs(4326,allow_override=True).to_crs(5070)
print('lake polygon km2',lake.area.sum()/1e6)
L=lake.geometry.union_all()
# charted: union of all depth areas (clipped to lake)
for c in cells+['ALL']:
    d=da if c=='ALL' else da[da.cell==c]
    u=d.geometry.union_all()
    print(c,'DEPARE union km2',round(u.area/1e6,2),'inside lake',round(u.intersection(L).area/1e6,2),'share of lake',round(u.intersection(L).area/L.area,3))
uall=da.geometry.union_all()
by={}
for key,sub in da.groupby(da.Depth_Area_Value_1.astype(str)+'-'+da.Depth_Area_Value_2.astype(str)+'|'+da.Source_Date.astype(str)):
    u=sub.geometry.union_all().intersection(L); by[key]=round(u.area/1e6,2)
print('inside-lake km2 by class|date',by)
print('lake uncovered by any DEPARE km2', round(L.difference(uall).area/1e6,2))
# 'No Coverage' polygons
nc=cv[cv.Category_of_Data_Coverage=='No Coverage'].geometry.union_all()
print('No Coverage ∩ lake km2',round(nc.intersection(L).area/1e6,2))
# lake bbox for reference
print(lake.to_crs(4326).total_bounds)
