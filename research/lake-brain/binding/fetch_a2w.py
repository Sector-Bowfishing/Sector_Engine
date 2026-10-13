"""USACE Access2Water reporting API (https://water.usace.army.mil/cda/reporting/): all districts' locations with latest values, levels, NIDID aliases."""
import json, os
from common import *
os.makedirs(f"{RAW}/a2w", exist_ok=True)
B = "https://water.usace.army.mil/cda/reporting"
s, provs = get_json(f"{B}/providers", timeout=60)
json.dump(provs, open(f"{RAW}/a2w/providers.json", "w"))
tot = 0
for p in provs:
    if p["type"] != "dis":
        continue
    f = f"{RAW}/a2w/locations_{p['slug']}.json"
    if os.path.exists(f):
        continue
    s, d = get_json(f"{B}/providers/{p['slug']}/locations", timeout=180, sleep=0.6)
    if d is None:
        print(p["slug"], "fail", s); continue
    json.dump(d, open(f, "w")); tot += len(d)
    print(p["slug"], len(d), sum(1 for x in d if x.get("kind") == "PROJECT"), flush=True)
print("total", tot)
