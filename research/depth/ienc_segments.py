"""Relate shipped Guntersville segments to IENC depth areas: why are 2,133 'unavailable'? Research only."""
import gzip,json,os,collections,geopandas as gpd,pandas as pd
R=os.path.expanduser('~/Desktop/Development/Sector_Research_Data'); A=R+'/depth-brain/adoption/'
seg=json.load(gzip.open(os.path.expanduser('~/Desktop/Development/iOS/sector-intel-phase3/Sector/Assets.xcassets/FishIntel/GuntersvilleSegmentGeometry.dataset/Guntersville.segments.geojson.gz')))
g=gpd.GeoDataFrame.from_features(seg['features'],crs=4326)
cells=['U37TN306','U37TN361','U37TN391']
da=pd.concat([gpd.read_file(A+f'{c}_DEPTH_AREA.geojson').assign(cell=c) for c in cells]).set_crs(4326,allow_override=True)
da['cls']=da.Depth_Area_Value_1.astype(str)+'-'+da.Depth_Area_Value_2.astype(str)
da['yr']=da.Source_Date.astype(str).str[:4]
g5=g.to_crs(5070); da5=da.to_crs(5070)
g5['cent']=g5.geometry.centroid
pts=g5.set_geometry('cent')[['id','depthClass','depthStatus','littoralBoundary','lakeRegion','basinClass','shorelineLengthM','cent']]
# nearest depth area within 150 m (segment centroid is on shoreline-adjacent littoral)
j=gpd.sjoin_nearest(pts,da5[['cls','yr','cell','geometry']],how='left',max_distance=150,distance_col='d')
j=j.drop_duplicates('id')
print('segments by shipped class x nearest DEPARE (<=150 m) class/year/cell')
print(j.groupby(['depthClass',j.cls.fillna('none'),j.yr.fillna('none')]).size())
print(j.groupby(['depthClass',j.cell.fillna('none')]).size())
# total shoreline length by class
print(j.groupby('depthClass').shorelineLengthM.sum()/1000)
# unavailable: where? by lat bands and region
ll=gpd.GeoSeries(pts.cent,crs=5070).to_crs(4326)
j['lat']=ll.y.values; j['lon']=ll.x.values
un=j[j.depthClass=='unknown']
print('unavailable lat quantiles',un.lat.quantile([0,.1,.5,.9,1]).round(3).tolist())
print('all lat quantiles',j.lat.quantile([0,.1,.5,.9,1]).round(3).tolist())
print('unavailable by lakeRegion top'); print(un.lakeRegion.value_counts().head(12))
print('unavailable by basinClass'); print(un.basinClass.value_counts())
print('share unavailable by basinClass'); print((j.groupby('basinClass').apply(lambda d:(d.depthClass=='unknown').mean())).round(3))
# footprint of each chart cell: unavailable by lon bins
j['lonbin']=pd.cut(j.lon,[-87,-86.3,-86.0,-85.8,-85.6,-85.0])
print(j.groupby('lonbin',observed=True).apply(lambda d: pd.Series({'n':len(d),'unavail':(d.depthClass=='unknown').sum(),'shallow':(d.depthClass=='shallow').sum(),'deep':(d.depthClass=='deep').sum()})))
# distance of unavailable centroids to nearest DEPARE
j2=gpd.sjoin_nearest(pts,da5[['geometry']],how='left',distance_col='dist').drop_duplicates('id')
print('dist to nearest DEPARE (m) by class'); print(j2.groupby('depthClass').dist.describe().round(1))
j.drop(columns='cent').to_csv(A+'seg_vs_depare.csv',index=False)
