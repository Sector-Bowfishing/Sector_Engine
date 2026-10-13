"""V7: does NBM P90 speed give a usable 'breezy risk' flag for tonight? (see prereg addendum 2)"""
import json, os, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.expanduser("~/Desktop/Development/Sector_Engine-wind/jobs/wind-hourly"))
import numpy as np
from sector_wind.store import LocalStore
from sector_wind.ingest import load_config
from sector_wind.interp import CutoutIndex, blend
from sector_wind.validate import load_obs
from sector_wind.sample import parse_iso
MPH = 0.44704
ROOT = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50")
S, E = datetime(2026, 5, 6, tzinfo=timezone.utc), datetime(2026, 10, 6, 23, tzinfo=timezone.utc)
store, cfg = LocalStore(ROOT), load_config()
obs = load_obs(store, S - timedelta(days=1), E + timedelta(days=2))
by = defaultdict(list)
for sid, s in cfg["stations"].items(): by[s["lake"]].append(sid)
idx, rows = {}, []
t = S
while t <= E:
    if t.hour in (12, 18):
        for lake in cfg["lakes"]:
            c = store.get_json(f"nbm/{lake}/{t:%Y%m%d%H}.json.gz")
            if not c: continue
            if lake not in idx:
                g = store.get_json(c["grid"]); ci = CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"])
                idx[lake] = {s: ci.weights(cfg["stations"][s]["lat"], cfg["stations"][s]["lon"]) for s in by[lake]}
            for stp in c["steps"]:
                vt = parse_iso(stp["validTime"]); lead = stp["leadHours"]
                if not ((t.hour == 12 and lead in (12, 18)) or (t.hour == 18 and lead in (6, 12))): continue
                if "speedP90" not in stp: continue
                for sid, wt in idx[lake].items():
                    o = obs.get((sid, vt))
                    if o: rows.append((blend(stp["speedMS"], wt) / MPH, blend(stp["speedP90"], wt) / MPH, o["speedMS"] / MPH))
    t += timedelta(hours=1)
A = np.array(rows); res = {"n": len(A)}
for thr in (10, 8):
    flag, ev = A[:, 1] >= thr, A[:, 2] >= thr
    res[f"obs>={thr}"] = {"flagShare": round(float(flag.mean()), 4), "obsRate": round(float(ev.mean()), 4),
        "P(ev|flag)": round(float(ev[flag].mean()), 3) if flag.any() else None, "P(ev|noflag)": round(float(ev[~flag].mean()), 4),
        "POD": round(float((flag & ev).sum() / max(ev.sum(), 1)), 3), "FAR": round(float((flag & ~ev).sum() / max(flag.sum(), 1)), 3),
        "lift": round(float(ev[flag].mean() / max(ev[~flag].mean(), 1e-9)), 1) if flag.any() else None, "nEvents": int(ev.sum()), "nFlag": int(flag.sum())}
    p50 = A[:, 0] >= thr
    res[f"obs>={thr}"]["compare_P50_flag"] = {"POD": round(float((p50 & ev).sum() / max(ev.sum(), 1)), 3), "FAR": round(float((p50 & ~ev).sum() / max(p50.sum(), 1)), 3), "nFlag": int(p50.sum())}
print(json.dumps(res, indent=1)); json.dump(res, open(sys.argv[1], "w"), indent=1)
