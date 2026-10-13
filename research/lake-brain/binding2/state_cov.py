"""Per-state and per-operator-family coverage before/after wave 2 (core = VERIFIED, VERIFIED_CORROBORATED, VERIFIED_ENVELOPE; flagged separate)."""
import json, collections, csv
from common2 import *
out = json.load(open(f"{B2}/assembled_v2.json"))
feat = {r["id"]: r for r in csv.DictReader(open(FEAT))}
CORE = ("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_ENVELOPE")
def tab(keyf):
    t = collections.defaultdict(lambda: dict(n=0, w1core=0, w1flag=0, core=0, flag=0))
    for r in out:
        k = keyf(r); d = t[k]; d["n"] += 1
        d["w1core"] += r["w1Status"] in ("VERIFIED", "VERIFIED_CORROBORATED"); d["w1flag"] += r["w1Status"] == "VERIFIED_FLAG"
        d["core"] += r["bindingStatus"] in CORE; d["flag"] += r["bindingStatus"] == "VERIFIED_FLAG"
    return dict(t)
S = tab(lambda r: r["state"]); O = tab(lambda r: (feat.get(r["lakeId"], {}).get("operator_family") or "?"))
json.dump(dict(state=S, opfam=O), open(f"{B2}/state_cov.json", "w"), indent=1)
print("opfam", O)
for s in ("AK", "CT", "HI", "NH", "ME", "WI", "DE", "RI", "VT", "MA", "MD", "NJ", "PA", "FL", "SC", "MI", "MN"):
    print(s, S.get(s))
