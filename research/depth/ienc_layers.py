import json,sys,requests
B='https://ienccloud.us/arcgis/rest/services/IENC'
for c in sys.argv[1:]:
    d=requests.get(f'{B}/{c}/MapServer?f=json',timeout=60).json()
    json.dump(d,open(f'ms_{c}.json','w'))
    print(c, d.get('error') or [(l['id'],l['name']) for l in d.get('layers',[])])
