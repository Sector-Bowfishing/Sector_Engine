"""Target list: bound lakes (core + flagged) without >= 5 complete years in verified.csv."""
import json
from common import *
rows = bound()
T = []
for r in rows:
    y = int(float(r["completeYears"] or 0))
    if y < 5:
        T.append({k: r[k] for k in ("lakeId", "name", "state", "operator", "bindingStatus", "provider", "station", "loc", "series", "histSeries", "firstYear", "completeYears", "historyClass", "medFt", "fullPoolFt")})
json.dump(T, open(f"{PLAN}/targets.json", "w"), indent=1)
print(len(T))
import collections
print(collections.Counter((t["bindingStatus"], t["provider"]) for t in T))
