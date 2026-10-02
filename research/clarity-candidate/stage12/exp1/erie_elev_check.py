"""Addendum C check: K4 with ACOLITE elevation (USGS 3DEP) on the 10 Lake Erie AERONET-OC matchups; results go into
exp1/res/<job>.json as config 'K4e' (does not alter the K0-K4 results)."""
import json, sys, os
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage12/exp1"); sys.argv = ["x"]
import run_exp1 as R
E = json.load(open(f"{S}/stage12/corpus/elevations.json"))
T = [t for t in R.tasks() if t["kind"] == "aeronet" and "Erie" in t["task"]]
for t in T:
    el = E.get(f"{t['lat']},{t['lon']}")
    R.K["K4e"] = {"dsf_interface_reflectance": True, "dsf_interface_option": "ffss_boa", **({"elevation": el} if el is not None else {})}
    t["configs"] = ["K4e"]
    print(R.one(t), el, flush=True)
