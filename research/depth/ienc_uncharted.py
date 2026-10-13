import gzip,os,geopandas as gpd,pandas as pd
R=os.path.expanduser('~/Desktop/Development/Sector_Research_Data'); A=R+'/depth-brain/adoption/'
polys=gpd.read_file(gzip.open(R+'/lake-brain/geometry/engine_polygons_599.geojson.gz'))
idc='id' if 'id' in polys.columns else polys.columns[0]
L=polys[polys[idc]=='Guntersville|AL'].set_crs(4326,allow_override=True).to_crs(5070).geometry.union_all()
cells=['U37TN306','U37TN361','U37TN391']
da=pd.concat([gpd.read_file(A+f'{c}_DEPTH_AREA.geojson') for c in cells]).set_crs(4326,allow_override=True).to_crs(5070)
unc=gpd.GeoDataFrame(geometry=[L.difference(da.geometry.union_all())],crs=5070).explode(index_parts=False)
unc['km2']=unc.area/1e6
unc=unc.sort_values('km2',ascending=False)
print('pieces',len(unc),'total km2',unc.km2.sum().round(2)); print(unc.km2.head(10).round(2).tolist())
print('pieces >0.5 km2:',(unc.km2>0.5).sum(),'area',unc[unc.km2>0.5].km2.sum().round(2),' >0.05:',unc[unc.km2>0.05].km2.sum().round(2))
c=unc.head(8).geometry.centroid.to_crs(4326); print([(round(p.y,3),round(p.x,3)) for p in c])
# channel-only test: width of deep polygon area vs lake
deep=da[da.Depth_Area_Value_2.astype(str)=='Unknown'].geometry.union_all()
print('deep(2.74-Unknown) km2 inside lake',round(deep.intersection(L).area/1e6,1),'share',round(deep.intersection(L).area/L.area,3))
sh=da[da.Depth_Area_Value_2.astype(str)!='Unknown'].geometry.union_all()
print('0-2.74 km2 inside lake',round(sh.intersection(L).area/1e6,1),'share',round(sh.intersection(L).area/L.area,3))
print('charted share of lake',round(1-unc.km2.sum()*1e6/L.area,3))
