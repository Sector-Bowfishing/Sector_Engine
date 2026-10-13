import gzip,os,geopandas as gpd,pandas as pd
R=os.path.expanduser('~/Desktop/Development/Sector_Research_Data'); A=R+'/depth-brain/adoption/'
polys=gpd.read_file(gzip.open(R+'/lake-brain/geometry/engine_polygons_599.geojson.gz'))
idc='id' if 'id' in polys.columns else polys.columns[0]
L=polys[polys[idc]=='Guntersville|AL'].set_crs(4326,allow_override=True).to_crs(5070).geometry.union_all()
cells=['U37TN306','U37TN361','U37TN391']
def ld(l): return pd.concat([gpd.read_file(A+f'{c}_{l}.geojson') for c in cells if os.path.exists(A+f'{c}_{l}.geojson')]).set_crs(4326,allow_override=True).to_crs(5070)
da=ld('DEPTH_AREA').geometry.union_all()
for l in ['LAKE_AREA','RIVERS_AREA']:
    g=ld(l).geometry.union_all(); print(l,'km2',round(g.area/1e6,1),'∩lake',round(g.intersection(L).area/1e6,1),' DEPARE∩',l,round(da.intersection(g).area/1e6,1),' of which lake-uncharted', round(g.intersection(L).difference(da).area/1e6,1))
w=ld('LAKE_AREA').geometry.union_all().union(ld('RIVERS_AREA').geometry.union_all())
print('LAKARE∪RIVERS ∩ lake',round(w.intersection(L).area/1e6,1),'; lake outside LAKARE∪RIVERS',round(L.difference(w).area/1e6,1),'; DEPARE outside LAKARE∪RIVERS ∩ lake', round(da.difference(w).intersection(L).area/1e6,1))
