"""NWPS gauge stageflow (30 d) -> daily means in lake-local time, saved to plan/raw/nwps_recent/<LID>.json (live-feed side of the agreement check)."""
import json
from common import *
os.makedirs(f"{PLAN}/raw/nwps_recent", exist_ok=True)
T = json.load(open(f"{PLAN}/targets.json"))
for t in T:
    if t["provider"] != "nwps": continue
    lid = t["station"]; p = f"{PLAN}/raw/nwps_recent/{lid}.json"
    if os.path.exists(p): continue
    try:
        d = json.loads(get(f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}/stageflow", sleep=0.4))
    except Exception as e:
        print(lid, "err", e); continue
    obs = d.get("observed", {})
    json.dump({"tz": obs.get("timeZone"), "pedts": obs.get("pedts"), "data": [(x["validTime"], x["primary"]) for x in obs.get("data", []) if x.get("primary") is not None]}, open(p, "w"))
    print(lid, obs.get("timeZone"), len(obs.get("data", [])))
