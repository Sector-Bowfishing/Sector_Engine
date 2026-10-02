"""Stage 12: corpus rows (<= 2025-12-31) with their ACOLITE BEST samples. S2C rows carry the adopted operational
harmonisation (harm/score_tandem.json 'adopted_operational_method': 'vop' = the TOA-harmonised run, 'vrhow' = the
production rhow coefficients on the raw run) and keep the raw values for the platform comparison. Writes rows12.json."""
import json, glob, os, math
from common12 import *
rows = [x for x in json.load(open(f"{S}/stage11/corpus/corpus.json")) if x["date"] <= "2025-12-31"]
T = json.load(open(f"{D12}/harm/score_tandem.json")) if os.path.exists(f"{D12}/harm/score_tandem.json") else None
method = T["adopted_operational_method"] if T else None
VR = T["production_vrhow_coef"] if T else None
samp = {}
for f in glob.glob(f"{D12}/corpus/res/*.json"):
    r = json.load(open(f))
    for c in r.get("crops", []):
        for pid, p in ((c.get("raw") or {}).get("points") or {}).items():
            samp.setdefault(pid, {})["raw"] = p
        for pid, p in ((c.get("harm_vop") or {}).get("points") or {}).items():
            samp.setdefault(pid, {})["vop"] = p
    samp.setdefault("_items", {})[r["item"]] = {"l1c": r.get("l1c"), "error": r.get("error")}
def valid(p): return bool(p) and p.get("n", 0) >= 5 and all(isinstance(p.get(b), (int, float)) and math.isfinite(p[b]) for b in ("B02", "B03", "B04", "B05"))
def vrhow(p):
    q = dict(p)
    for b, c in VR.items():
        if b not in p or not isinstance(p.get(b), (int, float)): continue
        v = c["g"] * p[b] + c["o"]
        if b == "B05": v += c["k"] * (p.get("B06", 0) - p.get("B04", 0))
        q[b] = v
    return q
out = []
for x in rows:
    s = samp.get(x["id"], {}); raw = s.get("raw")
    y = {k: x[k] for k in ("id", "set", "lake", "lat", "lon", "date", "secchi", "turb", "chl", "fnu", "sun_elev", "dt", "platform", "item", "state") if k in x}
    y["sen2cor"] = {k: x["raw"].get(k) for k in ("blue", "green", "red", "re1", "swir16")}
    y["gunt"] = gunt(x); y["insitu_type"] = insitu_type(x); y["processed"] = x["item"] in samp["_items"]
    y["aco_raw"] = {b: raw.get(b) for b in BANDS + ["n"]} if raw else None
    y["aco_raw_valid"] = valid(raw)
    if x["platform"] == "sentinel-2c" and method:
        op = s.get("vop") if method == "vop" else (vrhow(raw) if raw else None)
    else:
        op = raw
    y["aco"] = {b: op.get(b) for b in BANDS + ["n"]} if op else None
    y["aco_valid"] = valid(op)
    out.append(y)
json.dump(out, open(f"{D12}/analysis/rows12.json", "w"))
print(len(out), "rows;", sum(y["processed"] for y in out), "processed;", sum(y["aco_valid"] for y in out), "valid ACOLITE;",
      "S2C method", method, sum(1 for y in out if y["platform"] == "sentinel-2c"), "S2C rows")
