import gzip,os,geopandas as gpd,pandas as pd
R=os.path.expanduser('~/Desktop/Development/Sector_Research_Data'); A=R+'/depth-brain/adoption/'
polys=gpd.read_file(gzip.open(R+'/lake-brain/geometry/engine_polygons_599.geojson.gz'))
idc='id' if 'id' in polys.columns else polys.columns[0]
L=polys[polys[idc]=='Guntersville|AL'].set_crs(4326,allow_override=True).to_crs(5070)
Lg=L.geometry.union_all().buffer(200)
d=gpd.read_file(A+'U37TN391_DEPTH_CONTOUR_LINE.geojson').set_crs(4326,allow_override=True).to_crs(5070)
d['yr']=d.Source_Date.astype(str).str[:4]
for y,g in d.groupby('yr'):
    c=g.geometry.union_all(); inside=c.intersection(Lg).length/1000
    cc=gpd.GeoSeries([c.centroid],crs=5070).to_crs(4326).iloc[0]
    print(y,len(g),'km',round(c.length/1000,1),'km within 200m of Guntersville polygon',round(inside,1),'centroid lat/lon',round(cc.y,3),round(cc.x,3))
da=gpd.read_file(A+'U37TN391_DEPTH_AREA.geojson').set_crs(4326,allow_override=True).to_crs(5070)
da['yr']=da.Source_Date.astype(str).str[:4]
for y,g in da.groupby('yr'):
    c=g.geometry.union_all(); print('DEPARE',y,round(c.area/1e6,3),'km2; inside Guntersville polygon',round(c.intersection(L.geometry.union_all()).area/1e6,3))
