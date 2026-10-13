import json,collections
for c in ['U37TN306','U37TN361','U37TN391']:
    print('=====',c)
    for l,keys in [('DEPTH_AREA',['Depth_Area_Value_1','Depth_Area_Value_2','Source_Date','Source_Indication','Source_Dataset']),
                   ('DEPTH_CONTOUR_LINE',['Value_of_Depth_Contour','Source_Date','Source_Indication','Source_Dataset']),
                   ('DATA_QUALITY_AREA',['Category_of_Zone_Confidence','Technique_of_Sounding_Measurement','Source_Date','Source_Indication']),
                   ('DATA_COVERAGE_AREA',['Category_of_Data_Coverage','Source_Date','Source_Indication']),
                   ('LAKE_AREA',['Object_Name','Information','Source_Date']),
                   ('WATERWAY_GAUGE_POINT',['Object_Name','Category_of_Waterway_Gauge','Elevation','Reference_Gravitational_Level','Value_at_Relevant_High_Water_Level','Name_of_Relevant_High_Water_Level','Value_at_Relevant_Low_Water_Level','Name_at_Relevant_Low_Water_Level','Name_of_Sounding_Reference_Datum_Level','Source_Date']),
                   ('DAM_AREA',['Object_Name','Information'])]:
        try: d=json.load(open(f'{c}_{l}.geojson'))
        except Exception: continue
        cnt=collections.Counter(tuple(str(f['properties'].get(k)) for k in keys) for f in d['features'])
        print('--',l,keys)
        for k,v in cnt.most_common(30): print('  ',v,k)
