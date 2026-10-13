"""Which fleet lakes intersect a USACE IENC chart footprint? (research only)
Footprints: ienccloud.us ArcGIS REST IENC_Chart_Footprints_2025 layer 0 (109 charts).
Lake polygons: Lake Brain research cache (599 of 621). Lakes without polygon use a 1 km point buffer, flagged.
"""
import json, gzip, os, sys, requests, geopandas as gpd, pandas as pd
R = os.path.expanduser('~/Desktop/Development/Sector_Research_Data')
OUT = R + '/depth-brain/ienc'
url = 'https://ienccloud.us/arcgis/rest/services/IENC/IENC_Chart_Footprints_2025/MapServer/0/query'
r = requests.get(url, params=dict(where='1=1', outFields='*', f='geojson', outSR=4326), timeout=120)
open(OUT + '/footprints.geojson', 'wb').write(r.content)
fp = gpd.read_file(OUT + '/footprints.geojson')
fp['chart'] = fp['Feature_ID'] if 'Feature_ID' in fp else fp.index
feat = pd.read_csv('/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data/lake_features.csv')
polys = gpd.read_file(gzip.open(R + '/lake-brain/geometry/engine_polygons_599.geojson.gz'))
print(polys.columns.tolist()[:12], len(polys))
idcol = 'id' if 'id' in polys.columns else polys.columns[0]
polys = polys.set_crs(4326, allow_override=True)
have = set(polys[idcol])
pts = feat[~feat.id.isin(have)]
pg = gpd.GeoDataFrame(pts[['id']], geometry=gpd.points_from_xy(pts.lon, pts.lat), crs=4326).to_crs(5070)
pg['geometry'] = pg.buffer(1000); pg = pg.to_crs(4326); pg['geom_src'] = 'point_buffer_1km'
polys = polys[[idcol, 'geometry']].rename(columns={idcol: 'id'}); polys['geom_src'] = 'polygon'
allg = pd.concat([polys, pg[['id', 'geometry', 'geom_src']]])
allg = gpd.GeoDataFrame(allg, crs=4326)
j = gpd.sjoin(allg, fp[['Source_Date', 'Source_Indication', 'Source_Dataset', 'Category_of_Data_Coverage', 'geometry']], how='inner', predicate='intersects')
g = j.groupby('id').agg(n_charts=('index_right', 'nunique'), src_dates=('Source_Date', lambda s: ';'.join(sorted(set(map(str, s))))), geom_src=('geom_src', 'first')).reset_index()
g = g.merge(feat[['id', 'name', 'state1', 'area_km2', 'operator_family']], on='id')
g.to_csv(os.path.expanduser('~/Desktop/Development/Sector_Engine-depth-research/docs/research/depth-brain/data/ienc_fleet_overlap.csv'), index=False)
print('fleet lakes intersecting IENC footprint:', len(g), 'of', len(feat))
print(g.state1.value_counts().to_dict())
print(g.sort_values('area_km2', ascending=False).head(40)[['name', 'state1', 'area_km2', 'n_charts', 'src_dates', 'geom_src']].to_string())
print(fp[['Source_Date', 'Source_Indication', 'Source_Dataset']].describe(include='all').T)
